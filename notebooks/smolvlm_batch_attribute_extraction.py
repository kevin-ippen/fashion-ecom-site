# Databricks notebook source
# MAGIC %md
# MAGIC # 🎨 SmolVLM-2.2B Batch Attribute Extraction
# MAGIC
# MAGIC ## Overview
# MAGIC Extract rich semantic attributes from product images using SmolVLM-2.2B vision-language model.
# MAGIC
# MAGIC ### What We're Extracting
# MAGIC - **Material**: leather, denim, knit fabric, woven fabric, synthetic, metal
# MAGIC - **Pattern**: solid, striped, floral, geometric, polka dots, checkered
# MAGIC - **Formality**: formal, business casual, casual, athletic
# MAGIC - **Style Keywords**: vintage, modern, minimalist, athletic, bohemian
# MAGIC - **Visual Details**: pockets, buttons, zippers, collars, sleeves
# MAGIC
# MAGIC ### Strategy
# MAGIC 1. Deploy SmolVLM-2.2B for batch inference
# MAGIC 2. Use 3 focused prompts per image (material, style, garment details)
# MAGIC 3. Parallel processing with Spark
# MAGIC 4. Confidence filtering and validation
# MAGIC 5. Generate enriched text descriptions
# MAGIC
# MAGIC ### Estimated Cost & Time
# MAGIC - GPU cluster: g5.xlarge or g5.2xlarge
# MAGIC - Processing: ~2-3 hours for 44,424 products
# MAGIC - Cost: ~$3-6 total
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - GPU-enabled cluster (g5.xlarge recommended)
# MAGIC - Python 3.10+
# MAGIC - Access to main.fashion_demo.products table
# MAGIC - Images in Unity Catalog Volumes

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📦 Setup & Installation

# COMMAND ----------

# DBTITLE 1,Install Required Libraries
# MAGIC %pip install torch torchvision transformers pillow accelerate bitsandbytes --quiet
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

import torch
from transformers import AutoProcessor, AutoModelForVision2Seq
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

# Model configuration
MODEL_NAME = "HuggingFaceTB/SmolVLM-Instruct"  # SmolVLM-2.2B
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Cluster configuration
# Standard_NC4as_T4_v3: 2-8 workers, each with T4 GPU (16GB), 28GB RAM, 4 cores
MIN_WORKERS = 2
MAX_WORKERS = 8
NUM_PARTITIONS = 16  # 2x max workers for optimal load balancing

# Processing configuration
SAMPLE_SIZE = 100  # Start with 100 products for testing (set to None for full 44K catalog)
BATCH_SIZE = 8  # Images per batch (not currently used, but available for optimization)

print(f"✅ Configuration loaded")
print(f"   Products Table: {PRODUCTS_TABLE}")
print(f"   Output Table: {OUTPUT_TABLE}")
print(f"   Model: {MODEL_NAME}")
print(f"   Device: {DEVICE}")
print(f"   Cluster: {MIN_WORKERS}-{MAX_WORKERS} workers with T4 GPUs (Standard_NC4as_T4_v3)")
print(f"   Partitions: {NUM_PARTITIONS} (for optimal parallelism)")
print(f"   Sample Size: {SAMPLE_SIZE} (set to None for full catalog)")
print(f"\n   💡 Estimated throughput:")
print(f"      - With {MIN_WORKERS} workers: ~{20 * MIN_WORKERS} products/minute")
print(f"      - With {MAX_WORKERS} workers: ~{20 * MAX_WORKERS} products/minute")
print(f"      - Full catalog (44K): ~4.6 hours @ {MAX_WORKERS} workers")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🤖 SmolVLM Model Setup

# COMMAND ----------

# DBTITLE 1,Load SmolVLM Model
@dataclass
class SmolVLMConfig:
    """Configuration for SmolVLM model"""
    model_name: str = MODEL_NAME
    device: str = DEVICE
    torch_dtype: torch.dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    max_new_tokens: int = 200
    temperature: float = 0.1  # Low temp for consistent extraction
    do_sample: bool = False  # Deterministic output

config = SmolVLMConfig()

print("🔄 Loading SmolVLM-2.2B model...")
print(f"   Device: {config.device}")
print(f"   Dtype: {config.torch_dtype}")

