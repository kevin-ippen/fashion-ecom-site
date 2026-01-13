# Databricks notebook source
# MAGIC %md
# MAGIC # Batch Compute Product Recommendations
# MAGIC
# MAGIC This notebook pre-computes recommendations for all products:
# MAGIC 1. **Similar Products** - Visually similar items via Vector Search
# MAGIC 2. **Complete the Set** - Outfit pairings from lookbook data
# MAGIC
# MAGIC Results are written to Lakebase `products_lakebase` table for ultra-fast lookups.
# MAGIC
# MAGIC **Performance Impact**:
# MAGIC - Before: ~500ms per product page (real-time Vector Search + SQL)
# MAGIC - After: ~5ms per product page (simple Lakebase JOIN)
# MAGIC
# MAGIC **Recommended Schedule**: Daily or weekly via Databricks Jobs

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

# Configuration
CATALOG = "main"
SCHEMA = "fashion_sota"

# Source tables
PRODUCT_EMBEDDINGS_TABLE = f"{CATALOG}.{SCHEMA}.product_embeddings_us_relevant"
LOOKBOOK_TABLE = f"{CATALOG}.{SCHEMA}.outfit_recommendations_from_lookbook"

# Vector Search
VS_ENDPOINT = "one-env-shared-endpoint-15"
VS_INDEX = f"{CATALOG}.{SCHEMA}.product_embeddings_us_relevant_index"

# Lakebase connection (use environment variables in production)
LAKEBASE_HOST = dbutils.secrets.get(scope="lakebase", key="host")  # Or use env var
LAKEBASE_DATABASE = "databricks_postgres"
LAKEBASE_SCHEMA = "fashion_sota"
LAKEBASE_TABLE = "products_lakebase"

# Recommendation limits
SIMILAR_PRODUCTS_LIMIT = 10  # Store top 10 similar products per item
COMPLETE_SET_LIMIT = 8       # Store top 8 outfit pairings per item

# Batch processing
BATCH_SIZE = 1000            # Products per batch
CHECKPOINT_EVERY = 5         # Checkpoint every N batches

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

import json
import numpy as np
from typing import List, Dict, Any, Optional
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, IntegerType, StringType
from databricks.vector_search.client import VectorSearchClient

# Initialize Vector Search client
vs_client = VectorSearchClient()
vs_index = vs_client.get_index(index_name=VS_INDEX)

