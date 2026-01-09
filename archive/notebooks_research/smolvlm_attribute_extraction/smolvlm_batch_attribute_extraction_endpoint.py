# Databricks notebook source
# MAGIC %md
# MAGIC # 🎨 SmolVLM-2.2B Batch Attribute Extraction (Endpoint Version)
# MAGIC
# MAGIC ## Overview
# MAGIC Extract rich semantic attributes from product images using SmolVLM-2.2B via Databricks Model Serving endpoint.
# MAGIC
# MAGIC ### What We're Extracting
# MAGIC - **Material**: leather, denim, knit fabric, woven fabric, synthetic, metal
# MAGIC - **Pattern**: solid, striped, floral, geometric, polka dots, checkered
# MAGIC - **Formality**: formal, business casual, casual, athletic
# MAGIC - **Style Keywords**: vintage, modern, minimalist, athletic, bohemian
# MAGIC - **Visual Details**: pockets, buttons, zippers, collars, sleeves
# MAGIC
# MAGIC ### Strategy
# MAGIC 1. Call existing SmolVLM endpoint via Databricks SDK
# MAGIC 2. Use 3 focused prompts per image (material, style, garment details)
# MAGIC 3. Parallel processing with Spark
# MAGIC 4. Confidence filtering and validation
# MAGIC 5. Generate enriched text descriptions
# MAGIC
# MAGIC ### Estimated Cost & Time
# MAGIC - No GPU cluster needed (uses existing endpoint)
# MAGIC - Processing: ~1-2 hours for 44,424 products (depends on endpoint throughput)
# MAGIC - Cost: Endpoint inference costs only
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - Access to main.fashion_demo.products table
# MAGIC - Images in Unity Catalog Volumes
# MAGIC - Access to endpoint: https://adb-984752964297111.11.azuredatabricks.net/serving-endpoints/databricks-gpt-oss-120b/invocations

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📦 Setup & Installation

# COMMAND ----------

# DBTITLE 1,Install Required Libraries
# MAGIC %pip install databricks-sdk pillow --quiet
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Import Libraries
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from PIL import Image
import io
import base64

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from pyspark.sql import functions as F
from pyspark.sql.types import *
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("✅ Libraries imported successfully")

# COMMAND ----------

# DBTITLE 1,Configuration
# Database configuration
CATALOG = "main"
SCHEMA = "fashion_demo"
PRODUCTS_TABLE = f"{CATALOG}.{SCHEMA}.products"
OUTPUT_TABLE = f"{CATALOG}.{SCHEMA}.product_extracted_attributes"

# Model configuration - Using Foundation Model API with vision support
MODEL_NAME = "meta-llama-3-2-90b-vision-instruct"  # Vision-capable model
ENDPOINT_URL = "https://eastus2.azuredatabricks.net/serving-endpoints/databricks-meta-llama-3-2-90b-vision-instruct/invocations"

# Cluster configuration
MIN_WORKERS = 2
MAX_WORKERS = 8
NUM_PARTITIONS = 4  # Reduced from 16 to avoid rate limiting

# Processing configuration
SAMPLE_SIZE = 100  # Start with 100 products for testing (set to None for full 44K catalog)
MAX_RETRIES = 3  # Retry failed requests
TIMEOUT_SECONDS = 60  # Increased timeout for vision models

