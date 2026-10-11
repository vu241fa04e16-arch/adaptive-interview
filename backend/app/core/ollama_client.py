import json
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.core.exceptions import (
    AIProviderUnavailableException,
    AIStructuredGenerationException,
    ModelNotAvailableException,
)
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)


class AsyncOllamaClient:
    """Reusable asynchronous client for local Ollama service.
    
    Provides structured JSON generation validated by Pydantic, health probing,
    and resilience against connection errors and timeouts.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        settings: Settings = get_settings()
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout_seconds = timeout_seconds or settings.OLLAMA_TIMEOUT_SECONDS
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Returns or creates the underlying httpx AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout_seconds, connect=5.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def aclose(self) -> None:
        """Closes the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "AsyncOllamaClient":
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()

    async def check_health(self) -> Dict[str, Any]:
        """Probes Ollama service tags to determine liveness and model availability."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags", timeout=5.0)
            if response.status_code != 200:
                return {
                    "status": "unavailable",
                    "base_url": self.base_url,
                    "configured_model": self.model,
                    "model_available": False,
                    "error": f"Ollama returned HTTP {response.status_code}",
                }

            data = response.json()
            available_models = [m.get("name", "") for m in data.get("models", [])]
            model_exists = any(
                m == self.model
                or m == f"{self.model}:latest"
                or m.startswith(f"{self.model}:")
                for m in available_models
            )

            return {
                "status": "available",
                "base_url": self.base_url,
                "configured_model": self.model,
                "model_available": model_exists,
                "available_models": available_models,
            }
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            return {
                "status": "unavailable",
                "base_url": self.base_url,
                "configured_model": self.model,
                "model_available": False,
                "error": f"Cannot connect to Ollama at {self.base_url}: {str(e)}",
            }
        except httpx.TimeoutException as e:
            return {
                "status": "unavailable",
                "base_url": self.base_url,
                "configured_model": self.model,
                "model_available": False,
                "error": f"Ollama health probe timed out after 5s: {str(e)}",
            }
        except Exception as e:
            return {
                "status": "unavailable",
                "base_url": self.base_url,
                "configured_model": self.model,
                "model_available": False,
                "error": f"Unexpected health check error: {str(e)}",
            }

    async def list_models(self) -> List[str]:
        """Returns the list of model names currently loaded in Ollama."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m.get("name", "") for m in data.get("models", [])]
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise AIProviderUnavailableException(
                message=f"Cannot connect to Ollama at {self.base_url}.",
                details={"base_url": self.base_url, "error": str(e)},
            ) from e
        except httpx.TimeoutException as e:
            raise AIProviderUnavailableException(
                message=f"Ollama request timed out after {self.timeout_seconds} seconds.",
                details={"timeout_seconds": self.timeout_seconds, "error": str(e)},
            ) from e
        except httpx.HTTPStatusError as e:
            raise AIProviderUnavailableException(
                message=f"Ollama returned HTTP error {e.response.status_code}.",
                details={"status_code": e.response.status_code, "body": e.response.text},
            ) from e

    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        format: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Sends chat messages to Ollama and returns the assistant's message content.
        
        Raises AIProviderUnavailableException on network/server errors.
        """
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if format:
            payload["format"] = format
        if options:
            payload["options"] = options

        try:
            client = await self._get_client()
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "")
            return content
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            logger.error(f"Ollama connection error at {self.base_url}: {e}")
            raise AIProviderUnavailableException(
                message=f"Failed to connect to local Ollama service at {self.base_url}.",
                details={"base_url": self.base_url, "configured_model": self.model, "error": str(e)},
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"Ollama timeout after {self.timeout_seconds}s: {e}")
            raise AIProviderUnavailableException(
                message=f"Ollama inference timed out after {self.timeout_seconds}s.",
                details={"timeout_seconds": self.timeout_seconds, "configured_model": self.model},
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error {e.response.status_code}: {e.response.text}")
            if e.response.status_code == 404:
                raise ModelNotAvailableException(
                    model_name=self.model,
                    details={"base_url": self.base_url, "ollama_response": e.response.text},
                ) from e
            raise AIProviderUnavailableException(
                message=f"Ollama returned HTTP {e.response.status_code}.",
                details={"status_code": e.response.status_code, "body": e.response.text},
            ) from e

    @staticmethod
    def _salvage_truncated_json(text: str) -> Optional[Any]:
        """Attempts to repair slightly truncated JSON produced by LLM token cutoffs."""
        t = text.strip()
        if not (t.startswith("{") or t.startswith("[")):
            return None

        # Try closing brackets at last delimiter or unclosed string
        for try_close_str in (False, True):
            for i in range(len(t) - 1, 0, -1):
                if not try_close_str and t[i] not in ("}", "]"):
                    continue
                candidate = t[: i + 1]
                if try_close_str:
                    candidate = candidate + '"'
                open_braces = candidate.count("{") - candidate.count("}")
                open_brackets = candidate.count("[") - candidate.count("]")
                if open_braces >= 0 and open_brackets >= 0:
                    candidate_balanced = candidate + ("]" * open_brackets) + ("}" * open_braces)
                    try:
                        return json.loads(candidate_balanced)
                    except json.JSONDecodeError:
                        continue
        return None

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Generates structured output validated against a Pydantic schema using Ollama's JSON mode.
        
        Guarantees that responses adhere to the provided schema; raises
        AIStructuredGenerationException if the model produces malformed or schema-violating data.
        """
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        base_system = (
            "You are a specialized AI system that ONLY outputs valid JSON adhering strictly "
            "to the following JSON Schema. Do NOT include markdown blocks, introductory words, "
            f"or postscript commentary.\n\nJSON SCHEMA:\n{schema_json}\n\n"
            "IMPORTANT: Output the concrete values directly at the root level of a single JSON object. "
            "Do NOT output the schema definitions or wrap your response inside a 'properties' object."
        )
        if system_prompt:
            base_system = f"{system_prompt}\n\n{base_system}"

        messages = [
            {"role": "system", "content": base_system},
            {"role": "user", "content": prompt},
        ]

        raw_response = await self.generate_chat(
            messages=messages,
            format="json",
            options=options,
        )

        # Parse JSON
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            parsed_data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Attempt light recovery for truncated JSON (e.g. LLM token cutoff)
            parsed_data = self._salvage_truncated_json(cleaned)
            if parsed_data is None:
                logger.error(f"Ollama generated non-JSON content: {raw_response}")
                raise AIStructuredGenerationException(
                    message="Ollama produced malformed JSON that could not be parsed.",
                    details={"raw_output": raw_response, "json_error": str(e)},
                ) from e
            logger.info("Successfully recovered truncated structured JSON from Ollama.")

        # Check if model wrapped output in properties or wrapper key
        if isinstance(parsed_data, dict):
            schema_fields = set(schema.model_fields.keys())
            if "properties" in parsed_data and isinstance(parsed_data["properties"], dict):
                prop_keys = set(parsed_data["properties"].keys())
                if prop_keys.intersection(schema_fields):
                    logger.info("Unwrapping 'properties' dictionary from Ollama output.")
                    parsed_data = parsed_data["properties"]
            elif len(parsed_data) == 1:
                first_key = next(iter(parsed_data))
                if first_key in ("evaluation", "data", "result", "response") and isinstance(parsed_data[first_key], dict):
                    logger.info(f"Unwrapping '{first_key}' dictionary from Ollama output.")
                    parsed_data = parsed_data[first_key]

        # Validate with Pydantic
        try:
            validated = schema.model_validate(parsed_data)
            return validated
        except ValidationError as e:
            logger.error(f"Pydantic validation failure on Ollama output: {e.errors()}")
            raise AIStructuredGenerationException(
                message=f"Ollama output did not match schema '{schema.__name__}'.",
                details={
                    "validation_errors": e.errors(),
                    "raw_data": parsed_data,
                    "target_schema": schema.__name__,
                },
            ) from e


_global_ollama_client: Optional[AsyncOllamaClient] = None


def get_ollama_client() -> AsyncOllamaClient:
    """Dependency / accessor for singleton Ollama client."""
    global _global_ollama_client
    if _global_ollama_client is None:
        _global_ollama_client = AsyncOllamaClient()
    return _global_ollama_client
