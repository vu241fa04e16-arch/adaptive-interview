from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from pydantic import BaseModel, Field

from app.core.exceptions import (
    AIProviderUnavailableException,
    AIStructuredGenerationException,
    ModelNotAvailableException,
)
from app.core.groq_client import AsyncGroqClient


class SampleEvaluationOutput(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    verdict: str
    strengths: list[str]


@pytest.mark.asyncio
async def test_groq_structured_generation_success():
    """Verifies that OpenAI-compatible JSON returned by Groq is parsed into the Pydantic schema."""
    client = AsyncGroqClient(
        api_key="gsk_test_mock_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "chatcmpl-test-123",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": '{"score": 8.5, "verdict": "strong", "strengths": ["Clear explanation", "Accurate syntax"]}',
                },
                "finish_reason": "stop",
            }
        ],
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
async def test_groq_structured_generation_markdown_wrapped_json():
    """Verifies that markdown code fenced JSON (```json ... ```) is cleaned and parsed."""
    client = AsyncGroqClient(
        api_key="gsk_test_mock_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '```json\n{"score": 9.2, "verdict": "exceptional", "strengths": ["Deep concurrency knowledge"]}\n```',
                }
            }
        ]
    }

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = mock_resp

    with patch.object(client, "_get_client", return_value=mock_http_client):
        result = await client.generate_structured(
            prompt="Evaluate candidate",
            schema=SampleEvaluationOutput,
        )
        assert result.score == 9.2
        assert result.verdict == "exceptional"


@pytest.mark.asyncio
async def test_groq_structured_generation_properties_unwrapping():
    """Verifies that LLM responses wrapped in a 'properties' dictionary are automatically unwrapped."""
    client = AsyncGroqClient(
        api_key="gsk_test_mock_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"properties": {"score": 7.5, "verdict": "solid", "strengths": ["Good testing"]}}',
                }
            }
        ]
    }

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = mock_resp

    with patch.object(client, "_get_client", return_value=mock_http_client):
        result = await client.generate_structured(
            prompt="Evaluate candidate",
            schema=SampleEvaluationOutput,
        )
        assert result.score == 7.5
        assert result.verdict == "solid"


@pytest.mark.asyncio
async def test_groq_structured_generation_malformed_json_raises():
    """Verifies that non-JSON text output raises AIStructuredGenerationException."""
    client = AsyncGroqClient(
        api_key="gsk_test_mock_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "I am unable to answer this in JSON format. Here is unstructured text.",
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
async def test_groq_structured_generation_schema_mismatch_raises():
    """Verifies that JSON missing required fields or invalid types raises AIStructuredGenerationException."""
    client = AsyncGroqClient(
        api_key="gsk_test_mock_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    # Missing required 'score' field
                    "content": '{"verdict": "pass", "strengths": ["Good"]}',
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
async def test_groq_missing_api_key_raises_provider_unavailable():
    """Verifies that an unconfigured GROQ_API_KEY raises AIProviderUnavailableException."""
    client = AsyncGroqClient(
        api_key=None,
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    with pytest.raises(AIProviderUnavailableException) as exc_info:
        await client.generate_chat(messages=[{"role": "user", "content": "Hi"}])

    assert exc_info.value.status_code == 503
    assert "GROQ_API_KEY environment variable is not configured" in exc_info.value.message


@pytest.mark.asyncio
async def test_groq_unauthorized_401_raises_provider_unavailable():
    """Verifies that HTTP 401 from Groq raises AIProviderUnavailableException with clear guidance."""
    client = AsyncGroqClient(
        api_key="gsk_invalid_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    mock_response = httpx.Response(401, request=mock_request, text='{"error":{"message":"Invalid API Key"}}')

    mock_http_client = AsyncMock()
    mock_http_client.post.side_effect = httpx.HTTPStatusError(
        message="Client error '401 Unauthorized'",
        request=mock_request,
        response=mock_response,
    )

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(AIProviderUnavailableException) as exc_info:
            await client.generate_structured(
                prompt="Test prompt",
                schema=SampleEvaluationOutput,
            )
        assert exc_info.value.status_code == 503
        assert "authentication failed" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_groq_rate_limit_429_raises_provider_unavailable():
    """Verifies that HTTP 429 from Groq raises AIProviderUnavailableException."""
    client = AsyncGroqClient(
        api_key="gsk_test_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    mock_response = httpx.Response(429, request=mock_request, text='{"error":{"message":"Rate limit exceeded"}}')

    mock_http_client = AsyncMock()
    mock_http_client.post.side_effect = httpx.HTTPStatusError(
        message="Client error '429 Too Many Requests'",
        request=mock_request,
        response=mock_response,
    )

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(AIProviderUnavailableException) as exc_info:
            await client.generate_structured(
                prompt="Test prompt",
                schema=SampleEvaluationOutput,
            )
        assert exc_info.value.status_code == 503
        assert "rate limit" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_groq_connection_error_raises_ai_provider_unavailable():
    """Verifies that network connection failure raises AIProviderUnavailableException."""
    client = AsyncGroqClient(
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
async def test_groq_timeout_raises_ai_provider_unavailable():
    """Verifies that an inference timeout raises AIProviderUnavailableException."""
    client = AsyncGroqClient(
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
async def test_groq_check_health_healthy():
    """Verifies check_health reports available when API key is valid and model is in /models."""
    client = AsyncGroqClient(
        api_key="gsk_valid_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "object": "list",
        "data": [
            {"id": "llama-3.3-70b-versatile"},
            {"id": "llama-3.1-8b-instant"},
        ],
    }

    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = mock_resp

    with patch.object(client, "_get_client", return_value=mock_http_client):
        health = await client.check_health()
        assert health["status"] == "available"
        assert health["model_available"] is True
        assert "llama-3.3-70b-versatile" in health["available_models"]


@pytest.mark.asyncio
async def test_groq_check_health_missing_api_key():
    """Verifies check_health reports unavailable with helpful error when GROQ_API_KEY is unset."""
    client = AsyncGroqClient(
        api_key=None,
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    health = await client.check_health()
    assert health["status"] == "unavailable"
    assert health["model_available"] is False
    assert "GROQ_API_KEY environment variable is not configured" in health["error"]


@pytest.mark.asyncio
async def test_groq_check_health_401_unauthorized():
    """Verifies check_health reports unavailable when Groq API returns 401 Unauthorized."""
    client = AsyncGroqClient(
        api_key="gsk_bad_key",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"error":{"message":"Invalid API Key"}}'

    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = mock_resp

    with patch.object(client, "_get_client", return_value=mock_http_client):
        health = await client.check_health()
        assert health["status"] == "unavailable"
        assert health["model_available"] is False
        assert "401" in health["error"]
