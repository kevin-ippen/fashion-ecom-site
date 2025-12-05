"""
Health check endpoint
"""
from fastapi import APIRouter
from datetime import datetime, timezone

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
