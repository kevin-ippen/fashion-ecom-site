# Databricks notebook source
# MAGIC %md
# MAGIC # 🖥️ CPU-Optimized Distributed Batch Attribute Extraction
# MAGIC
# MAGIC ## Key Optimizations for CPU Clusters
# MAGIC - ✅ **Distributed processing**: Each worker processes images in parallel
# MAGIC - ✅ **Model quantization**: INT8 quantization for 2-4x faster CPU inference
# MAGIC - ✅ **Optimized models**: Moondream2 or lightweight alternatives
# MAGIC - ✅ **Smart batching**: Small batches (2-4) optimized for CPU
# MAGIC - ✅ **Resource management**: One model per worker, efficient memory usage
# MAGIC
# MAGIC ## Performance Estimates (CPU Cluster)
# MAGIC - **8 workers**: ~80-120 products/minute (44K catalog: 6-9 hours)
# MAGIC - **16 workers**: ~160-240 products/minute (44K catalog: 3-5 hours)
# MAGIC - **32 workers**: ~320-480 products/minute (44K catalog: 1.5-2.5 hours)
# MAGIC
# MAGIC ## Cost Comparison
# MAGIC - CPU cluster: ~$0.10-0.20/hour per worker
# MAGIC - 16 workers × 4 hours = **$6-13 total** (cheaper than GPU!)
# MAGIC
# MAGIC ## Recommended Cluster
# MAGIC - Standard_D4s_v3 or similar (4 cores, 16GB RAM per worker)
# MAGIC - 16-32 workers for optimal throughput
# MAGIC - Auto-scaling enabled

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📦 Setup & Installation

# COMMAND ----------

# DBTITLE 1,Install Required Libraries
# MAGIC %pip install torch torchvision transformers pillow accelerate einops timm optimum --quiet
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
from transformers import AutoProcessor, AutoModelForVision2Seq, AutoModelForCausalLM, BitsAndBytesConfig
from pyspark.sql import functions as F
from pyspark.sql.types import *
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("✅ Libraries imported successfully")
print(f"   PyTorch version: {torch.__version__}")
print(f"   Number of CPU cores: {torch.get_num_threads()}")

# COMMAND ----------

# DBTITLE 1,Configuration
# Database configuration
CATALOG = "main"
SCHEMA = "fashion_demo"
PRODUCTS_TABLE = f"{CATALOG}.{SCHEMA}.products"
OUTPUT_TABLE = f"{CATALOG}.{SCHEMA}.product_extracted_attributes_cpu"

# ============================================================================
# SCALING PRESETS - Choose one based on your needs
# ============================================================================
# Uncomment ONE of these presets:

# PRESET 1: Testing (8 workers) - Fast validation
# CLUSTER_PRESET = "test"

# PRESET 2: Balanced (16 workers) - Good cost/performance
CLUSTER_PRESET = "balanced"

# PRESET 3: Fast (32 workers) - Faster processing
# CLUSTER_PRESET = "fast"

# PRESET 4: Maximum Speed (64 workers) - Fastest option
# CLUSTER_PRESET = "max_speed"

# PRESET 5: Custom - Set your own values below
# CLUSTER_PRESET = "custom"

# Preset configurations
PRESETS = {
    "test": {
        "workers": 8,
        "partitions": 32,
        "throughput_min": 80,
        "throughput_max": 120,
        "time_hours": "6-9 hours"
    },
    "balanced": {
        "workers": 16,
        "partitions": 64,
        "throughput_min": 160,
        "throughput_max": 240,
        "time_hours": "3-4.5 hours"
    },
    "fast": {
        "workers": 32,
        "partitions": 128,
        "throughput_min": 320,
        "throughput_max": 480,
        "time_hours": "1.5-2.5 hours"
    },
    "max_speed": {
        "workers": 64,
        "partitions": 256,
        "throughput_min": 640,
        "throughput_max": 960,
        "time_hours": "45-70 minutes"
    },
    "custom": {
        "workers": 16,  # Set your desired worker count
        "partitions": 64,  # Typically 2-4x workers
        "throughput_min": None,
        "throughput_max": None,
        "time_hours": "varies"
    }
}

preset_config = PRESETS[CLUSTER_PRESET]
EXPECTED_WORKERS = preset_config["workers"]
NUM_PARTITIONS = preset_config["partitions"]

