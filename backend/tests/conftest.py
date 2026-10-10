import io
import os
import sys
import docx
import pypdf
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.deps import get_ollama_client
from app.core.exceptions import (
    AIProviderUnavailableException,
    AIStructuredGenerationException,
)
from app.main import app
from app.schemas.resume import (
    ClaimedSkill,
    ProjectSummary,
    ResumeAnalysisLLMOutput,
)


@pytest.fixture
def client() -> TestClient:
    """Synchronous FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_ollama_healthy():
    """Mock Ollama client simulating a healthy service with llama3.1 loaded."""
    class MockClient:
        async def check_health(self):
            return {
                "status": "available",
                "base_url": "http://localhost:11434",
                "configured_model": "llama3.1",
                "model_available": True,
                "available_models": ["llama3.1:latest", "llama3.2:latest"],
            }

        async def aclose(self):
            pass

    return MockClient()


@pytest.fixture
def mock_ollama_unavailable():
    """Mock Ollama client simulating connection refusal."""
    class MockClient:
        async def check_health(self):
            return {
                "status": "unavailable",
                "base_url": "http://localhost:11434",
                "configured_model": "llama3.1",
                "model_available": False,
                "error": "Cannot connect to Ollama at http://localhost:11434: Connection refused",
            }

        async def generate_structured(self, *args, **kwargs):
            raise AIProviderUnavailableException("Ollama service unreachable on port 11434.")

        async def aclose(self):
            pass

    return MockClient()


@pytest.fixture
def mock_resume_ollama_client():
    """Mock Ollama client returning a deterministic, valid ResumeAnalysisLLMOutput."""
    class MockResumeClient:
        async def check_health(self):
            return {
                "status": "available",
                "base_url": "http://localhost:11434",
                "configured_model": "llama3.1",
                "model_available": True,
            }

        async def generate_structured(self, prompt, schema, system_prompt=None, options=None):
            return ResumeAnalysisLLMOutput(
                candidate_overview=(
                    "Senior Backend Engineer with 7+ years designing high-throughput distributed architectures, "
                    "specializing in PostgreSQL transaction isolation and Kafka event streams."
                ),
                claimed_skills=[
                    ClaimedSkill(
                        name="PostgreSQL",
                        claimed_experience_years=6.0,
                        claimed_proficiency="Expert",
                        context_snippet="Led PostgreSQL migration and optimized MVCC query patterns across 10TB database.",
                    ),
                    ClaimedSkill(
                        name="Distributed Systems",
                        claimed_experience_years=4.5,
                        claimed_proficiency="Advanced",
                        context_snippet="Architected distributed event messaging pipelines processing 50k events/sec.",
                    ),
                    ClaimedSkill(
                        name="Apache Kafka",
                        claimed_experience_years=3.0,
                        claimed_proficiency="Intermediate",
                        context_snippet="Configured Kafka consumer groups and idempotency keys.",
                    ),
                ],
                projects=[
                    ProjectSummary(
                        project_name="High-Throughput Ledger Engine",
                        technologies=["PostgreSQL", "Kafka", "Python", "FastAPI"],
                        highlights=[
                            "Achieved 99.99% availability with zero double-entry errors using SSI isolation.",
                            "Reduced query latency by 45% via partitioning and composite indexing.",
                        ],
                    )
                ],
                suggested_focus_areas=[
                    "PostgreSQL MVCC SSI versus Read Committed isolation tradeoffs",
                    "Kafka exactly-once semantics and transactional coordinator recovery",
                    "Distributed deadlocks and lock escalation in multi-tenant schemas",
                ],
            )

        async def aclose(self):
            pass

    return MockResumeClient()


@pytest.fixture
def sample_docx_bytes() -> bytes:
    """Generates realistic valid DOCX resume binary content."""
    doc = docx.Document()
    doc.add_heading("Jane Doe - Senior Backend Architect", 0)
    doc.add_paragraph("Email: jane.doe@example.com | Location: Bengaluru, India")
    doc.add_heading("Summary", level=1)
    doc.add_paragraph(
        "Staff Backend Engineer with over 7 years of specialized expertise in high-concurrency systems, "
        "PostgreSQL performance tuning, distributed consensus, and event-driven architecture using Kafka."
    )
    doc.add_heading("Experience", level=1)
    doc.add_paragraph(
        "Senior Backend Architect at CloudFin Corp (2020 - Present):\n"
        "- Led PostgreSQL migration and optimized MVCC query patterns across 10TB database.\n"
        "- Architected distributed event messaging pipelines processing 50k events/sec with Apache Kafka.\n"
        "- Enforced Serializable Snapshot Isolation (SSI) for financial double-entry bookkeeping."
    )
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Generates realistic valid PDF resume binary content."""
    minimal_pdf = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 260 >> stream
BT /F1 12 Tf 50 720 Td (Jane Doe - Senior Backend Architect) Tj
0 -20 Td (Summary: 7+ years in distributed architecture, PostgreSQL internals, and Kafka event streaming.) Tj
0 -20 Td (Experience: Led PostgreSQL migration across 10TB database; architected Kafka pipelines at CloudFin Corp.) Tj
ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000555 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
630
%%EOF"""
    return minimal_pdf
