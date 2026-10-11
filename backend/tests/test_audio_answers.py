import io
import uuid
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.api.deps import get_ollama_client, get_transcription_service
from app.core.exceptions import (
    InvalidFileException,
    TranscriptionException,
)
from app.main import app
from app.schemas.answer import AnswerEvaluationLLM, AudioAnswerResponse
from app.schemas.question import GeneratedQuestionLLM
from app.services.transcription_service import TranscriptionService


@pytest.fixture
def mock_audio_ollama_client():
    """Deterministic Ollama client for audio tests."""
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
                    question_text="How does PostgreSQL handle multi-version concurrency control?",
                    key_evaluation_criteria=["MVCC snapshots", "Read committed isolation"],
                )
            self.eval_call_count += 1
            return AnswerEvaluationLLM(
                score=8.8,
                strengths=[
                    "Spoken answer clearly explains MVCC tuple headers (xmin/xmax).",
                    "Articulated how query-level snapshots prevent non-repeatable reads.",
                ],
                weaknesses=[],
                feedback="Excellent verbal articulation of relational database concurrency concepts.",
                improvement_suggestions=["Consider explaining VACUUM FREEZE in distributed environments."],
            )

        async def aclose(self):
            pass

    return MockClient()


@pytest.fixture
def mock_transcription_service():
    """Mock TranscriptionService returning deterministic transcript for fast unit tests."""
    class MockService(TranscriptionService):
        def __init__(self):
            super().__init__()
            self.transcribe_call_count = 0
            self.mock_transcript = (
                "PostgreSQL uses multi-version concurrency control with snapshot isolation "
                "to ensure concurrent queries do not block each other."
            )

        async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
            self.transcribe_call_count += 1
            return self.mock_transcript

    return MockService()


@pytest.fixture
def active_session_and_question(client: TestClient, mock_audio_ollama_client):
    """Sets up an active interview session and generates one question."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_audio_ollama_client

    # 1. Create session
    resp = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Alice Engineer",
            "candidate_email": "alice@example.com",
            "target_role": "Senior Database Engineer",
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


def test_submit_audio_answer_success(
    client: TestClient,
    active_session_and_question,
    mock_audio_ollama_client,
    mock_transcription_service,
):
    """Verifies successful audio answer submission, mock STT transcription, and Ollama evaluation."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_audio_ollama_client
    app.dependency_overrides[get_transcription_service] = lambda: mock_transcription_service

    # Simulated WAV payload (valid size and extension)
    audio_content = b"RIFF....WAVEfmt ...." + b"\x00" * 500
    files = {"file": ("spoken_answer.wav", audio_content, "audio/wav")}
    data = {"question_id": question_id, "time_taken_seconds": 35}

    resp = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files)
    assert resp.status_code == 200
    res_json = resp.json()

    # Validate response contract
    validated = AudioAnswerResponse.model_validate(res_json)
    assert validated.sessionId == session_id
    assert validated.question_id == question_id
    assert validated.score == 8.8
    assert validated.transcript == mock_transcription_service.mock_transcript
    assert len(validated.strengths) == 2
    assert "concurrency" in validated.feedback.lower()
    assert mock_transcription_service.transcribe_call_count == 1
    assert mock_audio_ollama_client.eval_call_count == 1

    app.dependency_overrides.clear()


