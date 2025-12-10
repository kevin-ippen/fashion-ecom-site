"""
Search API routes with CLIP + Vector Search integration
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from models.schemas import SearchRequest, SearchResponse, ProductDetail
from repositories.lakebase import LakebaseRepository
from core.database import get_async_db
import numpy as np
import json
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# Get workspace host for constructing Files API URLs
WORKSPACE_HOST = os.getenv("DATABRICKS_WORKSPACE_URL", "")
if WORKSPACE_HOST and not WORKSPACE_HOST.startswith("http"):
    WORKSPACE_HOST = f"https://{WORKSPACE_HOST}"


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
        logger.error(f"Text search error: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Text search failed: {str(e)}")


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
    restrict_category: bool = True,
    restrict_price: bool = True,
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

    # Load persona to get preferences
    from routes.v1.users import load_personas

    personas = load_personas()
    persona = next((p for p in personas if p["user_id"] == user_id), None)

    if not persona:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    logger.info(f"Getting recommendations for user {user_id} - {persona.get('name', 'Unknown')}")
    logger.info(f"Persona preferences: categories={persona.get('preferred_categories')}, colors={persona.get('color_prefs')}")
    logger.info(f"Filter settings: category={restrict_category}, price={restrict_price}, color={restrict_color}")

    try:
        # Try to get user embedding from user_style_features table
        user_features = await repo.get_user_style_features(user_id)

        if user_features and user_features.get("user_embedding"):
            # Use Hybrid Vector Search with user embedding
            from services.vector_search_service import vector_search_service

            # Parse JSON string to list, then convert to numpy array
            embedding_data = user_features["user_embedding"]
            if isinstance(embedding_data, str):
                embedding_data = json.loads(embedding_data)
            
            user_embedding = np.array(embedding_data, dtype=np.float32)

            logger.info(f"✅ Found user embedding: shape={user_embedding.shape}")

            # Build flexible filters based on parameters
            filters = {}

            if restrict_category and persona.get("preferred_categories"):
                filters["master_category"] = persona["preferred_categories"]
                logger.info(f"Restricting to categories: {persona['preferred_categories']}")

            # Only add price filter if we have valid price data
            if restrict_price and persona.get("p25_price") and persona.get("p75_price"):
                min_price = persona["p25_price"] * 0.8
                max_price = persona["p75_price"] * 1.2
                filters["price"] = {"$gte": min_price, "$lte": max_price}
                logger.info(f"Restricting to price range: ${min_price:.0f}-${max_price:.0f}")
            else:
                logger.info("Skipping price filter (no valid price data)")

            if restrict_color and persona.get("color_prefs"):
                filters["base_color"] = persona["color_prefs"]
                logger.info(f"Restricting to colors: {persona['color_prefs']}")

            # Try with filters first
            logger.info(f"Attempting vector search with filters: {filters}")
            products_data = await vector_search_service.search_hybrid(
                query_vector=user_embedding,
                num_results=limit * 2,
                filters=filters if filters else None
            )

            logger.info(f"✅ Hybrid Vector Search returned {len(products_data)} products")

            # If no results with filters, try without filters
            if len(products_data) == 0 and filters:
                logger.warning("No results with filters, retrying without filters...")
                products_data = await vector_search_service.search_hybrid(
                    query_vector=user_embedding,
                    num_results=limit * 2,
                    filters=None
                )
                logger.info(f"✅ Vector Search without filters returned {len(products_data)} products")

        else:
            # Fallback to rule-based if no user embedding
            logger.warning(f"No user embedding found for {user_id}, using rule-based recommendations")
            raise Exception("No user embedding - use fallback")

    except Exception as e:
        logger.warning(f"Vector Search failed, using rule-based fallback: {e}")

        # Fallback: Rule-based recommendations
        filters = {}

        if restrict_price and persona.get("p25_price") and persona.get("p75_price"):
            filters["min_price"] = persona["p25_price"] * 0.8
            filters["max_price"] = persona["p75_price"] * 1.2

        if restrict_category and persona.get("preferred_categories"):
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
        # Pass product_id directly - get_image_url handles conversion
        product.image_url = get_image_url(product.product_id)

        # Calculate hybrid score
        vector_score = p.get("score", 0.5)  # From Vector Search or default
        rule_score = 0.0
        
        # Category match bonus
        if category_match:
            rule_score += 0.3
        
        # Color match bonus
        if color_match:
            rule_score += 0.4
        
        # Price match bonus (only if we have valid price data)
        if persona.get("avg_price") and persona.get("min_price") and persona.get("max_price"):
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
        if persona.get("min_price") and persona.get("max_price") and persona["min_price"] <= p["price"] <= persona["max_price"]:
            reasons.append(f"Within your typical price range (${persona['min_price']:.0f}-${persona['max_price']:.0f})")
        if "score" in p and p["score"] > 0.8:
            reasons.append("Similar to items you've liked before")

        if reasons:
            product.personalization_reason = " • ".join(reasons)

        filtered_products.append(product)

    # Sort by hybrid score and limit
    filtered_products.sort(key=lambda x: x.similarity_score or 0, reverse=True)
    products = filtered_products[:limit]
    
    if len(products) > 0:
        avg_score = np.mean([p.similarity_score for p in products])
        logger.info(f"Returning {len(products)} personalized recommendations (avg score: {avg_score:.2f})")
    else:
        logger.warning(f"Returning 0 recommendations for user {user_id}")

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