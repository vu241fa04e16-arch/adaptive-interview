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


# ==============================================================================
# Claimed-Skill Verification Tests
# ==============================================================================

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from app.models.question import Question
from app.models.session import InterviewSession
from app.schemas.answer import AnswerSubmitRequest
from app.services.evaluation_service import EvaluationService


def make_mock_db() -> AsyncMock:
    """Creates an AsyncMock database session where execute() returns a synchronous MagicMock Result."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute.return_value = mock_result
    db.add = MagicMock()

    async def mock_refresh(target):
        if hasattr(target, "created_at") and getattr(target, "created_at", None) is None:
            target.created_at = datetime.now(timezone.utc)
        if hasattr(target, "id") and getattr(target, "id", None) is None:
            target.id = uuid.uuid4()

    db.refresh.side_effect = mock_refresh
    return db


def make_sample_session(claimed_skills=None) -> InterviewSession:
    """Helper creating an in-memory InterviewSession with claimed skills."""
    if claimed_skills is None:
        claimed_skills = [
            {
                "name": "PostgreSQL",
                "claimed_years": 6.0,
                "claimed_proficiency": "Expert",
                "verified": False,
                "demonstrated_score": None,
                "evaluation_notes": [],
            },
            {
                "name": "Apache Kafka",
                "claimed_years": 3.0,
                "claimed_proficiency": "Intermediate",
                "verified": False,
                "demonstrated_score": None,
                "evaluation_notes": [],
            },
            {
                "name": "Distributed Systems",
                "claimed_years": 5.0,
                "claimed_proficiency": "Advanced",
                "verified": False,
                "demonstrated_score": None,
                "evaluation_notes": [],
            },
        ]
    return InterviewSession(
        id=uuid.uuid4(),
        candidate_name="Jane Doe",
        candidate_email="jane@example.com",
        target_role="Senior Backend Architect",
        target_level="Senior",
        time_limit_minutes=45,
        status="in_progress",
        competency_state={"claimed_skills": claimed_skills},
    )


def make_sample_question(
    session_id: uuid.UUID,
    competency: str = "PostgreSQL MVCC SSI versus Read Committed isolation tradeoffs",
    question_text: str = "How do PostgreSQL MVCC snapshots prevent dirty reads?",
    criteria: list[str] = None,
) -> Question:
    """Helper creating an in-memory Question."""
    return Question(
        id=uuid.uuid4(),
        session_id=session_id,
        sequence_number=1,
        question_text=question_text,
        competency=competency,
        difficulty="advanced",
        question_type="technical_concept",
        key_evaluation_criteria=criteria or ["Read Committed isolation", "Active transaction XID snapshot list"],
    )


@pytest.mark.asyncio
async def test_claimed_skill_verification_relevant_high_scoring_answer():
    """Verifies that a relevant, high-scoring answer (>= 7.0) marks the claimed skill as verified."""
    session = make_sample_session()
    question = make_sample_question(session.id)
    answer_payload = AnswerSubmitRequest(
        question_id=str(question.id),
        answer_text=(
            "In PostgreSQL, Read Committed transactions take a new snapshot at the beginning of each query. "
            "The snapshot contains xmin, xmax, and a list of active transaction IDs. Tuples created after xmax "
            "or active in xip_list are ignored, thus dirty reads cannot occur."
        ),
    )

    mock_ollama = AsyncMock()
    mock_ollama.generate_structured.return_value = AnswerEvaluationLLM(
        score=8.5,
        strengths=["Accurate explanation of PostgreSQL MVCC snapshot isolation and xmin/xmax."],
        weaknesses=[],
        feedback="Solid architectural understanding of PostgreSQL transaction mechanics.",
        improvement_suggestions=[],
    )

    db = make_mock_db()

    service = EvaluationService(ollama_client=mock_ollama)
    resp = await service.evaluate_and_save_answer(session, question, answer_payload, db)

    assert resp.score == 8.5
    claimed = session.competency_state["claimed_skills"]
    by_name = {s["name"].lower(): s for s in claimed}

    # PostgreSQL must be verified with score 8.5
    assert by_name["postgresql"]["verified"] is True
    assert by_name["postgresql"]["demonstrated_score"] == 8.5
    assert any("Score 8.5/10" in n for n in by_name["postgresql"]["evaluation_notes"])

    # Unrelated skills must remain unverified and untouched
    assert by_name["apache kafka"]["verified"] is False
    assert by_name["apache kafka"]["demonstrated_score"] is None
    assert len(by_name["apache kafka"]["evaluation_notes"]) == 0

    assert by_name["distributed systems"]["verified"] is False
    assert by_name["distributed systems"]["demonstrated_score"] is None


@pytest.mark.asyncio
async def test_claimed_skill_verification_unrelated_answers():
    """Verifies that unrelated answers (off-topic or about different domains) do not verify skills."""
    service = EvaluationService(ollama_client=AsyncMock())
    db = make_mock_db()

    # Sub-case A: Off-topic answer to a PostgreSQL question
    session_a = make_sample_session()
    question_a = make_sample_question(session_a.id)
    answer_a = AnswerSubmitRequest(
        question_id=str(question_a.id),
        answer_text="I enjoy baking sourdough bread with high hydration dough and olive oil on weekends.",
    )

    service.ollama.generate_structured.return_value = AnswerEvaluationLLM(
        score=1.0,
        strengths=[],
        weaknesses=["Answer is completely off-topic and discusses baking instead of PostgreSQL."],
        feedback="No relevant evidence or technical answer provided.",
        improvement_suggestions=[],
    )

    await service.evaluate_and_save_answer(session_a, question_a, answer_a, db)

    claimed_a = session_a.competency_state["claimed_skills"]
    by_name_a = {s["name"].lower(): s for s in claimed_a}
    assert by_name_a["postgresql"]["verified"] is False
    assert by_name_a["postgresql"]["demonstrated_score"] is None
    assert by_name_a["apache kafka"]["verified"] is False

    # Sub-case B: High-scoring answer on an unrelated competency (Paxos for Distributed Systems)
    session_b = make_sample_session()
    question_b = make_sample_question(
        session_b.id,
        competency="Distributed Systems & Scalability",
        question_text="Explain Raft log replication and leader election quorums.",
        criteria=["Majority quorum", "Term numbers", "Heartbeat timeouts"],
    )
    answer_b = AnswerSubmitRequest(
        question_id=str(question_b.id),
        answer_text="In Raft distributed systems, consensus requires a majority quorum of node votes...",
    )

    service.ollama.generate_structured.return_value = AnswerEvaluationLLM(
        score=9.0,
        strengths=["Excellent grasp of distributed consensus algorithms and quorum mechanics."],
        weaknesses=[],
        feedback="Superb distributed systems answer.",
        improvement_suggestions=[],
    )

    await service.evaluate_and_save_answer(session_b, question_b, answer_b, db)

    claimed_b = session_b.competency_state["claimed_skills"]
    by_name_b = {s["name"].lower(): s for s in claimed_b}
    # Distributed Systems is verified because answer is relevant to it
    assert by_name_b["distributed systems"]["verified"] is True
    assert by_name_b["distributed systems"]["demonstrated_score"] == 9.0
    # PostgreSQL is UNRELATED to Raft question/answer, so it must remain unverified!
    assert by_name_b["postgresql"]["verified"] is False
    assert by_name_b["postgresql"]["demonstrated_score"] is None
    # Apache Kafka is UNRELATED, must remain unverified!
    assert by_name_b["apache kafka"]["verified"] is False


@pytest.mark.asyncio
async def test_claimed_skill_verification_relevant_low_scoring_answer():
    """Verifies that a relevant answer on topic that scores below threshold (< 7.0) is not verified."""
    session = make_sample_session()
    question = make_sample_question(session.id)
    answer_payload = AnswerSubmitRequest(
        question_id=str(question.id),
        answer_text=(
            "PostgreSQL locks every table when reading data so dirty reads are prevented. "
            "I do not know how MVCC or xmin works."
        ),
    )

    mock_ollama = AsyncMock()
    mock_ollama.generate_structured.return_value = AnswerEvaluationLLM(
        score=3.5,
        strengths=["Mentioned PostgreSQL table locking concept."],
        weaknesses=["Incorrect claim that reading rows locks tables in PostgreSQL.", "Lacks understanding of MVCC."],
        feedback="Candidate demonstrates fundamental misunderstanding of PostgreSQL MVCC.",
        improvement_suggestions=["Review MVCC snapshot mechanics."],
    )

    db = make_mock_db()

    service = EvaluationService(ollama_client=mock_ollama)
    resp = await service.evaluate_and_save_answer(session, question, answer_payload, db)

    assert resp.score == 3.5
    claimed = session.competency_state["claimed_skills"]
    by_name = {s["name"].lower(): s for s in claimed}

    # PostgreSQL was attempted, but score 3.5 is below the 7.0 threshold, so verified is False!
    assert by_name["postgresql"]["verified"] is False
    assert by_name["postgresql"]["demonstrated_score"] == 3.5
    assert any("threshold" in n.lower() or "attempted" in n.lower() for n in by_name["postgresql"]["evaluation_notes"])

    # Kafka and Distributed Systems remain unverified
    assert by_name["apache kafka"]["verified"] is False
    assert by_name["distributed systems"]["verified"] is False


def test_no_partial_substring_matching_alone():
    """Verifies that skill matching enforces word boundaries and does not match partial substrings alone."""
    # 1. Exact and word boundary matching should succeed
    assert EvaluationService._matches_skill_name("Go", "Implemented backend microservices in Go.")
    assert EvaluationService._matches_skill_name("C", "Wrote low-level drivers in C.")
    assert EvaluationService._matches_skill_name("SQL", "Optimized complex SQL queries.")
    assert EvaluationService._matches_skill_name("Java", "Engineered Java Spring Boot microservices.")
    assert EvaluationService._matches_skill_name("PostgreSQL", "Configured PostgreSQL MVCC transaction isolation.")
    assert EvaluationService._matches_skill_name("PostgreSQL", "Tuned Postgres connection pools.")
    assert EvaluationService._matches_skill_name("Apache Kafka", "Managed Kafka consumer lag.")

    # 2. Substrings inside other words must NEVER match
    assert not EvaluationService._matches_skill_name("Go", "Sorting algorithm efficiency and category.")
    assert not EvaluationService._matches_skill_name("C", "Cloud computing concurrency model.")
    assert not EvaluationService._matches_skill_name("SQL", "Document-oriented NoSQL storage.")
    assert not EvaluationService._matches_skill_name("Java", "Client-side JavaScript React application.")
    assert not EvaluationService._matches_skill_name("Kafka", "Kafkaesque bureaucracy in software teams.")

