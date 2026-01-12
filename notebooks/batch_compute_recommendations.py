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
    product_ids: List[int],
    embeddings: List[List[float]],
    limit: int = 10
) -> Dict[int, List[int]]:
    """
    Get similar products for a batch of products using Vector Search.

    Returns dict mapping product_id -> list of similar product_ids
    """
    results = {}

    for pid, embedding in zip(product_ids, embeddings):
        try:
            # Normalize embedding
            emb_array = np.array(embedding, dtype=np.float32)
            norm = np.linalg.norm(emb_array)
            if norm > 0:
                emb_array = emb_array / norm

            # Search for similar products
            search_results = vs_index.similarity_search(
                query_vector=emb_array.tolist(),
                columns=["product_id"],
                num_results=limit + 1  # +1 to exclude self
            )

            # Extract product IDs (exclude self)
            similar_ids = []
            if "result" in search_results and "data_array" in search_results["result"]:
                for row in search_results["result"]["data_array"]:
                    similar_pid = int(row[0])
                    if similar_pid != pid:
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

    product_ids = [row["product_id"] for row in batch]
    embeddings = [row["embedding"] for row in batch]

    batch_results = get_similar_products_batch(product_ids, embeddings, SIMILAR_PRODUCTS_LIMIT)
    similar_products_map.update(batch_results)

    batch_count += 1
    if batch_count % CHECKPOINT_EVERY == 0:
        print(f"Processed {len(similar_products_map):,} / {total_products:,} products for similar products")

print(f"✅ Computed similar products for {len(similar_products_map):,} products")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Compute Complete-the-Set (Outfit Pairings)

# COMMAND ----------

# Load lookbook outfit pairings
lookbook_df = spark.table(LOOKBOOK_TABLE)

# Get outfit pairings for each product
# Query both directions (product_1_id and product_2_id)
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

# Rank pairings by co-occurrence and take top N per product
from pyspark.sql.window import Window

window = Window.partitionBy("source_product_id").orderBy(F.desc("co_occurrence_count"))

top_pairings = all_pairs \
    .withColumn("rank", F.row_number().over(window)) \
    .filter(F.col("rank") <= COMPLETE_SET_LIMIT) \
    .groupBy("source_product_id") \
    .agg(F.collect_list("paired_product_id").alias("complete_set_ids"))

# Convert to dict
complete_set_map = {
    row["source_product_id"]: [int(x) for x in row["complete_set_ids"]]
    for row in top_pairings.collect()
}

print(f"✅ Computed complete-the-set for {len(complete_set_map):,} products")

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
