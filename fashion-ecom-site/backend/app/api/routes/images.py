"""
Image serving routes
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
from app.core.config import settings

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/{image_path:path}")
async def serve_image(image_path: str):
    """
    Serve product images from UC volume
    """
    # Construct full path
    full_path = os.path.join(settings.IMAGES_VOLUME_PATH, image_path)

    # Check if file exists
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Image not found")

    # Return image file
    return FileResponse(full_path)
