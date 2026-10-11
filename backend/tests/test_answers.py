import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.core.exceptions import (
    AIProviderUnavailableException,
    AIStructuredGenerationException,
)
from app.main import app
from app.schemas.answer import AnswerEvaluationLLM, AnswerResponse
from app.schemas.question import GeneratedQuestionLLM


@pytest.fixture
def mock_evaluation_ollama_client():
    """Mock Ollama client returning deterministic structured evaluation."""
    class MockClient:
        def __init__(self):
            self.eval_call_count = 0

        async def check_health(self):
            return {
                "status": "available",
                "base_url": "http://localhost:11434",
                "configured_model": "llama3.1",
                "model_available": True,
            }

        async def generate_structured(self, prompt, schema, system_prompt=None, options=None):
            if schema == GeneratedQuestionLLM:
                return GeneratedQuestionLLM(
                    question_text="How do PostgreSQL MVCC snapshots prevent dirty reads?",
                    key_evaluation_criteria=["Read Committed isolation", "Active transaction XID snapshot list"],
                )
            self.eval_call_count += 1
            return AnswerEvaluationLLM(
                score=8.5,
                strengths=[
                    "Clearly articulated active transaction snapshot array (xmin, xmax, xip_list).",
                    "Correctly differentiated Read Committed statement-level snapshots from Serializable snapshots.",
                ],
                weaknesses=[
                    "Did not touch upon frozen XID vacuum cleanup.",
                ],
                feedback="Strong technical answer demonstrating rigorous understanding of PostgreSQL MVCC mechanics.",
                improvement_suggestions=[
                    "Review autovacuum freezing parameters and wraparound prevention.",
                ],
            )

        async def aclose(self):
            pass

    return MockClient()


@pytest.fixture
def active_session_and_question(client: TestClient, mock_evaluation_ollama_client):
    """Sets up a session and generates one question."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_evaluation_ollama_client

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

    # 2. Generate question
    resp_q = client.get(f"/api/sessions/{session_id}/next-question")
    assert resp_q.status_code == 200
    question_id = resp_q.json()["question_id"]

    app.dependency_overrides.clear()
    return session_id, question_id


def test_submit_answer_success(
    client: TestClient,
    active_session_and_question,
    mock_evaluation_ollama_client,
):
    """Verifies successful candidate answer submission and rubric-based Ollama evaluation."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_evaluation_ollama_client

    payload = {
        "question_id": question_id,
        "answer_text": (
            "In PostgreSQL, Read Committed transactions take a new snapshot at the beginning of each query. "
            "The snapshot contains xmin, xmax, and a list of active transaction IDs. Tuples created after xmax "
            "or active in xip_list are ignored, thus dirty reads cannot occur."
        ),
    }

    resp = client.post(f"/api/sessions/{session_id}/answers", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Verify response schema
    validated = AnswerResponse.model_validate(data)
    assert validated.sessionId == session_id
    assert validated.question_id == question_id
    assert validated.score == 8.5
    assert len(validated.strengths) == 2
    assert len(validated.weaknesses) == 1
    assert "MVCC" in validated.feedback
    assert len(validated.improvement_suggestions) == 1

    app.dependency_overrides.clear()


def test_submit_answer_duplicate_submission_is_safe(
    client: TestClient,
    active_session_and_question,
    mock_evaluation_ollama_client,
):
    """Verifies that duplicate submission for the same question safely returns existing evaluation without re-running AI."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_evaluation_ollama_client

    payload = {
        "question_id": question_id,
        "answer_text": "First submission text explaining MVCC snapshot mechanics in depth.",
    }

    resp1 = client.post(f"/api/sessions/{session_id}/answers", json=payload)
    assert resp1.status_code == 200
    assert mock_evaluation_ollama_client.eval_call_count == 1
    first_ans_id = resp1.json()["answer_id"]

    # Re-submit duplicate
    resp2 = client.post(f"/api/sessions/{session_id}/answers", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["answer_id"] == first_ans_id
    # Call count should still be 1 (no re-inference)
    assert mock_evaluation_ollama_client.eval_call_count == 1

    app.dependency_overrides.clear()


def test_submit_answer_unknown_session_returns_404(client: TestClient, mock_evaluation_ollama_client):
    """Verifies that an unknown session UUID returns HTTP 404."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_evaluation_ollama_client
    fake_session = str(uuid.uuid4())
    fake_q = str(uuid.uuid4())

    resp = client.post(
        f"/api/sessions/{fake_session}/answers",
        json={"question_id": fake_q, "answer_text": "My answer"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "RESOURCE_NOT_FOUND"

    app.dependency_overrides.clear()


def test_submit_answer_unknown_question_returns_404(
    client: TestClient,
    active_session_and_question,
    mock_evaluation_ollama_client,
):
    """Verifies that a valid session with an unknown question returns HTTP 404."""
    session_id, _ = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_evaluation_ollama_client
    fake_q = str(uuid.uuid4())

    resp = client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": fake_q, "answer_text": "My answer"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "RESOURCE_NOT_FOUND"

    app.dependency_overrides.clear()


def test_submit_answer_invalid_uuid_returns_400(client: TestClient):
    """Verifies that invalid UUID strings return HTTP 400."""
    resp = client.post(
        "/api/sessions/invalid-uuid/answers",
        json={"question_id": str(uuid.uuid4()), "answer_text": "Answer"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_SESSION_STATE"


def test_submit_answer_ollama_unavailable_returns_503(
    client: TestClient,
    active_session_and_question,
    mock_ollama_unavailable,
):
    """Verifies HTTP 503 when Ollama is offline."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama_unavailable

    resp = client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": question_id, "answer_text": "Candidate explanation"},
    )
    assert resp.status_code == 503
    assert resp.json()["error"] == "AI_PROVIDER_UNAVAILABLE"

    app.dependency_overrides.clear()


def test_submit_answer_ollama_malformed_returns_502(
    client: TestClient,
    active_session_and_question,
):
    """Verifies HTTP 502 when Ollama produces malformed JSON output."""
    session_id, question_id = active_session_and_question

    class MockMalformedClient:
        async def check_health(self):
            return {"status": "available", "base_url": "http://localhost:11434", "configured_model": "llama3.1", "model_available": True}

        async def generate_structured(self, *args, **kwargs):
            raise AIStructuredGenerationException("Ollama generated invalid evaluation JSON.")

        async def aclose(self):
            pass

    app.dependency_overrides[get_ollama_client] = lambda: MockMalformedClient()

    resp = client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": question_id, "answer_text": "Candidate explanation"},
    )
    assert resp.status_code == 502
    assert resp.json()["error"] == "AI_STRUCTURED_GENERATION_FAILED"

    app.dependency_overrides.clear()
