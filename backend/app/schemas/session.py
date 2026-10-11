from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, model_validator


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

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: object) -> object:
        if isinstance(data, dict):
            d = dict(data)
            if "candidate_name" not in d and "name" in d:
                d["candidate_name"] = d["name"]
            if "candidate_email" not in d and "email" in d:
                d["candidate_email"] = d["email"]
            if "target_role" not in d and "targetRole" in d:
                d["target_role"] = d["targetRole"]
            if "target_level" not in d and "targetLevel" in d:
                d["target_level"] = d["targetLevel"]
            if "time_limit_minutes" not in d and "timeLimitMinutes" in d:
                d["time_limit_minutes"] = d["timeLimitMinutes"]
            if "job_description" not in d and "jobDescription" in d:
                d["job_description"] = d["jobDescription"]
            return d
        return data



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
