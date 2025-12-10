"""
CLIP Model Serving service for generating IMAGE embeddings only
Endpoint: clip-image-encoder (IMAGE ONLY - no text support)
Dimension: 512 (ViT-B/32)
"""
import base64
import logging
import numpy as np
import os

logger = logging.getLogger(__name__)


class CLIPService:
    """Service for interacting with CLIP model serving endpoint (IMAGE ONLY)"""
    
    def __init__(self):
        self.endpoint_name = "clip-image-encoder"
        self.workspace_host = os.getenv("DATABRICKS_HOST", "")
        if not self.workspace_host.startswith("http"):
            self.workspace_host = f"https://{self.workspace_host}"
        self.embedding_dim = 512  # CLIP ViT-B/32
        
        logger.info(f"🔧 CLIPService initialized: endpoint={self.endpoint_name}, dim={self.embedding_dim}")
        
    def _get_endpoint_url(self) -> str:
        """Construct the full endpoint URL"""
        return f"{self.workspace_host}/serving-endpoints/{self.endpoint_name}/invocations"
    
    def _get_auth_headers(self) -> dict:
        """Get authorization headers with fresh OAuth token"""
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        token = w.config.oauth_token().access_token
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    async def get_image_embedding(self, image_bytes: bytes) -> np.ndarray:
        """
        Generate CLIP embedding for an image
        
        Args:
            image_bytes: Raw image bytes (JPEG, PNG, etc.)
            
        Returns:
            numpy array of shape (512,) - L2 normalized embedding
        """
        import aiohttp
        
        try:
            # Encode image to base64
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            
            # Prepare payload in dataframe_records format (pyfunc model)
            payload = {
                "dataframe_records": [{"image": image_b64}]
            }
            
            logger.info(f"Calling CLIP endpoint for image embedding (size: {len(image_bytes)} bytes)")
            
            # Call Model Serving endpoint
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self._get_endpoint_url(),
                    json=payload,
                    headers=self._get_auth_headers()
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"CLIP endpoint error {response.status}: {error_text}")
                        raise Exception(f"CLIP endpoint returned {response.status}")
                    
                    result = await response.json()
            
            # Debug: Log the raw response (first 200 chars)
            logger.info(f"CLIP raw response: {str(result)[:200]}...")
            
            # ✅ Parse response - based on actual format from logs
            # Format: {'predictions': [0.0121, 0.0134, -0.0073, ...]} - flat array of 512 floats
            embedding = None
            
            if isinstance(result, dict) and "predictions" in result:
                predictions = result["predictions"]
                if isinstance(predictions, list) and len(predictions) > 0:
                    # Check if it's a flat array or nested
                    if isinstance(predictions[0], (int, float)):
                        # Flat array: [0.0121, 0.0134, ...]
                        embedding = np.array(predictions, dtype=np.float32)
                    elif isinstance(predictions[0], list):
                        # Nested array: [[0.0121, 0.0134, ...]]
                        embedding = np.array(predictions[0], dtype=np.float32)
            elif isinstance(result, list):
                # Direct array format
                if len(result) > 0:
                    if isinstance(result[0], (int, float)):
                        embedding = np.array(result, dtype=np.float32)
                    elif isinstance(result[0], list):
                        embedding = np.array(result[0], dtype=np.float32)
            
            if embedding is None or embedding.size == 0:
                logger.error(f"Failed to parse embedding from response. Full response: {result}")
                raise Exception("Could not extract embedding from CLIP response")
            
            # Flatten if needed
            if embedding.ndim > 1:
                embedding = embedding.flatten()
            
            # Verify shape
            if embedding.shape[0] != self.embedding_dim:
                logger.error(f"Wrong embedding dimension: got {embedding.shape[0]}, expected {self.embedding_dim}")
                raise Exception(f"Expected {self.embedding_dim}-dim embedding, got {embedding.shape[0]}")
            
            # Ensure L2 normalization (for cosine similarity on VS)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            else:
                logger.error("Embedding has zero norm!")
                raise Exception("Invalid embedding: zero norm")
            
            logger.info(f"✅ Generated image embedding: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating image embedding: {type(e).__name__}: {e}")
            raise


# Singleton instance
clip_service = CLIPService()