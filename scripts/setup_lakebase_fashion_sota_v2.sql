-- ============================================================================
-- Fashion SOTA Lakebase Setup Script (Updated for UC Registration)
-- ============================================================================
-- Purpose: Sync Unity Catalog tables to Lakebase using proper registration
-- Reference: https://docs.databricks.com/aws/en/oltp/instances/register-uc
-- Schema: fashion_sota (Lakebase)
-- Source: main.fashion_sota (Unity Catalog)
-- ============================================================================

-- Prerequisites:
-- 1. Lakebase database instance must be running
-- 2. Unity Catalog must be registered with Lakebase
-- 3. Databricks workspace must have permissions to access UC

-- ============================================================================
-- Step 1: Register Unity Catalog with Lakebase (One-Time Setup)
-- ============================================================================
-- Run this in Databricks SQL or notebook
-- Reference: https://docs.databricks.com/aws/en/oltp/instances/register-uc

-- Check if UC is already registered
SHOW CATALOGS IN LAKEBASE;

-- If main catalog not registered, register it:
-- REGISTER UNITY CATALOG main WITH LAKEBASE DATABASE INSTANCE <your-instance-name>;


-- ============================================================================
-- Step 2: Create Target Schema in Lakebase
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS lakebase.fashion_sota
COMMENT 'Fashion SOTA serving layer synced from Unity Catalog';


-- ============================================================================
-- Step 3: Sync Products Table from product_embeddings
-- ============================================================================
-- Reference: https://docs.databricks.com/aws/en/oltp/instances/sync-data/sync-table

-- Why sync product_embeddings?
-- - Contains ALL product metadata denormalized (no joins needed)
-- - Has embeddings ready for future features
-- - Source: main.fashion_sota.product_embeddings (43,916 products)

-- Sync table with SNAPSHOT mode (full refresh on demand)
CREATE OR REPLACE TABLE lakebase.fashion_sota.products
AS SELECT
    product_id,
    product_display_name,
    master_category,
    sub_category,
    article_type,
    base_color,
    price,
    image_path,
    gender,
    season,
    usage,
    year,
    brand,
    -- Optionally include embeddings if needed for advanced features
    -- image_embedding,
    -- text_embedding,
    -- embedding as hybrid_embedding,
    -- We typically don't sync embeddings to Lakebase since Vector Search handles them
    current_timestamp() as synced_at
FROM main.fashion_sota.product_embeddings;

-- Add primary key constraint
ALTER TABLE lakebase.fashion_sota.products
ADD CONSTRAINT pk_products PRIMARY KEY (product_id);

-- Create indexes for common queries
CREATE INDEX idx_products_category ON lakebase.fashion_sota.products(master_category, sub_category);
CREATE INDEX idx_products_gender ON lakebase.fashion_sota.products(gender);
CREATE INDEX idx_products_price ON lakebase.fashion_sota.products(price);
CREATE INDEX idx_products_season ON lakebase.fashion_sota.products(season);
CREATE INDEX idx_products_brand ON lakebase.fashion_sota.products(brand);

-- Verify sync
SELECT
  'products' as table_name,
  COUNT(*) as row_count,
  COUNT(DISTINCT product_id) as unique_products,
  COUNT(DISTINCT master_category) as categories,
  COUNT(DISTINCT gender) as genders,
  COUNT(DISTINCT brand) as brands,
  MIN(price) as min_price,
  MAX(price) as max_price,
  MAX(synced_at) as last_synced
FROM lakebase.fashion_sota.products;
-- Expected: 43,916 rows


-- ============================================================================
-- Alternative: CONTINUOUS SYNC (Real-time Updates)
-- ============================================================================
-- For production, you may want continuous sync so Lakebase updates automatically
-- when Unity Catalog data changes

-- Uncomment this section for continuous sync:
/*
DROP TABLE IF EXISTS lakebase.fashion_sota.products;

CREATE TABLE lakebase.fashion_sota.products
USING LAKEBASE
OPTIONS (
  source_table 'main.fashion_sota.product_embeddings',
  sync_mode 'CONTINUOUS',
  primary_key 'product_id'
)
AS SELECT
    product_id,
    product_display_name,
    master_category,
    sub_category,
    article_type,
    base_color,
    price,
    image_path,
    gender,
    season,
    usage,
    year,
    brand
FROM main.fashion_sota.product_embeddings;
*/


-- ============================================================================
-- Step 4: Create Users Table
-- ============================================================================

