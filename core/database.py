"""
Database connection and session management for Lakebase PostgreSQL
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import settings
import logging
import ssl

logger = logging.getLogger(__name__)

# Prepare SSL context for asyncpg (if SSL is required)
connect_args = {}
if settings.LAKEBASE_SSL_MODE != "disable":
    # Create SSL context - asyncpg requires ssl parameter, not sslmode
    ssl_context = ssl.create_default_context()
    if settings.LAKEBASE_SSL_MODE == "require":
        # Don't verify certificates (common for cloud databases with self-signed certs)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context

# Create async engine for Lakebase PostgreSQL
engine = create_async_engine(
    settings.lakebase_url,
    connect_args=connect_args,  # Pass SSL context for asyncpg
    pool_size=10,                # Adjust based on expected load
    max_overflow=20,             # Extra connections under load
    pool_pre_ping=True,          # Verify connections before use
    echo=settings.DEBUG,         # Log SQL queries in debug mode
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
