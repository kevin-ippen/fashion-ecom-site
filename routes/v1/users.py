"""
User and persona API routes
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import json
import os
from models.schemas import User, UserProfile, ProductDetail
from repositories.lakebase import LakebaseRepository
from core.database import get_async_db
from core.config import settings

router = APIRouter(prefix="/users", tags=["users"])

# Get workspace host for constructing Files API URLs
WORKSPACE_HOST = settings.DATABRICKS_WORKSPACE_URL


def get_image_url(product_id) -> str:
    """
    Construct direct Files API URL for product image

    Args:
        product_id: Product ID (int, float, or string)
    """
    # Safe conversion: handles int, float, or string (including '34029.0')
    import logging
    logger = logging.getLogger(__name__)
    try:
        pid = int(float(product_id))
    except (ValueError, TypeError):
        logger.warning(f"Invalid product_id format: {product_id}, using as-is")
        pid = product_id

    return f"{WORKSPACE_HOST}/ajax-api/2.0/fs/files/Volumes/main/fashion_demo/raw_data/images/{pid}.jpg"


def load_personas():
    """Load persona data from JSON file"""
    personas_path = os.path.join(os.path.dirname(__file__), "../../data/personas.json")
    with open(personas_path, "r") as f:
        data = json.load(f)
    return data["personas"]


@router.get("", response_model=List[dict])
async def list_personas():
    """
    Get all available user personas for demo
    """
    personas = load_personas()
    return personas


@router.get("/{user_id}", response_model=dict)
async def get_persona(user_id: str):
    """
    Get a specific user persona by ID
    """
    personas = load_personas()
    persona = next((p for p in personas if p["user_id"] == user_id), None)

    if not persona:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    return persona


@router.get("/{user_id}/profile", response_model=UserProfile)
async def get_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get detailed user profile including purchase history
    """
    repo = LakebaseRepository(db)

    # Load persona data
    personas = load_personas()
    persona = next((p for p in personas if p["user_id"] == user_id), None)

    if not persona:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Get some random products as "purchase history"
    # Filter by user preferences to make it realistic
    filters = {}
    if persona.get("preferred_categories"):
        # Pick the first preferred category
        filters["master_category"] = persona["preferred_categories"][0]

    products_data = await repo.get_products(
        limit=8,
        filters=filters if filters else None
    )

    # Convert to ProductDetail
    purchase_history = []
    for p in products_data:
        product = ProductDetail(**p)
        # Use direct Files API URL
        product.image_url = get_image_url(product.product_id)
        purchase_history.append(product)

    # Build profile
    profile = UserProfile(
        user_id=persona["user_id"],
        segment=persona["segment"],
        avg_price_point=persona["avg_price_point"],
        preferred_categories=persona["preferred_categories"],
        color_prefs=persona["color_prefs"],
        price_range={
            "min": persona["min_price"],
            "max": persona["max_price"],
            "avg": persona["avg_price"]
        },
        num_interactions=persona["num_interactions"],
        purchase_history=purchase_history
    )

    return profile