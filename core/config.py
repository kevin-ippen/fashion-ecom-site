import os
import logging
from typing import Optional, List

from pydantic_settings import BaseSettings, SettingsConfigDict
from databricks import sdk
from databricks.sdk.core import Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Pydantic v2 settings
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # App
    APP_NAME: str = os.getenv("DATABRICKS_APP_NAME", "Fashion Ecommerce API")
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = bool(os.getenv("DEBUG", "0") == "1")

    # Lakebase Postgres (env is injected when the Lakebase resource is attached to the app)
    LAKEBASE_HOST: str = os.getenv("PGHOST", "")
    LAKEBASE_PORT: int = int(os.getenv("PGPORT", "5432"))
    LAKEBASE_DATABASE: str = os.getenv("PGDATABASE", "main")
    LAKEBASE_USER: str = os.getenv("PGUSER", "")  # SP in Apps; user locally
    LAKEBASE_SSL_MODE: str = "require"

    # Unity Catalog (source metadata)
    CATALOG: str = "main"
    SCHEMA: str = "fashion_demo"

    # Lakebase synced tables (Postgres side)
    LAKEBASE_SCHEMA: str = "fashion_demo"
    LAKEBASE_PRODUCTS_TABLE: str = "productsdb"
    LAKEBASE_USERS_TABLE: str = "usersdb"
    LAKEBASE_EMBEDDINGS_TABLE: str = "product_image_embeddingsdb"
    LAKEBASE_USER_FEATURES_TABLE: str = "user_style_featuresdb"
    
    # CLIP Model Serving
    CLIP_ENDPOINT: str = "clip-image-encoder"
    CLIP_EMBEDDING_DIM: int = 512

    # Vector Search
    VS_ENDPOINT_NAME: str = "fashion_vector_search"
    VS_ENDPOINT_ID: str = "4d329fc8-1924-4131-ace8-14b542f8c14b"
    VS_INDEX_NAME: str = "main.fashion_demo.product_embeddings_index"

    # Aliases for backward compatibility (without LAKEBASE_ prefix)
    @property
    def PRODUCTS_TABLE(self) -> str:
        return self.LAKEBASE_PRODUCTS_TABLE
    
    @property
    def USERS_TABLE(self) -> str:
        return self.LAKEBASE_USERS_TABLE
    
    @property
    def EMBEDDINGS_TABLE(self) -> str:
        return self.LAKEBASE_EMBEDDINGS_TABLE
    
    @property
    def USER_FEATURES_TABLE(self) -> str:
        return self.LAKEBASE_USER_FEATURES_TABLE

    # Model Serving
    CLIP_ENDPOINT: Optional[str] = os.getenv("CLIP_ENDPOINT")

    # API
    API_PREFIX: str = "/api"
    CORS_ORIGINS: List[str] = ["*"]

    # Pagination
    DEFAULT_PAGE_SIZE: int = 24
    MAX_PAGE_SIZE: int = 100

    @property
    def lakebase_sqlalchemy_url(self) -> str:
        """
        Build SQLAlchemy URL for asyncpg with OAuth token injection.
        Password will be set dynamically via connection string at runtime.
        """
        if not (self.LAKEBASE_HOST and self.LAKEBASE_USER):
            raise RuntimeError(
                "Missing PGHOST/PGUSER env. Ensure the Lakebase resource is attached to the app "
                "so the Postgres host and user are injected into the app environment."
            )
        
        # Get fresh OAuth token
        try:
            token = workspace_client.config.oauth_token().access_token
            logger.info("✓ Retrieved OAuth token for Lakebase connection")
        except Exception as e:
            logger.error(f"❌ Failed to get OAuth token: {e}")
            raise
        
        # Build connection string with token as password (asyncpg format)
        return (
            f"postgresql+asyncpg://{self.LAKEBASE_USER}:{token}@"
            f"{self.LAKEBASE_HOST}:{self.LAKEBASE_PORT}/{self.LAKEBASE_DATABASE}"
        )

    def fq_pg(self, table_name: str) -> str:
        """Fully-qualified Postgres table name."""
        return f"{self.LAKEBASE_SCHEMA}.{table_name}"

# Instantiate settings
settings = Settings()

# Databricks SDK workspace client (OAuth M2M; auto-refresh via unified auth)
app_config = Config()  # picks up DATABRICKS_HOST, CLIENT_ID/SECRET, WORKSPACE_ID from env
workspace_client = sdk.WorkspaceClient()

def get_bearer_headers() -> dict:
    """
    Helper for calling Databricks services (e.g., Model Serving) with a fresh OAuth token.
    """
    token = workspace_client.config.oauth_token().access_token
    return {"Authorization": f"Bearer {token}"}