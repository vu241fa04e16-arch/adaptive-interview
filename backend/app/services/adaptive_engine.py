from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidSessionStateException
from app.core.logging import logger
from app.core.ollama_client import AsyncOllamaClient
from app.models.answer import Answer
from app.models.question import Question
from app.models.session import InterviewSession
from app.schemas.question import (
    AdaptationContext,
    GeneratedQuestionLLM,
    QuestionResponse,
)

ROLE_CORE_COMPETENCIES: Dict[str, List[str]] = {
    "backend": [
        "Distributed Systems & Scalability",
        "Database Internals & Concurrency",
        "API Design & Protocols",
        "Caching & Performance",
        "Reliability & Fault Tolerance",
    ],
    "frontend": [
        "Component Architecture & State Management",
        "Rendering Performance & Web Vitals",
        "Browser APIs & DOM Manipulation",
        "Accessibility & Responsive UI",
        "Frontend Security & Network Optimization",
    ],
    "fullstack": [
        "End-to-End System Architecture",
        "Database Modeling & Query Optimization",
        "REST & GraphQL API Engineering",
        "Client-Side State & Async Data Flow",
        "Authentication, Authorization & Security",
    ],
    "general": [
        "Software Design Patterns & Modularity",
        "Data Structures & Algorithmic Complexity",
        "Testing Strategies & Maintainability",
        "System Tradeoffs & Technical Debt",
    ],
}

SENIORITY_DIFFICULTY_MAP: Dict[str, str] = {
    "junior": "beginner",
    "mid": "intermediate",
    "senior": "advanced",
    "lead": "advanced",
    "staff": "advanced",
    "principal": "expert",
}


