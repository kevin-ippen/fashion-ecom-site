# Databricks notebook source
# MAGIC %md
# MAGIC # 🎨 SmolVLM-2.2B Batch Attribute Extraction (Fixed for UC Volumes)
# MAGIC
# MAGIC ## Overview
# MAGIC Extract rich semantic attributes from product images using SmolVLM-2.2B vision-language model.
# MAGIC
# MAGIC ### Fixed: Proper Unity Catalog Volumes Image Loading
# MAGIC This version correctly reads images from Unity Catalog Volumes by:
# MAGIC 1. Loading image bytes into DataFrame using Spark's `binary_file` source
# MAGIC 2. Passing bytes directly to Pandas UDF (no file path access needed)
# MAGIC 3. Using PIL Image.open() with BytesIO on raw bytes
# MAGIC
# MAGIC ### What We're Extracting
# MAGIC - **Material**: leather, denim, knit fabric, woven fabric, synthetic, metal
# MAGIC - **Pattern**: solid, striped, floral, geometric, polka dots, checkered
# MAGIC - **Formality**: formal, business casual, casual, athletic
# MAGIC - **Style Keywords**: vintage, modern, minimalist, athletic, bohemian
# MAGIC - **Visual Details**: pockets, buttons, zippers, collars, sleeves

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

# Batch processing configuration
SAMPLE_SIZE = 100  # Start with 100 products for testing
BATCH_SIZE = 8  # Process 8 images at a time on GPU
NUM_PARTITIONS = 4  # Spark parallelism

print(f"✅ Configuration loaded")
print(f"   Products Table: {PRODUCTS_TABLE}")
print(f"   Output Table: {OUTPUT_TABLE}")
print(f"   Model: {MODEL_NAME}")
print(f"   Device: {DEVICE}")
print(f"   Sample Size: {SAMPLE_SIZE} (set to None for full catalog)")

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
# MAGIC
# MAGIC (Same as original - keeping prompts)

# COMMAND ----------

