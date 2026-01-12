"""
Product API routes
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from models.schemas import ProductListResponse, ProductDetail, FilterOptions
from repositories.lakebase import LakebaseRepository
from core.database import get_async_db
from core.config import settings
import os
import numpy as np

router = APIRouter(prefix="/products", tags=["products"])

# Get workspace host for constructing Files API URLs
WORKSPACE_HOST = settings.DATABRICKS_WORKSPACE_URL


def get_image_url(product_id) -> str:
    """
    Construct direct Files API URL for product image
    Pattern: https://{workspace-host}/ajax-api/2.0/fs/files/Volumes/main/fashion_sota/product_images/{product_id}.jpg

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

    return f"{WORKSPACE_HOST}/ajax-api/2.0/fs/files/Volumes/main/fashion_sota/product_images/{pid}.jpg"


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(24, ge=1, le=100, description="Items per page"),
    user_id: Optional[str] = Query(None, description="User ID for personalized sorting"),
    gender: Optional[str] = None,
    master_category: Optional[str] = None,
    sub_category: Optional[str] = None,
    base_color: Optional[str] = None,
    season: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: str = Query("product_display_name", description="Field to sort by"),
    sort_order: str = Query("ASC", regex="^(ASC|DESC)$"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get paginated list of products with optional filtering and personalization

    If user_id is provided, products are sorted by taste propensity (personalized recommendations).
    Otherwise, products are sorted by the specified field.
    """
    repo = LakebaseRepository(db)
    import logging
    import json
    logger = logging.getLogger(__name__)

    # Build filters dict
    filters = {}
    if gender:
        filters["gender"] = gender
    if master_category:
        filters["master_category"] = master_category
    if sub_category:
        filters["sub_category"] = sub_category
    if base_color:
        filters["base_color"] = base_color
    if season:
        filters["season"] = season
    if min_price:
        filters["min_price"] = min_price
    if max_price:
        filters["max_price"] = max_price

    # Calculate offset
    offset = (page - 1) * page_size

    # Check if personalized sorting is requested
    if user_id:
        logger.info(f"🎯 Deterministic persona-based sorting for user {user_id}")
        try:
            # Get user to determine their style profile
            user = await repo.get_user_by_id(user_id)

            if user:
                # Import persona mappings to determine style
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

                # Note: user's preferred_categories contains sub_category values like "Outerwear", "Shoes"
                # NOT master_category values. Don't filter by them - let persona logic handle filters.
                preferred_cats = user.get("preferred_categories", [])
                logger.info(f"User preferred categories (for reference): {preferred_cats}")

                # Persona-specific category weights for diversity
                # These ensure balanced category representation instead of skewing toward one category
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

                # Apply persona-specific filters (actual product price range: $0-300)
                category_weights = PERSONA_CATEGORY_WEIGHTS.get(persona_style, {"Apparel": 0.50, "Footwear": 0.25, "Accessories": 0.25})
                use_balanced_sampling = True  # Use category-balanced sampling for diversity

                if persona_style == "luxury":
                    # Luxury: Top 20% of products ($200-300)
                    filters["min_price"] = 200
                    logger.info("Luxury persona → filtering price >= $200, category-balanced sampling")
                elif persona_style in ["budget", "budget_savvy"]:
                    # Budget: Low range ($10-100)
                    filters["min_price"] = 10
                    filters["max_price"] = 100
                    logger.info("Budget persona → filtering price $10-100, category-balanced sampling")
                elif persona_style == "athletic":
                    # Athletic: Mid range ($80-180), only Apparel/Footwear
                    filters["min_price"] = 80
                    filters["max_price"] = 180
                    logger.info("Athletic persona → filtering Apparel/Footwear $80-180, category-balanced sampling")
                elif persona_style in ["formal", "professional"]:
                    # Professional: Upper range ($150-300)
                    filters["min_price"] = 150
                    logger.info("Professional persona → filtering Apparel/Accessories $150+, category-balanced sampling")
                elif persona_style in ["casual", "urban_casual"]:
                    # Urban Casual: Mid-high range ($100-200)
                    filters["min_price"] = 100
                    filters["max_price"] = 200
                    logger.info("Urban Casual persona → filtering price $100-200, category-balanced sampling")
                else:
                    # All other personas: no specific filters
                    logger.info(f"{persona_style.title()} persona → no filters, category-balanced sampling")

                # If user applied a specific category filter, fall back to regular random
                if master_category or sub_category:
                    use_balanced_sampling = False
                    logger.info("User applied category filter → using regular random sorting")

                if use_balanced_sampling:
                    # Use category-balanced sampling for diverse results
                    products_data = await repo.get_products_category_balanced(
                        limit=page_size,
                        offset=offset,
                        filters=filters if filters else None,
                        category_weights=category_weights
                    )
                else:
                    # User applied category filter, use regular random
                    products_data = await repo.get_products(
                        limit=page_size,
                        offset=offset,
                        filters=filters if filters else None,
                        sort_by="RANDOM",
                        sort_order=""
                    )

                total = await repo.get_product_count(filters if filters else None)

                logger.info(f"✅ Returning {len(products_data)} category-balanced products")
            else:
                logger.warning(f"User {user_id} not found, falling back to standard sorting")
                # Fall through to standard sorting below
                products_data = await repo.get_products(
                    limit=page_size,
                    offset=offset,
                    filters=filters if filters else None,
                    sort_by=sort_by,
                    sort_order=sort_order
                )
                total = await repo.get_product_count(filters if filters else None)

        except Exception as e:
            logger.error(f"Deterministic persona sorting failed: {e}, falling back to standard sorting")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            # Fall through to standard sorting
            products_data = await repo.get_products(
                limit=page_size,
                offset=offset,
                filters=filters if filters else None,
                sort_by=sort_by,
                sort_order=sort_order
            )
            total = await repo.get_product_count(filters if filters else None)
    else:
        # Standard non-personalized sorting
        products_data = await repo.get_products(
            limit=page_size,
            offset=offset,
            filters=filters if filters else None,
            sort_by=sort_by,
            sort_order=sort_order
        )
        total = await repo.get_product_count(filters if filters else None)

    # Convert to ProductDetail models
    products = []
    for p in products_data:
        product = ProductDetail(**p)
        # Use direct Files API URL instead of proxying through /api/v1/images
        product.image_url = get_image_url(product.product_id)
        products.append(product)

    return ProductListResponse(
        products=products,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + page_size < total
    )


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get a single product by ID
    """
    repo = LakebaseRepository(db)
    
    # Convert product_id to int since the database column is INTEGER
    # Handle float strings like "14880.0" by converting through float first
    try:
        product_id_int = int(float(product_id))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid product_id: {product_id}")
    
    product_data = await repo.get_product_by_id(product_id_int)

    if not product_data:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    product = ProductDetail(**product_data)
    # Use direct Files API URL instead of proxying through /api/v1/images
    product.image_url = get_image_url(product.product_id)

    return product


@router.get("/filters/options", response_model=FilterOptions)
async def get_filter_options(db: AsyncSession = Depends(get_async_db)):
    """
    Get all available filter options for products
    """
    repo = LakebaseRepository(db)
    options = await repo.get_filter_options()
    return FilterOptions(**options)


@router.get("/{product_id}/similar", response_model=ProductListResponse)
async def get_similar_products(
    product_id: str,
    limit: int = Query(6, ge=1, le=20, description="Number of recommendations"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get visually similar products.

    First checks for pre-calculated recommendations (batch inference).
    Falls back to real-time vector search if pre-calculated data unavailable.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        repo = LakebaseRepository(db)

        # Convert product_id to int
        try:
            product_id_int = int(float(product_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"Invalid product_id: {product_id}")

        # Get source product with full metadata (includes pre-calculated IDs)
        source_product = await repo.get_product_by_id(product_id_int)
        if not source_product:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

        logger.info(f"Getting similar products for {product_id} - {source_product.get('product_display_name')}")

        # Check for pre-calculated similar products (batch inference)
        similar_ids = source_product.get("similar_product_ids", [])

        if similar_ids and len(similar_ids) > 0:
            # Use pre-calculated recommendations (fast path)
            logger.info(f"Using pre-calculated similar products: {len(similar_ids)} IDs available")

            # Fetch full product details via efficient batch lookup
            similar_products = await repo.get_products_by_ids(
                product_ids=similar_ids[:limit],
                preserve_order=True
            )

            logger.info(f"✅ Returning {len(similar_products)} pre-calculated similar products")

        else:
            # Fall back to real-time vector search (slow path)
            logger.info("No pre-calculated similar products, using real-time vector search")

            from services.vector_search_service import vector_search_service
            from services.recommendations_service import recommendations_service
            from databricks.sdk import WorkspaceClient

            w = WorkspaceClient()

            # Query product_embeddings table for source product embedding
            query = f"""
            SELECT embedding
            FROM main.fashion_sota.product_embeddings_us_relevant
            WHERE product_id = '{product_id_int}'
            LIMIT 1
            """

            execution_result = w.statement_execution.execute_statement(
                statement=query,
                warehouse_id=settings.SQL_WAREHOUSE_ID if hasattr(settings, 'SQL_WAREHOUSE_ID') else "148ccb90800933a1"
            )
            result = execution_result.result

            if not result or not result.data_array or len(result.data_array) == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"No embedding found for product {product_id}. Product may not be indexed."
                )

            # Extract embedding (stored as array<double>)
            embedding_data = result.data_array[0][0]
            if isinstance(embedding_data, str):
                import json
                embedding_data = json.loads(embedding_data)

            source_embedding = np.array(embedding_data, dtype=np.float32)

            # Normalize embedding
            norm = np.linalg.norm(source_embedding)
            if norm > 0:
                source_embedding = source_embedding / norm

            logger.info(f"Retrieved source embedding: shape={source_embedding.shape}, norm={norm:.4f}")

            # Get similar products via vector search
            similar_products = await recommendations_service.get_similar_products(
                source_product=source_product,
                source_embedding=source_embedding,
                vector_search_service=vector_search_service,
                lakebase_repo=repo,
                limit=limit
            )

            logger.info(f"✅ Returning {len(similar_products)} vector-searched similar products")

        # Convert to ProductDetail models
        products = []
        for p in similar_products:
            product = ProductDetail(**p)
            product.image_url = get_image_url(product.product_id)
            products.append(product)

        return ProductListResponse(
            products=products,
            total=len(products),
            page=1,
            page_size=limit,
            has_more=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting similar products: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get similar products: {str(e)}")


@router.get("/{product_id}/complete-the-look", response_model=ProductListResponse)
async def get_complementary_products(
    product_id: str,
    limit: int = Query(4, ge=1, le=12, description="Number of recommendations"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get complementary products for outfit completion.

    First checks for pre-calculated recommendations (batch inference).
    Falls back to real-time lookbook query if pre-calculated data unavailable.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        repo = LakebaseRepository(db)

        # Convert product_id to int
        try:
            product_id_int = int(float(product_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"Invalid product_id: {product_id}")

        # Get source product (includes pre-calculated IDs)
        source_product = await repo.get_product_by_id(product_id_int)
        if not source_product:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

        logger.info(f"Getting outfit pairings for {product_id} - {source_product.get('product_display_name')}")

        # Check for pre-calculated complete-the-set products (batch inference)
        complete_set_ids = source_product.get("complete_the_set_ids", [])

        if complete_set_ids and len(complete_set_ids) > 0:
            # Use pre-calculated recommendations (fast path)
            logger.info(f"Using pre-calculated complete-the-set: {len(complete_set_ids)} IDs available")

            # Fetch full product details via efficient batch lookup
            complete_products = await repo.get_products_by_ids(
                product_ids=complete_set_ids[:limit],
                preserve_order=True
            )

            # Convert to ProductDetail models
            products = []
            for p in complete_products:
                product = ProductDetail(**p)
                product.image_url = get_image_url(product.product_id)
                product.personalization_reason = "Styled together"
                products.append(product)

            logger.info(f"✅ Returning {len(products)} pre-calculated complete-the-set products")

            return ProductListResponse(
                products=products,
                total=len(products),
                page=1,
                page_size=limit,
                has_more=False
            )

        # Fall back to real-time lookbook query (slow path)
        logger.info("No pre-calculated complete-the-set, using real-time lookbook query")

        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()

        # Query for outfit pairs
        search_limit = max(100, limit * 20)

        query = f"""
        SELECT
            product_2_id as recommended_product_id,
            product_2_name as recommended_product_name,
            product_2_category as recommended_category,
            co_occurrence_count,
            0.8 as quality_score,
            source
        FROM main.fashion_sota.outfit_recommendations_from_lookbook
        WHERE product_1_id = '{product_id_int}'

        UNION ALL

        SELECT
            product_1_id as recommended_product_id,
            product_1_name as recommended_product_name,
            product_1_category as recommended_category,
            co_occurrence_count,
            0.8 as quality_score,
            source
        FROM main.fashion_sota.outfit_recommendations_from_lookbook
        WHERE product_2_id = '{product_id_int}'

        ORDER BY co_occurrence_count DESC
        LIMIT {search_limit}
        """

        warehouse_id = settings.SQL_WAREHOUSE_ID if hasattr(settings, 'SQL_WAREHOUSE_ID') else "148ccb90800933a1"
        logger.info(f"Executing lookbook query with warehouse: {warehouse_id}")

        execution_result = w.statement_execution.execute_statement(
            statement=query,
            warehouse_id=warehouse_id
        )
        result = execution_result.result

        if not result or not result.data_array or len(result.data_array) == 0:
            logger.warning(f"No outfit pairings found for product {product_id}")
            return ProductListResponse(
                products=[],
                total=0,
                page=1,
                page_size=limit,
                has_more=False
            )

        # Get full product details from Lakebase for each candidate
        candidates = []
        co_occurrence_map = {}

        for row in result.data_array:
            rec_product_id = row[0]
            co_occurrence = row[3]

            try:
                rec_product_id_int = int(float(rec_product_id))
                full_product = await repo.get_product_by_id(rec_product_id_int)

                if full_product:
                    candidates.append(full_product)
                    co_occurrence_map[rec_product_id_int] = co_occurrence
            except Exception as e:
                logger.warning(f"Failed to get product {rec_product_id}: {e}")
                continue

        logger.info(f"Retrieved {len(candidates)} candidate products")

        # Apply outfit compatibility filtering
        from services.outfit_compatibility_service import outfit_compatibility_service
        import random

        filter_limit = limit * 2

        filtered = outfit_compatibility_service.filter_outfit_recommendations(
            source_product=source_product,
            candidates=candidates,
            limit=filter_limit
        )

        # Apply category diversity constraint
        category_balanced = []
        footwear_count = 0
        accessories_count = 0

        apparel_items = [p for p in filtered if p.get("master_category") == "Apparel"]
        footwear_items = [p for p in filtered if p.get("master_category") == "Footwear"]
        accessories_items = [p for p in filtered if p.get("master_category") == "Accessories"]

        random.shuffle(apparel_items)
        random.shuffle(footwear_items)
        random.shuffle(accessories_items)

        target_apparel = max(limit - 2, int(limit * 0.75))
        category_balanced.extend(apparel_items[:target_apparel])

        if len(category_balanced) < limit and footwear_items:
            category_balanced.append(footwear_items[0])
            footwear_count = 1

        if len(category_balanced) < limit and accessories_items:
            category_balanced.append(accessories_items[0])
            accessories_count = 1

        remaining_slots = limit - len(category_balanced)
        if remaining_slots > 0 and len(apparel_items) > target_apparel:
            category_balanced.extend(apparel_items[target_apparel:target_apparel + remaining_slots])

        filtered = category_balanced
        logger.info(f"After category balancing: {len(filtered)} products")

        # Convert to ProductDetail models
        products = []
        for product_dict in filtered:
            product = ProductDetail(**product_dict)
            product.image_url = get_image_url(product.product_id)

            co_occurrence = co_occurrence_map.get(product.product_id, 1)
            product.personalization_reason = f"Paired together in {co_occurrence} outfits"

            products.append(product)

        logger.info(f"✅ Returning {len(products)} lookbook-sourced outfit recommendations")

        return ProductListResponse(
            products=products,
            total=len(products),
            page=1,
            page_size=limit,
            has_more=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting complementary products: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get complementary products: {str(e)}")


@router.get("/trending", response_model=ProductListResponse)
async def get_trending_products(
    limit: int = Query(20, ge=1, le=50, description="Number of trending products"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get trending products

    Returns popular/trending products based on engagement signals.
    In production, this would use real user interaction data (views, add-to-cart, purchases).
    For demo, uses weighted random selection with category balance.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        from services.business_features_service import business_features_service

        repo = LakebaseRepository(db)

        # Get trending products
        trending_data = await business_features_service.get_trending_products(
            lakebase_repo=repo,
            limit=limit,
            time_window="7_days"
        )

        # Convert to ProductDetail models
        products = []
        for product_dict in trending_data:
            product = ProductDetail(**product_dict)
            product.image_url = get_image_url(product.product_id)
            product.personalization_reason = "Trending now"
            products.append(product)

        logger.info(f"✅ Returning {len(products)} trending products")

        return ProductListResponse(
            products=products,
            total=len(products),
            page=1,
            page_size=limit,
            has_more=False
        )

    except Exception as e:
        logger.error(f"Error getting trending products: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get trending products: {str(e)}")


@router.get("/seasonal", response_model=ProductListResponse)
async def get_seasonal_products(
    season: Optional[str] = Query(None, description="Season (Spring, Summer, Fall, Winter) or None for current"),
    limit: int = Query(20, ge=1, le=50, description="Number of seasonal products"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get seasonal collection products

    Returns products appropriate for the current season (or specified season).
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        from services.business_features_service import business_features_service

        repo = LakebaseRepository(db)

        # Get current season if not specified
        if not season:
            season = business_features_service.get_current_season()

        # Get seasonal products
        seasonal_data = await business_features_service.get_seasonal_products(
            lakebase_repo=repo,
            season=season,
            limit=limit
        )

        # Convert to ProductDetail models
        products = []
        for product_dict in seasonal_data:
            product = ProductDetail(**product_dict)
            product.image_url = get_image_url(product.product_id)
            product.personalization_reason = f"{season} collection"
            products.append(product)

        logger.info(f"✅ Returning {len(products)} {season} products")

        return ProductListResponse(
            products=products,
            total=len(products),
            page=1,
            page_size=limit,
            has_more=False
        )

    except Exception as e:
        logger.error(f"Error getting seasonal products: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get seasonal products: {str(e)}")


@router.get("/new-arrivals", response_model=ProductListResponse)
async def get_new_arrivals(
    limit: int = Query(20, ge=1, le=50, description="Number of new arrivals"),
    min_year: int = Query(2017, ge=2011, le=2018, description="Minimum year for new arrivals"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get new arrival products

    Returns recently added products (using year as a proxy for demo).
    In production, would use creation_date or ingestion_date.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        from services.business_features_service import business_features_service

        repo = LakebaseRepository(db)

        # Get new arrivals
        new_arrivals_data = await business_features_service.get_new_arrivals(
            lakebase_repo=repo,
            limit=limit,
            min_year=min_year
        )

        # Convert to ProductDetail models
        products = []
        for product_dict in new_arrivals_data:
            product = ProductDetail(**product_dict)
            product.image_url = get_image_url(product.product_id)
            product.personalization_reason = "New arrival"
            products.append(product)

        logger.info(f"✅ Returning {len(products)} new arrivals")

        return ProductListResponse(
            products=products,
            total=len(products),
            page=1,
            page_size=limit,
            has_more=False
        )

    except Exception as e:
        logger.error(f"Error getting new arrivals: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get new arrivals: {str(e)}")