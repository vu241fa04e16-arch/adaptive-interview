import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.models.event import SessionEvent
from app.models.session import InterviewSession
from app.services.integrity_service import IntegrityService


def test_integrity_service_normal_events_low_risk():
    """Verifies that 1-2 tab switches and window focus events remain low risk without suspicion flag."""
    service = IntegrityService()
    session = InterviewSession(
        candidate_name="Alice",
        candidate_email="alice@example.com",
        target_role="Backend Engineer",
        target_level="Mid",
    )

    now = datetime.now(timezone.utc)
    events = [
        SessionEvent(event_type="INTERVIEW_START", event_data={}, timestamp=now),
        SessionEvent(event_type="TAB_SWITCH", event_data={"duration": 2}, timestamp=now),
        SessionEvent(event_type="WINDOW_FOCUS", event_data={}, timestamp=now),
    ]

    summary = service.analyze_events(events, session)
    assert summary.total_events == 3
    assert summary.tab_switches == 1
    assert summary.window_blurs == 0
    assert summary.suspicious_activity_flag is False
    assert summary.risk_level == "low"
    assert summary.risk_score <= 2.0
    assert len(summary.timeline) == 3
    assert summary.timeline[0].severity == "info"
    assert summary.timeline[1].severity == "low"


def test_integrity_service_moderate_events_medium_risk():
    """Verifies that 4-6 tab switches produce medium risk without flagging as suspicious."""
    service = IntegrityService()
    session = InterviewSession(
        candidate_name="Bob",
        candidate_email="bob@example.com",
        target_role="Backend Engineer",
        target_level="Mid",
    )

    now = datetime.now(timezone.utc)
    events = [
        SessionEvent(event_type="TAB_SWITCH", event_data={"duration": 3}, timestamp=now)
        for _ in range(5)
    ]

    summary = service.analyze_events(events, session)
    assert summary.tab_switches == 5
    assert summary.suspicious_activity_flag is False
    assert summary.risk_level in ["low", "medium"]
    assert any("Occasional tab switches" in r for r in summary.risk_indicators)


def test_integrity_service_elevated_tab_switches_high_risk():
    """Verifies that >= 10 tab switches escalate risk and trigger suspicious_activity_flag with explainable reasons."""
    service = IntegrityService()
    session = InterviewSession(
        candidate_name="Charlie",
        candidate_email="charlie@example.com",
        target_role="Backend Engineer",
        target_level="Mid",
    )

    now = datetime.now(timezone.utc)
    events = [
        SessionEvent(event_type="TAB_SWITCH", event_data={"duration": 4}, timestamp=now)
        for _ in range(11)
    ]

    summary = service.analyze_events(events, session)
    assert summary.tab_switches == 11
    assert summary.suspicious_activity_flag is True
    assert summary.risk_level == "high"
    assert summary.risk_score >= 5.0
    assert len(summary.reasons_for_flags) >= 1
    assert "11 occurrences" in summary.reasons_for_flags[0]


def test_integrity_service_long_blur_and_large_paste():
    """Verifies detection of long blur periods (> 45s) and large clipboard paste (> 400 chars)."""
    service = IntegrityService()
    session = InterviewSession(
        candidate_name="Diana",
        candidate_email="diana@example.com",
        target_role="Backend Engineer",
        target_level="Mid",
    )

    now = datetime.now(timezone.utc)
    events = [
        SessionEvent(event_type="WINDOW_BLUR", event_data={"duration": 60}, timestamp=now),
        SessionEvent(event_type="PASTE_DETECTED", event_data={"characters": 650}, timestamp=now),
    ]

    summary = service.analyze_events(events, session)
    assert summary.window_blurs == 1
    assert summary.pastes_detected == 1
    assert any("Extended window unfocus" in r for r in summary.risk_indicators)
    assert any("Large clipboard paste" in r for r in summary.risk_indicators)
    assert summary.timeline[0].severity == "medium"
    assert summary.timeline[1].severity == "medium"


def test_event_endpoint_lifecycle_and_validation(client: TestClient):
    """Verifies POST /api/sessions/{sessionId}/events validation and progress tracking."""
    # 1. Create session
    resp = client.post(
        "/api/sessions",
        json={
            "candidate_name": "Eve",
            "candidate_email": "eve@example.com",
            "target_role": "Backend Engineer",
            "target_level": "Mid",
            "time_limit_minutes": 45,
        },
    )
    assert resp.status_code == 201
    session_id = resp.json()["sessionId"]

    # 2. Record supported event types
    event_types = ["INTERVIEW_START", "TAB_SWITCH", "WINDOW_BLUR", "WINDOW_FOCUS", "PASTE_DETECTED"]
    for ev in event_types:
        resp_ev = client.post(
            f"/api/sessions/{session_id}/events",
            json={"event_type": ev, "event_data": {"test_key": "val"}},
        )
        assert resp_ev.status_code == 200
        assert resp_ev.json()["event_type"] == ev
        assert "progress" in resp_ev.json()

    # 3. Validation: short event_type (< 2 chars) returns 422 (Pydantic validation error)
    resp_short = client.post(
        f"/api/sessions/{session_id}/events",
        json={"event_type": "x"},
    )
    assert resp_short.status_code == 422
    assert resp_short.json()["error"] == "VALIDATION_ERROR"

    # 4. Validation: invalid session ID
    resp_bad_id = client.post(
        "/api/sessions/not-a-uuid/events",
        json={"event_type": "TAB_SWITCH"},
    )
    assert resp_bad_id.status_code == 400
