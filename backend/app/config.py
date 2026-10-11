from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_PATHS = (
    str(_BACKEND_DIR / ".env"),
    str(_BACKEND_DIR.parent / ".env"),
    ".env",
)


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=_ENV_PATHS,
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
    OLLAMA_MODEL: str = "llama3.2:1b"
    OLLAMA_TIMEOUT_SECONDS: float = 180.0

    # Resume Upload Configuration
    MAX_RESUME_SIZE_MB: int = 10
    UPLOAD_DIR: str = "uploads"
    ALLOWED_RESUME_EXTENSIONS: List[str] = [".pdf", ".docx"]

    # Audio Speech-to-Text (STT) Configuration
    WHISPER_MODEL: str = "tiny.en"
    WHISPER_MODEL_SIZE: Optional[str] = None
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    MAX_AUDIO_SIZE_MB: int = 25
    ALLOWED_AUDIO_EXTENSIONS: List[str] = [
        ".wav",
        ".mp3",
        ".m4a",
        ".webm",
        ".ogg",
        ".flac",
        ".aac",
        ".mp4",
    ]

    @property
    def effective_whisper_model(self) -> str:
        return self.WHISPER_MODEL_SIZE or self.WHISPER_MODEL or "tiny.en"

    # Cross-Origin Resource Sharing (CORS)
  
    # Cross-Origin Resource Sharing (CORS)
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5176",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5176",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            return [
                origin.strip()
                for origin in value.split(",")
                if origin.strip()
            ]
        return value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance."""
    return Settings()