# Load processor and model
processor = AutoProcessor.from_pretrained(config.model_name, trust_remote_code=True)
model = AutoModelForVision2Seq.from_pretrained(
    config.model_name,
    torch_dtype=config.torch_dtype,
    device_map="auto",
    trust_remote_code=True
)

print("✅ SmolVLM-2.2B loaded successfully")
print(f"   Model size: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B parameters")
print(f"   Memory: {torch.cuda.memory_allocated() / 1e9:.2f}GB" if torch.cuda.is_available() else "")

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

# DBTITLE 1,Core Inference Function
def query_smolvlm(image: Image.Image, prompt: str, config: SmolVLMConfig) -> Dict:
    """
    Query SmolVLM with image and prompt

    Args:
        image: PIL Image
        prompt: Text prompt
        config: Model configuration

    Returns:
        Parsed JSON response or error dict
    """
    try:
        # Prepare inputs
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        # Process with SmolVLM
        prompt_text = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(
            text=prompt_text,
            images=[image],
            return_tensors="pt"
        ).to(config.device)

        # Generate response
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=config.max_new_tokens,
                temperature=config.temperature,
                do_sample=config.do_sample
            )

        # Decode response
        generated_texts = processor.batch_decode(
            generated_ids,
            skip_special_tokens=True
        )

        response_text = generated_texts[0]

        # Extract JSON from response - handle nested braces properly
        start_idx = response_text.find('{')
        
        if start_idx == -1:
            return {"error": "No JSON found in response", "raw_response": response_text}

        # Count braces to find the matching closing brace
        brace_count = 0
        end_idx = -1
        
        for i in range(start_idx, len(response_text)):
            if response_text[i] == '{':
                brace_count += 1
            elif response_text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break
        
        if end_idx == -1:
            return {"error": "No matching closing brace found", "raw_response": response_text}

        json_text = response_text[start_idx:end_idx+1]

        # Parse JSON
        result = json.loads(json_text)
        return result

    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {str(e)}", "raw_response": response_text, "extracted_json": json_text}
    except Exception as e:
        return {"error": f"Inference error: {str(e)}"}


def extract_attributes(image: Image.Image, article_type: str, config: SmolVLMConfig) -> Dict:
    """
    Extract all attributes using multi-stage prompts

    Args:
        image: PIL Image
        article_type: Product article type (e.g., "Tshirts", "Watches")
        config: Model configuration

    Returns:
        Dictionary with all extracted attributes
    """
    results = {
        "extraction_success": True,
        "extraction_errors": []
    }

    # Stage 1: Material & Pattern (always run)
    logger.info("Extracting material & pattern...")
    material_result = query_smolvlm(image, prompts.material_pattern(), config)

    if "error" in material_result:
        results["extraction_success"] = False
        results["extraction_errors"].append(f"Material: {material_result['error']}")
        # Set defaults
        results["material"] = "unknown"
        results["pattern"] = "no clear pattern"
        results["confidence_material"] = "low"
    else:
        results["material"] = material_result.get("material", "unknown")
        results["pattern"] = material_result.get("pattern", "no clear pattern")
        results["confidence_material"] = material_result.get("confidence", "low")

    # Stage 2: Style & Formality (always run)
    logger.info("Extracting style & formality...")
    style_result = query_smolvlm(image, prompts.style_formality(), config)

    if "error" in style_result:
        results["extraction_success"] = False
        results["extraction_errors"].append(f"Style: {style_result['error']}")
        # Set defaults
        results["formality"] = "casual"
        results["style_keywords"] = []
        results["visual_details"] = []
    else:
        results["formality"] = style_result.get("formality", "casual")
        results["style_keywords"] = style_result.get("style_keywords", [])
        results["visual_details"] = style_result.get("details", [])

    # Stage 3: Garment Details (only for apparel)
    apparel_types = ["Topwear", "Bottomwear", "Dress", "Innerwear", "Loungewear"]

    if any(apparel in article_type for apparel in apparel_types):
        logger.info("Extracting garment details...")
        garment_result = query_smolvlm(image, prompts.garment_details(), config)

        if "error" in garment_result:
            results["extraction_errors"].append(f"Garment: {garment_result['error']}")
            # Set defaults
            results["collar"] = "not applicable"
            results["sleeves"] = "not applicable"
            results["fit"] = "cannot determine"
        else:
            results["collar"] = garment_result.get("collar", "not applicable")
            results["sleeves"] = garment_result.get("sleeves", "not applicable")
            results["fit"] = garment_result.get("fit", "cannot determine")
    else:
        # Not apparel, set N/A
        results["collar"] = "not applicable"
        results["sleeves"] = "not applicable"
        results["fit"] = "cannot determine"

    return results

