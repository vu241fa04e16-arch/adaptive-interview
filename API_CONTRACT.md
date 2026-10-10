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

## 4. Error Responses

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