def test_submit_audio_duplicate_submission_is_safe(
    client: TestClient,
    active_session_and_question,
    mock_audio_ollama_client,
    mock_transcription_service,
):
    """Verifies that re-submitting audio for the same question returns the existing answer without duplicate rows."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_audio_ollama_client
    app.dependency_overrides[get_transcription_service] = lambda: mock_transcription_service

    audio_content = b"RIFF....WAVEfmt ...." + b"\x00" * 500
    files = {"file": ("answer1.wav", audio_content, "audio/wav")}
    data = {"question_id": question_id}

    resp1 = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files)
    assert resp1.status_code == 200
    first_ans_id = resp1.json()["answer_id"]
    assert mock_audio_ollama_client.eval_call_count == 1

    # Second submission for the same question
    files2 = {"file": ("answer2.wav", audio_content, "audio/wav")}
    resp2 = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files2)
    assert resp2.status_code == 200
    assert resp2.json()["answer_id"] == first_ans_id
    # Ollama evaluation count must remain 1 (no re-evaluation or duplicate record)
    assert mock_audio_ollama_client.eval_call_count == 1

    app.dependency_overrides.clear()


def test_submit_audio_empty_file_rejected(
    client: TestClient,
    active_session_and_question,
    mock_audio_ollama_client,
    mock_transcription_service,
):
    """Verifies that 0-byte audio uploads are rejected with 400 Bad Request."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_audio_ollama_client
    app.dependency_overrides[get_transcription_service] = lambda: mock_transcription_service

    files = {"file": ("empty.wav", b"", "audio/wav")}
    data = {"question_id": question_id}

    resp = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files)
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "EMPTY_AUDIO_FILE"
    assert "empty" in body["message"].lower()

    app.dependency_overrides.clear()


def test_submit_audio_unsupported_format_rejected(
    client: TestClient,
    active_session_and_question,
    mock_audio_ollama_client,
    mock_transcription_service,
):
    """Verifies that non-audio formats (.pdf, .txt) are rejected with 415 Unsupported Media Type."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_audio_ollama_client
    app.dependency_overrides[get_transcription_service] = lambda: mock_transcription_service

    files = {"file": ("document.pdf", b"%PDF-1.4...", "application/pdf")}
    data = {"question_id": question_id}

    resp = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files)
    assert resp.status_code == 415
    body = resp.json()
    assert body["error"] == "UNSUPPORTED_MEDIA_TYPE"

    app.dependency_overrides.clear()


def test_submit_audio_corrupted_audio_data(
    client: TestClient,
    active_session_and_question,
    mock_audio_ollama_client,
):
    """Verifies that corrupt or unparseable audio raises 400 with INVALID_AUDIO."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_audio_ollama_client

    class FailingService(TranscriptionService):
        async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
            raise InvalidFileException(
                message="Uploaded file contains invalid or corrupted audio data: stream header missing",
                status_code=400,
                error_code="INVALID_AUDIO",
            )

    app.dependency_overrides[get_transcription_service] = lambda: FailingService()

    files = {"file": ("corrupt.wav", b"corrupted_stream_bytes", "audio/wav")}
    data = {"question_id": question_id}

    resp = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files)
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "INVALID_AUDIO"

    app.dependency_overrides.clear()


def test_submit_audio_no_speech_detected(
    client: TestClient,
    active_session_and_question,
    mock_audio_ollama_client,
):
    """Verifies that silent/inaudible audio raises 400 with NO_SPEECH_DETECTED."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_audio_ollama_client

    class SilentService(TranscriptionService):
        async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
            raise InvalidFileException(
                message="No intelligible speech detected in audio recording.",
                status_code=400,
                error_code="NO_SPEECH_DETECTED",
            )

    app.dependency_overrides[get_transcription_service] = lambda: SilentService()

    files = {"file": ("silence.wav", b"RIFF....WAVE" + b"\x00" * 200, "audio/wav")}
    data = {"question_id": question_id}

    resp = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files)
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "NO_SPEECH_DETECTED"

    app.dependency_overrides.clear()


def test_submit_audio_transcription_failure(
    client: TestClient,
    active_session_and_question,
    mock_audio_ollama_client,
):
    """Verifies that transcription engine failure raises 500 with TRANSCRIPTION_FAILED."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_audio_ollama_client

    class FailingModelService(TranscriptionService):
        async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
            raise TranscriptionException(
                message="Speech-to-text inference failed: CTranslate2 runtime allocation error",
            )

    app.dependency_overrides[get_transcription_service] = lambda: FailingModelService()

    files = {"file": ("sample.wav", b"RIFF....WAVE" + b"\x00" * 200, "audio/wav")}
    data = {"question_id": question_id}

    resp = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files)
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"] == "TRANSCRIPTION_FAILED"

    app.dependency_overrides.clear()


