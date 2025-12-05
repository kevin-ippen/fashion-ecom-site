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

    # Databricks
    DATABRICKS_HOST: Optional[str] = os.getenv("DATABRICKS_HOST")
    DATABRICKS_TOKEN: Optional[str] = os.getenv("DATABRICKS_TOKEN")
    DATABRICKS_HTTP_PATH: Optional[str] = os.getenv("DATABRICKS_HTTP_PATH")

    # Unity Catalog
    CATALOG: str = "main"
    SCHEMA: str = "fashion_demo"
    PRODUCTS_TABLE: str = "productsdb"
    USERS_TABLE: str = "usersdb"
    EMBEDDINGS_TABLE: str = "product_image_embeddingsdb"
    USER_FEATURES_TABLE: str = "user_style_featuresdb"

    # UC Volume for images
    IMAGES_VOLUME_PATH: str = "/Volumes/main/fashion_demo/raw_data/images/"

    # Model Serving
    CLIP_ENDPOINT: Optional[str] = os.getenv("CLIP_ENDPOINT")
    CLIP_TOKEN: Optional[str] = os.getenv("DATABRICKS_TOKEN")

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
