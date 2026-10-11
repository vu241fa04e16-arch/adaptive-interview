# Adaptive Interview Intelligence Platform

An intelligent, real-time technical screening platform that dynamically scales interview question difficulty based on candidate performance, monitors anti-cheat telemetry, supports multi-modal audio transcription, and generates comprehensive recruiter competency analytics.

[![GitHub Repository](https://img.shields.io/badge/GitHub-adaptive--interview-181717?style=for-the-badge&logo=github)](https://github.com/vu241fa04e16-arch/adaptive-interview)
[![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20PostgreSQL%20%7C%20Ollama-009688?style=for-the-badge&logo=fastapi)](backend/)
[![Frontend](https://img.shields.io/badge/Frontend-React%2019%20%7C%20Vite%20%7C%20TailwindCSS-61DAFB?style=for-the-badge&logo=react)](frontend/)

---

## 🌟 Key Features

- **Adaptive Dynamic Scaling**: Questions adjust in real time across difficulty tiers based on answer evaluation scores.
- **Local AI Privacy**: Powered by local **Ollama** (`llama3.1`) — zero cloud API keys required, no rate limits, deterministic schema validation.
- **Voice & Text Dual Input**: Candidates can dictate responses using faster-whisper speech-to-text or type into the response editor.
- **Anti-Cheat Telemetry**: Tracks tab switching, blur events, copy/paste attempts, and mouse telemetry with automated integrity scoring.
- **Automated Skill Gap Analysis**: Compares candidate answers against job description requirements to generate competency maps and hiring decisions.
- **Recruiter Dashboard**: Interactive visual reports with radar charts, integrity timelines, and actionable feedback.

---

## 🏗️ Architecture

```text
adaptive-interview/
├── backend/                  # FastAPI + SQLAlchemy + PostgreSQL + Ollama
│   ├── app/
│   │   ├── api/routes.py     # REST API routes
│   │   ├── core/             # Database, config, Ollama & Whisper clients
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── services/         # Adaptive engine, skill gap, resume parser
│   ├── alembic/              # Database migration scripts
│   └── tests/                # Comprehensive test suite (100+ tests)
├── frontend/                 # React 19 + Vite + Tailwind CSS
│   ├── src/
│   │   ├── components/       # Reusable UI & interview widgets
│   │   ├── pages/            # Home, UploadResume, Interview, RecruiterDashboard
│   │   ├── hooks/            # useInterviewSession, useIntegrity, useTimer, useAudioRecorder
│   │   └── services/api.js   # Centralized API service with offline mock fallback
│   └── public/
├── API_CONTRACT.md           # Full specification of backend REST endpoints
└── README.md
```

---

## 🚀 Quick Start Guide (For Anyone Running This Project)

### 📋 Prerequisites

1. **Git**: Installed on your system ([Download Git](https://git-scm.com/))
2. **Node.js**: v18.0.0 or higher ([Download Node.js](https://nodejs.org/))
3. **Python**: 3.10+ (tested with 3.11 - 3.14) ([Download Python](https://python.org/))
4. **PostgreSQL**: Running locally on port `5432` ([Download PostgreSQL](https://www.postgresql.org/download/))
5. **Ollama**: Running locally with `llama3.1` model ([Download Ollama](https://ollama.ai/))
   ```bash
   ollama run llama3.1
   ```

---

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/vu241fa04e16-arch/adaptive-interview.git
cd adaptive-interview
```

---

### 2️⃣ Backend Setup

Open a terminal in the project directory:

```bash
# Navigate to backend
cd backend

# Create and activate Python virtual environment
# On Windows:
python -m venv venv
.\venv\Scripts\activate

# On macOS / Linux:
# python3 -m venv venv
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
# Copy .env.example to .env
# Windows:
copy .env.example .env
# macOS / Linux:
# cp .env.example .env

# Verify database credentials in .env:
# DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/adaptive_interview

# Run database migrations
alembic upgrade head

# Start the FastAPI server
uvicorn app.main:app --reload --port 8000
```

The backend API will be live at:
- **API Base**: `http://localhost:8000`
- **Swagger Docs**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

### 3️⃣ Frontend Setup

Open a second terminal window:

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Open your browser and navigate to:
**`http://localhost:5173`**

*(Note: The frontend includes an automatic offline mock fallback mode in `src/services/api.js`, so you can test the entire interview workflow even before configuring PostgreSQL or Ollama!)*

---

## 🧪 Running Tests

### Backend Unit & Integration Tests:
```bash
cd backend
pytest
```

---

## 📄 API Documentation

For the full specification of all REST endpoints, payloads, and response schemas, refer to [`API_CONTRACT.md`](API_CONTRACT.md).
