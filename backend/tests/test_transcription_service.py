import io
import pytest
from unittest.mock import MagicMock, patch
from fastapi import UploadFile

from app.config import Settings
from app.core.exceptions import (
    FileSizeLimitExceededException,
    InvalidFileException,
    TranscriptionException,
)
from app.services.transcription_service import TranscriptionService


def test_transcription_service_lazy_loading():
    """Verifies that WhisperModel is NOT loaded on initialization (lazy loading requirement)."""
    service = TranscriptionService()
    # Model reference must be None initially
    assert service._model is None


def test_transcription_service_model_configuration():
    """Verifies that model name, device, and compute_type are taken from settings."""
    custom_settings = Settings(
        WHISPER_MODEL="tiny.en",
        WHISPER_DEVICE="cpu",
        WHISPER_COMPUTE_TYPE="int8",
    )
    service = TranscriptionService(config=custom_settings)
    assert service.settings.effective_whisper_model == "tiny.en"
    assert service.settings.WHISPER_DEVICE == "cpu"
    assert service.settings.WHISPER_COMPUTE_TYPE == "int8"


@pytest.mark.asyncio
async def test_validate_and_read_audio_empty_file():
    """Verifies rejection of empty audio files."""
    service = TranscriptionService()
    empty_file = UploadFile(
        file=io.BytesIO(b""),
        filename="test.wav",
    )

    with pytest.raises(InvalidFileException) as exc_info:
        await service.validate_and_read_audio(empty_file)

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "EMPTY_AUDIO_FILE"


@pytest.mark.asyncio
async def test_validate_and_read_audio_unsupported_extension():
    """Verifies rejection of unsupported audio extensions."""
    service = TranscriptionService()
    doc_file = UploadFile(
        file=io.BytesIO(b"content"),
        filename="recording.exe",
    )

    with pytest.raises(InvalidFileException) as exc_info:
        await service.validate_and_read_audio(doc_file)

    assert exc_info.value.status_code == 415
    assert exc_info.value.error_code == "UNSUPPORTED_MEDIA_TYPE"


@pytest.mark.asyncio
async def test_validate_and_read_audio_oversized_file():
    """Verifies rejection of oversized audio files exceeding MAX_AUDIO_SIZE_MB."""
    custom_settings = Settings(MAX_AUDIO_SIZE_MB=1)  # 1 MB limit
    service = TranscriptionService(config=custom_settings)

    oversized_content = b"x" * (2 * 1024 * 1024)  # 2 MB
    big_file = UploadFile(
        file=io.BytesIO(oversized_content),
        filename="big_recording.wav",
    )

    with pytest.raises(FileSizeLimitExceededException) as exc_info:
        await service.validate_and_read_audio(big_file)

    assert exc_info.value.status_code == 413
    assert exc_info.value.error_code == "FILE_SIZE_LIMIT_EXCEEDED"


def test_transcribe_sync_handles_model_init_failure():
    """Verifies that model initialization failure raises TranscriptionException."""
    custom_settings = Settings(WHISPER_MODEL="nonexistent_invalid_model_12345")
    service = TranscriptionService(config=custom_settings)

    with patch("faster_whisper.WhisperModel", side_effect=RuntimeError("Model download failed")):
        with pytest.raises(TranscriptionException) as exc_info:
            service._get_model()

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == "TRANSCRIPTION_FAILED"
