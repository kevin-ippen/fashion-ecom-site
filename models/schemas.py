"""
Pydantic models matching Databricks Unity Catalog table schemas
"""
from datetime import datetime
from typing import Optional, List, Union
from pydantic import BaseModel, Field, field_validator


class Product(BaseModel):
    """Product catalog model - matches main.fashion_demo.products"""
    product_id: str
    gender: Optional[str] = None
    master_category: Optional[str] = None
    sub_category: Optional[str] = None
    article_type: Optional[str] = None
    base_color: Optional[str] = None
    season: Optional[str] = None  # ✅ Now accepts NULL
    year: Optional[int] = None
    usage: Optional[str] = None
    product_display_name: Optional[str] = None  # Can be NULL in database
    price: Optional[float] = None
    image_path: Optional[str] = None
    ingested_at: Optional[datetime] = None

    @field_validator('product_id', mode='before')
    @classmethod
    def coerce_product_id_to_str(cls, v: Union[str, int]) -> str:
        """Convert product_id to string if it's an int (handles DB type mismatch)"""
        return str(v) if v is not None else None

    class Config:
        from_attributes = True


class ProductDetail(Product):
    """Extended product model with additional computed fields"""
    image_url: Optional[str] = None
    similarity_score: Optional[float] = None
    personalization_reason: Optional[str] = None


class ProductListResponse(BaseModel):
    """Response model for product list endpoints"""
    products: List[ProductDetail]
    total: int
    page: int
    page_size: int
    has_more: bool


class User(BaseModel):
    """User model - matches main.fashion_demo.users"""
    user_id: str
    avg_price_point: float
    created_date: datetime
    preferred_categories: List[str]
    segment: str

    @field_validator('user_id', mode='before')
    @classmethod
    def coerce_user_id_to_str(cls, v: Union[str, int]) -> str:
        """Convert user_id to string if it's an int (handles DB type mismatch)"""
        return str(v) if v is not None else None

    class Config:
        from_attributes = True


class UserStyleFeatures(BaseModel):
    """User style features - matches main.fashion_demo.user_style_features"""
    user_id: str
    segment: str
    category_prefs: List[str]
    brand_prefs: Optional[List[str]] = []
    color_prefs: List[str]
    min_price: float
    max_price: float
    avg_price: float
    p25_price: float
    p75_price: float
    user_embedding: List[float]
    num_interactions: int
    created_at: datetime

    @field_validator('user_id', mode='before')
    @classmethod
    def coerce_user_id_to_str(cls, v: Union[str, int]) -> str:
        """Convert user_id to string if it's an int (handles DB type mismatch)"""
        return str(v) if v is not None else None

    class Config:
        from_attributes = True


class UserProfile(BaseModel):
    """Combined user profile for display"""
    user_id: str
    segment: str
    avg_price_point: float
    preferred_categories: List[str]
    color_prefs: List[str]
    price_range: dict  # min, max, avg
    num_interactions: int
    purchase_history: List[ProductDetail] = []


class ProductImageEmbedding(BaseModel):
    """Product image embeddings - matches main.fashion_demo.product_image_embeddings"""
    product_id: str
    image_embedding: List[float]
    embedding_model: str
    embedding_dimension: int
    created_at: datetime

    @field_validator('product_id', mode='before')
    @classmethod
    def coerce_product_id_to_str(cls, v: Union[str, int]) -> str:
        """Convert product_id to string if it's an int (handles DB type mismatch)"""
        return str(v) if v is not None else None

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    """Request model for text search"""
    query: str
    user_id: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    filters: Optional[dict] = None


class ImageSearchRequest(BaseModel):
    """Request model for image search"""
    user_id: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    filters: Optional[dict] = None


class SearchResponse(BaseModel):
    """Response model for search endpoints"""
    products: List[ProductDetail]
    query: Optional[str] = None
    search_type: str  # "text", "image", or "hybrid"
    user_id: Optional[str] = None


class CartItem(BaseModel):
    """Shopping cart item"""
    product_id: str
    quantity: int = Field(default=1, ge=1)
    product: Optional[ProductDetail] = None


class Cart(BaseModel):
    """Shopping cart"""
    items: List[CartItem] = []
    total: float = 0.0
    item_count: int = 0


class FilterOptions(BaseModel):
    """Available filter options for products"""
    genders: List[str]
    master_categories: List[str]
    sub_categories: List[str]
    article_types: List[str]
    colors: List[str]
    seasons: List[str]
    price_range: dict  # min and max
