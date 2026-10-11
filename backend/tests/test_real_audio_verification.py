import os
import tempfile
import pytest

from app.services.transcription_service import TranscriptionService


@pytest.mark.asyncio
async def test_real_audio_transcription_end_to_end():
    """End-to-End Real Audio Verification:

    Generates a real spoken speech audio file using Windows speech synthesis,
    loads the real faster-whisper 'tiny.en' model, and asserts actual speech-to-text accuracy.
    """
    temp_wav = os.path.join(tempfile.gettempdir(), "test_real_stt_verification.wav")
    try:
        import win32com.client

        # Generate real spoken audio via system speech synthesizer
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        filestream = win32com.client.Dispatch("SAPI.SpFileStream")
        filestream.Open(temp_wav, 3)  # SSFMCreateForWrite
        speaker.AudioOutputStream = filestream
        spoken_text = "PostgreSQL uses multi-version concurrency control with snapshots."
        speaker.Speak(spoken_text)
        filestream.Close()

        assert os.path.exists(temp_wav)
        with open(temp_wav, "rb") as f:
            audio_bytes = f.read()

        assert len(audio_bytes) > 1000

        # Execute real production transcription service
        service = TranscriptionService()
        transcribed = await service.transcribe_audio(audio_bytes, "test_real_stt_verification.wav")

        print(f"\n[Real Audio Verification] Spoken: '{spoken_text}'")
        print(f"[Real Audio Verification] Transcribed: '{transcribed}'")

        # Verify transcription semantic accuracy
        lower_transcribed = transcribed.lower()
        assert any(keyword in lower_transcribed for keyword in ["postgresql", "concurrency", "snapshots", "version"])

    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except OSError:
                pass
