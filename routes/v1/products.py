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
    Get paginated list of products with optional filtering
    """
    repo = LakebaseRepository(db)

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

    # Get products and total count
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
    Get visually similar products using vector similarity

    Returns products that look similar based on FashionCLIP embeddings,
    filtered by category compatibility and diversified by color.
    """
    from services.vector_search_service import vector_search_service
    from services.recommendations_service import recommendations_service
    import logging

    logger = logging.getLogger(__name__)

    try:
        repo = LakebaseRepository(db)

        # Convert product_id to int
        try:
            product_id_int = int(float(product_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"Invalid product_id: {product_id}")

        # Get source product with full metadata
        source_product = await repo.get_product_by_id(product_id_int)
        if not source_product:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

        logger.info(f"Getting similar products for {product_id} - {source_product.get('product_display_name')}")

        # Get source product embedding from vector index
        # We'll search with a dummy embedding first to get the source product's embedding
        # Alternative: query the product_embeddings table directly
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()

        # Query product_embeddings table for source product embedding
        query = f"""
        SELECT embedding
        FROM main.fashion_sota.product_embeddings
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
        embedding_data = result.data_array[0][0]  # First row, first column
        if isinstance(embedding_data, str):
            import json
            embedding_data = json.loads(embedding_data)

        source_embedding = np.array(embedding_data, dtype=np.float32)

        # Normalize embedding
        norm = np.linalg.norm(source_embedding)
        if norm > 0:
            source_embedding = source_embedding / norm

        logger.info(f"Retrieved source embedding: shape={source_embedding.shape}, norm={norm:.4f}")

        # Get similar products
        similar_products = await recommendations_service.get_similar_products(
            source_product=source_product,
            source_embedding=source_embedding,
            vector_search_service=vector_search_service,
            lakebase_repo=repo,
            limit=limit
        )

        # Convert to ProductDetail models
        products = []
        for p in similar_products:
            product = ProductDetail(**p)
            product.image_url = get_image_url(product.product_id)
            products.append(product)

        logger.info(f"✅ Returning {len(products)} similar products")

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
    Get complementary products from outfit pairings

    Returns products that have been paired with this product in brand lookbook outfits.
    Uses the outfit_recommendations_filtered table (outliers removed).
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

        # Get source product
        source_product = await repo.get_product_by_id(product_id_int)
        if not source_product:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

        logger.info(f"Getting outfit pairings for {product_id} - {source_product.get('product_display_name')}")

        # Query outfit_recommendations_filtered table
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()

        # Query outfit pairings - check BOTH directions since table is bidirectional
        query = f"""
        SELECT
            product_2_id as recommended_product_id,
            product_2_name as recommended_product_name,
            product_2_category as recommended_category,
            co_occurrence_count
        FROM main.fashion_sota.outfit_recommendations_filtered
        WHERE product_1_id = '{product_id_int}'

        UNION ALL

        SELECT
            product_1_id as recommended_product_id,
            product_1_name as recommended_product_name,
            product_1_category as recommended_category,
            co_occurrence_count
        FROM main.fashion_sota.outfit_recommendations_filtered
        WHERE product_2_id = '{product_id_int}'

        ORDER BY co_occurrence_count DESC
        LIMIT {limit}
        """

        execution_result = w.statement_execution.execute_statement(
            statement=query,
            warehouse_id=settings.SQL_WAREHOUSE_ID if hasattr(settings, 'SQL_WAREHOUSE_ID') else "148ccb90800933a1"
        )
        result = execution_result.result

        if not result or not result.data_array or len(result.data_array) == 0:
            # Fallback: no outfit recommendations, return empty
            logger.warning(f"No outfit pairings found for product {product_id}")
            return ProductListResponse(
                products=[],
                total=0,
                page=1,
                page_size=limit,
                has_more=False
            )

        # Get full product details from Lakebase for each recommendation
        products = []
        for row in result.data_array:
            rec_product_id = row[0]
            co_occurrence = row[3]

            try:
                rec_product_id_int = int(float(rec_product_id))
                full_product = await repo.get_product_by_id(rec_product_id_int)

                if full_product:
                    product = ProductDetail(**full_product)
                    product.image_url = get_image_url(product.product_id)
                    # Add personalization reason
                    product.personalization_reason = f"Paired together in {co_occurrence} outfits"
                    products.append(product)
            except Exception as e:
                logger.warning(f"Failed to get product {rec_product_id}: {e}")
                continue

        logger.info(f"✅ Returning {len(products)} complementary products from outfit pairings")

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