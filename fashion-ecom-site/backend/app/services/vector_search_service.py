
"""
Vector Search Service
Integrates with Databricks Vector Search for similarity search
"""
from typing import List, Dict, Any, Optional
import numpy as np
from databricks.vector_search.client import VectorSearchClient
from app.core.config import settings


class VectorSearchService:
    """Service for querying Databricks Vector Search index."""

    def __init__(self):
        self.workspace_url = settings.VECTOR_SEARCH_ENDPOINT_URL
        self.index_name = settings.VECTOR_SEARCH_INDEX_NAME
        self.token = settings.DATABRICKS_TOKEN
        
        if not self.workspace_url:
            raise ValueError("VECTOR_SEARCH_ENDPOINT_URL must be configured")
        if not self.token:
            raise ValueError("DATABRICKS_TOKEN must be configured")
            
        # Initialize Vector Search client
        self.client = VectorSearchClient(
            workspace_url=self.workspace_url,
            personal_access_token=self.token
        )
        
        # Get the index
        try:
            self.index = self.client.get_index(
                index_name=self.index_name
            )
        except Exception as e:
            raise ValueError(f"Failed to connect to Vector Search index {self.index_name}: {e}")

    def similarity_search(
        self,
        query_vector: np.ndarray,
        num_results: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search using a query vector.
        
        Args:
            query_vector: Query embedding vector
            num_results: Number of results to return
            filters: Optional metadata filters (e.g., {"gender": "Women"})
            
        Returns:
            List of results with product_id and similarity score
        """
        # Convert numpy array to list if needed
        if isinstance(query_vector, np.ndarray):
            query_vector = query_vector.tolist()
        
        # Perform similarity search
        try:
            results = self.index.similarity_search(
                query_vector=query_vector,
                columns=["product_id", "image_path"],
                num_results=num_results,
                filters=filters
            )
            
            # Parse results
            parsed_results = []
            if hasattr(results, 'get') and 'result' in results:
                data_array = results['result'].get('data_array', [])
            elif hasattr(results, 'data_array'):
                data_array = results.data_array
            else:
                data_array = results
            
            for item in data_array:
                parsed_results.append({
                    "product_id": item.get("product_id"),
                    "score": item.get("score", 0.0),
                    "image_path": item.get("image_path")
                })
            
            return parsed_results
            
        except Exception as e:
            raise RuntimeError(f"Vector search failed: {e}")


# Global service instance
vector_search_service = VectorSearchService()
