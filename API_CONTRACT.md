# Adaptive Interview Intelligence — API Contract Specification

This document defines the strict, unversioned API contracts (`/api/...`) for communication between the FastAPI backend and React frontend.

---

## 1. System Health & Readiness Probe

### `GET /api/health`
Probes separate application, PostgreSQL database, and local Ollama model statuses.

#### Response: `200 OK`
```json
{
  "status": "healthy",
  "app": "Adaptive Interview Intelligence",
  "environment": "development",
  "timestamp": "2026-10-10T16:20:15.707472Z",
  "database": {
    "status": "connected",
    "dialect": "postgresql",
    "driver": "asyncpg",
    "error": null
  },
  "ollama": {
    "status": "available",
    "base_url": "http://localhost:11434",
    "configured_model": "llama3.1",
    "model_available": true,
    "available_models": ["llama3.1:latest", "llama3.2:latest"],
    "error": null
  }
}
```

---

## 2. Session Management

### `POST /api/sessions`
Initializes a new interview session and persists baseline configuration in PostgreSQL.

#### Request Body (`application/json`)
```json
{
  "candidate_name": "Jane Doe",
  "candidate_email": "jane.doe@example.com",
  "target_role": "Senior Backend Architect",
  "target_level": "Senior",
  "time_limit_minutes": 45
}
```

* Validation Constraints:
  * `candidate_name`: string (2 - 255 chars)
  * `candidate_email`: valid RFC email format
  * `target_role`: string (2 - 255 chars)
  * `target_level`: `"Junior"` | `"Mid"` | `"Senior"` | `"Lead"` | `"Staff"` | `"Principal"`
  * `time_limit_minutes`: integer between 15 and 120 (default: 45)

#### Response: `201 Created`
```json
{
  "sessionId": "b8f67e42-1a2b-4c3d-9e5f-112233445566",
  "candidate_name": "Jane Doe",
  "candidate_email": "jane.doe@example.com",
  "target_role": "Senior Backend Architect",
  "target_level": "Senior",
  "status": "created",
  "time_limit_minutes": 45,
  "created_at": "2026-10-10T21:55:00.000Z",
  "resume_uploaded": false
}
```

---

## 3. Resume Upload & Real AI Analysis

### `POST /api/sessions/{sessionId}/resume`
Accepts multipart file upload of PDF or DOCX resume, validates file size/content, computes SHA-256 hash, and runs real local Ollama skill extraction.

#### Request Headers & Body
* **Content-Type**: `multipart/form-data`
* **Form Field**: `file` (binary PDF or DOCX, max size 10 MB)

#### Response: `200 OK`
```json
{
  "sessionId": "b8f67e42-1a2b-4c3d-9e5f-112233445566",
  "resume_parsed": true,
  "file_name": "Jane_Doe_Resume.pdf",
  "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "file_size_bytes": 1048576,
  "candidate_overview": "Senior Backend Engineer with 7+ years designing high-throughput distributed architectures, specializing in PostgreSQL transaction isolation and Kafka event streams.",
  "claimed_skills": [
    {
      "name": "PostgreSQL",
      "claimed_experience_years": 6.0,
      "claimed_proficiency": "Expert",
      "context_snippet": "Led PostgreSQL migration and optimized MVCC query patterns across 10TB database."
    },
    {
      "name": "Distributed Systems",
      "claimed_experience_years": 4.5,
      "claimed_proficiency": "Advanced",
      "context_snippet": "Architected distributed event messaging pipelines processing 50k events/sec."
    },
    {
      "name": "Apache Kafka",
      "claimed_experience_years": 3.0,
      "claimed_proficiency": "Intermediate",
      "context_snippet": "Configured Kafka consumer groups and idempotency keys."
    }
  ],
  "projects": [
    {
      "project_name": "High-Throughput Ledger Engine",
      "technologies": ["PostgreSQL", "Kafka", "Python", "FastAPI"],
      "highlights": [
        "Achieved 99.99% availability with zero double-entry errors using SSI isolation.",
        "Reduced query latency by 45% via partitioning and composite indexing."
      ]
    }
  ],
  "suggested_focus_areas": [
    "PostgreSQL MVCC SSI versus Read Committed isolation tradeoffs",
    "Kafka exactly-once semantics and transactional coordinator recovery",
    "Distributed deadlocks and lock escalation in multi-tenant schemas"
  ],
  "message": "Resume analyzed successfully. Interview competency profile primed."
}
```

