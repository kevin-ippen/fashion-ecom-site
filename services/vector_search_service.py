"""
Vector Search service for similarity queries across multiple indexes
Supports: Image search, Text search, Hybrid search
"""
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from databricks.vector_search.client import VectorSearchClient
from databricks.sdk import WorkspaceClient
from core.config import settings

logger = logging.getLogger(__name__)


class VectorSearchService:
    """Service for Vector Search similarity queries with multiple indexes"""

    def __init__(self):
        self.endpoint_name = settings.VS_ENDPOINT_NAME
        self.embedding_dim = settings.CLIP_EMBEDDING_DIM

        # Unified index for all search types (image/text/hybrid)
        self.index_name = settings.VS_INDEX

        self.workspace_host = settings.DATABRICKS_WORKSPACE_URL

        logger.info(f"🔧 VectorSearchService initialized (fashion_sota unified index)")
        logger.info(f"   Endpoint: {self.endpoint_name}")
        logger.info(f"   Index: {self.index_name}")

    def _get_client(self) -> VectorSearchClient:
        """Get or create Vector Search client with OAuth authentication"""
        # ALWAYS get a fresh OAuth token (they expire after ~1 hour)
        # Don't cache the client to avoid stale token issues
        w = WorkspaceClient()
        token = w.config.oauth_token().access_token

        # Pass token explicitly to VectorSearchClient
        client = VectorSearchClient(
            workspace_url=self.workspace_host,
            personal_access_token=token,
            disable_notice=True
        )
        logger.debug(f"✅ Created Vector Search client with fresh OAuth token")
        return client

    def _get_index(self, index_name: str):
        """Get Vector Search index by name (no caching to avoid stale tokens)"""
        logger.debug(f"🔍 Getting Vector Search index: '{index_name}'")

        if not index_name:
            raise ValueError("Index name is empty or None!")

        # Always get fresh client with fresh OAuth token
        client = self._get_client()
        index = client.get_index(index_name=index_name)

        logger.debug(f"✅ Connected to Vector Search index: {index_name}")

        return index

    async def search(
        self,
        query_vector: np.ndarray,
        index_name: str,
        num_results: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Flexible vector similarity search across any index

        Args:
            query_vector: Normalized embedding vector (512 dims)
            index_name: Which index to search (image/text/hybrid)
            num_results: Number of results to return
            filters: Optional filters (e.g., {"master_category": "Apparel", "price >=": 50})
            columns: Columns to return (defaults to standard product columns)

        Returns:
            List of product dictionaries with similarity scores
        """
        try:
            # Ensure vector is normalized and correct shape
            if query_vector.shape != (self.embedding_dim,):
                raise ValueError(f"Expected vector shape ({self.embedding_dim},), got {query_vector.shape}")

            # Ensure L2 normalization for cosine similarity
            norm = np.linalg.norm(query_vector)
            if norm > 0:
                query_vector = query_vector / norm

            logger.info(f"Vector Search query:")
            logger.info(f"  Index: {index_name}")
            logger.info(f"  Vector: dim={query_vector.shape[0]}, norm={np.linalg.norm(query_vector):.4f}")
            logger.info(f"  Filters: {filters}")
            logger.info(f"  Num results: {num_results}")

            # Get index
            index = self._get_index(index_name)

            # Default columns if not specified
            # IMPORTANT: Only request columns that exist in the index
            # Index source: main.fashion_sota.product_embeddings
            if columns is None:
                columns = [
                    "product_id",
                    "product_display_name",
                    "master_category",
                    "sub_category",
                    "gender",
                    "base_color",
                    "image_path"
                ]

            # Perform similarity search (sync call, wrap in executor)
            import asyncio
            loop = asyncio.get_event_loop()

            def do_search():
                return index.similarity_search(
                    query_vector=query_vector.tolist(),
                    columns=columns,
                    num_results=num_results,
                    filters=filters or {}  # Empty dict if no filters
                )

            results = await loop.run_in_executor(None, do_search)

            # Parse results with improved error handling
            if "result" not in results:
                logger.warning(f"Unexpected Vector Search response format (missing 'result'): {results}")
                return []

            result = results["result"]

            # Check if data_array exists
            if "data_array" not in result:
                # Handle empty results gracefully
                row_count = result.get("row_count", 0)
                if row_count == 0:
                    logger.info("✅ Vector Search returned 0 results (no matches found)")
                    return []
                else:
                    logger.warning(f"Unexpected result format (missing 'data_array'): {results}")
                    return []

            data_array = result["data_array"]
            logger.info(f"✅ Vector Search returned {len(data_array)} results")

            # Convert to list of dicts
            # Vector Search automatically appends the score as the LAST element in each row
            products = []
            for i, row in enumerate(data_array):
                # Check if row has more elements than requested columns (score is appended)
                if len(row) > len(columns):
                    # Last element is the similarity score
                    product = dict(zip(columns, row[:-1]))
                    product["score"] = row[-1]  # Add score separately

                    # Debug logging for first result
                    if i == 0:
                        logger.info(f"📊 First result score debugging:")
                        logger.info(f"   Row length: {len(row)}, Columns: {len(columns)}")
                        logger.info(f"   Last element (score): {row[-1]} (type: {type(row[-1])})")
                        logger.info(f"   Product dict keys: {list(product.keys())}")
                else:
                    # No score in response (shouldn't happen with similarity_search)
                    product = dict(zip(columns, row))
                    logger.warning(f"⚠️  Row {i}: No score found! Row length={len(row)}, Columns={len(columns)}")
                    logger.warning(f"   Row: {row}")

                products.append(product)

            # Log score statistics
            if products:
                scores = [p.get("score") for p in products if "score" in p]
                if scores:
                    logger.info(f"📈 Score statistics: min={min(scores):.4f}, max={max(scores):.4f}, unique={len(set(scores))}")
                else:
                    logger.warning(f"⚠️  No scores found in any of the {len(products)} products!")

            return products

        except Exception as e:
            logger.error(f"Vector Search error: {type(e).__name__}: {e}")
            raise

    async def search_image(
        self,
        query_vector: np.ndarray,
        num_results: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using image embeddings (visual similarity)
        Uses unified index - works seamlessly with image embeddings

        Args:
            query_vector: Image embedding (512 dims)
            num_results: Number of results
            filters: Optional filters

        Returns:
            List of visually similar products
        """
        return await self.search(
            query_vector=query_vector,
            index_name=self.index_name,  # Unified index
            num_results=num_results,
            filters=filters
        )

    async def search_text(
        self,
        query_vector: np.ndarray,
        num_results: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using text embeddings (semantic text similarity)
        Uses unified index - works seamlessly with text embeddings

        Args:
            query_vector: Text embedding (512 dims)
            num_results: Number of results
            filters: Optional filters

        Returns:
            List of semantically matching products
        """
        return await self.search(
            query_vector=query_vector,
            index_name=self.index_name,  # Unified index
            num_results=num_results,
            filters=filters
        )

    async def search_hybrid(
        self,
        query_vector: np.ndarray,
        num_results: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using hybrid embeddings (best overall quality)
        Uses unified index - works seamlessly with hybrid embeddings

        Args:
            query_vector: Hybrid embedding (512 dims)
            num_results: Number of results
            filters: Optional filters

        Returns:
            List of matching products (combines visual + semantic)
        """
        return await self.search(
            query_vector=query_vector,
            index_name=self.index_name,  # Unified index
            num_results=num_results,
            filters=filters
        )

    async def search_cross_modal(
        self,
        query_vector: np.ndarray,
        source_type: str,
        num_results: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Cross-modal search (legacy method - unified index handles all modalities automatically)

        With the unified index, cross-modal search is automatic since the index
        contains hybrid embeddings that work across text and image modalities.

        Args:
            query_vector: Embedding (512 dims)
            source_type: "text" or "image" (for logging only)
            num_results: Number of results
            filters: Optional filters

        Returns:
            List of cross-modal matching products
        """
        logger.info(f"🔀 Cross-modal search ({source_type} query) using unified index")

        return await self.search(
            query_vector=query_vector,
            index_name=self.index_name,  # Unified index handles all modalities
            num_results=num_results,
            filters=filters
        )


# Singleton instance
vector_search_service = VectorSearchService()