from functools import lru_cache
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core Application Settings
    PROJECT_NAME: str = "Adaptive Interview Intelligence"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_PREFIX: str = "/api"

    # Database Configuration (PostgreSQL 18)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:root@localhost:5432/adaptive_interview"

    # Ollama Local Service Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    OLLAMA_TIMEOUT_SECONDS: float = 120.0

    # Resume Upload Configuration
    MAX_RESUME_SIZE_MB: int = 10
    UPLOAD_DIR: str = "uploads"
    ALLOWED_RESUME_EXTENSIONS: List[str] = [".pdf", ".docx"]

    # Cross-Origin Resource Sharing (CORS)
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance."""
    return Settings()
