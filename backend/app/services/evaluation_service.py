from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidSessionStateException, ResourceNotFoundException
from app.core.logging import logger
from app.core.ollama_client import AsyncOllamaClient
from app.models.answer import Answer
from app.models.question import Question
from app.models.session import InterviewSession
from app.schemas.answer import AnswerEvaluationLLM, AnswerResponse, AnswerSubmitRequest


class EvaluationService:
    """Evaluates candidate interview answers using local Ollama structured inference."""

    def __init__(self, ollama_client: AsyncOllamaClient):
        self.ollama = ollama_client

    async def evaluate_and_save_answer(
        self,
        session: InterviewSession,
        question: Question,
        answer_payload: AnswerSubmitRequest,
        db: AsyncSession,
    ) -> AnswerResponse:
        """Evaluates submitted answer, handles idempotency, updates competency state, and persists."""
        # 1. State validation
        if session.status in ["completed", "abandoned"]:
            raise InvalidSessionStateException(
                message=f"Cannot submit answer: session is already '{session.status}'.",
                details={"sessionId": str(session.id), "status": session.status},
            )

        if session.started_at is None:
            session.started_at = datetime.now(timezone.utc)
        if session.status == "created":
            session.status = "in_progress"

        # 2. Check for duplicate submission on this question
        stmt = select(Answer).where(Answer.question_id == question.id)
        result = await db.execute(stmt)
        existing_answer = result.scalar_one_or_none()

        if existing_answer is not None:
            logger.info(
                f"Duplicate answer submission detected for question {question.id} in session {session.id}. "
                "Returning existing saved evaluation."
            )
            return AnswerResponse(
                sessionId=str(session.id),
                answer_id=str(existing_answer.id),
                question_id=str(question.id),
                score=existing_answer.score,
                strengths=existing_answer.strengths,
                weaknesses=existing_answer.weaknesses,
                feedback=existing_answer.feedback,
                improvement_suggestions=existing_answer.improvement_suggestions,
                competency=question.competency,
                created_at=existing_answer.created_at,
            )

        # 3. Build Ollama prompt with rubric constraints
        criteria_list = question.key_evaluation_criteria or []
        criteria_str = "\n".join(f"- {c}" for c in criteria_list) if criteria_list else "- Technical correctness, depth, and clarity"

        system_prompt = (
            "You are an expert technical interviewer evaluating an engineering candidate's answer.\n"
            "Evaluate the candidate's answer rigorously, objectively, and constructively against the target role, seniority level, and question evaluation criteria.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. Output MUST strictly conform to the provided JSON Schema.\n"
            "2. Score on a scale from 0.0 to 10.0:\n"
            "   - 0.0 to 4.9: Inadequate or incorrect understanding\n"
            "   - 5.0 to 6.9: Basic knowledge with notable omissions or inaccuracies\n"
            "   - 7.0 to 8.4: Solid competency fulfilling expectations for seniority level\n"
            "   - 8.5 to 10.0: Expert mastery demonstrating deep architectural and practical grasp\n"
            "3. Identify concrete demonstrated strengths.\n"
            "4. Identify specific technical weaknesses or omissions.\n"
            "5. Provide constructive feedback and concrete recommendations for improvement."
        )

        prompt = (
            f"TARGET ROLE: {session.target_role}\n"
            f"SENIORITY LEVEL: {session.target_level}\n"
            f"COMPETENCY: {question.competency}\n"
            f"QUESTION DIFFICULTY: {question.difficulty}\n"
            f"QUESTION:\n{question.question_text}\n\n"
            f"KEY EVALUATION CRITERIA:\n{criteria_str}\n\n"
            f"CANDIDATE ANSWER:\n{answer_payload.answer_text.strip()}\n\n"
            "Evaluate the answer according to the rubric and return structured evaluation JSON."
        )

        logger.info(
            f"Invoking Ollama answer evaluation for session {session.id} | "
            f"Question {question.id} | Competency: '{question.competency}'"
        )

        # 4. Invoke Ollama structured inference
        evaluation: AnswerEvaluationLLM = await self.ollama.generate_structured(
            prompt=prompt,
            schema=AnswerEvaluationLLM,
            system_prompt=system_prompt,
            options={"temperature": 0.1, "num_predict": 400},
        )

        # 5. Persist Answer
        new_answer = Answer(
            session_id=session.id,
            question_id=question.id,
            answer_text=answer_payload.answer_text.strip(),
            score=round(evaluation.score, 2),
            strengths=evaluation.strengths,
            weaknesses=evaluation.weaknesses,
            feedback=evaluation.feedback.strip(),
            improvement_suggestions=evaluation.improvement_suggestions,
            raw_evaluation=evaluation.model_dump(),
        )

        db.add(new_answer)

        # 6. Update session competency state
        comp_state = dict(session.competency_state or {})
        comp_state["latest_score"] = new_answer.score

        eval_history = list(comp_state.get("evaluations", []))
        eval_history.append({
            "question_id": str(question.id),
            "competency": question.competency,
            "score": new_answer.score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        comp_state["evaluations"] = eval_history

        # Update matching claimed skills if present
        claimed_skills = list(comp_state.get("claimed_skills", []))
        for skill in claimed_skills:
            skill_name = skill.get("name", "").strip().lower()
            if skill_name and (skill_name in question.competency.lower() or question.competency.lower() in skill_name):
                skill["verified"] = True
                skill["demonstrated_score"] = new_answer.score
                notes = list(skill.get("evaluation_notes", []))
                notes.append(f"Score {new_answer.score}/10: {new_answer.feedback[:120]}")
                skill["evaluation_notes"] = notes
        comp_state["claimed_skills"] = claimed_skills

        session.competency_state = comp_state

        await db.commit()
        await db.refresh(new_answer)

        logger.info(
            f"Answer persisted (ID: {new_answer.id}) with score {new_answer.score}/10. "
            f"Competency '{question.competency}' updated."
        )

        return AnswerResponse(
            sessionId=str(session.id),
            answer_id=str(new_answer.id),
            question_id=str(question.id),
            score=new_answer.score,
            strengths=new_answer.strengths,
            weaknesses=new_answer.weaknesses,
            feedback=new_answer.feedback,
            improvement_suggestions=new_answer.improvement_suggestions,
            competency=question.competency,
            created_at=new_answer.created_at,
        )
