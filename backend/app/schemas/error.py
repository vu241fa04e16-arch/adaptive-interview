from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str = Field(description="High-level machine-readable error code")
    message: str = Field(description="Human-readable error explanation")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional contextual metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
