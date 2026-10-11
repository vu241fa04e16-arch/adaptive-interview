import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.core.exceptions import (
    AIProviderUnavailableException,
    AIStructuredGenerationException,
)
from app.main import app
from app.schemas.answer import AnswerEvaluationLLM
from app.schemas.question import GeneratedQuestionLLM, QuestionResponse
from app.services.adaptive_engine import AdaptiveEngine


@pytest.fixture
def mock_question_ollama_client():
    """Mock Ollama client returning deterministic structured questions and answer evaluations."""
    class MockClient:
        def __init__(self):
            self.call_count = 0
            self.eval_score = 8.5

        async def check_health(self):
            return {"status": "available", "base_url": "http://localhost:11434", "configured_model": "llama3.1", "model_available": True}

        async def generate_structured(self, prompt, schema, system_prompt=None, options=None):
            self.call_count += 1
            if schema == GeneratedQuestionLLM:
                return GeneratedQuestionLLM(
                    question_text=f"Explain how PostgreSQL handles MVCC write contention under concurrent transactions? (Call {self.call_count})",
                    key_evaluation_criteria=[
                        "SIREAD non-blocking lock table",
                        "Snapshot isolation anomalies",
                        "Serialization failure retry loop",
                    ],
                )
            elif schema == AnswerEvaluationLLM:
                return AnswerEvaluationLLM(
                    score=self.eval_score,
                    strengths=["SIREAD lock escalation", "Serialization failure handling"],
                    weaknesses=["Could clarify read committed vs SSI write skew differences"],
                    feedback="Strong conceptual explanation with clear architectural tradeoffs.",
                    improvement_suggestions=["Review predicate lock memory limits"],
                )
            raise ValueError(f"Unexpected schema: {schema}")

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


def test_unanswered_question_competency_remains_unassessed_with_anti_repetition(
    client: TestClient,
    session_with_resume: str,
    mock_question_ollama_client,
):
    """Verifies that unanswered questions leave the competency unassessed while advancing sequence and avoiding repeat text."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_question_ollama_client

    # First question generated
    resp1 = client.get(f"/api/sessions/{session_with_resume}/next-question")
    assert resp1.status_code == 200
    q1 = resp1.json()
    assert q1["sequence_number"] == 1

    # Second question generated WITHOUT answering the first question
    resp2 = client.get(f"/api/sessions/{session_with_resume}/next-question")
    assert resp2.status_code == 200
    q2 = resp2.json()
    assert q2["sequence_number"] == 2

    # Because question 1 was not answered or evaluated, its competency remains unassessed
    assert q1["competency"] == q2["competency"]
    assert q2["adaptation_context"]["trigger"] == "UNASSESSED_FOCUS_AREA"
    # Question text should be different (anti-repetition avoids duplicate text)
    assert q1["question_text"] != q2["question_text"]

    app.dependency_overrides.clear()


def test_evaluated_answer_marks_competency_assessed_and_advances_to_next_focus_area(
    client: TestClient,
    session_with_resume: str,
    mock_question_ollama_client,
):
    """Verifies that once an answer is submitted and evaluated, the competency is marked assessed and the engine advances."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_question_ollama_client

    # 1. First question generated
    resp1 = client.get(f"/api/sessions/{session_with_resume}/next-question")
    assert resp1.status_code == 200
    q1 = resp1.json()
    assert q1["sequence_number"] == 1
    competency_q1 = q1["competency"]

    # 2. Submit candidate answer for question 1
    ans_resp = client.post(
        f"/api/sessions/{session_with_resume}/answers",
        json={
            "question_id": q1["question_id"],
            "answer_text": "PostgreSQL MVCC uses xmin/xmax transaction visibility checks with SSI conflict graphs to prevent write skew.",
            "time_taken_seconds": 90,
        },
    )
    assert ans_resp.status_code == 200
    eval_data = ans_resp.json()
    assert eval_data["score"] == 8.5
    assert eval_data["competency"] == competency_q1

    # 3. Second question generated AFTER evaluation
    resp2 = client.get(f"/api/sessions/{session_with_resume}/next-question")
    assert resp2.status_code == 200
    q2 = resp2.json()
    assert q2["sequence_number"] == 2

    # Competency must now advance to the next unassessed focus area or skill
    assert q2["competency"] != competency_q1
    assert q2["adaptation_context"]["trigger"] in ["UNASSESSED_FOCUS_AREA", "UNASSESSED_CLAIMED_SKILL"]
    # Senior baseline is advanced, score 8.5 increases difficulty to expert
    assert q2["difficulty"] == "expert"
    assert q2["adaptation_context"]["difficulty_direction"] == "increased"
    assert q2["adaptation_context"]["prior_competency_score"] == 8.5

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

    # Submit an answer with a high score (8.5)
    mock_question_ollama_client.eval_score = 8.5
    ans_resp = client.post(
        f"/api/sessions/{session_id}/answers",
        json={
            "question_id": q1["question_id"],
            "answer_text": "Detailed explanation of distributed system consensus and failure modes.",
        },
    )
    assert ans_resp.status_code == 200

    # Next question difficulty should adapt to advanced (increased)
    q2 = client.get(f"/api/sessions/{session_id}/next-question").json()
    assert q2["difficulty"] == "advanced"
    assert q2["adaptation_context"]["difficulty_direction"] == "increased"
    assert q2["adaptation_context"]["prior_competency_score"] == 8.5

    app.dependency_overrides.clear()


