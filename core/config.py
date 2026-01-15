"""
Updated configuration for Fashion SOTA schema migration
To activate: Copy this file to config.py or merge changes into existing config.py
"""
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
    APP_VERSION: str = "2.0.0"  # Bumped for fashion_sota migration
    DEBUG: bool = bool(os.getenv("DEBUG", "0") == "1")

    # Lakebase Postgres (env is injected when the Lakebase resource is attached to the app)
    # For local development, set PGHOST, PGUSER in your .env file
    LAKEBASE_HOST: str = os.getenv("PGHOST", "")
    LAKEBASE_PORT: int = int(os.getenv("PGPORT", "5432"))
    LAKEBASE_DATABASE: str = os.getenv("PGDATABASE", "databricks_postgres")
    LAKEBASE_USER: str = os.getenv("PGUSER", "")
    LAKEBASE_SSL_MODE: str = "require"

    # Unity Catalog (source metadata) - UPDATED FOR FASHION_SOTA
    CATALOG: str = "main"
    SCHEMA: str = "fashion_sota"  # Changed from fashion_demo

    # Unity Catalog Tables - Using Lakebase-synced tables in UC
    # These are foreign tables in UC that sync from Lakebase PostgreSQL
    UC_PRODUCTS_TABLE: str = "main.fashion_sota.products_filtered_lakebase"  # Filtered products with outfit pairings
    UC_PRODUCT_EMBEDDINGS_TABLE: str = "main.fashion_sota.product_embeddings_us_relevant"  # For vector search
    UC_USERS_TABLE: str = "main.fashion_sota.users"  # User accounts
    UC_USER_PREFERENCES_TABLE: str = "main.fashion_sota.user_preferences"  # User preferences

    # Lakebase table names (PostgreSQL schema.table format)
    LAKEBASE_SCHEMA: str = "fashion_sota"
    LAKEBASE_PRODUCTS_TABLE: str = "products_filtered_lakebase"
    LAKEBASE_USERS_TABLE: str = "users_lakebase"  # fashion_sota.users_lakebase (taste_embedding as JSON string)

    # Databricks Workspace
    @property
    def DATABRICKS_WORKSPACE_URL(self) -> str:
        """Get workspace URL from env or construct from DATABRICKS_HOST"""
        # First try explicit DATABRICKS_WORKSPACE_URL
        workspace_url = os.getenv("DATABRICKS_WORKSPACE_URL")
        if workspace_url:
            if not workspace_url.startswith("http"):
                return f"https://{workspace_url}"
            return workspace_url

        # Fall back to DATABRICKS_HOST (set by Databricks Apps)
        host = os.getenv("DATABRICKS_HOST")
        if host:
            if not host.startswith("http"):
                return f"https://{host}"
            return host

        # No default - must be configured via environment
        raise RuntimeError(
            "DATABRICKS_WORKSPACE_URL or DATABRICKS_HOST must be set. "
            "Set via environment variable or .env file."
        )

    # CLIP Multimodal Model Serving
    CLIP_ENDPOINT_NAME: str = "fashionclip-endpoint"  # FashionCLIP endpoint
    CLIP_UC_MODEL: str = "main.fashion_demo.clip_multimodal_encoder"  # Still in fashion_demo
    CLIP_EMBEDDING_DIM: int = 512

    # Vector Search Endpoint
    VS_ENDPOINT_NAME: str = os.getenv("VS_ENDPOINT_NAME", "one-env-shared-endpoint-15")

    # Vector Search Index - US relevant products
    VS_INDEX: str = os.getenv("VS_INDEX", "main.fashion_sota.product_embeddings_us_relevant_index")

    # SQL Warehouse for queries
    SQL_WAREHOUSE_ID: str = os.getenv("SQL_WAREHOUSE_ID", "")

    # Legacy indexes - REMOVED (no longer needed with unified index)
    # VS_IMAGE_INDEX: str = "main.fashion_demo.vs_image_search"  # DELETED
    # VS_TEXT_INDEX: str = "main.fashion_demo.vs_text_search"  # DELETED
    # VS_HYBRID_INDEX: str = "main.fashion_demo.vs_hybrid_search"  # DELETED

    @property
    def CLIP_ENDPOINT_URL(self) -> str:
        """Full URL to CLIP model serving endpoint"""
        return f"{self.DATABRICKS_WORKSPACE_URL}/serving-endpoints/{self.CLIP_ENDPOINT_NAME}/invocations"

    # Aliases for backward compatibility - Point to fully qualified UC tables
    @property
    def PRODUCTS_TABLE(self) -> str:
        """Fully qualified Unity Catalog table name for products"""
        return self.UC_PRODUCTS_TABLE

    @property
    def USERS_TABLE(self) -> str:
        """Fully qualified Unity Catalog table name for users"""
        return self.UC_USERS_TABLE

    @property
    def EMBEDDINGS_TABLE(self) -> str:
        """Fully qualified Unity Catalog table name for embeddings"""
        return self.UC_PRODUCT_EMBEDDINGS_TABLE

    @property
    def USER_FEATURES_TABLE(self) -> str:
        """Fully qualified Unity Catalog table name for user preferences"""
        return self.UC_USER_PREFERENCES_TABLE

    # API
    API_PREFIX: str = "/api"
    CORS_ORIGINS: List[str] = ["*"]

    # Pagination
    DEFAULT_PAGE_SIZE: int = 24
    MAX_PAGE_SIZE: int = 100

    # Image Serving - UPDATED FOR FASHION_SOTA
    @property
    def IMAGE_VOLUME_PATH(self) -> str:
        """Path to product images in Unity Catalog Volumes"""
        return f"/Volumes/{self.CATALOG}/{self.SCHEMA}/product_images"

    def get_image_url(self, product_id: int) -> str:
        """
        Construct Files API URL for product image
        Updated for fashion_sota volume structure
        """
        return f"{self.DATABRICKS_WORKSPACE_URL}/ajax-api/2.0/fs/files{self.IMAGE_VOLUME_PATH}/{product_id}.jpg"

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


# ============================================================================
# Migration Info
# ============================================================================

MIGRATION_INFO = {
    "version": "2.0.0",
    "schema": "fashion_sota",
    "changes": [
        "Migrated from main.fashion_demo to main.fashion_sota",
        "Unified vector search index (1 index instead of 3)",
        "Denormalized product embeddings (metadata + embeddings in one table)",
        "Updated image volume path",
        "Simplified table naming (removed 'db' suffix)",
        "Added brand metadata",
        "43,916 validated products (down from 44,424 - quality filtered)"
    ],
    "breaking_changes": [
        "Vector search index names changed",
        "Image URLs updated (new volume path)",
        "Product IDs may differ (filtered dataset)",
        "Lakebase schema changed to fashion_sota"
    ]
}

# Log migration info on startup
logger.info("=" * 80)
logger.info("Fashion SOTA Configuration Active")
logger.info("=" * 80)
logger.info(f"Schema: {settings.SCHEMA}")
logger.info(f"Lakebase Schema: {settings.LAKEBASE_SCHEMA}")
logger.info(f"Products Table: {settings.LAKEBASE_PRODUCTS_TABLE}")
logger.info(f"Vector Search Index: {settings.VS_INDEX}")
logger.info(f"Vector Search Endpoint: {settings.VS_ENDPOINT_NAME}")
logger.info(f"Image Volume: {settings.IMAGE_VOLUME_PATH}")
logger.info("=" * 80)
