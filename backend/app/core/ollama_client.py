"""Backwards compatibility adapter mapping Ollama client calls to AsyncGroqClient."""

from app.core.groq_client import (
    AsyncGroqClient,
    AsyncGroqClient as AsyncOllamaClient,
    get_groq_client,
    get_groq_client as get_ollama_client,
)

__all__ = [
    "AsyncGroqClient",
    "AsyncOllamaClient",
    "get_groq_client",
    "get_ollama_client",
]