def test_difficulty_adjustment_decreased_on_low_score(
    client: TestClient,
    mock_question_ollama_client,
):
    """Verifies difficulty decreases to beginner when prior answer evaluation score is below 5.0."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_question_ollama_client

    resp = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Charlie",
            "candidate_email": "charlie@example.com",
            "target_role": "Backend Engineer",
            "target_level": "Mid",
            "time_limit_minutes": 45,
        },
    )
    session_id = resp.json()["sessionId"]

    q1 = client.get(f"/api/sessions/{session_id}/next-question").json()
    assert q1["difficulty"] == "intermediate"

    # Submit answer with low score (3.5)
    mock_question_ollama_client.eval_score = 3.5
    ans_resp = client.post(
        f"/api/sessions/{session_id}/answers",
        json={
            "question_id": q1["question_id"],
            "answer_text": "I do not know the details of transaction isolation.",
        },
    )
    assert ans_resp.status_code == 200

    q2 = client.get(f"/api/sessions/{session_id}/next-question").json()
    assert q2["difficulty"] == "beginner"
    assert q2["adaptation_context"]["difficulty_direction"] == "decreased"
    assert q2["adaptation_context"]["prior_competency_score"] == 3.5

    app.dependency_overrides.clear()


def test_time_awareness_question_type_adaptation():
    """Verifies that when time remaining is low (<= 300 seconds), system_tradeoff question type is selected."""
    engine = AdaptiveEngine(ollama_client=None)  # type: ignore

    # When 5 minutes or less remain (<= 300s), always pivot to system_tradeoff
    assert engine._determine_question_type(sequence_number=1, time_remaining_seconds=300) == "system_tradeoff"
    assert engine._determine_question_type(sequence_number=1, time_remaining_seconds=120) == "system_tradeoff"

    # With normal time remaining, sequence 1 is technical_concept
    assert engine._determine_question_type(sequence_number=1, time_remaining_seconds=1800) == "technical_concept"
    # Sequences 2 and 3 are deep_probe
    assert engine._determine_question_type(sequence_number=2, time_remaining_seconds=1800) == "deep_probe"
    assert engine._determine_question_type(sequence_number=3, time_remaining_seconds=1800) == "deep_probe"
    # Sequence 4+ is architecture_scenario
    assert engine._determine_question_type(sequence_number=4, time_remaining_seconds=1800) == "architecture_scenario"


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
