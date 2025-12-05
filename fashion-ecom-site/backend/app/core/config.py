
"""
Application configuration and settings
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # App
    APP_NAME: str = "Fashion Ecommerce API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Databricks - will be auto-populated by Databricks Apps
    DATABRICKS_HOST: Optional[str] = os.getenv("DATABRICKS_HOST")
    DATABRICKS_TOKEN: Optional[str] = os.getenv("DATABRICKS_TOKEN")
    DATABRICKS_HTTP_PATH: Optional[str] = os.getenv("DATABRICKS_HTTP_PATH")

    # Unity Catalog
    CATALOG: str = "main"
    SCHEMA: str = "fashion_demo"
    PRODUCTS_TABLE: str = "products"
    USERS_TABLE: str = "users"
    EMBEDDINGS_TABLE: str = "product_image_embeddings"
    USER_FEATURES_TABLE: str = "user_style_features"

    # UC Volume for images
    IMAGES_VOLUME_PATH: str = "/Volumes/main/fashion_demo/raw_data/images/"

    # Model Serving
    CLIP_ENDPOINT: str = os.getenv(
        "CLIP_ENDPOINT",
        "https://adb-984752964297111.11.azuredatabricks.net/serving-endpoints/clip-image-encoder/invocations"
    )
    CLIP_TOKEN: Optional[str] = os.getenv("DATABRICKS_TOKEN")
    
    # Vector Search
    VECTOR_SEARCH_ENDPOINT_URL: str = os.getenv(
        "VECTOR_SEARCH_ENDPOINT_URL",
        "https://adb-984752964297111.11.azuredatabricks.net"
    )
    VECTOR_SEARCH_INDEX_NAME: str = os.getenv(
        "VECTOR_SEARCH_INDEX_NAME",
        "main.fashion_demo.product_embeddings_index"
    )

    # API
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list = ["*"]  # Update for production

    # Pagination
    DEFAULT_PAGE_SIZE: int = 24
    MAX_PAGE_SIZE: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