print(f"Connected to Vector Search index: {VS_INDEX}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Get All Products

# COMMAND ----------

# Load all products with embeddings
products_df = spark.table(PRODUCT_EMBEDDINGS_TABLE).select(
    "product_id",
    "product_display_name",
    "master_category",
    "sub_category",
    "gender",
    "base_color",
    "embedding"
)

total_products = products_df.count()
print(f"Total products to process: {total_products:,}")

# Convert to list for batch processing
products_list = products_df.collect()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Compute Similar Products (Vector Search)

# COMMAND ----------

def get_similar_products_batch(
    products_batch: List[Dict],
    limit: int = 10
) -> Dict[int, List[int]]:
    """
    Get similar products for a batch of products using Vector Search.

    STRICT FILTERING for "You May Also Like":
    - Same master_category (Apparel with Apparel)
    - Same sub_category (Shorts with Shorts, Pants with Pants)
    - Same gender (or Unisex)
    - No duplicates
    - Color diversity

    Returns dict mapping product_id -> list of similar product_ids
    """
    results = {}

    for row in products_batch:
        pid = row["product_id"]
        embedding = row["embedding"]
        source_category = row["master_category"]
        source_sub_category = row["sub_category"]
        source_gender = row["gender"]

        try:
            # Normalize embedding
            emb_array = np.array(embedding, dtype=np.float32)
            norm = np.linalg.norm(emb_array)
            if norm > 0:
                emb_array = emb_array / norm

            # Search for more candidates to allow for strict filtering
            search_limit = limit * 10  # More candidates for stricter filtering
            search_results = vs_index.similarity_search(
                query_vector=emb_array.tolist(),
                columns=["product_id", "master_category", "sub_category", "gender", "base_color"],
                num_results=search_limit + 1  # +1 to exclude self
            )

            # Apply strict filtering:
            # 1. Exclude self and duplicates
            # 2. Same master_category
            # 3. Same sub_category (shorts with shorts, pants with pants)
            # 4. Same gender (or Unisex)
            # 5. Diversify by color
            similar_ids = []
            seen_ids = {pid}
            color_counts = {}
            max_per_color = 3  # Limit same-color items for diversity

            if "result" in search_results and "data_array" in search_results["result"]:
                for result_row in search_results["result"]["data_array"]:
                    similar_pid = int(result_row[0])
                    similar_category = result_row[1] if len(result_row) > 1 else None
                    similar_sub_category = result_row[2] if len(result_row) > 2 else None
                    similar_gender = result_row[3] if len(result_row) > 3 else None
                    similar_color = result_row[4] if len(result_row) > 4 else "Unknown"

                    # Skip self and duplicates
                    if similar_pid in seen_ids:
                        continue
                    seen_ids.add(similar_pid)

                    # SAME CATEGORY: Only include products from same master_category
                    if similar_category != source_category:
                        continue

                    # SAME SUB_CATEGORY: shorts with shorts, pants with pants
                    if similar_sub_category != source_sub_category:
                        continue

                    # SAME GENDER: Only same gender or Unisex
                    if similar_gender != source_gender and similar_gender != "Unisex" and source_gender != "Unisex":
                        continue

                    # Color diversity: limit items of same color
                    color_counts[similar_color] = color_counts.get(similar_color, 0) + 1
                    if color_counts[similar_color] > max_per_color:
                        continue

                    similar_ids.append(similar_pid)
                    if len(similar_ids) >= limit:
                        break

            results[pid] = similar_ids

        except Exception as e:
            print(f"Error processing product {pid}: {e}")
            results[pid] = []

    return results


# Process in batches
similar_products_map = {}
batch_count = 0

for i in range(0, len(products_list), BATCH_SIZE):
    batch = products_list[i:i + BATCH_SIZE]

    # Convert to list of dicts for the updated function
    batch_dicts = [row.asDict() for row in batch]

    batch_results = get_similar_products_batch(batch_dicts, SIMILAR_PRODUCTS_LIMIT)
    similar_products_map.update(batch_results)

    batch_count += 1
    if batch_count % CHECKPOINT_EVERY == 0:
        print(f"Processed {len(similar_products_map):,} / {total_products:,} products for similar products")

print(f"✅ Computed similar products for {len(similar_products_map):,} products")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Compute Complete-the-Set (Outfit Pairings)

# COMMAND ----------

# ============================================================================
# Outfit Compatibility Rules (deterministic, no 2 bottoms together, etc.)
# ============================================================================

def categorize_product(master_category: str, sub_category: str, article_type: str) -> str:
    """
    Categorize product for outfit compatibility checking.

    MUST be kept in sync with:
    - services/outfit_compatibility_service.py
    - frontend/src/lib/outfitRules.ts

    Returns one of: tops, bottoms, dress, outerwear, footwear, accessories,
                   innerwear, sleepwear, swimwear, unknown
    """
    OUTERWEAR_TYPES = {
        "Jackets", "Blazers", "Sweaters", "Sweatshirts", "Rain Jacket",
        "Nehru Jackets", "Shrug", "Coats", "Cardigans"
    }
    SWIMWEAR_TYPES = {"Swimwear"}

    # Check isolated categories first (highest priority)
    if sub_category == "Innerwear":
        return "innerwear"
    if sub_category == "Loungewear and Nightwear":
        return "sleepwear"
    if article_type in SWIMWEAR_TYPES:
        return "swimwear"

    # Check structural categories
    if master_category == "Footwear":
        return "footwear"
    if master_category == "Accessories":
        return "accessories"

    # Apparel subcategories
    if sub_category in ("Dress", "Saree"):
        # Sarees and dresses are complete outfits - shouldn't pair with tops/bottoms
        return "dress"
    if sub_category == "Bottomwear":
        return "bottoms"
    if sub_category == "Socks" and master_category == "Apparel":
        # Baby booties/socks under Apparel are accessories
        return "accessories"
    if sub_category == "Apparel Set":
        # Clothing sets are complete outfits - treat like dress
        return "dress"

    # Outerwear vs regular tops
    if sub_category == "Topwear":
        if article_type in OUTERWEAR_TYPES:
            return "outerwear"
        return "tops"

    # Default: unknown apparel items treated as accessories
    if master_category == "Apparel":
        return "accessories"

    return "unknown"


def is_outfit_compatible(
    source_category: str, source_gender: str,
    target_category: str, target_gender: str
) -> bool:
    """
    Check if two products are compatible for an outfit pairing.

    Core rules:
    - NO duplicate categories (2 tops, 2 bottoms, 2 footwear)
    - NO dress with tops/bottoms
    - NO innerwear/sleepwear/swimwear with regular apparel
    - Gender must be compatible
    """
    # NEVER: Isolated categories
    isolated = {"innerwear", "sleepwear", "swimwear"}
    if source_category in isolated or target_category in isolated:
        return False

    # NEVER: Same category duplicates
    if source_category == target_category:
        return False

    # NEVER: Dress with tops or bottoms
    if source_category == "dress" and target_category in {"tops", "bottoms"}:
        return False
    if target_category == "dress" and source_category in {"tops", "bottoms"}:
        return False

    # NEVER: Gender incompatibility
    adult_genders = {"Men", "Women", "Unisex"}
    kids_genders = {"Boys", "Girls"}
    source_adult = source_gender in adult_genders
    source_kids = source_gender in kids_genders
    target_adult = target_gender in adult_genders
    target_kids = target_gender in kids_genders

    # No adult with kids mixing
    if (source_adult and target_kids) or (source_kids and target_adult):
        return False

    # Unisex is compatible with any adult
    if source_gender == "Unisex" or target_gender == "Unisex":
        return True

    # Same gender is fine
    if source_gender == target_gender:
        return True

    # Men and Women don't mix (unless Unisex)
    if source_gender in {"Men", "Women"} and target_gender in {"Men", "Women"}:
        return False

    return True


# Load lookbook outfit pairings
lookbook_df = spark.table(LOOKBOOK_TABLE)

# Get all products for metadata lookup
products_metadata_df = spark.table(PRODUCT_EMBEDDINGS_TABLE).select(
    "product_id", "master_category", "sub_category", "article_type", "gender"
)
products_metadata = {
    row["product_id"]: row.asDict()
    for row in products_metadata_df.collect()
}

# Get outfit pairings for each product
outfit_pairs_1 = lookbook_df.select(
    F.col("product_1_id").alias("source_product_id"),
    F.col("product_2_id").alias("paired_product_id"),
    F.col("co_occurrence_count")
)

outfit_pairs_2 = lookbook_df.select(
    F.col("product_2_id").alias("source_product_id"),
    F.col("product_1_id").alias("paired_product_id"),
    F.col("co_occurrence_count")
)

# Union and aggregate
all_pairs = outfit_pairs_1.union(outfit_pairs_2)

# Rank pairings by co-occurrence - get more than needed for filtering
from pyspark.sql.window import Window

window = Window.partitionBy("source_product_id").orderBy(F.desc("co_occurrence_count"))

# Get top 30 pairings per product (we'll filter down to COMPLETE_SET_LIMIT after compatibility check)
top_pairings_raw = all_pairs \
    .withColumn("rank", F.row_number().over(window)) \
    .filter(F.col("rank") <= 30) \
    .select("source_product_id", "paired_product_id", "co_occurrence_count")

# Convert to dict and apply compatibility filtering
raw_pairings = top_pairings_raw.collect()

# Group by source product
from collections import defaultdict
source_to_candidates = defaultdict(list)
for row in raw_pairings:
    source_to_candidates[row["source_product_id"]].append({
        "paired_id": row["paired_product_id"],
        "co_occurrence": row["co_occurrence_count"]
    })

# Apply outfit compatibility filtering
complete_set_map = {}
filtered_count = 0
total_candidates = 0

for source_id, candidates in source_to_candidates.items():
    source_meta = products_metadata.get(source_id, {})
    source_cat = categorize_product(
        source_meta.get("master_category", ""),
        source_meta.get("sub_category", ""),
        source_meta.get("article_type", "")
    )
    source_gender = source_meta.get("gender", "")

    compatible_ids = []
    category_counts = {source_cat: 1}  # Track category counts for diversity

    for candidate in candidates:
        paired_id = candidate["paired_id"]
        paired_meta = products_metadata.get(paired_id, {})
        paired_cat = categorize_product(
            paired_meta.get("master_category", ""),
            paired_meta.get("sub_category", ""),
            paired_meta.get("article_type", "")
        )
        paired_gender = paired_meta.get("gender", "")

        total_candidates += 1

        # Apply outfit compatibility rules
        if not is_outfit_compatible(source_cat, source_gender, paired_cat, paired_gender):
            filtered_count += 1
            continue

        # Ensure category diversity (max 2 from same category)
        current_count = category_counts.get(paired_cat, 0)
        if current_count >= 2:
            continue

        category_counts[paired_cat] = current_count + 1
        compatible_ids.append(paired_id)

        if len(compatible_ids) >= COMPLETE_SET_LIMIT:
            break

    complete_set_map[source_id] = compatible_ids

print(f"✅ Computed complete-the-set for {len(complete_set_map):,} products")
print(f"   Filtered {filtered_count:,} / {total_candidates:,} incompatible pairings ({100*filtered_count/max(total_candidates,1):.1f}%)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Write Results to Lakebase

# COMMAND ----------

import psycopg2
from psycopg2.extras import execute_batch

def get_lakebase_connection():
    """Get connection to Lakebase PostgreSQL"""
    # Get OAuth token for authentication
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    token = w.config.oauth_token().access_token

    return psycopg2.connect(
        host=LAKEBASE_HOST,
        database=LAKEBASE_DATABASE,
        user=spark.conf.get("spark.databricks.userContext.email", ""),  # Current user
        password=token,
        sslmode="require"
    )


def update_recommendations_batch(
    conn,
    product_ids: List[int],
    similar_map: Dict[int, List[int]],
    complete_map: Dict[int, List[int]]
):
    """Update recommendations for a batch of products"""
    cursor = conn.cursor()

    update_sql = f"""
        UPDATE {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}
        SET
            similar_product_ids = %s::jsonb,
            complete_the_set_ids = %s::jsonb,
            recommendations_updated_at = CURRENT_TIMESTAMP
        WHERE product_id = %s
    """

    batch_data = []
    for pid in product_ids:
        similar_ids = similar_map.get(pid, [])
        complete_ids = complete_map.get(pid, [])
        batch_data.append((
            json.dumps(similar_ids),
            json.dumps(complete_ids),
            pid
        ))

    execute_batch(cursor, update_sql, batch_data, page_size=100)
    conn.commit()
    cursor.close()


# Write to Lakebase in batches
conn = get_lakebase_connection()
all_product_ids = list(set(list(similar_products_map.keys()) + list(complete_set_map.keys())))

batch_count = 0
for i in range(0, len(all_product_ids), BATCH_SIZE):
    batch_ids = all_product_ids[i:i + BATCH_SIZE]

    update_recommendations_batch(conn, batch_ids, similar_products_map, complete_set_map)

    batch_count += 1
    if batch_count % CHECKPOINT_EVERY == 0:
        print(f"Written {i + len(batch_ids):,} / {len(all_product_ids):,} products to Lakebase")

conn.close()
print(f"✅ Written recommendations for {len(all_product_ids):,} products to Lakebase")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Verify Results

# COMMAND ----------

# Verify in Lakebase
verification_query = f"""
SELECT
    COUNT(*) as total_products,
    COUNT(*) FILTER (WHERE similar_product_ids != '[]'::jsonb) as has_similar,
    COUNT(*) FILTER (WHERE complete_the_set_ids != '[]'::jsonb) as has_complete_set,
    COUNT(*) FILTER (WHERE recommendations_updated_at IS NOT NULL) as has_timestamp,
    ROUND(100.0 * COUNT(*) FILTER (WHERE similar_product_ids != '[]'::jsonb) / COUNT(*), 2) as similar_coverage_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE complete_the_set_ids != '[]'::jsonb) / COUNT(*), 2) as complete_set_coverage_pct,
    MAX(recommendations_updated_at) as last_updated
FROM {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}
"""

# Execute via Spark JDBC
jdbc_url = f"jdbc:postgresql://{LAKEBASE_HOST}:5432/{LAKEBASE_DATABASE}"

verification_df = spark.read \
    .format("jdbc") \
    .option("url", jdbc_url) \
    .option("query", verification_query) \
    .option("user", spark.conf.get("spark.databricks.userContext.email", "")) \
    .option("password", WorkspaceClient().config.oauth_token().access_token) \
    .load()

display(verification_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC **Recommendation Pipeline Complete!**
# MAGIC
# MAGIC - Similar Products: Uses Vector Search to find visually similar items
# MAGIC - Complete the Set: Uses lookbook co-occurrence data for outfit pairings
# MAGIC - Results stored in Lakebase for ~5ms product page loads
# MAGIC
# MAGIC **Next Steps**:
# MAGIC 1. Schedule this notebook as a daily/weekly Databricks Job
# MAGIC 2. Monitor coverage percentages over time
# MAGIC 3. Add alerting if coverage drops below threshold
