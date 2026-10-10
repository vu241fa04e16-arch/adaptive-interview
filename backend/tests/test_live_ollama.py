import pytest
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.ollama_client import AsyncOllamaClient
from app.schemas.resume import ResumeAnalysisLLMOutput
from app.services.resume_service import ResumeService


class RealStructuredAIProbe(BaseModel):
    domain: str = Field(description="Domain of the question, e.g., Databases")
    core_concept: str = Field(description="Key concept being evaluated")
    suggested_question: str = Field(description="Technical interview question")
    difficulty: str = Field(description="beginner, intermediate, or advanced")


@pytest.mark.live_ollama
@pytest.mark.asyncio
async def test_live_ollama_structured_generation():
    """Live integration test against the real locally running Ollama service.
    
    Calls http://localhost:11434 directly and verifies that real AI inference
    produces valid Pydantic models with zero hardcoded mocks.
    """
    settings = get_settings()
    client = AsyncOllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout_seconds=60.0,
    )

    try:
        # 1. Probe live service health
        health = await client.check_health()
        assert health["status"] == "available", f"Ollama not available at {settings.OLLAMA_BASE_URL}"
        assert health["model_available"] is True, f"Model '{settings.OLLAMA_MODEL}' not loaded in Ollama"

        # 2. Live structured generation test
        prompt = (
            "Generate a technical backend interview question evaluating PostgreSQL concurrency control "
            "and MVCC transaction isolation levels for a senior engineer."
        )

        result = await client.generate_structured(
            prompt=prompt,
            schema=RealStructuredAIProbe,
        )

        # 3. Assert real model output
        assert isinstance(result, RealStructuredAIProbe)
        assert len(result.domain) > 0
        assert len(result.suggested_question) > 15
        assert result.difficulty.lower() in ["beginner", "intermediate", "advanced", "expert"]
        print(f"\n[LIVE OLLAMA TEST SUCCESS] Model: {settings.OLLAMA_MODEL}")
        print(f"Generated Question: {result.suggested_question}")
        print(f"Concept: {result.core_concept} | Difficulty: {result.difficulty}")

    finally:
        await client.aclose()


@pytest.mark.live_ollama
@pytest.mark.asyncio
async def test_live_ollama_resume_analysis():
    """Live integration test executing real Ollama resume skill extraction on local llama3.1."""
    settings = get_settings()
    client = AsyncOllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout_seconds=180.0,
    )
    service = ResumeService(ollama_client=client)

    sample_resume_text = (
        "Jane Doe - Senior Backend Architect\n"
        "Summary: 7+ years designing distributed systems, high-throughput microservices, and database engines.\n"
        "Experience:\n"
        "Senior Backend Architect at CloudFin Corp (2020 - Present):\n"
        "- Migrated monolithic database to PostgreSQL 16 cluster managing 8TB data, tuning MVCC query execution.\n"
        "- Architected real-time event streaming pipeline using Apache Kafka processing 40,000 msg/sec.\n"
        "- Implemented distributed locks with Redis token bucket algorithm.\n"
        "Skills: PostgreSQL, Apache Kafka, Python, Go, Docker, Redis, Distributed Systems."
    )

    try:
        analysis = await service.analyze_resume_with_ollama(
            resume_text=sample_resume_text,
            target_role="Senior Backend Architect",
            target_level="Senior",
        )

        assert isinstance(analysis, ResumeAnalysisLLMOutput)
        assert len(analysis.candidate_overview) > 20
        assert len(analysis.claimed_skills) >= 3
        assert len(analysis.suggested_focus_areas) >= 2

        skill_names = [s.name.lower() for s in analysis.claimed_skills]
        assert any("postgres" in s for s in skill_names)

        print(f"\n[LIVE OLLAMA RESUME EXTRACTION SUCCESS] Model: {settings.OLLAMA_MODEL}")
        print(f"Overview: {analysis.candidate_overview}")
        print(f"Extracted Skills Count: {len(analysis.claimed_skills)}")
        for s in analysis.claimed_skills[:3]:
            print(f" - {s.name} ({s.claimed_proficiency}): {s.context_snippet}")
        print(f"Focus Areas: {analysis.suggested_focus_areas}")

    finally:
        await client.aclose()
