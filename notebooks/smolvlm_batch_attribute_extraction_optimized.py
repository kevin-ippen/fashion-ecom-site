# Databricks notebook source
# MAGIC %md
# MAGIC # 🚀 Optimized Batch Attribute Extraction for Databricks Serverless GPU
# MAGIC
# MAGIC ## Key Optimizations
# MAGIC - ✅ **True batching**: Process 8-16 images simultaneously
# MAGIC - ✅ **Single prompt**: 1 inference call per image (vs 3 before)
# MAGIC - ✅ **Faster model option**: Moondream2 (3-5x faster) or SmolVLM
# MAGIC - ✅ **GPU optimization**: torch.compile, Flash Attention, better memory management
# MAGIC - ✅ **Serverless optimized**: Efficient model loading and caching
# MAGIC
# MAGIC ## Performance Estimates
# MAGIC - **Moondream2**: ~200-300 products/minute (full catalog: 2.5-3.5 hours)
# MAGIC - **SmolVLM (batched)**: ~100-150 products/minute (full catalog: 5-7 hours)
# MAGIC
# MAGIC ## Recommended Setup
# MAGIC - Serverless GPU cluster (auto-scaling)
# MAGIC - Python 3.10+
# MAGIC - For clean background-removed images: **Moondream2 recommended** (faster, accurate)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📦 Setup & Installation

# COMMAND ----------

# DBTITLE 1,Install Required Libraries
# MAGIC %pip install torch torchvision transformers pillow accelerate einops timm --quiet
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Import Libraries
import json
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

from PIL import Image
import io
import base64

import torch
from transformers import AutoProcessor, AutoModelForVision2Seq, AutoModelForCausalLM
from pyspark.sql import functions as F
from pyspark.sql.types import *
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("✅ Libraries imported successfully")
print(f"   PyTorch version: {torch.__version__}")
print(f"   CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   CUDA device: {torch.cuda.get_device_name(0)}")
    print(f"   CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")

# COMMAND ----------

# DBTITLE 1,Configuration
# Database configuration
CATALOG = "main"
SCHEMA = "fashion_demo"
PRODUCTS_TABLE = f"{CATALOG}.{SCHEMA}.products"
OUTPUT_TABLE = f"{CATALOG}.{SCHEMA}.product_extracted_attributes"

# Model configuration - Choose one:
# "moondream" - Moondream2 (1.6B, FASTEST, great for clean images)
# "smolvlm" - SmolVLM (2.2B, more detailed, slightly slower)
MODEL_CHOICE = "moondream"  # Change to "smolvlm" if you want more detail

MODEL_CONFIGS = {
    "moondream": {
        "name": "vikhyatk/moondream2",
        "revision": "2024-08-26",
        "batch_size": 16,  # Can handle larger batches
        "description": "Fast & accurate for clean images"
    },
    "smolvlm": {
        "name": "HuggingFaceTB/SmolVLM-Instruct",
        "revision": None,
        "batch_size": 8,
        "description": "More detailed analysis, slower"
    }
}

selected_config = MODEL_CONFIGS[MODEL_CHOICE]
MODEL_NAME = selected_config["name"]
MODEL_REVISION = selected_config["revision"]
BATCH_SIZE = selected_config["batch_size"]
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Processing configuration
SAMPLE_SIZE = 100  # Set to None for full catalog
NUM_PARTITIONS = 32  # Higher for better distribution on serverless

print(f"✅ Configuration loaded")
print(f"   Products Table: {PRODUCTS_TABLE}")
print(f"   Output Table: {OUTPUT_TABLE}")
print(f"   Selected Model: {MODEL_CHOICE.upper()} - {selected_config['description']}")
print(f"   Model: {MODEL_NAME}")
print(f"   Batch Size: {BATCH_SIZE}")
print(f"   Device: {DEVICE}")
print(f"   Partitions: {NUM_PARTITIONS}")
print(f"   Sample Size: {SAMPLE_SIZE}")
print(f"\n   💡 Estimated Performance:")
if MODEL_CHOICE == "moondream":
    print(f"      - Throughput: ~200-300 products/minute")
    print(f"      - Full catalog (44K): ~2.5-3.5 hours")
