"""
Vector Search service for similarity queries - FIXED AUTHENTICATION
Endpoint: fashion_vector_search (4d329fc8-1924-4131-ace8-14b542f8c14b)
Index: main.fashion_demo.product_embeddings_index
"""
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from databricks.vector_search.client import VectorSearchClient
from databricks.sdk import WorkspaceClient
import os

logger = logging.getLogger(__name__)


class VectorSearchService:
    """Service for Vector Search similarity queries"""
    
    def __init__(self):
        self.endpoint_name = "fashion_vector_search"
        self.endpoint_id = "4d329fc8-1924-4131-ace8-14b542f8c14b"
        self.index_name = "main.fashion_demo.product_embeddings_index"
        self.embedding_dim = 512
        self.workspace_host = os.getenv("DATABRICKS_HOST", "")
        if not self.workspace_host.startswith("http"):
            self.workspace_host = f"https://{self.workspace_host}"
        self._client = None
        self._index = None
    
    def _get_client(self) -> VectorSearchClient:
        """Get or create Vector Search client with OAuth authentication"""
        if self._client is None:
            # ✅ FIX: Get OAuth token from WorkspaceClient
            w = WorkspaceClient()
            token = w.config.oauth_token().access_token
            
            # ✅ FIX: Pass token explicitly to VectorSearchClient
            self._client = VectorSearchClient(
                workspace_url=self.workspace_host,
                personal_access_token=token,  # ← This was missing!
                disable_notice=True
            )
            logger.info(f"✅ Created Vector Search client for {self.workspace_host}")
        return self._client
    
    def _get_index(self):
        """Get Vector Search index"""
        if self._index is None:
            client = self._get_client()
            self._index = client.get_index(self.index_name)
            logger.info(f"✅ Connected to Vector Search index: {self.index_name}")
        return self._index
    
    async def similarity_search(
        self,
        query_vector: np.ndarray,
        num_results: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar products using vector similarity
        
        Args:
            query_vector: Normalized embedding vector (512 dims)
            num_results: Number of results to return
            filters: Optional filters (e.g., {"price >= ": 50})
            
        Returns:
            List of product dictionaries with similarity scores
        """
        try:
            # Ensure vector is normalized and correct shape
            if query_vector.shape != (self.embedding_dim,):
                raise ValueError(f"Expected vector shape ({self.embedding_dim},), got {query_vector.shape}")
            
            # Ensure L2 normalization for cosine-like similarity
            norm = np.linalg.norm(query_vector)
            if norm > 0:
                query_vector = query_vector / norm
            
            logger.info(f"Vector Search query: dim={query_vector.shape[0]}, norm={np.linalg.norm(query_vector):.4f}, filters={filters}")
            
            # Get index and perform similarity search
            index = self._get_index()
            
            # Columns to return from the index
            columns = [
                "product_id",
                "product_display_name", 
                "master_category",
                "sub_category",
                "article_type",
                "base_color",
                "price",
                "image_path",
                "gender",
                "season",
                "usage",
                "year"
            ]
            
            # Perform similarity search
            # Note: Vector Search SDK is synchronous, wrap in executor
            import asyncio
            loop = asyncio.get_event_loop()
            
            def do_search():
                return index.similarity_search(
                    query_vector=query_vector.tolist(),
                    columns=columns,
                    num_results=num_results,
                    filters=filters
                )
            
            results = await loop.run_in_executor(None, do_search)
            
            # Parse results
            if "result" in results and "data_array" in results["result"]:
                data_array = results["result"]["data_array"]
                logger.info(f"✅ Vector Search returned {len(data_array)} results")
                
                # Convert to list of dicts
                products = []
                for row in data_array:
                    product = dict(zip(columns, row))
                    products.append(product)
                
                return products
            else:
                logger.warning(f"Unexpected Vector Search response format: {results}")
                return []
                
        except Exception as e:
            logger.error(f"Vector Search error: {type(e).__name__}: {e}")
            raise


# Singleton instance
vector_search_service = VectorSearchService()