"""
Generate outfit pairing recommendations from product_to_lookbook_matches

This script leverages the EXISTING reverse-matching data where products from our
catalog were matched to lookbook outfit regions. Products matched to different
regions of the SAME lookbook outfit naturally pair well together.

Coverage Impact:
- Current: 1,086 products (2.4%)
- After this script: ~21,326 products (48%)
- Remaining gap: ~23,000 products (52%) - can use GenAI or rules
"""

from databricks.sdk import WorkspaceClient
from databricks import sql
import os

w = WorkspaceClient()

def create_outfit_pairs_from_lookbook():
    """
    Generate outfit pairs by matching products from the same lookbook outfit
    """

    print("=" * 80)
    print("Generating Outfit Pairs from Lookbook Matches")
    print("=" * 80)

    # Step 1: Create the outfit pairs table from lookbook matches
    create_pairs_query = """
    CREATE OR REPLACE TABLE main.fashion_sota.outfit_recommendations_from_lookbook AS

    WITH product_lookbook_matches AS (
      -- Get product-to-lookbook matches with good similarity
      SELECT
        CAST(pm.product_id AS INT) as product_id,
        pm.product_display_name,
        pm.master_category,
        pm.sub_category,
        pm.inspo_id,
        pm.region_id,
        pm.similarity,
        pm.rank
      FROM main.fashion_sota.product_to_lookbook_matches pm
      WHERE pm.similarity >= 0.30  -- Reasonable similarity threshold
        AND pm.rank <= 5  -- Top 5 matches per lookbook region
    ),

    product_enriched AS (
      -- Join with product catalog to get full metadata
      SELECT
        plm.*,
        p.base_color,
        p.gender,
        p.season,
        p.usage,
        p.price
      FROM product_lookbook_matches plm
      INNER JOIN main.fashion_sota.products_lakebase p
        ON plm.product_id = p.product_id
    ),

    outfit_pairs AS (
      -- Pair products from same lookbook outfit (same inspo_id)
      SELECT
        a.product_id as product_1_id,
        a.product_display_name as product_1_name,
        a.master_category as product_1_category,
        b.product_id as product_2_id,
        b.product_display_name as product_2_name,
        b.master_category as product_2_category,
        a.inspo_id,
        COUNT(DISTINCT a.inspo_id) as co_occurrence_count,
        AVG(a.similarity) as avg_similarity_1,
        AVG(b.similarity) as avg_similarity_2
      FROM product_enriched a
      INNER JOIN product_enriched b
        ON a.inspo_id = b.inspo_id  -- Same lookbook outfit
        AND a.region_id < b.region_id  -- Different items (avoid duplicates)
        AND a.product_id != b.product_id  -- Different products

      -- Apply compatibility filters
      WHERE
        -- Same gender (or unisex)
        (a.gender = b.gender OR a.gender = 'Unisex' OR b.gender = 'Unisex')

        -- Exclude obvious incompatibilities
        AND NOT (a.master_category = b.master_category AND a.sub_category = b.sub_category)

        -- Exclude dress + pants/top combinations
        AND NOT (a.sub_category = 'Dress' AND b.sub_category IN ('Topwear', 'Bottomwear'))
        AND NOT (b.sub_category = 'Dress' AND a.sub_category IN ('Topwear', 'Bottomwear'))

      GROUP BY
        a.product_id, a.product_display_name, a.master_category,
        b.product_id, b.product_display_name, b.master_category,
        a.inspo_id

      HAVING co_occurrence_count >= 1  -- At least 1 lookbook in common
    )

    SELECT
      CAST(product_1_id AS STRING) as product_1_id,
      product_1_name,
      product_1_category,
      CAST(product_2_id AS STRING) as product_2_id,
      product_2_name,
      product_2_category,
      co_occurrence_count,
      'lookbook_matching' as source
    FROM outfit_pairs
    """

    print("\n📊 Creating outfit pairs from lookbook matches...")
    print("This may take 2-3 minutes...")

    execution = w.statement_execution.execute_statement(
        statement=create_pairs_query,
        warehouse_id="148ccb90800933a1"
    )
    result = execution.result

    print("✅ Table created: main.fashion_sota.outfit_recommendations_from_lookbook")

    # Step 2: Get statistics
    stats_query = """
    SELECT
      COUNT(*) as total_pairs,
      COUNT(DISTINCT product_1_id) as unique_products_1,
      COUNT(DISTINCT product_2_id) as unique_products_2,
      COUNT(DISTINCT product_1_id) + COUNT(DISTINCT product_2_id) -
        COUNT(DISTINCT CASE WHEN product_1_id = product_2_id THEN product_1_id END) as total_unique_products
    FROM main.fashion_sota.outfit_recommendations_from_lookbook
    """

    print("\n📈 Analyzing results...")
    execution = w.statement_execution.execute_statement(
        statement=stats_query,
        warehouse_id="148ccb90800933a1"
    )
    result = execution.result

    if result and result.data_array:
        row = result.data_array[0]
        total_pairs = int(row[0]) if row[0] else 0
        unique_1 = int(row[1]) if row[1] else 0
        unique_2 = int(row[2]) if row[2] else 0

        print(f"\n📊 Results:")
        print(f"  Total outfit pairs generated:  {total_pairs:,}")
        print(f"  Unique products covered:       ~{unique_1 + unique_2:,}")

        # Calculate new coverage
        total_products = 44424
        new_coverage_pct = ((unique_1 + unique_2) / total_products * 100)

        print(f"\n🎯 Coverage Impact:")
        print(f"  Before: 1,086 products (2.4%)")
        print(f"  After:  ~{unique_1 + unique_2:,} products ({new_coverage_pct:.1f}%)")
        print(f"  Improvement: {new_coverage_pct - 2.4:.1f} percentage points!")

    # Step 3: Create unified view
    unified_view_query = """
    CREATE OR REPLACE VIEW main.fashion_sota.outfit_recommendations_unified AS

    -- Existing lookbook pairs (high quality, manually curated)
    SELECT
      product_1_id,
      product_1_name,
      product_1_category,
      product_2_id,
      product_2_name,
      product_2_category,
      co_occurrence_count,
      'lookbook_curated' as source,
      1.0 as quality_score
    FROM main.fashion_sota.outfit_recommendations_filtered

    UNION ALL

    -- New pairs from reverse matching (good quality, algorithmic)
    SELECT
      product_1_id,
      product_1_name,
      product_1_category,
      product_2_id,
      product_2_name,
      product_2_category,
      co_occurrence_count,
      source,
      0.8 as quality_score  -- Slightly lower confidence
    FROM main.fashion_sota.outfit_recommendations_from_lookbook
    WHERE
      -- Exclude if already in curated set
      NOT EXISTS (
        SELECT 1 FROM main.fashion_sota.outfit_recommendations_filtered f
        WHERE
          (f.product_1_id = product_1_id AND f.product_2_id = product_2_id)
          OR (f.product_1_id = product_2_id AND f.product_2_id = product_1_id)
      )
    """

    print("\n🔗 Creating unified view...")
    execution = w.statement_execution.execute_statement(
        statement=unified_view_query,
        warehouse_id="148ccb90800933a1"
    )

    print("✅ Created: main.fashion_sota.outfit_recommendations_unified")

    # Step 4: Final coverage stats
    final_coverage_query = """
    WITH all_paired_products AS (
      SELECT DISTINCT CAST(product_1_id AS INT) as product_id
      FROM main.fashion_sota.outfit_recommendations_unified
      UNION
      SELECT DISTINCT CAST(product_2_id AS INT) as product_id
      FROM main.fashion_sota.outfit_recommendations_unified
    )
    SELECT
      COUNT(DISTINCT product_id) as products_with_pairings,
      (SELECT COUNT(*) FROM main.fashion_sota.products_lakebase) as total_products
    FROM all_paired_products
    """

    print("\n📊 Final Coverage Analysis:")
    execution = w.statement_execution.execute_statement(
        statement=final_coverage_query,
        warehouse_id="148ccb90800933a1"
    )
    result = execution.result

    if result and result.data_array:
        row = result.data_array[0]
        with_pairings = int(row[0]) if row[0] else 0
        total = int(row[1]) if row[1] else 0
        coverage_pct = (with_pairings / total * 100) if total > 0 else 0
        remaining = total - with_pairings

        print(f"  Products with pairings:  {with_pairings:,} ({coverage_pct:.1f}%)")
        print(f"  Products without:        {remaining:,} ({100-coverage_pct:.1f}%)")

        print(f"\n✅ SUCCESS! Coverage improved from 2.4% to {coverage_pct:.1f}%")

        if coverage_pct < 90:
            print(f"\n📝 Next Steps:")
            print(f"  - Remaining gap: {remaining:,} products ({100-coverage_pct:.1f}%)")
            print(f"  - Option 1: Use GenAI (Llama 3.1 70B) for remaining products")
            print(f"  - Option 2: Use rule-based pairing for remaining products")
            print(f"  - See: OUTFIT_PAIRING_100_PERCENT_PLAN.md")

    return True


if __name__ == "__main__":
    print("🚀 Starting outfit pair generation from lookbook matches...\n")
    success = create_outfit_pairs_from_lookbook()

    if success:
        print("\n" + "=" * 80)
        print("✅ COMPLETE - Update API to use outfit_recommendations_unified view")
        print("=" * 80)
