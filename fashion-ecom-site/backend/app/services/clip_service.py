
"""
CLIP Image Embedding Service
Integrates with Databricks Model Serving endpoint for CLIP embeddings
"""
from typing import Optional
import requests
import base64
from io import BytesIO
from PIL import Image
import numpy as np
from app.core.config import settings


class CLIPService:
    """Service for generating image embeddings via CLIP model serving endpoint."""

    def __init__(self):
        self.endpoint_url = settings.CLIP_ENDPOINT
        self.token = settings.CLIP_TOKEN or settings.DATABRICKS_TOKEN
        
        if not self.endpoint_url:
            raise ValueError("CLIP_ENDPOINT must be configured in settings")
        if not self.token:
            raise ValueError("DATABRICKS_TOKEN must be configured for CLIP authentication")
            
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def encode_image_to_base64(self, image_bytes: bytes) -> str:
        """
        Encode image bytes to base64 string, with optional resizing.
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Base64 encoded string of the image
        """
        with Image.open(BytesIO(image_bytes)) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize if too large (CLIP typically uses 224x224)
            if img.size[0] > 512 or img.size[1] > 512:
                img.thumbnail((512, 512), Image.Resampling.LANCZOS)

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_bytes = buffer.getvalue()
            return base64.b64encode(img_bytes).decode("utf-8")

    def get_embedding(self, image_bytes: bytes) -> np.ndarray:
        """
        Get CLIP embedding for an image.
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Numpy array of embedding vector
            
        Raises:
            requests.HTTPError: If the API request fails
            ValueError: If the response format is unexpected
        """
        # Encode image to base64
        image_base64 = self.encode_image_to_base64(image_bytes)
        
        # Prepare payload for CLIP endpoint
        payload = {
            "inputs": {
                "image": image_base64
            }
        }
        
        # Call the model serving endpoint
        response = requests.post(
            self.endpoint_url,
            headers=self.headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        # Parse response
        result = response.json()
        
        # Handle different response formats
        if "predictions" in result:
            embedding = result["predictions"]
            if isinstance(embedding, list) and len(embedding) > 0:
                embedding = embedding[0]
        elif "embedding" in result:
            embedding = result["embedding"]
        else:
            embedding = result
        
        return np.array(embedding, dtype=np.float32)

    def get_text_embedding(self, text: str) -> np.ndarray:
        """
        Get CLIP embedding for text (if supported by endpoint).
        
        Args:
            text: Text query
            
        Returns:
            Numpy array of embedding vector
        """
        payload = {
            "inputs": {
                "text": text
            }
        }
        
        response = requests.post(
            self.endpoint_url,
            headers=self.headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        
        if "predictions" in result:
            embedding = result["predictions"]
            if isinstance(embedding, list) and len(embedding) > 0:
                embedding = embedding[0]
        elif "embedding" in result:
            embedding = result["embedding"]
        else:
            embedding = result
        
        return np.array(embedding, dtype=np.float32)


# Global service instance
clip_service = CLIPService()
