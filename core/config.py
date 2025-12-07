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
    LAKEBASE_DATABASE: str = os.getenv("LAKEBASE_DATABASE", "main")  # Database name from Lakebase instance
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

        Authentication strategy (in order of precedence):
        1. LAKEBASE_PASSWORD environment variable (personal access token)
        2. DATABRICKS_TOKEN environment variable (workspace token)
        3. Fetch directly from Databricks Secrets API (redditscope.redditkey)
        """
        import logging
        logger = logging.getLogger(__name__)

        password = None
        token_source = None

        # Strategy 1: Try LAKEBASE_PASSWORD env var
        if self.LAKEBASE_PASSWORD:
            password = self.LAKEBASE_PASSWORD
            token_source = "LAKEBASE_PASSWORD (env var)"
            logger.info(f"✓ Using LAKEBASE_PASSWORD environment variable")

        # Strategy 2: Try DATABRICKS_TOKEN env var
        elif self.DATABRICKS_TOKEN:
            password = self.DATABRICKS_TOKEN
            token_source = "DATABRICKS_TOKEN (env var)"
            logger.warning(f"⚠️  LAKEBASE_PASSWORD not set - falling back to DATABRICKS_TOKEN")

        # Strategy 3: Try fetching from Databricks Secrets API directly
        else:
            logger.warning("⚠️  No environment variables set - attempting to fetch from Databricks Secrets API")
            try:
                from databricks.sdk import WorkspaceClient
                w = WorkspaceClient()
                password = w.dbutils.secrets.get(scope="redditscope", key="redditkey")
                token_source = "Databricks Secrets API (redditscope.redditkey)"
                logger.info(f"✓ Successfully fetched password from Databricks Secrets API")
            except Exception as e:
                logger.error(f"❌ Failed to fetch secret from Databricks Secrets API: {e}")
                logger.error("  → All authentication strategies exhausted!")
                password = ""

        # Log token preview (mask sensitive data)
        if password:
            token_preview = password[:8] + "..." if len(password) > 8 else "***"
            logger.info(f"✓ Lakebase auth: Using {token_source} (starts with: {token_preview})")
        else:
            logger.error("⚠️  LAKEBASE AUTHENTICATION ERROR: No password/token available!")
            logger.error("  Tried:")
            logger.error("    1. LAKEBASE_PASSWORD environment variable")
            logger.error("    2. DATABRICKS_TOKEN environment variable")
            logger.error("    3. Databricks Secrets API (redditscope.redditkey)")

        return (
            f"postgresql+asyncpg://{self.LAKEBASE_USER}:{password}@"
            f"{self.LAKEBASE_HOST}:{self.LAKEBASE_PORT}/{self.LAKEBASE_DATABASE}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
