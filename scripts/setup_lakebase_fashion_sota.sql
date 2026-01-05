-- ============================================================================
-- Fashion SOTA Lakebase Setup Script
-- ============================================================================
-- Purpose: Create Lakebase foreign tables synced with Unity Catalog tables
-- Schema: lakebase.fashion_sota
-- Source: main.fashion_sota (Unity Catalog)
-- ============================================================================

-- Step 1: Create Lakebase schema
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS lakebase.fashion_sota
COMMENT 'Fashion SOTA serving layer synced from Unity Catalog';


-- Step 2: Sync Products Table (from product_embeddings)
-- ============================================================================
-- Why product_embeddings? It has ALL metadata denormalized (no joins needed)
-- Source: main.fashion_sota.product_embeddings (43,916 products)
-- Contains: product metadata + image_embedding + text_embedding + hybrid embedding

DROP FOREIGN TABLE IF EXISTS lakebase.fashion_sota.products;

CREATE FOREIGN TABLE lakebase.fashion_sota.products
USING lakebase.lakebase_catalog
OPTIONS (
  table 'main.fashion_sota.product_embeddings',
  sync_mode 'SNAPSHOT'  -- Use 'CONTINUOUS' for real-time updates if needed
)
COMMENT 'Product catalog with denormalized embeddings from Unity Catalog';

-- Verify sync
SELECT
  'products' as table_name,
  COUNT(*) as row_count,
  COUNT(DISTINCT product_id) as unique_products,
  COUNT(DISTINCT master_category) as categories,
  COUNT(DISTINCT gender) as genders,
  COUNT(DISTINCT brand) as brands,
  MIN(price) as min_price,
  MAX(price) as max_price
FROM lakebase.fashion_sota.products;
-- Expected: 43,916 rows


-- Step 3: Create Users Table (Option A - New Table)
-- ============================================================================
-- First create Unity Catalog table if it doesn't exist
CREATE TABLE IF NOT EXISTS main.fashion_sota.users (
  user_id STRING PRIMARY KEY,
  email STRING NOT NULL,
  name STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  preferences MAP<STRING, STRING>,
  favorite_categories ARRAY<STRING>,
  favorite_brands ARRAY<STRING>
)
USING DELTA
COMMENT 'User accounts for fashion e-commerce app';

-- Then sync to Lakebase
DROP FOREIGN TABLE IF EXISTS lakebase.fashion_sota.users;

CREATE FOREIGN TABLE lakebase.fashion_sota.users
USING lakebase.lakebase_catalog
OPTIONS (
  table 'main.fashion_sota.users',
  sync_mode 'CONTINUOUS'  -- Real-time sync for user updates
)
COMMENT 'User accounts synced from Unity Catalog';


-- Step 3 (Alternative): Reuse Existing Users from fashion_demo
-- ============================================================================
-- Uncomment this section if you want to reuse existing users

-- DROP FOREIGN TABLE IF EXISTS lakebase.fashion_sota.users;
--
-- CREATE FOREIGN TABLE lakebase.fashion_sota.users
-- USING lakebase.lakebase_catalog
-- OPTIONS (
--   table 'main.fashion_demo.users',  -- Point to existing users
--   sync_mode 'CONTINUOUS'
-- )
-- COMMENT 'User accounts (reused from fashion_demo)';


-- Step 4: Create User Preferences Table
-- ============================================================================
-- Store user style preferences and browsing history

CREATE TABLE IF NOT EXISTS main.fashion_sota.user_preferences (
  user_id STRING NOT NULL,
  preference_type STRING NOT NULL,  -- 'favorite', 'browsed', 'purchased', 'style_cluster'
  value STRING,  -- product_id, brand, category, or cluster_id
  score FLOAT,  -- Affinity score (0-1)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT pk_user_prefs PRIMARY KEY (user_id, preference_type, value)
)
USING DELTA
COMMENT 'User style preferences and interaction history';

-- Sync to Lakebase
DROP FOREIGN TABLE IF EXISTS lakebase.fashion_sota.user_preferences;

CREATE FOREIGN TABLE lakebase.fashion_sota.user_preferences
USING lakebase.lakebase_catalog
OPTIONS (
  table 'main.fashion_sota.user_preferences',
  sync_mode 'CONTINUOUS'
)
COMMENT 'User preferences synced from Unity Catalog';


-- Step 5: Verify All Tables
-- ============================================================================
SELECT
  table_name,
  table_type,
  comment
FROM information_schema.tables
WHERE table_schema = 'fashion_sota'
ORDER BY table_name;

-- Expected tables:
-- - products (43,916 rows)
-- - users (variable)
-- - user_preferences (variable)


-- Step 6: Grant Permissions (for App Service Principal)
-- ============================================================================
-- Replace {app_service_principal} with your app's service principal name

-- Grant read access to products
GRANT SELECT ON lakebase.fashion_sota.products TO `{app_service_principal}`;

-- Grant read/write access to users and preferences
GRANT SELECT, INSERT, UPDATE, DELETE ON lakebase.fashion_sota.users TO `{app_service_principal}`;
GRANT SELECT, INSERT, UPDATE, DELETE ON lakebase.fashion_sota.user_preferences TO `{app_service_principal}`;


-- ============================================================================
-- Validation Queries
-- ============================================================================

-- 1. Check product data quality
SELECT
  master_category,
  gender,
  COUNT(*) as product_count,
  AVG(price) as avg_price,
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
LIMIT 10;

-- 3. Check for missing critical fields
SELECT
  COUNT(*) as total,
  COUNT(product_display_name) as has_name,
  COUNT(image_path) as has_image,
  COUNT(price) as has_price,
  COUNT(master_category) as has_category
FROM lakebase.fashion_sota.products;

-- All counts should equal 43,916 (no nulls in critical fields)


-- ============================================================================
-- Optional: Create Indexes for Performance
-- ============================================================================
-- Note: Lakebase foreign tables may not support indexes directly
-- These would be on the Unity Catalog source tables

-- On Unity Catalog table (run in Databricks SQL):
-- ALTER TABLE main.fashion_sota.product_embeddings
-- SET TBLPROPERTIES (
--   'delta.columnMapping.mode' = 'name',
--   'delta.feature.clustering' = 'supported'
-- );
--
-- CLUSTER BY (master_category, gender, price);


-- ============================================================================
-- Migration Complete!
-- ============================================================================
-- Next steps:
-- 1. Update core/config.py to point to fashion_sota schema
-- 2. Test app endpoints with new schema
-- 3. Verify Vector Search works with product_embeddings_index
-- 4. Deploy to Databricks Apps
