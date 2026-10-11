import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.main import app
from app.schemas.answer import AnswerEvaluationLLM
from app.schemas.question import GeneratedQuestionLLM
from app.schemas.resume import ClaimedSkill, ProjectSummary, ResumeAnalysisLLMOutput
from app.schemas.skill_gap import SkillGapReport


@pytest.fixture
def mock_skill_gap_ollama():
    """Mock Ollama client handling resume, question generation, and evaluation."""
    class MockClient:
        async def check_health(self):
            return {"status": "available", "base_url": "http://localhost:11434", "configured_model": "llama3.1", "model_available": True}

        async def generate_structured(self, prompt, schema, system_prompt=None, options=None):
            schema_name = getattr(schema, "__name__", str(schema))
            if "ResumeAnalysis" in schema_name:
                return ResumeAnalysisLLMOutput(
                    candidate_overview="Senior Backend Architect with 8 years in PostgreSQL and Python.",
                    claimed_skills=[
                        ClaimedSkill(name="PostgreSQL", claimed_experience_years=6.0, claimed_proficiency="Expert"),
                        ClaimedSkill(name="Kafka", claimed_experience_years=3.0, claimed_proficiency="Intermediate"),
                    ],
                    projects=[ProjectSummary(project_name="Ledger System", technologies=["PostgreSQL", "Python"])],
                    suggested_focus_areas=["MVCC", "Kafka partitioning"],
                )
            if "GeneratedQuestion" in schema_name:
                return GeneratedQuestionLLM(
                    question_text="How do PostgreSQL MVCC snapshots prevent dirty reads?",
                    key_evaluation_criteria=["Snapshot list", "MVCC tuple visibility"],
                )
            if "AnswerEvaluation" in schema_name:
                return AnswerEvaluationLLM(
                    score=8.5,
                    strengths=["Accurate description of snapshot xmin and xmax in PostgreSQL."],
                    weaknesses=[],
                    feedback="Thorough technical grasp of PostgreSQL internals.",
                    improvement_suggestions=["Review 2PC boundaries."],
                )
            return None

        async def aclose(self):
            pass

    return MockClient()


