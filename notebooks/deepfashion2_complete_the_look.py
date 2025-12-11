# Databricks notebook source
# MAGIC %md
# MAGIC # DeepFashion2 → Complete the Look System
# MAGIC
# MAGIC This notebook processes DeepFashion2 dataset to build a fashion complementarity system.
# MAGIC
# MAGIC **Pipeline:**
# MAGIC 1. Load and parse DeepFashion2 annotations
# MAGIC 2. Generate CLIP embeddings for all clothing items
# MAGIC 3. Extract outfit compositions and co-occurrence patterns
# MAGIC 4. Build complementarity matrix
# MAGIC 5. Save to Unity Catalog for downstream use
# MAGIC
# MAGIC **Output Tables:**
# MAGIC - `main.fashion_demo.df2_items` - Individual items with embeddings
# MAGIC - `main.fashion_demo.df2_outfits` - Outfit compositions
# MAGIC - `main.fashion_demo.df2_complementarity` - Item pair complementarity scores
# MAGIC
# MAGIC **Output Volume:**
# MAGIC - `/Volumes/main/fashion_demo/complete_the_look/` - Model artifacts and intermediate data

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

# DeepFashion2 paths (adjust to where you've downloaded the data)
# Assuming data is in a DBFS location or cloud storage
DF2_BASE_PATH = "/mnt/deepfashion2"  # CHANGE THIS to your actual path
DF2_TRAIN_ANNOS = f"{DF2_BASE_PATH}/train/annos"
DF2_TRAIN_IMAGES = f"{DF2_BASE_PATH}/train/image"
DF2_VALIDATION_ANNOS = f"{DF2_BASE_PATH}/validation/annos"
DF2_VALIDATION_IMAGES = f"{DF2_BASE_PATH}/validation/image"

# Model configuration
CLIP_MODEL = "ViT-L-14"  # or "ViT-B-32" for faster processing
CLIP_PRETRAINED = "openai"
EMBEDDING_DIM = 768  # for ViT-L-14
BATCH_SIZE = 32

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

print(f"📁 Volume path: {VOLUME_PATH}")
print(f"📊 Tables prefix: {TABLE_PREFIX}")
print(f"🗂️  DeepFashion2 base: {DF2_BASE_PATH}")

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
def load_annotations_from_path(annos_path: str, images_path: str, split_name: str) -> pd.DataFrame:
    """
    Load all DeepFashion2 annotations from a directory.
    Returns pandas DataFrame with all items.
    """
    print(f"Loading annotations from {annos_path}...")
    
    # Use Spark to read all JSON files
    json_files = spark.read.text(annos_path + "/*.json")
    
    # Get corresponding image names
    json_files = json_files.withColumn(
        "image_name",
        F.regexp_replace(F.input_file_name(), ".*/", "")  # Extract filename
    ).withColumn(
        "image_name", 
        F.regexp_replace(F.col("image_name"), ".json", ".jpg")  # Change extension
    ).withColumn(
        "split", F.lit(split_name)
    )
    
    # Parse each annotation file
    @pandas_udf(ArrayType(StructType([
        StructField("image_name", StringType()),
        StructField("item_id", IntegerType()),
        StructField("category_id", IntegerType()),
        StructField("category_name", StringType()),
        StructField("bbox", ArrayType(FloatType())),
        StructField("style", IntegerType()),
        StructField("scale", FloatType()),
        StructField("occlusion", FloatType()),
        StructField("zoom_in", FloatType()),
        StructField("viewpoint", IntegerType()),
        StructField("pair_id", IntegerType()),
        StructField("has_segmentation", BooleanType()),
        StructField("num_landmarks", IntegerType())
    ])))
    def parse_json_udf(json_series: pd.Series, image_series: pd.Series) -> pd.Series:
        def parse_row(json_content, image_name):
            return parse_deepfashion2_annotation(json_content, image_name)
        return pd.Series([parse_row(j, i) for j, i in zip(json_series, image_series)])
    
    parsed = json_files.withColumn(
        "items",
        parse_json_udf(F.col("value"), F.col("image_name"))
    )
    
    # Explode items array into individual rows
    items_df = parsed.select(
        F.col("split"),
        F.explode(F.col("items")).alias("item")
    ).select(
        "split",
        "item.*"
    )
    
    # Add full image path
    items_df = items_df.withColumn(
        "image_path",
        F.concat(F.lit(images_path + "/"), F.col("image_name"))
    )
    
    return items_df

