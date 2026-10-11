import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.main import app
from app.schemas.answer import AnswerEvaluationLLM
from app.schemas.event import EventResponse
from app.schemas.question import GeneratedQuestionLLM


@pytest.fixture
def mock_session_ollama():
    """Mock Ollama client for generating test questions."""
    class MockClient:
        async def check_health(self):
            return {"status": "available", "base_url": "http://localhost:11434", "configured_model": "llama3.1", "model_available": True}

        async def generate_structured(self, prompt, schema, system_prompt=None, options=None):
            if schema == GeneratedQuestionLLM:
                return GeneratedQuestionLLM(
                    question_text="Describe database sharding strategies?",
                    key_evaluation_criteria=["Range vs Hash partitioning", "Cross-shard joins"],
                )
            return AnswerEvaluationLLM(
                score=7.5,
                strengths=["Good understanding of hash sharding"],
                weaknesses=["Did not discuss rebalancing"],
                feedback="Solid overview",
                improvement_suggestions=["Study consistent hashing"],
            )

        async def aclose(self):
            pass

    return MockClient()


@pytest.fixture
def created_session_id(client: TestClient) -> str:
    """Creates a basic session for event testing."""
    resp = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Event Candidate",
            "candidate_email": "candidate@example.com",
            "target_role": "Backend Engineer",
            "target_level": "Mid",
            "time_limit_minutes": 30,
        },
    )
    assert resp.status_code == 201
    return resp.json()["sessionId"]


def test_record_event_success(client: TestClient, created_session_id: str):
    """Verifies successful telemetry event recording and progress output."""
    payload = {
        "event_type": "TAB_SWITCH",
        "event_data": {"blur_duration_seconds": 4.2},
    }

    resp = client.post(f"/api/sessions/{created_session_id}/events", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    validated = EventResponse.model_validate(data)
    assert validated.sessionId == created_session_id
    assert validated.event_type == "TAB_SWITCH"
    assert validated.progress.questions_asked == 0
    assert validated.progress.answers_submitted == 0
    assert validated.progress.current_status == "created"
    assert validated.progress.time_remaining_seconds > 0


def test_record_event_tracks_actual_progress(
    client: TestClient,
    created_session_id: str,
    mock_session_ollama,
):
    """Verifies that events accurately reflect asked questions and submitted answers."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_session_ollama

    # 1. Ask a question
    resp_q = client.get(f"/api/sessions/{created_session_id}/next-question")
    assert resp_q.status_code == 200
    q_id = resp_q.json()["question_id"]

    # 2. Submit an answer
    resp_ans = client.post(
        f"/api/sessions/{created_session_id}/answers",
        json={"question_id": q_id, "answer_text": "Sharding distributes data horizontally across nodes."},
    )
    assert resp_ans.status_code == 200

    # 3. Ask second question
    resp_q2 = client.get(f"/api/sessions/{created_session_id}/next-question")
    assert resp_q2.status_code == 200

    # 4. Record event
    resp_evt = client.post(
        f"/api/sessions/{created_session_id}/events",
        json={"event_type": "WINDOW_FOCUS", "event_data": {}},
    )
    assert resp_evt.status_code == 200
    data = resp_evt.json()

    assert data["progress"]["questions_asked"] == 2
    assert data["progress"]["answers_submitted"] == 1
    assert data["progress"]["current_status"] == "in_progress"

    app.dependency_overrides.clear()


def test_record_event_invalid_uuid_returns_400(client: TestClient):
    """Verifies malformed sessionId returns HTTP 400."""
    resp = client.post(
        "/api/sessions/invalid-uuid/events",
        json={"event_type": "TAB_SWITCH"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_SESSION_STATE"


def test_record_event_unknown_session_returns_404(client: TestClient):
    """Verifies unknown sessionId returns HTTP 404."""
    fake_id = str(uuid.uuid4())
    resp = client.post(
        f"/api/sessions/{fake_id}/events",
        json={"event_type": "TAB_SWITCH"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "RESOURCE_NOT_FOUND"


def test_record_event_invalid_event_type_returns_422(client: TestClient, created_session_id: str):
    """Verifies that an empty or single-character event_type returns HTTP 422 validation error."""
    resp = client.post(
        f"/api/sessions/{created_session_id}/events",
        json={"event_type": "x"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "VALIDATION_ERROR"
