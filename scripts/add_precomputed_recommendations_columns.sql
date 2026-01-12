-- ============================================================================
-- Add Pre-computed Recommendations Columns to Products Table
-- ============================================================================
-- Purpose: Store batch-computed similar products and outfit pairings directly
--          in the products table for ultra-fast lookups (no real-time vector search)
--
-- Columns Added:
--   - similar_product_ids: JSONB array of product IDs for "You Might Also Like"
--   - complete_the_set_ids: JSONB array of product IDs for "Complete the Look"
--
-- Benefits:
--   - Eliminates real-time Vector Search calls on product pages
--   - Reduces latency from ~500ms to ~5ms for recommendations
--   - Simple JOIN instead of external API call
--   - Recommendations computed via batch inference (more thorough/accurate)
-- ============================================================================

-- Connect to Lakebase PostgreSQL
-- Run these statements against the fashion_sota schema

-- ============================================================================
-- Step 1: Add New Columns
-- ============================================================================

-- Add similar_product_ids column (visually similar products)
-- Stored as JSONB array: [12345, 67890, 11111, ...]
ALTER TABLE fashion_sota.products_lakebase
ADD COLUMN IF NOT EXISTS similar_product_ids JSONB DEFAULT '[]'::jsonb;

-- Add complete_the_set_ids column (outfit pairing recommendations)
-- Stored as JSONB array: [12345, 67890, 11111, ...]
ALTER TABLE fashion_sota.products_lakebase
ADD COLUMN IF NOT EXISTS complete_the_set_ids JSONB DEFAULT '[]'::jsonb;

-- Add timestamp for when recommendations were last computed
ALTER TABLE fashion_sota.products_lakebase
ADD COLUMN IF NOT EXISTS recommendations_updated_at TIMESTAMP DEFAULT NULL;

COMMENT ON COLUMN fashion_sota.products_lakebase.similar_product_ids IS
  'Pre-computed visually similar product IDs from batch vector search. Array of integers.';

COMMENT ON COLUMN fashion_sota.products_lakebase.complete_the_set_ids IS
  'Pre-computed outfit pairing product IDs from batch inference. Array of integers.';

COMMENT ON COLUMN fashion_sota.products_lakebase.recommendations_updated_at IS
  'Timestamp when recommendations were last batch-computed for this product.';


-- ============================================================================
-- Step 2: Create GIN Indexes for Fast Array Lookups
-- ============================================================================

-- GIN index for fast "contains" queries on similar products
CREATE INDEX IF NOT EXISTS idx_products_similar_ids
ON fashion_sota.products_lakebase USING GIN (similar_product_ids);

-- GIN index for fast "contains" queries on complete the set
CREATE INDEX IF NOT EXISTS idx_products_complete_set_ids
ON fashion_sota.products_lakebase USING GIN (complete_the_set_ids);


-- ============================================================================
-- Step 3: Verify Schema Changes
-- ============================================================================

SELECT
  column_name,
  data_type,
  column_default,
  is_nullable
FROM information_schema.columns
WHERE table_schema = 'fashion_sota'
  AND table_name = 'products_lakebase'
  AND column_name IN ('similar_product_ids', 'complete_the_set_ids', 'recommendations_updated_at')
ORDER BY ordinal_position;


-- ============================================================================
-- Step 4: Sample Update Query (for batch inference job)
-- ============================================================================

-- Example: Update a single product with pre-computed recommendations
-- This would be run by your batch inference pipeline

/*
UPDATE fashion_sota.products_lakebase
SET
  similar_product_ids = '[12345, 67890, 11111, 22222, 33333, 44444]'::jsonb,
  complete_the_set_ids = '[55555, 66666, 77777, 88888]'::jsonb,
  recommendations_updated_at = CURRENT_TIMESTAMP
WHERE product_id = 10001;
*/

-- Example: Batch update multiple products at once
/*
UPDATE fashion_sota.products_lakebase AS p
SET
  similar_product_ids = batch.similar_ids::jsonb,
  complete_the_set_ids = batch.complete_ids::jsonb,
  recommendations_updated_at = CURRENT_TIMESTAMP
FROM (VALUES
  (10001, '[12345, 67890]', '[55555, 66666]'),
  (10002, '[12346, 67891]', '[55556, 66667]'),
  (10003, '[12347, 67892]', '[55557, 66668]')
) AS batch(product_id, similar_ids, complete_ids)
WHERE p.product_id = batch.product_id;
*/


-- ============================================================================
-- Step 5: Query Examples
-- ============================================================================

-- Get a product with its pre-computed recommendations
SELECT
  product_id,
  product_display_name,
  similar_product_ids,
  complete_the_set_ids,
  recommendations_updated_at
FROM fashion_sota.products_lakebase
WHERE product_id = 10001;

-- Get similar products with full details (efficient JOIN)
/*
WITH source AS (
  SELECT similar_product_ids
  FROM fashion_sota.products_lakebase
  WHERE product_id = 10001
)
SELECT p.*
FROM fashion_sota.products_lakebase p
JOIN source s ON p.product_id::text IN (
  SELECT jsonb_array_elements_text(s.similar_product_ids)
);
*/

-- Alternative: Use ANY for cleaner syntax
/*
SELECT p.*
FROM fashion_sota.products_lakebase p
WHERE p.product_id = ANY(
  SELECT (jsonb_array_elements_text(similar_product_ids))::int
  FROM fashion_sota.products_lakebase
  WHERE product_id = 10001
);
*/


-- ============================================================================
-- Step 6: Check How Many Products Have Recommendations
-- ============================================================================

SELECT
  COUNT(*) as total_products,
  COUNT(*) FILTER (WHERE similar_product_ids != '[]'::jsonb) as has_similar,
  COUNT(*) FILTER (WHERE complete_the_set_ids != '[]'::jsonb) as has_complete_set,
  COUNT(*) FILTER (WHERE recommendations_updated_at IS NOT NULL) as has_updated_timestamp,
  ROUND(100.0 * COUNT(*) FILTER (WHERE similar_product_ids != '[]'::jsonb) / COUNT(*), 2) as similar_coverage_pct,
  ROUND(100.0 * COUNT(*) FILTER (WHERE complete_the_set_ids != '[]'::jsonb) / COUNT(*), 2) as complete_set_coverage_pct
FROM fashion_sota.products_lakebase;


-- ============================================================================
-- Notes for Batch Inference Pipeline
-- ============================================================================
--
-- Your Databricks batch inference notebook should:
--
-- 1. For SIMILAR PRODUCTS (vector search):
--    - For each product, query vector search index for top 10 similar products
--    - Filter out same category if desired, ensure color diversity
--    - Store as JSON array: [id1, id2, id3, ...]
--
-- 2. For COMPLETE THE SET (outfit pairings):
--    - Query outfit_recommendations_from_lookbook table
--    - Apply outfit compatibility filtering
--    - Store as JSON array: [id1, id2, id3, ...]
--
-- 3. Write to Lakebase:
--    - Use batch UPDATE statements (not individual)
--    - Process in batches of 1000-5000 products
--    - Set recommendations_updated_at = CURRENT_TIMESTAMP
--
-- 4. Recommended refresh frequency:
--    - Daily for high-traffic products
--    - Weekly for full catalog
--    - On-demand after new product additions
-- ============================================================================
