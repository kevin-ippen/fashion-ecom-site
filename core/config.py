"""Application configuration and settings"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger(__name__)


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
    LAKEBASE_DATABASE: str = os.getenv("LAKEBASE_DATABASE", "main")
    LAKEBASE_USER: str = os.getenv("LAKEBASE_USER", "kevin.ippen@databricks.com")
    LAKEBASE_PASSWORD: Optional[str] = os.getenv("LAKEBASE_PASSWORD")
    LAKEBASE_SSL_MODE: str = os.getenv("LAKEBASE_SSL_MODE", "require")

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
    CORS_ORIGINS: list = ["*"]

    # Pagination
    DEFAULT_PAGE_SIZE: int = 24
    MAX_PAGE_SIZE: int = 100

    def _get_oauth_token(self) -> Optional[tuple[str, str]]:
        """Generate OAuth token using service principal (bypasses IP ACL).
        
        Returns:
            Tuple of (username, token) if successful, None otherwise
        """
        client_id = os.getenv("DATABRICKS_CLIENT_ID")
        client_secret = os.getenv("DATABRICKS_CLIENT_SECRET")
        
        if not (client_id and client_secret):
            return None
        
        try:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            
            token_response = w.api_client.do(
                'POST',
                '/api/2.0/token/generate',
                data={'lifetime_seconds': 3600, 'comment': 'Lakebase access'}
            )
            oauth_token = token_response.get('access_token')
            
            if oauth_token:
                logger.info("✓ Using OAuth token (bypasses IP ACL)")
                return (client_id, oauth_token)
        except Exception as e:
            logger.warning(f"OAuth token generation failed: {e}")
        
        return None

    @property
    def lakebase_url(self) -> str:
        """Build PostgreSQL connection URL for Lakebase.
        
        Tries OAuth first (bypasses IP ACL), falls back to PAT token.
        """
        # Try OAuth first (preferred - bypasses IP ACL)
        oauth_result = self._get_oauth_token()
        if oauth_result:
            username, password = oauth_result
        else:
            # Fallback to PAT token
            username = self.LAKEBASE_USER
            password = self.LAKEBASE_PASSWORD or ""
            if password:
                logger.info("✓ Using PAT token from LAKEBASE_PASSWORD")
            else:
                logger.error("❌ No authentication available")
        
        return (
            f"postgresql+asyncpg://{username}:{password}@"
            f"{self.LAKEBASE_HOST}:{self.LAKEBASE_PORT}/{self.LAKEBASE_DATABASE}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()