class AdaptiveEngine:
    """Deterministic selection state machine coupled with real Ollama question generation."""

    def __init__(self, ollama_client: AsyncOllamaClient):
        self.ollama = ollama_client

    def _get_role_competencies(self, role: str) -> List[str]:
        """Resolves core competencies based on candidate target role."""
        role_lower = role.lower()
        if "back" in role_lower or "architect" in role_lower or "cloud" in role_lower:
            return ROLE_CORE_COMPETENCIES["backend"]
        elif "front" in role_lower or "ui" in role_lower or "react" in role_lower:
            return ROLE_CORE_COMPETENCIES["frontend"]
        elif "full" in role_lower or "web" in role_lower:
            return ROLE_CORE_COMPETENCIES["fullstack"]
        return ROLE_CORE_COMPETENCIES["general"]

    def _determine_competency(
        self,
        session: InterviewSession,
        assessed_competencies: set,
        existing_questions: Optional[List[Question]] = None,
    ) -> tuple[str, str, str]:
        """Deterministically selects the next competency to assess, prioritizing unassessed areas."""
        comp_state = session.competency_state or {}
        focus_areas: List[str] = comp_state.get("suggested_focus_areas", [])
        claimed_skills: List[Dict[str, Any]] = comp_state.get("claimed_skills", [])

        # 1. Check unassessed resume focus areas
        for focus in focus_areas:
            if focus.strip().lower() not in assessed_competencies:
                return (
                    focus.strip(),
                    "UNASSESSED_FOCUS_AREA",
                    f"Prioritizing unassessed focus area '{focus}' identified from resume analysis.",
                )

        # 2. Check unassessed claimed skills from resume
        for skill in claimed_skills:
            skill_name = skill.get("name", "").strip()
            if skill_name and skill_name.lower() not in assessed_competencies:
                return (
                    skill_name,
                    "UNASSESSED_CLAIMED_SKILL",
                    f"Testing unassessed claimed skill '{skill_name}' declared in candidate resume.",
                )

        # 3. Check unassessed core role competencies (fallback if no resume or all resume items tested)
        role_competencies = self._get_role_competencies(session.target_role)
        for role_comp in role_competencies:
            if role_comp.strip().lower() not in assessed_competencies:
                return (
                    role_comp.strip(),
                    "CORE_ROLE_COMPETENCY",
                    f"Evaluating core role competency '{role_comp}' for {session.target_role}.",
                )

        questions = existing_questions if existing_questions is not None else []
        repeat_target = questions[0].competency if questions else "System Architecture"
        return (
            repeat_target,
            "DEEP_PROBE_FOLLOW_UP",
            f"All initial competencies sampled; deepening evaluation on '{repeat_target}'.",
        )

    def _determine_difficulty(
        self,
        session: InterviewSession,
        previous_score: Optional[float] = None,
    ) -> tuple[str, str, Optional[float]]:
        """Calibrates difficulty based on seniority and previous answer evaluation score if present."""
        level_key = session.target_level.lower()
        baseline_diff = SENIORITY_DIFFICULTY_MAP.get(level_key, "intermediate")

        if previous_score is not None:
            if previous_score >= 8.0:
                adjusted = "expert" if baseline_diff == "advanced" else "advanced"
                return adjusted, "increased", previous_score
            elif previous_score < 5.0:
                adjusted = "beginner" if baseline_diff == "intermediate" else "intermediate"
                return adjusted, "decreased", previous_score
            return baseline_diff, "baseline", previous_score

        return baseline_diff, "baseline", None

    def _determine_question_type(self, sequence_number: int, time_remaining_seconds: int) -> str:
        """Determines pedagogical question type based on sequence position and remaining time."""
        if time_remaining_seconds <= 300:
            return "system_tradeoff"
        if sequence_number == 1:
            return "technical_concept"
        if sequence_number in [2, 3]:
            return "deep_probe"
        return "architecture_scenario"

    def _calculate_time_remaining(self, session: InterviewSession) -> int:
        """Calculates seconds remaining in the interview session."""
        now = datetime.now(timezone.utc)
        if session.started_at is None:
            return session.time_limit_minutes * 60
        elapsed_sec = (now - session.started_at).total_seconds()
        total_sec = session.time_limit_minutes * 60
        return max(0, int(total_sec - elapsed_sec))

    async def generate_next_question(
        self,
        session: InterviewSession,
        db: AsyncSession,
    ) -> QuestionResponse:
        """Executes adaptive selection and invokes Ollama to formulate the next interview question."""
        # 1. State validations
        if session.status in ["completed", "abandoned"]:
            raise InvalidSessionStateException(
                message=f"Cannot generate next question: session is already '{session.status}'.",
                details={"sessionId": str(session.id), "status": session.status},
            )

        # 2. Timing and status initialization
        now = datetime.now(timezone.utc)
        if session.started_at is None:
            session.started_at = now
        if session.status == "created":
            session.status = "in_progress"

        try:
            raw_questions = session.questions
            if isinstance(raw_questions, (list, tuple)):
                existing_questions = list(raw_questions)
            elif raw_questions is not None:
                existing_questions = [raw_questions]
            else:
                existing_questions = []
        except Exception:
            q_stmt = (
                select(Question)
                .where(Question.session_id == session.id)
                .order_by(Question.sequence_number.asc())
            )
            q_res = await db.execute(q_stmt)
            existing_questions = list(q_res.scalars().all())

        time_remaining = self._calculate_time_remaining(session)
        sequence_number = len(existing_questions) + 1

        # 3. Gather historical state
        # A competency counts as assessed ONLY when its question has a submitted answer and evaluation
        assessed_competencies: set = set()

        # Query database for questions in this session with submitted and evaluated answers
        stmt = (
            select(Question.competency)
            .join(Answer, Answer.question_id == Question.id)
            .where(Question.session_id == session.id)
        )
        result = await db.execute(stmt)
        for row in result.all():
            if row[0]:
                assessed_competencies.add(row[0].strip().lower())

        # Check competency_state evaluations history
        comp_state = session.competency_state or {}
        for ev in comp_state.get("evaluations", []):
            if isinstance(ev, dict) and "competency" in ev and ev.get("score") is not None:
                assessed_competencies.add(str(ev["competency"]).strip().lower())

        # Check uncommitted new answers in current db session
        for obj in db.new:
            if isinstance(obj, Answer) and obj.session_id == session.id:
                for q in existing_questions:
                    if q.id == obj.question_id:
                        assessed_competencies.add(q.competency.strip().lower())

        previous_questions_text = [q.question_text for q in existing_questions]

        # Extract latest evaluation score if available (from competency_state or prior answer)
        latest_score: Optional[float] = None
        if "latest_score" in comp_state and isinstance(comp_state["latest_score"], (int, float)):
            latest_score = float(comp_state["latest_score"])
        elif assessed_competencies:
            # Check latest answer score from DB if not in comp_state
            latest_answer_stmt = (
                select(Answer.score)
                .where(Answer.session_id == session.id)
                .order_by(Answer.created_at.desc())
                .limit(1)
            )
            latest_ans_res = await db.execute(latest_answer_stmt)
            latest_score_val = latest_ans_res.scalar_one_or_none()
            if latest_score_val is not None:
                latest_score = float(latest_score_val)

        # 4. Deterministic decision rules
        competency, trigger, reason_base = self._determine_competency(
            session, assessed_competencies, existing_questions
        )
        difficulty, diff_direction, score_used = self._determine_difficulty(session, previous_score=latest_score)
        question_type = self._determine_question_type(sequence_number, time_remaining)

        reasoning = f"{reason_base} Calibrated at {difficulty} difficulty (adjustment: {diff_direction})."

        # 5. Extract optional relevant resume snippet for context
        snippet_context = ""
        claimed_skills = comp_state.get("claimed_skills", [])
        for s in claimed_skills:
            if s.get("name", "").lower() in competency.lower():
                snippet = s.get("context_snippet")
                if snippet:
                    snippet_context = f"\nCandidate's resume mention: \"{snippet}\""
                break

        # 6. Compose targeted prompt for Ollama
        system_prompt = (
            "You are an expert technical interviewer conducting a live adaptive engineering interview.\n"
            "Formulate ONE direct, precise interview question tailored to the target role, competency, and difficulty.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. Output MUST strictly conform to the JSON schema provided.\n"
            "2. Formulate ONLY ONE question. Do not bundle multiple unrelated questions.\n"
            "3. Do NOT repeat or duplicate any questions previously asked in this session.\n"
            "4. Keep the question professional, practical, and focused on real-world engineering."
        )

        avoid_clause = ""
        if previous_questions_text:
            avoid_list = "\n".join(f"- {q}" for q in previous_questions_text[-3:])
            avoid_clause = f"\n\nDO NOT ASK OR REPEAT ANY OF THESE PREVIOUS QUESTIONS:\n{avoid_list}"

        prompt = (
            f"TARGET ROLE: {session.target_role}\n"
            f"SENIORITY LEVEL: {session.target_level}\n"
            f"COMPETENCY: {competency}\n"
            f"TARGET DIFFICULTY: {difficulty}\n"
            f"QUESTION TYPE: {question_type}{snippet_context}{avoid_clause}\n\n"
            "Generate the technical question and 2 to 4 key evaluation criteria."
        )

        logger.info(
            f"Invoking Ollama for question #{sequence_number} | Session {session.id} | "
            f"Competency='{competency}' | Difficulty={difficulty}"
        )

        # 7. Real Ollama structured inference (fast, bounded to 250 tokens)
        llm_output: GeneratedQuestionLLM = await self.ollama.generate_structured(
            prompt=prompt,
            schema=GeneratedQuestionLLM,
            system_prompt=system_prompt,
            options={"temperature": 0.2, "num_predict": 250},
        )

        # 8. Persist new Question record
        adaptation_context = AdaptationContext(
            trigger=trigger,
            prior_competency_score=score_used,
            difficulty_direction=diff_direction,
            reasoning=reasoning,
        )

        new_question = Question(
            session_id=session.id,
            sequence_number=sequence_number,
            question_text=llm_output.question_text.strip(),
            competency=competency,
            difficulty=difficulty,
            question_type=question_type,
            key_evaluation_criteria=llm_output.key_evaluation_criteria,
            adaptation_context=adaptation_context.model_dump(),
        )

        db.add(new_question)
        await db.commit()
        await db.refresh(new_question)

        logger.info(f"Persisted question #{sequence_number} (ID: {new_question.id}) for session {session.id}")

        return QuestionResponse(
            sessionId=str(session.id),
            question_id=str(new_question.id),
            sequence_number=new_question.sequence_number,
            question_text=new_question.question_text,
            competency=new_question.competency,
            difficulty=new_question.difficulty,
            question_type=new_question.question_type,
            time_remaining_seconds=time_remaining,
            key_evaluation_criteria=new_question.key_evaluation_criteria,
            adaptation_context=adaptation_context,
        )
