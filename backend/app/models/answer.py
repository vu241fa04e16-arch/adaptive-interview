import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List
from sqlalchemy import DateTime, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.session import InterviewSession
    from app.models.question import Question


class Answer(Base):
    """Candidate answer submission along with AI rubric evaluation."""

    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    strengths: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    weaknesses: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    improvement_suggestions: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    raw_evaluation: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped["InterviewSession"] = relationship(
        "InterviewSession",
        back_populates="answers",
    )
    question: Mapped["Question"] = relationship(
        "Question",
        back_populates="answer",
    )

    def __repr__(self) -> str:
        return f"<Answer(id={self.id}, question_id={self.question_id}, score={self.score})>"