# DBTITLE 1,Define Prompt Templates
class PromptTemplates:
    """Structured prompts for attribute extraction"""

    @staticmethod
    def material_pattern() -> str:
        return """Analyze this fashion product image carefully.

Identify:
1. PRIMARY MATERIAL - What is the main material? Choose EXACTLY ONE:
   - leather (shiny textured animal hide)
   - denim (blue woven cotton fabric)
   - knit fabric (stretchy soft like t-shirt or sweater)
   - woven fabric (structured like dress shirt)
   - synthetic (shiny athletic or performance fabric)
   - metal (jewelry, watches, buckles)
   - canvas (thick woven fabric)
   - unknown (cannot determine)

2. PATTERN - What pattern is visible? Choose EXACTLY ONE:
   - solid color (no pattern visible)
   - striped (lines or stripes)
   - floral print (flowers or botanical)
   - geometric (shapes or geometric patterns)
   - polka dots (dots or circles)
   - checkered (grid or plaid pattern)
   - abstract print (unclear or artistic pattern)
   - no clear pattern

3. CONFIDENCE - How confident are you in these assessments?
   - high (very certain)
   - medium (somewhat certain)
   - low (not very certain)

Respond ONLY with valid JSON in this exact format:
{
  "material": "one of the material options",
  "pattern": "one of the pattern options",
  "confidence": "high, medium, or low"
}"""

    @staticmethod
    def style_formality() -> str:
        return """Analyze this fashion product image carefully.

Identify:
1. FORMALITY LEVEL - How formal is this item? Choose EXACTLY ONE:
   - formal (suits, gowns, tuxedos, very dressy)
   - business casual (office appropriate but not a full suit)
   - casual (everyday wear like t-shirts, jeans, casual dresses)
   - athletic (sportswear, activewear, gym clothes)

2. STYLE KEYWORDS - What style best describes it? Choose UP TO 3 from this list ONLY:
   - athletic, sporty, vintage, retro, modern, contemporary
   - minimalist, simple, bohemian, hippie, streetwear, urban
   - professional, corporate, elegant, sophisticated

3. VISIBLE DETAILS - What details can you see? List any that apply from this list ONLY:
   - has pockets, has buttons, has zipper, has hood, has logo
   - has drawstrings, has belt, has collar, none visible

Respond ONLY with valid JSON in this exact format:
{
  "formality": "one of the formality options",
  "style_keywords": ["keyword1", "keyword2"],
  "details": ["detail1", "detail2"]
}"""

    @staticmethod
    def garment_details() -> str:
        return """Analyze this clothing item image carefully.

Identify:
1. COLLAR/NECKLINE - What type of collar or neckline? Choose EXACTLY ONE:
   - crew neck, v-neck, collar, hooded, turtleneck, scoop neck
   - no collar, not applicable

2. SLEEVE LENGTH - What is the sleeve length? Choose EXACTLY ONE:
   - short sleeve, long sleeve, sleeveless, three-quarter sleeve
   - not applicable

3. FIT - How does it fit? Choose EXACTLY ONE:
   - fitted, regular, loose, oversized, cannot determine

Respond ONLY with valid JSON in this exact format:
{
  "collar": "one of the collar options",
  "sleeves": "one of the sleeve options",
  "fit": "one of the fit options"
}"""

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
                # temperature removed - SmolVLM doesn't support it reliably
                do_sample=config.do_sample
            )

        # Decode response
        generated_texts = processor.batch_decode(
            generated_ids,
            skip_special_tokens=True
        )

        response_text = generated_texts[0]

        # IMPROVED: Extract JSON more carefully (handles extra text after JSON)
        # SmolVLM sometimes adds commentary after JSON

        # Find start of JSON
        start_idx = response_text.find('{')
        if start_idx == -1:
            return {"error": "No JSON found in response", "raw_response": response_text[:300]}

        # Strategy: Find first complete JSON object (stop at first valid parse)
        stack = []
        for i, char in enumerate(response_text[start_idx:], start=start_idx):
            if char == '{':
                stack.append(i)
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack:  # Found complete JSON object!
                        json_text = response_text[start_idx:i+1]
                        try:
                            result = json.loads(json_text)
                            return result  # Success!
                        except json.JSONDecodeError:
                            continue  # Try next closing brace

        # Fallback: Extract between first { and last }
        end_idx = response_text.rfind('}')
        if end_idx != -1:
            json_text = response_text[start_idx:end_idx+1]
            try:
                result = json.loads(json_text)
                return result
            except json.JSONDecodeError as e:
                return {
                    "error": f"JSON parse error: {str(e)}",
                    "raw_response": response_text[:300]
                }

        return {"error": "No valid JSON found", "raw_response": response_text[:300]}

    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {str(e)}", "raw_response": response_text[:300]}
    except Exception as e:
        return {"error": f"Inference error: {str(e)}"}


def extract_attributes(image: Image.Image, article_type: str, config: SmolVLMConfig) -> Dict:
    """
    Extract all attributes using multi-stage prompts

    Args:
        image: PIL Image
        article_type: Product article type
        config: Model configuration

    Returns:
        Dictionary with all extracted attributes
    """
    results = {
        "extraction_success": True,
        "extraction_errors": []
    }

    # Stage 1: Material & Pattern
    material_result = query_smolvlm(image, prompts.material_pattern(), config)

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

    # Stage 2: Style & Formality
    style_result = query_smolvlm(image, prompts.style_formality(), config)

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

    # Stage 3: Garment Details (only for apparel)
    apparel_types = ["Topwear", "Bottomwear", "Dress", "Innerwear", "Loungewear"]

    if any(apparel in article_type for apparel in apparel_types):
        garment_result = query_smolvlm(image, prompts.garment_details(), config)

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
        results["fit"] = "not applicable"

    return results