print("✅ Inference functions defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Test on Sample Images

# COMMAND ----------

# DBTITLE 1,Test Single Image
# Load a sample product for testing
sample_product = spark.sql(f"""
    SELECT *
    FROM {PRODUCTS_TABLE}
    WHERE image_path IS NOT NULL
    LIMIT 1
""").collect()[0]

print("🔍 Testing on sample product:")
print(f"   Product: {sample_product['product_display_name']}")
print(f"   Article Type: {sample_product['article_type']}")
print(f"   Category: {sample_product['master_category']}")
print(f"   Image Path: {sample_product['image_path']}")

# Load image
try:
    # Read image from Unity Catalog Volume
    image_path = sample_product['image_path']

    # For local testing, you may need to adjust the path
    # If images are in /Volumes/main/fashion_demo/raw_data/images/
    # You can read them directly
    with open(image_path, 'rb') as f:
        image = Image.open(f).convert('RGB')

    print(f"✅ Image loaded: {image.size}")

    # Extract attributes
    print("\n🔄 Extracting attributes...")
    attributes = extract_attributes(image, sample_product['article_type'], config)

    print("\n✅ Extraction complete!")
    print(json.dumps(attributes, indent=2))

except Exception as e:
    print(f"❌ Error testing: {e}")
    print("   Note: Adjust image path if running locally vs on Databricks")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚀 Batch Processing with Spark

# COMMAND ----------

# DBTITLE 1,Define Spark UDF Schema
# Define output schema for extracted attributes
attributes_schema = StructType([
    StructField("material", StringType(), True),
    StructField("pattern", StringType(), True),
    StructField("confidence_material", StringType(), True),
    StructField("formality", StringType(), True),
    StructField("style_keywords", ArrayType(StringType()), True),
    StructField("visual_details", ArrayType(StringType()), True),
    StructField("collar", StringType(), True),
    StructField("sleeves", StringType(), True),
    StructField("fit", StringType(), True),
    StructField("extraction_success", BooleanType(), True),
    StructField("extraction_errors", ArrayType(StringType()), True),
])

print("✅ Spark UDF schema defined")

# COMMAND ----------

# DBTITLE 1,Create Pandas UDF for Batch Processing
def process_batch(iterator):
    """
    Process batches of products using mapInPandas
    
    All inference logic is self-contained to avoid serializing driver objects
    """
    # Import libraries in worker context
    import torch
    from transformers import AutoProcessor, AutoModelForVision2Seq
    from PIL import Image
    import logging
    import json
    from dataclasses import dataclass
    
    # Get MODEL_NAME from global scope (string is small)
    model_name = "HuggingFaceTB/SmolVLM-Instruct"
    
    # Load model on worker
    logger = logging.getLogger(__name__)
    logger.info("Loading SmolVLM model on worker...")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    
    processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForVision2Seq.from_pretrained(
        model_name,
        torch_dtype=torch_dtype,
        device_map="auto",
        trust_remote_code=True
    )
    
    @dataclass
    class WorkerConfig:
        model_name: str
        device: str
        torch_dtype: torch.dtype
        max_new_tokens: int = 200
        temperature: float = 0.1
        do_sample: bool = False
    
    worker_config = WorkerConfig(
        model_name=model_name,
        device=device,
        torch_dtype=torch_dtype
    )
    logger.info(f"Model loaded on {device}")
    
    # Define prompts inside worker
    def material_pattern_prompt():
        return """Look at this product image and identify the material and pattern.\n\nFor material, choose from: leather, denim, knit fabric, woven fabric, synthetic, metal, canvas, unknown\nFor pattern, choose from: solid color, striped, floral print, geometric, polka dots, checkered, abstract print, no clear pattern\nFor confidence, choose from: high, medium, low\n\nExample for a leather jacket:\n{\"material\": \"leather\", \"pattern\": \"solid color\", \"confidence\": \"high\"}\n\nExample for a striped cotton shirt:\n{\"material\": \"woven fabric\", \"pattern\": \"striped\", \"confidence\": \"high\"}\n\nNow analyze this image and respond with JSON:"""
    
    def style_formality_prompt():
        return """Look at this product and describe its style.\n\nFormality: formal, business casual, casual, or athletic\nStyle keywords: Pick 1-3 from: athletic, sporty, vintage, retro, modern, contemporary, minimalist, simple, bohemian, hippie, streetwear, urban, professional, corporate, elegant, sophisticated\nDetails: List only what you see from: has pockets, has buttons, has zipper, has hood, has logo, has drawstrings, has belt, has collar\n\nExample for a hoodie:\n{\"formality\": \"casual\", \"style_keywords\": [\"streetwear\", \"urban\"], \"details\": [\"has hood\", \"has pockets\", \"has drawstrings\"]}\n\nExample for a business shirt:\n{\"formality\": \"business casual\", \"style_keywords\": [\"professional\", \"simple\"], \"details\": [\"has collar\", \"has buttons\"]}\n\nNow analyze this image and respond with JSON:"""
    
    def garment_details_prompt():
        return """Look at this clothing item and identify its features.\n\nCollar: crew neck, v-neck, collar, hooded, turtleneck, scoop neck, no collar, or not applicable\nSleeves: short sleeve, long sleeve, sleeveless, three-quarter sleeve, or not applicable\nFit: fitted, regular, loose, oversized, or cannot determine\n\nExample for a t-shirt:\n{\"collar\": \"crew neck\", \"sleeves\": \"short sleeve\", \"fit\": \"regular\"}\n\nExample for a dress:\n{\"collar\": \"scoop neck\", \"sleeves\": \"sleeveless\", \"fit\": \"fitted\"}\n\nNow analyze this image and respond with JSON:"""
    
    # Define query function inside worker
    def query_smolvlm(image, prompt):
        try:
            messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
            prompt_text = processor.apply_chat_template(messages, add_generation_prompt=True)
            inputs = processor(text=prompt_text, images=[image], return_tensors="pt").to(worker_config.device)
            
            with torch.no_grad():
                generated_ids = model.generate(**inputs, max_new_tokens=worker_config.max_new_tokens, temperature=worker_config.temperature, do_sample=worker_config.do_sample)
            
            generated_texts = processor.batch_decode(generated_ids, skip_special_tokens=True)
            response_text = generated_texts[0]
            
            start_idx = response_text.find('{')
            if start_idx == -1:
                return {"error": "No JSON found in response"}
            
            brace_count = 0
            end_idx = -1
            for i in range(start_idx, len(response_text)):
                if response_text[i] == '{':
                    brace_count += 1
                elif response_text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            
            if end_idx == -1:
                return {"error": "No matching closing brace found"}
            
            json_text = response_text[start_idx:end_idx+1]
            result = json.loads(json_text)
            return result
        except Exception as e:
            return {"error": f"Inference error: {str(e)}"}
    
    # Define extract function inside worker
    def extract_attributes(image, article_type):
        results = {"extraction_success": True, "extraction_errors": []}
        
        material_result = query_smolvlm(image, material_pattern_prompt())
        if "error" in material_result:
            results["extraction_success"] = False
            results["extraction_errors"].append(f"Material: {material_result['error']}")
            results["material"] = "unknown"
            results["pattern"] = "no clear pattern"
            results["confidence_material"] = "low"
        else:
            results["material"] = material_result.get("material", "unknown")
            results["pattern"] = material_result.get("pattern", "no clear pattern")
            results["confidence_material"] = material_result.get("confidence", "low")
        
        style_result = query_smolvlm(image, style_formality_prompt())
        if "error" in style_result:
            results["extraction_success"] = False
            results["extraction_errors"].append(f"Style: {style_result['error']}")
            results["formality"] = "casual"
            results["style_keywords"] = []
            results["visual_details"] = []
        else:
            results["formality"] = style_result.get("formality", "casual")
            results["style_keywords"] = style_result.get("style_keywords", [])
            results["visual_details"] = style_result.get("details", [])
        
        apparel_types = ["Topwear", "Bottomwear", "Dress", "Innerwear", "Loungewear"]
        if any(apparel in article_type for apparel in apparel_types):
            garment_result = query_smolvlm(image, garment_details_prompt())
            if "error" in garment_result:
                results["extraction_errors"].append(f"Garment: {garment_result['error']}")
                results["collar"] = "not applicable"
                results["sleeves"] = "not applicable"
                results["fit"] = "cannot determine"
            else:
                results["collar"] = garment_result.get("collar", "not applicable")
                results["sleeves"] = garment_result.get("sleeves", "not applicable")
                results["fit"] = garment_result.get("fit", "cannot determine")
        else:
            results["collar"] = "not applicable"
            results["sleeves"] = "not applicable"
            results["fit"] = "cannot determine"
        
        return results
    
    # Process batches
    for batch_df in iterator:
        results = []
        
        for idx, row in batch_df.iterrows():
            try:
                with open(row['image_path'], 'rb') as f:
                    image = Image.open(f).convert('RGB')
                
                attrs = extract_attributes(image, row['article_type'])
                
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
                    'collar_type': attrs['collar'],
                    'sleeve_length': attrs['sleeves'],
                    'fit_type': attrs['fit'],
                    'extraction_success': attrs['extraction_success'],
                    'extraction_errors': attrs['extraction_errors']
                }
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing {row['image_path']}: {e}")
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
                    'fit_type': 'cannot determine',
                    'extraction_success': False,
                    'extraction_errors': [str(e)]
                }
                results.append(result)
        
        yield pd.DataFrame(results)

