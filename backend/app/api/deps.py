from fastapi import Depends

from app.core.ollama_client import AsyncOllamaClient, get_ollama_client
from app.database import get_db
from app.services.adaptive_engine import AdaptiveEngine
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


__all__ = [
    "get_db",
    "get_ollama_client",
    "AsyncOllamaClient",
    "get_resume_service",
    "ResumeService",
    "get_adaptive_engine",
    "AdaptiveEngine",
]