def test_job_description_ingestion_and_skill_classification(
    client: TestClient,
    sample_docx_bytes: bytes,
    mock_skill_gap_ollama,
):
    """Verifies end-to-end Resume-JD skill gap analysis with all 4 skill classifications:
    - demonstrated: PostgreSQL (answered with 8.5/10)
    - claimed_but_unvalidated: Kafka (claimed in resume, not yet asked)
    - not_assessed: Kubernetes / Docker (required in JD, neither in resume nor answered)
    """
    app.dependency_overrides[get_ollama_client] = lambda: mock_skill_gap_ollama

    # 1. Create session
    resp = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Bob Martin",
            "candidate_email": "bob@example.com",
            "target_role": "Senior Backend Architect",
            "target_level": "Senior",
            "time_limit_minutes": 45,
        },
    )
    assert resp.status_code == 201
    session_id = resp.json()["sessionId"]

    # 2. Upload resume (claims PostgreSQL and Kafka)
    files = {"file": ("resume.docx", sample_docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    resp_r = client.post(f"/api/sessions/{session_id}/resume", files=files)
    assert resp_r.status_code == 200

    # 3. Ask question and submit answer for PostgreSQL
    resp_q = client.get(f"/api/sessions/{session_id}/next-question")
    assert resp_q.status_code == 200
    q_id = resp_q.json()["question_id"]

    resp_a = client.post(
        f"/api/sessions/{session_id}/answers",
        json={
            "question_id": q_id,
            "answer_text": "PostgreSQL uses MVCC transaction snapshots with xmin and xmax tuple headers to prevent dirty reads.",
        },
    )
    assert resp_a.status_code == 200

    # 4. Submit Job Description requiring PostgreSQL, Kafka, and Kubernetes
    jd_content = (
        "We are looking for a Senior Backend Architect.\n"
        "Requirements:\n"
        "- Strong experience with PostgreSQL database optimization and transactions\n"
        "- Experience with Kafka distributed event streaming\n"
        "- Proficient in Kubernetes container orchestration\n"
        "- Deep knowledge of Distributed Systems\n"
    )

    resp_jd = client.post(
        f"/api/sessions/{session_id}/job-description",
        json={"job_description": jd_content},
    )
    assert resp_jd.status_code == 200
    gap_data = resp_jd.json()

    validated = SkillGapReport.model_validate(gap_data)
    assert validated.target_role == "Senior Backend Architect"
    assert validated.job_description_provided is True
    assert len(validated.required_skills) >= 3

    # Map classifications by skill name
    classifications = {item.skill_name.lower(): item for item in validated.required_skills}

    # Verify 'demonstrated' for PostgreSQL
    pg_item = next((item for name, item in classifications.items() if "postgres" in name), None)
    assert pg_item is not None
    assert pg_item.classification == "demonstrated"
    assert "8.5" in pg_item.evidence or "verified" in pg_item.evidence.lower()

    # Verify 'claimed_but_unvalidated' for Kafka
    kafka_item = next((item for name, item in classifications.items() if "kafka" in name), None)
    assert kafka_item is not None
    assert kafka_item.classification == "claimed_but_unvalidated"
    assert "resume" in kafka_item.evidence.lower()

    # Verify 'not_assessed' for Kubernetes
    k8s_item = next((item for name, item in classifications.items() if "kubernetes" in name), None)
    assert k8s_item is not None
    assert k8s_item.classification == "not_assessed"

    # Verify missing skills list and follow-up recommendations
    assert any("kubernetes" in s.lower() for s in validated.missing_skills)
    assert len(validated.suggested_follow_up_questions) >= 1

    # 5. Query skill gap report via GET /api/sessions/{sessionId}/skill-gap
    resp_get = client.get(f"/api/sessions/{session_id}/skill-gap")
    assert resp_get.status_code == 200
    assert resp_get.json()["job_description_provided"] is True

    app.dependency_overrides.clear()


def test_skill_gap_classification_not_demonstrated(
    client: TestClient,
    mock_skill_gap_ollama,
):
    """Verifies that an answer scoring below 7.0 classifies the skill as 'not_demonstrated'."""
    class LowScoreOllama(mock_skill_gap_ollama.__class__):
        async def generate_structured(self, prompt, schema, system_prompt=None, options=None):
            schema_name = getattr(schema, "__name__", str(schema))
            if "GeneratedQuestion" in schema_name:
                return GeneratedQuestionLLM(
                    question_text="How do PostgreSQL indexes work?",
                    key_evaluation_criteria=["B-tree index mechanics"],
                )
            if "AnswerEvaluation" in schema_name:
                return AnswerEvaluationLLM(
                    score=4.0,
                    strengths=[],
                    weaknesses=["Incorrect explanation of B-tree depth and page splits"],
                    feedback="Inadequate grasp of index leaf nodes.",
                    improvement_suggestions=["Study relational index internals."],
                )
            return None

    app.dependency_overrides[get_ollama_client] = lambda: LowScoreOllama()

    # Create session
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
    assert resp.status_code == 201
    session_id = resp.json()["sessionId"]

    # Ask question and answer with low score
    resp_q = client.get(f"/api/sessions/{session_id}/next-question")
    q_id = resp_q.json()["question_id"]

    client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": q_id, "answer_text": "Indexes are just tables with rows."},
    )

    # Ingest JD requiring PostgreSQL
    resp_jd = client.post(
        f"/api/sessions/{session_id}/job-description",
        json={"job_description": "Must have hands-on experience with PostgreSQL and SQL query optimization."},
    )
    assert resp_jd.status_code == 200
    data = resp_jd.json()

    pg_item = next((item for item in data["required_skills"] if "postgres" in item["skill_name"].lower()), None)
    assert pg_item is not None
    assert pg_item["classification"] == "not_demonstrated"
    assert "4.0" in pg_item["evidence"]

    app.dependency_overrides.clear()


def test_skill_gap_missing_jd_graceful_role_benchmark(client: TestClient):
    """Verifies that when no job description is uploaded, the service gracefully benchmarks role competencies."""
    resp = client.post(
        "/api/sessions",
        json={
            "candidate_name": "David",
            "candidate_email": "david@example.com",
            "target_role": "Senior Backend Architect",
            "target_level": "Senior",
            "time_limit_minutes": 45,
        },
    )
    session_id = resp.json()["sessionId"]

    resp_gap = client.get(f"/api/sessions/{session_id}/skill-gap")
    assert resp_gap.status_code == 200
    data = resp_gap.json()
    assert data["job_description_provided"] is False
    assert len(data["required_skills"]) >= 3
    # When no resume or questions exist yet, all role benchmark skills are not_assessed
    for skill in data["required_skills"]:
        assert skill["classification"] == "not_assessed"


def test_job_description_invalid_inputs(client: TestClient):
    """Verifies validation errors on invalid session and JD payloads."""
    # Invalid UUID
    resp1 = client.post("/api/sessions/invalid-id/job-description", json={"job_description": "Valid JD text here."})
    assert resp1.status_code == 400

    # Nonexistent session
    random_session = str(uuid.uuid4())
    resp2 = client.post(f"/api/sessions/{random_session}/job-description", json={"job_description": "Valid JD text here."})
    assert resp2.status_code == 404

    # Too short JD (< 10 chars)
    resp3 = client.post(f"/api/sessions/{random_session}/job-description", json={"job_description": "short"})
    assert resp3.status_code == 422
