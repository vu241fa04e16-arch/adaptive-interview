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
```

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

### Live Ollama Integration Test (Hits Local `llama3.1`)
```powershell
python -m pytest -m "live_ollama" -s
```

### All Tests
```powershell
python -m pytest
```

---

## API Endpoints Status (Phase 1)
| Endpoint | Method | Phase Status | Description |
| :--- | :--- | :--- | :--- |
| `/api/health` | GET | **Active** | System liveness probe (PostgreSQL + Ollama). |
| `/api/sessions` | POST | Reserved (Phase 2) | Session initialization. |
| `/api/sessions/{sessionId}/resume` | POST | Reserved (Phase 2) | Resume upload & extraction. |
| `/api/sessions/{sessionId}/next-question` | GET | Reserved (Phase 3) | Deterministic adaptive question generation. |
| `/api/sessions/{sessionId}/answers` | POST | Reserved (Phase 4) | Real-time rubric-based answer evaluation. |
| `/api/sessions/{sessionId}/events` | POST | Reserved (Phase 5) | Telemetry & integrity event stream. |
| `/api/sessions/{sessionId}/complete` | POST | Reserved (Phase 5) | Session completion & report trigger. |
| `/api/sessions/{sessionId}/report` | GET | Reserved (Phase 5) | Final candidate decision report. |
