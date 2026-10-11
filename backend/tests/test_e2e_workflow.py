import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.main import app
from app.schemas.answer import AnswerEvaluationLLM, AnswerResponse
from app.schemas.event import EventResponse
from app.schemas.question import GeneratedQuestionLLM, QuestionResponse
from app.schemas.report import InterviewReportResponse, SessionCompleteResponse
from app.schemas.resume import (
    ClaimedSkill,
    ProjectSummary,
    ResumeAnalysisLLMOutput,
    ResumeUploadResponse,
)
from app.schemas.session import SessionResponse


@pytest.fixture
def mock_e2e_ollama():
    """Deterministic mocked Ollama client for complete E2E workflow."""
    class MockE2EClient:
        def __init__(self):
            self.question_count = 0
            self.eval_count = 0

        async def check_health(self):
            return {
                "status": "available",
                "base_url": "http://localhost:11434",
                "configured_model": "llama3.1",
                "model_available": True,
            }

        async def generate_structured(self, prompt, schema, system_prompt=None, options=None):
            if schema == ResumeAnalysisLLMOutput:
                return ResumeAnalysisLLMOutput(
                    candidate_overview="Lead Backend Architect with 8+ years designing high-throughput distributed microservices.",
                    claimed_skills=[
                        ClaimedSkill(
                            name="PostgreSQL",
                            claimed_experience_years=7.0,
                            claimed_proficiency="Expert",
                            context_snippet="Optimized PostgreSQL MVCC queries and connection pooling across high-volume cluster.",
                        ),
                        ClaimedSkill(
                            name="Distributed Systems",
                            claimed_experience_years=5.0,
                            claimed_proficiency="Advanced",
                            context_snippet="Architected event-driven microservices handling 25k requests/sec.",
                        ),
                    ],
                    projects=[
                        ProjectSummary(
                            project_name="High-Throughput Ledger",
                            technologies=["PostgreSQL", "Kafka", "Python"],
                            highlights=["Zero inconsistency ledger with SSI isolation"],
                        )
                    ],
                    suggested_focus_areas=[
                        "PostgreSQL MVCC SSI vs Read Committed isolation tradeoffs",
                        "Distributed consensus algorithms and split-brain recovery",
                    ],
                )

            if schema == GeneratedQuestionLLM:
                self.question_count += 1
                if self.question_count == 1:
                    return GeneratedQuestionLLM(
                        question_text="How does PostgreSQL MVCC handle serialization anomalies in concurrent read-write workloads?",
                        key_evaluation_criteria=["SIREAD lock table", "SSI serialization failure retry loop"],
                    )
                else:
                    return GeneratedQuestionLLM(
                        question_text="Explain Raft log compaction and leader election during network partitions.",
                        key_evaluation_criteria=["Term numbers", "Heartbeat timeouts", "Snapshot installation"],
                    )

            if schema == AnswerEvaluationLLM:
                self.eval_count += 1
                if self.eval_count == 1:
                    return AnswerEvaluationLLM(
                        score=8.5,
                        strengths=["Accurate description of SIREAD lock predicate locks", "Clear explanation of retry loop"],
                        weaknesses=["Did not mention pg_locks inspection"],
                        feedback="Solid mastery of PostgreSQL serializable snapshot isolation.",
                        improvement_suggestions=["Review DEFERRABLE transaction semantics"],
                    )
                else:
                    return AnswerEvaluationLLM(
                        score=9.0,
                        strengths=["Thorough analysis of Raft majority quorum", "Correct leader step-down explanation"],
                        weaknesses=[],
                        feedback="Outstanding distributed systems reasoning.",
                        improvement_suggestions=[],
                    )

            raise ValueError(f"Unexpected schema in mock: {schema}")

        async def aclose(self):
            pass

    return MockE2EClient()


