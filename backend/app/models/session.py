import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.resume import ResumeAnalysis


class InterviewSession(Base):
    """Interview session model tracking candidate details, status, and competency state."""

    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_role: Mapped[str] = mapped_column(String(255), nullable=False)
    target_level: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="created", nullable=False)
    time_limit_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)

    competency_state: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    resume_analysis: Mapped[Optional["ResumeAnalysis"]] = relationship(
        "ResumeAnalysis",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<InterviewSession(id={self.id}, candidate={self.candidate_name}, status={self.status})>"