# Load training data
print("📂 Loading training annotations...")
train_items = load_annotations_from_path(DF2_TRAIN_ANNOS, DF2_TRAIN_IMAGES, "train")
print(f"✓ Loaded {train_items.count():,} items from training set")

# Optionally load validation data
print("📂 Loading validation annotations...")
val_items = load_annotations_from_path(DF2_VALIDATION_ANNOS, DF2_VALIDATION_IMAGES, "validation")
print(f"✓ Loaded {val_items.count():,} items from validation set")

# Combine
all_items = train_items.union(val_items)
print(f"📊 Total items: {all_items.count():,}")

# Show sample
display(all_items.limit(10))

# COMMAND ----------

# DBTITLE 1,Exploratory Analysis
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
# Define schema for embeddings
embedding_schema = ArrayType(FloatType())

@pandas_udf(embedding_schema)
def generate_embeddings_udf(image_paths: pd.Series, bboxes: pd.Series) -> pd.Series:
    """
    Pandas UDF to generate embeddings in parallel across cluster.
    """
    # Initialize model once per batch
    model, preprocess, device = get_clip_model()
    
    embeddings = []
    
    for img_path, bbox in zip(image_paths, bboxes):
        try:
            # Read image from DBFS/cloud storage
            with open(img_path, 'rb') as f:
                image_bytes = f.read()
            
            # Load and crop
            img = Image.open(BytesIO(image_bytes)).convert('RGB')
            x1, y1, x2, y2 = bbox
            cropped = img.crop((x1, y1, x2, y2))
            
            # Handle edge cases
            if cropped.size[0] < 10 or cropped.size[1] < 10:
                cropped = img
            
            # Embed
            image_tensor = preprocess(cropped).unsqueeze(0).to(device)
            with torch.no_grad():
                embedding = model.encode_image(image_tensor)
                embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            
            embeddings.append(embedding.cpu().numpy().flatten().tolist())
            
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            embeddings.append([0.0] * EMBEDDING_DIM)
    
    return pd.Series(embeddings)

print("✓ Pandas UDF for embeddings defined")

# COMMAND ----------

# DBTITLE 1,Generate Embeddings for All Items
print("🚀 Generating CLIP embeddings for all items...")
print(f"   Using model: {CLIP_MODEL}")
print(f"   Embedding dimension: {EMBEDDING_DIM}")
print(f"   This may take 30-60 minutes for full dataset...")

# Sample for testing (remove .limit() for full processing)
# items_to_embed = all_items.limit(1000)  # TEST WITH SMALL SAMPLE FIRST
items_to_embed = all_items  # Full dataset

# Add unique ID
items_with_id = items_to_embed.withColumn(
    "item_uid", 
    F.concat(F.col("image_name"), F.lit("_"), F.col("item_id").cast("string"))
)

# Repartition for parallel processing (adjust based on cluster size)
items_partitioned = items_with_id.repartition(100)

# Generate embeddings
items_embedded = items_partitioned.withColumn(
    "clip_embedding",
    generate_embeddings_udf(F.col("image_path"), F.col("bbox"))
)

# Cache result (important!)
items_embedded = items_embedded.cache()

# Trigger computation
embedding_count = items_embedded.count()
print(f"✓ Generated {embedding_count:,} embeddings")

# COMMAND ----------

# DBTITLE 1,Save Items with Embeddings to Delta
# Write to Delta table
items_table = f"{TABLE_PREFIX}.df2_items"

print(f"💾 Saving items with embeddings to {items_table}...")

items_embedded.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(items_table)

print(f"✓ Saved {items_embedded.count():,} items to {items_table}")

# Optimize table
spark.sql(f"OPTIMIZE {items_table}")
print("✓ Table optimized")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Build Outfit Compositions

# COMMAND ----------

# DBTITLE 1,Create Outfit-Level Table
print("👗 Building outfit compositions...")

# Group items by image to create outfits
outfits_df = spark.table(items_table).groupBy("image_name", "split").agg(
    F.collect_list(
        F.struct(
            "item_uid",
            "item_id",
            "category_id",
            "category_name",
            "bbox",
            "clip_embedding",
            "style",
            "scale",
            "occlusion"
        )
    ).alias("items"),
    F.count("*").alias("num_items")
).filter(
    F.col("num_items") >= 2  # Only outfits with 2+ items
)

print(f"✓ Created {outfits_df.count():,} outfit compositions")

# Save outfits table
outfits_table = f"{TABLE_PREFIX}.df2_outfits"
outfits_df.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(outfits_table)

print(f"✓ Saved to {outfits_table}")

# Show sample
display(spark.table(outfits_table).limit(5))

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
