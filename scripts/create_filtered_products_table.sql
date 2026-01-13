-- Create a filtered products table that only includes products with outfit pairings
-- Run this in Databricks SQL or a notebook

-- First, check the current data
SELECT
    COUNT(*) as total_products,
    COUNT(CASE WHEN complete_the_set_ids IS NOT NULL THEN 1 END) as with_outfit_data,
    COUNT(CASE WHEN complete_the_set_ids IS NOT NULL
               AND complete_the_set_ids != '[]'
               AND LENGTH(complete_the_set_ids) > 2 THEN 1 END) as with_actual_outfits
FROM main.fashion_sota.products_lakebase;

-- Create the filtered table (drop if exists)
DROP TABLE IF EXISTS main.fashion_sota.products_with_outfits;

CREATE TABLE main.fashion_sota.products_with_outfits AS
SELECT *
FROM main.fashion_sota.products_lakebase
WHERE
    -- Category filters
    master_category IN ('Apparel', 'Accessories', 'Footwear')
    AND sub_category NOT IN (
        'Innerwear', 'Loungewear and Nightwear', 'Free Gifts', 'Fragrance', 'Skin Care',
        'Saree', 'Kurta', 'Kurtas', 'Dupatta', 'Churidar', 'Salwar', 'Lehenga Choli',
        'Kameez', 'Dhoti', 'Patiala', 'Kurta Sets', 'Sarees', 'Salwar and Dupatta', 'Lehenga'
    )
    AND article_type NOT IN (
        'Swimwear', 'Free Gifts', 'Perfume and Body Mist', 'Mens Grooming Kit',
        'Saree', 'Sarees', 'Kurta', 'Kurtas', 'Dupatta', 'Churidar', 'Salwar',
        'Lehenga Choli', 'Kameez', 'Dhoti', 'Patiala'
    )
    -- Outfit pairing filter
    AND complete_the_set_ids IS NOT NULL
    AND complete_the_set_ids != '[]'
    AND LENGTH(complete_the_set_ids) > 2;

-- Verify the result
SELECT COUNT(*) as filtered_product_count FROM main.fashion_sota.products_with_outfits;

-- Show sample
SELECT product_id, product_display_name, master_category, complete_the_set_ids
FROM main.fashion_sota.products_with_outfits
LIMIT 5;
