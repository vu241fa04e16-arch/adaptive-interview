import asyncio
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


class AsyncGroqClient:
    """Reusable asynchronous client for Groq's OpenAI-compatible API.

    Provides structured JSON generation validated by Pydantic, model health probing,
    and resilience against connection errors, rate limits, and timeouts.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        settings: Settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.base_url = (base_url or settings.GROQ_BASE_URL).rstrip("/")
        self.model = model or settings.GROQ_MODEL
        self.timeout_seconds = timeout_seconds or settings.GROQ_TIMEOUT_SECONDS
        self._client: Optional[httpx.AsyncClient] = None

    def _build_headers(self) -> Dict[str, str]:
        """Builds HTTP headers including Bearer authorization if api_key is present."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Returns or creates the underlying httpx AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout_seconds, connect=5.0),
                headers=self._build_headers(),
            )
        return self._client

    async def aclose(self) -> None:
        """Closes the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "AsyncGroqClient":
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()

    async def check_health(self) -> Dict[str, Any]:
        """Probes Groq OpenAI-compatible /models endpoint to verify API key and model availability."""
        if not self.api_key or not self.api_key.strip():
            return {
                "status": "unavailable",
                "base_url": self.base_url,
                "configured_model": self.model,
                "model_available": False,
                "error": "GROQ_API_KEY environment variable is not configured.",
            }

        try:
            client = await self._get_client()
            response = await client.get("/models", timeout=5.0)

            if response.status_code == 401:
                return {
                    "status": "unavailable",
                    "base_url": self.base_url,
                    "configured_model": self.model,
                    "model_available": False,
                    "error": "Groq API key authentication failed (HTTP 401 Unauthorized).",
                }

            if response.status_code != 200:
                return {
                    "status": "unavailable",
                    "base_url": self.base_url,
                    "configured_model": self.model,
                    "model_available": False,
                    "error": f"Groq API returned HTTP {response.status_code}: {response.text[:150]}",
                }

            data = response.json()
            # Groq returns {"object": "list", "data": [{"id": "llama-3.3-70b-versatile", ...}]}
            models_data = data.get("data", [])
            available_models = [m.get("id", "") for m in models_data if isinstance(m, dict)]

            model_exists = any(
                m == self.model
                or m.startswith(f"{self.model}:")
                or self.model.startswith(m)
                for m in available_models
            )

            # If models list was retrieved successfully, the Groq service is available
            return {
                "status": "available",
                "base_url": self.base_url,
                "configured_model": self.model,
                "model_available": model_exists or len(available_models) > 0,
                "available_models": available_models[:15] if available_models else [],
            }

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            return {
                "status": "unavailable",
                "base_url": self.base_url,
                "configured_model": self.model,
                "model_available": False,
                "error": f"Cannot connect to Groq API at {self.base_url}: {str(e)}",
            }
        except httpx.TimeoutException as e:
            return {
                "status": "unavailable",
                "base_url": self.base_url,
                "configured_model": self.model,
                "model_available": False,
                "error": f"Groq health probe timed out after 5s: {str(e)}",
            }
        except Exception as e:
            return {
                "status": "unavailable",
                "base_url": self.base_url,
                "configured_model": self.model,
                "model_available": False,
                "error": f"Unexpected Groq health probe error: {str(e)}",
            }

    async def list_models(self) -> List[str]:
        """Returns the list of active model IDs available on Groq."""
        if not self.api_key:
            raise AIProviderUnavailableException(
                message="GROQ_API_KEY environment variable is not configured.",
                details={"base_url": self.base_url},
            )

        try:
            client = await self._get_client()
            response = await client.get("/models")
            response.raise_for_status()
            data = response.json()
            return [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict)]
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise AIProviderUnavailableException(
                message=f"Cannot connect to Groq API at {self.base_url}.",
                details={"base_url": self.base_url, "error": str(e)},
            ) from e
        except httpx.TimeoutException as e:
            raise AIProviderUnavailableException(
                message=f"Groq request timed out after {self.timeout_seconds} seconds.",
                details={"timeout_seconds": self.timeout_seconds, "error": str(e)},
            ) from e
        except httpx.HTTPStatusError as e:
            raise AIProviderUnavailableException(
                message=f"Groq returned HTTP error {e.response.status_code}.",
                details={"status_code": e.response.status_code, "body": e.response.text},
            ) from e

    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        format: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Sends chat messages to Groq OpenAI-compatible Chat Completions API.

        Maps options (temperature, max_tokens, num_predict) to OpenAI-compatible payload.
        Raises AIProviderUnavailableException or ModelNotAvailableException on failure.
        """
        if not self.api_key or not self.api_key.strip():
            raise AIProviderUnavailableException(
                message="GROQ_API_KEY environment variable is not configured.",
                details={"base_url": self.base_url, "configured_model": self.model},
            )

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        # Handle JSON mode
        if format == "json":
            payload["response_format"] = {"type": "json_object"}

        # Map options
        if options:
            if "temperature" in options:
                payload["temperature"] = options["temperature"]
            if "max_tokens" in options:
                payload["max_tokens"] = options["max_tokens"]
            elif "num_predict" in options:
                payload["max_tokens"] = options["num_predict"]
            if "top_p" in options:
                payload["top_p"] = options["top_p"]
            if "seed" in options:
                payload["seed"] = options["seed"]

        # Ensure a sufficient completion token ceiling for JSON generation if unspecified
        if "max_tokens" not in payload:
            payload["max_tokens"] = 512

        retries = 2
        for attempt in range(retries + 1):
            try:
                client = await self._get_client()
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()
                result = response.json()
                choices = result.get("choices", [])
                if not choices:
                    raise AIStructuredGenerationException(
                        message="Groq returned empty choices in completion response.",
                        details={"raw_response": result},
                    )
                content = choices[0].get("message", {}).get("content", "")
                return content

            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                logger.error(f"Groq connection error at {self.base_url}: {e}")
                raise AIProviderUnavailableException(
                    message=f"Failed to connect to Groq API at {self.base_url}.",
                    details={"base_url": self.base_url, "configured_model": self.model, "error": str(e)},
                ) from e
            except httpx.TimeoutException as e:
                logger.error(f"Groq timeout after {self.timeout_seconds}s: {e}")
                raise AIProviderUnavailableException(
                    message=f"Groq inference timed out after {self.timeout_seconds}s.",
                    details={"timeout_seconds": self.timeout_seconds, "configured_model": self.model},
                ) from e
            except httpx.HTTPStatusError as e:
                logger.error(f"Groq HTTP error {e.response.status_code}: {e.response.text}")
                if e.response.status_code == 429 and attempt < retries:
                    retry_after = 3.0
                    if "retry-after" in e.response.headers:
                        try:
                            retry_after = float(e.response.headers["retry-after"])
                        except ValueError:
                            pass
                    logger.warning(f"Groq 429 rate limit reached. Retrying in {retry_after}s (attempt {attempt+1}/{retries})...")
                    await asyncio.sleep(min(retry_after, 6.0))
                    continue

                if e.response.status_code == 404:
                    raise ModelNotAvailableException(
                        model_name=self.model,
                        details={"base_url": self.base_url, "groq_response": e.response.text},
                    ) from e
                elif e.response.status_code == 401:
                    raise AIProviderUnavailableException(
                        message="Groq API authentication failed (HTTP 401 Unauthorized). Verify GROQ_API_KEY.",
                        details={"status_code": 401, "body": e.response.text},
                    ) from e
                elif e.response.status_code == 429:
                    raise AIProviderUnavailableException(
                        message="Groq API rate limit reached (HTTP 429).",
                        details={"status_code": 429, "body": e.response.text},
                    ) from e
                raise AIProviderUnavailableException(
                    message=f"Groq API returned HTTP {e.response.status_code}.",
                    details={"status_code": e.response.status_code, "body": e.response.text},
                ) from e

    @staticmethod
    def _salvage_truncated_json(text: str) -> Optional[Any]:
        """Attempts to repair slightly truncated JSON produced by LLM token cutoffs."""
        t = text.strip()
        if not (t.startswith("{") or t.startswith("[")):
            return None

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
        """Generates structured output validated against a Pydantic schema using Groq's JSON mode.

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

        user_content = prompt if "json" in prompt.lower() else f"{prompt}\n\nPlease respond with a valid JSON object."
        messages = [
            {"role": "system", "content": base_system},
            {"role": "user", "content": user_content},
        ]

        try:
            raw_response = await self.generate_chat(
                messages=messages,
                format="json",
                options=options,
            )
        except AIProviderUnavailableException as e:
            if e.details and "json_validate_failed" in str(e.details):
                logger.warning("Groq json_validate_failed encountered; retrying prompt without strict JSON mode constraint...")
                raw_response = await self.generate_chat(
                    messages=messages,
                    format=None,
                    options=options,
                )
            else:
                raise

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
            parsed_data = self._salvage_truncated_json(cleaned)
            if parsed_data is None:
                logger.error(f"Groq generated non-JSON content: {raw_response}")
                raise AIStructuredGenerationException(
                    message="Groq produced malformed JSON that could not be parsed.",
                    details={"raw_output": raw_response, "json_error": str(e)},
                ) from e
            logger.info("Successfully recovered truncated structured JSON from Groq.")

        # Check if model wrapped output in properties or wrapper key
        if isinstance(parsed_data, dict):
            schema_fields = set(schema.model_fields.keys())
            if "properties" in parsed_data and isinstance(parsed_data["properties"], dict):
                prop_keys = set(parsed_data["properties"].keys())
                if prop_keys.intersection(schema_fields):
                    logger.info("Unwrapping 'properties' dictionary from Groq output.")
                    parsed_data = parsed_data["properties"]
            elif len(parsed_data) == 1:
                first_key = next(iter(parsed_data))
                if first_key in ("evaluation", "data", "result", "response") and isinstance(parsed_data[first_key], dict):
                    logger.info(f"Unwrapping '{first_key}' dictionary from Groq output.")
                    parsed_data = parsed_data[first_key]

        # Validate with Pydantic
        try:
            validated = schema.model_validate(parsed_data)
            return validated
        except ValidationError as e:
            logger.error(f"Pydantic validation failure on Groq output: {e.errors()}")
            raise AIStructuredGenerationException(
                message=f"Groq output did not match schema '{schema.__name__}'.",
                details={
                    "validation_errors": e.errors(),
                    "raw_data": parsed_data,
                    "target_schema": schema.__name__,
                },
            ) from e


_global_groq_client: Optional[AsyncGroqClient] = None


def get_groq_client() -> AsyncGroqClient:
    """Dependency / accessor for singleton Groq client."""
    global _global_groq_client
    if _global_groq_client is None:
        _global_groq_client = AsyncGroqClient()
    return _global_groq_client
