"""
Search API routes with CLIP + Vector Search integration
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from models.schemas import SearchRequest, SearchResponse, ProductDetail
from repositories.lakebase import LakebaseRepository
from core.database import get_async_db
from core.config import settings
import numpy as np
import json
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# Get workspace host for constructing Files API URLs
WORKSPACE_HOST = settings.DATABRICKS_WORKSPACE_URL


def get_image_url(product_id) -> str:
    """
    Construct direct Files API URL for product image

    Args:
        product_id: Product ID (int, float, or string)

    Returns:
        Image URL string
    """
    # Safe conversion: handles int, float, or string (including '34029.0')
    try:
        # Convert to float first (handles '34029.0'), then to int
        pid = int(float(product_id))
    except (ValueError, TypeError):
        logger.warning(f"Invalid product_id format: {product_id}, using as-is")
        pid = product_id

    return f"{WORKSPACE_HOST}/ajax-api/2.0/fs/files/Volumes/main/fashion_demo/raw_data/images/{pid}.jpg"


@router.post("/text", response_model=SearchResponse)
async def search_by_text(
    request: SearchRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Semantic text search using CLIP text embeddings + hybrid vector search
    """
    try:
        from services.clip_service import clip_service
        from services.vector_search_service import vector_search_service

        logger.info(f"Text search request: '{request.query}' (limit={request.limit})")

        # Generate text embedding using CLIP
        text_embedding = await clip_service.get_text_embedding(request.query)
        logger.info(f"Generated text embedding with shape: {text_embedding.shape}")

        # Search hybrid index for best semantic results
        products_data = await vector_search_service.search_hybrid(
            query_vector=text_embedding,
            num_results=request.limit
        )

        # Convert to ProductDetail
        products = []
        for p in products_data:
            product = ProductDetail(**p)
            # Pass product_id directly - get_image_url handles conversion
            product.image_url = get_image_url(product.product_id)
            # Similarity score comes from Vector Search
            product.similarity_score = p.get("score", 0.85)
            products.append(product)

        logger.info(f"✅ Semantic text search returned {len(products)} results")

        return SearchResponse(
            products=products,
            query=request.query,
            search_type="text",
            user_id=request.user_id
        )

    except Exception as e:
        # Classify error type for better debugging
        error_type = type(e).__name__
        error_msg = str(e)

        if "timeout" in error_msg.lower() or "TimeoutError" in error_type:
            logger.error(f"⏱️ CLIP Model Serving timeout: {error_msg}")
            raise HTTPException(status_code=504, detail=f"CLIP endpoint timeout (cold start): {error_msg}")
        elif "vector" in error_msg.lower() or "index" in error_msg.lower():
            logger.error(f"🔍 Vector Search error: {error_type}: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Vector Search failed: {error_msg}")
        else:
            logger.error(f"❌ Text search error: {error_type}: {error_msg}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Text search failed: {error_msg}")


