from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.core.ollama_client import get_ollama_client
from app.database import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup warmup and graceful shutdown."""
    logger.info(f"Starting {settings.PROJECT_NAME} in [{settings.ENVIRONMENT}] mode...")
    logger.info(f"Ollama configured at: {settings.OLLAMA_BASE_URL} (Model: {settings.OLLAMA_MODEL})")
    logger.info(f"Database target: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'configured'}")

    # Warmup / probe Ollama asynchronously
    ollama_client = get_ollama_client()
    try:
        health = await ollama_client.check_health()
        if health.get("status") == "available":
            model_status = "READY" if health.get("model_available") else "MODEL NOT FOUND"
            logger.info(f"Ollama connection verified. Configured model status: {model_status}")
        else:
            logger.warning(f"Ollama connection warning: {health.get('error')}")
    except Exception as e:
        logger.warning(f"Ollama initial health check encountered an error: {e}")

    yield

    # Graceful shutdown
    logger.info("Initiating graceful shutdown...")
    await ollama_client.aclose()
    await engine.dispose()
    logger.info("Application resources successfully disposed.")


def create_application() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=(
            "Adaptive Interview Intelligence Backend API. "
            "Features deterministic adaptive interview engine, real-time rubric-based evaluation, "
            "local Ollama AI inference, and telemetry integrity analytics."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS Middleware configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Centralized Exception Handlers
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.error(f"Domain exception on {request.method} {request.url.path}: {exc.message} ({exc.error_code})")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request body or query parameter validation failed.",
                "details": {"errors": jsonable_encoder(exc.errors())},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_EXCEPTION",
                "message": str(exc.detail),
                "detail": str(exc.detail),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled server error on {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    # Mount API Routes
    app.include_router(router)

    return app


app = create_application()
