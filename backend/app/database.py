from typing import Any, AsyncGenerator, Dict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings
from app.core.logging import logger

settings = get_settings()

# Asynchronous SQLAlchemy Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session with automatic cleanup."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> Dict[str, Any]:
    """Executes a ping query to verify database connectivity and readiness."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            scalar = result.scalar()
            if scalar == 1:
                return {
                    "status": "connected",
                    "dialect": engine.dialect.name,
                    "driver": engine.dialect.driver,
                }
            return {
                "status": "degraded",
                "dialect": engine.dialect.name,
                "detail": f"Unexpected health check scalar: {scalar}",
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "disconnected",
            "dialect": engine.dialect.name,
            "error": str(e),
        }
