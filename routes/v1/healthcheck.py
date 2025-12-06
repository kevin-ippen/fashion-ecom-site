"""
Health check endpoint
"""
from fastapi import APIRouter
from datetime import datetime, timezone
from core.config import settings

router = APIRouter(tags=["healthcheck"])


@router.get("/healthcheck")
async def healthcheck():
    """
    Health check endpoint for monitoring
    Required for Databricks Apps
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/config-check")
async def config_check():
    """
    Configuration check endpoint - helps diagnose authentication issues
    Shows which environment variables are set (without exposing values)
    """
    def mask_value(value: str) -> str:
        """Mask sensitive values, showing only first 8 chars"""
        if not value:
            return "❌ NOT SET"
        return f"✓ Set (starts with: {value[:8]}...)"

    return {
        "lakebase_config": {
            "host": settings.LAKEBASE_HOST,
            "port": settings.LAKEBASE_PORT,
            "database": settings.LAKEBASE_DATABASE,
            "user": settings.LAKEBASE_USER,
            "password_source": (
                "LAKEBASE_PASSWORD" if settings.LAKEBASE_PASSWORD
                else "DATABRICKS_TOKEN" if settings.DATABRICKS_TOKEN
                else "❌ NONE"
            ),
            "lakebase_password": mask_value(settings.LAKEBASE_PASSWORD or ""),
            "databricks_token": mask_value(settings.DATABRICKS_TOKEN or ""),
            "ssl_mode": settings.LAKEBASE_SSL_MODE,
        },
        "databricks_config": {
            "host": mask_value(settings.DATABRICKS_HOST or ""),
            "http_path": mask_value(settings.DATABRICKS_HTTP_PATH or ""),
        },
        "warnings": [
            w for w in [
                "⚠️  LAKEBASE_PASSWORD not set - using DATABRICKS_TOKEN" if not settings.LAKEBASE_PASSWORD else None,
                "⚠️  No authentication token available!" if not (settings.LAKEBASE_PASSWORD or settings.DATABRICKS_TOKEN) else None,
            ] if w
        ]
    }
