-- Join Enriched Attributes Back to Products Table
-- This creates the final enriched products table ready for embedding generation

-- ============================================================================
-- STEP 1: Review Extraction Quality
-- ============================================================================

-- Check extraction statistics
SELECT
  COUNT(*) as total_products,
  SUM(CASE WHEN extraction_success THEN 1 ELSE 0 END) as successful_extractions,
  ROUND(100.0 * SUM(CASE WHEN extraction_success THEN 1 ELSE 0 END) / COUNT(*), 1) as success_rate_pct,
  SUM(CASE WHEN confidence_material = 'high' THEN 1 ELSE 0 END) as high_confidence,
  SUM(CASE WHEN confidence_material = 'medium' THEN 1 ELSE 0 END) as medium_confidence,
  SUM(CASE WHEN confidence_material = 'low' THEN 1 ELSE 0 END) as low_confidence
FROM main.fashion_demo.product_extracted_attributes;

-- Material distribution
SELECT
  material,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM main.fashion_demo.product_extracted_attributes
GROUP BY material
ORDER BY count DESC;

-- Formality distribution
SELECT
  formality,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM main.fashion_demo.product_extracted_attributes
GROUP BY formality
ORDER BY count DESC;


-- ============================================================================
-- STEP 2: Create Final Enriched Products Table
-- ============================================================================

CREATE OR REPLACE TABLE main.fashion_demo.products_with_visual_attributes AS
SELECT
  -- Original product data
  p.product_id,
  p.product_display_name,
  p.master_category,
  p.sub_category,
  p.article_type,
  p.base_color,
  p.price,
  p.image_path,
  p.gender,
  p.season,
  p.usage,
  p.year,

  -- Extracted visual attributes (NULL if extraction failed)
  CASE
    WHEN ea.extraction_success AND ea.confidence_material IN ('high', 'medium')
    THEN ea.material
    ELSE NULL
  END as material,

  ea.pattern,
  ea.formality as formality_level,
  ea.style_keywords,
  ea.visual_details,
  ea.collar_type,
  ea.sleeve_length,
  ea.fit_type,

  -- Metadata about extraction
  ea.extraction_success,
  ea.confidence_material,
  ea.extraction_timestamp,

  -- Create RICH TEXT DESCRIPTION
  -- Combines original attributes + extracted attributes
  CONCAT_WS(' ',
    -- Product basics
    p.product_display_name,
    p.article_type,
    p.base_color,
    p.gender,

    -- Extracted attributes (only if high/medium confidence)
    CASE WHEN ea.extraction_success AND ea.confidence_material IN ('high', 'medium')
         THEN ea.material ELSE NULL END,
    CASE WHEN ea.extraction_success THEN ea.pattern ELSE NULL END,
    CASE WHEN ea.extraction_success THEN ea.formality ELSE NULL END,

    -- Style keywords as text
    CASE WHEN ea.extraction_success AND SIZE(ea.style_keywords) > 0
         THEN ARRAY_JOIN(ea.style_keywords, ' ') ELSE NULL END,

    -- Visual details as text
    CASE WHEN ea.extraction_success AND SIZE(ea.visual_details) > 0
         THEN ARRAY_JOIN(ea.visual_details, ' ') ELSE NULL END,

    -- Garment details (if applicable)
    CASE WHEN ea.collar_type IS NOT NULL AND ea.collar_type != 'not applicable'
         THEN ea.collar_type ELSE NULL END,
    CASE WHEN ea.sleeve_length IS NOT NULL AND ea.sleeve_length != 'not applicable'
         THEN ea.sleeve_length ELSE NULL END,

    -- Context
    p.season,
    p.usage
  ) as rich_text_description,

  -- Also keep a BASELINE DESCRIPTION for comparison
  CONCAT_WS(' ',
    p.product_display_name,
    p.article_type,
    p.base_color,
    p.gender,
    p.season,
    p.usage
  ) as baseline_description

FROM main.fashion_demo.products p
LEFT JOIN main.fashion_demo.product_extracted_attributes ea
  ON p.product_id = ea.product_id
WHERE p.image_path IS NOT NULL;  -- Only products with images


-- ============================================================================
-- STEP 3: Add Table Properties & Optimize
-- ============================================================================

-- Enable Change Data Feed for Vector Search Delta Sync
ALTER TABLE main.fashion_demo.products_with_visual_attributes
SET TBLPROPERTIES (delta.enableChangeDataFeed = true);

-- Optimize table
OPTIMIZE main.fashion_demo.products_with_visual_attributes
ZORDER BY (master_category, article_type, material);

-- Add table comment
COMMENT ON TABLE main.fashion_demo.products_with_visual_attributes IS
'Products table enriched with visual attributes extracted by SmolVLM-2.2B.
Includes rich text descriptions combining original metadata + extracted visual features.
Ready for CLIP text embedding generation.';