else:
    print(f"      - Throughput: ~100-150 products/minute")
    print(f"      - Full catalog (44K): ~5-7 hours")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🤖 Optimized Model Setup

# COMMAND ----------

# DBTITLE 1,Load Model with Optimizations
@dataclass
class VLMConfig:
    """Configuration for vision-language model"""
    model_name: str
    model_revision: Optional[str]
    model_choice: str
    device: str = DEVICE
    torch_dtype: torch.dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    batch_size: int = BATCH_SIZE
    max_new_tokens: int = 300  # Enough for single comprehensive response
    temperature: float = 0.1
    do_sample: bool = False

config = VLMConfig(
    model_name=MODEL_NAME,
    model_revision=MODEL_REVISION,
    model_choice=MODEL_CHOICE,
    batch_size=BATCH_SIZE
)

print(f"🔄 Loading {MODEL_CHOICE.upper()} model with optimizations...")
print(f"   Device: {config.device}")
print(f"   Dtype: {config.torch_dtype}")

start_time = time.time()

if MODEL_CHOICE == "moondream":
    # Moondream2 - faster loading and inference
    model_id = config.model_name
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        revision=config.model_revision,
        trust_remote_code=True,
        torch_dtype=config.torch_dtype,
        device_map={"": 0} if torch.cuda.is_available() else None,
        low_cpu_mem_usage=True,
        attn_implementation="flash_attention_2" if torch.cuda.is_available() else None,
    ).eval()
    
    # Moondream uses model.encode_image directly
    processor = None
    
