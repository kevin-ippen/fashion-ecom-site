# Databricks notebook source
# MAGIC %md
# MAGIC # DeepFashion2 CLIP Embedding Generation (GPU Optimized)
# MAGIC
# MAGIC This notebook generates CLIP embeddings for DeepFashion2 items using single-node GPU optimization.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC * DeepFashion2 data prepared in `/Volumes/main/fashion_demo/complete_the_look/`
# MAGIC * Metadata CSV files with item information
# MAGIC * GPU cluster (A100 or similar recommended)
# MAGIC
# MAGIC **Pipeline:**
# MAGIC 1. Load metadata from complete_the_look volume
# MAGIC 2. Generate CLIP embeddings with GPU optimization
# MAGIC 3. Save embeddings to Delta table
# MAGIC
# MAGIC **GPU Optimizations:**
# MAGIC * Mixed precision (BF16/FP16)
# MAGIC * Large batch sizes (128-256)
# MAGIC * Efficient data loading with prefetching
# MAGIC * Pinned memory for fast GPU transfers
# MAGIC * Model compilation (torch.compile)
# MAGIC
# MAGIC **Output:**
# MAGIC * `main.fashion_demo.df2_items` - Items with CLIP embeddings (768-dim vectors)
# MAGIC
# MAGIC **Note:** Data preparation (download, extraction, annotation parsing) is handled by the `complementarity_optimized` notebook.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Configuration & Setup

# COMMAND ----------

# DBTITLE 1,Install Required Libraries
# MAGIC %pip install torch torchvision transformers pillow ftfy regex tqdm open-clip-torch
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Imports
import json
import torch
import numpy as np
import pandas as pd
from pathlib import Path
from PIL import Image
from io import BytesIO
import base64
from typing import List, Dict, Tuple
from itertools import combinations

from pyspark.sql import functions as F
from pyspark.sql.types import *
from pyspark.sql.window import Window

# CLIP for embeddings
import open_clip

# For distributed processing
from pyspark.sql.functions import pandas_udf, PandasUDFType

print("✓ Imports successful")

# COMMAND ----------

# DBTITLE 1,Configuration
# Unity Catalog paths
UC_CATALOG = "main"
UC_SCHEMA = "fashion_demo"
UC_VOLUME = "complete_the_look"

# Full paths
VOLUME_PATH = f"/Volumes/{UC_CATALOG}/{UC_SCHEMA}/{UC_VOLUME}"
TABLE_PREFIX = f"{UC_CATALOG}.{UC_SCHEMA}"

# DeepFashion2 paths - Reading from complete_the_look volume
# Data prepared by complementarity_optimized notebook
DF2_BASE_PATH = f"{VOLUME_PATH}/deepfashion2/DeepFashion2"
DF2_IMAGES_PATH = f"{DF2_BASE_PATH}/deepfashion2_original_images"
DF2_METADATA_PATH = f"{DF2_BASE_PATH}/img_info_dataframes"

# CLIP Model configuration
CLIP_MODEL = "ViT-L-14"  # or "ViT-B-32" for faster processing
CLIP_PRETRAINED = "openai"
EMBEDDING_DIM = 768  # for ViT-L-14 (512 for ViT-B-32)

# GPU Optimization settings
BATCH_SIZE = 128  # Large batch for GPU (increase to 256 if memory allows)
NUM_WORKERS = 8  # DataLoader workers for CPU preprocessing
PREFETCH_FACTOR = 4  # Batches to prefetch per worker
PIN_MEMORY = True  # Pin memory for faster GPU transfer
USE_AMP = True  # Automatic Mixed Precision (BF16 on A100)
COMPILE_MODEL = True  # Use torch.compile for faster inference

# Processing configuration
CHUNK_SIZE = 50000  # Process images in chunks to manage memory

# Category mapping (DeepFashion2 uses numeric category IDs)
CATEGORY_NAMES = {
    1: "short_sleeve_top",
    2: "long_sleeve_top",
    3: "short_sleeve_outwear",
    4: "long_sleeve_outwear",
    5: "vest",
    6: "sling",
    7: "shorts",
    8: "trousers",
    9: "skirt",
    10: "short_sleeve_dress",
    11: "long_sleeve_dress",
    12: "vest_dress",
    13: "sling_dress"
}

print("📁 Configuration:")
print(f"   Volume: {VOLUME_PATH}")
print(f"   Tables: {TABLE_PREFIX}")
print(f"   Images: {DF2_IMAGES_PATH}")
print(f"   Metadata: {DF2_METADATA_PATH}")
print("")
print("⚡ GPU Settings:")
print(f"   Model: {CLIP_MODEL}")
print(f"   Batch size: {BATCH_SIZE}")
print(f"   Mixed precision: {USE_AMP}")
print(f"   Workers: {NUM_WORKERS}")
print(f"   Compile model: {COMPILE_MODEL}")

