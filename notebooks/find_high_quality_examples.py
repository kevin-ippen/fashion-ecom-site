# Databricks notebook source
# MAGIC %md
# MAGIC # Find High-Quality Example Products
# MAGIC
# MAGIC Find products with good matches for both:
# MAGIC 1. "You May Also Like" - same sub_category, same gender, diverse colors
# MAGIC 2. "Complete the Look" - complementary categories from lookbook

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Find products with many same-subcategory matches

# COMMAND ----------

# Count products by sub_category and gender to find well-populated segments
category_counts = spark.sql("""
SELECT
    master_category,
    sub_category,
    gender,
    COUNT(*) as product_count,
    COUNT(DISTINCT base_color) as color_variety
FROM main.fashion_sota.product_embeddings_us_relevant
GROUP BY master_category, sub_category, gender
HAVING COUNT(*) >= 20  -- At least 20 products for good similarity matches
ORDER BY product_count DESC
""")

display(category_counts)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Find products with lookbook pairings

# COMMAND ----------

# Find products that appear in lookbook outfit pairings
products_with_pairings = spark.sql("""
WITH pairing_counts AS (
    SELECT
        product_1_id as product_id,
        COUNT(*) as pairing_count
    FROM main.fashion_sota.outfit_recommendations_from_lookbook
    GROUP BY product_1_id

    UNION ALL

    SELECT
        product_2_id as product_id,
        COUNT(*) as pairing_count
    FROM main.fashion_sota.outfit_recommendations_from_lookbook
    GROUP BY product_2_id
)
SELECT
    product_id,
    SUM(pairing_count) as total_pairings
FROM pairing_counts
GROUP BY product_id
HAVING SUM(pairing_count) >= 3  -- At least 3 outfit pairings
ORDER BY total_pairings DESC
LIMIT 100
""")

display(products_with_pairings)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Find best example products (high quality for both sections)

# COMMAND ----------

# Join to get products with both good similarity candidates AND lookbook pairings
best_examples = spark.sql("""
WITH pairing_counts AS (
    SELECT
        product_1_id as product_id,
        COUNT(*) as pairing_count
    FROM main.fashion_sota.outfit_recommendations_from_lookbook
    GROUP BY product_1_id

    UNION ALL

    SELECT
        product_2_id as product_id,
        COUNT(*) as pairing_count
    FROM main.fashion_sota.outfit_recommendations_from_lookbook
    GROUP BY product_2_id
),
products_with_pairings AS (
    SELECT
        product_id,
        SUM(pairing_count) as total_pairings
    FROM pairing_counts
    GROUP BY product_id
),
category_populations AS (
    SELECT
        p.product_id,
        p.product_display_name,
        p.master_category,
        p.sub_category,
        p.gender,
        p.base_color,
        p.article_type,
        -- Count how many other products share same sub_category + gender
        COUNT(*) OVER (PARTITION BY p.sub_category, p.gender) as same_segment_count,
        -- Count color variety in segment
        COUNT(DISTINCT p.base_color) OVER (PARTITION BY p.sub_category, p.gender) as segment_color_variety
    FROM main.fashion_sota.product_embeddings_us_relevant p
)
SELECT
    cp.product_id,
    cp.product_display_name,
    cp.master_category,
    cp.sub_category,
    cp.article_type,
    cp.gender,
    cp.base_color,
    cp.same_segment_count,
    cp.segment_color_variety,
    COALESCE(pp.total_pairings, 0) as lookbook_pairings
FROM category_populations cp
LEFT JOIN products_with_pairings pp ON cp.product_id = pp.product_id
WHERE
    cp.same_segment_count >= 20  -- Good similarity candidate pool
    AND COALESCE(pp.total_pairings, 0) >= 3  -- Good outfit pairings
ORDER BY
    pp.total_pairings DESC,
    cp.same_segment_count DESC
LIMIT 50
""")

display(best_examples)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Get specific product IDs by category

# COMMAND ----------

# Get best examples for each major category type
print("=== BEST EXAMPLES BY CATEGORY ===\n")

# Women's Tops (Topwear)
womens_tops = spark.sql("""
WITH pairing_counts AS (
    SELECT product_1_id as product_id, COUNT(*) as cnt FROM main.fashion_sota.outfit_recommendations_from_lookbook GROUP BY product_1_id
    UNION ALL
    SELECT product_2_id as product_id, COUNT(*) as cnt FROM main.fashion_sota.outfit_recommendations_from_lookbook GROUP BY product_2_id
),
pairings AS (SELECT product_id, SUM(cnt) as total FROM pairing_counts GROUP BY product_id)
SELECT p.product_id, p.product_display_name, p.base_color, COALESCE(pr.total, 0) as pairings
FROM main.fashion_sota.product_embeddings_us_relevant p
LEFT JOIN pairings pr ON p.product_id = pr.product_id
WHERE p.sub_category = 'Topwear' AND p.gender = 'Women'
ORDER BY pr.total DESC NULLS LAST
LIMIT 5
""").collect()

