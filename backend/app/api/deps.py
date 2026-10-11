from typing import Optional
from fastapi import Depends

from app.core.ollama_client import AsyncOllamaClient, get_ollama_client
from app.database import get_db
from app.services.adaptive_engine import AdaptiveEngine
from app.services.evaluation_service import EvaluationService
from app.services.integrity_service import IntegrityService
from app.services.report_service import ReportService
from app.services.resume_service import ResumeService
from app.services.skill_gap_service import SkillGapService
from app.services.transcription_service import TranscriptionService

_transcription_service_instance: Optional[TranscriptionService] = None


def get_resume_service(
    ollama_client: AsyncOllamaClient = Depends(get_ollama_client),
) -> ResumeService:
    """Dependency injection for ResumeService."""
    return ResumeService(ollama_client=ollama_client)


def get_adaptive_engine(
    ollama_client: AsyncOllamaClient = Depends(get_ollama_client),
) -> AdaptiveEngine:
    """Dependency injection for AdaptiveEngine."""
    return AdaptiveEngine(ollama_client=ollama_client)


def get_evaluation_service(
    ollama_client: AsyncOllamaClient = Depends(get_ollama_client),
) -> EvaluationService:
    """Dependency injection for EvaluationService."""
    return EvaluationService(ollama_client=ollama_client)


def get_integrity_service() -> IntegrityService:
    """Dependency injection for IntegrityService."""
    return IntegrityService()


def get_skill_gap_service(
    ollama_client: AsyncOllamaClient = Depends(get_ollama_client),
) -> SkillGapService:
    """Dependency injection for SkillGapService."""
    return SkillGapService(ollama_client=ollama_client)


def get_report_service(
    ollama_client: AsyncOllamaClient = Depends(get_ollama_client),
    skill_gap_service: SkillGapService = Depends(get_skill_gap_service),
    integrity_service: IntegrityService = Depends(get_integrity_service),
) -> ReportService:
    """Dependency injection for ReportService."""
    return ReportService(
        ollama_client=ollama_client,
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
    "get_ollama_client",
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
