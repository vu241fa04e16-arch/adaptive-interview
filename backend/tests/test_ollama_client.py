from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from pydantic import BaseModel, Field

from app.core.exceptions import (
    AIProviderUnavailableException,
    AIStructuredGenerationException,
    ModelNotAvailableException,
)
from app.core.ollama_client import AsyncOllamaClient


class SampleEvaluationOutput(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    verdict: str
    strengths: list[str]


@pytest.mark.asyncio
async def test_structured_generation_success():
    """Verifies that valid JSON returned by client is parsed into the Pydantic schema."""
    client = AsyncOllamaClient(
        api_key="gsk_test_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"score": 8.5, "verdict": "strong", "strengths": ["Clear explanation", "Accurate syntax"]}'
                }
            }
        ]
    }

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = mock_resp

    with patch.object(client, "_get_client", return_value=mock_http_client):
        result = await client.generate_structured(
            prompt="Evaluate this code snippet",
            schema=SampleEvaluationOutput,
        )

        assert isinstance(result, SampleEvaluationOutput)
        assert result.score == 8.5
        assert result.verdict == "strong"
        assert len(result.strengths) == 2


@pytest.mark.asyncio
async def test_structured_generation_malformed_json_raises():
    """Verifies that non-JSON text output raises AIStructuredGenerationException."""
    client = AsyncOllamaClient(
        api_key="gsk_test_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "I am unable to answer this question in JSON format. Here is some text."
                }
            }
        ]
    }

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = mock_resp

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(AIStructuredGenerationException) as exc_info:
            await client.generate_structured(
                prompt="Evaluate this answer",
                schema=SampleEvaluationOutput,
            )
        assert "malformed JSON" in exc_info.value.message


@pytest.mark.asyncio
async def test_structured_generation_schema_mismatch_raises():
    """Verifies that JSON missing required fields or invalid types raises AIStructuredGenerationException."""
    client = AsyncOllamaClient(
        api_key="gsk_test_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"verdict": "pass", "strengths": ["Good"]}'
                }
            }
        ]
    }

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = mock_resp

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(AIStructuredGenerationException) as exc_info:
            await client.generate_structured(
                prompt="Evaluate this",
                schema=SampleEvaluationOutput,
            )
        assert "did not match schema" in exc_info.value.message


@pytest.mark.asyncio
async def test_connection_error_raises_ai_provider_unavailable():
    """Verifies that network connection failure raises AIProviderUnavailableException."""
    client = AsyncOllamaClient(
        api_key="gsk_test_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_http_client = AsyncMock()
    mock_http_client.post.side_effect = httpx.ConnectError("Connection refused")

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(AIProviderUnavailableException) as exc_info:
            await client.generate_structured(
                prompt="Generate question",
                schema=SampleEvaluationOutput,
            )
        assert exc_info.value.status_code == 503
        assert "Failed to connect to Groq API" in exc_info.value.message


@pytest.mark.asyncio
async def test_timeout_raises_ai_provider_unavailable():
    """Verifies that an inference timeout raises AIProviderUnavailableException."""
    client = AsyncOllamaClient(
        api_key="gsk_test_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_http_client = AsyncMock()
    mock_http_client.post.side_effect = httpx.TimeoutException("Read timed out")

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(AIProviderUnavailableException) as exc_info:
            await client.generate_structured(
                prompt="Generate question",
                schema=SampleEvaluationOutput,
            )
        assert exc_info.value.status_code == 503
        assert "timed out" in exc_info.value.message


@pytest.mark.asyncio
async def test_missing_model_raises_model_not_available():
    """Verifies that HTTP 404 from client raises ModelNotAvailableException."""
    client = AsyncOllamaClient(
        api_key="gsk_test_key",
        base_url="https://api.groq.com/openai/v1",
        model="non_existent_model",
    )

    mock_request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    mock_response = httpx.Response(404, request=mock_request, text='{"error":"model not found"}')

    mock_http_client = AsyncMock()
    mock_http_client.post.side_effect = httpx.HTTPStatusError(
        message="Client error '404 Not Found'",
        request=mock_request,
        response=mock_response,
    )

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(ModelNotAvailableException) as exc_info:
            await client.generate_structured(
                prompt="Hello",
                schema=SampleEvaluationOutput,
            )
        assert exc_info.value.status_code == 503
