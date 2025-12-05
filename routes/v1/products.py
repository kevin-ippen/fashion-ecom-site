"""
Product API routes
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from models.schemas import ProductListResponse, ProductDetail, FilterOptions
from repositories.lakebase import lakebase_repo
from core.config import settings

router = APIRouter(prefix="/products", tags=["products"])


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
    sort_order: str = Query("ASC", regex="^(ASC|DESC)$")
):
    """
    Get paginated list of products with optional filtering
    """
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
    products_data = lakebase_repo.get_products(
        limit=page_size,
        offset=offset,
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order
    )

    total = lakebase_repo.get_product_count(filters if filters else None)

    # Convert to ProductDetail models
    products = []
    for p in products_data:
        product = ProductDetail(**p)
        # Add image URL (we'll create an endpoint to serve images)
        product.image_url = f"/api/images/{product.image_path}"
        products.append(product)

    return ProductListResponse(
        products=products,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + page_size < total
    )


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(product_id: str):
    """
    Get a single product by ID
    """
    product_data = lakebase_repo.get_product_by_id(product_id)

    if not product_data:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    product = ProductDetail(**product_data)
    product.image_url = f"/api/images/{product.image_path}"

    return product


@router.get("/filters/options", response_model=FilterOptions)
async def get_filter_options():
    """
    Get all available filter options for products
    """
    options = lakebase_repo.get_filter_options()
    return FilterOptions(**options)