-- Option A: Create new users table in Unity Catalog first
CREATE TABLE IF NOT EXISTS main.fashion_sota.users (
  user_id STRING PRIMARY KEY,
  email STRING NOT NULL UNIQUE,
  name STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  preferences MAP<STRING, STRING>,
  favorite_categories ARRAY<STRING>,
  favorite_brands ARRAY<STRING>
)
USING DELTA
LOCATION '/Volumes/main/fashion_sota/tables/users'
COMMENT 'User accounts for fashion e-commerce app';

-- Sync to Lakebase with continuous updates
CREATE OR REPLACE TABLE lakebase.fashion_sota.users
AS SELECT * FROM main.fashion_sota.users;

ALTER TABLE lakebase.fashion_sota.users
ADD CONSTRAINT pk_users PRIMARY KEY (user_id);

CREATE UNIQUE INDEX idx_users_email ON lakebase.fashion_sota.users(email);


-- Option B: Reuse existing users from fashion_demo
-- (Uncomment if you want to migrate existing users)
/*
CREATE OR REPLACE TABLE lakebase.fashion_sota.users
AS SELECT * FROM lakebase.fashion_demo.users;

ALTER TABLE lakebase.fashion_sota.users
ADD CONSTRAINT pk_users PRIMARY KEY (user_id);
*/


-- ============================================================================
-- Step 5: Create User Preferences Table
-- ============================================================================

-- Create in Unity Catalog first
CREATE TABLE IF NOT EXISTS main.fashion_sota.user_preferences (
  user_id STRING NOT NULL,
  preference_type STRING NOT NULL,  -- 'favorite', 'browsed', 'purchased', 'style_cluster'
  value STRING NOT NULL,  -- product_id, brand, category, or cluster_id
  score FLOAT,  -- Affinity score (0-1)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT pk_user_prefs PRIMARY KEY (user_id, preference_type, value)
)
USING DELTA
LOCATION '/Volumes/main/fashion_sota/tables/user_preferences'
COMMENT 'User style preferences and interaction history';

-- Sync to Lakebase
CREATE OR REPLACE TABLE lakebase.fashion_sota.user_preferences
AS SELECT * FROM main.fashion_sota.user_preferences;

ALTER TABLE lakebase.fashion_sota.user_preferences
ADD CONSTRAINT pk_user_prefs PRIMARY KEY (user_id, preference_type, value);

CREATE INDEX idx_user_prefs_user ON lakebase.fashion_sota.user_preferences(user_id);
CREATE INDEX idx_user_prefs_type ON lakebase.fashion_sota.user_preferences(preference_type);


-- ============================================================================
-- Step 6: Set Up Incremental Sync (Optional)
-- ============================================================================
-- For tables that change frequently (users, preferences), set up periodic sync

-- Create sync job (pseudo-code - adjust based on your Lakebase setup)
/*
CREATE SYNC JOB sync_users_to_lakebase
SOURCE main.fashion_sota.users
TARGET lakebase.fashion_sota.users
SCHEDULE CRON '*/5 * * * *'  -- Every 5 minutes
SYNC_MODE INCREMENTAL
PRIMARY_KEY user_id
UPDATED_COLUMN updated_at;

CREATE SYNC JOB sync_preferences_to_lakebase
SOURCE main.fashion_sota.user_preferences
TARGET lakebase.fashion_sota.user_preferences
SCHEDULE CRON '*/5 * * * *'
SYNC_MODE INCREMENTAL
PRIMARY_KEY (user_id, preference_type, value)
UPDATED_COLUMN updated_at;
*/


-- ============================================================================
-- Step 7: Verify All Tables
-- ============================================================================
SELECT
  table_schema,
  table_name,
  table_type
FROM information_schema.tables
WHERE table_schema = 'fashion_sota'
ORDER BY table_name;

-- Expected tables:
-- - fashion_sota.products (43,916 rows)
-- - fashion_sota.users (variable)
-- - fashion_sota.user_preferences (variable)


-- ============================================================================
-- Step 8: Grant Permissions (for App Service Principal)
-- ============================================================================
-- Replace {app_service_principal} with your Databricks App's service principal
-- Example: `databricks-app-12345-67890`

-- Grant read access to products
GRANT SELECT ON TABLE lakebase.fashion_sota.products TO `{app_service_principal}`;

-- Grant read/write access to users and preferences
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE lakebase.fashion_sota.users TO `{app_service_principal}`;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE lakebase.fashion_sota.user_preferences TO `{app_service_principal}`;

-- Also grant schema usage
GRANT USAGE ON SCHEMA lakebase.fashion_sota TO `{app_service_principal}`;


-- ============================================================================
-- Step 9: Create Helper Views (Optional)
-- ============================================================================

