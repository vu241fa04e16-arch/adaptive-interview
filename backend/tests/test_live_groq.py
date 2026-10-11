import os
import pytest
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.groq_client import AsyncGroqClient
from app.schemas.answer import AnswerEvaluationLLM, AnswerSubmitRequest
from app.schemas.question import GeneratedQuestionLLM
from app.schemas.resume import ResumeAnalysisLLMOutput
from app.services.evaluation_service import EvaluationService
from app.services.resume_service import ResumeService


class LiveGroqProbeSchema(BaseModel):
    domain: str = Field(description="Domain of the question, e.g., Databases")
    core_concept: str = Field(description="Key concept being evaluated")
    suggested_question: str = Field(description="Technical interview question")
    difficulty: str = Field(description="beginner, intermediate, or advanced")


@pytest.fixture
def require_groq_api_key():
    settings = get_settings()
    api_key = os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY
    if not api_key:
        pytest.skip("GROQ_API_KEY environment variable is not configured. Skipping live integration test.")
    return api_key


@pytest.mark.live_groq
@pytest.mark.asyncio
async def test_live_groq_health_probe(require_groq_api_key):
    """Probes live Groq OpenAI-compatible API health and models listing."""
    settings = get_settings()
    client = AsyncGroqClient(
        api_key=require_groq_api_key,
        base_url=settings.GROQ_BASE_URL,
        model=settings.GROQ_MODEL,
        timeout_seconds=30.0,
    )

    try:
        health = await client.check_health()
        assert health["status"] == "available"
        assert health["model_available"] is True
        print(f"\n[LIVE GROQ HEALTH SUCCESS] Model: {settings.GROQ_MODEL} is active.")
    finally:
        await client.aclose()


@pytest.mark.live_groq
@pytest.mark.asyncio
async def test_live_groq_structured_generation(require_groq_api_key):
    """Verifies that live Groq inference produces valid structured Pydantic models with real AI."""
    settings = get_settings()
    client = AsyncGroqClient(
        api_key=require_groq_api_key,
        base_url=settings.GROQ_BASE_URL,
        model=settings.GROQ_MODEL,
        timeout_seconds=30.0,
    )

    try:
        prompt = (
            "Generate a technical backend interview question evaluating PostgreSQL concurrency control "
            "and MVCC transaction isolation levels for a senior engineer."
        )

        result = await client.generate_structured(
            prompt=prompt,
            schema=LiveGroqProbeSchema,
        )

        assert isinstance(result, LiveGroqProbeSchema)
        assert len(result.domain) > 0
        assert len(result.suggested_question) > 15
        assert result.difficulty.lower() in ["beginner", "intermediate", "advanced", "expert"]
        print(f"\n[LIVE GROQ GENERATION SUCCESS]\nQuestion: {result.suggested_question}")
        print(f"Concept: {result.core_concept} | Difficulty: {result.difficulty}")
    finally:
        await client.aclose()


@pytest.mark.live_groq
@pytest.mark.asyncio
async def test_live_groq_resume_analysis(require_groq_api_key):
    """Verifies live Groq resume skill extraction on candidate text."""
    settings = get_settings()
    client = AsyncGroqClient(
        api_key=require_groq_api_key,
        base_url=settings.GROQ_BASE_URL,
        model=settings.GROQ_MODEL,
        timeout_seconds=45.0,
    )
    service = ResumeService(ai_client=client)

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
        analysis = await service.analyze_resume_with_groq(
            resume_text=sample_resume_text,
            target_role="Senior Backend Architect",
            target_level="Senior",
        )

        assert isinstance(analysis, ResumeAnalysisLLMOutput)
        assert len(analysis.candidate_overview) > 20
        assert len(analysis.claimed_skills) >= 1

        skill_names = [s.name.lower() for s in analysis.claimed_skills]
        assert any("postgres" in s for s in skill_names)
        print(f"\n[LIVE GROQ RESUME ANALYSIS SUCCESS] Extracted {len(analysis.claimed_skills)} skills.")
    finally:
        await client.aclose()