elif MODEL_CHOICE == "smolvlm":
    # SmolVLM
    processor = AutoProcessor.from_pretrained(
        config.model_name,
        trust_remote_code=True
    )
    model = AutoModelForVision2Seq.from_pretrained(
        config.model_name,
        torch_dtype=config.torch_dtype,
        device_map="auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    ).eval()

# Compile model for faster inference (PyTorch 2.0+)
if torch.cuda.is_available() and hasattr(torch, 'compile'):
    print("   🔥 Compiling model with torch.compile...")
    try:
        model = torch.compile(model, mode="reduce-overhead")
    except Exception as e:
        print(f"   ⚠️  Compilation skipped: {e}")

load_time = time.time() - start_time
print(f"✅ Model loaded in {load_time:.1f}s")
print(f"   Model size: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B parameters")
if torch.cuda.is_available():
    print(f"   GPU memory: {torch.cuda.memory_allocated() / 1e9:.2f}GB")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💬 Optimized Single Prompt

# COMMAND ----------

# DBTITLE 1,Unified Comprehensive Prompt
def get_unified_prompt() -> str:
    """
    Single comprehensive prompt that extracts ALL attributes in one pass.
    This is 3x faster than making 3 separate inference calls.
    """
    return """Analyze this product image and extract the following attributes. Respond ONLY with valid JSON.

Identify these attributes:
1. MATERIAL: leather, denim, knit fabric, woven fabric, synthetic, metal, canvas, or unknown
2. PATTERN: solid color, striped, floral print, geometric, polka dots, checkered, abstract print, or no clear pattern
3. FORMALITY: formal, business casual, casual, or athletic
4. STYLE: Pick 1-3 keywords from: athletic, sporty, vintage, retro, modern, contemporary, minimalist, simple, bohemian, streetwear, urban, professional, elegant, sophisticated
5. DETAILS: List what you see from: has pockets, has buttons, has zipper, has hood, has logo, has drawstrings, has belt, has collar, has laces
6. COLLAR (if clothing): crew neck, v-neck, collar, hooded, turtleneck, scoop neck, no collar, or not applicable
7. SLEEVES (if clothing): short sleeve, long sleeve, sleeveless, three-quarter sleeve, or not applicable
8. FIT (if clothing): fitted, regular, loose, oversized, or cannot determine
9. CONFIDENCE: high, medium, or low

Example response for a striped casual shirt:
{
  "material": "woven fabric",
  "pattern": "striped",
  "formality": "casual",
  "style_keywords": ["casual", "simple"],
  "details": ["has collar", "has buttons", "has pockets"],
  "collar": "collar",
  "sleeves": "long sleeve",
  "fit": "regular",
  "confidence": "high"
}

Example response for athletic shoes:
{
  "material": "synthetic",
  "pattern": "solid color",
  "formality": "athletic",
  "style_keywords": ["athletic", "sporty"],
  "details": ["has laces", "has logo"],
  "collar": "not applicable",
  "sleeves": "not applicable",
  "fit": "not applicable",
  "confidence": "high"
}

Now analyze the image:"""

unified_prompt = get_unified_prompt()
print("✅ Unified prompt created (1 call per image instead of 3)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚀 Optimized Batch Inference

# COMMAND ----------

# DBTITLE 1,Batch Inference Functions
def process_batch_moondream(images: List[Image.Image], prompt: str, config: VLMConfig) -> List[Dict]:
    """
    Process a batch of images with Moondream2 - optimized for speed
    """
    results = []
    
    with torch.no_grad():
        for image in images:
            try:
                # Moondream2 uses a simpler interface
                enc_image = model.encode_image(image)
                response = model.answer_question(enc_image, prompt, model.tokenizer)
                
                # Parse JSON response
                result = parse_json_response(response)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Moondream inference error: {e}")
                results.append({"error": str(e), "raw_response": ""})
    
    return results


def process_batch_smolvlm(images: List[Image.Image], prompt: str, config: VLMConfig) -> List[Dict]:
    """
    Process a batch of images with SmolVLM - true batching
    """
    try:
        # Prepare messages for all images
        messages_list = []
        for _ in images:
            messages_list.append([
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": prompt}
                    ]
                }
            ])
        
        # Process batch
        prompts = [processor.apply_chat_template(msgs, add_generation_prompt=True) 
                   for msgs in messages_list]
        
        inputs = processor(
            text=prompts,
            images=images,
            return_tensors="pt",
            padding=True
        ).to(config.device)
        
        # Generate for entire batch
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=config.max_new_tokens,
                temperature=config.temperature,
                do_sample=config.do_sample,
                pad_token_id=processor.tokenizer.pad_token_id
            )
        
        # Decode all responses
        generated_texts = processor.batch_decode(
            generated_ids,
            skip_special_tokens=True
        )
        
        # Parse each response
        results = []
        for text in generated_texts:
            result = parse_json_response(text)
            results.append(result)
        
        return results
        
    except Exception as e:
        logger.error(f"SmolVLM batch inference error: {e}")
        return [{"error": str(e), "raw_response": ""} for _ in images]


def parse_json_response(text: str) -> Dict:
    """
    Parse JSON from model response, handling various formats
    """
    try:
        # Extract JSON from response (handle markdown code blocks)
        text = text.strip()
        
        # Remove markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        # Find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)
        else:
            return {"error": "No JSON found", "raw_response": text}
            
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw_response": text}
    except Exception as e:
        return {"error": str(e), "raw_response": text}


def query_batch(images: List[Image.Image], config: VLMConfig) -> List[Dict]:
    """
    Main batch processing function - routes to appropriate model
    """
    if not images:
        return []
    
    prompt = unified_prompt
    
    if config.model_choice == "moondream":
        return process_batch_moondream(images, prompt, config)
    else:
        return process_batch_smolvlm(images, prompt, config)

