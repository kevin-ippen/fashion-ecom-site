
"""
Search API routes (text and image search)
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
from app.models.schemas import SearchRequest, SearchResponse, ProductDetail
from app.repositories.lakebase import lakebase_repo
from app.services.clip_service import clip_service
from app.services.vector_search_service import vector_search_service
from app.services.recommendation_service import recommendation_service
import numpy as np

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/text", response_model=SearchResponse)
async def search_by_text(request: SearchRequest):
    """
    Search products by text query using CLIP text embeddings + Vector Search
    """
    try:
        # Generate text embedding using CLIP
        text_embedding = clip_service.get_text_embedding(request.query)
        
        # Perform vector search
        search_results = vector_search_service.similarity_search(
            query_vector=text_embedding,
            num_results=request.limit
        )
        
        # Extract product IDs and scores
        product_ids = [r["product_id"] for r in search_results]
        scores = [r["score"] for r in search_results]
        
        # Fetch full product details
        products_data = []
        for product_id in product_ids:
            product = lakebase_repo.get_product_by_id(str(product_id))
            if product:
                products_data.append(product)
        
        # Get user preferences if provided
        user_preferences = None
        if request.user_id:
            user_features = lakebase_repo.get_user_style_features(request.user_id)
            if user_features:
                user_preferences = user_features
        
        # Score and rank products
        scored_products = recommendation_service.score_products(
            products=products_data,
            visual_scores=scores,
            user_preferences=user_preferences
        )
        
        # Convert to ProductDetail
        products = []
        for p in scored_products:
            product = ProductDetail(**p)
            product.image_url = f"/api/images/{product.image_path}"
            products.append(product)
        
        return SearchResponse(
            products=products,
            query=request.query,
            search_type="text",
            user_id=request.user_id
        )
        
    except Exception as e:
        # Fallback to simple text search
        print(f"Error in text search: {e}")
        products_data = lakebase_repo.search_products_by_text(
            query=request.query,
            limit=request.limit
        )
        
        products = []
        for p in products_data:
            product = ProductDetail(**p)
            product.image_url = f"/api/images/{product.image_path}"
            product.similarity_score = 0.75
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
    limit: int = Form(20)
):
    """
    Search products by uploaded image using CLIP + Vector Search
    """
    try:
        # Read image bytes
        image_bytes = await image.read()
        
        # Generate image embedding using CLIP
        image_embedding = clip_service.get_embedding(image_bytes)
        
        # Perform vector search
        search_results = vector_search_service.similarity_search(
            query_vector=image_embedding,
            num_results=limit
        )
        
        # Extract product IDs and scores
        product_ids = [r["product_id"] for r in search_results]
        scores = [r["score"] for r in search_results]
        
        # Fetch full product details
        products_data = []
        for product_id in product_ids:
            product = lakebase_repo.get_product_by_id(str(product_id))
            if product:
                products_data.append(product)
        
        # Get user preferences if provided
        user_preferences = None
        if user_id:
            user_features = lakebase_repo.get_user_style_features(user_id)
            if user_features:
                user_preferences = user_features
        
        # Score and rank products
        scored_products = recommendation_service.score_products(
            products=products_data,
            visual_scores=scores,
            user_preferences=user_preferences
        )
        
        # Convert to ProductDetail
        products = []
        for p in scored_products:
            product = ProductDetail(**p)
            product.image_url = f"/api/images/{product.image_path}"
            products.append(product)
        
        return SearchResponse(
            products=products,
            query=None,
            search_type="image",
            user_id=user_id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Image search failed: {str(e)}"
        )


@router.get("/recommendations/{user_id}", response_model=SearchResponse)
async def get_recommendations(user_id: str, limit: int = 20):
    """
    Get personalized product recommendations for a user
    """
    try:
        # Get user style features
        user_features = lakebase_repo.get_user_style_features(user_id)
        if not user_features:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # If user has an embedding, use it for vector search
        if user_features.get("user_embedding"):
            user_embedding = np.array(user_features["user_embedding"])
            
            search_results = vector_search_service.similarity_search(
                query_vector=user_embedding,
                num_results=limit * 2
            )
            
            product_ids = [r["product_id"] for r in search_results]
            scores = [r["score"] for r in search_results]
            
            products_data = []
            for product_id in product_ids:
                product = lakebase_repo.get_product_by_id(str(product_id))
                if product:
                    products_data.append(product)
        else:
            # Fallback to filter-based recommendations
            filters = {}
            if user_features.get("p25_price") and user_features.get("p75_price"):
                filters["min_price"] = user_features["p25_price"] * 0.8
                filters["max_price"] = user_features["p75_price"] * 1.2
            
            products_data = lakebase_repo.get_products(
                limit=limit * 2,
                filters=filters
            )
            scores = [0.7] * len(products_data)
        
        # Score and rank products
        scored_products = recommendation_service.score_products(
            products=products_data,
            visual_scores=scores,
            user_preferences=user_features
        )
        
        # Apply diversity constraints
        diversified_products = recommendation_service.diversify_results(
            products=scored_products,
            max_per_category=3
        )
        
        final_products = diversified_products[:limit]
        
        # Convert to ProductDetail
        products = []
        for p in final_products:
            product = ProductDetail(**p)
            product.image_url = f"/api/images/{product.image_path}"
            products.append(product)
        
        return SearchResponse(
            products=products,
            query=None,
            search_type="personalized",
            user_id=user_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Recommendations failed: {str(e)}"
        )
