"""
CLIP Multimodal Model Serving service for generating TEXT and IMAGE embeddings
Text Endpoint: clip-multimodal-encoder (for text queries)
Image Endpoint: clip-image-encoder (for user-uploaded images)
Dimension: 512 (ViT-B/32)
"""
import base64
import logging
import numpy as np
from typing import Union, List
from core.config import settings

logger = logging.getLogger(__name__)


class CLIPService:
    """Service for interacting with CLIP model serving endpoints"""

    def __init__(self):
        # Two separate endpoints for text and image
        self.text_endpoint_name = "siglip-multimodal-endpoint"
        self.image_endpoint_name = "siglip-multimodal-endpoint"
        
        # Construct URLs
        base_url = settings.DATABRICKS_WORKSPACE_URL.rstrip('/')
        self.text_endpoint_url = f"{base_url}/serving-endpoints/{self.text_endpoint_name}/invocations"
        self.image_endpoint_url = f"{base_url}/serving-endpoints/{self.image_endpoint_name}/invocations"
        
        self.embedding_dim = settings.CLIP_EMBEDDING_DIM

        logger.info(f"🔧 CLIPService initialized")
        logger.info(f"   Text Endpoint: {self.text_endpoint_name}")
        logger.info(f"   Text URL: {self.text_endpoint_url}")
        logger.info(f"   Image Endpoint: {self.image_endpoint_name}")
        logger.info(f"   Image URL: {self.image_endpoint_url}")
        logger.info(f"   Dimension: {self.embedding_dim}")

    def _get_auth_headers(self) -> dict:
        """Get authorization headers with fresh OAuth token"""
        from core.config import get_bearer_headers
        return {
            **get_bearer_headers(),
            "Content-Type": "application/json"
        }

    async def get_text_embedding(self, text: str) -> np.ndarray:
        """
        Generate CLIP embedding for text using clip-multimodal-encoder

        Args:
            text: Text string to encode

        Returns:
            numpy array of shape (512,) - L2 normalized embedding
        """
        import aiohttp

        try:
            # Prepare payload in dataframe_records format (pyfunc model)
            payload = {
                "dataframe_records": [{"text": text}]
            }

            logger.info(f"Calling CLIP text endpoint: '{text[:100]}...'")

            # Call Model Serving endpoint (longer timeout for cold starts)
            timeout = aiohttp.ClientTimeout(total=120)  # 2 minutes for cold starts
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.text_endpoint_url,
                    json=payload,
                    headers=self._get_auth_headers()
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"CLIP text endpoint error {response.status}: {error_text}")
                        raise Exception(f"CLIP text endpoint returned {response.status}")

                    result = await response.json()

            # Parse and normalize embedding
            # clip-multimodal-encoder returns: {"predictions": [[0.01, 0.02, ...]]}
            embedding = self._parse_embedding(result, is_nested=True)
            logger.info(f"✅ Generated text embedding: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}")

            return embedding

        except Exception as e:
            logger.error(f"Error generating text embedding: {type(e).__name__}: {e}")
            raise

    async def get_image_embedding(self, image_bytes: bytes) -> np.ndarray:
        """
        Generate CLIP embedding for an image using clip-image-encoder

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

            logger.info(f"Calling CLIP image endpoint (size: {len(image_bytes)} bytes)")

            # Call Model Serving endpoint (longer timeout for cold starts)
            timeout = aiohttp.ClientTimeout(total=120)  # 2 minutes for cold starts
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.image_endpoint_url,
                    json=payload,
                    headers=self._get_auth_headers()
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"CLIP image endpoint error {response.status}: {error_text}")
                        raise Exception(f"CLIP image endpoint returned {response.status}")

                    result = await response.json()

            # Parse and normalize embedding
            # clip-image-encoder returns: {"predictions": [0.01, 0.02, ...]} (flat array)
            embedding = self._parse_embedding(result, is_nested=False)
            logger.info(f"✅ Generated image embedding: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}")

            return embedding

        except Exception as e:
            logger.error(f"Error generating image embedding: {type(e).__name__}: {e}")
            raise

    async def get_hybrid_embedding(
        self,
        text: str = None,
        image_bytes: bytes = None,
        text_weight: float = 0.5
    ) -> np.ndarray:
        """
        Generate hybrid embedding combining text and image

        Args:
            text: Text string (optional if image provided)
            image_bytes: Image bytes (optional if text provided)
            text_weight: Weight for text embedding (0-1), image gets (1-text_weight)

        Returns:
            numpy array of shape (512,) - L2 normalized combined embedding
        """
        if not text and not image_bytes:
            raise ValueError("Must provide at least text or image")

        embeddings = []
        weights = []

        if text:
            text_emb = await self.get_text_embedding(text)
            embeddings.append(text_emb)
            weights.append(text_weight)

        if image_bytes:
            image_emb = await self.get_image_embedding(image_bytes)
            embeddings.append(image_emb)
            weights.append(1.0 - text_weight if text else 1.0)

        # Weighted combination
        combined = np.zeros(self.embedding_dim, dtype=np.float32)
        for emb, weight in zip(embeddings, weights):
            combined += weight * emb

        # Normalize
        norm = np.linalg.norm(combined)
        if norm > 0:
            combined = combined / norm

        logger.info(f"✅ Generated hybrid embedding: text_weight={text_weight}, norm={norm:.4f}")
        return combined

    def _parse_embedding(self, result: Union[dict, list], is_nested: bool = True) -> np.ndarray:
        """
        Parse embedding from CLIP endpoint response

        Args:
            result: Response from CLIP endpoint
            is_nested: True if predictions are nested [[...]], False if flat [...]

        Handles multiple response formats:
        - clip-multimodal-encoder: {'predictions': [[0.01, 0.02, ...]]} (nested)
        - clip-image-encoder: {'predictions': [0.01, 0.02, ...]} (flat)
        """
        embedding = None

        if isinstance(result, dict) and "predictions" in result:
            predictions = result["predictions"]
            if isinstance(predictions, list) and len(predictions) > 0:
                if is_nested:
                    # Nested array: [[0.0121, 0.0134, ...]]
                    if isinstance(predictions[0], list):
                        embedding = np.array(predictions[0], dtype=np.float32)
                    else:
                        # Fallback: treat as flat
                        embedding = np.array(predictions, dtype=np.float32)
                else:
                    # Flat array: [0.0121, 0.0134, ...]
                    if isinstance(predictions[0], (int, float)):
                        embedding = np.array(predictions, dtype=np.float32)
                    elif isinstance(predictions[0], list):
                        # Fallback: treat as nested
                        embedding = np.array(predictions[0], dtype=np.float32)
        elif isinstance(result, list):
            # Direct array format
            if len(result) > 0:
                if isinstance(result[0], (int, float)):
                    embedding = np.array(result, dtype=np.float32)
                elif isinstance(result[0], list):
                    embedding = np.array(result[0], dtype=np.float32)

        if embedding is None or embedding.size == 0:
            logger.error(f"Failed to parse embedding from response: {str(result)[:200]}")
            raise Exception("Could not extract embedding from CLIP response")

        # Flatten if needed
        if embedding.ndim > 1:
            embedding = embedding.flatten()

        # Verify shape
        if embedding.shape[0] != self.embedding_dim:
            logger.error(f"Wrong embedding dimension: got {embedding.shape[0]}, expected {self.embedding_dim}")
            raise Exception(f"Expected {self.embedding_dim}-dim embedding, got {embedding.shape[0]}")

        # Ensure L2 normalization (for cosine similarity in Vector Search)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        else:
            logger.error("Embedding has zero norm!")
            raise Exception("Invalid embedding: zero norm")

        return embedding


# Singleton instance
clip_service = CLIPService()