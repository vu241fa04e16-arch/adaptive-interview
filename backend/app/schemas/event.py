from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class EventCreateRequest(BaseModel):
    """Payload for submitting session telemetry and integrity events."""

    event_type: str = Field(min_length=2, max_length=100, description="Event identifier, e.g. TAB_SWITCH, WINDOW_BLUR, HEARTBEAT")
    event_data: Dict[str, Any] = Field(default_factory=dict, description="Metadata or context payload associated with event")
    timestamp: Optional[datetime] = Field(default=None, description="Client timestamp when event occurred")


class InterviewProgress(BaseModel):
    """Current progress indicators computed from persisted session state."""

    questions_asked: int
    answers_submitted: int
    current_status: str
    time_remaining_seconds: int


class EventResponse(BaseModel):
    """API response returned by POST /api/sessions/{sessionId}/events."""

    sessionId: str
    event_id: str
    event_type: str
    timestamp: datetime
    progress: InterviewProgress
