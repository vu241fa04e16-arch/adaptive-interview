# Adaptive Interview Intelligence — Backend (Phase 1)

Welcome Hackathon 2026 — Problem Statement 03

## Overview
Modular, high-performance backend for the Adaptive Interview Intelligence web application.
Phase 1 establishes the foundational architecture:
- **FastAPI** web framework with OpenAPI / Redoc documentation.
- **PostgreSQL 18** database with asynchronous SQLAlchemy 2.0 and Alembic migrations.
- **Local Ollama** (`http://localhost:11434`, default model `llama3.1`) real AI integration with structured JSON generation and Pydantic validation.
- Zero cloud API keys required; no hardcoded responses or fake AI in production.
- Strictly maintained API route contracts (`/api/...`).

---

## Prerequisites (Windows)
1. **Python 3.14.3** installed.
2. **PostgreSQL 18** running locally on port `5432`.
3. **Ollama** running locally on `http://localhost:11434` with `llama3.1` pulled (`ollama run llama3.1`).

---

## Setup & Running with PowerShell

### 1. Environment Configuration
Copy `.env.example` to `.env` and verify your credentials:
```powershell
cd backend
Copy-Item .env.example .env
```
Ensure your `DATABASE_URL` matches your local PostgreSQL credentials:
```ini
DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/adaptive_interview
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
OLLAMA_TIMEOUT_SECONDS=60.0

# Speech-to-Text (STT) Whisper Configuration
WHISPER_MODEL=tiny.en
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
MAX_AUDIO_SIZE_MB=25
```

> [!NOTE]
> **First-Time Speech-to-Text Model Download:**
> The backend loads the faster-whisper model lazily on the first audio transcription request. The default model (`tiny.en`) requires approximately ~75 MB of disk space downloaded to the HuggingFace cache (`~/.cache/huggingface/hub`). For higher accuracy in multilingual setups, `base`, `small.en`, or `medium` can be configured via `WHISPER_MODEL` or `WHISPER_MODEL_SIZE`.

### 2. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 3. Apply Database Migrations
```powershell
python -m alembic upgrade head
```

### 4. Run Development Server
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API docs available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Running Tests

### Unit Tests (Fast, Isolated, with Explicit Mocks)
```powershell
python -m pytest -m "not live_ollama"
```

### Speech-to-Text Tests
```powershell
# Mocked STT Unit Tests (Fast, CI-friendly)
python -m pytest backend/tests/test_audio_answers.py backend/tests/test_transcription_service.py -q

# Real Audio Transcription Verification (hits real faster-whisper model)
python -m pytest backend/tests/test_real_audio_verification.py -s -v
```

### Live Ollama Integration Test (Hits Local `llama3.1`)
```powershell
python -m pytest -m "live_ollama" -s
```

### All Tests
```powershell
python -m pytest
```

---

## API Endpoints Status
| Endpoint | Method | Phase Status | Description |
| :--- | :--- | :--- | :--- |
| `/api/health` | GET | **Active** | System liveness probe (PostgreSQL + Ollama). |
| `/api/sessions` | POST | **Active** | Session initialization. |
| `/api/sessions/{sessionId}/resume` | POST | **Active** | Resume upload & extraction. |
| `/api/sessions/{sessionId}/next-question` | GET | **Active** | Deterministic adaptive question generation. |
| `/api/sessions/{sessionId}/answers` | POST | **Active** | Real-time rubric-based answer evaluation (typed text). |
| `/api/sessions/{sessionId}/answers/audio` | POST | **Active** | Real faster-whisper speech-to-text audio answer submission & evaluation. |
| `/api/sessions/{sessionId}/job-description` | POST | **Active** | Job description submission & skill requirement extraction. |
| `/api/sessions/{sessionId}/skill-gap` | GET | **Active** | 4-way skill gap analysis (JD vs Resume vs Live Evidence). |
| `/api/sessions/{sessionId}/events` | POST | **Active** | Telemetry & integrity event stream with 500-event safety cap. |
| `/api/sessions/{sessionId}/complete` | POST | **Active** | Session completion & report trigger. |
| `/api/sessions/{sessionId}/report` | GET | **Active** | Final candidate decision report with integrity & skill gap synthesis. |
