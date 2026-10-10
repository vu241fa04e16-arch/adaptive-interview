import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_create_session_success(client: TestClient):
    """Verifies that POST /api/sessions successfully initializes and persists a new session."""
    payload = {
        "candidate_name": "Jane Doe",
        "candidate_email": "jane.doe@example.com",
        "target_role": "Senior Backend Architect",
        "target_level": "Senior",
        "time_limit_minutes": 45,
    }

    response = client.post("/api/sessions", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "sessionId" in data
    # Verify sessionId is a valid UUID
    parsed_uuid = uuid.UUID(data["sessionId"])
    assert str(parsed_uuid) == data["sessionId"]

    assert data["candidate_name"] == "Jane Doe"
    assert data["candidate_email"] == "jane.doe@example.com"
    assert data["target_role"] == "Senior Backend Architect"
    assert data["target_level"] == "Senior"
    assert data["status"] == "created"
    assert data["time_limit_minutes"] == 45
    assert data["resume_uploaded"] is False
    assert "created_at" in data


def test_create_session_invalid_email(client: TestClient):
    """Verifies that an invalid email address format fails validation with HTTP 422."""
    payload = {
        "candidate_name": "Jane Doe",
        "candidate_email": "not-an-email-address",
        "target_role": "Senior Backend Architect",
        "target_level": "Senior",
        "time_limit_minutes": 45,
    }

    response = client.post("/api/sessions", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"


def test_create_session_invalid_time_limit(client: TestClient):
    """Verifies that time limits below 15 or above 120 minutes are rejected with HTTP 422."""
    payload_too_low = {
        "candidate_name": "Jane Doe",
        "candidate_email": "jane@example.com",
        "target_role": "Backend Engineer",
        "target_level": "Mid",
        "time_limit_minutes": 10,
    }
    response_low = client.post("/api/sessions", json=payload_too_low)
    assert response_low.status_code == 422

    payload_too_high = {
        "candidate_name": "Jane Doe",
        "candidate_email": "jane@example.com",
        "target_role": "Backend Engineer",
        "target_level": "Mid",
        "time_limit_minutes": 180,
    }
    response_high = client.post("/api/sessions", json=payload_too_high)
    assert response_high.status_code == 422


def test_create_session_invalid_seniority_level(client: TestClient):
    """Verifies that non-standard seniority levels are rejected with HTTP 422."""
    payload = {
        "candidate_name": "Jane Doe",
        "candidate_email": "jane@example.com",
        "target_role": "Backend Engineer",
        "target_level": "SuperSenior",
        "time_limit_minutes": 45,
    }
    response = client.post("/api/sessions", json=payload)
    assert response.status_code == 422


def test_create_session_missing_required_fields(client: TestClient):
    """Verifies that missing candidate name or role is rejected with HTTP 422."""
    response = client.post("/api/sessions", json={"candidate_email": "jane@example.com"})
    assert response.status_code == 422
