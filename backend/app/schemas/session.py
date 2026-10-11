from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class SessionCreateRequest(BaseModel):
    """Payload to initialize a new interview session."""

    candidate_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full name of candidate",
        examples=["Jane Doe"],
    )
    candidate_email: EmailStr = Field(
        ...,
        description="Candidate email address",
        examples=["jane.doe@example.com"],
    )
    target_role: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Target engineering role",
        examples=["Senior Backend Architect"],
    )
    target_level: Literal["Junior", "Mid", "Senior", "Lead", "Staff", "Principal"] = Field(
        default="Senior",
        description="Seniority level for interview calibration",
    )
    time_limit_minutes: int = Field(
        default=45,
        ge=15,
        le=120,
        description="Allocated interview time in minutes",
    )
    job_description: Optional[str] = Field(
        default=None,
        max_length=50000,
        description="Optional full text of target role job description for skill gap analysis",
    )


class SessionResponse(BaseModel):
    """Response returned upon session creation or state query."""

    sessionId: str = Field(description="UUID of interview session")
    candidate_name: str
    candidate_email: str
    target_role: str
    target_level: str
    status: str
    time_limit_minutes: int
    created_at: datetime
    resume_uploaded: bool = False
    job_description_provided: bool = False
