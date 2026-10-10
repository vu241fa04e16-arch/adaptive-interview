import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.session import InterviewSession


class ResumeAnalysis(Base):
    """Stores extracted resume text, SHA-256 integrity hash, and Ollama-extracted skill claims."""

    __tablename__ = "resume_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    parsed_text_length: Mapped[int] = mapped_column(Integer, nullable=False)
    parsed_text: Mapped[str] = mapped_column(Text, nullable=False)

    candidate_overview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    claimed_skills: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    projects: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    suggested_focus_areas: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    raw_model_output: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped["InterviewSession"] = relationship(
        "InterviewSession",
        back_populates="resume_analysis",
    )

    def __repr__(self) -> str:
        return f"<ResumeAnalysis(id={self.id}, session_id={self.session_id}, file_name={self.file_name})>"