print("✅ Batch processing function created")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Process Products

# COMMAND ----------

# DBTITLE 1,Load Products for Processing
# Load products with images
products_df = spark.sql(f"""
    SELECT
        product_id,
        product_display_name,
        master_category,
        sub_category,
        article_type,
        base_color,
        price,
        gender,
        season,
        usage,
        year,
        image_path
    FROM {PRODUCTS_TABLE}
    WHERE image_path IS NOT NULL
""")

# For testing: limit to sample size
if SAMPLE_SIZE:
    products_df = products_df.limit(SAMPLE_SIZE)
    print(f"📝 Processing sample of {SAMPLE_SIZE} products")
else:
    print(f"📝 Processing full catalog")

product_count = products_df.count()
print(f"✅ Loaded {product_count:,} products")

# Repartition for parallel processing
products_df = products_df.repartition(NUM_PARTITIONS)
print(f"✅ Repartitioned to {NUM_PARTITIONS} partitions")

# COMMAND ----------

# DBTITLE 1,Extract Attributes
print("🔄 Starting attribute extraction...")
print(f"   Cluster: {MIN_WORKERS}-{MAX_WORKERS} workers with T4 GPUs")
print(f"   Strategy: Each worker loads model once per partition, then processes all images")
print(f"   Estimated time: {product_count * 3 / 60 / MAX_WORKERS:.1f}-{product_count * 3 / 60 / MIN_WORKERS:.1f} minutes")
print(f"   (3 prompts per image, ~20 images/minute per worker)")

start_time = time.time()

# Optimize partitioning for dynamic worker scaling (2-8 workers)
products_df_optimized = products_df.repartition(NUM_PARTITIONS)
print(f"   Repartitioned to {NUM_PARTITIONS} partitions for optimal parallelism")

# Define output schema for mapInPandas
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
    StructField("fit_type", StringType(), True),
    StructField("extraction_success", BooleanType(), True),
    StructField("extraction_errors", ArrayType(StringType()), True),
])

# Use mapInPandas for distributed GPU processing
# Each worker loads the model once per partition, then processes all images in that partition
print("\n🚀 Starting distributed processing across GPU workers...")
products_with_attrs = products_df_optimized.mapInPandas(process_batch, schema=output_schema)

# Trigger execution and count results
count = products_with_attrs.count()

elapsed = time.time() - start_time
print(f"\n✅ Extraction complete!")
print(f"   Processed: {count:,} products")
print(f"   Time: {elapsed/60:.1f} minutes")
print(f"   Speed: {count/(elapsed/60):.1f} products/minute")
print(f"   Effective parallelism: {(count/(elapsed/60))/20:.1f}x (vs single GPU @ 20 products/min)")

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
# MAGIC - Run full extraction (~2-3 hours for 44K products)
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