print(f"✅ Configuration loaded")
print(f"   Products Table: {PRODUCTS_TABLE}")
print(f"   Output Table: {OUTPUT_TABLE}")
print(f"   Model: {MODEL_NAME} (Vision-capable)")
print(f"   Endpoint URL: {ENDPOINT_URL}")
print(f"   Cluster: {MIN_WORKERS}-{MAX_WORKERS} workers")
print(f"   Partitions: {NUM_PARTITIONS} (reduced to avoid rate limits)")
print(f"   Sample Size: {SAMPLE_SIZE} (set to None for full catalog)")
print(f"\n   ⚠️  Note: Using Foundation Model API (pay-per-token pricing)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔌 Databricks SDK Setup

# COMMAND ----------

# DBTITLE 1,Initialize Databricks Client
# Initialize the Databricks SDK client
# This will use the notebook's authentication automatically
w = WorkspaceClient()

print(f"✅ Databricks SDK initialized")
print(f"   Workspace: {w.config.host}")
print(f"   Endpoint: {ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💬 Prompt Templates

# COMMAND ----------

# DBTITLE 1,Define Prompt Templates
class PromptTemplates:
    """Structured prompts for attribute extraction"""

    @staticmethod
    def material_pattern() -> str:
        """Prompt for material and pattern extraction"""
        return """Look at this product image and identify the material and pattern.

For material, choose from: leather, denim, knit fabric, woven fabric, synthetic, metal, canvas, unknown
For pattern, choose from: solid color, striped, floral print, geometric, polka dots, checkered, abstract print, no clear pattern
For confidence, choose from: high, medium, low

Example for a leather jacket:
{"material": "leather", "pattern": "solid color", "confidence": "high"}

Example for a striped cotton shirt:
{"material": "woven fabric", "pattern": "striped", "confidence": "high"}

Now analyze this image and respond with JSON:"""

    @staticmethod
    def style_formality() -> str:
        """Prompt for style and formality extraction"""
        return """Look at this product and describe its style.

Formality: formal, business casual, casual, or athletic
Style keywords: Pick 1-3 from: athletic, sporty, vintage, retro, modern, contemporary, minimalist, simple, bohemian, hippie, streetwear, urban, professional, corporate, elegant, sophisticated
Details: List only what you see from: has pockets, has buttons, has zipper, has hood, has logo, has drawstrings, has belt, has collar

Example for a hoodie:
{"formality": "casual", "style_keywords": ["streetwear", "urban"], "details": ["has hood", "has pockets", "has drawstrings"]}

Example for a business shirt:
{"formality": "business casual", "style_keywords": ["professional", "simple"], "details": ["has collar", "has buttons"]}

Now analyze this image and respond with JSON:"""

    @staticmethod
    def garment_details() -> str:
        """Prompt for garment-specific details (only for apparel)"""
        return """Look at this clothing item and identify its features.

Collar: crew neck, v-neck, collar, hooded, turtleneck, scoop neck, no collar, or not applicable
Sleeves: short sleeve, long sleeve, sleeveless, three-quarter sleeve, or not applicable
Fit: fitted, regular, loose, oversized, or cannot determine

Example for a t-shirt:
{"collar": "crew neck", "sleeves": "short sleeve", "fit": "regular"}

Example for a dress:
{"collar": "scoop neck", "sleeves": "sleeveless", "fit": "fitted"}

Now analyze this image and respond with JSON:"""

prompts = PromptTemplates()
print("✅ Prompt templates defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔧 Inference Functions

# COMMAND ----------

# DBTITLE 1,Core Inference Function using Endpoint
def query_endpoint(image: Image.Image, prompt: str, max_retries: int = MAX_RETRIES) -> Dict:
    """
    Query Databricks Model Serving endpoint with image and prompt
    
    Args:
        image: PIL Image
        prompt: Text prompt
        max_retries: Number of retry attempts
        
    Returns:
        Parsed JSON response or error dict
    """
    # Convert image to base64
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    # Create the request payload
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }
    ]
    
    for attempt in range(max_retries):
        try:
            # Call the endpoint
            response = w.serving_endpoints.query(
                name=ENDPOINT_NAME,
                messages=messages,
                max_tokens=200,
                temperature=0.1
            )
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Try to parse JSON from response
            # The model might wrap JSON in markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()
            
            # Find JSON object in the text
            start_idx = json_text.find("{")
            end_idx = json_text.rfind("}") + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_text = json_text[start_idx:end_idx]
                return json.loads(json_text)
            else:
                return {"error": "No JSON found in response", "raw_response": response_text}
                
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                return {"error": f"JSON decode failed: {str(e)}", "raw_response": response_text}
            time.sleep(1)  # Brief pause before retry
            
        except Exception as e:
            logger.warning(f"Endpoint error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                return {"error": f"Endpoint error: {str(e)}"}
            time.sleep(2)  # Longer pause for endpoint errors
    
    return {"error": "Max retries exceeded"}

# COMMAND ----------

# DBTITLE 1,Extract Attributes Function
def extract_attributes_from_image(
    image_bytes: bytes,
    article_type: str,
    prompts: PromptTemplates
) -> Dict[str, any]:
    """
    Extract all attributes from a single product image
    
    Args:
        image_bytes: Image as bytes
        article_type: Product type (for conditional logic)
        prompts: Prompt templates
        
    Returns:
        Dictionary with all extracted attributes
    """
    try:
        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Ensure RGB format
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Query 1: Material and Pattern
        material_result = query_endpoint(image, prompts.material_pattern())
        
        # Query 2: Style and Formality
        style_result = query_endpoint(image, prompts.style_formality())
        
        # Query 3: Garment Details (only for apparel)
        is_apparel = article_type.lower() in [
            'tshirts', 'shirts', 'tops', 'dresses', 'sweaters',
            'jackets', 'coats', 'hoodies', 'sweatshirts'
        ]
        
        if is_apparel:
            garment_result = query_endpoint(image, prompts.garment_details())
        else:
            garment_result = {
                "collar": "not applicable",
                "sleeves": "not applicable",
                "fit": "not applicable"
            }
        
        # Combine results
        attributes = {
            # Material & Pattern
            "material": material_result.get("material", "unknown"),
            "pattern": material_result.get("pattern", "no clear pattern"),
            "confidence_material": material_result.get("confidence", "low"),
            
            # Style & Formality
            "formality": style_result.get("formality", "casual"),
            "style_keywords": style_result.get("style_keywords", []),
            "visual_details": style_result.get("details", []),
            
            # Garment Details
            "collar_type": garment_result.get("collar", "not applicable"),
            "sleeve_length": garment_result.get("sleeves", "not applicable"),
            "fit": garment_result.get("fit", "cannot determine"),
            
            # Metadata
            "extraction_success": True,
            "extraction_errors": []
        }
        
        # Validate and collect errors
        errors = []
        if "error" in material_result:
            errors.append(f"Material extraction: {material_result['error']}")
        if "error" in style_result:
            errors.append(f"Style extraction: {style_result['error']}")
        if is_apparel and "error" in garment_result:
            errors.append(f"Garment extraction: {garment_result['error']}")
        
        if errors:
            attributes["extraction_success"] = False
            attributes["extraction_errors"] = errors
        
        return attributes
        
    except Exception as e:
        logger.error(f"Failed to extract attributes: {str(e)}")
        return {
            "material": "unknown",
            "pattern": "no clear pattern",
            "confidence_material": "low",
            "formality": "casual",
            "style_keywords": [],
            "visual_details": [],
            "collar_type": "not applicable",
            "sleeve_length": "not applicable",
            "fit": "cannot determine",
            "extraction_success": False,
            "extraction_errors": [str(e)]
        }

print("✅ Inference functions defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Load Product Data

# COMMAND ----------

# DBTITLE 1,Load Products with Images
print("📊 Loading product data...")

# Load products
products = spark.table(PRODUCTS_TABLE)

# Apply sampling if configured
if SAMPLE_SIZE:
    products = products.limit(SAMPLE_SIZE)

count = products.count()
print(f"✅ Loaded {count:,} products")

# Verify image paths
print("\n📷 Sample image paths:")
products.select("product_id", "product_display_name", "image_path").show(5, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚀 Batch Attribute Extraction

# COMMAND ----------

# DBTITLE 1,Define Spark UDF for Batch Processing
# Define output schema
attributes_schema = StructType([
    StructField("material", StringType(), True),
    StructField("pattern", StringType(), True),
    StructField("confidence_material", StringType(), True),
    StructField("formality", StringType(), True),
    StructField("style_keywords", ArrayType(StringType()), True),
    StructField("visual_details", ArrayType(StringType()), True),
    StructField("collar_type", StringType(), True),
    StructField("sleeve_length", StringType(), True),
    StructField("fit", StringType(), True),
    StructField("extraction_success", BooleanType(), True),
    StructField("extraction_errors", ArrayType(StringType()), True)
])

def extract_attributes_udf(image_bytes: bytes, article_type: str) -> Dict:
    """Wrapper function for Spark UDF - self-contained to avoid serialization issues"""
    # Import inside UDF to avoid capturing outer scope
    import json
    import io
    import base64
    from PIL import Image
    from databricks.sdk import WorkspaceClient
    
    # Create WorkspaceClient inside worker
    w_worker = WorkspaceClient()
    
    # Define prompts inside worker
    class WorkerPrompts:
        @staticmethod
        def material_pattern():
            return """Look at this product image and identify the material and pattern.\n\nFor material, choose from: leather, denim, knit fabric, woven fabric, synthetic, metal, canvas, unknown\nFor pattern, choose from: solid color, striped, floral print, geometric, polka dots, checkered, abstract print, no clear pattern\nFor confidence, choose from: high, medium, low\n\nExample for a leather jacket:\n{\"material\": \"leather\", \"pattern\": \"solid color\", \"confidence\": \"high\"}\n\nExample for a striped cotton shirt:\n{\"material\": \"woven fabric\", \"pattern\": \"striped\", \"confidence\": \"high\"}\n\nNow analyze this image and respond with JSON:"""
        
        @staticmethod
        def style_formality():
            return """Look at this product and describe its style.\n\nFormality: formal, business casual, casual, or athletic\nStyle keywords: Pick 1-3 from: athletic, sporty, vintage, retro, modern, contemporary, minimalist, simple, bohemian, hippie, streetwear, urban, professional, corporate, elegant, sophisticated\nDetails: List only what you see from: has pockets, has buttons, has zipper, has hood, has logo, has drawstrings, has belt, has collar\n\nExample for a hoodie:\n{\"formality\": \"casual\", \"style_keywords\": [\"streetwear\", \"urban\"], \"details\": [\"has hood\", \"has pockets\", \"has drawstrings\"]}\n\nExample for a business shirt:\n{\"formality\": \"business casual\", \"style_keywords\": [\"professional\", \"simple\"], \"details\": [\"has collar\", \"has buttons\"]}\n\nNow analyze this image and respond with JSON:"""
        
        @staticmethod
        def garment_details():
            return """Look at this clothing item and identify its features.\n\nCollar: crew neck, v-neck, collar, hooded, turtleneck, scoop neck, no collar, or not applicable\nSleeves: short sleeve, long sleeve, sleeveless, three-quarter sleeve, or not applicable\nFit: fitted, regular, loose, oversized, or cannot determine\n\nExample for a t-shirt:\n{\"collar\": \"crew neck\", \"sleeves\": \"short sleeve\", \"fit\": \"regular\"}\n\nExample for a dress:\n{\"collar\": \"scoop neck\", \"sleeves\": \"sleeveless\", \"fit\": \"fitted\"}\n\nNow analyze this image and respond with JSON:"""
    
    worker_prompts = WorkerPrompts()
    
    # Call extract_attributes_from_image logic inline
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Helper function to query endpoint
        def query_endpoint_worker(img, prompt):
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                    {"type": "text", "text": prompt}
                ]
            }]
            
            try:
                response = w_worker.serving_endpoints.query(
                    name="databricks-gpt-oss-120b",
                    messages=messages,
                    max_tokens=200,
                    temperature=0.1
                )
                response_text = response.choices[0].message.content
                
                # Parse JSON from response
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                else:
                    json_text = response_text.strip()
                
                start_idx = json_text.find("{")
                end_idx = json_text.rfind("}") + 1
                
                if start_idx >= 0 and end_idx > start_idx:
                    json_text = json_text[start_idx:end_idx]
                    return json.loads(json_text)
                else:
                    return {"error": "No JSON found"}
            except Exception as e:
                return {"error": str(e)}
        
        # Query endpoint for each attribute type
        material_result = query_endpoint_worker(image, worker_prompts.material_pattern())
        style_result = query_endpoint_worker(image, worker_prompts.style_formality())
        
        is_apparel = article_type.lower() in ['tshirts', 'shirts', 'tops', 'dresses', 'sweaters', 'jackets', 'coats', 'hoodies', 'sweatshirts']
        if is_apparel:
            garment_result = query_endpoint_worker(image, worker_prompts.garment_details())
        else:
            garment_result = {"collar": "not applicable", "sleeves": "not applicable", "fit": "not applicable"}
        
        # Combine results
        attributes = {
            "material": material_result.get("material", "unknown"),
            "pattern": material_result.get("pattern", "no clear pattern"),
            "confidence_material": material_result.get("confidence", "low"),
            "formality": style_result.get("formality", "casual"),
            "style_keywords": style_result.get("style_keywords", []),
            "visual_details": style_result.get("details", []),
            "collar_type": garment_result.get("collar", "not applicable"),
            "sleeve_length": garment_result.get("sleeves", "not applicable"),
            "fit": garment_result.get("fit", "cannot determine"),
            "extraction_success": True,
            "extraction_errors": []
        }
        
        errors = []
        if "error" in material_result:
            errors.append(f"Material: {material_result['error']}")
        if "error" in style_result:
            errors.append(f"Style: {style_result['error']}")
        if is_apparel and "error" in garment_result:
            errors.append(f"Garment: {garment_result['error']}")
        
        if errors:
            attributes["extraction_success"] = False
            attributes["extraction_errors"] = errors
        
        return attributes
        
    except Exception as e:
        return {
            "material": "unknown",
            "pattern": "no clear pattern",
            "confidence_material": "low",
            "formality": "casual",
            "style_keywords": [],
            "visual_details": [],
            "collar_type": "not applicable",
            "sleeve_length": "not applicable",
            "fit": "cannot determine",
            "extraction_success": False,
            "extraction_errors": [str(e)]
        }

# Register as Spark UDF
from pyspark.sql.functions import udf
extract_udf = udf(extract_attributes_udf, attributes_schema)

print("✅ Spark UDF registered")

# COMMAND ----------

# DBTITLE 1,Run Batch Extraction
print("🚀 Starting batch attribute extraction...")
print(f"   Processing {count:,} products")
print(f"   Using {NUM_PARTITIONS} partitions")
print(f"   Model: {MODEL_NAME}")
print()

start_time = time.time()

# Get authentication token from notebook context
driver_host = w.config.host
driver_token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()

print(f"🔑 Using workspace: {driver_host}")

# Define the batch processing function
def process_product_batch(batch_iterator):
    """
    Process a batch of products - reads images and extracts attributes
    """
    import io
    from PIL import Image
    import requests
    import time as worker_time
    
    for batch_df in batch_iterator:
        results = []
        
        for idx, row in batch_df.iterrows():
            try:
                # Read image file from path
                with open(row['image_path'], 'rb') as f:
                    image_bytes = f.read()
                
                import json
                import base64
                
                image = Image.open(io.BytesIO(image_bytes))
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Helper function to query Foundation Model API
                def query_endpoint_worker(img, prompt, max_retries=3):
                    buffered = io.BytesIO()
                    img.save(buffered, format="PNG")
                    image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                    
                    payload = {
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                                {"type": "text", "text": prompt}
                            ]
                        }],
                        "max_tokens": 200,
                        "temperature": 0.1
                    }
                    
                    for attempt in range(max_retries):
                        try:
                            # Use Foundation Model API endpoint
                            url = f"{driver_host}/serving-endpoints/databricks-meta-llama-3-2-90b-vision-instruct/invocations"
                            headers = {
                                "Authorization": f"Bearer {driver_token}",
                                "Content-Type": "application/json"
                            }
                            
                            response = requests.post(url, json=payload, headers=headers, timeout=60)
                            
                            # Handle rate limiting
                            if response.status_code == 429:
                                if attempt < max_retries - 1:
                                    worker_time.sleep(2 ** attempt)  # Exponential backoff
                                    continue
                                else:
                                    return {"error": "Rate limit exceeded after retries"}
                            
                            response.raise_for_status()
                            
                            response_data = response.json()
                            response_text = response_data['choices'][0]['message']['content']
                            
                            # Parse JSON from response
                            if "```json" in response_text:
                                json_start = response_text.find("```json") + 7
                                json_end = response_text.find("```", json_start)
                                json_text = response_text[json_start:json_end].strip()
                            elif "```" in response_text:
                                json_start = response_text.find("```") + 3
                                json_end = response_text.find("```", json_start)
                                json_text = response_text[json_start:json_end].strip()
                            else:
                                json_text = response_text.strip()
                            
                            start_idx = json_text.find("{")
                            end_idx = json_text.rfind("}") + 1
                            
                            if start_idx >= 0 and end_idx > start_idx:
                                json_text = json_text[start_idx:end_idx]
                                return json.loads(json_text)
                            else:
                                return {"error": "No JSON found"}
                                
                        except requests.exceptions.RequestException as e:
                            if attempt < max_retries - 1:
                                worker_time.sleep(1)
                                continue
                            return {"error": str(e)}
                        except Exception as e:
                            return {"error": str(e)}
                    
                    return {"error": "Max retries exceeded"}
                
                # Define prompts
                material_prompt = """Look at this product image and identify the material and pattern.\n\nFor material, choose from: leather, denim, knit fabric, woven fabric, synthetic, metal, canvas, unknown\nFor pattern, choose from: solid color, striped, floral print, geometric, polka dots, checkered, abstract print, no clear pattern\nFor confidence, choose from: high, medium, low\n\nExample for a leather jacket:\n{\"material\": \"leather\", \"pattern\": \"solid color\", \"confidence\": \"high\"}\n\nExample for a striped cotton shirt:\n{\"material\": \"woven fabric\", \"pattern\": \"striped\", \"confidence\": \"high\"}\n\nNow analyze this image and respond with JSON:"""
                
                style_prompt = """Look at this product and describe its style.\n\nFormality: formal, business casual, casual, or athletic\nStyle keywords: Pick 1-3 from: athletic, sporty, vintage, retro, modern, contemporary, minimalist, simple, bohemian, hippie, streetwear, urban, professional, corporate, elegant, sophisticated\nDetails: List only what you see from: has pockets, has buttons, has zipper, has hood, has logo, has drawstrings, has belt, has collar\n\nExample for a hoodie:\n{\"formality\": \"casual\", \"style_keywords\": [\"streetwear\", \"urban\"], \"details\": [\"has hood\", \"has pockets\", \"has drawstrings\"]}\n\nExample for a business shirt:\n{\"formality\": \"business casual\", \"style_keywords\": [\"professional\", \"simple\"], \"details\": [\"has collar\", \"has buttons\"]}\n\nNow analyze this image and respond with JSON:"""
                
                # Query endpoint with retry logic
                material_result = query_endpoint_worker(image, material_prompt)
                style_result = query_endpoint_worker(image, style_prompt)
                
                is_apparel = row['article_type'].lower() in ['tshirts', 'shirts', 'tops', 'dresses', 'sweaters', 'jackets', 'coats', 'hoodies', 'sweatshirts']
                if is_apparel:
                    garment_prompt = """Look at this clothing item and identify its features.\n\nCollar: crew neck, v-neck, collar, hooded, turtleneck, scoop neck, no collar, or not applicable\nSleeves: short sleeve, long sleeve, sleeveless, three-quarter sleeve, or not applicable\nFit: fitted, regular, loose, oversized, or cannot determine\n\nExample for a t-shirt:\n{\"collar\": \"crew neck\", \"sleeves\": \"short sleeve\", \"fit\": \"regular\"}\n\nExample for a dress:\n{\"collar\": \"scoop neck\", \"sleeves\": \"sleeveless\", \"fit\": \"fitted\"}\n\nNow analyze this image and respond with JSON:"""
                    garment_result = query_endpoint_worker(image, garment_prompt)
                else:
                    garment_result = {"collar": "not applicable", "sleeves": "not applicable", "fit": "not applicable"}
                
                # Combine results
                attrs = {
                    "material": material_result.get("material", "unknown"),
                    "pattern": material_result.get("pattern", "no clear pattern"),
                    "confidence_material": material_result.get("confidence", "low"),
                    "formality": style_result.get("formality", "casual"),
                    "style_keywords": style_result.get("style_keywords", []),
                    "visual_details": style_result.get("details", []),
                    "collar_type": garment_result.get("collar", "not applicable"),
                    "sleeve_length": garment_result.get("sleeves", "not applicable"),
                    "fit": garment_result.get("fit", "cannot determine"),
                    "extraction_success": True,
                    "extraction_errors": []
                }
                
                errors = []
                if "error" in material_result:
                    errors.append(f"Material: {material_result['error']}")
                if "error" in style_result:
                    errors.append(f"Style: {style_result['error']}")
                if is_apparel and "error" in garment_result:
                    errors.append(f"Garment: {garment_result['error']}")
                
                if errors:
                    attrs["extraction_success"] = False
                    attrs["extraction_errors"] = errors
                
                # Combine with original data
                result = {
                    'product_id': row['product_id'],
                    'product_display_name': row['product_display_name'],
                    'master_category': row['master_category'],
                    'sub_category': row['sub_category'],
                    'article_type': row['article_type'],
                    'base_color': row['base_color'],
                    'price': row['price'],
                    'gender': row['gender'],
                    'season': row['season'],
                    'usage': row['usage'],
                    'year': row['year'],
                    'image_path': row['image_path'],
                    'material': attrs['material'],
                    'pattern': attrs['pattern'],
                    'confidence_material': attrs['confidence_material'],
                    'formality': attrs['formality'],
                    'style_keywords': attrs['style_keywords'],
                    'visual_details': attrs['visual_details'],
                    'collar_type': attrs['collar_type'],
                    'sleeve_length': attrs['sleeve_length'],
                    'fit': attrs['fit'],
                    'extraction_success': attrs['extraction_success'],
                    'extraction_errors': attrs['extraction_errors']
                }
                results.append(result)
                
            except Exception as e:
                # Add error result
                result = {
                    'product_id': row['product_id'],
                    'product_display_name': row['product_display_name'],
                    'master_category': row['master_category'],
                    'sub_category': row['sub_category'],
                    'article_type': row['article_type'],
                    'base_color': row['base_color'],
                    'price': row['price'],
                    'gender': row['gender'],
                    'season': row['season'],
                    'usage': row['usage'],
                    'year': row['year'],
                    'image_path': row['image_path'],
                    'material': 'unknown',
                    'pattern': 'no clear pattern',
                    'confidence_material': 'low',
                    'formality': 'casual',
                    'style_keywords': [],
                    'visual_details': [],
                    'collar_type': 'not applicable',
                    'sleeve_length': 'not applicable',
                    'fit': 'cannot determine',
                    'extraction_success': False,
                    'extraction_errors': [str(e)]
                }
                results.append(result)
        
        yield pd.DataFrame(results)