# Model configuration for CPU
# "moondream" - Best for CPU (1.6B, fastest)
# "smolvlm" - More detailed but slower on CPU
MODEL_CHOICE = "moondream"  # Recommended for CPU

MODEL_CONFIGS = {
    "moondream": {
        "name": "vikhyatk/moondream2",
        "revision": "2024-08-26",
        "batch_size": 2,  # Smaller batches for CPU
        "description": "Fastest on CPU, great for clean images"
    },
    "smolvlm": {
        "name": "HuggingFaceTB/SmolVLM-Instruct",
        "revision": None,
        "batch_size": 1,  # Even smaller for CPU
        "description": "More detailed, slower on CPU"
    }
}

selected_config = MODEL_CONFIGS[MODEL_CHOICE]
MODEL_NAME = selected_config["name"]
MODEL_REVISION = selected_config["revision"]
BATCH_SIZE_PER_WORKER = selected_config["batch_size"]

# CPU-specific optimizations
USE_QUANTIZATION = True  # INT8 quantization for 2-4x speedup
NUM_THREADS_PER_WORKER = 4  # CPU threads per worker

# Processing configuration
SAMPLE_SIZE = 100  # Set to None for full catalog

# Get cluster info
try:
    sc = spark.sparkContext
    num_executors = int(sc._conf.get("spark.executor.instances", str(EXPECTED_WORKERS)))
    executor_cores = int(sc._conf.get("spark.executor.cores", "4"))
except:
    num_executors = EXPECTED_WORKERS  # Use preset default
    executor_cores = 4

total_cores = num_executors * executor_cores

print(f"✅ Configuration loaded")
print(f"   Products Table: {PRODUCTS_TABLE}")
print(f"   Output Table: {OUTPUT_TABLE}")
print(f"\n   🎯 CLUSTER PRESET: {CLUSTER_PRESET.upper()}")
print(f"   Expected Workers: {EXPECTED_WORKERS}")
print(f"   Actual Workers: {num_executors}")
print(f"   Cores per Worker: {executor_cores}")
print(f"   Total CPU Cores: {total_cores}")
print(f"   Partitions: {NUM_PARTITIONS}")
print(f"\n   🤖 MODEL CONFIGURATION:")
print(f"   Selected Model: {MODEL_CHOICE.upper()} - {selected_config['description']}")
print(f"   Model: {MODEL_NAME}")
print(f"   Quantization: {'INT8' if USE_QUANTIZATION else 'FP32'}")
print(f"   Batch Size per Worker: {BATCH_SIZE_PER_WORKER}")
print(f"   CPU Threads per Worker: {NUM_THREADS_PER_WORKER}")
print(f"\n   💡 EXPECTED PERFORMANCE:")
if preset_config["throughput_min"]:
    print(f"   Throughput: ~{preset_config['throughput_min']}-{preset_config['throughput_max']} products/minute")
    print(f"   Full catalog (44K): {preset_config['time_hours']}")
else:
    products_per_min_low = num_executors * 10
    products_per_min_high = num_executors * 15
    print(f"   Throughput: ~{products_per_min_low}-{products_per_min_high} products/minute")
    print(f"   Full catalog (44K): ~{44424 / products_per_min_high / 60:.1f}-{44424 / products_per_min_low / 60:.1f} hours")

# Recommended VM types by preset
VM_RECOMMENDATIONS = {
    "test": "Standard_D4s_v5 (Azure) | m6i.xlarge (AWS) | n2-standard-4 (GCP)",
    "balanced": "Standard_D4s_v5 (Azure) | m6i.xlarge (AWS) | n2-standard-4 (GCP)",
    "fast": "Standard_D4s_v5 or D8s_v5 (Azure) | m6i.xlarge or c6i.2xlarge (AWS) | n2-standard-4 (GCP)",
    "max_speed": "Standard_D4s_v5 (Azure) | m6i.xlarge (AWS) | n2-standard-4 (GCP)",
    "custom": "See 64_WORKER_SCALING_GUIDE.md for VM recommendations"
}

print(f"\n   💻 RECOMMENDED VMs:")
print(f"   {VM_RECOMMENDATIONS[CLUSTER_PRESET]}")
print(f"\n   💰 ESTIMATED COST (with spot/preemptible):")
if CLUSTER_PRESET == "max_speed":
    print(f"   44K products: $2-4 (45-70 minutes)")
