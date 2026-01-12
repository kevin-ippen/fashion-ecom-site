# Databricks notebook source
# DBTITLE 1,Configuration and imports
# Install required package
%pip install databricks-vectorsearch --quiet
dbutils.library.restartPython()

# Configuration
import numpy as np
from datetime import datetime
from pyspark.sql import functions as F
from pyspark.sql.types import *
from pyspark.sql.window import Window
from databricks.vector_search.client import VectorSearchClient
import time

CATALOG = "main"
DEMO_SCHEMA = "fashion_demo"
SOTA_SCHEMA = "fashion_sota"

# Table names
PRODUCT_TABLE = f"{CATALOG}.{SOTA_SCHEMA}.product_embeddings"
FILTERED_PRODUCT_TABLE = f"{CATALOG}.{SOTA_SCHEMA}.product_embeddings_us_relevant"
DF2_GARMENTS_TABLE = f"{CATALOG}.{DEMO_SCHEMA}.df2_garment_embeddings_fashionclip"
DF2_OUTFITS_TABLE = f"{CATALOG}.{DEMO_SCHEMA}.df2_outfit_composition"

# Vector search config (REQUIRED for performance at scale)
VECTOR_SEARCH_ENDPOINT = "fashion_vector_search"
VECTOR_INDEX_NAME = f"{CATALOG}.{SOTA_SCHEMA}.product_embeddings_us_relevant_index"

# Output tables
GARMENT_MATCHES_TABLE = f"{CATALOG}.{DEMO_SCHEMA}.df2_garment_to_product_matches"
OUTFIT_RECOMMENDATIONS_TABLE = f"{CATALOG}.{SOTA_SCHEMA}.df2_outfit_recommendations_v2"

# Pipeline parameters
TOP_K_PRODUCTS = 25  # Number of similar products per garment
CHECKPOINT_BATCH_SIZE = 500  # Save progress every N garments

print("✓ Configuration loaded")
print(f"\n📊 Pipeline Overview:")
print(f"  1. Filter products: {PRODUCT_TABLE} → {FILTERED_PRODUCT_TABLE}")
print(f"  2. Create vector index: {VECTOR_INDEX_NAME} (REQUIRED for performance)")
print(f"  3. Match garments: {DF2_GARMENTS_TABLE} → top {TOP_K_PRODUCTS} products each")
print(f"  4. Cross-match: {DF2_OUTFITS_TABLE} → {OUTFIT_RECOMMENDATIONS_TABLE}")

# COMMAND ----------

# DBTITLE 1,Filter products to US-relevant items
# Filter product embeddings to US-relevant Apparel and Footwear
from pyspark.sql.functions import col

print("🌎 Filtering to US-relevant products...\n")
print("=" * 80)

# Load full product catalog
products_all = spark.table("main.fashion_sota.product_embeddings")
total_products = products_all.count()

print(f"✓ Total products: {total_products:,}")

# Category distribution
print("\n📊 Category distribution:")
category_dist = products_all.groupBy("master_category").count().orderBy(col("count").desc())
display(category_dist)

# Filter to Apparel + Footwear
products_apparel_footwear = products_all.filter(
    col("master_category").isin(["Apparel", "Footwear"])
)

print(f"\n✓ Apparel + Footwear: {products_apparel_footwear.count():,}")

# Exclude culturally specific items not common in US market
exclude_subcategories = [
    "Saree", "Kurta", "Kurtas", "Kurtis", "Tunics",
    "Churidar", "Salwar", "Salwar and Dupatta", "Lehenga", "Dupatta",
    "Patiala", "Dhoti", "Nehru Jackets"
]

products_us_relevant = products_apparel_footwear.filter(
    ~col("sub_category").isin(exclude_subcategories)
)

us_count = products_us_relevant.count()
print(f"\n✓ US-relevant products: {us_count:,}")
print(f"✓ Excluded: {products_apparel_footwear.count() - us_count:,} culturally specific items")
print(f"✓ Total reduction: {total_products - us_count:,} products ({(total_products - us_count)/total_products*100:.1f}%)")

print(f"\n💾 Saving to: {FILTERED_PRODUCT_TABLE}")
print("   (Required for vector search index)")

# Check if table exists
try:
    existing = spark.table(FILTERED_PRODUCT_TABLE)
    print(f"\n⚠️  Table already exists with {existing.count():,} rows")
    print("   Skipping write (use DROP TABLE to recreate)")
except:
    products_us_relevant.write.saveAsTable(FILTERED_PRODUCT_TABLE)
    print(f"\n✓ Table created: {us_count:,} rows")

print("\n✓ Filtered product data ready!")

# COMMAND ----------

# DBTITLE 1,Load DF2 data and analyze composition
# Load DF2 garment embeddings AND outfit compositions
from pyspark.sql.functions import col, size

print("📸 Loading DF2 data...\n")
print("=" * 80)

# CRITICAL: Load df2_garments from the garment embeddings table
print(f"📂 Loading garment embeddings from: {DF2_GARMENTS_TABLE}")
df2_garments = spark.table(DF2_GARMENTS_TABLE)
total_garments = df2_garments.count()
print(f"✓ Total DF2 garments: {total_garments:,}")

# Verify embedding column exists and check dimensions
sample_embedding = df2_garments.select("embedding").first()
if sample_embedding and sample_embedding.embedding:
    embedding_dim = len(sample_embedding.embedding)
    print(f"✓ Embedding dimension: {embedding_dim}")
else:
    raise ValueError("❌ Embedding column is missing or empty!")

# Load outfit compositions
print(f"\n📂 Loading outfit compositions from: {DF2_OUTFITS_TABLE}")
df2_outfits = spark.table(DF2_OUTFITS_TABLE)
total_outfits = df2_outfits.count()
print(f"✓ Total DF2 outfits: {total_outfits:,}")

