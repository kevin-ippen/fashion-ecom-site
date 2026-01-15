"""
Image serving routes - Redirect to Databricks Files API
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from databricks.sdk import WorkspaceClient
from core.config import settings
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["images"])

# Use workspace client to get workspace host
w = WorkspaceClient()

# Get workspace host for constructing Files API URLs
WORKSPACE_HOST = settings.DATABRICKS_WORKSPACE_URL


@router.get("/{image_path:path}")
async def get_image(image_path: str):
    """
    Redirect to Databricks Files API for direct image access

    Pattern: https://{workspace-host}/ajax-api/2.0/fs/files{volume_path}

    This approach:
    - Avoids proxying large files through the app
    - Leverages browser's built-in auth (user's session)
    - Much faster than downloading and re-serving
    """
    try:
        # Handle different image_path formats
        # Note: FastAPI strips leading / from path parameters
        if image_path.startswith("Volumes/") or image_path.startswith("/Volumes/"):
            # Already a full volume path - ensure it starts with /
            volume_path = image_path if image_path.startswith("/") else f"/{image_path}"
        elif image_path.startswith("images/"):
            # Relative path with "images/" prefix - prepend volume base
            filename = image_path[7:]  # Remove "images/" prefix
            volume_path = f"/Volumes/main/fashion_demo/raw_data/images/{filename}"
        else:
            # Just a filename - prepend full volume path
            volume_path = f"/Volumes/main/fashion_demo/raw_data/images/{image_path}"
        
        # Construct Files API URL
        files_api_url = f"{WORKSPACE_HOST}/ajax-api/2.0/fs/files{volume_path}"
        
        logger.info(f"Redirecting to Files API: {files_api_url}")
        
        # Redirect to Files API
        return RedirectResponse(url=files_api_url, status_code=302)
        
    except Exception as e:
        logger.error(f"Error constructing Files API URL for {image_path}: {e}")
        raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")