elif CLUSTER_PRESET == "fast":
    print(f"   44K products: $2-4 (1.5-2.5 hours)")
elif CLUSTER_PRESET == "balanced":
    print(f"   44K products: $2-4 (3-4.5 hours)")
else:
    cost_per_worker_hour = 0.06  # Average spot price
    hours = 44424 / ((preset_config["throughput_min"] or 80) * 60)
    cost = num_executors * hours * cost_per_worker_hour
    print(f"   44K products: ${cost:.2f} ({hours:.1f} hours)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔧 CPU-Optimized Model Loading

# COMMAND ----------

# DBTITLE 1,Model Loading Function (Per Worker)
def load_model_cpu_optimized(model_choice: str, use_quantization: bool = True):
    """
    Load model optimized for CPU inference
    This function will be called on each worker
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor, BitsAndBytesConfig
    
    # Set CPU threads for optimal performance
    torch.set_num_threads(NUM_THREADS_PER_WORKER)
    
    model_name = MODEL_CONFIGS[model_choice]["name"]
    model_revision = MODEL_CONFIGS[model_choice]["revision"]
    
    logger.info(f"Loading {model_choice} on CPU worker...")
    
    if model_choice == "moondream":
        # Moondream2 - optimized for CPU
        if use_quantization:
            # Load with dynamic quantization for faster CPU inference
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                revision=model_revision,
                trust_remote_code=True,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
            ).eval()
            
            # Apply dynamic quantization
            model = torch.quantization.quantize_dynamic(
                model,
                {torch.nn.Linear},
                dtype=torch.qint8
            )
            logger.info("   ✅ INT8 quantization applied")
        else:
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                revision=model_revision,
                trust_remote_code=True,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
            ).eval()
        
        processor = None
        
    elif model_choice == "smolvlm":
        # SmolVLM on CPU
        processor = AutoProcessor.from_pretrained(
            model_name,
            trust_remote_code=True
        )
        
        if use_quantization:
            model = AutoModelForVision2Seq.from_pretrained(
                model_name,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
                trust_remote_code=True,
            ).eval()
            
            # Dynamic quantization
            model = torch.quantization.quantize_dynamic(
                model,
                {torch.nn.Linear},
                dtype=torch.qint8
            )
            logger.info("   ✅ INT8 quantization applied")
        else:
            model = AutoModelForVision2Seq.from_pretrained(
                model_name,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
                trust_remote_code=True,
            ).eval()
    
    logger.info(f"   ✅ Model loaded on worker")
    return model, processor

print("✅ Model loading function defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💬 Unified Prompt (Same as GPU Version)

# COMMAND ----------

# DBTITLE 1,Comprehensive Single Prompt
def get_unified_prompt() -> str:
    """Single comprehensive prompt for all attributes"""
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

Example for athletic shoes:
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

UNIFIED_PROMPT = get_unified_prompt()
print("✅ Unified prompt created")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚀 Distributed Processing Functions

# COMMAND ----------

# DBTITLE 1,Parse JSON Response
def parse_json_response(text: str) -> Dict:
    """Parse JSON from model response"""
    try:
        text = text.strip()
        
        # Remove markdown code blocks
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
            return {"error": "No JSON found", "raw_response": text[:200]}
            
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw_response": text[:200]}
    except Exception as e:
        return {"error": str(e), "raw_response": text[:200]}

# COMMAND ----------

# DBTITLE 1,Process Batch on CPU
def process_batch_cpu(images: List[Image.Image], model, processor, model_choice: str) -> List[Dict]:
    """Process a batch of images on CPU"""
    import torch
    
    results = []
    prompt = UNIFIED_PROMPT
    
    try:
        if model_choice == "moondream":
            # Moondream2 - process sequentially (it's fast enough)
            with torch.no_grad():
                for image in images:
                    try:
                        enc_image = model.encode_image(image)
                        response = model.answer_question(enc_image, prompt, model.tokenizer)
                        result = parse_json_response(response)
                        results.append(result)
                    except Exception as e:
                        results.append({"error": str(e), "raw_response": ""})
        
        elif model_choice == "smolvlm":
            # SmolVLM - can batch on CPU
            with torch.no_grad():
                messages_list = [[{
                    "role": "user",
                    "content": [{"type": "image"}, {"type": "text", "text": prompt}]
                }] for _ in images]
                
                prompts = [processor.apply_chat_template(msgs, add_generation_prompt=True) 
                          for msgs in messages_list]
                
                inputs = processor(
                    text=prompts,
                    images=images,
                    return_tensors="pt",
                    padding=True
                )
                
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=300,
                    temperature=0.1,
                    do_sample=False,
                    pad_token_id=processor.tokenizer.pad_token_id
                )
                
                generated_texts = processor.batch_decode(generated_ids, skip_special_tokens=True)
                
                for text in generated_texts:
                    result = parse_json_response(text)
                    results.append(result)
    
    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        results = [{"error": str(e), "raw_response": ""} for _ in images]
    
    return results

# COMMAND ----------

# DBTITLE 1,Worker Processing Function (Distributed)
def process_partition_cpu(partition_data):
    """
    Process a partition of images on a single worker
    This is the main distributed processing function
    """
    import torch
    from PIL import Image
    import io
    import base64
    import time
    
    # Load model once per partition (per worker)
    logger.info(f"Worker starting - loading model...")
    start_load = time.time()
    
    model, processor = load_model_cpu_optimized(MODEL_CHOICE, USE_QUANTIZATION)
    
    load_time = time.time() - start_load
    logger.info(f"Worker: Model loaded in {load_time:.1f}s")
    
    # Process images in small batches
    batch_size = BATCH_SIZE_PER_WORKER
    batch_images = []
    batch_rows = []
    results = []
    
    processed_count = 0
    start_time = time.time()
    
    for row in partition_data:
        try:
            # Decode image
            if row.image_base64 is None:
                results.append({
                    **row.asDict(),
                    "extraction_json": json.dumps({
                        "extraction_success": False,
                        "error": "No image data"
                    })
                })
                continue
            
            image_bytes = base64.b64decode(row.image_base64)
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            
            # Resize for efficiency
            max_size = 768
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = tuple(int(dim * ratio) for dim in image.size)
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            batch_images.append(image)
            batch_rows.append(row)
            
            # Process batch when full
            if len(batch_images) >= batch_size:
                batch_results = process_batch_cpu(batch_images, model, processor, MODEL_CHOICE)
                
                for batch_row, batch_result in zip(batch_rows, batch_results):
                    if "error" not in batch_result:
                        batch_result["extraction_success"] = True
                        batch_result["error"] = None
                    else:
                        batch_result["extraction_success"] = False
                    
                    results.append({
                        **batch_row.asDict(),
                        "extraction_json": json.dumps(batch_result)
                    })
                
                processed_count += len(batch_images)
                batch_images = []
                batch_rows = []
        
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            results.append({
                **row.asDict(),
                "extraction_json": json.dumps({
                    "extraction_success": False,
                    "error": str(e)
                })
            })
    
    # Process remaining images
    if batch_images:
        batch_results = process_batch_cpu(batch_images, model, processor, MODEL_CHOICE)
        
        for batch_row, batch_result in zip(batch_rows, batch_results):
            if "error" not in batch_result:
                batch_result["extraction_success"] = True
                batch_result["error"] = None
            else:
                batch_result["extraction_success"] = False
            
            results.append({
                **batch_row.asDict(),
                "extraction_json": json.dumps(batch_result)
            })
        
        processed_count += len(batch_images)
    
    elapsed = time.time() - start_time
    logger.info(f"Worker: Processed {processed_count} images in {elapsed:.1f}s ({processed_count/elapsed:.1f} img/s)")
    
    return iter(results)

print("✅ Distributed processing functions defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Extract Attributes - Distributed

# COMMAND ----------

# DBTITLE 1,Load Products
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

# Repartition for optimal CPU distribution
products_with_images = products_with_images.repartition(NUM_PARTITIONS)
print(f"   Repartitioned into {NUM_PARTITIONS} partitions")
print(f"   Each partition: ~{count // NUM_PARTITIONS} products")

# COMMAND ----------

# DBTITLE 1,Run Distributed Extraction on CPU
print("🚀 Starting distributed CPU extraction...")
print(f"   Model: {MODEL_CHOICE.upper()} ({'Quantized INT8' if USE_QUANTIZATION else 'FP32'})")
print(f"   Batch size per worker: {BATCH_SIZE_PER_WORKER}")
print(f"   Estimated workers: {num_executors}")
print(f"   Total products: {count:,}")
print("-" * 80)

start_time = time.time()

# Define output schema (matches input + extraction_json)
output_schema = products_with_images.schema.add(
    StructField("extraction_json", StringType(), True)
)

# Process using mapPartitions for distributed execution
products_with_extractions = products_with_images.rdd.mapPartitions(
    process_partition_cpu
).toDF(output_schema)

# Parse JSON results
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

products_with_attrs = products_with_extractions.withColumn(
    "extraction_result",
    F.from_json(F.col("extraction_json"), extraction_schema)
).select(
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

# Trigger execution and cache
products_with_attrs.cache()
final_count = products_with_attrs.count()

elapsed_time = time.time() - start_time
products_per_minute = (final_count / elapsed_time) * 60

print("\n" + "=" * 80)
print("✅ DISTRIBUTED CPU EXTRACTION COMPLETE")
print("=" * 80)
print(f"   Total products: {final_count:,}")
print(f"   Processing time: {elapsed_time / 60:.1f} minutes ({elapsed_time / 3600:.2f} hours)")
print(f"   Throughput: {products_per_minute:.1f} products/minute")
print(f"   Average: {elapsed_time / final_count:.2f}s per product")
print(f"   Workers: ~{num_executors}")
print(f"   Per-worker throughput: ~{products_per_minute / num_executors:.1f} products/min")
print("=" * 80)

# Estimate full catalog
if final_count > 0 and final_count < 44000:
    full_time_hours = (44424 / products_per_minute) / 60
    print(f"\n💡 Estimated time for full catalog (44K):")
    print(f"   ~{full_time_hours:.1f} hours at current throughput")
    print(f"   To reduce to 2 hours, scale to ~{int(num_executors * full_time_hours / 2)} workers")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📈 Quality Analysis

# COMMAND ----------

# DBTITLE 1,Analyze Results
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
    print(f"\n❌ Failed: {final_count - success_count}")
    failed.select("product_id", "product_display_name", "extraction_errors").show(5, truncate=False)

# Distributions
print("\n📊 Material Distribution:")
products_with_attrs.groupBy("material").count().orderBy(F.desc("count")).show(15)

print("\n📊 Pattern Distribution:")
products_with_attrs.groupBy("pattern").count().orderBy(F.desc("count")).show(15)

print("\n📊 Formality Distribution:")
products_with_attrs.groupBy("formality").count().orderBy(F.desc("count")).show(10)

# COMMAND ----------

# DBTITLE 1,Sample Results
print("=" * 80)
print("SAMPLE EXTRACTED ATTRIBUTES")
print("=" * 80)

samples = products_with_attrs.filter(
    F.col("extraction_success") == True
).select(
    "product_display_name",
    "article_type",
    "material",
    "pattern",
    "formality",
    "style_keywords"
).limit(15)

samples.show(15, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💾 Save Results

# COMMAND ----------

# DBTITLE 1,Save to Unity Catalog
print(f"💾 Saving to {OUTPUT_TABLE}")

products_with_attrs_final = products_with_attrs.withColumns({
    "extraction_timestamp": F.current_timestamp(),
    "model_name": F.lit(MODEL_NAME),
    "model_choice": F.lit(MODEL_CHOICE),
    "processing_type": F.lit("distributed_cpu"),
    "quantized": F.lit(USE_QUANTIZATION)
})

products_with_attrs_final.write.mode("overwrite").saveAsTable(OUTPUT_TABLE)

print(f"✅ Saved {final_count:,} products")
print(f"   Table: {OUTPUT_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Enriched Descriptions

# COMMAND ----------

# DBTITLE 1,Generate Rich Descriptions
enriched = products_with_attrs_final.withColumn(
    "rich_description",
    F.concat_ws(" ",
        F.col("product_display_name"),
        F.col("article_type"),
        F.col("base_color"),
        F.col("gender"),
        F.col("material"),
        F.col("pattern"),
        F.col("formality"),
        F.array_join(F.col("style_keywords"), " "),
        F.array_join(F.col("visual_details"), " "),
        F.when(F.col("collar_type") != "not applicable", F.col("collar_type")).otherwise(""),
        F.when(F.col("sleeve_length") != "not applicable", F.col("sleeve_length")).otherwise(""),
        F.col("season"),
        F.col("usage")
    )
)

ENRICHED_TABLE = f"{CATALOG}.{SCHEMA}.products_enriched_descriptions_cpu"
enriched.write.mode("overwrite").saveAsTable(ENRICHED_TABLE)

print(f"✅ Saved enriched descriptions to {ENRICHED_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Performance Summary & Scaling Guide

# COMMAND ----------

# DBTITLE 1,Scaling Recommendations
print("=" * 80)
print("CPU CLUSTER SCALING GUIDE")
print("=" * 80)

current_throughput = products_per_minute
current_workers = num_executors

print(f"\n📊 Current Performance:")
print(f"   Workers: {current_workers}")
print(f"   Throughput: {current_throughput:.1f} products/minute")
print(f"   Per-worker: {current_throughput / current_workers:.1f} products/min")

print(f"\n🎯 Scaling Recommendations for 44K Catalog:")

target_times = [1.5, 2, 3, 4, 6]
for target_hours in target_times:
    required_throughput = 44424 / (target_hours * 60)
    required_workers = int(required_throughput / (current_throughput / current_workers))
    cost_per_worker_hour = 0.15  # Estimate
    total_cost = required_workers * target_hours * cost_per_worker_hour
    
    print(f"\n   Target: {target_hours} hours")
    print(f"      Required throughput: {required_throughput:.0f} products/min")
    print(f"      Required workers: {required_workers}")
    print(f"      Estimated cost: ${total_cost:.2f}")

print(f"\n💡 Recommendations:")
print(f"   • For speed: 32-64 workers (~1.5-2 hours, $7-15)")
print(f"   • For balance: 16-24 workers (~3-4 hours, $7-12)")
print(f"   • For cost: 8-12 workers (~6-8 hours, $7-10)")
print(f"\n   • Enable auto-scaling for efficiency")
print(f"   • Use spot instances to reduce cost by 60-80%")
print("=" * 80)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚀 Next Steps
# MAGIC
# MAGIC ### 1. Validate Results (Current)
# MAGIC - ✅ Review quality metrics above
# MAGIC - ✅ Check sample outputs
# MAGIC - ✅ Verify throughput meets needs
# MAGIC
# MAGIC ### 2. Change Cluster Preset
# MAGIC ```python
# MAGIC # In Configuration cell, uncomment ONE preset:
# MAGIC
# MAGIC # For 64 workers (45-70 minutes, $2-4):
# MAGIC CLUSTER_PRESET = "max_speed"
# MAGIC
# MAGIC # For 32 workers (1.5-2.5 hours, $2-4):
# MAGIC CLUSTER_PRESET = "fast"
# MAGIC
# MAGIC # For 16 workers (3-4.5 hours, $2-4):
# MAGIC CLUSTER_PRESET = "balanced"
# MAGIC ```
# MAGIC
# MAGIC ### 3. Configure Databricks Cluster
# MAGIC ```yaml
# MAGIC # For 64 workers on Azure:
# MAGIC cluster_name: "cpu-extraction-64"
# MAGIC node_type_id: "Standard_D4s_v5"  # 4 cores, 16GB RAM
# MAGIC num_workers: 64
# MAGIC autoscale:
# MAGIC   min_workers: 32
# MAGIC   max_workers: 64
# MAGIC azure_attributes:
# MAGIC   availability: SPOT_WITH_FALLBACK_AZURE
# MAGIC   first_on_demand: 1
# MAGIC   spot_bid_max_price: -1
# MAGIC
# MAGIC # For AWS, use: m6i.xlarge
# MAGIC # For GCP, use: n2-standard-4
# MAGIC ```
# MAGIC See **64_WORKER_SCALING_GUIDE.md** for detailed VM recommendations!
# MAGIC
# MAGIC ### 4. Scale to Full Catalog
# MAGIC ```python
# MAGIC SAMPLE_SIZE = None  # Process all 44K
# MAGIC CLUSTER_PRESET = "max_speed"  # Use 64 workers
# MAGIC ```
# MAGIC
# MAGIC ### 5. Cost Optimization
# MAGIC - ✅ Use spot/preemptible instances (60-80% cheaper)
# MAGIC - ✅ Enable auto-scaling (scales down after processing)
# MAGIC - ✅ Use cheaper instance types (see scaling guide)
# MAGIC - ✅ Run during off-peak hours
# MAGIC
# MAGIC ### 6. Performance Tips
# MAGIC - More partitions = better distribution (4x workers recommended)
# MAGIC - Monitor Spark UI for stragglers
# MAGIC - Quantization is essential (2-4x speedup)
# MAGIC - Watch for memory pressure (reduce batch size if needed)