print("✅ Inference functions defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📸 Load Images from Unity Catalog Volumes
# MAGIC
# MAGIC **KEY FIX**: Read image bytes into DataFrame first, then pass to UDF

# COMMAND ----------

# DBTITLE 1,Load Products with Image Bytes
print("📂 Loading products with images from Unity Catalog Volumes...")

# Load product metadata
products_metadata = spark.sql(f"""
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

# Apply sample limit for testing
if SAMPLE_SIZE:
    products_metadata = products_metadata.limit(SAMPLE_SIZE)
    print(f"📝 Processing sample of {SAMPLE_SIZE} products")

product_count = products_metadata.count()
print(f"✅ Loaded {product_count:,} product records")

# CRITICAL: Read image bytes using Spark's binary_file format
# This properly handles Unity Catalog Volumes paths
print("\n🔄 Reading image bytes from Unity Catalog Volumes...")

# Create path for binary file reading (need to get directory)
# Extract directory from first image_path
first_image_path = products_metadata.select("image_path").first()[0]
import os
image_dir = os.path.dirname(first_image_path)

print(f"   Image directory: {image_dir}")

# Read all images as binary files
images_binary = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.jpg") \
    .option("recursiveFileLookup", "false") \
    .load(image_dir)

print(f"✅ Read binary images")

# Extract product_id from path and join with metadata
images_binary = images_binary.withColumn(
    "product_id",
    F.regexp_extract(F.col("path"), r"(\d+)\.jpg$", 1).cast("int")
)

# Join metadata with image bytes
products_df = products_metadata.join(
    images_binary.select("product_id", "content"),
    on="product_id",
    how="inner"
)

print(f"✅ Joined {products_df.count():,} products with image data")
print(f"   Schema includes 'content' column with image bytes")

# Repartition for parallel processing
products_df = products_df.repartition(NUM_PARTITIONS)
print(f"✅ Repartitioned to {NUM_PARTITIONS} partitions")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Test on Sample Image

# COMMAND ----------

# DBTITLE 1,Test Single Image with Bytes
# Test with first product
sample_row = products_df.select("product_display_name", "article_type", "content").first()

print("🔍 Testing on sample product:")
print(f"   Product: {sample_row['product_display_name']}")
print(f"   Article Type: {sample_row['article_type']}")
print(f"   Image bytes: {len(sample_row['content'])} bytes")

try:
    # Load image from bytes
    image = Image.open(io.BytesIO(sample_row['content'])).convert('RGB')
    print(f"✅ Image loaded from bytes: {image.size}")

    # Extract attributes
    print("\n🔄 Extracting attributes...")
    attributes = extract_attributes(image, sample_row['article_type'], config)

    print("\n✅ Extraction complete!")
    print(json.dumps(attributes, indent=2))

except Exception as e:
    print(f"❌ Error testing: {e}")
    import traceback
    traceback.print_exc()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚀 Batch Processing with Spark
# MAGIC
# MAGIC **FIXED**: Pandas UDF now receives image bytes, not paths

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

# DBTITLE 1,Create Pandas UDF for Batch Processing (FIXED)
from pyspark.sql.functions import pandas_udf

@pandas_udf(attributes_schema)
def extract_attributes_udf(image_bytes_series: pd.Series, article_types: pd.Series) -> pd.DataFrame:
    """
    Pandas UDF for batch attribute extraction

    FIXED: Receives image bytes instead of file paths
    This works reliably with Unity Catalog Volumes

    Args:
        image_bytes_series: Series of binary image data
        article_types: Series of article type strings

    Returns:
        DataFrame with extracted attributes
    """
    results = []

    for image_bytes, article_type in zip(image_bytes_series, article_types):
        try:
            # Load image from bytes (no file access needed!)
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

            # Extract attributes
            attrs = extract_attributes(image, article_type, config)

            results.append(attrs)

        except Exception as e:
            # Return error result
            logger.error(f"Error processing image: {e}")
            results.append({
                "material": "unknown",
                "pattern": "no clear pattern",
                "confidence_material": "low",
                "formality": "casual",
                "style_keywords": [],
                "visual_details": [],
                "collar": "not applicable",
                "sleeves": "not applicable",
                "fit": "cannot determine",
                "extraction_success": False,
                "extraction_errors": [str(e)]
            })

    return pd.DataFrame(results)

print("✅ Pandas UDF created (receives image bytes)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Process Products

# COMMAND ----------

# DBTITLE 1,Extract Attributes
print("🔄 Starting attribute extraction...")
print(f"   This will take approximately {product_count * 3 / 60:.1f} minutes")
print(f"   (3 prompts per image, ~20 images/minute)")

start_time = time.time()

# Apply UDF to extract attributes (FIXED: pass bytes, not paths)
products_with_attrs = products_df.withColumn(
    "extracted_attrs",
    extract_attributes_udf(
        F.col("content"),  # Image bytes!
        F.col("article_type")
    )
)

# Expand struct into columns
products_with_attrs = products_with_attrs.select(
    "product_id",
    "product_display_name",
    "master_category",
    "sub_category",
    "article_type",
    "base_color",
    "price",
    "gender",
    "season",
    "usage",
    "year",
    "image_path",
    F.col("extracted_attrs.material").alias("material"),
    F.col("extracted_attrs.pattern").alias("pattern"),
    F.col("extracted_attrs.confidence_material").alias("confidence_material"),
    F.col("extracted_attrs.formality").alias("formality"),
    F.col("extracted_attrs.style_keywords").alias("style_keywords"),
    F.col("extracted_attrs.visual_details").alias("visual_details"),
    F.col("extracted_attrs.collar").alias("collar_type"),
    F.col("extracted_attrs.sleeves").alias("sleeve_length"),
    F.col("extracted_attrs.fit").alias("fit_type"),
    F.col("extracted_attrs.extraction_success").alias("extraction_success"),
    F.col("extracted_attrs.extraction_errors").alias("extraction_errors")
)

# Cache result
products_with_attrs.cache()
count = products_with_attrs.count()

elapsed = time.time() - start_time
print(f"\n✅ Extraction complete!")
print(f"   Processed: {count:,} products")
print(f"   Time: {elapsed/60:.1f} minutes")
print(f"   Speed: {count/(elapsed/60):.1f} products/minute")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📈 Quality Analysis
# MAGIC
# MAGIC (Same validation as original - omitted for brevity)

# COMMAND ----------

# DBTITLE 1,Analyze Extraction Quality
print("=" * 80)
print("EXTRACTION QUALITY REPORT")
print("=" * 80)

# Success rate
success_count = products_with_attrs.filter(F.col("extraction_success") == True).count()
success_rate = success_count / count * 100
print(f"\n✅ Success Rate: {success_rate:.1f}% ({success_count:,}/{count:,})")

# Material distribution
print("\n📊 Material Distribution:")
products_with_attrs.groupBy("material").count().orderBy(F.desc("count")).show(20)

# Pattern distribution
print("\n📊 Pattern Distribution:")
products_with_attrs.groupBy("pattern").count().orderBy(F.desc("count")).show(20)

# Formality distribution
print("\n📊 Formality Distribution:")
products_with_attrs.groupBy("formality").count().orderBy(F.desc("count")).show(10)

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Key Improvements in This Version
# MAGIC
# MAGIC ### ✅ Fixed Unity Catalog Volumes Access
# MAGIC 1. **Before**: Used `open(image_path)` - unreliable in distributed UDF
# MAGIC 2. **After**: Used `spark.read.format("binaryFile")` - proper distributed file reading
# MAGIC 3. **Result**: Image bytes loaded directly into DataFrame, no filesystem access in UDF
# MAGIC
# MAGIC ### ✅ More Reliable Processing
# MAGIC - Pandas UDF receives raw bytes, not paths
# MAGIC - No dependency on FUSE mounts on worker nodes
# MAGIC - Works with any Spark-accessible file system
# MAGIC - Easier to debug (bytes are in DataFrame)
# MAGIC
# MAGIC ### Next Steps
# MAGIC 1. Review quality metrics above
# MAGIC 2. If success rate >85%, scale to full catalog (set SAMPLE_SIZE = None)
# MAGIC 3. Run join SQL to create enriched products table
# MAGIC 4. Generate new CLIP embeddings from rich descriptions

# COMMAND ----------
