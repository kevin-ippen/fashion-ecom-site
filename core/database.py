"""
Database connection and session management for Lakebase PostgreSQL
With lazy initialization to support OAuth token generation
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import settings
import logging
import ssl
from typing import Optional

logger = logging.getLogger(__name__)

# Global variables for lazy initialization
_engine: Optional[create_async_engine] = None
_session_factory: Optional[async_sessionmaker] = None

def get_engine():
    """Get or create the database engine (lazy initialization)"""
    global _engine
    if _engine is None:
        logger.info("🔄 Creating database engine (lazy initialization)")
        
        # Prepare SSL context for asyncpg
        connect_args = {}
        if settings.LAKEBASE_SSL_MODE != "disable":
            ssl_context = ssl.create_default_context()
            if settings.LAKEBASE_SSL_MODE == "require":
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_context
        
        # Create engine with current lakebase_url (includes OAuth logic)
        # This is called at REQUEST TIME, not IMPORT TIME
        _engine = create_async_engine(
            settings.lakebase_url,  # This will try OAuth first!
            connect_args=connect_args,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=settings.DEBUG,
        )
        logger.info(f"✅ Database engine created with OAuth support")
    
    return _engine

def get_session_factory():
    """Get or create the session factory (lazy initialization)"""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory

async def get_async_db():
    """
    Dependency for FastAPI route injection
    Yields an async database session
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

# For compatibility with existing shutdown code in app.py
class _EngineProxy:
    """Proxy to maintain compatibility with app.py shutdown code"""
    
    async def dispose(self):
        """Dispose of the engine if it exists"""
        global _engine
        if _engine:
            await _engine.dispose()
            _engine = None
            logger.info("🗑️ Database engine disposed")

# Create proxy instance for app.py to use
engine = _EngineProxy()