# Define output schema
output_schema = StructType([
    StructField("product_id", IntegerType(), True),
    StructField("product_display_name", StringType(), True),
    StructField("master_category", StringType(), True),
    StructField("sub_category", StringType(), True),
    StructField("article_type", StringType(), True),
    StructField("base_color", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("gender", StringType(), True),
    StructField("season", StringType(), True),
    StructField("usage", StringType(), True),
    StructField("year", IntegerType(), True),
    StructField("image_path", StringType(), True),
    StructField("material", StringType(), True),
    StructField("pattern", StringType(), True),
    StructField("confidence_material", StringType(), True),
    StructField("formality", StringType(), True),
    StructField("style_keywords", ArrayType(StringType()), True),
    StructField("visual_details", ArrayType(StringType()), True),
    StructField("collar_type", StringType(), True),
    StructField("sleeve_length", StringType(), True),
    StructField("fit", StringType(), True),
    StructField("extraction_success", BooleanType(), True),
    StructField("extraction_errors", ArrayType(StringType()), True)
])

# Repartition and process
print("💾 Repartitioning for parallel processing...")
products_partitioned = products.repartition(NUM_PARTITIONS)

print("🤖 Processing images with vision model...")
products_with_attrs = products_partitioned.mapInPandas(process_product_batch, schema=output_schema)

# Trigger execution and count
print("⏳ Executing...")
result_count = products_with_attrs.count()

end_time = time.time()
duration = end_time - start_time

print(f"\n✅ Extraction complete!")
print(f"   Duration: {duration/60:.1f} minutes")
print(f"   Throughput: {result_count/duration*60:.1f} products/minute")
print(f"   Total products: {result_count:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📈 Quality Analysis

# COMMAND ----------

# DBTITLE 1,Analyze Extraction Quality
print("=" * 80)
print("EXTRACTION QUALITY REPORT")
print("=" * 80)

# Success rate
success_count = products_with_attrs.filter(F.col("extraction_success") == True).count()
success_rate = success_count / count * 100
print(f"\n✅ Success Rate: {success_rate:.1f}% ({success_count:,}/{count:,})")

# Failed extractions
if success_count < count:
    failed = products_with_attrs.filter(F.col("extraction_success") == False)
    print(f"\n❌ Failed Extractions: {count - success_count}")
    failed.select("product_id", "product_display_name", "extraction_errors").show(5, truncate=False)

# Material distribution
print("\n📊 Material Distribution:")
products_with_attrs.groupBy("material").count().orderBy(F.desc("count")).show(20)

# Pattern distribution
print("\n📊 Pattern Distribution:")
products_with_attrs.groupBy("pattern").count().orderBy(F.desc("count")).show(20)

# Formality distribution
print("\n📊 Formality Distribution:")
products_with_attrs.groupBy("formality").count().orderBy(F.desc("count")).show(10)

# Confidence distribution
print("\n📊 Confidence Distribution:")
products_with_attrs.groupBy("confidence_material").count().orderBy(F.desc("count")).show(10)

# Style keywords frequency
print("\n📊 Most Common Style Keywords:")
style_keywords_exploded = products_with_attrs.select(
    F.explode(F.col("style_keywords")).alias("keyword")
)
style_keywords_exploded.groupBy("keyword").count().orderBy(F.desc("count")).show(20)

# COMMAND ----------

# DBTITLE 1,Sample Results Review
print("=" * 80)
print("SAMPLE EXTRACTED ATTRIBUTES")
print("=" * 80)

# Show diverse samples
samples = products_with_attrs.select(
    "product_display_name",
    "article_type",
    "material",
    "pattern",
    "formality",
    "style_keywords",
    "confidence_material"
).limit(20)

samples.show(20, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💾 Save Results

# COMMAND ----------

# DBTITLE 1,Save Extracted Attributes to Unity Catalog
print(f"💾 Saving extracted attributes to {OUTPUT_TABLE}")

# Add timestamp
products_with_attrs_final = products_with_attrs.withColumn(
    "extraction_timestamp",
    F.current_timestamp()
)

# Write to Delta table
products_with_attrs_final.write.mode("overwrite").saveAsTable(OUTPUT_TABLE)

print(f"✅ Saved {count:,} products with extracted attributes")
print(f"   Table: {OUTPUT_TABLE}")

# Show table info
spark.sql(f"DESCRIBE TABLE {OUTPUT_TABLE}").show(100, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Generate Enriched Descriptions

# COMMAND ----------

# DBTITLE 1,Create Rich Text Descriptions
print("📝 Generating enriched text descriptions...")

# Create rich descriptions combining original + extracted attributes
enriched_descriptions = products_with_attrs_final.withColumn(
    "rich_description",
    F.concat_ws(" ",
        F.col("product_display_name"),
        F.col("article_type"),
        F.col("base_color"),
        F.col("gender"),
        # Extracted attributes
        F.col("material"),
        F.col("pattern"),
        F.col("formality"),
        F.array_join(F.col("style_keywords"), " "),
        F.array_join(F.col("visual_details"), " "),
        # Garment details (if applicable)
        F.when(F.col("collar_type") != "not applicable", F.col("collar_type")).otherwise(""),
        F.when(F.col("sleeve_length") != "not applicable", F.col("sleeve_length")).otherwise(""),
        # Context
        F.col("season"),
        F.col("usage")
    )
)

# Show sample descriptions
print("\n📋 Sample Enriched Descriptions:")
print("=" * 80)

samples = enriched_descriptions.select(
    "product_display_name",
    "rich_description"
).limit(10)

for row in samples.collect():
    print(f"\nProduct: {row['product_display_name']}")
    print(f"Enriched: {row['rich_description']}")
    print("-" * 80)

# Save with rich descriptions
ENRICHED_TABLE = f"{CATALOG}.{SCHEMA}.products_enriched_descriptions"
enriched_descriptions.write.mode("overwrite").saveAsTable(ENRICHED_TABLE)

print(f"\n✅ Saved enriched descriptions to {ENRICHED_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Next Steps
# MAGIC
# MAGIC ### 1. Validate Results
# MAGIC - Review sample results above
# MAGIC - Check accuracy for different product types
# MAGIC - Identify any systematic errors
# MAGIC
# MAGIC ### 2. Process Full Catalog
# MAGIC - Set `SAMPLE_SIZE = None` in configuration
# MAGIC - Run full extraction (~1-2 hours for 44K products)
# MAGIC
# MAGIC ### 3. Generate New CLIP Embeddings
# MAGIC - Use enriched descriptions to generate new text embeddings
# MAGIC - Run multimodal_clip_implementation notebook
# MAGIC - Update Vector Search indexes
# MAGIC
# MAGIC ### 4. A/B Test Search Quality
# MAGIC - Compare search results: baseline vs enriched
# MAGIC - Measure: precision, recall, score distribution
# MAGIC - Monitor: CTR, conversion rate
# MAGIC
# MAGIC ### Expected Improvements
# MAGIC - ✅ Search precision: +20-30%
# MAGIC - ✅ Score distribution: 2% → 10-15% range
# MAGIC - ✅ User engagement: +15-20% CTR

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Validation Queries
# MAGIC
# MAGIC Run these to validate quality:

# COMMAND ----------

# DBTITLE 1,Consistency Check: Watches Should Be Metal
# Watches should be extracted as "metal"
spark.sql(f"""
    SELECT
        product_display_name,
        article_type,
        material,
        confidence_material
    FROM {OUTPUT_TABLE}
    WHERE article_type = 'Watches'
    LIMIT 20
""").show(truncate=False)

# COMMAND ----------

# DBTITLE 1,Consistency Check: T-Shirts Should Be Knit Fabric
# T-shirts should be "knit fabric"
spark.sql(f"""
    SELECT
        product_display_name,
        article_type,
        material,
        pattern,
        confidence_material
    FROM {OUTPUT_TABLE}
    WHERE article_type = 'Tshirts'
    LIMIT 20
""").show(truncate=False)

# COMMAND ----------

# DBTITLE 1,Consistency Check: Formal Shirts
# Formal shirts should have "formal" or "business casual" formality
spark.sql(f"""
    SELECT
        product_display_name,
        article_type,
        material,
        formality,
        collar_type
    FROM {OUTPUT_TABLE}
    WHERE article_type = 'Shirts' AND usage = 'Formal'
    LIMIT 20
""").show(truncate=False)

# COMMAND ----------

# DBTITLE 1,Check Material Diversity
# Should have good distribution across materials
spark.sql(f"""
    SELECT
        material,
        COUNT(*) as count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as percentage
    FROM {OUTPUT_TABLE}
    GROUP BY material
    ORDER BY count DESC
""").show()

# COMMAND ----------

# DBTITLE 1,Find Products with Rich Attributes
# Find products with many extracted attributes (high information)
spark.sql(f"""
    SELECT
        product_display_name,
        material,
        pattern,
        formality,
        style_keywords,
        visual_details,
        LENGTH(rich_description) as description_length
    FROM {ENRICHED_TABLE}
    WHERE extraction_success = true
        AND confidence_material IN ('high', 'medium')
        AND SIZE(style_keywords) > 0
        AND SIZE(visual_details) > 0
    ORDER BY description_length DESC
    LIMIT 10
""").show(truncate=False)
