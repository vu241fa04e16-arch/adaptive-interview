from typing import Optional
from fastapi import Depends

from app.core.groq_client import AsyncGroqClient, get_groq_client
from app.database import get_db
from app.services.adaptive_engine import AdaptiveEngine
from app.services.evaluation_service import EvaluationService
from app.services.integrity_service import IntegrityService
from app.services.report_service import ReportService
from app.services.resume_service import ResumeService
from app.services.skill_gap_service import SkillGapService
from app.services.transcription_service import TranscriptionService

# Backward compatibility aliases
AsyncOllamaClient = AsyncGroqClient
get_ollama_client = get_groq_client

_transcription_service_instance: Optional[TranscriptionService] = None


def get_resume_service(
    ai_client: AsyncGroqClient = Depends(get_groq_client),
) -> ResumeService:
    """Dependency injection for ResumeService using Groq client."""
    return ResumeService(ai_client=ai_client)


def get_adaptive_engine(
    ai_client: AsyncGroqClient = Depends(get_groq_client),
) -> AdaptiveEngine:
    """Dependency injection for AdaptiveEngine using Groq client."""
    return AdaptiveEngine(ai_client=ai_client)


def get_evaluation_service(
    ai_client: AsyncGroqClient = Depends(get_groq_client),
) -> EvaluationService:
    """Dependency injection for EvaluationService using Groq client."""
    return EvaluationService(ai_client=ai_client)


def get_integrity_service() -> IntegrityService:
    """Dependency injection for IntegrityService."""
    return IntegrityService()


def get_skill_gap_service(
    ai_client: AsyncGroqClient = Depends(get_groq_client),
) -> SkillGapService:
    """Dependency injection for SkillGapService using Groq client."""
    return SkillGapService(ai_client=ai_client)


def get_report_service(
    ai_client: AsyncGroqClient = Depends(get_groq_client),
    skill_gap_service: SkillGapService = Depends(get_skill_gap_service),
    integrity_service: IntegrityService = Depends(get_integrity_service),
) -> ReportService:
    """Dependency injection for ReportService using Groq client."""
    return ReportService(
        ai_client=ai_client,
        skill_gap_service=skill_gap_service,
        integrity_service=integrity_service,
    )


def get_transcription_service() -> TranscriptionService:
    """Dependency injection for TranscriptionService (singleton for lazy model reuse)."""
    global _transcription_service_instance
    if _transcription_service_instance is None:
        _transcription_service_instance = TranscriptionService()
    return _transcription_service_instance


__all__ = [
    "get_db",
    "get_groq_client",
    "get_ollama_client",
    "AsyncGroqClient",
    "AsyncOllamaClient",
    "get_resume_service",
    "ResumeService",
    "get_adaptive_engine",
    "AdaptiveEngine",
    "get_evaluation_service",
    "EvaluationService",
    "get_integrity_service",
    "IntegrityService",
    "get_skill_gap_service",
    "SkillGapService",
    "get_report_service",
    "ReportService",
    "get_transcription_service",
    "TranscriptionService",
]
