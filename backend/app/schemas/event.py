from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class SingleEventItem(BaseModel):
    """Normalized single telemetry event."""
    event_type: str = Field(min_length=2, max_length=100, description="Event identifier")
    event_data: Dict[str, Any] = Field(default_factory=dict, description="Metadata or context payload")
    timestamp: Optional[datetime] = Field(default=None, description="Client timestamp")

    @model_validator(mode="before")
    @classmethod
    def normalize_event_item(cls, data: object) -> object:
        if isinstance(data, dict):
            d = dict(data)
            if "event_type" not in d and "type" in d:
                d["event_type"] = d["type"]
            if "event_data" not in d:
                extra = {k: v for k, v in d.items() if k not in ("event_type", "type", "timestamp")}
                d["event_data"] = extra
            return d
        return data


class EventCreateRequest(BaseModel):
    """Payload for submitting session telemetry and integrity events (single or batched)."""

    event_type: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Event identifier, e.g. TAB_SWITCH, WINDOW_BLUR, HEARTBEAT")
    event_data: Dict[str, Any] = Field(default_factory=dict, description="Metadata or context payload associated with event")
    timestamp: Optional[datetime] = Field(default=None, description="Client timestamp when event occurred")
    events: Optional[List[SingleEventItem]] = Field(default=None, description="Optional batch list of events")

    @model_validator(mode="before")
    @classmethod
    def normalize_request(cls, data: object) -> object:
        if isinstance(data, dict):
            d = dict(data)
            if "events" in d and isinstance(d["events"], list):
                return d
            if "event_type" not in d and "type" in d:
                d["event_type"] = d["type"]
            if "event_data" not in d:
                extra = {k: v for k, v in d.items() if k not in ("event_type", "type", "timestamp", "events")}
                d["event_data"] = extra
            return d
        return data



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