-- View 1: Products with computed fields
CREATE OR REPLACE VIEW lakebase.fashion_sota.products_enriched AS
SELECT
  *,
  CONCAT(master_category, ' - ', sub_category) as full_category,
  CASE
    WHEN price < 500 THEN 'Budget'
    WHEN price < 2000 THEN 'Mid-Range'
    ELSE 'Premium'
  END as price_tier,
  CONCAT('https://your-workspace.cloud.databricks.com/ajax-api/2.0/fs/files/Volumes/main/fashion_sota/product_images/', product_id, '.jpg') as image_url
FROM lakebase.fashion_sota.products;

-- View 2: User favorites summary
CREATE OR REPLACE VIEW lakebase.fashion_sota.user_favorites_summary AS
SELECT
  user_id,
  COUNT(DISTINCT value) as total_favorites,
  COUNT(DISTINCT CASE WHEN preference_type = 'favorite' THEN value END) as favorited_products,
  ARRAY_AGG(DISTINCT value) FILTER (WHERE preference_type = 'style_cluster') as preferred_styles
FROM lakebase.fashion_sota.user_preferences
GROUP BY user_id;


-- ============================================================================
-- Validation Queries
-- ============================================================================

-- 1. Check product data quality
SELECT
  master_category,
  gender,
  COUNT(*) as product_count,
  ROUND(AVG(price), 2) as avg_price,
  MIN(price) as min_price,
  MAX(price) as max_price
FROM lakebase.fashion_sota.products
GROUP BY master_category, gender
ORDER BY master_category, gender;

-- 2. Sample products with all fields
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
  brand,
  image_path
FROM lakebase.fashion_sota.products
ORDER BY RANDOM()
LIMIT 10;

-- 3. Check for missing critical fields
SELECT
  COUNT(*) as total,
  COUNT(product_display_name) as has_name,
  COUNT(image_path) as has_image,
  COUNT(price) as has_price,
  COUNT(master_category) as has_category,
  COUNT(brand) as has_brand,
  -- Calculate completeness percentage
  ROUND(100.0 * COUNT(product_display_name) / COUNT(*), 2) as name_completeness,
  ROUND(100.0 * COUNT(image_path) / COUNT(*), 2) as image_completeness,
  ROUND(100.0 * COUNT(brand) / COUNT(*), 2) as brand_completeness
FROM lakebase.fashion_sota.products;

-- All should be 100% (no nulls in critical fields)

-- 4. Check price distribution
SELECT
  CASE
    WHEN price < 500 THEN '< 500'
    WHEN price < 1000 THEN '500-1000'
    WHEN price < 2000 THEN '1000-2000'
    WHEN price < 5000 THEN '2000-5000'
    ELSE '> 5000'
  END as price_range,
  COUNT(*) as product_count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM lakebase.fashion_sota.products), 2) as percentage
FROM lakebase.fashion_sota.products
GROUP BY price_range
ORDER BY MIN(price);

-- 5. Top brands by product count
SELECT
  brand,
  COUNT(*) as product_count,
  AVG(price) as avg_price
FROM lakebase.fashion_sota.products
WHERE brand IS NOT NULL
GROUP BY brand
ORDER BY product_count DESC
LIMIT 20;


-- ============================================================================
-- Troubleshooting Queries
-- ============================================================================

-- Check table sizes
SELECT
  table_name,
  pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) as size
FROM information_schema.tables
WHERE table_schema = 'fashion_sota'
  AND table_type = 'BASE TABLE';

-- Check last sync time (if using continuous sync)
SELECT
  MAX(synced_at) as last_sync,
  COUNT(*) as total_rows,
  COUNT(DISTINCT product_id) as unique_products
FROM lakebase.fashion_sota.products;


-- ============================================================================
-- Refresh/Resync Commands
-- ============================================================================

-- If you need to refresh the products table from Unity Catalog:
TRUNCATE TABLE lakebase.fashion_sota.products;

INSERT INTO lakebase.fashion_sota.products
SELECT
    product_id,
    product_display_name,
    master_category,
    sub_category,
    article_type,
    base_color,
    price,
    image_path,
    gender,
    season,
    usage,
    year,
    brand,
    current_timestamp() as synced_at
FROM main.fashion_sota.product_embeddings;

-- Refresh users and preferences similarly if needed


-- ============================================================================
-- Migration Complete!
-- ============================================================================
-- Next steps:
-- 1. Update core/config.py to point to fashion_sota schema
-- 2. Test app endpoints with new schema
-- 3. Verify Vector Search works with product_embeddings_index
-- 4. Update app.yaml to grant permissions to fashion_sota volume
-- 5. Deploy to Databricks Apps
--
-- Expected Row Counts:
-- - products: 43,916
-- - users: variable (depends on existing users)
-- - user_preferences: variable