* **Duplicate Handling**: If the identical file (same SHA-256 hash) is re-uploaded to the session, the API deliberately returns the existing analysis with the message `"Identical resume already analyzed for this session. Retrieved existing profile."`.

---

## 4. Audio Answer Submission via Speech-to-Text

### `POST /api/sessions/{sessionId}/answers/audio`
Accepts candidate spoken audio via multipart form data, executes Speech-to-Text with local `faster-whisper`, feeds the transcript into rubric-based Ollama evaluation, and returns the transcript alongside evaluation results.

#### Request Headers & Body
* **Content-Type**: `multipart/form-data`
* **Form Fields**:
  * `question_id`: UUID string (Required)
  * `file`: Binary audio file (Required). Supported formats: `.wav`, `.mp3`, `.m4a`, `.webm`, `.ogg`, `.flac`, `.aac`, `.mp4` (Max size: 25 MB).
  * `time_taken_seconds`: Integer (Optional)

#### Response: `200 OK`
```json
{
  "sessionId": "b8f67e42-1a2b-4c3d-9e5f-112233445566",
  "answer_id": "c1f78e53-2b3c-4d4e-af6a-223344556677",
  "question_id": "a9e56d31-0b1a-3c2b-8d4e-001122334455",
  "transcript": "PostgreSQL uses multi-version concurrency control with snapshot isolation to isolate transactions.",
  "score": 8.8,
  "strengths": [
    "Correctly explained snapshot isolation and tuple visibility rules.",
    "Mentioned non-blocking read and write concurrency."
  ],
  "weaknesses": [],
  "feedback": "Strong spoken answer demonstrating clear technical communication and database concurrency mastery.",
  "improvement_suggestions": [
    "Discuss Serializable Snapshot Isolation (SSI) predicate locks."
  ],
  "competency": "Database Architecture",
  "created_at": "2026-10-11T14:10:00.000Z"
}
```

* **Duplicate Protection**: If an answer was already submitted and evaluated for the given question ID, duplicate answer creation is prevented and the existing evaluation is safely returned.

---

## 5. Job Description & Skill Gap Analysis

### `POST /api/sessions/{sessionId}/job-description`
Submits a job description (raw text or structured JSON) for a session, extracts required skills/competencies via Ollama or deterministic heuristics, and generates a baseline skill gap report.

#### Request Body (`application/json`)
```json
{
  "job_description": "We are seeking a Senior Distributed Systems Engineer with expertise in PostgreSQL, Kafka, and System Design..."
}
```

#### Response: `200 OK`
```json
{
  "sessionId": "b8f67e42-1a2b-4c3d-9e5f-112233445566",
  "job_description_provided": true,
  "required_skills": [
    {
      "name": "PostgreSQL",
      "category": "technical",
      "importance": "high"
    },
    {
      "name": "Apache Kafka",
      "category": "technical",
      "importance": "high"
    }
  ],
  "demonstrated_skills": ["PostgreSQL"],
  "claimed_unvalidated_skills": ["Apache Kafka"],
  "missing_skills": ["Kubernetes"],
  "not_assessed_skills": [],
  "evidence_by_skill": {
    "PostgreSQL": ["Score 8.5/10: Thoroughly explained MVCC and snapshot isolation."]
  },
  "improvement_suggestions": [
    "Assess candidate hands-on experience in Kafka partition rebalancing."
  ],
  "follow_up_questions": [
    "How would you troubleshoot consumer lag in Kafka?"
  ]
}
```

