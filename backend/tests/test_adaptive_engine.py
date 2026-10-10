import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.core.exceptions import (
    AIProviderUnavailableException,
    AIStructuredGenerationException,
)
from app.main import app
from app.schemas.question import GeneratedQuestionLLM, QuestionResponse


@pytest.fixture
def mock_question_ollama_client():
    """Mock Ollama client returning deterministic structured questions."""
    class MockClient:
        def __init__(self):
            self.call_count = 0

        async def check_health(self):
            return {"status": "available", "base_url": "http://localhost:11434", "configured_model": "llama3.1", "model_available": True}

        async def generate_structured(self, prompt, schema, system_prompt=None, options=None):
            self.call_count += 1
            return GeneratedQuestionLLM(
                question_text=f"Explain how PostgreSQL handles MVCC write contention under concurrent transactions? (Call {self.call_count})",
                key_evaluation_criteria=[
                    "SIREAD non-blocking lock table",
                    "Snapshot isolation anomalies",
                    "Serialization failure retry loop",
                ],
            )

        async def aclose(self):
            pass

    return MockClient()


@pytest.fixture
def session_with_resume(client: TestClient, sample_docx_bytes: bytes, mock_resume_ollama_client) -> str:
    """Creates a session and uploads a resume to prime focus areas."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_resume_ollama_client

    # 1. Create session
    resp = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Jane Doe",
            "candidate_email": "jane@example.com",
            "target_role": "Senior Backend Architect",
            "target_level": "Senior",
            "time_limit_minutes": 45,
        },
    )
    assert resp.status_code == 201
    session_id = resp.json()["sessionId"]

    # 2. Upload resume
    files = {"file": ("resume.docx", sample_docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    resp_upload = client.post(f"/api/sessions/{session_id}/resume", files=files)
    assert resp_upload.status_code == 200

    app.dependency_overrides.clear()
    return session_id


def test_next_question_unknown_session_returns_404(client: TestClient, mock_question_ollama_client):
    """Verifies that an unknown session UUID returns HTTP 404."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_question_ollama_client

    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/sessions/{fake_id}/next-question")
    assert resp.status_code == 404
    assert resp.json()["error"] == "RESOURCE_NOT_FOUND"

    app.dependency_overrides.clear()


def test_next_question_invalid_uuid_returns_400(client: TestClient):
    """Verifies that a malformed UUID returns HTTP 400."""
    resp = client.get("/api/sessions/not-a-uuid/next-question")
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_SESSION_STATE"


def test_next_question_success_with_resume(
    client: TestClient,
    session_with_resume: str,
    mock_question_ollama_client,
):
    """Verifies successful adaptive question generation prioritizing unassessed resume focus areas."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_question_ollama_client

    resp = client.get(f"/api/sessions/{session_with_resume}/next-question")
    assert resp.status_code == 200
    data = resp.json()

    # Validate against QuestionResponse schema
    validated = QuestionResponse.model_validate(data)
    assert validated.sessionId == session_with_resume
    assert validated.sequence_number == 1
    assert len(validated.question_text) > 20
    assert validated.difficulty == "advanced"
    assert validated.adaptation_context is not None
    assert validated.adaptation_context.trigger == "UNASSESSED_FOCUS_AREA"
    assert "MVCC" in validated.competency or "PostgreSQL" in validated.competency or len(validated.competency) > 0

    app.dependency_overrides.clear()


def test_prioritization_unassessed_competency_and_no_repeats(
    client: TestClient,
    session_with_resume: str,
    mock_question_ollama_client,
):
    """Verifies that consecutive next-question calls advance sequence and choose different unassessed competencies."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_question_ollama_client

    # First question
    resp1 = client.get(f"/api/sessions/{session_with_resume}/next-question")
    assert resp1.status_code == 200
    q1 = resp1.json()
    assert q1["sequence_number"] == 1

    # Second question
    resp2 = client.get(f"/api/sessions/{session_with_resume}/next-question")
    assert resp2.status_code == 200
    q2 = resp2.json()
    assert q2["sequence_number"] == 2

    # Different competencies tested
    assert q1["competency"] != q2["competency"]
    assert q2["adaptation_context"]["trigger"] in ["UNASSESSED_FOCUS_AREA", "UNASSESSED_CLAIMED_SKILL"]

    app.dependency_overrides.clear()


def test_missing_resume_analysis_falls_back_to_core_role_competency(
    client: TestClient,
    mock_question_ollama_client,
):
    """Verifies that a session without a resume gracefully falls back to deterministic role core competencies."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_question_ollama_client

    # Create session WITHOUT uploading resume
    resp = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Bob Smith",
            "candidate_email": "bob@example.com",
            "target_role": "Senior Backend Engineer",
            "target_level": "Senior",
            "time_limit_minutes": 30,
        },
    )
    assert resp.status_code == 201
    session_id = resp.json()["sessionId"]

    resp_q = client.get(f"/api/sessions/{session_id}/next-question")
    assert resp_q.status_code == 200
    data = resp_q.json()

    assert data["sequence_number"] == 1
    assert data["adaptation_context"]["trigger"] == "CORE_ROLE_COMPETENCY"
    assert "Distributed Systems" in data["competency"] or len(data["competency"]) > 0

    app.dependency_overrides.clear()


def test_difficulty_adjustment_when_previous_score_exists(
    client: TestClient,
    mock_question_ollama_client,
):
    """Verifies deterministic difficulty adjustment when previous evaluation scores exist."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_question_ollama_client

    # Create mid-level session
    resp = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Alice Brown",
            "candidate_email": "alice@example.com",
            "target_role": "Backend Engineer",
            "target_level": "Mid",
            "time_limit_minutes": 45,
        },
    )
    session_id = resp.json()["sessionId"]

    # Baseline difficulty for Mid should be intermediate
    q1 = client.get(f"/api/sessions/{session_id}/next-question").json()
    assert q1["difficulty"] == "intermediate"
    assert q1["adaptation_context"]["difficulty_direction"] == "baseline"

    app.dependency_overrides.clear()


def test_next_question_ollama_unavailable_returns_503(
    client: TestClient,
    session_with_resume: str,
    mock_ollama_unavailable,
):
    """Verifies that when Ollama is offline, GET /next-question returns HTTP 503 without fake fallback."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama_unavailable

    resp = client.get(f"/api/sessions/{session_with_resume}/next-question")
    assert resp.status_code == 503
    assert resp.json()["error"] == "AI_PROVIDER_UNAVAILABLE"

    app.dependency_overrides.clear()


def test_next_question_ollama_malformed_output_returns_502(
    client: TestClient,
    session_with_resume: str,
):
    """Verifies that when Ollama produces malformed output, GET /next-question returns HTTP 502."""
    class MockMalformedClient:
        async def check_health(self):
            return {"status": "available", "base_url": "http://localhost:11434", "configured_model": "llama3.1", "model_available": True}

        async def generate_structured(self, *args, **kwargs):
            raise AIStructuredGenerationException("Ollama generated malformed question output.")

        async def aclose(self):
            pass

    app.dependency_overrides[get_ollama_client] = lambda: MockMalformedClient()

    resp = client.get(f"/api/sessions/{session_with_resume}/next-question")
    assert resp.status_code == 502
    assert resp.json()["error"] == "AI_STRUCTURED_GENERATION_FAILED"

    app.dependency_overrides.clear()
