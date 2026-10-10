from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AdaptationContext(BaseModel):
    """Explains why this question and competency were selected deterministically."""

    trigger: str = Field(description="Deterministic trigger: e.g. UNASSESSED_FOCUS_AREA, UNASSESSED_CLAIMED_SKILL, CORE_ROLE_COMPETENCY")
    prior_competency_score: Optional[float] = Field(default=None, description="Score from previous answer if available")
    difficulty_direction: str = Field(description="Adjustment direction: baseline, increased, decreased")
    reasoning: str = Field(description="Audit explanation for this adaptive decision")


class QuestionResponse(BaseModel):
    """Response returned by GET /api/sessions/{sessionId}/next-question."""

    sessionId: str
    question_id: str
    sequence_number: int
    question_text: str
    competency: str
    difficulty: str
    question_type: str
    time_remaining_seconds: int
    key_evaluation_criteria: List[str] = Field(default_factory=list)
    adaptation_context: Optional[AdaptationContext] = None


class GeneratedQuestionLLM(BaseModel):
    """Structured output expected from Ollama for question generation."""

    question_text: str = Field(
        description="A clear, professional, direct interview question targeting the specified competency and difficulty",
    )
    key_evaluation_criteria: List[str] = Field(
        default_factory=list,
        description="2 to 4 technical concepts or criteria an expert answer must demonstrate",
    )
