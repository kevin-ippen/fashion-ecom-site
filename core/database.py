"""
Database connection and session management for Lakebase PostgreSQL
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create async engine for Lakebase PostgreSQL
engine = create_async_engine(
    settings.lakebase_url,
    pool_size=10,           # Adjust based on expected load
    max_overflow=20,        # Extra connections under load
    pool_pre_ping=True,     # Verify connections before use
    echo=settings.DEBUG,    # Log SQL queries in debug mode
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Important for async operations
    autocommit=False,
    autoflush=False,
)


async def get_async_db():
    """
    Dependency for FastAPI route injection
    Yields an async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