### `GET /api/sessions/{sessionId}/skill-gap`
Retrieves the real-time skill gap analysis for the session comparing job requirements against resume claims and evaluated interview answers.

#### Response: `200 OK`
Returns the `SkillGapReport` schema matching the structure above.

---

## 6. Interview Integrity Telemetry

### `POST /api/sessions/{sessionId}/events`
Records browser focus, tab switches, blur duration, paste anomalies, and window state events. Enforces safety caps (up to 500 events per session) against spamming.

#### Request Body (`application/json`)
```json
{
  "events": [
    {
      "event_type": "tab_switch",
      "timestamp": "2026-10-10T22:05:00.000Z",
      "metadata": {
        "blur_duration_seconds": 12.5,
        "paste_character_count": 450
      }
    }
  ]
}
```

#### Response: `200 OK`
```json
{
  "recorded_count": 1,
  "session_status": "in_progress"
}
```

---

## 7. Candidate Decision Report

### `GET /api/sessions/{sessionId}/report`
Generates or retrieves the comprehensive candidate evaluation report, integrating resume extraction, actual interview performance, 4-way skill gap classification, and chronological integrity telemetry into a holistic hiring decision recommendation.

#### Response: `200 OK`
```json
{
  "sessionId": "b8f67e42-1a2b-4c3d-9e5f-112233445566",
  "candidate_name": "Jane Doe",
  "target_role": "Senior Backend Architect",
  "overall_score": 8.5,
  "competency_breakdown": {
    "Database Architecture": 8.8,
    "System Design": 8.2
  },
  "claimed_skills": ["PostgreSQL", "Apache Kafka"],
  "demonstrated_skills": ["PostgreSQL"],
  "skill_gap_analysis": {
    "job_description_provided": true,
    "demonstrated_skills": ["PostgreSQL"],
    "claimed_unvalidated_skills": ["Apache Kafka"],
    "missing_skills": ["Kubernetes"],
    "not_assessed_skills": []
  },
  "overall_assessment": "Candidate demonstrated strong competencies across assessed areas.",
  "decision_recommendation": "hire",
  "strengths": ["PostgreSQL MVCC mastery"],
  "weaknesses": ["Unassessed in event streaming under load"],
  "integrity_summary": {
    "risk_level": "low",
    "risk_score": 15,
    "tab_switch_count": 2,
    "unusual_pasting_count": 0,
    "multiple_faces_detected": false,
    "no_face_detected": false,
    "suspicious_flag": false,
    "reasons_for_flags": [],
    "timeline": [
      {
        "event_type": "tab_switch",
        "timestamp": "2026-10-10T22:05:00.000Z",
        "severity": "low",
        "summary": "Brief tab switch (12.5s)"
      }
    ]
  },
  "created_at": "2026-10-10T22:30:00.000Z"
}
```

---

## 8. Error Responses

All error payloads use a standardized envelope:
```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable explanation of error.",
  "details": {},
  "timestamp": "2026-10-10T21:55:00.000Z"
}
```

### Common HTTP Status Codes
* `400 Bad Request`: Invalid UUID format, empty file (0 bytes), invalid session state.
* `404 Not Found`: Session ID does not exist (`RESOURCE_NOT_FOUND`).
* `413 Payload Too Large`: Uploaded file exceeds 10 MB (`FILE_SIZE_LIMIT_EXCEEDED`).
* `415 Unsupported Media Type`: Non-PDF and non-DOCX upload (`UNSUPPORTED_MEDIA_TYPE`).
* `422 Unprocessable Entity`: Request body validation failed or corrupt/unreadable document.
* `501 Not Implemented`: Endpoints scheduled for subsequent phases.
* `502 Bad Gateway`: Ollama generated malformed JSON output (`AI_STRUCTURED_GENERATION_FAILED`).
* `503 Service Unavailable`: Local Ollama service is offline or unreachable (`AI_PROVIDER_UNAVAILABLE`).