print("Women's Tops:")
for row in womens_tops:
    print(f"  {row.product_id}: {row.product_display_name} ({row.base_color}) - {row.pairings} pairings")

# Men's Shirts
mens_shirts = spark.sql("""
WITH pairing_counts AS (
    SELECT product_1_id as product_id, COUNT(*) as cnt FROM main.fashion_sota.outfit_recommendations_from_lookbook GROUP BY product_1_id
    UNION ALL
    SELECT product_2_id as product_id, COUNT(*) as cnt FROM main.fashion_sota.outfit_recommendations_from_lookbook GROUP BY product_2_id
),
pairings AS (SELECT product_id, SUM(cnt) as total FROM pairing_counts GROUP BY product_id)
SELECT p.product_id, p.product_display_name, p.base_color, COALESCE(pr.total, 0) as pairings
FROM main.fashion_sota.product_embeddings_us_relevant p
LEFT JOIN pairings pr ON p.product_id = pr.product_id
WHERE p.sub_category = 'Topwear' AND p.gender = 'Men'
ORDER BY pr.total DESC NULLS LAST
LIMIT 5
""").collect()

print("\nMen's Tops:")
for row in mens_shirts:
    print(f"  {row.product_id}: {row.product_display_name} ({row.base_color}) - {row.pairings} pairings")

# Women's Dresses
womens_dresses = spark.sql("""
WITH pairing_counts AS (
    SELECT product_1_id as product_id, COUNT(*) as cnt FROM main.fashion_sota.outfit_recommendations_from_lookbook GROUP BY product_1_id
    UNION ALL
    SELECT product_2_id as product_id, COUNT(*) as cnt FROM main.fashion_sota.outfit_recommendations_from_lookbook GROUP BY product_2_id
),
pairings AS (SELECT product_id, SUM(cnt) as total FROM pairing_counts GROUP BY product_id)
SELECT p.product_id, p.product_display_name, p.base_color, COALESCE(pr.total, 0) as pairings
FROM main.fashion_sota.product_embeddings_us_relevant p
LEFT JOIN pairings pr ON p.product_id = pr.product_id
WHERE p.sub_category = 'Dress' AND p.gender = 'Women'
ORDER BY pr.total DESC NULLS LAST
LIMIT 5
""").collect()

print("\nWomen's Dresses:")
for row in womens_dresses:
    print(f"  {row.product_id}: {row.product_display_name} ({row.base_color}) - {row.pairings} pairings")

# Men's Jeans/Pants
mens_bottoms = spark.sql("""
WITH pairing_counts AS (
    SELECT product_1_id as product_id, COUNT(*) as cnt FROM main.fashion_sota.outfit_recommendations_from_lookbook GROUP BY product_1_id
    UNION ALL
    SELECT product_2_id as product_id, COUNT(*) as cnt FROM main.fashion_sota.outfit_recommendations_from_lookbook GROUP BY product_2_id
),
pairings AS (SELECT product_id, SUM(cnt) as total FROM pairing_counts GROUP BY product_id)
SELECT p.product_id, p.product_display_name, p.base_color, COALESCE(pr.total, 0) as pairings
FROM main.fashion_sota.product_embeddings_us_relevant p
LEFT JOIN pairings pr ON p.product_id = pr.product_id
WHERE p.sub_category = 'Bottomwear' AND p.gender = 'Men'
ORDER BY pr.total DESC NULLS LAST
LIMIT 5
""").collect()

print("\nMen's Bottomwear:")
for row in mens_bottoms:
    print(f"  {row.product_id}: {row.product_display_name} ({row.base_color}) - {row.pairings} pairings")

# Footwear
footwear = spark.sql("""
WITH pairing_counts AS (
    SELECT product_1_id as product_id, COUNT(*) as cnt FROM main.fashion_sota.outfit_recommendations_from_lookbook GROUP BY product_1_id
    UNION ALL
    SELECT product_2_id as product_id, COUNT(*) as cnt FROM main.fashion_sota.outfit_recommendations_from_lookbook GROUP BY product_2_id
),
pairings AS (SELECT product_id, SUM(cnt) as total FROM pairing_counts GROUP BY product_id)
SELECT p.product_id, p.product_display_name, p.gender, p.base_color, COALESCE(pr.total, 0) as pairings
FROM main.fashion_sota.product_embeddings_us_relevant p
LEFT JOIN pairings pr ON p.product_id = pr.product_id
WHERE p.master_category = 'Footwear'
ORDER BY pr.total DESC NULLS LAST
LIMIT 5
""").collect()

print("\nFootwear:")
for row in footwear:
    print(f"  {row.product_id}: {row.product_display_name} ({row.gender}, {row.base_color}) - {row.pairings} pairings")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC Run this notebook to get product IDs with:
# MAGIC - High similarity match potential (many products in same sub_category + gender)
# MAGIC - High complete-the-look potential (many lookbook outfit pairings)
