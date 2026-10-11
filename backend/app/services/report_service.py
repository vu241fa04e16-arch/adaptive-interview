from collections import defaultdict
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.core.ollama_client import AsyncOllamaClient
from app.models.session import InterviewSession
from app.schemas.report import (
    AnswerDetail,
    CompetencyPerformance,
    IntegritySummary,
    InterviewReportResponse,
    QuestionWithAnswer,
    ReportSummaryMetrics,
)
from app.schemas.skill_gap import SkillGapReport
from app.services.integrity_service import IntegrityService
from app.services.skill_gap_service import SkillGapService


class ExecutiveAssessmentLLM(BaseModel):
    """Structured LLM synthesis of candidate interview performance."""

    overall_assessment: str = Field(
        description="Concise 2-3 sentence evidence-based evaluation grounded strictly in candidate scores and verified answers."
    )
    decision_recommendation: str = Field(
        description="Objective recommendation summary without arbitrary hire/reject labels."
    )


class ReportService:
    """Compiles comprehensive, evidence-grounded candidate decision reports from persisted DB records."""

    def __init__(
        self,
        ollama_client: Optional[AsyncOllamaClient] = None,
        skill_gap_service: Optional[SkillGapService] = None,
        integrity_service: Optional[IntegrityService] = None,
    ):
        self.ollama = ollama_client
        self.skill_gap_service = skill_gap_service or SkillGapService(ollama_client=ollama_client)
        self.integrity_service = integrity_service or IntegrityService()

    @staticmethod
    def calculate_proficiency(avg_score: Optional[float]) -> str:
        """Determines qualitative competency proficiency category from numerical score."""
        if avg_score is None:
            return "Unassessed"
        if avg_score >= 8.5:
            return "Expert"
        if avg_score >= 7.0:
            return "Advanced"
        if avg_score >= 5.0:
            return "Intermediate"
        return "Novice"

    async def generate_report(self, session: InterviewSession) -> InterviewReportResponse:
        """Constructs an interview decision report deterministically from database entities."""
        raw_questions = session.questions or []
        questions_list = list(raw_questions)

        # Build answer lookup by question_id
        answers_by_qid = {}
        for ans in session.answers or []:
            answers_by_qid[ans.question_id] = ans

        # 1. Compile questions and answers
        report_questions: List[QuestionWithAnswer] = []
        all_scores: List[float] = []
        competency_groups: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "questions_count": 0,
                "answers_count": 0,
                "scores": [],
                "strengths": set(),
                "improvements": set(),
            }
        )

        for q in questions_list:
            ans = answers_by_qid.get(q.id) or getattr(q, "answer", None)
            ans_detail: Optional[AnswerDetail] = None

            comp_group = competency_groups[q.competency]
            comp_group["questions_count"] += 1

            if ans is not None:
                ans_detail = AnswerDetail(
                    answer_id=str(ans.id),
                    answer_text=ans.answer_text,
                    score=ans.score,
                    strengths=ans.strengths or [],
                    weaknesses=ans.weaknesses or [],
                    feedback=ans.feedback,
                    improvement_suggestions=ans.improvement_suggestions or [],
                    created_at=ans.created_at,
                )
                all_scores.append(ans.score)
                comp_group["answers_count"] += 1
                comp_group["scores"].append(ans.score)

                for s in ans.strengths or []:
                    if s.strip():
                        comp_group["strengths"].add(s.strip())
                for w in ans.weaknesses or []:
                    if w.strip():
                        comp_group["improvements"].add(w.strip())
                for imp in ans.improvement_suggestions or []:
                    if imp.strip():
                        comp_group["improvements"].add(imp.strip())

            report_questions.append(
                QuestionWithAnswer(
                    question_id=str(q.id),
                    sequence_number=q.sequence_number,
                    question_text=q.question_text,
                    competency=q.competency,
                    difficulty=q.difficulty,
                    question_type=q.question_type,
                    key_evaluation_criteria=q.key_evaluation_criteria or [],
                    answer=ans_detail,
                )
            )

        # 2. Compile competency performance
        competencies_perf: List[CompetencyPerformance] = []
        for comp_name, data in competency_groups.items():
            scores = data["scores"]
            avg = round(sum(scores) / len(scores), 2) if scores else None
            competencies_perf.append(
                CompetencyPerformance(
                    competency=comp_name,
                    questions_count=data["questions_count"],
                    answers_count=data["answers_count"],
                    average_score=avg,
                    demonstrated_proficiency=self.calculate_proficiency(avg),
                    strengths=sorted(list(data["strengths"])),
                    areas_for_improvement=sorted(list(data["improvements"])),
                )
            )

        # Sort competencies by question count descending
        competencies_perf.sort(key=lambda x: x.questions_count, reverse=True)

        # 3. Calculate summary metrics
        total_q = len(report_questions)
        total_a = len(all_scores)
        overall_avg = round(sum(all_scores) / total_a, 2) if total_a > 0 else None
        completion_rate = round((total_a / total_q) * 100.0, 1) if total_q > 0 else 0.0

        duration_sec: Optional[int] = None
        if session.started_at and session.completed_at:
            duration_sec = max(0, int((session.completed_at - session.started_at).total_seconds()))

        # 4. Aggregate integrity telemetry events using IntegrityService
        raw_events = session.events or []
        integrity: IntegritySummary = self.integrity_service.analyze_events(raw_events, session)

        metrics = ReportSummaryMetrics(
            total_questions=total_q,
            total_answers=total_a,
            completion_rate=completion_rate,
            overall_average_score=overall_avg,
            total_duration_seconds=duration_sec,
            integrity=integrity,
        )

        candidate_overview = (
            session.resume_analysis.candidate_overview
            if session.resume_analysis
            else None
        )

        # 5. Compute Resume–JD Skill Gap Analysis
        comp_state = session.competency_state or {}
        persisted_gap = comp_state.get("skill_gap_analysis")
        if persisted_gap:
            try:
                skill_gap_report = SkillGapReport.model_validate(persisted_gap)
            except Exception:
                skill_gap_report = await self.skill_gap_service.generate_skill_gap_report(session)
        else:
            skill_gap_report = await self.skill_gap_service.generate_skill_gap_report(session)

        # 6. Extract claimed & demonstrated skills
        claimed_skills = list(comp_state.get("claimed_skills", []))
        if not claimed_skills and session.resume_analysis:
            claimed_skills = list(session.resume_analysis.claimed_skills or [])

        demonstrated_skills = skill_gap_report.demonstrated_skills

        # 7. Evidence-based Assessment & Decision Recommendation
        overall_assessment, decision_recommendation = await self._synthesize_assessment(
            session=session,
            overall_avg=overall_avg,
            total_a=total_a,
            total_q=total_q,
            demonstrated_skills=demonstrated_skills,
            missing_skills=skill_gap_report.missing_skills,
            integrity=integrity,
        )

        return InterviewReportResponse(
            sessionId=str(session.id),
            candidate_name=session.candidate_name,
            candidate_email=session.candidate_email,
            target_role=session.target_role,
            target_level=session.target_level,
            status=session.status,
            time_limit_minutes=session.time_limit_minutes,
            created_at=session.created_at,
            started_at=session.started_at,
            completed_at=session.completed_at,
            candidate_overview=candidate_overview,
            questions=report_questions,
            competencies=competencies_perf,
            summary=metrics,
            skill_gap_analysis=skill_gap_report,
            claimed_skills=claimed_skills,
            demonstrated_skills=demonstrated_skills,
            overall_assessment=overall_assessment,
            decision_recommendation=decision_recommendation,
            suggested_follow_up_questions=skill_gap_report.suggested_follow_up_questions,
        )

    async def _synthesize_assessment(
        self,
        session: InterviewSession,
        overall_avg: Optional[float],
        total_a: int,
        total_q: int,
        demonstrated_skills: List[str],
        missing_skills: List[str],
        integrity: IntegritySummary,
    ) -> tuple[str, str]:
        """Synthesizes evidence-based assessment using Ollama with deterministic fallback."""
        # Baseline deterministic recommendation
        if total_a == 0:
            rec = "Interview Incomplete — Insufficient answers submitted for definitive assessment."
            summary = (
                f"Candidate {session.candidate_name} initiated an interview session for {session.target_role} "
                f"({session.target_level}) but submitted zero evaluated answers."
            )
            return summary, rec

        demo_str = ", ".join(demonstrated_skills) if demonstrated_skills else "none to date"
        miss_str = ", ".join(missing_skills[:3]) if missing_skills else "none identified"

        if overall_avg is not None and overall_avg >= 8.0:
            rec = "Strong Technical Mastery — Recommended for Senior / Architecture Responsibilities"
        elif overall_avg is not None and overall_avg >= 6.5:
            rec = "Solid Technical Competence — Recommended with Targeted Follow-Up on Gaps"
        else:
            rec = "Developing Proficiency — Recommend Further Preparation in Core Competencies"

        deterministic_summary = (
            f"Candidate {session.candidate_name} achieved an overall average score of {overall_avg}/10 across "
            f"{total_a} evaluated questions for the {session.target_level} {session.target_role} role. "
            f"Demonstrated verified mastery in: {demo_str}. Identified priority growth areas in: {miss_str}. "
            f"Integrity telemetry indicates {integrity.risk_level} focus disruption ({integrity.total_events} total events)."
        )

        # Optional Ollama enrichment
        if self.ollama:
            try:
                system_prompt = (
                    "You are a principal technical hiring manager writing a concise candidate assessment.\n"
                    "Ground your assessment STRICTLY in the provided score and verified skills. Do not invent details."
                )
                prompt = (
                    f"CANDIDATE: {session.candidate_name}\n"
                    f"ROLE: {session.target_role} ({session.target_level})\n"
                    f"AVERAGE SCORE: {overall_avg}/10 ({total_a}/{total_q} questions answered)\n"
                    f"DEMONSTRATED SKILLS: {demo_str}\n"
                    f"SKILL GAPS: {miss_str}\n"
                    f"INTEGRITY STATUS: {integrity.risk_level} risk\n\n"
                    "Synthesize an evidence-based assessment and decision recommendation."
                )
                llm_output: ExecutiveAssessmentLLM = await self.ollama.generate_structured(
                    prompt=prompt,
                    schema=ExecutiveAssessmentLLM,
                    system_prompt=system_prompt,
                    options={"temperature": 0.1, "num_predict": 250},
                )
                if llm_output.overall_assessment.strip():
                    return llm_output.overall_assessment.strip(), llm_output.decision_recommendation.strip() or rec
            except Exception as e:
                logger.info(f"Ollama report enrichment bypassed, using deterministic synthesis: {e}")

        return deterministic_summary, rec
