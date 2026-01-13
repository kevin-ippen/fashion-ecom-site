# Databricks notebook source
# MAGIC %md
# MAGIC # Create Filtered Products Table
# MAGIC
# MAGIC Creates a products table that only includes products with outfit pairings.
# MAGIC Then syncs to Lakebase for the app to use.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Check current data counts

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     COUNT(*) as total_products,
# MAGIC     COUNT(CASE WHEN complete_the_set_ids IS NOT NULL THEN 1 END) as with_outfit_column,
# MAGIC     COUNT(CASE WHEN complete_the_set_ids IS NOT NULL
# MAGIC                AND complete_the_set_ids != '[]'
# MAGIC                AND LENGTH(complete_the_set_ids) > 2 THEN 1 END) as with_actual_outfits
# MAGIC FROM main.fashion_sota.products_lakebase;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Create filtered table in Unity Catalog

# COMMAND ----------

# MAGIC %sql
# MAGIC DROP TABLE IF EXISTS main.fashion_sota.products_filtered;
# MAGIC
# MAGIC CREATE TABLE main.fashion_sota.products_filtered AS
# MAGIC SELECT *
# MAGIC FROM main.fashion_sota.products_lakebase
# MAGIC WHERE
# MAGIC     -- Category filters
# MAGIC     master_category IN ('Apparel', 'Accessories', 'Footwear')
# MAGIC     AND sub_category NOT IN (
# MAGIC         'Innerwear', 'Loungewear and Nightwear', 'Free Gifts', 'Fragrance', 'Skin Care',
# MAGIC         'Saree', 'Kurta', 'Kurtas', 'Dupatta', 'Churidar', 'Salwar', 'Lehenga Choli',
# MAGIC         'Kameez', 'Dhoti', 'Patiala', 'Kurta Sets', 'Sarees', 'Salwar and Dupatta', 'Lehenga'
# MAGIC     )
# MAGIC     AND article_type NOT IN (
# MAGIC         'Swimwear', 'Free Gifts', 'Perfume and Body Mist', 'Mens Grooming Kit',
# MAGIC         'Saree', 'Sarees', 'Kurta', 'Kurtas', 'Dupatta', 'Churidar', 'Salwar',
# MAGIC         'Lehenga Choli', 'Kameez', 'Dhoti', 'Patiala'
# MAGIC     )
# MAGIC     -- Outfit pairing filter
# MAGIC     AND complete_the_set_ids IS NOT NULL
# MAGIC     AND complete_the_set_ids != '[]'
# MAGIC     AND LENGTH(complete_the_set_ids) > 2;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) as filtered_count FROM main.fashion_sota.products_filtered;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Sync to Lakebase
# MAGIC
# MAGIC Option A: Replace the existing products_lakebase table
# MAGIC Option B: Create a new foreign table pointing to products_filtered

# COMMAND ----------

# Option A: Overwrite products_lakebase with filtered data
# This replaces the source table

spark.sql("""
    INSERT OVERWRITE main.fashion_sota.products_lakebase
    SELECT * FROM main.fashion_sota.products_filtered
""")

print("Done! products_lakebase now contains only filtered products.")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Verify
# MAGIC SELECT COUNT(*) as final_count FROM main.fashion_sota.products_lakebase;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Done!
# MAGIC
# MAGIC The products_lakebase table now only contains products with outfit pairings.
# MAGIC The app will automatically use this filtered data.
