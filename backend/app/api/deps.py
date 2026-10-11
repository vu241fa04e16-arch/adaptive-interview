from fastapi import Depends

from app.core.ollama_client import AsyncOllamaClient, get_ollama_client
from app.database import get_db
from app.services.adaptive_engine import AdaptiveEngine
from app.services.evaluation_service import EvaluationService
from app.services.report_service import ReportService
from app.services.resume_service import ResumeService


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


def get_report_service() -> ReportService:
    """Dependency injection for ReportService."""
    return ReportService()


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
    "get_report_service",
    "ReportService",
]
