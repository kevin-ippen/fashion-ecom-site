"""
Search API routes (text and image search)
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from models.schemas import SearchRequest, SearchResponse, ProductDetail
from repositories.lakebase import LakebaseRepository
from core.database import get_async_db
import numpy as np

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/text", response_model=SearchResponse)
async def search_by_text(
    request: SearchRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Search products by text query
    Currently using simple ILIKE search, will integrate with CLIP text embeddings
    """
    repo = LakebaseRepository(db)

    # Simple text search for now
    products_data = await repo.search_products_by_text(
        query=request.query,
        limit=request.limit
    )

    # Convert to ProductDetail
    products = []
    for p in products_data:
        product = ProductDetail(**p)
        product.image_url = f"/api/v1/images/{product.image_path}"
        # Add a mock similarity score for demo
        product.similarity_score = 0.85
        products.append(product)

    return SearchResponse(
        products=products,
        query=request.query,
        search_type="text",
        user_id=request.user_id
    )


@router.post("/image", response_model=SearchResponse)
async def search_by_image(
    image: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    limit: int = Form(20),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Search products by uploaded image
    Will integrate with CLIP image embeddings
    """
    repo = LakebaseRepository(db)

    # TODO: Implement CLIP image embedding generation
    # For now, return random products as placeholder

    products_data = await repo.get_products(limit=limit)

    # Convert to ProductDetail
    products = []
    for p in products_data:
        product = ProductDetail(**p)
        product.image_url = f"/api/v1/images/{product.image_path}"
        # Add a mock similarity score for demo
        product.similarity_score = np.random.uniform(0.7, 0.95)
        products.append(product)

    # Sort by similarity score
    products.sort(key=lambda x: x.similarity_score or 0, reverse=True)

    return SearchResponse(
        products=products,
        query=None,
        search_type="image",
        user_id=user_id
    )


@router.get("/recommendations/{user_id}", response_model=SearchResponse)
async def get_recommendations(
    user_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get personalized product recommendations for a user
    Uses user style features to find matching products
    """
    repo = LakebaseRepository(db)

    # Load persona to get preferences
    from routes.v1.users import load_personas

    personas = load_personas()
    persona = next((p for p in personas if p["user_id"] == user_id), None)

    if not persona:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Build filters based on user preferences
    filters = {}

    # Filter by price range with some flexibility
    min_price = persona["p25_price"] * 0.8  # 20% below 25th percentile
    max_price = persona["p75_price"] * 1.2  # 20% above 75th percentile
    filters["min_price"] = min_price
    filters["max_price"] = max_price

    # Get products
    products_data = await repo.get_products(
        limit=limit * 2,  # Get more to filter by colors
        filters=filters
    )

    # Filter by preferred colors
    preferred_colors = set(persona["color_prefs"])
    filtered_products = []

    for p in products_data:
        # Check if product color matches user preferences
        color_match = p["base_color"] in preferred_colors if p["base_color"] else False

        product = ProductDetail(**p)
        product.image_url = f"/api/v1/images/{product.image_path}"

        # Calculate personalization score
        score = 0.5  # Base score

        if color_match:
            score += 0.3

        # Price match score
        price_diff = abs(p["price"] - persona["avg_price"])
        price_range = persona["max_price"] - persona["min_price"]
        if price_range > 0:
            price_score = 1 - (price_diff / price_range)
            score += 0.2 * max(0, price_score)

        product.similarity_score = min(score, 1.0)

        # Add personalization reason
        reasons = []
        if color_match:
            reasons.append(f"Matches your preference for {p['base_color']} items")
        if persona["min_price"] <= p["price"] <= persona["max_price"]:
            reasons.append(f"Within your typical price range (${persona['min_price']:.0f}-${persona['max_price']:.0f})")

        if reasons:
            product.personalization_reason = " • ".join(reasons)

        filtered_products.append(product)

    # Sort by personalization score and limit
    filtered_products.sort(key=lambda x: x.similarity_score or 0, reverse=True)
    products = filtered_products[:limit]

    return SearchResponse(
        products=products,
        query=None,
        search_type="personalized",
        user_id=user_id
    )
