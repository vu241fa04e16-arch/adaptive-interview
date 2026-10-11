import asyncio
import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile

from app.config import Settings, get_settings
from app.core.exceptions import (
    AppException,
    FileSizeLimitExceededException,
    InvalidFileException,
    TranscriptionException,
)
from app.core.logging import logger

settings = get_settings()

# Compatibility hook for faster-whisper with newer PyAV versions
try:
    import av
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        try:
            return _orig_av_open(*args, **kwargs)
        except TypeError as e:
            if "metadata_errors" in str(e):
                kwargs.pop("metadata_errors", None)
                return _orig_av_open(*args, **kwargs)
            raise

    av.open = _safe_av_open
except ImportError:
    pass


class TranscriptionService:
    """Production Speech-to-Text service utilizing faster-whisper with lazy model loading."""

    def __init__(self, config: Optional[Settings] = None):
        self.settings = config or get_settings()
        self._model = None
        self._model_lock = asyncio.Lock()

    def _get_model(self):
        """Lazily load faster-whisper model on first actual transcription request."""
        if self._model is None:
            model_name = self.settings.effective_whisper_model
            device = self.settings.WHISPER_DEVICE
            compute_type = self.settings.WHISPER_COMPUTE_TYPE
            logger.info(
                f"Loading faster-whisper model '{model_name}' (device={device}, compute_type={compute_type})..."
            )
            try:
                from faster_whisper import WhisperModel

                self._model = WhisperModel(
                    model_size_or_path=model_name,
                    device=device,
                    compute_type=compute_type,
                )
                logger.info(f"faster-whisper model '{model_name}' loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load faster-whisper model '{model_name}': {e}")
                raise TranscriptionException(
                    message=f"Failed to initialize transcription model '{model_name}': {str(e)}",
                    details={"model": model_name, "error": str(e)},
                )
        return self._model

    async def validate_and_read_audio(self, file: UploadFile) -> Tuple[bytes, str]:
        """Validates file extension, non-empty content, and max size.

        Returns:
            Tuple of (raw_bytes, sanitized_filename)
        """
        filename = file.filename or "recording.wav"
        clean_filename = os.path.basename(filename)
        clean_filename = re.sub(r"[^\w\.-]", "_", clean_filename)

        ext = Path(clean_filename).suffix.lower()
        if not ext or ext not in self.settings.ALLOWED_AUDIO_EXTENSIONS:
            raise InvalidFileException(
                message=(
                    f"Unsupported audio format '{ext}'. "
                    f"Allowed formats: {', '.join(self.settings.ALLOWED_AUDIO_EXTENSIONS)}"
                ),
                status_code=415,
                error_code="UNSUPPORTED_MEDIA_TYPE",
                details={
                    "allowed_extensions": self.settings.ALLOWED_AUDIO_EXTENSIONS,
                    "received_filename": clean_filename,
                },
            )

        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            raise InvalidFileException(
                message="Uploaded audio file is empty (0 bytes).",
                status_code=400,
                error_code="EMPTY_AUDIO_FILE",
            )

        max_size_bytes = self.settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
        if file_size > max_size_bytes:
            raise FileSizeLimitExceededException(
                max_size_mb=self.settings.MAX_AUDIO_SIZE_MB,
                actual_size_bytes=file_size,
            )

        return content, clean_filename

    def _transcribe_sync(self, audio_bytes: bytes, filename: str) -> str:
        """Synchronous audio decoding and Whisper inference executed in threadpool."""
        model = self._get_model()
        ext = Path(filename).suffix.lower() or ".wav"

        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
                tf.write(audio_bytes)
                temp_file = tf.name

            try:
                segments, info = model.transcribe(temp_file, beam_size=5)
                # Consume generator to decode audio frames and verify complete inference
                transcript_parts = [segment.text.strip() for segment in segments]
            except Exception as decode_err:
                err_msg = str(decode_err)
                logger.warning(f"Audio decoding error for {filename}: {err_msg}")
                # Check for PyAV / corrupt audio decoding errors
                is_decode_error = any(
                    token in err_msg.lower()
                    for token in [
                        "invalid data",
                        "corrupt",
                        "decode",
                        "demuxing",
                        "stream",
                        "header",
                        "errno 1094995529",
                    ]
                )
                if is_decode_error or type(decode_err).__name__ in [
                    "InvalidDataError",
                    "FFmpegError",
                    "AVError",
                ]:
                    raise InvalidFileException(
                        message=f"Uploaded file contains invalid or corrupted audio data: {err_msg}",
                        status_code=400,
                        error_code="INVALID_AUDIO",
                        details={"filename": filename, "error": err_msg},
                    )
                raise TranscriptionException(
                    message=f"Speech-to-text inference failed: {err_msg}",
                    details={"filename": filename, "error": err_msg},
                )

            full_transcript = " ".join(part for part in transcript_parts if part).strip()

            if not full_transcript:
                raise InvalidFileException(
                    message="No intelligible speech detected in audio recording. Please provide a clear verbal response.",
                    status_code=400,
                    error_code="NO_SPEECH_DETECTED",
                    details={"filename": filename},
                )

            return full_transcript

        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
        """Asynchronously transcribes audio bytes without blocking the main event loop."""
        return await asyncio.to_thread(self._transcribe_sync, audio_bytes, filename)
