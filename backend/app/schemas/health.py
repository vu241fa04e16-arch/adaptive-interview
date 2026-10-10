from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    status: Literal["connected", "disconnected", "degraded"]
    dialect: Optional[str] = None
    driver: Optional[str] = None
    error: Optional[str] = None


class OllamaHealth(BaseModel):
    status: Literal["available", "unavailable"]
    base_url: str
    configured_model: str
    model_available: bool
    available_models: Optional[List[str]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        description="Overall system status. 'healthy' if DB and Ollama are fully functional, 'degraded' if Ollama is unavailable, 'unhealthy' if DB is down."
    )
    app: str = "Adaptive Interview Intelligence API"
    environment: str
    timestamp: datetime
    database: DatabaseHealth
    ollama: OllamaHealth
