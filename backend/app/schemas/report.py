from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SessionCompleteResponse(BaseModel):
    """API response returned by POST /api/sessions/{sessionId}/complete."""

    sessionId: str
    status: str
    completed_at: datetime
    total_questions: int
    total_answers: int
    average_score: Optional[float] = None
    message: str


class AnswerDetail(BaseModel):
    """Detail of a candidate's answer and AI evaluation in the report."""

    answer_id: str
    answer_text: str
    score: float
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    feedback: str
    improvement_suggestions: List[str] = Field(default_factory=list)
    created_at: datetime


class QuestionWithAnswer(BaseModel):
    """Interview question paired with submitted answer and evaluation."""

    question_id: str
    sequence_number: int
    question_text: str
    competency: str
    difficulty: str
    question_type: str
    key_evaluation_criteria: List[str] = Field(default_factory=list)
    answer: Optional[AnswerDetail] = None


class CompetencyPerformance(BaseModel):
    """Aggregated performance for a distinct evaluated competency."""

    competency: str
    questions_count: int
    answers_count: int
    average_score: Optional[float] = None
    demonstrated_proficiency: str
    strengths: List[str] = Field(default_factory=list)
    areas_for_improvement: List[str] = Field(default_factory=list)


class IntegrityTimelineEntry(BaseModel):
    """Single chronological event in the interview integrity timeline."""

    timestamp: datetime
    event_type: str
    severity: str = "info"  # info, low, medium, high
    description: str


class IntegritySummary(BaseModel):
    """Integrity telemetry analytics aggregated from events with explainable risk assessment."""

    total_events: int
    tab_switches: int
    window_blurs: int
    window_focuses: int = 0
    pastes_detected: int = 0
    suspicious_activity_flag: bool = False
    risk_level: str = "low"  # low, medium, high
    risk_score: float = 0.0  # 0.0 to 10.0 scale
    risk_indicators: List[str] = Field(default_factory=list)
    reasons_for_flags: List[str] = Field(default_factory=list)
    timeline: List[IntegrityTimelineEntry] = Field(default_factory=list)


class ReportSummaryMetrics(BaseModel):
    """Overall deterministic summary metrics."""

    total_questions: int
    total_answers: int
    completion_rate: float
    overall_average_score: Optional[float] = None
    total_duration_seconds: Optional[int] = None
    integrity: IntegritySummary


class InterviewReportResponse(BaseModel):
    """Comprehensive candidate interview evaluation decision report."""

    sessionId: str
    candidate_name: str
    candidate_email: str
    target_role: str
    target_level: str
    status: str
    time_limit_minutes: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    candidate_overview: Optional[str] = None
    questions: List[QuestionWithAnswer] = Field(default_factory=list)
    competencies: List[CompetencyPerformance] = Field(default_factory=list)
    summary: ReportSummaryMetrics

    # Candidate Decision Intelligence & Skill Gap Analysis
    skill_gap_analysis: Optional[Any] = None
    claimed_skills: List[Dict[str, Any]] = Field(default_factory=list)
    demonstrated_skills: List[str] = Field(default_factory=list)
    overall_assessment: Optional[str] = None
    decision_recommendation: Optional[str] = None
    suggested_follow_up_questions: List[str] = Field(default_factory=list)
