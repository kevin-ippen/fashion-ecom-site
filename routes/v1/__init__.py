"""V1 API routes."""
from fastapi import APIRouter

from .products import router as products_router
from .users import router as users_router
from .search import router as search_router
from .images import router as images_router

router = APIRouter()

# Include endpoint-specific routers (without prefix since they define their own)
router.include_router(products_router)
router.include_router(users_router)
router.include_router(search_router)
router.include_router(images_router)
