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

router = APIRouter(prefix="/products", tags=["products"])

# Get workspace host for constructing Files API URLs
WORKSPACE_HOST = os.getenv("DATABRICKS_HOST", "")
if WORKSPACE_HOST and not WORKSPACE_HOST.startswith("http"):
    WORKSPACE_HOST = f"https://{WORKSPACE_HOST}"


def get_image_url(product_id: int) -> str:
    """
    Construct direct Files API URL for product image
    Pattern: https://{workspace-host}/ajax-api/2.0/fs/files/Volumes/main/fashion_demo/raw_data/images/{product_id}.jpg
    """
    return f"{WORKSPACE_HOST}/ajax-api/2.0/fs/files/Volumes/main/fashion_demo/raw_data/images/{product_id}.jpg"


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
        product.image_url = get_image_url(int(product.product_id))
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
    try:
        product_id_int = int(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid product_id: {product_id}")
    
    product_data = await repo.get_product_by_id(product_id_int)

    if not product_data:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    product = ProductDetail(**product_data)
    # Use direct Files API URL instead of proxying through /api/v1/images
    product.image_url = get_image_url(product_id_int)

    return product


@router.get("/filters/options", response_model=FilterOptions)
async def get_filter_options(db: AsyncSession = Depends(get_async_db)):
    """
    Get all available filter options for products
    """
    repo = LakebaseRepository(db)
    options = await repo.get_filter_options()
    return FilterOptions(**options)