def test_submit_audio_invalid_session_id(
    client: TestClient,
    mock_transcription_service,
):
    """Verifies that non-UUID sessionId returns 400 Bad Request."""
    app.dependency_overrides[get_transcription_service] = lambda: mock_transcription_service

    files = {"file": ("test.wav", b"RIFF....WAVE" + b"\x00" * 100, "audio/wav")}
    data = {"question_id": str(uuid.uuid4())}

    resp = client.post("/api/sessions/invalid-uuid-123/answers/audio", data=data, files=files)
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_SESSION_STATE"

    app.dependency_overrides.clear()


def test_submit_audio_session_not_found(
    client: TestClient,
    mock_transcription_service,
):
    """Verifies that nonexistent sessionId returns 404 Not Found."""
    app.dependency_overrides[get_transcription_service] = lambda: mock_transcription_service

    random_session = str(uuid.uuid4())
    files = {"file": ("test.wav", b"RIFF....WAVE" + b"\x00" * 100, "audio/wav")}
    data = {"question_id": str(uuid.uuid4())}

    resp = client.post(f"/api/sessions/{random_session}/answers/audio", data=data, files=files)
    assert resp.status_code == 404
    assert resp.json()["error"] == "RESOURCE_NOT_FOUND"

    app.dependency_overrides.clear()


def test_submit_audio_invalid_question_id(
    client: TestClient,
    active_session_and_question,
    mock_transcription_service,
):
    """Verifies that non-UUID question_id returns 400 Bad Request."""
    session_id, _ = active_session_and_question
    app.dependency_overrides[get_transcription_service] = lambda: mock_transcription_service

    files = {"file": ("test.wav", b"RIFF....WAVE" + b"\x00" * 100, "audio/wav")}
    data = {"question_id": "not-a-valid-uuid"}

    resp = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files)
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_SESSION_STATE"

    app.dependency_overrides.clear()


def test_submit_audio_question_not_found(
    client: TestClient,
    active_session_and_question,
    mock_transcription_service,
):
    """Verifies that nonexistent question_id returns 404 Not Found."""
    session_id, _ = active_session_and_question
    app.dependency_overrides[get_transcription_service] = lambda: mock_transcription_service

    random_q_id = str(uuid.uuid4())
    files = {"file": ("test.wav", b"RIFF....WAVE" + b"\x00" * 100, "audio/wav")}
    data = {"question_id": random_q_id}

    resp = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files)
    assert resp.status_code == 404
    assert resp.json()["error"] == "RESOURCE_NOT_FOUND"

    app.dependency_overrides.clear()


def test_submit_audio_session_completed(
    client: TestClient,
    active_session_and_question,
    mock_audio_ollama_client,
    mock_transcription_service,
):
    """Verifies that answering audio in an already completed session returns 400 Bad Request."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_audio_ollama_client
    app.dependency_overrides[get_transcription_service] = lambda: mock_transcription_service

    # Complete the session
    comp_resp = client.post(f"/api/sessions/{session_id}/complete")
    assert comp_resp.status_code == 200

    # Attempt audio submission
    files = {"file": ("test.wav", b"RIFF....WAVE" + b"\x00" * 100, "audio/wav")}
    data = {"question_id": question_id}

    resp = client.post(f"/api/sessions/{session_id}/answers/audio", data=data, files=files)
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_SESSION_STATE"

    app.dependency_overrides.clear()


def test_existing_typed_answer_unaffected(
    client: TestClient,
    active_session_and_question,
    mock_audio_ollama_client,
):
    """Verifies that POST /api/sessions/{sessionId}/answers JSON contract remains completely functional and unchanged."""
    session_id, question_id = active_session_and_question
    app.dependency_overrides[get_ollama_client] = lambda: mock_audio_ollama_client

    payload = {
        "question_id": question_id,
        "answer_text": "PostgreSQL MVCC ensures snapshot isolation using xmin and xmax.",
        "time_taken_seconds": 25,
    }

    resp = client.post(f"/api/sessions/{session_id}/answers", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["sessionId"] == session_id
    assert res_data["question_id"] == question_id
    assert res_data["score"] == 8.8

    app.dependency_overrides.clear()
