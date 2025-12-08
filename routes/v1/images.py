"""
Image serving routes - Proxy to UC Volumes via Databricks Files API
"""
from fastapi import APIRouter, HTTPException, Response
from databricks.sdk import WorkspaceClient
import mimetypes
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["images"])

# Use workspace client with app's built-in service principal auth
w = WorkspaceClient()


@router.get("/{image_path:path}")
async def get_image(image_path: str):
    """
    Serve product images from Unity Catalog volume via Files API

    Uses the Databricks Files REST API to read bytes from a volume path,
    then returns them as an image response.

    Example paths:
    - /Volumes/main/fashion_demo/raw_data/images/12345.jpg
    - images/12345.jpg (auto-prepends volume path)
    - 12345.jpg (auto-prepends volume path)
    """
    try:
        # If image_path doesn't start with /Volumes, prepend the standard volume path
        if not image_path.startswith("/Volumes"):
            # Strip leading "images/" if present (for backward compatibility)
            if image_path.startswith("images/"):
                image_path = image_path[7:]

            volume_path = f"/Volumes/main/fashion_demo/raw_data/images/{image_path}"
        else:
            volume_path = image_path

        logger.info(f"Fetching image from volume: {volume_path}")

        # Download file from UC Volume using Files API
        # GET https://<workspace-host>/ajax-api/2.0/fs/files/Volumes/<catalog>/<schema>/<volume>/<path>
        # Example: https://adb-984752964297111.11.azuredatabricks.net/ajax-api/2.0/fs/files/Volumes/main/fashion_demo/raw_data/images/10004.jpg
        download = w.files.download(volume_path)
        content = download.contents.read()

        # Determine MIME type from file extension
        mime_type, _ = mimetypes.guess_type(volume_path)

        return Response(
            content=content,
            media_type=mime_type or "application/octet-stream",
            headers={
                "Cache-Control": "private, max-age=300"  # Cache for 5 minutes
            }
        )

    except Exception as e:
        logger.error(f"Error fetching image from {volume_path}: {e}")
        raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")
