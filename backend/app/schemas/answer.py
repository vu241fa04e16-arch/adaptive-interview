from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnswerSubmitRequest(BaseModel):
    """Payload for submitting a candidate answer."""

    question_id: str = Field(description="UUID of the question being answered")
    answer_text: str = Field(min_length=1, description="Candidate answer content")
    time_taken_seconds: Optional[int] = Field(default=None, ge=0, description="Optional time spent formulating answer")


class AnswerEvaluationLLM(BaseModel):
    """Structured rubric-based evaluation returned by local Ollama."""

    score: float = Field(
        ge=0.0,
        le=10.0,
        description="Rubric score between 0.0 (inadequate) and 10.0 (flawless mastery)",
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Technical strengths and correct arguments demonstrated in candidate answer",
    )
    weaknesses: List[str] = Field(
        default_factory=list,
        description="Technical omissions, errors, or anti-patterns observed",
    )
    feedback: str = Field(
        description="Concise, actionable qualitative feedback for the candidate",
    )
    improvement_suggestions: List[str] = Field(
        default_factory=list,
        description="Specific topics or architectural concepts recommended for deeper mastery",
    )


class AnswerResponse(BaseModel):
    """API response returned by POST /api/sessions/{sessionId}/answers."""

    sessionId: str
    answer_id: str
    question_id: str
    score: float
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    feedback: str
    improvement_suggestions: List[str] = Field(default_factory=list)
    competency: str
    created_at: datetime


class AudioAnswerResponse(AnswerResponse):
    """API response returned by POST /api/sessions/{sessionId}/answers/audio."""

    transcript: str = Field(description="Full speech-to-text transcript of candidate audio")
