from unittest.mock import patch
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.main import app


def test_endpoint_lifecycle_and_unimplemented_contract(client: TestClient, mock_ollama_healthy):
    """Verifies that implemented endpoints respond properly and reserved endpoints return 501."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama_healthy

    with patch("app.api.routes.check_database_health") as mock_db:
        mock_db.return_value = {"status": "connected", "dialect": "postgresql"}

        # 1. GET /api/health (Active Phase 1)
        resp = client.get("/api/health")
        assert resp.status_code == 200

    app.dependency_overrides.clear()

    # 2. POST /api/sessions (Active Phase 2 - returns 201 on valid input, 422 on empty)
    resp = client.post("/api/sessions", json={})
    assert resp.status_code == 422

    # 3. POST /api/sessions/{sessionId}/resume (Active Phase 2 - returns 400 on invalid UUID when file is provided)
    resp = client.post(
        "/api/sessions/invalid-id/resume",
        files={"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")},
    )
    assert resp.status_code == 400

    # 4. GET /api/sessions/{sessionId}/next-question (Active Phase 3 - returns 400 on invalid UUID)
    resp = client.get("/api/sessions/invalid-id/next-question")
    assert resp.status_code == 400

    # 5. POST /api/sessions/{sessionId}/answers (501 Phase 4)
    resp = client.post("/api/sessions/test-id/answers", json={})
    assert resp.status_code == 501
    assert "Phase 4" in resp.json()["detail"]

    # 6. POST /api/sessions/{sessionId}/events (501 Phase 5)
    resp = client.post("/api/sessions/test-id/events", json={})
    assert resp.status_code == 501
    assert "Phase 5" in resp.json()["detail"]

    # 7. POST /api/sessions/{sessionId}/complete (501 Phase 5)
    resp = client.post("/api/sessions/test-id/complete", json={})
    assert resp.status_code == 501
    assert "Phase 5" in resp.json()["detail"]

    # 8. GET /api/sessions/{sessionId}/report (501 Phase 5)
    resp = client.get("/api/sessions/test-id/report")
    assert resp.status_code == 501
    assert "Phase 5" in resp.json()["detail"]
