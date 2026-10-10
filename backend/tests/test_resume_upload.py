import io
import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.core.exceptions import (
    AIProviderUnavailableException,
    AIStructuredGenerationException,
)
from app.main import app


@pytest.fixture
def created_session_id(client: TestClient) -> str:
    """Helper fixture to create a fresh interview session for testing."""
    payload = {
        "candidate_name": "Jane Doe",
        "candidate_email": "jane.doe@example.com",
        "target_role": "Senior Backend Architect",
        "target_level": "Senior",
        "time_limit_minutes": 45,
    }
    resp = client.post("/api/sessions", json=payload)
    assert resp.status_code == 201
    return resp.json()["sessionId"]


def test_upload_resume_success_docx(
    client: TestClient,
    created_session_id: str,
    sample_docx_bytes: bytes,
    mock_resume_ollama_client,
):
    """Verifies successful upload, text extraction, and mock Ollama analysis of DOCX resume."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_resume_ollama_client

    files = {
        "file": ("jane_doe_resume.docx", io.BytesIO(sample_docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    }
    response = client.post(f"/api/sessions/{created_session_id}/resume", files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["sessionId"] == created_session_id
    assert data["resume_parsed"] is True
    assert data["file_name"] == "jane_doe_resume.docx"
    assert len(data["file_hash"]) == 64
    assert data["file_size_bytes"] > 0
    assert len(data["claimed_skills"]) == 3
    assert len(data["projects"]) == 1
    assert len(data["suggested_focus_areas"]) == 3
    assert data["claimed_skills"][0]["name"] == "PostgreSQL"
    assert data["claimed_skills"][0]["claimed_proficiency"] == "Expert"

    app.dependency_overrides.clear()


def test_upload_resume_success_pdf(
    client: TestClient,
    created_session_id: str,
    sample_pdf_bytes: bytes,
    mock_resume_ollama_client,
):
    """Verifies successful upload, text extraction, and mock Ollama analysis of PDF resume."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_resume_ollama_client

    files = {
        "file": ("jane_doe_resume.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")
    }
    response = client.post(f"/api/sessions/{created_session_id}/resume", files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["sessionId"] == created_session_id
    assert data["resume_parsed"] is True
    assert data["file_name"] == "jane_doe_resume.pdf"
    assert len(data["claimed_skills"]) > 0

    app.dependency_overrides.clear()


def test_upload_resume_duplicate_identical_file(
    client: TestClient,
    created_session_id: str,
    sample_docx_bytes: bytes,
    mock_resume_ollama_client,
):
    """Verifies deliberate duplicate handling when the identical file is re-uploaded."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_resume_ollama_client

    files_1 = {
        "file": ("resume.docx", io.BytesIO(sample_docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    }
    resp1 = client.post(f"/api/sessions/{created_session_id}/resume", files=files_1)
    assert resp1.status_code == 200

    # Second upload with identical bytes
    files_2 = {
        "file": ("resume.docx", io.BytesIO(sample_docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    }
    resp2 = client.post(f"/api/sessions/{created_session_id}/resume", files=files_2)
    assert resp2.status_code == 200
    data2 = resp2.json()

    # Must detect identical duplicate and return without error
    assert "Identical resume already analyzed" in data2["message"]
    assert data2["file_hash"] == resp1.json()["file_hash"]

    app.dependency_overrides.clear()


def test_upload_resume_unknown_session_id(
    client: TestClient,
    sample_pdf_bytes: bytes,
    mock_resume_ollama_client,
):
    """Verifies that uploading to an unknown session UUID returns HTTP 404."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_resume_ollama_client

    fake_uuid = str(uuid.uuid4())
    files = {"file": ("resume.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    response = client.post(f"/api/sessions/{fake_uuid}/resume", files=files)
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "RESOURCE_NOT_FOUND"

    app.dependency_overrides.clear()


def test_upload_resume_invalid_session_uuid_format(client: TestClient, sample_pdf_bytes: bytes):
    """Verifies that non-UUID session strings return HTTP 400."""
    files = {"file": ("resume.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    response = client.post("/api/sessions/not-a-valid-uuid/resume", files=files)
    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_SESSION_STATE"


def test_upload_resume_unsupported_file_extension(client: TestClient, created_session_id: str):
    """Verifies that unsupported file formats (.txt, .exe) return HTTP 415."""
    files = {"file": ("resume.txt", io.BytesIO(b"Plain text resume content"), "text/plain")}
    response = client.post(f"/api/sessions/{created_session_id}/resume", files=files)
    assert response.status_code == 415
    assert response.json()["error"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_resume_empty_file(client: TestClient, created_session_id: str):
    """Verifies that 0-byte uploads return HTTP 400."""
    files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    response = client.post(f"/api/sessions/{created_session_id}/resume", files=files)
    assert response.status_code == 400
    assert response.json()["error"] == "EMPTY_FILE"


def test_upload_resume_file_size_exceeded(client: TestClient, created_session_id: str):
    """Verifies that files exceeding 10MB limit return HTTP 413."""
    # 10.5 MB payload
    oversized_bytes = b"0" * (11 * 1024 * 1024)
    files = {"file": ("oversized.pdf", io.BytesIO(oversized_bytes), "application/pdf")}
    response = client.post(f"/api/sessions/{created_session_id}/resume", files=files)
    assert response.status_code == 413
    assert response.json()["error"] == "FILE_SIZE_LIMIT_EXCEEDED"


def test_upload_resume_corrupt_pdf(client: TestClient, created_session_id: str):
    """Verifies that corrupted unreadable PDF files return HTTP 422."""
    corrupt_bytes = b"%PDF-1.4 completely invalid garbage binary data that cannot be parsed"
    files = {"file": ("corrupt.pdf", io.BytesIO(corrupt_bytes), "application/pdf")}
    response = client.post(f"/api/sessions/{created_session_id}/resume", files=files)
    assert response.status_code == 422
    assert response.json()["error"] == "DOCUMENT_PARSE_ERROR"


def test_upload_resume_ollama_unavailable(
    client: TestClient,
    created_session_id: str,
    sample_pdf_bytes: bytes,
    mock_ollama_unavailable,
):
    """Verifies that when Ollama is offline, POST /resume returns HTTP 503 instead of fake data."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama_unavailable

    files = {"file": ("resume.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    response = client.post(f"/api/sessions/{created_session_id}/resume", files=files)
    assert response.status_code == 503
    data = response.json()
    assert data["error"] == "AI_PROVIDER_UNAVAILABLE"

    app.dependency_overrides.clear()


def test_upload_resume_ollama_malformed_output(
    client: TestClient,
    created_session_id: str,
    sample_pdf_bytes: bytes,
):
    """Verifies that when Ollama emits malformed JSON, POST /resume returns HTTP 502."""
    class MockMalformedClient:
        async def check_health(self):
            return {"status": "available", "base_url": "http://localhost:11434", "configured_model": "llama3.1", "model_available": True}

        async def generate_structured(self, *args, **kwargs):
            raise AIStructuredGenerationException("Ollama generated malformed JSON.")

        async def aclose(self):
            pass

    app.dependency_overrides[get_ollama_client] = lambda: MockMalformedClient()

    files = {"file": ("resume.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    response = client.post(f"/api/sessions/{created_session_id}/resume", files=files)
    assert response.status_code == 502
    assert response.json()["error"] == "AI_STRUCTURED_GENERATION_FAILED"

    app.dependency_overrides.clear()