@router.post("/image", response_model=SearchResponse)
async def search_by_image(
    image: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    limit: int = Form(20),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Visual search using CLIP image embeddings + image vector search index
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
        logger.info(f"Generated image embedding with shape: {image_embedding.shape}")

        # Search image index for visual similarity
        products_data = await vector_search_service.search_image(
            query_vector=image_embedding,
            num_results=limit
        )

        # Convert to ProductDetail
        products = []
        for p in products_data:
            product = ProductDetail(**p)
            # Pass product_id directly - get_image_url handles conversion
            product.image_url = get_image_url(product.product_id)
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
    restrict_category: bool = False,  # Changed to False - too restrictive
    restrict_price: bool = False,      # Changed to False - let vector search decide
    restrict_color: bool = False,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Hybrid personalized recommendations using user embeddings + flexible filters

    Args:
        user_id: User identifier
        limit: Maximum number of results
        restrict_category: Filter by user's preferred categories
        restrict_price: Filter by user's typical price range
        restrict_color: Filter by user's preferred colors
    """
    repo = LakebaseRepository(db)

    # Get user from database
    user = await repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Format as persona for backwards compatibility
    from routes.v1.users import format_persona
    persona = format_persona(user)

    logger.info(f"Getting recommendations for user {user_id} - {persona.get('name', 'Unknown')}")
    logger.info(f"Persona preferences: categories={persona.get('preferred_categories')}, colors={persona.get('color_prefs')}")
    logger.info(f"Filter settings: category={restrict_category}, price={restrict_price}, color={restrict_color}")

    # Import persona mappings to determine style (define outside try block for scoping)
    from routes.v1.users import CURATED_PERSONA_IDS

    # Find persona style for this user_id
    persona_style = None
    for style, pid in CURATED_PERSONA_IDS.items():
        if pid == user_id:
            persona_style = style
            break

    # If not a curated persona, use style_profile from database
    if not persona_style:
        persona_style = user.get("style_profile", "").lower()

    logger.info(f"User {user_id} has persona style: {persona_style}")

    try:
        # INTELLIGENT ML-POWERED RECOMMENDATIONS
        logger.info(f"🤖 Intelligent recommendations for user {user_id} ({persona_style} persona)")

        # Get user embedding from user_style_features table
        user_features = await repo.get_user_style_features(user_id)

        if not user_features or not user_features.get("taste_embedding"):
            logger.warning(f"No taste_embedding found for {user_id}, falling back to category-balanced sampling")
            raise Exception("No user embedding available")

        # Parse user embedding (stored as taste_embedding in users table)
        import json
        import numpy as np
        user_embedding_json = user_features.get("taste_embedding")
        if isinstance(user_embedding_json, str):
            user_embedding = np.array(json.loads(user_embedding_json), dtype=np.float32)
        else:
            user_embedding = np.array(user_embedding_json, dtype=np.float32)

        # Normalize embedding (ensure L2 norm = 1 for cosine similarity)
        norm = np.linalg.norm(user_embedding)
        if norm > 0:
            user_embedding = user_embedding / norm

        logger.info(f"User embedding loaded: shape={user_embedding.shape}, norm={np.linalg.norm(user_embedding):.4f}")

        # Use intelligent recommendations service
        from services.intelligent_recommendations_service import intelligent_recommendations_service
        from services.vector_search_service import vector_search_service

        products_data = await intelligent_recommendations_service.get_recommendations(
            user=user,
            user_embedding=user_embedding,
            persona_style=persona_style,
            vector_search_service=vector_search_service,
            limit=limit,
            apply_diversity=True  # Apply MMR for variety
        )

        logger.info(f"✅ Returning {len(products_data)} intelligent ML-powered recommendations")

    except Exception as e:
        logger.warning(f"⚠️ Vector Search failed, using category-balanced fallback: {e}")

        # Fallback: Category-balanced recommendations using Lakebase query
        filters = {}

        # Persona-specific category weights for diversity
        PERSONA_CATEGORY_WEIGHTS = {
            "luxury": {"Apparel": 0.50, "Accessories": 0.25, "Footwear": 0.25},
            "budget": {"Apparel": 0.50, "Footwear": 0.30, "Accessories": 0.20},
            "budget_savvy": {"Apparel": 0.50, "Footwear": 0.30, "Accessories": 0.20},
            "athletic": {"Apparel": 0.60, "Footwear": 0.40},
            "formal": {"Apparel": 0.55, "Accessories": 0.30, "Footwear": 0.15},
            "professional": {"Apparel": 0.55, "Accessories": 0.30, "Footwear": 0.15},
            "casual": {"Apparel": 0.60, "Footwear": 0.25, "Accessories": 0.15},
            "urban_casual": {"Apparel": 0.60, "Footwear": 0.25, "Accessories": 0.15},
        }

        # Apply persona-specific price filters
        if persona_style == "luxury":
            filters["min_price"] = 200
        elif persona_style in ["budget", "budget_savvy"]:
            filters["min_price"] = 10
            filters["max_price"] = 100
        elif persona_style == "athletic":
            filters["min_price"] = 80
            filters["max_price"] = 180
        elif persona_style in ["formal", "professional"]:
            filters["min_price"] = 150
        elif persona_style in ["casual", "urban_casual"]:
            filters["min_price"] = 100
            filters["max_price"] = 200

        category_weights = PERSONA_CATEGORY_WEIGHTS.get(
            persona_style,
            {"Apparel": 0.50, "Footwear": 0.25, "Accessories": 0.25}
        )

        # Use category-balanced sampling for diverse results
        products_data = await repo.get_products_category_balanced(
            limit=limit,
            filters=filters,
            category_weights=category_weights
        )

        logger.info(f"✅ Category-balanced fallback returned {len(products_data)} products")

    # Convert to ProductDetail models with personalization reasons
    products = []
    preferred_colors = set(c.title() for c in persona.get("color_prefs", []))

    for p in products_data:
        product = ProductDetail(**p)
        product.image_url = get_image_url(product.product_id)

        # Add deterministic similarity score (not ML-based)
        # Score based on position in sorted list (first = highest score)
        product.similarity_score = 1.0 - (len(products) * 0.01)  # Decreases slightly for each item

        # Add personalization reasons based on persona
        reasons = []

        # Category match
        if p.get("master_category") in persona.get("preferred_categories", []):
            reasons.append(f"Matches your interest in {p['master_category']}")

        # Color match
        product_color = (p.get("base_color") or "").title()
        if product_color in preferred_colors:
            reasons.append(f"Matches your preference for {product_color} items")

        # Price-based reason (persona-specific)
        if persona_style == "luxury" and p.get("price") and p["price"] > 2000:
            reasons.append("Premium quality")
        elif persona_style == "budget" and p.get("price") and p["price"] < 1000:
            reasons.append("Great value")
        elif persona_style == "trendy":
            reasons.append("Latest style")
        elif persona_style == "vintage":
            reasons.append("Classic style")

        if reasons:
            product.personalization_reason = " • ".join(reasons)
        else:
            product.personalization_reason = f"Recommended for {persona_style} style"

        products.append(product)

    logger.info(f"Returning {len(products)} deterministic recommendations for {persona_style} persona")

    return SearchResponse(
        products=products,
        query=None,
        search_type="personalized",
        user_id=user_id
    )


@router.post("/cross-modal", response_model=SearchResponse)
async def cross_modal_search(
    request: SearchRequest = None,
    image: UploadFile = File(None),
    query: str = Form(None),
    user_id: Optional[str] = Form(None),
    limit: int = Form(20),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Cross-modal search: text query → image index OR image query → text index

    This enables finding products that LOOK like a text description
    or finding products semantically related to an uploaded image.
    """
    try:
        from services.clip_service import clip_service
        from services.vector_search_service import vector_search_service

        # Determine which mode: text→image or image→text
        if query:
            # Text → Image index (find products that LOOK like the description)
            logger.info(f"Cross-modal search: text→image for query '{query}' (limit={limit})")

            # Generate text embedding
            query_embedding = await clip_service.get_text_embedding(query)
            logger.info(f"Generated text embedding with shape: {query_embedding.shape}")

            # Search IMAGE index with text embedding (cross-modal!)
            products_data = await vector_search_service.search_cross_modal(
                query_vector=query_embedding,
                source_type="text",  # text query → image index
                num_results=limit
            )

            search_description = f"Products that look like: {query}"

        elif image:
            # Image → Text index (find products semantically related to image)
            logger.info(f"Cross-modal search: image→text for {image.filename} (limit={limit})")

            # Read uploaded image
            image_bytes = await image.read()
            logger.info(f"Read {len(image_bytes)} bytes from uploaded image")

            # Generate image embedding
            query_embedding = await clip_service.get_image_embedding(image_bytes)
            logger.info(f"Generated image embedding with shape: {query_embedding.shape}")

            # Search TEXT index with image embedding (cross-modal!)
            products_data = await vector_search_service.search_cross_modal(
                query_vector=query_embedding,
                source_type="image",  # image query → text index
                num_results=limit
            )

            search_description = f"Products semantically related to uploaded image"

        else:
            raise HTTPException(status_code=400, detail="Must provide either text query or image")

        # Convert to ProductDetail
        products = []
        for p in products_data:
            product = ProductDetail(**p)
            # Pass product_id directly - get_image_url handles conversion
            product.image_url = get_image_url(product.product_id)
            product.similarity_score = p.get("score", 0.85)
            products.append(product)

        logger.info(f"✅ Cross-modal search returned {len(products)} results")

        return SearchResponse(
            products=products,
            query=search_description,
            search_type="cross-modal",
            user_id=user_id
        )

    except Exception as e:
        logger.error(f"Cross-modal search error: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Cross-modal search failed: {str(e)}")