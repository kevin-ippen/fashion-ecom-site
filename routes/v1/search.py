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

    try:
        # Get taste_embedding from fashion_sota.users (BATCH PRE-CALCULATED)
        logger.info(f"🔍 Looking for pre-calculated taste_embedding for user {user_id} in fashion_sota.users...")
        logger.info(f"   User record keys: {list(user.keys())}")
        logger.info(f"   Has taste_embedding key: {'taste_embedding' in user}")
        if 'taste_embedding' in user:
            te_value = user.get('taste_embedding')
            logger.info(f"   taste_embedding type: {type(te_value)}")
            logger.info(f"   taste_embedding is None: {te_value is None}")
            if te_value:
                logger.info(f"   taste_embedding length: {len(te_value) if hasattr(te_value, '__len__') else 'N/A'}")

        # Check if user has taste_embedding (already fetched above)
        if user.get("taste_embedding"):
            # Use Hybrid Vector Search with user taste embedding
            from services.vector_search_service import vector_search_service

            # Parse embedding data
            embedding_data = user["taste_embedding"]
            if isinstance(embedding_data, str):
                embedding_data = json.loads(embedding_data)
            elif isinstance(embedding_data, list):
                pass  # Already a list
            else:
                logger.error(f"❌ Unexpected embedding type: {type(embedding_data)}")
                raise Exception(f"Invalid embedding type: {type(embedding_data)}")

            user_embedding = np.array(embedding_data, dtype=np.float32)

            logger.info(f"✅ Using BATCH pre-calculated taste_embedding from fashion_sota.users")
            logger.info(f"   Shape: {user_embedding.shape}, dtype: {user_embedding.dtype}")

            # Build filters for application-layer filtering (NOT for vector search index)
            # Vector search index only has embedding column, so we do unfiltered search
            # and filter results in application layer
            app_filters = {}

            if restrict_category and persona.get("preferred_categories"):
                app_filters["categories"] = persona["preferred_categories"]
                logger.info(f"Will filter to categories: {persona['preferred_categories']}")

            # Only set price filter if we have valid price data
            if restrict_price and persona.get("p25_price") and persona.get("p75_price"):
                min_price = persona["p25_price"] * 0.8
                max_price = persona["p75_price"] * 1.2
                app_filters["min_price"] = min_price
                app_filters["max_price"] = max_price
                logger.info(f"Will filter to price range: ${min_price:.0f}-${max_price:.0f}")

            if restrict_color and persona.get("color_prefs"):
                app_filters["colors"] = persona["color_prefs"]
                logger.info(f"Will filter to colors: {persona['color_prefs']}")

            # Get more results from vector search (unfiltered) so we have enough after filtering
            logger.info(f"Performing unfiltered vector search to get {limit * 4} candidates")
            products_data = await vector_search_service.search_hybrid(
                query_vector=user_embedding,
                num_results=limit * 4,  # Get more to compensate for filtering
                filters=None  # NO FILTERS - index doesn't support them
            )

            logger.info(f"✅ Hybrid Vector Search returned {len(products_data)} products")

            # Apply application-layer filtering to vector search results
            # Use LENIENT filtering to avoid dropping all results
            if app_filters:
                # Log sample candidates before filtering
                if len(products_data) > 0:
                    sample = products_data[0]
                    logger.info(f"Sample candidate before filtering: master_category={sample.get('master_category')}, sub_category={sample.get('sub_category')}, base_color={sample.get('base_color')}")

                filtered_data = []
                filter_stats = {"category_dropped": 0, "color_dropped": 0}

                for p in products_data:
                    # Category filter - check both master_category and sub_category
                    # preferred_categories might contain either level
                    if "categories" in app_filters:
                        master_cat = p.get("master_category", "")
                        sub_cat = p.get("sub_category", "")
                        article = p.get("article_type", "")

                        # Match if ANY category field matches ANY preferred category
                        category_match = any(
                            pref in [master_cat, sub_cat, article]
                            for pref in app_filters["categories"]
                        )

                        if not category_match:
                            filter_stats["category_dropped"] += 1
                            continue

                    # Color filter - more lenient
                    if "colors" in app_filters:
                        product_color = (p.get("base_color") or "").title()
                        normalized_colors = [c.title() for c in app_filters["colors"]]
                        if product_color and product_color not in normalized_colors:
                            filter_stats["color_dropped"] += 1
                            # Don't drop - color is a soft preference
                            # continue

                    filtered_data.append(p)

                logger.info(f"Filter stats: {filter_stats}")
                logger.info(f"After application filters: {len(filtered_data)} products (removed {len(products_data) - len(filtered_data)})")

                # Fallback: If filters removed everything, retry without filters
                if len(filtered_data) == 0 and len(products_data) > 0:
                    logger.warning(f"⚠️ Filters removed all results! Using unfiltered candidates.")
                    filtered_data = products_data

                products_data = filtered_data

        else:
            # Fallback to rule-based if no taste_embedding
            logger.warning(f"⚠️ No taste_embedding field found for {user_id}")
            logger.warning(f"   User exists in fashion_sota.users but taste_embedding is NULL")
            logger.warning(f"   Falling back to rule-based recommendations based on preferences")
            raise Exception("No taste_embedding - use fallback")

    except Exception as e:
        logger.warning(f"⚠️ Vector Search failed, using rule-based fallback: {e}")

        # Fallback: Rule-based recommendations using Lakebase query
        filters = {}
        app_filters = {}  # Initialize for fallback path

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
        
        # Price match bonus (only if we have valid price data in BOTH product and persona)
        # Note: product_embeddings table doesn't have price, only products_lakebase does
        if (p.get("price") is not None and
            persona.get("avg_price") and
            persona.get("min_price") and
            persona.get("max_price")):
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
        # Only check price range if product has price data
        if (p.get("price") is not None and
            persona.get("min_price") and
            persona.get("max_price") and
            persona["min_price"] <= p["price"] <= persona["max_price"]):
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