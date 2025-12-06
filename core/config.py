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

    # Lakebase PostgreSQL
    LAKEBASE_HOST: str = os.getenv(
        "LAKEBASE_HOST",
        "instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net"
    )
    LAKEBASE_PORT: int = 5432
    LAKEBASE_DATABASE: str = os.getenv("LAKEBASE_DATABASE", "databricks_postgres")
    LAKEBASE_USER: str = os.getenv("LAKEBASE_USER", "kevin.ippen@databricks.com")  # Databricks email
    LAKEBASE_PASSWORD: Optional[str] = os.getenv("LAKEBASE_PASSWORD")  # Personal access token or workspace token
    LAKEBASE_SSL_MODE: str = os.getenv("LAKEBASE_SSL_MODE", "require")  # SSL: disable, allow, prefer, require, verify-ca, verify-full

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

    @property
    def lakebase_url(self) -> str:
        """Build PostgreSQL connection URL for Lakebase with asyncpg driver

        Note: SSL is handled via connect_args in database.py, not in the URL.
        asyncpg does not accept sslmode as a URL parameter.

        Authentication: Use LAKEBASE_PASSWORD (personal access token) if set,
        otherwise fall back to DATABRICKS_TOKEN (workspace token).
        """
        # Use dedicated Lakebase password if set, otherwise fall back to workspace token
        password = self.LAKEBASE_PASSWORD or self.DATABRICKS_TOKEN or ""
        return (
            f"postgresql+asyncpg://{self.LAKEBASE_USER}:{password}@"
            f"{self.LAKEBASE_HOST}:{self.LAKEBASE_PORT}/{self.LAKEBASE_DATABASE}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