# COMMAND ----------

# DBTITLE 1,Create Unity Catalog Schema and Volume
# Create schema if it doesn't exist
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {UC_CATALOG}.{UC_SCHEMA}")

# Create volume if it doesn't exist
spark.sql(f"""
CREATE VOLUME IF NOT EXISTS {UC_CATALOG}.{UC_SCHEMA}.{UC_VOLUME}
""")

print(f"✓ Schema and volume ready: {UC_CATALOG}.{UC_SCHEMA}.{UC_VOLUME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parse DeepFashion2 Annotations

# COMMAND ----------

# DBTITLE 1,Define Annotation Parser
def parse_deepfashion2_annotation(json_content: str, image_name: str) -> List[Dict]:
    """
    Parse a single DeepFashion2 annotation JSON file.
    
    Returns list of items with their metadata.
    """
    try:
        data = json.loads(json_content)
    except:
        return []
    
    items = []
    for item_id, item_data in data.items():
        if item_id == "source":  # Skip the source field
            continue
            
        try:
            items.append({
                "image_name": image_name,
                "item_id": int(item_id),
                "category_id": item_data.get("category_id"),
                "category_name": CATEGORY_NAMES.get(item_data.get("category_id"), "unknown"),
                "bbox": item_data.get("bounding_box", []),
                "style": item_data.get("style", 0),
                "scale": item_data.get("scale", 0.0),
                "occlusion": item_data.get("occlusion", 0.0),
                "zoom_in": item_data.get("zoom_in", 0.0),
                "viewpoint": item_data.get("viewpoint", 0),
                "pair_id": item_data.get("pair_id"),
                # Store segmentation as JSON string (it's large)
                "has_segmentation": "segmentation" in item_data,
                "num_landmarks": len(item_data.get("landmarks", []))
            })
        except Exception as e:
            print(f"Warning: Error parsing item {item_id} in {image_name}: {e}")
            continue
    
    return items

# Test on a sample
sample_json = """
{
    "source": "user",
    "1": {
        "category_id": 1,
        "style": 1,
        "bounding_box": [10, 20, 100, 200],
        "scale": 0.5,
        "occlusion": 0.0,
        "zoom_in": 0.0,
        "viewpoint": 1
    }
}
"""
test_result = parse_deepfashion2_annotation(sample_json, "test.jpg")
print(f"✓ Parser test successful: {test_result}")

# COMMAND ----------

# DBTITLE 1,Load All Annotations
import pandas as pd

print("📂 Loading DeepFashion2 metadata from CSV files...")
print("")

# Load train CSV using pandas (files are on driver node)
train_csv_path = f"{DF2_METADATA_PATH}/train.csv"
print(f"Loading training data from: {train_csv_path}")
train_pdf = pd.read_csv(train_csv_path)
train_pdf['split'] = 'train'
print(f"   ✓ Loaded {len(train_pdf):,} training items")

# Load validation CSV
val_csv_path = f"{DF2_METADATA_PATH}/validation.csv"
print(f"Loading validation data from: {val_csv_path}")
val_pdf = pd.read_csv(val_csv_path)
val_pdf['split'] = 'validation'
print(f"   ✓ Loaded {len(val_pdf):,} validation items")

# Combine
all_items_pdf = pd.concat([train_pdf, val_pdf], ignore_index=True)
print("")
print(f"📊 Total items: {len(all_items_pdf):,}")
print("")

# Convert to Spark DataFrame
all_items = spark.createDataFrame(all_items_pdf)

print("📋 Sample of data:")
display(all_items.limit(5))

print("")
print("📝 Schema:")
all_items.printSchema()

# COMMAND ----------

# DBTITLE 1,Exploratory Analysis
# Extract image name from path
all_items = all_items.withColumn(
    "image_name",
    F.regexp_extract(F.col("path"), r"([^/]+\.jpg)$", 1)
)

# Category distribution
print("📊 Category Distribution:")
category_dist = all_items.groupBy("category_name").count().orderBy(F.desc("count"))
display(category_dist)

# Items per image distribution
print("\n📊 Items per Image:")
items_per_image = all_items.groupBy("image_name", "split").count().withColumnRenamed("count", "num_items")
display(items_per_image.groupBy("num_items").count().orderBy("num_items"))

# Filter to outfits with 2+ items (these are the ones we care about for complementarity)
outfits = items_per_image.filter(F.col("num_items") >= 2)
print(f"\n✓ Found {outfits.count():,} images with 2+ items (outfit compositions)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Generate CLIP Embeddings

# COMMAND ----------

# DBTITLE 1,Setup CLIP Model for Distributed Processing
# This will be broadcast to workers
def get_clip_model():
    """Initialize CLIP model (called on each worker)"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(
        CLIP_MODEL, 
        pretrained=CLIP_PRETRAINED,
        device=device
    )
    model.eval()
    return model, preprocess, device

print("✓ CLIP model setup function defined")

# COMMAND ----------

# DBTITLE 1,Define Embedding Generation Function
def crop_and_embed_item(image_bytes: bytes, bbox: List[float]) -> np.ndarray:
    """
    Crop item from image using bbox and generate CLIP embedding.
    
    Args:
        image_bytes: Raw image bytes
        bbox: [x1, y1, x2, y2] bounding box coordinates
    
    Returns:
        CLIP embedding as numpy array
    """
    try:
        # Load image
        img = Image.open(BytesIO(image_bytes)).convert('RGB')
        
        # Crop to bounding box
        x1, y1, x2, y2 = bbox
        cropped = img.crop((x1, y1, x2, y2))
        
        # Ensure cropped image is valid
        if cropped.size[0] < 10 or cropped.size[1] < 10:
            # Too small, use full image
            cropped = img
        
        # Get CLIP model (initialized per worker)
        if not hasattr(crop_and_embed_item, 'model'):
            crop_and_embed_item.model, crop_and_embed_item.preprocess, crop_and_embed_item.device = get_clip_model()
        
        model = crop_and_embed_item.model
        preprocess = crop_and_embed_item.preprocess
        device = crop_and_embed_item.device
        
        # Preprocess and embed
        image_tensor = preprocess(cropped).unsqueeze(0).to(device)
        
        with torch.no_grad():
            embedding = model.encode_image(image_tensor)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)  # Normalize
        
        return embedding.cpu().numpy().flatten()
    
    except Exception as e:
        print(f"Error embedding item: {e}")
        # Return zero embedding on error
        return np.zeros(EMBEDDING_DIM, dtype=np.float32)

print("✓ Embedding function defined")

# COMMAND ----------

# DBTITLE 1,Create Pandas UDF for Distributed Embedding
print("📝 Preparing data for embedding generation...")
print("")

# Parse bbox from string to array
import ast

@F.udf(ArrayType(FloatType()))
def parse_bbox(bbox_str):
    """Parse bbox string '[x1, y1, x2, y2]' to array"""
    try:
        bbox = ast.literal_eval(bbox_str)
        return [float(x) for x in bbox]
    except:
        return [0.0, 0.0, 0.0, 0.0]

# Prepare items with parsed bbox and correct image paths
items_prepared = all_items.withColumn(
    "bbox_parsed", 
    parse_bbox(F.col("b_box"))
).withColumn(
    "image_path_local",
    # Construct path to /tmp images
    F.concat(
        F.lit(f"{DF2_IMAGES_PATH}/"),
        F.col("split"),
        F.lit("/image/"),
        F.col("image_name")
    )
).withColumn(
    "item_uid",
    F.concat(F.col("image_name"), F.lit("_"), F.monotonically_increasing_id().cast("string"))
)

print("✓ Data prepared")
print("")
print("📋 Sample:")
display(items_prepared.select("item_uid", "image_name", "category_name", "bbox_parsed", "image_path_local").limit(5))

print("")
print("📊 Total items ready for embedding: {items_prepared.count():,}")

# COMMAND ----------

# DBTITLE 1,Generate Embeddings for All Items
from torch.utils.data import Dataset, DataLoader
from torch.cuda.amp import autocast
from tqdm import tqdm
import time

print("⚡ GPU-Optimized CLIP Embedding Generation")
print("="*60)
print("")

# Check GPU availability
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"💻 Device: {device}")

if torch.cuda.is_available():
    print(f"   GPU: {torch.cuda.get_device_name(0)}")
    print(f"   Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    
    # A100/GPU optimizations
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    print("   ✓ GPU optimizations enabled")

print("")

# Initialize CLIP model
print("🧠 Loading CLIP model...")
model, _, preprocess = open_clip.create_model_and_transforms(
    CLIP_MODEL,
    pretrained=CLIP_PRETRAINED,
    device=device
)
model.eval()

# Compile model for faster inference (PyTorch 2.0+)
if COMPILE_MODEL and hasattr(torch, 'compile'):
    print("   Compiling model with torch.compile()...")
    model = torch.compile(model, mode='reduce-overhead')
    print("   ✓ Model compiled")

print(f"   ✓ {CLIP_MODEL} loaded on {device}")
print("")

# Custom Dataset for efficient image loading
class DeepFashion2Dataset(Dataset):
    """Optimized dataset for loading and cropping DeepFashion2 items"""
    
    def __init__(self, items_pdf, transform):
        self.items = items_pdf
        self.transform = transform
    
    def __len__(self):
        return len(self.items)
    
    def __getitem__(self, idx):
        row = self.items.iloc[idx]
        
        try:
            # Load image
            img = Image.open(row['image_path_local']).convert('RGB')
            
            # Crop to bounding box
            x1, y1, x2, y2 = row['bbox_parsed']
            cropped = img.crop((x1, y1, x2, y2))
            
            # Handle edge cases
            if cropped.size[0] < 10 or cropped.size[1] < 10:
                cropped = img
            
            # Transform
            image_tensor = self.transform(cropped)
            
            return image_tensor, row['item_uid'], True
            
        except Exception as e:
            # Return blank image on error
            blank = Image.new('RGB', (224, 224), color='gray')
            return self.transform(blank), row['item_uid'], False

print("📊 Processing configuration:")
print(f"   Total items: {items_prepared.count():,}")
print(f"   Batch size: {BATCH_SIZE}")
print(f"   Chunk size: {CHUNK_SIZE:,}")
print(f"   Workers: {NUM_WORKERS}")
print("")

# Convert to pandas for efficient processing
print("📝 Loading items to memory...")
items_pdf = items_prepared.toPandas()
print(f"   ✓ Loaded {len(items_pdf):,} items")
print("")

# Process in chunks
total_items = len(items_pdf)
num_chunks = (total_items + CHUNK_SIZE - 1) // CHUNK_SIZE

all_embeddings = []
all_item_uids = []
all_success_flags = []

print(f"🚀 Generating embeddings in {num_chunks} chunks...")
print("")

overall_start = time.time()

for chunk_idx in range(num_chunks):
    start_idx = chunk_idx * CHUNK_SIZE
    end_idx = min(start_idx + CHUNK_SIZE, total_items)
    
    chunk_pdf = items_pdf.iloc[start_idx:end_idx]
    
    print(f"📦 Chunk {chunk_idx + 1}/{num_chunks}: Items {start_idx:,} to {end_idx:,}")
    
    # Create dataset and dataloader
    dataset = DeepFashion2Dataset(chunk_pdf, preprocess)
    dataloader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        num_workers=NUM_WORKERS,
        pin_memory=PIN_MEMORY,
        prefetch_factor=PREFETCH_FACTOR,
        persistent_workers=True if NUM_WORKERS > 0 else False,
        shuffle=False
    )
    
    chunk_embeddings = []
    chunk_uids = []
    chunk_success = []
    
    chunk_start = time.time()
    
    with torch.no_grad():
        for batch_images, batch_uids, batch_success in tqdm(dataloader, desc=f"  Chunk {chunk_idx+1}"):
            batch_images = batch_images.to(device, non_blocking=True)
            
            # Use mixed precision if enabled
            if USE_AMP and device == "cuda":
                with autocast(dtype=torch.bfloat16):
                    features = model.encode_image(batch_images)
            else:
                features = model.encode_image(batch_images)
            
            # Normalize
            features = features / features.norm(dim=-1, keepdim=True)
            
            # Move to CPU
            chunk_embeddings.append(features.cpu().numpy())
            chunk_uids.extend(batch_uids)
            chunk_success.extend(batch_success.tolist())
    
    # Concatenate chunk results
    chunk_embeddings = np.vstack(chunk_embeddings)
    all_embeddings.append(chunk_embeddings)
    all_item_uids.extend(chunk_uids)
    all_success_flags.extend(chunk_success)
    
    chunk_time = time.time() - chunk_start
    items_per_sec = len(chunk_pdf) / chunk_time
    
    print(f"   ✓ Processed {len(chunk_pdf):,} items in {chunk_time:.1f}s ({items_per_sec:.1f} items/sec)")
    print("")
    
    # Clear GPU cache
    if device == "cuda":
        torch.cuda.empty_cache()

# Concatenate all chunks
print("🔗 Concatenating all embeddings...")
final_embeddings = np.vstack(all_embeddings)

total_time = time.time() - overall_start
overall_rate = total_items / total_time

print("")
print("✅ Embedding generation complete!")
print(f"   Total items: {len(final_embeddings):,}")
print(f"   Embedding shape: {final_embeddings.shape}")
print(f"   Total time: {total_time/60:.1f} minutes")
print(f"   Average speed: {overall_rate:.1f} items/sec")
print(f"   Success rate: {sum(all_success_flags)/len(all_success_flags)*100:.1f}%")
print("")

# Add embeddings to dataframe
items_pdf['clip_embedding'] = [emb.tolist() for emb in final_embeddings]
items_pdf['embedding_success'] = all_success_flags

# Convert to Spark DataFrame
items_embedded = spark.createDataFrame(items_pdf)
items_embedded = items_embedded.cache()

print("📋 Sample embeddings:")
display(items_embedded.select("item_uid", "category_name", "embedding_success", "clip_embedding").limit(5))

# COMMAND ----------

# DBTITLE 1,Save Items with Embeddings to Delta
items_table = f"{TABLE_PREFIX}.df2_items"

print(f"💾 Saving items with embeddings to Delta table...")
print(f"   Table: {items_table}")
print("")

# Show statistics before saving
print("📊 Embedding Statistics:")
successful_embeddings = items_embedded.filter(F.col("embedding_success") == True).count()
failed_embeddings = items_embedded.filter(F.col("embedding_success") == False).count()

print(f"   Successful: {successful_embeddings:,}")
print(f"   Failed: {failed_embeddings:,}")
print(f"   Success rate: {successful_embeddings/(successful_embeddings+failed_embeddings)*100:.2f}%")
print("")

# Category breakdown
print("📊 Category breakdown:")
category_counts = items_embedded.groupBy("category_name").count().orderBy(F.desc("count"))
display(category_counts)

print("")
print("💾 Writing to Delta table...")

# Write to Delta
items_embedded.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(items_table)

print(f"   ✓ Saved {items_embedded.count():,} items")
print("")

# Optimize table
print("🛠️ Optimizing Delta table...")
spark.sql(f"OPTIMIZE {items_table}")
print("   ✓ Table optimized")
print("")

print("✅ Embeddings saved successfully!")
print(f"   Table: {items_table}")
print("")
print("🚀 Ready for downstream processing (outfit compositions, complementarity analysis)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Progress Summary
# MAGIC
# MAGIC ### What's Complete:
# MAGIC
# MAGIC **1. Data Loading** ✓
# MAGIC * Downloaded DeepFashion2 from Kaggle (14.9 GB)
# MAGIC * Extracted 510,870 files to `/tmp/deepfashion2_extracted/DeepFashion2`
# MAGIC * Loaded 364,676 items from CSV metadata (312K train + 52K validation)
# MAGIC * Found 135,323 images with 2+ items (outfit compositions)
# MAGIC
# MAGIC **2. Data Preparation** ✓
# MAGIC * Parsed bounding boxes from string format
# MAGIC * Constructed image paths pointing to `/tmp` storage
# MAGIC * Created unique item UIDs
# MAGIC * Data ready in `items_prepared` DataFrame
# MAGIC
# MAGIC **3. CLIP Embeddings** ✓
# MAGIC * Generated 1,000 sample embeddings using ViT-L-14 model
# MAGIC * Embeddings are 768-dimensional vectors
# MAGIC * Normalized to unit length (L2 norm = 1.0)
# MAGIC * Data cached in `items_embedded` DataFrame
# MAGIC
# MAGIC ### Category Distribution:
# MAGIC * Short sleeve top: 84,201 items
# MAGIC * Trousers: 64,973 items  
# MAGIC * Long sleeve top: 42,030 items
# MAGIC * Shorts: 40,783 items
# MAGIC * Skirt: 37,357 items
# MAGIC * And 8 more categories...
# MAGIC
# MAGIC ### Next Steps:
# MAGIC
# MAGIC **To save embeddings to Delta table:**
# MAGIC ```python
# MAGIC # Run this manually (safety system blocks automated writes)
# MAGIC items_embedded.write.format("delta").mode("overwrite").saveAsTable("main.fashion_demo.df2_items")
# MAGIC ```
# MAGIC
# MAGIC **To process full dataset (364K items):**
# MAGIC 1. Copy images to DBFS or cloud storage (workers need access)
# MAGIC 2. Update `image_path_local` to point to accessible location
# MAGIC 3. Remove `.limit(1000)` in Cell 24
# MAGIC 4. Re-run embedding generation (will take 1-2 hours)
# MAGIC
# MAGIC **To continue with current 1K sample:**
# MAGIC * Proceed to Cell 27 to build outfit compositions
# MAGIC * Then Cell 29+ for complementarity analysis
# MAGIC * Vector search index creation (Cell 34+)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Build Outfit Compositions

# COMMAND ----------

# DBTITLE 1,Create Outfit-Level Table
print("👗 Building outfit compositions...")
print("")

# Group items by image to create outfits
outfits_df = spark.table(items_table).groupBy("image_name", "split").agg(
    F.collect_list(
        F.struct(
            "item_uid",
            "category_id",
            "category_name",
            "bbox_parsed",
            "clip_embedding",
            "scale",
            "occlusion",
            "viewpoint"
        )
    ).alias("items"),
    F.count("*").alias("num_items")
).filter(
    F.col("num_items") >= 2  # Only outfits with 2+ items
)

outfit_count = outfits_df.count()
print(f"✓ Created {outfit_count:,} outfit compositions")
print("")

# Save outfits table
outfits_table = f"{TABLE_PREFIX}.df2_outfits"

print(f"💾 Saving to {outfits_table}...")
outfits_df.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(outfits_table)

print(f"   ✓ Saved {outfit_count:,} outfits")
print("")

# Show sample
print("📋 Sample outfits:")
display(spark.table(outfits_table).limit(5))

print("")
print("✅ Outfit compositions ready!")
print(f"   Table: {outfits_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Extract Complementarity Patterns

# COMMAND ----------

# DBTITLE 1,Generate Item Pairs from Outfits
print("🔗 Generating item pairs from outfits...")

# Define UDF to create all pairs within an outfit
@F.udf(ArrayType(StructType([
    StructField("item_a_uid", StringType()),
    StructField("item_b_uid", StringType()),
    StructField("category_a", StringType()),
    StructField("category_b", StringType()),
    StructField("embedding_a", ArrayType(FloatType())),
    StructField("embedding_b", ArrayType(FloatType())),
    StructField("style_a", IntegerType()),
    StructField("style_b", IntegerType())
])))
def create_item_pairs(items):
    """Create all pairwise combinations from items in an outfit"""
    pairs = []
    items_list = list(items)
    
    for i in range(len(items_list)):
        for j in range(i + 1, len(items_list)):
            item_a = items_list[i]
            item_b = items_list[j]
            
            # Only create pairs from different categories
            if item_a.category_name != item_b.category_name:
                pairs.append({
                    "item_a_uid": item_a.item_uid,
                    "item_b_uid": item_b.item_uid,
                    "category_a": item_a.category_name,
                    "category_b": item_b.category_name,
                    "embedding_a": item_a.clip_embedding,
                    "embedding_b": item_b.clip_embedding,
                    "style_a": item_a.style,
                    "style_b": item_b.style
                })
    
    return pairs

# Generate pairs
pairs_df = spark.table(outfits_table).withColumn(
    "pairs",
    create_item_pairs(F.col("items"))
).select(
    F.col("image_name"),
    F.explode(F.col("pairs")).alias("pair")
).select(
    "image_name",
    "pair.*"
)

print(f"✓ Generated {pairs_df.count():,} item pairs from outfits")

# COMMAND ----------

# DBTITLE 1,Calculate Style Similarity Scores
print("📊 Calculating style similarity scores...")

# Define cosine similarity UDF
@F.udf(FloatType())
def cosine_similarity(vec_a, vec_b):
    """Calculate cosine similarity between two embeddings"""
    if vec_a is None or vec_b is None:
        return 0.0
    
    try:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        
        # Cosine similarity
        similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)
        return float(similarity)
    except:
        return 0.0

# Add style similarity
pairs_with_similarity = pairs_df.withColumn(
    "style_similarity",
    cosine_similarity(F.col("embedding_a"), F.col("embedding_b"))
).withColumn(
    "same_style_label",
    (F.col("style_a") == F.col("style_b")).cast("int")
)

print("✓ Style similarity calculated")
display(pairs_with_similarity.limit(10))

# COMMAND ----------

# DBTITLE 1,Aggregate Complementarity Scores
print("📈 Aggregating complementarity scores by category pairs...")

# Aggregate by category pairs
complementarity_by_category = pairs_with_similarity.groupBy(
    "category_a", 
    "category_b"
).agg(
    F.count("*").alias("cooccurrence_count"),
    F.avg("style_similarity").alias("avg_style_similarity"),
    F.stddev("style_similarity").alias("stddev_style_similarity"),
    F.min("style_similarity").alias("min_style_similarity"),
    F.max("style_similarity").alias("max_style_similarity"),
    F.avg("same_style_label").alias("same_style_rate")
)

# Calculate overall complementarity score
# High co-occurrence + moderate-to-high style similarity = good complementarity
complementarity_by_category = complementarity_by_category.withColumn(
    "complementarity_score",
    # Normalize cooccurrence (log scale) and combine with style similarity
    (F.log10(F.col("cooccurrence_count") + 1) * 0.5 + 
     F.col("avg_style_similarity") * 0.5)
).withColumn(
    "complementarity_score_normalized",
    # Normalize to 0-1 range
    (F.col("complementarity_score") - F.min("complementarity_score").over(Window.partitionBy())) /
    (F.max("complementarity_score").over(Window.partitionBy()) - 
     F.min("complementarity_score").over(Window.partitionBy()) + 1e-8)
)

# Save complementarity matrix
complementarity_table = f"{TABLE_PREFIX}.df2_complementarity"
complementarity_by_category.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(complementarity_table)

print(f"✓ Saved complementarity matrix to {complementarity_table}")

# Show top complementary pairs
print("\n🔥 Top Complementary Category Pairs:")
display(
    spark.table(complementarity_table)
    .orderBy(F.desc("complementarity_score_normalized"))
    .limit(20)
)

# COMMAND ----------

# DBTITLE 1,Save Individual Pair-Level Data (for ML training)
# Save the detailed pair-level data for training complementarity models
pairs_table = f"{TABLE_PREFIX}.df2_item_pairs"

# Keep a sample for training (optional: save all pairs, but it's large)
pairs_sample = pairs_with_similarity.sample(fraction=0.1, seed=42)  # 10% sample

pairs_sample.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(pairs_table)

print(f"✓ Saved {pairs_sample.count():,} item pairs to {pairs_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Create Vector Search Index

# COMMAND ----------

# DBTITLE 1,Create Vector Search Index for Items
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Create endpoint if it doesn't exist
endpoint_name = "fashion_complementarity_endpoint"

try:
    vsc.create_endpoint(name=endpoint_name)
    print(f"✓ Created endpoint: {endpoint_name}")
except Exception as e:
    print(f"ℹ️  Endpoint already exists or error: {e}")

# Create vector search index on items table
index_name = f"{TABLE_PREFIX}.df2_items_vector_idx"

try:
    index = vsc.create_delta_sync_index(
        endpoint_name=endpoint_name,
        index_name=index_name,
        source_table_name=items_table,
        pipeline_type="TRIGGERED",
        primary_key="item_uid",
        embedding_dimension=EMBEDDING_DIM,
        embedding_vector_column="clip_embedding"
    )
    print(f"✓ Created vector search index: {index_name}")
except Exception as e:
    print(f"ℹ️  Index already exists or error: {e}")

# COMMAND ----------

# DBTITLE 1,Test Vector Search
# Test similarity search
test_item = spark.table(items_table).filter(
    F.col("category_name") == "short_sleeve_dress"
).first()

print(f"🔍 Testing vector search with item: {test_item.item_uid}")
print(f"   Category: {test_item.category_name}")

# Search for similar items
results = vsc.get_index(endpoint_name, index_name).similarity_search(
    query_vector=test_item.clip_embedding,
    num_results=10
)

print("\n📊 Similar items found:")
for i, result in enumerate(results['result']['data_array'], 1):
    print(f"   {i}. {result[0]} (score: {result[1]:.4f})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Helper Functions for Downstream Use

# COMMAND ----------

# DBTITLE 1,Complete the Look Function
def get_complementary_items(
    anchor_category: str,
    num_recommendations: int = 5,
    min_cooccurrence: int = 10
) -> pd.DataFrame:
    """
    Get complementary categories for a given anchor category.
    
    Args:
        anchor_category: Category of the anchor item (e.g., "short_sleeve_dress")
        num_recommendations: Number of complementary categories to return
        min_cooccurrence: Minimum co-occurrence count threshold
    
    Returns:
        DataFrame with complementary categories and scores
    """
    query = f"""
    SELECT 
        category_b as complementary_category,
        cooccurrence_count,
        avg_style_similarity,
        complementarity_score_normalized,
        same_style_rate
    FROM {complementarity_table}
    WHERE category_a = '{anchor_category}'
        AND cooccurrence_count >= {min_cooccurrence}
    ORDER BY complementarity_score_normalized DESC
    LIMIT {num_recommendations}
    """
    
    return spark.sql(query).toPandas()

# Test the function
print("🧪 Testing complementarity lookup...")
test_category = "short_sleeve_dress"
recommendations = get_complementary_items(test_category)

print(f"\nTop complementary items for '{test_category}':")
print(recommendations)

# COMMAND ----------

# DBTITLE 1,Find Similar Items in Category
def find_items_in_category_similar_to(
    anchor_item_uid: str,
    target_category: str,
    num_results: int = 10
) -> List[Dict]:
    """
    Find items in a specific category that are stylistically similar to an anchor item.
    
    This is useful for "complete the look" - given a dress, find shoes that match its style.
    
    Args:
        anchor_item_uid: UID of the anchor item
        target_category: Category to search in (e.g., "shorts", "sling")
        num_results: Number of results to return
    
    Returns:
        List of similar items with scores
    """
    # Get anchor item embedding
    anchor = spark.table(items_table).filter(
        F.col("item_uid") == anchor_item_uid
    ).first()
    
    if not anchor:
        return []
    
    # Search vector index with category filter
    results = vsc.get_index(endpoint_name, index_name).similarity_search(
        query_vector=anchor.clip_embedding,
        filters={"category_name": target_category},
        num_results=num_results
    )
    
    return results['result']['data_array']

# Test
print("\n🧪 Testing category-filtered similarity search...")
test_anchor = spark.table(items_table).filter(
    F.col("category_name") == "long_sleeve_dress"
).first()

similar_shorts = find_items_in_category_similar_to(
    test_anchor.item_uid,
    target_category="shorts",
    num_results=5
)

print(f"\nItems in 'shorts' similar to dress '{test_anchor.item_uid}':")
for item in similar_shorts:
    print(f"  - {item[0]} (similarity: {item[1]:.4f})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Summary & Next Steps

# COMMAND ----------

# DBTITLE 1,Pipeline Summary
print("=" * 80)
print("🎉 DEEPFASHION2 PROCESSING COMPLETE!")
print("=" * 80)

# Count records in each table
items_count = spark.table(items_table).count()
outfits_count = spark.table(outfits_table).count()
pairs_count = spark.table(pairs_table).count()
comp_count = spark.table(complementarity_table).count()

print(f"""
📊 CREATED ASSETS:

Tables:
  ✓ {items_table}
    - {items_count:,} items with CLIP embeddings
    
  ✓ {outfits_table}
    - {outfits_count:,} outfit compositions
    
  ✓ {pairs_table}
    - {pairs_count:,} training pairs for complementarity model
    
  ✓ {complementarity_table}
    - {comp_count} category-level complementarity scores

Vector Search:
  ✓ {index_name}
    - {EMBEDDING_DIM}-dim embeddings
    - Searchable by item similarity

Volume:
  ✓ {VOLUME_PATH}
    - Ready for model artifacts
""")

print("""
📝 NEXT STEPS:

1. Train Complementarity Model
   - Use df2_item_pairs table for training data
   - Build binary classifier: do items complement each other?
   - Save model to MLflow

2. Map to Your Product Catalog
   - Generate CLIP embeddings for your products
   - Use vector search to find nearest DeepFashion2 items
   - Transfer complementarity scores to your catalog

3. Build Complete-the-Look API
   - Input: anchor product from your catalog
   - Lookup: complementary categories from df2_complementarity
   - Search: similar items in those categories from your catalog
   - Rank: using complementarity model + user preferences

4. Add Accessories
   - Supplement with shoe/bag datasets
   - Or scrape targeted social images for accessories
   - Extend complementarity matrix

5. A/B Test
   - Compare against baseline recommendations
   - Measure click-through, add-to-cart, conversion
""")

print("=" * 80)

# COMMAND ----------

# DBTITLE 1,Quick Validation Queries
print("🔍 Sample Queries for Validation:\n")

print("1. Most common outfit compositions:")
print("-" * 50)
spark.sql(f"""
SELECT 
    items[0].category_name as item1,
    items[1].category_name as item2,
    items[2].category_name as item3,
    COUNT(*) as count
FROM {outfits_table}
WHERE num_items = 3
GROUP BY item1, item2, item3
ORDER BY count DESC
LIMIT 10
""").show()

print("\n2. Category co-occurrence heatmap data:")
print("-" * 50)
spark.sql(f"""
SELECT 
    category_a,
    category_b,
    cooccurrence_count,
    ROUND(avg_style_similarity, 3) as avg_similarity,
    ROUND(complementarity_score_normalized, 3) as comp_score
FROM {complementarity_table}
WHERE cooccurrence_count > 100
ORDER BY complementarity_score_normalized DESC
LIMIT 20
""").show()

print("\n3. Items with highest style variance (interesting for diversity):")
print("-" * 50)
spark.sql(f"""
SELECT 
    category_a,
    category_b,
    stddev_style_similarity,
    cooccurrence_count
FROM {complementarity_table}
WHERE cooccurrence_count > 50
ORDER BY stddev_style_similarity DESC
LIMIT 10
""").show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Example Usage: Complete the Look
# MAGIC
# MAGIC ```python
# MAGIC # Example: User is viewing a dress, recommend complementary items
# MAGIC
# MAGIC anchor_item = "001234_dress"  # From your catalog
# MAGIC
# MAGIC # Step 1: Find DeepFashion2 item similar to anchor
# MAGIC similar_df2_items = vector_search(anchor_item_embedding)
# MAGIC df2_category = similar_df2_items[0].category_name
# MAGIC
# MAGIC # Step 2: Get complementary categories
# MAGIC complementary_cats = get_complementary_items(df2_category, num_recommendations=3)
# MAGIC # Returns: ["shorts", "vest", "sling"]
# MAGIC
# MAGIC # Step 3: For each category, find items from YOUR catalog
# MAGIC for cat in complementary_cats:
# MAGIC     # Search your catalog in this category
# MAGIC     candidates = your_catalog_search(
# MAGIC         category=cat,
# MAGIC         style_similar_to=anchor_item_embedding,
# MAGIC         num_results=5
# MAGIC     )
# MAGIC     
# MAGIC     # Rank by complementarity model
# MAGIC     scored_candidates = complementarity_model.predict(
# MAGIC         anchor_embedding=anchor_item_embedding,
# MAGIC         candidate_embeddings=candidates
# MAGIC     )
# MAGIC     
# MAGIC     # Personalize
# MAGIC     personalized = recommender_model.rerank(scored_candidates, user_id)
# MAGIC     
# MAGIC     recommendations[cat] = personalized.top(2)
# MAGIC
# MAGIC # Return: {
# MAGIC #   "shorts": [item_A, item_B],
# MAGIC #   "vest": [item_C, item_D],
# MAGIC #   "sling": [item_E, item_F]
# MAGIC # }
# MAGIC ```
