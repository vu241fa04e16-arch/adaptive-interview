import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.main import app
from app.schemas.answer import AnswerEvaluationLLM
from app.schemas.question import GeneratedQuestionLLM
from app.schemas.report import InterviewReportResponse


@pytest.fixture
def mock_report_ollama(mock_resume_ollama_client):
    """Mock Ollama handling resume parsing, question generation, and evaluation."""
    class MockClient:
        async def check_health(self):
            return {"status": "available", "base_url": "http://localhost:11434", "configured_model": "llama3.1", "model_available": True}

        async def generate_structured(self, prompt, schema, system_prompt=None, options=None):
            if "ResumeAnalysisLLMOutput" in str(schema):
                return await mock_resume_ollama_client.generate_structured(prompt, schema)
            if schema == GeneratedQuestionLLM:
                return GeneratedQuestionLLM(
                    question_text="How do PostgreSQL MVCC snapshots prevent dirty reads?",
                    key_evaluation_criteria=["Read Committed isolation", "Active transaction XID list"],
                )
            return AnswerEvaluationLLM(
                score=8.5,
                strengths=["Accurate description of snapshot xmin and xmax"],
                weaknesses=["Did not mention subtransactions"],
                feedback="Very thorough response demonstrating solid understanding",
                improvement_suggestions=["Review 2PC transaction boundaries"],
            )

        async def aclose(self):
            pass

    return MockClient()


def test_get_report_empty_session_handles_gracefully(client: TestClient):
    """Verifies that an empty session without questions or answers generates a valid deterministic report."""
    resp_s = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Dave Bowman",
            "candidate_email": "dave@example.com",
            "target_role": "Backend Engineer",
            "target_level": "Mid",
            "time_limit_minutes": 30,
        },
    )
    assert resp_s.status_code == 201
    session_id = resp_s.json()["sessionId"]

    resp = client.get(f"/api/sessions/{session_id}/report")
    assert resp.status_code == 200
    data = resp.json()

    validated = InterviewReportResponse.model_validate(data)
    assert validated.sessionId == session_id
    assert validated.candidate_name == "Dave Bowman"
    assert validated.summary.total_questions == 0
    assert validated.summary.total_answers == 0
    assert validated.summary.overall_average_score is None
    assert validated.summary.completion_rate == 0.0
    assert len(validated.questions) == 0
    assert len(validated.competencies) == 0


def test_get_report_full_interview_lifecycle(
    client: TestClient,
    sample_docx_bytes: bytes,
    mock_report_ollama,
):
    """Verifies end-to-end report generation with resume, questions, answers, events, and completion."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_report_ollama

    # 1. Create session
    resp_s = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Jane Doe",
            "candidate_email": "jane@example.com",
            "target_role": "Senior Backend Architect",
            "target_level": "Senior",
            "time_limit_minutes": 45,
        },
    )
    assert resp_s.status_code == 201
    session_id = resp_s.json()["sessionId"]

    # 2. Upload resume
    files = {"file": ("resume.docx", sample_docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    resp_r = client.post(f"/api/sessions/{session_id}/resume", files=files)
    assert resp_r.status_code == 200

    # 3. Generate first question
    resp_q1 = client.get(f"/api/sessions/{session_id}/next-question")
    assert resp_q1.status_code == 200
    q1_id = resp_q1.json()["question_id"]

    # 4. Submit answer
    resp_a1 = client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": q1_id, "answer_text": "PostgreSQL MVCC uses tuple visibility rules based on transaction snapshots."},
    )
    assert resp_a1.status_code == 200

    # 5. Record telemetry events
    resp_e1 = client.post(
        f"/api/sessions/{session_id}/events",
        json={"event_type": "TAB_SWITCH", "event_data": {"duration": 2}},
    )
    assert resp_e1.status_code == 200

    # 6. Complete interview
    resp_c = client.post(f"/api/sessions/{session_id}/complete")
    assert resp_c.status_code == 200

    # 7. Retrieve final report
    resp_rep = client.get(f"/api/sessions/{session_id}/report")
    assert resp_rep.status_code == 200
    report_data = resp_rep.json()

    validated = InterviewReportResponse.model_validate(report_data)
    assert validated.sessionId == session_id
    assert validated.candidate_name == "Jane Doe"
    assert validated.target_role == "Senior Backend Architect"
    assert validated.status == "completed"
    assert validated.candidate_overview is not None

    # Verify questions and answers
    assert len(validated.questions) == 1
    q_entry = validated.questions[0]
    assert q_entry.question_id == q1_id
    assert q_entry.answer is not None
    assert q_entry.answer.score == 8.5
    assert len(q_entry.answer.strengths) > 0

    # Verify competency aggregation
    assert len(validated.competencies) >= 1
    comp = validated.competencies[0]
    assert comp.average_score == 8.5
    assert comp.demonstrated_proficiency in ["Expert", "Advanced"]
    assert comp.answers_count == 1

    # Verify summary metrics
    assert validated.summary.total_questions == 1
    assert validated.summary.total_answers == 1
    assert validated.summary.completion_rate == 100.0
    assert validated.summary.overall_average_score == 8.5
    assert validated.summary.integrity.total_events >= 1
    assert validated.summary.integrity.tab_switches >= 1
    assert validated.summary.integrity.suspicious_activity_flag is False

    # Verify Decision Intelligence & Skill Gap additions
    assert validated.skill_gap_analysis is not None
    assert validated.overall_assessment is not None
    assert validated.decision_recommendation is not None
    assert len(validated.summary.integrity.timeline) >= 1
    assert validated.summary.integrity.risk_level in ["low", "medium", "high"]
    assert len(validated.suggested_follow_up_questions) >= 1

    app.dependency_overrides.clear()


def test_get_report_invalid_uuid_returns_400(client: TestClient):
    """Verifies malformed sessionId returns HTTP 400."""
    resp = client.get("/api/sessions/invalid-id/report")
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_SESSION_STATE"


def test_get_report_unknown_session_returns_404(client: TestClient):
    """Verifies unknown sessionId returns HTTP 404."""
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/sessions/{fake_id}/report")
    assert resp.status_code == 404
    assert resp.json()["error"] == "RESOURCE_NOT_FOUND"
