from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    status: Literal["connected", "disconnected", "degraded"]
    dialect: Optional[str] = None
    driver: Optional[str] = None
    error: Optional[str] = None


class AIHealth(BaseModel):
    status: Literal["available", "unavailable"]
    base_url: str
    configured_model: str
    model_available: bool
    available_models: Optional[List[str]] = None
    error: Optional[str] = None


# Backward and forward compatible aliases
OllamaHealth = AIHealth
GroqHealth = AIHealth


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        description="Overall system status. 'healthy' if DB and AI provider (Groq) are fully functional, 'degraded' if AI is unavailable, 'unhealthy' if DB is down."
    )
    app: str = "Adaptive Interview Intelligence API"
    environment: str
    timestamp: datetime
    database: DatabaseHealth
    ollama: AIHealth = Field(
        description="AI provider health probe (retained for backward compatibility with existing clients and contracts)."
    )
    groq: Optional[AIHealth] = Field(
        default=None,
        description="Groq AI provider health probe."
    )