-- ============================================================================
-- STEP 4: Quality Validation Queries
-- ============================================================================

-- Check total products
SELECT COUNT(*) as total_products_with_images
FROM main.fashion_demo.products_with_visual_attributes;

-- Check enrichment coverage
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN material IS NOT NULL THEN 1 ELSE 0 END) as has_material,
  SUM(CASE WHEN pattern IS NOT NULL THEN 1 ELSE 0 END) as has_pattern,
  SUM(CASE WHEN formality_level IS NOT NULL THEN 1 ELSE 0 END) as has_formality,
  SUM(CASE WHEN SIZE(style_keywords) > 0 THEN 1 ELSE 0 END) as has_style_keywords,
  ROUND(100.0 * SUM(CASE WHEN material IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as material_coverage_pct
FROM main.fashion_demo.products_with_visual_attributes;

-- Sample enriched descriptions
SELECT
  product_display_name,
  baseline_description,
  rich_text_description,
  LENGTH(rich_text_description) - LENGTH(baseline_description) as added_chars
FROM main.fashion_demo.products_with_visual_attributes
WHERE extraction_success = true
ORDER BY added_chars DESC
LIMIT 20;

-- Consistency Check 1: Watches should be metal
SELECT
  product_display_name,
  article_type,
  material,
  confidence_material,
  extraction_success
FROM main.fashion_demo.products_with_visual_attributes
WHERE article_type = 'Watches'
LIMIT 20;

-- Expected: 90%+ should have material='metal'
SELECT
  ROUND(100.0 * SUM(CASE WHEN material = 'metal' THEN 1 ELSE 0 END) / COUNT(*), 1) as watches_metal_pct
FROM main.fashion_demo.products_with_visual_attributes
WHERE article_type = 'Watches';


-- Consistency Check 2: T-Shirts should be knit fabric
SELECT
  product_display_name,
  article_type,
  material,
  pattern,
  confidence_material
FROM main.fashion_demo.products_with_visual_attributes
WHERE article_type = 'Tshirts'
LIMIT 20;

-- Expected: 85%+ should have material='knit fabric'
SELECT
  ROUND(100.0 * SUM(CASE WHEN material = 'knit fabric' THEN 1 ELSE 0 END) / COUNT(*), 1) as tshirts_knit_pct
FROM main.fashion_demo.products_with_visual_attributes
WHERE article_type = 'Tshirts';


-- Consistency Check 3: Formal shirts
SELECT
  product_display_name,
  article_type,
  usage,
  formality_level,
  collar_type,
  material
FROM main.fashion_demo.products_with_visual_attributes
WHERE article_type = 'Shirts' AND usage = 'Formal'
LIMIT 20;


-- ============================================================================
-- STEP 5: Compare Description Lengths
-- ============================================================================

-- How much richer are the new descriptions?
SELECT
  ROUND(AVG(LENGTH(baseline_description)), 0) as avg_baseline_length,
  ROUND(AVG(LENGTH(rich_text_description)), 0) as avg_enriched_length,
  ROUND(AVG(LENGTH(rich_text_description) - LENGTH(baseline_description)), 0) as avg_added_chars,
  ROUND(100.0 * AVG(LENGTH(rich_text_description)) / AVG(LENGTH(baseline_description)) - 100, 1) as pct_increase
FROM main.fashion_demo.products_with_visual_attributes
WHERE extraction_success = true;


-- ============================================================================
-- STEP 6: Export Sample for Manual Review (Optional)
-- ============================================================================

-- Export diverse sample for manual validation
SELECT
  product_id,
  product_display_name,
  master_category,
  article_type,
  -- Original attributes
  base_color,
  usage,
  -- Extracted attributes
  material,
  pattern,
  formality_level,
  style_keywords,
  -- Descriptions
  baseline_description,
  rich_text_description,
  -- Metadata
  confidence_material,
  extraction_success,
  image_path
FROM main.fashion_demo.products_with_visual_attributes
WHERE extraction_success = true
  AND confidence_material IN ('high', 'medium')
-- Sample across different categories
DISTRIBUTE BY master_category
SORT BY RAND()
LIMIT 50;

-- Save this to CSV for manual review if needed


-- ============================================================================
-- STEP 7: Ready for Next Steps
-- ============================================================================

-- ✅ Table created: main.fashion_demo.products_with_visual_attributes
-- ✅ Rich text descriptions generated
-- ✅ Change Data Feed enabled (for Vector Search)

-- NEXT: Generate CLIP text embeddings using rich_text_description
--       Run: multimodal_clip_implementation.py
--       OR create new embedding generation notebook

SELECT 'Ready to generate CLIP text embeddings!' as status;