def test_complete_interview_lifecycle_e2e(
    client: TestClient,
    sample_docx_bytes: bytes,
    mock_e2e_ollama,
):
    """Validates the entire end-to-end workflow from session creation to report retrieval."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_e2e_ollama

    # -------------------------------------------------------------
    # Step 1: Health Probe (GET /api/health)
    # -------------------------------------------------------------
    resp_health = client.get("/api/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] in ["healthy", "degraded"]

    # -------------------------------------------------------------
    # Step 2: Session Initialization (POST /api/sessions)
    # -------------------------------------------------------------
    resp_session = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Alexander Hamilton",
            "candidate_email": "alexander@example.com",
            "target_role": "Lead Backend Architect",
            "target_level": "Lead",
            "time_limit_minutes": 45,
        },
    )
    assert resp_session.status_code == 201
    session_data = SessionResponse.model_validate(resp_session.json())
    session_id = session_data.sessionId
    assert session_data.candidate_name == "Alexander Hamilton"
    assert session_data.status == "created"
    assert session_data.resume_uploaded is False

    # -------------------------------------------------------------
    # Step 3: Resume Upload & Analysis (POST /api/sessions/{id}/resume)
    # -------------------------------------------------------------
    files = {"file": ("resume.docx", sample_docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    resp_resume = client.post(f"/api/sessions/{session_id}/resume", files=files)
    assert resp_resume.status_code == 200
    resume_data = ResumeUploadResponse.model_validate(resp_resume.json())
    assert resume_data.sessionId == session_id
    assert resume_data.resume_parsed is True
    assert len(resume_data.claimed_skills) >= 2
    assert len(resume_data.suggested_focus_areas) >= 2

    # -------------------------------------------------------------
    # Step 4: First Question Generation (GET /api/sessions/{id}/next-question)
    # -------------------------------------------------------------
    resp_q1 = client.get(f"/api/sessions/{session_id}/next-question")
    assert resp_q1.status_code == 200
    q1 = QuestionResponse.model_validate(resp_q1.json())
    assert q1.sequence_number == 1
    assert q1.adaptation_context is not None
    assert q1.adaptation_context.trigger in ["UNASSESSED_FOCUS_AREA", "UNASSESSED_CLAIMED_SKILL", "CORE_ROLE_COMPETENCY"]
    q1_id = q1.question_id

    # -------------------------------------------------------------
    # Step 5: First Answer Submission (POST /api/sessions/{id}/answers)
    # -------------------------------------------------------------
    resp_ans1 = client.post(
        f"/api/sessions/{session_id}/answers",
        json={
            "question_id": q1_id,
            "answer_text": "PostgreSQL implements SSI via SIREAD locks to detect rw-antidependency cycles and abort one transaction.",
        },
    )
    assert resp_ans1.status_code == 200
    ans1 = AnswerResponse.model_validate(resp_ans1.json())
    assert ans1.question_id == q1_id
    assert ans1.score == 8.5
    assert len(ans1.strengths) > 0

    # -------------------------------------------------------------
    # Step 6: Telemetry Event Stream (POST /api/sessions/{id}/events)
    # -------------------------------------------------------------
    resp_evt = client.post(
        f"/api/sessions/{session_id}/events",
        json={"event_type": "TAB_SWITCH", "event_data": {"blur_ms": 1500}},
    )
    assert resp_evt.status_code == 200
    evt = EventResponse.model_validate(resp_evt.json())
    assert evt.progress.questions_asked == 1
    assert evt.progress.answers_submitted == 1
    assert evt.progress.current_status == "in_progress"

    # -------------------------------------------------------------
    # Step 7: Second Question Generation (GET /api/sessions/{id}/next-question)
    # -------------------------------------------------------------
    resp_q2 = client.get(f"/api/sessions/{session_id}/next-question")
    assert resp_q2.status_code == 200
    q2 = QuestionResponse.model_validate(resp_q2.json())
    assert q2.sequence_number == 2
    # Verify score adaptation from prior answer
    assert q2.adaptation_context.prior_competency_score == 8.5
    assert q2.adaptation_context.difficulty_direction in ["increased", "baseline"]
    q2_id = q2.question_id

    # -------------------------------------------------------------
    # Step 8: Second Answer Submission (POST /api/sessions/{id}/answers)
    # -------------------------------------------------------------
    resp_ans2 = client.post(
        f"/api/sessions/{session_id}/answers",
        json={
            "question_id": q2_id,
            "answer_text": "In Raft, if a leader is partitioned with a minority of nodes, it cannot commit log entries.",
        },
    )
    assert resp_ans2.status_code == 200
    ans2 = AnswerResponse.model_validate(resp_ans2.json())
    assert ans2.score == 9.0

    # -------------------------------------------------------------
    # Step 9: Interview Completion (POST /api/sessions/{id}/complete)
    # -------------------------------------------------------------
    resp_complete = client.post(f"/api/sessions/{session_id}/complete")
    assert resp_complete.status_code == 200
    complete_data = SessionCompleteResponse.model_validate(resp_complete.json())
    assert complete_data.status == "completed"
    assert complete_data.total_questions == 2
    assert complete_data.total_answers == 2
    assert complete_data.average_score == 8.75

    # Verify idempotency of complete
    resp_complete_again = client.post(f"/api/sessions/{session_id}/complete")
    assert resp_complete_again.status_code == 200
    assert resp_complete_again.json()["status"] == "completed"

    # -------------------------------------------------------------
    # Step 10: Final Decision Report (GET /api/sessions/{id}/report)
    # -------------------------------------------------------------
    resp_report = client.get(f"/api/sessions/{session_id}/report")
    assert resp_report.status_code == 200
    report = InterviewReportResponse.model_validate(resp_report.json())
    assert report.sessionId == session_id
    assert report.candidate_name == "Alexander Hamilton"
    assert report.status == "completed"
    assert report.completed_at is not None
    assert len(report.questions) == 2
    assert report.questions[0].answer is not None
    assert report.questions[1].answer is not None
    assert len(report.competencies) >= 1
    assert report.summary.total_questions == 2
    assert report.summary.total_answers == 2
    assert report.summary.completion_rate == 100.0
    assert report.summary.overall_average_score == 8.75
    assert report.summary.integrity.tab_switches == 1
    assert report.summary.integrity.suspicious_activity_flag is False

    # -------------------------------------------------------------
    # Step 11: Guard Enforcement (No more actions after completion)
    # -------------------------------------------------------------
    resp_post_q = client.get(f"/api/sessions/{session_id}/next-question")
    assert resp_post_q.status_code == 400
    assert resp_post_q.json()["error"] == "INVALID_SESSION_STATE"

    resp_post_ans = client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": q1_id, "answer_text": "Late answer"},
    )
    assert resp_post_ans.status_code == 400
    assert resp_post_ans.json()["error"] == "INVALID_SESSION_STATE"

    app.dependency_overrides.clear()
