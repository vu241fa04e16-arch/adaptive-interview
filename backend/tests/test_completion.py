import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.main import app
from app.schemas.answer import AnswerEvaluationLLM
from app.schemas.question import GeneratedQuestionLLM
from app.schemas.report import SessionCompleteResponse


@pytest.fixture
def mock_completion_ollama():
    """Mock Ollama for questions and answers before completion."""
    class MockClient:
        async def check_health(self):
            return {"status": "available", "base_url": "http://localhost:11434", "configured_model": "llama3.1", "model_available": True}

        async def generate_structured(self, prompt, schema, system_prompt=None, options=None):
            if schema == GeneratedQuestionLLM:
                return GeneratedQuestionLLM(
                    question_text="Explain CAP theorem tradeoffs in distributed databases.",
                    key_evaluation_criteria=["Consistency vs Availability", "Partition tolerance inevitability"],
                )
            return AnswerEvaluationLLM(
                score=9.0,
                strengths=["Clear articulation of PACELC theorem extension"],
                weaknesses=[],
                feedback="Outstanding answer",
                improvement_suggestions=[],
            )

        async def aclose(self):
            pass

    return MockClient()


@pytest.fixture
def interview_with_question_and_answer(client: TestClient, mock_completion_ollama) -> tuple[str, str]:
    """Sets up an interview session with 1 question and 1 evaluated answer."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_completion_ollama

    # 1. Create session
    resp = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Carol Danvers",
            "candidate_email": "carol@example.com",
            "target_role": "Principal Distributed Systems Engineer",
            "target_level": "Principal",
            "time_limit_minutes": 60,
        },
    )
    session_id = resp.json()["sessionId"]

    # 2. Next question
    resp_q = client.get(f"/api/sessions/{session_id}/next-question")
    question_id = resp_q.json()["question_id"]

    # 3. Submit answer
    resp_a = client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": question_id, "answer_text": "In distributed networks, network partitions are inevitable."},
    )
    assert resp_a.status_code == 200

    app.dependency_overrides.clear()
    return session_id, question_id


def test_complete_session_success(client: TestClient, interview_with_question_and_answer):
    """Verifies that POST /complete marks the interview as completed and returns summary metrics."""
    session_id, _ = interview_with_question_and_answer

    resp = client.post(f"/api/sessions/{session_id}/complete")
    assert resp.status_code == 200
    data = resp.json()

    validated = SessionCompleteResponse.model_validate(data)
    assert validated.sessionId == session_id
    assert validated.status == "completed"
    assert validated.total_questions == 1
    assert validated.total_answers == 1
    assert validated.average_score == 9.0
    assert validated.completed_at is not None


def test_complete_session_idempotent(client: TestClient, interview_with_question_and_answer):
    """Verifies that completing an already completed session is idempotent and preserves timestamps."""
    session_id, _ = interview_with_question_and_answer

    resp1 = client.post(f"/api/sessions/{session_id}/complete")
    assert resp1.status_code == 200
    time1 = resp1.json()["completed_at"]

    # Call complete again
    resp2 = client.post(f"/api/sessions/{session_id}/complete")
    assert resp2.status_code == 200
    assert resp2.json()["completed_at"] == time1
    assert resp2.json()["status"] == "completed"


def test_complete_session_prevents_subsequent_activity(
    client: TestClient,
    interview_with_question_and_answer,
    mock_completion_ollama,
):
    """Verifies that after completion, asking new questions, answering, or sending events is rejected."""
    session_id, question_id = interview_with_question_and_answer
    app.dependency_overrides[get_ollama_client] = lambda: mock_completion_ollama

    # Complete session
    resp_c = client.post(f"/api/sessions/{session_id}/complete")
    assert resp_c.status_code == 200

    # 1. Attempt next-question -> HTTP 400
    resp_q = client.get(f"/api/sessions/{session_id}/next-question")
    assert resp_q.status_code == 400
    assert resp_q.json()["error"] == "INVALID_SESSION_STATE"

    # 2. Attempt submit answer -> HTTP 400
    resp_a = client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": question_id, "answer_text": "Late answer"},
    )
    assert resp_a.status_code == 400
    assert resp_a.json()["error"] == "INVALID_SESSION_STATE"

    # 3. Attempt record event -> HTTP 400
    resp_e = client.post(
        f"/api/sessions/{session_id}/events",
        json={"event_type": "TAB_SWITCH"},
    )
    assert resp_e.status_code == 400
    assert resp_e.json()["error"] == "INVALID_SESSION_STATE"

    app.dependency_overrides.clear()


def test_complete_session_invalid_uuid_returns_400(client: TestClient):
    """Verifies invalid sessionId returns HTTP 400."""
    resp = client.post("/api/sessions/not-a-valid-uuid/complete")
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_SESSION_STATE"


def test_complete_session_unknown_session_returns_404(client: TestClient):
    """Verifies unknown sessionId returns HTTP 404."""
    fake_id = str(uuid.uuid4())
    resp = client.post(f"/api/sessions/{fake_id}/complete")
    assert resp.status_code == 404
    assert resp.json()["error"] == "RESOURCE_NOT_FOUND"
