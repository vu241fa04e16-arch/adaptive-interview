import re
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

    SKILL_VERIFICATION_THRESHOLD: float = 7.0

    def __init__(self, ollama_client: AsyncOllamaClient):
        self.ollama = ollama_client

    @staticmethod
    def _get_skill_terms(skill_name: str) -> List[str]:
        """Generates canonical matching terms and aliases for a skill to prevent false matches."""
        name_clean = skill_name.strip().lower()
        if not name_clean:
            return []
        terms = [name_clean]
        if name_clean.startswith("apache "):
            terms.append(name_clean.replace("apache ", "").strip())

        aliases = {
            "postgresql": ["postgres", "psql"],
            "kubernetes": ["k8s"],
            "amazon web services": ["aws"],
            "google cloud platform": ["gcp"],
            "microsoft azure": ["azure"],
            "distributed systems": ["distributed system", "distributed architecture"],
            "kafka": ["apache kafka"],
        }
        if name_clean in aliases:
            for alias in aliases[name_clean]:
                if alias not in terms:
                    terms.append(alias)
        return terms

    @classmethod
    def _matches_skill_name(cls, skill_name: str, text: str) -> bool:
        """
        Matches skill terms using strict regex word boundaries to avoid false partial substring matches
        (e.g., 'C' in 'cloud', 'Go' in 'algorithm', 'SQL' in 'NoSQL', 'Java' in 'JavaScript').
        """
        if not skill_name or not text:
            return False
        terms = cls._get_skill_terms(skill_name)
        for term in terms:
            pattern = rf"(?:\b|_){re.escape(term)}(?:\b|_)"
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _evaluate_skill_evidence(
        self,
        skill_name: str,
        question: Question,
        answer_text: str,
        evaluation: AnswerEvaluationLLM,
    ) -> bool:
        """
        Determines whether the candidate's evaluated answer provides relevant evidence for a claimed skill.
        Avoids partial substring matching alone and requires genuine technical relevance and evidence.
        """
        # 1. Check if question context targets this skill
        question_context = (
            f"{question.competency or ''} "
            f"{question.question_text or ''} "
            f"{' '.join(question.key_evaluation_criteria or [])}"
        )
        question_targets_skill = self._matches_skill_name(skill_name, question_context)

        # 2. Check if answer text explicitly mentions the skill (with word boundary)
        answer_mentions_skill = self._matches_skill_name(skill_name, answer_text)

        # 3. Check if evaluation feedback or strengths explicitly reference the skill
        eval_context = f"{' '.join(evaluation.strengths or [])} {evaluation.feedback or ''}"
        eval_mentions_skill = self._matches_skill_name(skill_name, eval_context)

        # 4. Check for pure non-answers or disclaimers with no technical substance
        lower_ans = answer_text.strip().lower()
        pure_non_answers = [
            "i don't know",
            "i do not know",
            "not familiar",
            "never used",
            "haven't used",
            "have not used",
            "no experience",
            "cannot answer",
            "n/a",
        ]
        is_pure_non_answer = any(d in lower_ans for d in pure_non_answers) and len(lower_ans.split()) < 10
        if is_pure_non_answer:
            return False

        # 5. Check substantive criteria overlap if question targets skill
        if question_targets_skill:
            if answer_mentions_skill:
                return True

            criteria = question.key_evaluation_criteria or []
            criteria_words = set()
            for c in criteria:
                criteria_words.update(re.findall(r"\b[a-zA-Z]{4,}\b", c.lower()))
            ans_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", lower_ans))
            has_criteria_overlap = bool(criteria_words.intersection(ans_words))

            if (has_criteria_overlap or eval_mentions_skill) and len(evaluation.strengths or []) > 0:
                return True

            return False

        # 6. If question does NOT target the skill:
        # Candidate must have actively applied the skill in the answer AND evaluation confirmed strengths in it
        if answer_mentions_skill and eval_mentions_skill and len(evaluation.strengths or []) > 0:
            return True

        return False

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
            skill_name = skill.get("name", "").strip()
            if not skill_name:
                continue

            is_relevant = self._evaluate_skill_evidence(
                skill_name=skill_name,
                question=question,
                answer_text=answer_payload.answer_text,
                evaluation=evaluation,
            )

            if is_relevant:
                meets_threshold = new_answer.score >= self.SKILL_VERIFICATION_THRESHOLD
                was_verified = bool(skill.get("verified", False))

                if meets_threshold:
                    skill["verified"] = True
                    prev_score = skill.get("demonstrated_score")
                    skill["demonstrated_score"] = (
                        max(prev_score, new_answer.score)
                        if prev_score is not None
                        else new_answer.score
                    )
                    notes = list(skill.get("evaluation_notes", []))
                    notes.append(f"Score {new_answer.score}/10: {new_answer.feedback[:120]}")
                    skill["evaluation_notes"] = notes
                else:
                    skill["verified"] = was_verified
                    if skill.get("demonstrated_score") is None:
                        skill["demonstrated_score"] = new_answer.score
                    notes = list(skill.get("evaluation_notes", []))
                    notes.append(
                        f"Attempted (Score {new_answer.score}/10, threshold {self.SKILL_VERIFICATION_THRESHOLD}): {new_answer.feedback[:120]}"
                    )
                    skill["evaluation_notes"] = notes

        comp_state["claimed_skills"] = claimed_skills
        session.competency_state = comp_state

        await db.commit()
        await db.refresh(new_answer)

        logger.info(
            f"Answer persisted (ID: {new_answer.id}) with score {new_answer.score}/10. "
            f"Competency '{question.competency}' updated."
        )

        # Check if more questions remain (standard adaptive session length: 4 questions)
        has_more_questions = question.sequence_number < 4

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
            has_more=has_more_questions,
        )
