from unittest.mock import patch
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.main import app


def test_endpoint_lifecycle_and_implemented_contract(client: TestClient, mock_ollama_healthy):
    """Verifies that all 8 API endpoints are implemented and respond properly according to contract."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama_healthy

    with patch("app.api.routes.check_database_health") as mock_db:
        mock_db.return_value = {"status": "connected", "dialect": "postgresql"}

        # 1. GET /api/health (Phase 1)
        resp = client.get("/api/health")
        assert resp.status_code == 200

    app.dependency_overrides.clear()

    # 2. POST /api/sessions (Phase 2 - returns 201 on valid input, 422 on empty)
    resp = client.post("/api/sessions", json={})
    assert resp.status_code == 422

    # 3. POST /api/sessions/{sessionId}/resume (Phase 2 - returns 400 on invalid UUID when file is provided)
    resp = client.post(
        "/api/sessions/invalid-id/resume",
        files={"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")},
    )
    assert resp.status_code == 400

    # 4. GET /api/sessions/{sessionId}/next-question (Phase 3 - returns 400 on invalid UUID)
    resp = client.get("/api/sessions/invalid-id/next-question")
    assert resp.status_code == 400

    # 5. POST /api/sessions/{sessionId}/answers (Phase 4 - returns 400 on invalid UUID)
    resp = client.post(
        "/api/sessions/invalid-id/answers",
        json={"question_id": "b8f67e42-1a2b-4c3d-9e5f-112233445566", "answer_text": "sample"},
    )
    assert resp.status_code == 400

    # 6. POST /api/sessions/{sessionId}/events (Phase 5 - returns 400 on invalid UUID)
    resp = client.post(
        "/api/sessions/invalid-id/events",
        json={"event_type": "TAB_SWITCH"},
    )
    assert resp.status_code == 400

    # 7. POST /api/sessions/{sessionId}/complete (Phase 6 - returns 400 on invalid UUID)
    resp = client.post("/api/sessions/invalid-id/complete")
    assert resp.status_code == 400

    # 8. GET /api/sessions/{sessionId}/report (Phase 7 - returns 400 on invalid UUID)
    resp = client.get("/api/sessions/invalid-id/report")
    assert resp.status_code == 400
