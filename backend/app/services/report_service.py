from typing import Any, Dict, List, Optional
from collections import defaultdict

from app.models.session import InterviewSession
from app.schemas.report import (
    AnswerDetail,
    CompetencyPerformance,
    IntegritySummary,
    InterviewReportResponse,
    QuestionWithAnswer,
    ReportSummaryMetrics,
)


class ReportService:
    """Deterministically compiles comprehensive interview decision reports from persisted DB records."""

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

    def generate_report(self, session: InterviewSession) -> InterviewReportResponse:
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

        # 4. Aggregate integrity telemetry events
        raw_events = session.events or []
        events_list = list(raw_events)
        tab_switches = sum(1 for e in events_list if "TAB_SWITCH" in e.event_type.upper())
        window_blurs = sum(1 for e in events_list if "BLUR" in e.event_type.upper())
        suspicious = (tab_switches >= 3) or (window_blurs >= 5)

        integrity = IntegritySummary(
            total_events=len(events_list),
            tab_switches=tab_switches,
            window_blurs=window_blurs,
            suspicious_activity_flag=suspicious,
        )

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
        )