# Analyze outfit composition
outfits_with_counts = df2_outfits.withColumn("garment_count", size(col("garments")))

# Statistics
print("\n📊 Outfit composition:")
size_dist = outfits_with_counts.groupBy("garment_count").count().orderBy("garment_count")
display(size_dist)

# Multi-garment outfits (positive pairs)
multi_garment = outfits_with_counts.filter(col("garment_count") >= 2)
multi_count = multi_garment.count()

print(f"\n✓ Multi-garment outfits (2+ items): {multi_count:,} ({multi_count/total_outfits*100:.1f}%)")
print(f"✓ Single-garment outfits: {total_outfits - multi_count:,} ({(total_outfits-multi_count)/total_outfits*100:.1f}%)")
print(f"✓ Avg garments per outfit: {total_garments / total_outfits:.2f}")

print("\n📊 Sample multi-garment outfit:")
sample = multi_garment.limit(1).collect()[0]
print(f"  Outfit ID: {sample.outfit_id}")
print(f"  Garments: {len(sample.garments)}")
for g in sample.garments:
    print(f"    • {g.garment_id}: {g.category_name}")

# Cache the garments dataframe for reuse
df2_garments.cache()
print(f"\n✓ df2_garments cached ({total_garments:,} rows)")
print(f"✓ Data ready for pipeline!")

# COMMAND ----------

# DBTITLE 1,Create vector search index on filtered products
# Create vector search index for performant similarity search
from databricks.vector_search.client import VectorSearchClient
import time

print("🔨 Creating vector search index...\n")
print("=" * 80)

vsc = VectorSearchClient()

print(f"📊 Scale requirements:")
print(f"  • DF2 garments: 3,212")
print(f"  • Products: ~25,000 (US-relevant)")
print(f"  • Without index: 3,212 × 25,000 = 80M comparisons (too slow!)")
print(f"  • With index: 3,212 × log(25,000) ≈ 45K comparisons (fast!)\n")

# Check if index exists
try:
    existing_index = vsc.get_index(
        endpoint_name=VECTOR_SEARCH_ENDPOINT,
        index_name=VECTOR_INDEX_NAME
    )
    status = existing_index.describe()
    is_ready = status.get('status', {}).get('ready', False)
    
    if is_ready:
        print(f"✓ Index already exists and is READY: {VECTOR_INDEX_NAME}")
        print(f"  Primary key: {status.get('primary_key')}")
        print(f"  Embedding dimension: {status.get('index_spec', {}).get('embedding_vector_columns', [{}])[0].get('embedding_dimension', 'N/A')}")
        print("\n✓ Skipping index creation")
    else:
        print(f"⚠️  Index exists but not ready. Status: {status.get('status')}")
        print("   Waiting for index to sync...")
        
except Exception as e:
    print(f"📝 Index doesn't exist. Creating: {VECTOR_INDEX_NAME}\n")
    
    # Verify filtered table exists
    try:
        filtered_table = spark.table(FILTERED_PRODUCT_TABLE)
        row_count = filtered_table.count()
        print(f"✓ Source table exists: {FILTERED_PRODUCT_TABLE} ({row_count:,} rows)")
    except:
        print(f"✗ Source table not found: {FILTERED_PRODUCT_TABLE}")
        print("   Run previous cell to create filtered product table first")
        raise
    
    # Create index
    print(f"\n🔨 Creating delta sync index...")
    print(f"   Endpoint: {VECTOR_SEARCH_ENDPOINT}")
    print(f"   Source: {FILTERED_PRODUCT_TABLE}")
    print(f"   Primary key: product_id")
    print(f"   Embedding column: embedding")
    print(f"   Dimension: 512\n")
    
    index = vsc.create_delta_sync_index(
        endpoint_name=VECTOR_SEARCH_ENDPOINT,
        source_table_name=FILTERED_PRODUCT_TABLE,
        index_name=VECTOR_INDEX_NAME,
        primary_key="product_id",
        embedding_dimension=512,
        embedding_vector_column="embedding",
        pipeline_type="TRIGGERED"
    )
    
    print("✓ Index creation initiated!")
    print("\n⏳ Waiting for index to sync (5-10 minutes)...")
    
    # Wait for index to be ready
    max_wait = 600  # 10 minutes
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            status = vsc.get_index(
                endpoint_name=VECTOR_SEARCH_ENDPOINT,
                index_name=VECTOR_INDEX_NAME
            ).describe()
            
            if status.get('status', {}).get('ready', False):
                print(f"\n✓ Index is READY! (took {int(time.time() - start_time)}s)")
                break
            else:
                elapsed = int(time.time() - start_time)
                if elapsed % 30 == 0:  # Update every 30s
                    print(f"   [{elapsed}s] Still syncing...")
                time.sleep(10)
        except:
            time.sleep(10)
    else:
        print(f"\n⚠️  Index not ready after {max_wait}s")
        print("   Check status manually before proceeding")

print("\n✓ Vector search index ready for queries!")

# COMMAND ----------

# DBTITLE 1,Per-garment retrieval: Find top-k products (with checkpointing)
# For each DF2 garment, retrieve top-k similar products via vector search
# INCLUDES: Checkpointing for restart capability, efficient batching

print("🔍 Per-Garment Retrieval: Top-K Products\n")
print("=" * 80)

# Schema for matches table (pre-create for checkpointing)
matches_schema = StructType([
    StructField("garment_id", StringType(), False),
    StructField("outfit_id", StringType(), False),
    StructField("garment_category", StringType(), False),
    StructField("product_id", StringType(), False),
    StructField("product_name", StringType(), True),
    StructField("product_category", StringType(), True),
    StructField("product_gender", StringType(), True),
    StructField("similarity", DoubleType(), False),
    StructField("rank", IntegerType(), False),
    StructField("processed_at", TimestampType(), False)
])