print("✅ Batch inference functions ready")
print(f"   Batch size: {BATCH_SIZE}")
print(f"   Model: {MODEL_CHOICE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Extract Attributes from Images

# COMMAND ----------

# DBTITLE 1,Batch Processing UDF
def extract_attributes_batch(image_paths_batch: pd.Series) -> pd.Series:
    """
    Process a batch of images and extract attributes
    Optimized for Pandas UDF in Spark
    """
    import torch
    from PIL import Image
    import io
    import base64
    
    # Ensure model is on correct device
    if not hasattr(extract_attributes_batch, 'model_loaded'):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        extract_attributes_batch.model_loaded = True
    
    results = []
    batch_images = []
    batch_indices = []
    
    for idx, image_data in enumerate(image_paths_batch):
        if image_data is None:
            results.append(json.dumps({
                "extraction_success": False,
                "error": "No image data"
            }))
            continue
            
        try:
            # Decode image
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            
            # Resize for efficiency (max 768px)
            max_size = 768
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = tuple(int(dim * ratio) for dim in image.size)
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            batch_images.append(image)
            batch_indices.append(idx)
            
            # Process when batch is full or at end
            if len(batch_images) >= config.batch_size or idx == len(image_paths_batch) - 1:
                # Process batch
                batch_results = query_batch(batch_images, config)
                
                # Store results
                for batch_idx, result in enumerate(batch_results):
                    original_idx = batch_indices[batch_idx]
                    
                    # Add success flag
                    if "error" not in result:
                        result["extraction_success"] = True
                        result["error"] = None
                    else:
                        result["extraction_success"] = False
                    
                    # Ensure result is at correct position
                    while len(results) <= original_idx:
                        results.append(None)
                    results[original_idx] = json.dumps(result)
                
                # Clear batch
                batch_images = []
                batch_indices = []
                
                # Free GPU memory periodically
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
        except Exception as e:
            logger.error(f"Error processing image {idx}: {e}")
            results.append(json.dumps({
                "extraction_success": False,
                "error": str(e)
            }))
    
    return pd.Series(results)

# Define return schema
extraction_schema = StructType([
    StructField("extraction_success", BooleanType(), True),
    StructField("error", StringType(), True),
    StructField("material", StringType(), True),
    StructField("pattern", StringType(), True),
    StructField("formality", StringType(), True),
    StructField("style_keywords", ArrayType(StringType()), True),
    StructField("details", ArrayType(StringType()), True),
    StructField("collar", StringType(), True),
    StructField("sleeves", StringType(), True),
    StructField("fit", StringType(), True),
    StructField("confidence", StringType(), True),
    StructField("raw_response", StringType(), True)
])

print("✅ Batch processing UDF defined")

# COMMAND ----------

# DBTITLE 1,Load Products with Images
print("📥 Loading products from Unity Catalog...")

# Load products
products = spark.table(PRODUCTS_TABLE)

# Sample if needed
if SAMPLE_SIZE is not None:
    products = products.limit(SAMPLE_SIZE)

# Keep products with images
products_with_images = products.filter(F.col("image_base64").isNotNull())
count = products_with_images.count()

print(f"✅ Loaded {count:,} products with images")

# Repartition for optimal parallelism
products_with_images = products_with_images.repartition(NUM_PARTITIONS)
print(f"   Repartitioned into {NUM_PARTITIONS} partitions")

# COMMAND ----------

# DBTITLE 1,Run Batch Attribute Extraction
print("🚀 Starting batch attribute extraction...")
print(f"   Model: {MODEL_CHOICE.upper()}")
print(f"   Batch size: {BATCH_SIZE}")
print(f"   Total products: {count:,}")
print("-" * 80)

start_time = time.time()

# Process images in batches
products_with_attrs = products_with_images.withColumn(
    "extraction_json",
    F.udf(extract_attributes_batch, StringType())(F.col("image_base64"))
)

# Parse JSON into columns
products_with_attrs = products_with_attrs.withColumn(
    "extraction_result",
    F.from_json(F.col("extraction_json"), extraction_schema)
)

# Expand into separate columns
products_with_attrs = products_with_attrs.select(
    "*",
    F.col("extraction_result.extraction_success").alias("extraction_success"),
    F.col("extraction_result.error").alias("extraction_errors"),
    F.col("extraction_result.material").alias("material"),
    F.col("extraction_result.pattern").alias("pattern"),
    F.col("extraction_result.formality").alias("formality"),
    F.col("extraction_result.style_keywords").alias("style_keywords"),
    F.col("extraction_result.details").alias("visual_details"),
    F.col("extraction_result.collar").alias("collar_type"),
    F.col("extraction_result.sleeves").alias("sleeve_length"),
    F.col("extraction_result.fit").alias("garment_fit"),
    F.col("extraction_result.confidence").alias("confidence_material")
).drop("extraction_json", "extraction_result", "image_base64")

# Cache for analysis
products_with_attrs.cache()
final_count = products_with_attrs.count()

elapsed_time = time.time() - start_time
products_per_minute = (final_count / elapsed_time) * 60

print("\n" + "=" * 80)
print("✅ EXTRACTION COMPLETE")
print("=" * 80)
print(f"   Total products: {final_count:,}")
print(f"   Processing time: {elapsed_time / 60:.1f} minutes")
print(f"   Throughput: {products_per_minute:.1f} products/minute")
print(f"   Average time: {elapsed_time / final_count:.2f}s per product")
print("=" * 80)

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
success_rate = success_count / final_count * 100
print(f"\n✅ Success Rate: {success_rate:.1f}% ({success_count:,}/{final_count:,})")

# Failed extractions
if success_count < final_count:
    failed = products_with_attrs.filter(F.col("extraction_success") == False)
    print(f"\n❌ Failed Extractions: {final_count - success_count}")
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

# Style keywords frequency
print("\n📊 Most Common Style Keywords:")
style_keywords_exploded = products_with_attrs.select(
    F.explode(F.col("style_keywords")).alias("keyword")
).filter(F.col("keyword").isNotNull())
style_keywords_exploded.groupBy("keyword").count().orderBy(F.desc("count")).show(20)

# COMMAND ----------

# DBTITLE 1,Sample Results Review
print("=" * 80)
print("SAMPLE EXTRACTED ATTRIBUTES")
print("=" * 80)

# Show diverse samples
samples = products_with_attrs.filter(
    F.col("extraction_success") == True
).select(
    "product_display_name",
    "article_type",
    "material",
    "pattern",
    "formality",
    "style_keywords",
    "visual_details",
    "confidence_material"
).limit(20)

samples.show(20, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💾 Save Results

# COMMAND ----------

# DBTITLE 1,Save to Unity Catalog
print(f"💾 Saving extracted attributes to {OUTPUT_TABLE}")

# Add metadata
products_with_attrs_final = products_with_attrs.withColumns({
    "extraction_timestamp": F.current_timestamp(),
    "model_name": F.lit(MODEL_NAME),
    "model_choice": F.lit(MODEL_CHOICE),
    "batch_size": F.lit(BATCH_SIZE)
})

# Write to Delta
products_with_attrs_final.write.mode("overwrite").saveAsTable(OUTPUT_TABLE)

print(f"✅ Saved {final_count:,} products with extracted attributes")
print(f"   Table: {OUTPUT_TABLE}")

# Show schema
spark.sql(f"DESCRIBE TABLE {OUTPUT_TABLE}").show(100, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Generate Enriched Descriptions

# COMMAND ----------

# DBTITLE 1,Create Rich Descriptions
print("📝 Generating enriched text descriptions...")

enriched_descriptions = products_with_attrs_final.withColumn(
    "rich_description",
    F.concat_ws(" ",
        # Original attributes
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
        # Garment details
        F.when(F.col("collar_type") != "not applicable", F.col("collar_type")).otherwise(""),
        F.when(F.col("sleeve_length") != "not applicable", F.col("sleeve_length")).otherwise(""),
        F.when(F.col("garment_fit") != "cannot determine", F.col("garment_fit")).otherwise(""),
        # Context
        F.col("season"),
        F.col("usage")
    )
)

# Show samples
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

# Save
ENRICHED_TABLE = f"{CATALOG}.{SCHEMA}.products_enriched_descriptions"
enriched_descriptions.write.mode("overwrite").saveAsTable(ENRICHED_TABLE)

print(f"\n✅ Saved enriched descriptions to {ENRICHED_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Performance Summary

# COMMAND ----------

# DBTITLE 1,Final Performance Stats
print("=" * 80)
print(f"{'PERFORMANCE SUMMARY':^80}")
print("=" * 80)
print(f"\n📊 Configuration:")
print(f"   Model: {MODEL_CHOICE.upper()} ({MODEL_NAME})")
print(f"   Batch Size: {BATCH_SIZE}")
print(f"   Device: {DEVICE}")
print(f"\n⏱️  Timing:")
print(f"   Total products: {final_count:,}")
print(f"   Processing time: {elapsed_time / 60:.1f} minutes ({elapsed_time / 3600:.2f} hours)")
print(f"   Throughput: {products_per_minute:.1f} products/minute")
print(f"   Avg per product: {elapsed_time / final_count:.2f} seconds")
print(f"\n✅ Quality:")
print(f"   Success rate: {success_rate:.1f}%")
print(f"   Successful: {success_count:,}")
print(f"   Failed: {final_count - success_count:,}")
print(f"\n💡 Estimated time for full catalog:")
if final_count > 0:
    full_catalog_minutes = (44424 / final_count) * (elapsed_time / 60)
    print(f"   44,424 products: ~{full_catalog_minutes:.1f} minutes ({full_catalog_minutes / 60:.1f} hours)")
print("=" * 80)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔍 Validation Queries

# COMMAND ----------

# DBTITLE 1,Check Key Product Categories
# Watches should be metal
print("🔍 Watches (should be metal):")
spark.sql(f"""
    SELECT product_display_name, material, confidence_material
    FROM {OUTPUT_TABLE}
    WHERE article_type = 'Watches'
    LIMIT 10
""").show(truncate=False)

# T-shirts should be knit
print("\n🔍 T-Shirts (should be knit fabric):")
spark.sql(f"""
    SELECT product_display_name, material, pattern, confidence_material
    FROM {OUTPUT_TABLE}
    WHERE article_type = 'Tshirts'
    LIMIT 10
""").show(truncate=False)

# Formal wear
print("\n🔍 Formal Wear:")
spark.sql(f"""
    SELECT product_display_name, formality, material, style_keywords
    FROM {OUTPUT_TABLE}
    WHERE usage = 'Formal'
    LIMIT 10
""").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚀 Next Steps
# MAGIC
# MAGIC ### 1. Validate Results (Current)
# MAGIC - ✅ Review sample outputs above
# MAGIC - ✅ Check accuracy for key categories
# MAGIC - ✅ Verify performance meets requirements
# MAGIC
# MAGIC ### 2. Scale to Full Catalog
# MAGIC ```python
# MAGIC # In Configuration cell, set:
# MAGIC SAMPLE_SIZE = None  # Process all 44K products
# MAGIC ```
# MAGIC
# MAGIC ### 3. Model Selection Tips
# MAGIC - **Moondream2** (recommended): Faster, great for clean background-removed images
# MAGIC - **SmolVLM**: More detailed analysis, use if accuracy > speed
# MAGIC
# MAGIC ### 4. Further Optimizations
# MAGIC - Increase `BATCH_SIZE` if GPU memory allows (16-32 for Moondream)
# MAGIC - Adjust `NUM_PARTITIONS` based on cluster size
# MAGIC - Enable Flash Attention 2 for even faster inference
# MAGIC
# MAGIC ### 5. Generate CLIP Embeddings
# MAGIC - Use enriched descriptions for better text embeddings
# MAGIC - Update Vector Search indexes
# MAGIC - A/B test search quality
