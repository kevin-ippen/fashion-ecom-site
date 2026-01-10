"""
User and persona API routes - now fetches real users from database
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from models.schemas import User, UserProfile, ProductDetail
from repositories.lakebase import LakebaseRepository
from core.database import get_async_db
from core.config import settings

router = APIRouter(prefix="/users", tags=["users"])

# Get workspace host for constructing Files API URLs
WORKSPACE_HOST = settings.DATABRICKS_WORKSPACE_URL

# Curated personas with rich data and complete embeddings
# These users have the most complete taste profiles and shopping history
# Updated to 5 high-quality personas with properly aligned embeddings
CURATED_PERSONA_IDS = {
    "luxury": "user_luxury_001",
    "urban_casual": "user_casual_002",
    "athletic": "user_athletic_003",
    "budget_savvy": "user_budget_004",
    "professional": "user_professional_005"
}


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


def format_persona(user_data: dict) -> dict:
    """
    Transform database user record into persona format expected by frontend

    Database columns (fashion_sota.users schema):
    - user_id: str
    - style_profile: str (e.g., "budget_conscious", "luxury_seeker")
    - preferred_categories: array<string>
    - color_prefs: map<string,double> (need to extract keys)
    - brand_prefs: map<string,double> (need to extract keys)
    - min_price, max_price, avg_price, p25_price, p75_price: float
    - num_interactions: bigint
    - taste_embedding: array<double> (512-dim)
    """
    # Generate a display name from the style_profile
    style_profile = user_data.get("style_profile", "Shopper")
    segment_names = {
        # Current 5 personas
        "luxury": "Luxury Fashion Enthusiast",
        "urban_casual": "Urban Casual Style",
        "athletic": "Athletic Lifestyle",
        "budget_savvy": "Budget-Conscious Shopper",
        "professional": "Business Professional",
        # Legacy mappings (for backward compatibility)
        "budget": "Budget-Conscious Shopper",
        "casual": "Casual Style Lover",
        "formal": "Business Professional",
        "minimalist": "Minimalist Style Enthusiast",
        "trendy": "Trendsetter",
        "vintage": "Vintage Style Enthusiast",
        "budget_conscious": "Budget-Conscious Shopper",
        "luxury_seeker": "Luxury Fashion Enthusiast",
        "trendsetter": "Trendsetter",
        "vintage_lover": "Vintage Style Enthusiast",
        "athleisure": "Athletic Lifestyle"
    }
    name = segment_names.get(style_profile.lower() if style_profile else "", f"{style_profile.title() if style_profile else 'Fashion'} Shopper")

    # Generate a description from the user's preferences
    preferred_cats = user_data.get("preferred_categories", [])
    avg_price = user_data.get("avg_price") or 0  # Handle NULL from database

    if preferred_cats and len(preferred_cats) > 0:
        cats_str = " and ".join(preferred_cats[:2])
        description = f"Prefers {cats_str} with an average spend of ${avg_price:.2f}"
    else:
        description = f"Fashion enthusiast with an average spend of ${avg_price:.2f}"

    # Extract color preferences from map (get keys where value > threshold)
    color_prefs_map = user_data.get("color_prefs", {})
    if isinstance(color_prefs_map, dict):
        # Get top colors sorted by preference score
        color_prefs = sorted(color_prefs_map.keys(), key=lambda k: color_prefs_map[k], reverse=True)[:5]
    else:
        color_prefs = []

    # Extract brand preferences from map
    brand_prefs_map = user_data.get("brand_prefs", {})
    if isinstance(brand_prefs_map, dict):
        brand_prefs = sorted(brand_prefs_map.keys(), key=lambda k: brand_prefs_map[k], reverse=True)[:5]
    else:
        brand_prefs = []

    return {
        "user_id": user_data.get("user_id"),
        "name": name,
        "description": description,
        "segment": style_profile or "shopper",  # Use style_profile as segment
        "avg_price_point": avg_price,
        "preferred_categories": preferred_cats,
        "color_prefs": color_prefs,
        "brand_prefs": brand_prefs,
        "min_price": user_data.get("min_price") or 0,  # Handle NULL
        "max_price": user_data.get("max_price") or 0,  # Handle NULL
        "avg_price": avg_price,
        "p25_price": user_data.get("p25_price") or 0,  # Handle NULL
        "p75_price": user_data.get("p75_price") or 0,  # Handle NULL
        "num_interactions": user_data.get("num_interactions") or 0,  # Handle NULL
        "purchase_history_ids": [],  # Not in schema, would need separate table
        "style_tags": []  # Could derive from style_profile if needed
    }


@router.get("", response_model=List[dict])
async def list_personas(
    curated: bool = True,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get user personas from database

    Args:
        curated: If True, return only curated personas with rich embeddings (default)
                 If False, return all users (for admin/testing)

    Returns a list of real users with their style preferences and shopping behavior.
    """
    repo = LakebaseRepository(db)

    if curated:
        # Get only curated personas - one per style profile
        personas = []
        for style_profile, user_id in CURATED_PERSONA_IDS.items():
            user = await repo.get_user_by_id(user_id)
            if user:
                personas.append(format_persona(user))

        # Sort by style profile for consistent ordering
        personas.sort(key=lambda p: p["segment"])
    else:
        # Get all users (for admin/testing)
        users = await repo.get_users()
        personas = [format_persona(user) for user in users[:20]]  # Limit to 20

    return personas


@router.get("/{user_id}", response_model=dict)
async def get_persona(
    user_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get a specific user persona by ID from database
    """
    repo = LakebaseRepository(db)

    # Get user from database
    user = await repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Format as persona
    persona = format_persona(user)

    return persona


@router.get("/{user_id}/profile", response_model=UserProfile)
async def get_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get detailed user profile including purchase history from database
    """
    repo = LakebaseRepository(db)

    # Get user from database
    user = await repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Get some random products as "purchase history"
    # Filter by user preferences to make it realistic
    filters = {}
    preferred_cats = user.get("preferred_categories", [])
    if preferred_cats and len(preferred_cats) > 0:
        # Pick the first preferred category
        filters["master_category"] = preferred_cats[0]

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

    # Convert color_prefs from map to list (database stores as map<string,double>)
    color_prefs_map = user.get("color_prefs", {})
    if isinstance(color_prefs_map, dict):
        color_prefs = sorted(color_prefs_map.keys(), key=lambda k: color_prefs_map[k], reverse=True)[:5]
    else:
        color_prefs = []

    # Build profile
    profile = UserProfile(
        user_id=user["user_id"],
        segment=user.get("segment", "Shopper"),
        avg_price_point=user.get("avg_price_point", user.get("avg_price", 0)),
        preferred_categories=user.get("preferred_categories", []),
        color_prefs=color_prefs,
        price_range={
            "min": user.get("min_price", 0),
            "max": user.get("max_price", 0),
            "avg": user.get("avg_price", user.get("avg_price_point", 0))
        },
        num_interactions=user.get("num_interactions", 0),
        purchase_history=purchase_history
    )

    return profile