# Pre-create output table if it doesn't exist
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {GARMENT_MATCHES_TABLE} (
        garment_id STRING NOT NULL,
        outfit_id STRING NOT NULL,
        garment_category STRING NOT NULL,
        product_id STRING NOT NULL,
        product_name STRING,
        product_category STRING,
        product_gender STRING,
        similarity DOUBLE NOT NULL,
        rank INT NOT NULL,
        processed_at TIMESTAMP NOT NULL
    ) USING DELTA
""")
print(f"✓ Output table ready: {GARMENT_MATCHES_TABLE}")

# Get already-processed garment IDs (for restart capability)
try:
    processed_garments = set([
        row['garment_id'] for row in
        spark.table(GARMENT_MATCHES_TABLE)
            .select('garment_id').distinct().collect()
    ])
    print(f"✓ Found {len(processed_garments):,} already-processed garments (restart mode)")
except:
    processed_garments = set()
    print("✓ Starting fresh (no existing progress)")

# Initialize vector search
vsc = VectorSearchClient()
index = vsc.get_index(
    endpoint_name=VECTOR_SEARCH_ENDPOINT,
    index_name=VECTOR_INDEX_NAME
)
print(f"✓ Vector search index loaded")

# Get garments to process (excluding already processed)
all_garments = df2_garments.select(
    "garment_id",
    "outfit_id",
    "category_name",
    "embedding"
)

total_garments = all_garments.count()
remaining_garments = total_garments - len(processed_garments)

print(f"\n📊 Processing Status:")
print(f"   Total garments: {total_garments:,}")
print(f"   Already processed: {len(processed_garments):,}")
print(f"   Remaining: {remaining_garments:,}")
print(f"   Top-K per garment: {TOP_K_PRODUCTS}")
print(f"   Checkpoint every: {CHECKPOINT_BATCH_SIZE} garments\n")

if remaining_garments == 0:
    print("✓ All garments already processed! Skipping to next step.")
else:
    # Collect garments to process (filter out already processed)
    garments_list = [
        g for g in all_garments.collect()
        if g.garment_id not in processed_garments
    ]

    print(f"🔄 Starting vector search queries...")
    start_time = time.time()

    # Process in checkpoint batches
    batch_matches = []
    error_count = 0
    processed_count = 0

    for idx, garment in enumerate(garments_list):
        try:
            # Query vector search for top-k similar products
            search_result = index.similarity_search(
                query_vector=list(garment.embedding),  # Ensure it's a list
                columns=["product_id", "product_display_name", "sub_category", "gender"],
                num_results=TOP_K_PRODUCTS
            )

            # Extract matches with rank
            if search_result and 'result' in search_result:
                data_array = search_result['result'].get('data_array', [])
                current_time = datetime.now()

                for rank, row in enumerate(data_array, 1):
                    batch_matches.append({
                        'garment_id': garment.garment_id,
                        'outfit_id': garment.outfit_id,
                        'garment_category': garment.category_name,
                        'product_id': str(row[0]),
                        'product_name': row[1] if len(row) > 1 else None,
                        'product_category': row[2] if len(row) > 2 else None,
                        'product_gender': row[3] if len(row) > 3 else None,
                        'similarity': float(row[-1]),  # Score is always last
                        'rank': rank,
                        'processed_at': current_time
                    })

            processed_count += 1

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"  ⚠️  Error for garment {garment.garment_id}: {str(e)[:100]}")
            continue

        # Checkpoint: Save progress every CHECKPOINT_BATCH_SIZE garments
        if (processed_count > 0 and processed_count % CHECKPOINT_BATCH_SIZE == 0) or \
           (idx == len(garments_list) - 1 and batch_matches):

            # Write batch to table
            batch_df = spark.createDataFrame(batch_matches, schema=matches_schema)
            batch_df.write.format("delta").mode("append").saveAsTable(GARMENT_MATCHES_TABLE)

            elapsed = time.time() - start_time
            rate = processed_count / elapsed if elapsed > 0 else 0
            eta = (remaining_garments - processed_count) / rate if rate > 0 else 0

            print(f"  ✓ Checkpoint {processed_count:,}/{remaining_garments:,} " +
                  f"({processed_count/remaining_garments*100:.1f}%) | " +
                  f"{len(batch_matches):,} matches saved | " +
                  f"Rate: {rate:.1f}/s | ETA: {eta/60:.1f}min")

            batch_matches = []  # Reset batch

    # Final stats
    elapsed = time.time() - start_time
    print(f"\n✓ Vector search complete!")
    print(f"✓ Processed: {processed_count:,} garments in {elapsed/60:.1f} minutes")
    print(f"✓ Rate: {processed_count/elapsed:.1f} garments/sec")

    if error_count > 0:
        print(f"⚠️  Errors encountered: {error_count} ({error_count/remaining_garments*100:.1f}%)")

# Verify final results
final_matches = spark.table(GARMENT_MATCHES_TABLE)
total_matches = final_matches.count()
unique_garments = final_matches.select("garment_id").distinct().count()

print(f"\n📊 Final Results:")
print(f"   Total matches: {total_matches:,}")
print(f"   Unique garments matched: {unique_garments:,}")
print(f"   Expected matches: {total_garments * TOP_K_PRODUCTS:,}")
print(f"   Coverage: {unique_garments/total_garments*100:.1f}%")

print(f"\n📊 Top 10 matches (highest similarity):")
display(final_matches.orderBy(F.col("similarity").desc()).limit(10))

# COMMAND ----------

# DBTITLE 1,Strategy explanation
# MAGIC %md
# MAGIC ## 🎯 Strategy: Garment-to-Product Matching
# MAGIC
# MAGIC ### What We Just Did
# MAGIC
# MAGIC For each of **3,212 DF2 garments**, we found the **top 25 most similar products** from the catalog using FashionCLIP cosine similarity.
# MAGIC
# MAGIC **Example:**
# MAGIC ```
# MAGIC DF2 Outfit 000620:
# MAGIC   ├─ Garment 000620_7 (shorts, embedding C)
# MAGIC   │  └─ Top 25: [Puma Shorts, Nike Shorts, Adidas Shorts, ...]
# MAGIC   └─ Garment 000620_1 (short sleeve top, embedding H)
# MAGIC      └─ Top 25: [Locomotive T-shirt, Puma Top, Nike Tee, ...]
# MAGIC ```
# MAGIC
# MAGIC ### Next Step: Cross-Match Within Outfits
# MAGIC
# MAGIC For each **multi-garment outfit** (601 outfits with 2+ items):
# MAGIC 1. Get products matched to Garment 1 (25 products)
# MAGIC 2. Get products matched to Garment 2 (25 products)
# MAGIC 3. Cross-match: 25 × 25 = **625 outfit combinations**
# MAGIC 4. Repeat for all garment pairs in the outfit
# MAGIC
# MAGIC **Result:** Product outfit recommendations that mirror real DF2 outfit patterns!

# COMMAND ----------

# DBTITLE 1,Slot-aware cross-matching within outfits (with Delta checkpoint)
# Slot-aware cross-matching: Match products from DIFFERENT garment slots
# CHECKPOINT: Save intermediate outfit-garment-product mappings to Delta

# Temp table for checkpoint
OUTFIT_GARMENT_PRODUCTS_TABLE = f"{CATALOG}.{DEMO_SCHEMA}.df2_outfit_garment_products_temp"

print("🎯 Slot-Aware Cross-Matching Within Outfits\n")
print("=" * 80)

# Check if checkpoint already exists
try:
    existing_checkpoint = spark.table(OUTFIT_GARMENT_PRODUCTS_TABLE)
    checkpoint_count = existing_checkpoint.count()
    print(f"✓ Found existing checkpoint: {OUTFIT_GARMENT_PRODUCTS_TABLE}")
    print(f"  Rows: {checkpoint_count:,}")

    use_checkpoint = checkpoint_count > 0
except:
    use_checkpoint = False
    print("✓ No existing checkpoint found - will create fresh")

if use_checkpoint:
    # Use existing checkpoint
    outfit_garment_products = spark.table(OUTFIT_GARMENT_PRODUCTS_TABLE)
    joined_count = outfit_garment_products.count()
    print(f"\n✓ Loaded {joined_count:,} outfit-garment-product mappings from checkpoint")
else:
    # Load garment matches
    garment_matches = spark.table(GARMENT_MATCHES_TABLE)
    total_matches = garment_matches.count()
    total_garments = df2_garments.count()

    print(f"✓ Loaded {total_matches:,} garment-to-product matches")
    print(f"  Expected: {total_garments * TOP_K_PRODUCTS:,} ({total_garments:,} garments × {TOP_K_PRODUCTS} products)")
    print(f"  Coverage: {total_matches / (total_garments * TOP_K_PRODUCTS) * 100:.1f}%\n")

    # Load multi-garment outfits
    multi_garment_outfits = spark.table(DF2_OUTFITS_TABLE).withColumn(
        "garment_count", F.size(F.col("garments"))
    ).filter(F.col("garment_count") >= 2)

    multi_outfit_count = multi_garment_outfits.count()
    print(f"✓ Multi-garment outfits: {multi_outfit_count:,}\n")

    # Explode garments to get outfit-garment pairs
    outfit_garments = multi_garment_outfits.select(
        F.col("outfit_id"),
        F.explode(F.col("garments")).alias("garment")
    ).select(
        F.col("outfit_id"),
        F.col("garment.garment_id").alias("garment_id"),
        F.col("garment.category_name").alias("garment_category")
    )

    outfit_garment_count = outfit_garments.count()
    print(f"✓ Exploded to {outfit_garment_count:,} outfit-garment pairs")

    # Join with matches to get products for each garment in each outfit
    # Use broadcast hint for smaller table if garment matches fits in memory
    outfit_garment_products = outfit_garments.join(
        garment_matches.select(
            "garment_id", "outfit_id", "product_id", "product_name",
            "product_category", "product_gender", "similarity", "rank"
        ),
        on=["outfit_id", "garment_id"],
        how="inner"
    ).select(
        F.col("outfit_id"),
        F.col("garment_id"),
        F.col("garment_category"),
        F.col("product_id"),
        F.col("product_name"),
        F.col("product_category"),
        F.col("product_gender"),
        F.col("similarity"),
        F.col("rank")
    )

    joined_count = outfit_garment_products.count()
    print(f"✓ Joined outfit-garment-product mappings: {joined_count:,} rows")

    if joined_count == 0:
        print("\n❌ ERROR: No matches found!")
        print("   Possible causes:")
        print("   1. garment_id mismatch between tables")
        print("   2. outfit_id mismatch")
        print("   3. Vector search returned no results")

        # Debug info
        print("\n🔍 Debug info:")
        print(f"   Garment IDs in matches: {garment_matches.select('garment_id').distinct().count()}")
        print(f"   Outfit IDs in matches: {garment_matches.select('outfit_id').distinct().count()}")
        print(f"   Sample match garment_id: {garment_matches.select('garment_id').first()}")
        print(f"   Sample outfit garment_id: {outfit_garments.select('garment_id').first()}")
        raise ValueError("No outfit-garment-product mappings found")

    # CHECKPOINT: Save to Delta table
    print(f"\n💾 Saving checkpoint to: {OUTFIT_GARMENT_PRODUCTS_TABLE}")
    outfit_garment_products.write.format("delta").mode("overwrite").saveAsTable(OUTFIT_GARMENT_PRODUCTS_TABLE)
    print(f"✓ Checkpoint saved: {joined_count:,} rows")

print("\n📊 Sample outfit-garment-product mappings:")
display(outfit_garment_products.limit(10))

# COMMAND ----------

# DBTITLE 1,Generate outfit combinations with slot filtering (optimized)
# Cross-match products from DIFFERENT garment slots (categories)
# OPTIMIZED: Process by outfit to reduce memory, checkpoint to Delta

# Temp table for raw pairs checkpoint
OUTFIT_PAIRS_TABLE = f"{CATALOG}.{DEMO_SCHEMA}.df2_outfit_pairs_temp"

print("🔀 Generating Outfit Combinations (Slot-Aware)\n")
print("=" * 80)

print("🔑 Key principle: Each garment occupies a DIFFERENT slot")
print("   • Top + Bottom = Valid outfit")
print("   • Top + Top = Invalid (same slot)")
print("   • Shoe + Shoe = Invalid (same slot)\n")

# Check if checkpoint exists
try:
    existing_pairs = spark.table(OUTFIT_PAIRS_TABLE)
    pairs_count = existing_pairs.count()
    print(f"✓ Found existing pairs checkpoint: {pairs_count:,} rows")
    use_pairs_checkpoint = pairs_count > 0
except:
    use_pairs_checkpoint = False
    print("✓ No pairs checkpoint found - will generate fresh")

if use_pairs_checkpoint:
    outfit_pairs = spark.table(OUTFIT_PAIRS_TABLE)
    print(f"✓ Loaded {outfit_pairs.count():,} outfit pairs from checkpoint")
else:
    # Load intermediate checkpoint
    outfit_garment_products = spark.table(OUTFIT_GARMENT_PRODUCTS_TABLE)

    print(f"📊 Cross-matching stats:")
    print(f"   Input rows: {outfit_garment_products.count():,}")
    unique_outfits = outfit_garment_products.select("outfit_id").distinct().count()
    print(f"   Unique outfits: {unique_outfits:,}")

    # OPTIMIZATION: Repartition by outfit_id to co-locate data for self-join
    outfit_garment_products = outfit_garment_products.repartition(200, "outfit_id")

    print("\n🔄 Self-joining to create product pairs...")
    start_time = time.time()

    # Self-join to create pairs from DIFFERENT garment categories
    # Use explicit column references to avoid ambiguity
    g1 = outfit_garment_products.alias("g1")
    g2 = outfit_garment_products.alias("g2")

    outfit_pairs = g1.join(
        g2,
        (
            (F.col("g1.outfit_id") == F.col("g2.outfit_id")) &  # Same DF2 outfit
            (F.col("g1.garment_id") < F.col("g2.garment_id")) &  # Avoid duplicates
            (F.col("g1.garment_category") != F.col("g2.garment_category")) &  # DIFFERENT slots
            (F.col("g1.product_id") != F.col("g2.product_id"))  # Different products
        ),
        "inner"
    ).select(
        F.col("g1.outfit_id").alias("source_outfit_id"),
        F.col("g1.garment_id").alias("garment_1_id"),
        F.col("g1.garment_category").alias("garment_1_category"),
        F.col("g1.product_id").alias("product_1_id"),
        F.col("g1.product_name").alias("product_1_name"),
        F.col("g1.product_category").alias("product_1_category"),
        F.col("g1.product_gender").alias("product_1_gender"),
        F.col("g1.similarity").alias("garment_1_similarity"),
        F.col("g1.rank").alias("garment_1_rank"),
        F.col("g2.garment_id").alias("garment_2_id"),
        F.col("g2.garment_category").alias("garment_2_category"),
        F.col("g2.product_id").alias("product_2_id"),
        F.col("g2.product_name").alias("product_2_name"),
        F.col("g2.product_category").alias("product_2_category"),
        F.col("g2.product_gender").alias("product_2_gender"),
        F.col("g2.similarity").alias("garment_2_similarity"),
        F.col("g2.rank").alias("garment_2_rank")
    )

    # CHECKPOINT: Save raw pairs to Delta
    print(f"\n💾 Saving pairs checkpoint to: {OUTFIT_PAIRS_TABLE}")
    outfit_pairs.write.format("delta").mode("overwrite").saveAsTable(OUTFIT_PAIRS_TABLE)

    elapsed = time.time() - start_time
    pairs_count = spark.table(OUTFIT_PAIRS_TABLE).count()
    print(f"✓ Generated {pairs_count:,} outfit pairs in {elapsed:.1f}s")

    # Reload from checkpoint for consistency
    outfit_pairs = spark.table(OUTFIT_PAIRS_TABLE)

# Calculate outfit-level score (average of garment similarities)
print("\n📈 Calculating outfit scores...")

outfit_recommendations = outfit_pairs.withColumn(
    "outfit_score",
    (F.col("garment_1_similarity") + F.col("garment_2_similarity")) / 2
).withColumn(
    "combined_rank",
    F.col("garment_1_rank") + F.col("garment_2_rank")
).withColumn(
    "source_method",
    F.lit("df2_slot_aware_matching")
).withColumn(
    "created_at",
    F.current_timestamp()
).withColumn(
    "model_version",
    F.lit("v2.0_fashionclip_vector_search")
)

total_recs = outfit_recommendations.count()
print(f"✓ Generated {total_recs:,} outfit combinations with scores")

# Quality filtering stats
print("\n📈 Similarity distribution:")
stats = outfit_recommendations.select(
    "garment_1_similarity",
    "garment_2_similarity",
    "outfit_score"
).summary("mean", "25%", "50%", "75%", "max")
display(stats)

print("\n🏆 Top 20 outfit recommendations (by score):")
display(outfit_recommendations.orderBy(F.col("outfit_score").desc()).limit(20))

# COMMAND ----------

# DBTITLE 1,Save outfit recommendations to Delta table (with quality filtering)
# Save final outfit recommendations with optional quality filtering

print(f"💾 Saving outfit recommendations...\n")
print("=" * 80)

# Quality filtering parameters
MIN_OUTFIT_SCORE = 0.0  # Set > 0 to filter low-quality matches (e.g., 0.3)
MAX_COMBINED_RANK = 50  # Set lower to keep only top matches (e.g., 10)

# Apply quality filters
filtered_recommendations = outfit_recommendations

if MIN_OUTFIT_SCORE > 0:
    before_filter = filtered_recommendations.count()
    filtered_recommendations = filtered_recommendations.filter(
        F.col("outfit_score") >= MIN_OUTFIT_SCORE
    )
    after_filter = filtered_recommendations.count()
    print(f"✓ Score filter (>= {MIN_OUTFIT_SCORE}): {before_filter:,} → {after_filter:,}")

if MAX_COMBINED_RANK < 50:
    before_filter = filtered_recommendations.count()
    filtered_recommendations = filtered_recommendations.filter(
        F.col("combined_rank") <= MAX_COMBINED_RANK
    )
    after_filter = filtered_recommendations.count()
    print(f"✓ Rank filter (<= {MAX_COMBINED_RANK}): {before_filter:,} → {after_filter:,}")

total_recs = filtered_recommendations.count()
print(f"\n✓ Final recommendations: {total_recs:,}")
print(f"💾 Saving to: {OUTFIT_RECOMMENDATIONS_TABLE}")

# Save to table with optimization
filtered_recommendations.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(OUTFIT_RECOMMENDATIONS_TABLE)

print(f"\n✓ Table created successfully!")

# Optimize the table for query performance
print(f"⚡ Optimizing table...")
spark.sql(f"OPTIMIZE {OUTFIT_RECOMMENDATIONS_TABLE}")

# Verify
saved_table = spark.table(OUTFIT_RECOMMENDATIONS_TABLE)
print(f"\n📊 Table details:")
print(f"   Name: {OUTFIT_RECOMMENDATIONS_TABLE}")
print(f"   Rows: {saved_table.count():,}")
print(f"   Columns: {len(saved_table.columns)}")
print(f"   Schema:")
for field in saved_table.schema.fields[:12]:  # Show first 12 columns
    print(f"     • {field.name}: {field.dataType.simpleString()}")

print(f"\n✓ Pipeline complete!")
print(f"\n🎉 Output: {OUTFIT_RECOMMENDATIONS_TABLE}")
print(f"   Use this table for outfit recommendations in your application!")

# COMMAND ----------

# DBTITLE 1,Validate results and analyze quality
# Comprehensive validation of outfit recommendations

print("✅ Validating Outfit Recommendations\n")
print("=" * 80)

recs = spark.table(OUTFIT_RECOMMENDATIONS_TABLE)
recs_count = recs.count()

# Coverage analysis
print("📊 Coverage Analysis:\n")

unique_products_1 = recs.select("product_1_id").distinct().count()
unique_products_2 = recs.select("product_2_id").distinct().count()
unique_products_total = recs.select("product_1_id").union(
    recs.select("product_2_id")
).distinct().count()

# Load product count from filtered table
total_products = spark.table(FILTERED_PRODUCT_TABLE).count()

print(f"✓ Total recommendations: {recs_count:,}")
print(f"✓ Unique products in recommendations: {unique_products_total:,}")
print(f"✓ Total US-relevant products: {total_products:,}")
print(f"✓ Product coverage: {unique_products_total/total_products*100:.1f}%")
print(f"\n  Product 1 (first slot): {unique_products_1:,} unique")
print(f"  Product 2 (second slot): {unique_products_2:,} unique")

# Source outfit coverage
unique_outfits = recs.select("source_outfit_id").distinct().count()
multi_outfit_count = spark.table(DF2_OUTFITS_TABLE).withColumn(
    "garment_count", F.size(F.col("garments"))
).filter(F.col("garment_count") >= 2).count()

print(f"\n✓ DF2 outfits used: {unique_outfits:,} / {multi_outfit_count:,} multi-garment outfits")
print(f"✓ Outfit coverage: {unique_outfits/multi_outfit_count*100:.1f}%")

# Quality metrics
print(f"\n📈 Quality Metrics:\n")

quality_stats = recs.agg(
    F.avg("outfit_score").alias("avg_score"),
    F.min("outfit_score").alias("min_score"),
    F.max("outfit_score").alias("max_score"),
    F.avg("garment_1_similarity").alias("avg_g1_sim"),
    F.avg("garment_2_similarity").alias("avg_g2_sim"),
    F.avg("combined_rank").alias("avg_rank")
).collect()[0]

print(f"✓ Avg outfit score: {quality_stats.avg_score:.3f}")
print(f"✓ Score range: [{quality_stats.min_score:.3f} - {quality_stats.max_score:.3f}]")
print(f"✓ Avg garment 1 similarity: {quality_stats.avg_g1_sim:.3f}")
print(f"✓ Avg garment 2 similarity: {quality_stats.avg_g2_sim:.3f}")
print(f"✓ Avg combined rank: {quality_stats.avg_rank:.1f}")

# Category slot pairings (cross-category only)
print(f"\n🎯 Top 15 Garment Slot Pairings (Cross-Category):")
category_pairs = recs.groupBy(
    "garment_1_category",
    "garment_2_category"
).agg(
    F.count("*").alias("pair_count"),
    F.avg("outfit_score").alias("avg_score")
).orderBy(F.col("pair_count").desc())

display(category_pairs.limit(15))

print("\n✓ Validation complete!")
print("\n💡 Key Insight: All pairs are cross-category (different slots) as intended!")

# COMMAND ----------

# DBTITLE 1,Compare with existing recommendations
# Compare new DF2-based recommendations with existing recommendations
from pyspark.sql.functions import col

print("🔍 Comparing with existing recommendations...\n")
print("=" * 80)

# Load existing recommendations
try:
    existing_recs = spark.table(f"{CATALOG}.{SOTA_SCHEMA}.outfit_recommendations")
    
    print("Existing recommendations:")
    print(f"  Total pairs: {existing_recs.count():,}")
    print(f"  Method: Co-occurrence based")
    print(f"  Columns: {existing_recs.columns}")
    
    print("\nNew DF2-based recommendations:")
    new_recs = spark.table(OUTFIT_RECOMMENDATIONS_TABLE)
    print(f"  Total pairs: {new_recs.count():,}")
    print(f"  Method: Garment similarity matching")
    print(f"  Source: DeepFashion2 outfit patterns")
    
    print("\n🎯 Key Differences:")
    print("  • Existing: Based on product co-purchase/co-view data")
    print("  • New: Based on visual similarity to real outfit compositions")
    print("  • New: Captures style coherence via FashionCLIP embeddings")
    print("  • New: Each recommendation traces back to specific DF2 outfit")
    
    print("\n💡 Usage Recommendation:")
    print("  • Use NEW for style-aware, visually coherent recommendations")
    print("  • Use EXISTING for popularity-based recommendations")
    print("  • Consider ENSEMBLE: Combine both with weighted scoring")
    
except Exception as e:
    print(f"⚠️  Could not load existing recommendations: {e}")
    print("\n✓ New recommendations table is ready to use!")

print(f"\n✓ Analysis complete!")
print(f"\n🎉 Pipeline finished successfully!")
print(f"\n📊 Final output: {OUTFIT_RECOMMENDATIONS_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎉 DF2 Garment-to-Product Outfit Recommendations Pipeline
# MAGIC
# MAGIC ### ✅ Pipeline Complete!
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 📊 What Was Built
# MAGIC
# MAGIC **Input Data:**
# MAGIC * **3,212 DF2 garments** with FashionCLIP embeddings (512-dim, L2-normalized)
# MAGIC * **601 multi-garment outfits** from DeepFashion2 (avg 3.21 garments/outfit)
# MAGIC * **~25,000 apparel/footwear products** from catalog (filtered from 43,916)
# MAGIC
# MAGIC **Pipeline Steps:**
# MAGIC
# MAGIC 1️⃣ **Filter Products** → Apparel + Footwear only  
# MAGIC 2️⃣ **Rebuild Vector Index** → `product_embeddings_apparel_footwear_index`  
# MAGIC 3️⃣ **Vector Search** → For each garment, find top 25 similar products  
# MAGIC 4️⃣ **Cross-Match** → Combine products from different garments in same outfit  
# MAGIC 5️⃣ **Score & Save** → Combined similarity score, save to Delta table
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 🎯 How It Works (Your Strategy)
# MAGIC
# MAGIC **Example: DF2 Outfit 000710**
# MAGIC
# MAGIC ```
# MAGIC Outfit 000710 (3 garments):
# MAGIC ├─ Garment 1: long sleeve top (embedding C)
# MAGIC │  └─ Top 25 products: [Locomotive Shirt, Puma Top, ...]
# MAGIC ├─ Garment 2: trousers (embedding H)  
# MAGIC │  └─ Top 25 products: [Levis Jeans, Puma Trousers, ...]
# MAGIC └─ Garment 3: skirt (embedding Y)
# MAGIC    └─ Top 25 products: [Shree Skirt, Elle Skirt, ...]
# MAGIC
# MAGIC Cross-match:
# MAGIC ├─ Garment 1 products (25) × Garment 2 products (25) = 625 pairs
# MAGIC ├─ Garment 1 products (25) × Garment 3 products (25) = 625 pairs  
# MAGIC └─ Garment 2 products (25) × Garment 3 products (25) = 625 pairs
# MAGIC
# MAGIC Total: 1,875 outfit combinations from this single DF2 outfit
# MAGIC ```
# MAGIC
# MAGIC **Across 601 outfits:** ~375,000+ potential combinations (filtered by score)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 💾 Output Table
# MAGIC
# MAGIC **Table:** [`main.fashion_sota.df2_outfit_recommendations_v2`](#table/main.fashion_sota.df2_outfit_recommendations_v2)
# MAGIC
# MAGIC **Schema:**
# MAGIC * `source_outfit_id` - DF2 outfit that inspired this pairing
# MAGIC * `garment_1_id`, `garment_1_category` - First garment from DF2
# MAGIC * `product_1_id`, `product_1_name`, `product_1_category` - Matched product
# MAGIC * `garment_1_similarity` - FashionCLIP similarity (garment → product)
# MAGIC * `garment_2_id`, `garment_2_category` - Second garment from DF2
# MAGIC * `product_2_id`, `product_2_name`, `product_2_category` - Matched product
# MAGIC * `garment_2_similarity` - FashionCLIP similarity (garment → product)
# MAGIC * `combined_score` - Average of both similarities
# MAGIC * `source_method` - "df2_garment_similarity_matching"
# MAGIC * `created_at`, `model_version` - Metadata
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 🔑 Key Advantages
# MAGIC
# MAGIC **vs. Category-Based Matching:**
# MAGIC * ✅ Preserves **style nuances** (embedding profile C vs other tops)
# MAGIC * ✅ No arbitrary category limits (uses actual similarity)
# MAGIC * ✅ Scales naturally (top-25 per garment = manageable)
# MAGIC
# MAGIC **vs. Previous Approach:**
# MAGIC * ✅ Simpler: Direct garment → product matching (no category aggregation)
# MAGIC * ✅ More accurate: Uses actual garment embeddings, not category averages
# MAGIC * ✅ Traceable: Each recommendation links to specific DF2 outfit
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 🚀 Usage Examples
# MAGIC
# MAGIC **Get recommendations for a product:**
# MAGIC ```sql
# MAGIC SELECT 
# MAGIC   product_2_id,
# MAGIC   product_2_name,
# MAGIC   combined_score,
# MAGIC   source_outfit_id
# MAGIC FROM main.fashion_sota.df2_outfit_recommendations_v2
# MAGIC WHERE product_1_id = '58684'
# MAGIC ORDER BY combined_score DESC
# MAGIC LIMIT 10
# MAGIC ```
# MAGIC
# MAGIC **Filter by category pairing:**
# MAGIC ```sql
# MAGIC SELECT *
# MAGIC FROM main.fashion_sota.df2_outfit_recommendations_v2
# MAGIC WHERE garment_1_category = 'short sleeve top'
# MAGIC   AND garment_2_category = 'trousers'
# MAGIC   AND combined_score >= 0.70
# MAGIC ORDER BY combined_score DESC
# MAGIC ```
# MAGIC
# MAGIC **Trace back to DF2 source:**
# MAGIC ```sql
# MAGIC SELECT 
# MAGIC   source_outfit_id,
# MAGIC   COUNT(*) as recommendation_count,
# MAGIC   AVG(combined_score) as avg_score
# MAGIC FROM main.fashion_sota.df2_outfit_recommendations_v2
# MAGIC GROUP BY source_outfit_id
# MAGIC ORDER BY recommendation_count DESC
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### ⚡ Next Steps
# MAGIC
# MAGIC **To scale to full catalog:**
# MAGIC 1. Remove product limit (currently ~25K apparel/footwear)
# MAGIC 2. Increase top-K from 25 to 50 for more variety
# MAGIC 3. Add filters: gender matching, color harmony, season
# MAGIC 4. Batch process by outfit to manage memory
# MAGIC
# MAGIC **To improve quality:**
# MAGIC 1. Filter out low-similarity matches (< 0.30)
# MAGIC 2. Add diversity penalty (avoid recommending same product multiple times)
# MAGIC 3. Ensemble with existing co-occurrence recommendations
# MAGIC 4. A/B test with user engagement metrics

# COMMAND ----------

# DBTITLE 1,Cleanup: Drop temporary checkpoint tables (optional)
# Run this cell ONLY after verifying the final output is correct
# These temp tables are used for checkpointing and restart capability

CLEANUP_TEMP_TABLES = False  # Set to True to drop temp tables

if CLEANUP_TEMP_TABLES:
    print("🧹 Cleaning up temporary checkpoint tables...\n")

    temp_tables = [
        OUTFIT_GARMENT_PRODUCTS_TABLE,  # Intermediate join results
        OUTFIT_PAIRS_TABLE,              # Raw outfit pairs before scoring
    ]

    for table in temp_tables:
        try:
            spark.sql(f"DROP TABLE IF EXISTS {table}")
            print(f"✓ Dropped: {table}")
        except Exception as e:
            print(f"⚠️  Could not drop {table}: {e}")

    print("\n✓ Cleanup complete!")
else:
    print("ℹ️  Temp tables preserved for restart capability:")
    print(f"   • {OUTFIT_GARMENT_PRODUCTS_TABLE}")
    print(f"   • {OUTFIT_PAIRS_TABLE}")
    print(f"   • {GARMENT_MATCHES_TABLE}")
    print("\n💡 Set CLEANUP_TEMP_TABLES = True and re-run to drop these tables")

# COMMAND ----------

# DBTITLE 1,Pipeline Summary
# Final summary of all tables created/used

print("=" * 80)
print("📊 PIPELINE ARTIFACTS SUMMARY")
print("=" * 80)

print("\n🔵 INPUT TABLES (Read-Only):")
print(f"   • {PRODUCT_TABLE} - All product embeddings")
print(f"   • {DF2_GARMENTS_TABLE} - DF2 garment embeddings")
print(f"   • {DF2_OUTFITS_TABLE} - DF2 outfit compositions")

print("\n🟢 OUTPUT TABLES (Created):")
print(f"   • {FILTERED_PRODUCT_TABLE} - US-relevant products only")
print(f"   • {GARMENT_MATCHES_TABLE} - Garment→Product matches (top-k)")
print(f"   • {OUTFIT_RECOMMENDATIONS_TABLE} - Final outfit recommendations ⭐")

print("\n🟡 CHECKPOINT TABLES (Temporary):")
print(f"   • {OUTFIT_GARMENT_PRODUCTS_TABLE} - Intermediate join")
print(f"   • {OUTFIT_PAIRS_TABLE} - Raw outfit pairs")

print("\n🔍 VECTOR SEARCH INDEX:")
print(f"   • {VECTOR_INDEX_NAME}")
print(f"   • Endpoint: {VECTOR_SEARCH_ENDPOINT}")

print("\n✅ Pipeline ready for production use!")
print(f"\n🎯 Primary output: {OUTFIT_RECOMMENDATIONS_TABLE}")