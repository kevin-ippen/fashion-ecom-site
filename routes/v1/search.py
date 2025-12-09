"""
Search API routes - FIXED for CLIP image-only endpoint
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from models.schemas import SearchRequest, SearchResponse, ProductDetail
from repositories.lakebase import LakebaseRepository
from core.database import get_async_db
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# Get workspace host for constructing Files API URLs
WORKSPACE_HOST = os.getenv("DATABRICKS_HOST", "")
if WORKSPACE_HOST and not WORKSPACE_HOST.startswith("http"):
    WORKSPACE_HOST = f"https://{WORKSPACE_HOST}"


def get_image_url(product_id: int) -> str:
    """
    Construct direct Files API URL for product image
    """
    return f"{WORKSPACE_HOST}/ajax-api/2.0/fs/files/Volumes/main/fashion_demo/raw_data/images/{product_id}.jpg"


@router.post("/text", response_model=SearchResponse)
async def search_by_text(
    request: SearchRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Text search using basic keyword matching
    Note: CLIP endpoint only supports images, not text
    """
    repo = LakebaseRepository(db)
    
    logger.info(f"Text search request: '{request.query}' (limit={request.limit})")
    
    # Use basic text search (CLIP endpoint doesn't support text)
    products_data = await repo.search_products_by_text(
        query=request.query,
        limit=request.limit
    )
    
    # Convert to ProductDetail
    products = []
    for p in products_data:
        product = ProductDetail(**p)
        product.image_url = get_image_url(int(product.product_id))
        # Mock similarity score for basic search
        product.similarity_score = 0.75
        products.append(product)
    
    logger.info(f"Text search returned {len(products)} results")
    
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
    Visual search using CLIP image embeddings + Vector Search
    """
    try:
        from services.clip_service import clip_service
        from services.vector_search_service import vector_search_service
        
        logger.info(f"Image search request: {image.filename} (limit={limit})")
        
        # Read uploaded image
        image_bytes = await image.read()
        
        logger.info(f"Read {len(image_bytes)} bytes from uploaded image")
        
        # Generate image embedding using CLIP
        image_embedding = await clip_service.get_image_embedding(image_bytes)
        
        logger.info(f"Generated embedding with shape: {image_embedding.shape}")
        
        # Search for similar products using Vector Search
        products_data = await vector_search_service.similarity_search(
            query_vector=image_embedding,
            num_results=limit
        )
        
        # Convert to ProductDetail
        products = []
        for p in products_data:
            product = ProductDetail(**p)
            product.image_url = get_image_url(int(product.product_id))
            # Similarity score comes from Vector Search
            product.similarity_score = p.get("score", 0.85)
            products.append(product)
        
        logger.info(f"✅ Image search returned {len(products)} results")
        
        return SearchResponse(
            products=products,
            query=None,
            search_type="image",
            user_id=user_id
        )
        
    except Exception as e:
        logger.error(f"Image search error: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Image search failed: {str(e)}")


@router.get("/recommendations/{user_id}", response_model=SearchResponse)
async def get_recommendations(
    user_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Hybrid personalized recommendations:
    - Try Vector Search with user embeddings first
    - Fallback to rule-based filtering
    """
    repo = LakebaseRepository(db)

    # Load persona to get preferences
    from routes.v1.users import load_personas

    personas = load_personas()
    persona = next((p for p in personas if p["user_id"] == user_id), None)

    if not persona:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    logger.info(f"Getting recommendations for user {user_id} - {persona.get('name', 'Unknown')}")
    logger.info(f"Persona preferences: categories={persona.get('preferred_categories')}, colors={persona.get('color_prefs')}")

    try:
        # Try to get user embedding from user_style_features table
        user_features = await repo.get_user_style_features(user_id)
        
        if user_features and user_features.get("user_embedding"):
            # Use Vector Search with user embedding
            from services.vector_search_service import vector_search_service
            
            user_embedding = np.array(user_features["user_embedding"], dtype=np.float32)
            
            # Build price filters for Vector Search
            min_price = persona["p25_price"] * 0.8
            max_price = persona["p75_price"] * 1.2
            
            # Vector Search with filters
            products_data = await vector_search_service.similarity_search(
                query_vector=user_embedding,
                num_results=limit * 2,  # Get more for additional filtering
                filters={"price >= ": min_price, "price <= ": max_price}
            )
            
            logger.info(f"Vector Search returned {len(products_data)} products")
            
        else:
            # Fallback to rule-based if no user embedding
            logger.warning(f"No user embedding found for {user_id}, using rule-based recommendations")
            raise Exception("No user embedding - use fallback")
            
    except Exception as e:
        logger.warning(f"Vector Search failed, using rule-based fallback: {e}")
        
        # Fallback: Rule-based recommendations
        filters = {}
        filters["min_price"] = persona["p25_price"] * 0.8
        filters["max_price"] = persona["p75_price"] * 1.2
        
        # ✅ ADD: Filter by preferred master_category
        if persona.get("preferred_categories"):
            filters["master_category"] = persona["preferred_categories"][0]
            logger.info(f"Filtering by category: {filters['master_category']}")
        
        products_data = await repo.get_products(
            limit=limit * 3,
            filters=filters
        )

    # Normalize preferred colors to Title Case for matching
    preferred_colors = set(c.title() for c in persona["color_prefs"])
    logger.info(f"Normalized color preferences: {preferred_colors}")
    
    filtered_products = []

    for p in products_data:
        # Normalize product color to Title Case
        product_color = (p["base_color"] or "").title()
        color_match = product_color in preferred_colors
        
        # Check category match
        category_match = p.get("master_category") in persona.get("preferred_categories", [])

        product = ProductDetail(**p)
        product.image_url = get_image_url(int(product.product_id))

        # Calculate hybrid score
        # If from Vector Search, use that score (60%) + rules (40%)
        # If rule-based only, use rules (100%)
        vector_score = p.get("score", 0.5)  # From Vector Search or default
        rule_score = 0.0
        
        # Category match bonus
        if category_match:
            rule_score += 0.3
        
        # Color match bonus
        if color_match:
            rule_score += 0.4
        
        # Price match bonus
        price_diff = abs(p["price"] - persona["avg_price"])
        price_range = persona["max_price"] - persona["min_price"]
        if price_range > 0:
            price_score = 1 - (price_diff / price_range)
            rule_score += 0.3 * max(0, price_score)
        
        # Hybrid score: 60% vector + 40% rules
        if "score" in p:  # Has vector similarity
            product.similarity_score = 0.6 * vector_score + 0.4 * rule_score
        else:  # Rule-based only
            product.similarity_score = rule_score

        # Add personalization reasons
        reasons = []
        if category_match:
            reasons.append(f"Matches your interest in {p['master_category']}")
        if color_match:
            reasons.append(f"Matches your preference for {product_color} items")
        if persona["min_price"] <= p["price"] <= persona["max_price"]:
            reasons.append(f"Within your typical price range (${persona['min_price']:.0f}-${persona['max_price']:.0f})")
        if "score" in p and p["score"] > 0.8:
            reasons.append("Similar to items you've liked before")

        if reasons:
            product.personalization_reason = " • ".join(reasons)

        filtered_products.append(product)

    # Sort by hybrid score and limit
    filtered_products.sort(key=lambda x: x.similarity_score or 0, reverse=True)
    products = filtered_products[:limit]
    
    logger.info(f"Returning {len(products)} personalized recommendations (avg score: {np.mean([p.similarity_score for p in products]):.2f})")

    return SearchResponse(
        products=products,
        query=None,
        search_type="personalized",
        user_id=user_id
    )