from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ollama_client
from app.main import app
from app.schemas.health import HealthResponse


def test_health_all_healthy(client: TestClient, mock_ollama_healthy):
    """Verifies that GET /api/health reports 'healthy' when DB and Ollama are both ready."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama_healthy

    with patch("app.api.routes.check_database_health") as mock_db_health:
        mock_db_health.return_value = {
            "status": "connected",
            "dialect": "postgresql",
            "driver": "asyncpg",
        }

        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["database"]["status"] == "connected"
        assert data["ollama"]["status"] == "available"
        assert data["ollama"]["model_available"] is True

        # Validate against Pydantic schema
        validated = HealthResponse.model_validate(data)
        assert validated.status == "healthy"

    app.dependency_overrides.clear()


def test_health_ollama_unavailable_reports_degraded(client: TestClient, mock_ollama_unavailable):
    """Verifies that GET /api/health reports 'degraded' when Ollama is offline, not falsely healthy."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama_unavailable

    with patch("app.api.routes.check_database_health") as mock_db_health:
        mock_db_health.return_value = {
            "status": "connected",
            "dialect": "postgresql",
            "driver": "asyncpg",
        }

        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()

        # Must report degraded, NOT healthy
        assert data["status"] == "degraded"
        assert data["database"]["status"] == "connected"
        assert data["ollama"]["status"] == "unavailable"
        assert data["ollama"]["model_available"] is False
        assert "error" in data["ollama"]

    app.dependency_overrides.clear()


def test_health_database_failure_reports_unhealthy(client: TestClient, mock_ollama_healthy):
    """Verifies that GET /api/health reports 'unhealthy' when Database connection fails."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama_healthy

    with patch("app.api.routes.check_database_health") as mock_db_health:
        mock_db_health.return_value = {
            "status": "disconnected",
            "dialect": "postgresql",
            "error": "connection refused on 127.0.0.1:5432",
        }

        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()

        # Must report unhealthy
        assert data["status"] == "unhealthy"
        assert data["database"]["status"] == "disconnected"
        assert data["database"]["error"] is not None

    app.dependency_overrides.clear()
