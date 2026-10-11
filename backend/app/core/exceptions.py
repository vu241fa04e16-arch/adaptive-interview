from typing import Any, Dict, Optional


class AppException(Exception):
    """Base class for all domain-specific application exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class AIProviderUnavailableException(AppException):
    """Raised when the local Ollama service is unreachable or encounters a network error/timeout."""

    def __init__(
        self,
        message: str = "Local AI service (Ollama) is unavailable or unresponsive.",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=503,
            error_code="AI_PROVIDER_UNAVAILABLE",
            details=details,
        )


class ModelNotAvailableException(AppException):
    """Raised when the requested Ollama model has not been pulled or is not loaded."""

    def __init__(
        self,
        model_name: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        msg = message or f"Requested model '{model_name}' is not found in the local Ollama library."
        err_details = details or {}
        err_details["requested_model"] = model_name
        super().__init__(
            message=msg,
            status_code=503,
            error_code="MODEL_NOT_AVAILABLE",
            details=err_details,
        )


class AIStructuredGenerationException(AppException):
    """Raised when Ollama output cannot be parsed or validated against the expected Pydantic schema."""

    def __init__(
        self,
        message: str = "Failed to parse structured JSON response from Ollama.",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=502,
            error_code="AI_STRUCTURED_GENERATION_FAILED",
            details=details,
        )


class DatabaseConnectionException(AppException):
    """Raised when the database connection cannot be established or health check fails."""

    def __init__(
        self,
        message: str = "Database connection could not be established.",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=503,
            error_code="DATABASE_CONNECTION_ERROR",
            details=details,
        )


class ResourceNotFoundException(AppException):
    """Raised when an entity (session, question, report) is not found."""

    def __init__(
        self,
        resource: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=f"{resource} with ID '{resource_id}' was not found.",
            status_code=404,
            error_code="RESOURCE_NOT_FOUND",
            details=details,
        )


class InvalidSessionStateException(AppException):
    """Raised when an operation is invalid for current session state."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=400,
            error_code="INVALID_SESSION_STATE",
            details=details,
        )


class InvalidFileException(AppException):
    """Raised when an uploaded file is invalid, empty, corrupt, or unsupported."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "INVALID_FILE",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code,
            details=details,
        )


class FileSizeLimitExceededException(AppException):
    """Raised when an uploaded file exceeds the maximum allowed size."""

    def __init__(
        self,
        max_size_mb: int,
        actual_size_bytes: int,
        details: Optional[Dict[str, Any]] = None,
    ):
        err_details = details or {}
        err_details["max_size_mb"] = max_size_mb
        err_details["actual_size_bytes"] = actual_size_bytes
        super().__init__(
            message=f"File exceeds maximum allowed size of {max_size_mb} MB.",
            status_code=413,
            error_code="FILE_SIZE_LIMIT_EXCEEDED",
            details=err_details,
        )


class ConflictException(AppException):
    """Raised when a resource state conflict occurs (e.g. duplicate active upload)."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=409,
            error_code="RESOURCE_CONFLICT",
            details=details,
        )


class TranscriptionException(AppException):
    """Raised when speech-to-text audio transcription encounters a failure."""

    def __init__(
        self,
        message: str = "Audio transcription failed.",
        status_code: int = 500,
        error_code: str = "TRANSCRIPTION_FAILED",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code,
            details=details,
        )

