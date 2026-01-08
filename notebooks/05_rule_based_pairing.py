"""
Option 2: Rule-Based Pairing for Remaining Products

Simple, deterministic rules to generate outfit pairings for products
that don't have lookbook matches.

Covers remaining ~22,500 products to achieve 100% coverage.
"""

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()


def generate_rule_based_pairs():
    """Generate outfit pairs using simple compatibility rules"""

    print("=" * 80)
    print("Rule-Based Pairing for Remaining Products")
    print("=" * 80)

    # Create rule-based pairs using SQL
    # This applies outfit compatibility rules directly in the database

    rule_based_query = """
    CREATE OR REPLACE TABLE main.fashion_sota.outfit_recommendations_rule_based AS

    WITH paired_products AS (
      -- Products already paired
      SELECT DISTINCT CAST(product_1_id AS INT) as product_id
      FROM main.fashion_sota.outfit_recommendations_unified
      UNION
      SELECT DISTINCT CAST(product_2_id AS INT) as product_id
      FROM main.fashion_sota.outfit_recommendations_unified
    ),

    unpaired AS (
      -- Products needing pairs
      SELECT
        p.product_id,
        p.product_display_name,
        p.master_category,
        p.sub_category,
        p.gender,
        p.base_color,
        p.season,
        p.usage,
        p.price
      FROM main.fashion_sota.products_lakebase p
      LEFT JOIN paired_products pp ON p.product_id = pp.product_id
      WHERE pp.product_id IS NULL
    ),

    compatible_pairs AS (
      -- Generate pairs using compatibility rules
      SELECT
        CAST(a.product_id AS STRING) as product_1_id,
        a.product_display_name as product_1_name,
        a.master_category as product_1_category,
        CAST(b.product_id AS STRING) as product_2_id,
        b.product_display_name as product_2_name,
        b.master_category as product_2_category,
        1 as co_occurrence_count

      FROM unpaired a
      CROSS JOIN main.fashion_sota.products_lakebase b

      WHERE
        -- Same gender (or unisex)
        (a.gender = b.gender OR a.gender = 'Unisex' OR b.gender = 'Unisex')

        -- Different products
        AND a.product_id < b.product_id

        -- Category compatibility rules
        AND (
          -- Apparel + Footwear
          (a.master_category = 'Apparel' AND a.sub_category IN ('Topwear', 'Bottomwear', 'Dress')
           AND b.master_category = 'Footwear' AND b.sub_category IN ('Shoes', 'Sandal', 'Flip Flops'))

          OR

          -- Apparel + Accessories
          (a.master_category = 'Apparel' AND a.sub_category IN ('Topwear', 'Bottomwear', 'Dress')
           AND b.master_category = 'Accessories' AND b.sub_category IN ('Watches', 'Bags', 'Belts', 'Eyewear'))

          OR

          -- Topwear + Bottomwear
          (a.master_category = 'Apparel' AND a.sub_category = 'Topwear'
           AND b.master_category = 'Apparel' AND b.sub_category = 'Bottomwear')

          OR

          -- Footwear + Accessories
          (a.master_category = 'Footwear'
           AND b.master_category = 'Accessories' AND b.sub_category IN ('Bags', 'Watches', 'Eyewear'))
        )

        -- Avoid duplicate types
        AND NOT (a.sub_category = b.sub_category AND a.master_category = b.master_category)

        -- Color compatibility (neutrals always work, avoid clashes)
        AND (
          -- Both neutral
          (a.base_color IN ('Black', 'White', 'Grey', 'Navy', 'Beige', 'Cream')
           OR b.base_color IN ('Black', 'White', 'Grey', 'Navy', 'Beige', 'Cream'))

          OR

          -- Same color family
          (a.base_color = b.base_color)

          OR

          -- Blue tones together
          (a.base_color IN ('Blue', 'Navy') AND b.base_color IN ('Blue', 'Navy', 'White', 'Grey'))

          OR

          -- Earth tones together
          (a.base_color IN ('Brown', 'Tan', 'Beige', 'Khaki') AND b.base_color IN ('Brown', 'Tan', 'Beige', 'Khaki', 'White'))
        )

        -- Limit pairs per product to avoid explosion
        QUALIFY ROW_NUMBER() OVER (PARTITION BY a.product_id ORDER BY RAND()) <= 4
    )

    SELECT
      product_1_id,
      product_1_name,
      product_1_category,
      product_2_id,
      product_2_name,
      product_2_category,
      co_occurrence_count,
      'rule_based' as source
    FROM compatible_pairs
    """

    print("\n⏳ Generating rule-based pairs...")
    print("This will take 3-5 minutes...\n")

    execution = w.statement_execution.execute_statement(
        statement=rule_based_query,
        warehouse_id="148ccb90800933a1"
    )

    print("✅ Rule-based pairs table created")

    # Check results
    stats_query = """
    SELECT
      COUNT(*) as total_pairs,
      COUNT(DISTINCT product_1_id) + COUNT(DISTINCT product_2_id) as approx_products_covered
    FROM main.fashion_sota.outfit_recommendations_rule_based
    """

    print("\n📊 Analyzing results...")
    execution = w.statement_execution.execute_statement(
        statement=stats_query,
        warehouse_id="148ccb90800933a1"
    )
    result = execution.result

    if result and result.data_array:
        row = result.data_array[0]
        pairs = int(row[0]) if row[0] else 0
        products = int(row[1]) if row[1] else 0

        print(f"  Total rule-based pairs:    {pairs:,}")
        print(f"  Approx products covered:   {products:,}")

    # Update unified view
    print("\n🔧 Updating unified view to include rule-based pairs...")

    final_unified_query = """
    CREATE OR REPLACE VIEW main.fashion_sota.outfit_recommendations_unified AS

    -- Tier 1: Curated lookbook pairs (highest quality)
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

    -- Tier 2: Algorithmic lookbook pairs (good quality)
    SELECT
      product_1_id,
      product_1_name,
      product_1_category,
      product_2_id,
      product_2_name,
      product_2_category,
      co_occurrence_count,
      source,
      0.8 as quality_score
    FROM main.fashion_sota.outfit_recommendations_from_lookbook

    UNION ALL

    -- Tier 3: Rule-based pairs (acceptable quality)
    SELECT
      product_1_id,
      product_1_name,
      product_1_category,
      product_2_id,
      product_2_name,
      product_2_category,
      co_occurrence_count,
      source,
      0.6 as quality_score
    FROM main.fashion_sota.outfit_recommendations_rule_based
    """

    execution = w.statement_execution.execute_statement(
        statement=final_unified_query,
        warehouse_id="148ccb90800933a1"
    )

    print("✅ Unified view updated")

    # Final coverage check
    print("\n\n📊 FINAL COVERAGE CHECK:")
    print("=" * 80)

    final_coverage_query = """
    WITH all_paired_products AS (
      SELECT DISTINCT CAST(product_1_id AS INT) as product_id
      FROM main.fashion_sota.outfit_recommendations_unified
      UNION
      SELECT DISTINCT CAST(product_2_id AS INT) as product_id
      FROM main.fashion_sota.outfit_recommendations_unified
    )
    SELECT
      COUNT(*) as products_with_pairings,
      (SELECT COUNT(*) FROM main.fashion_sota.products_lakebase) as total_products
    FROM all_paired_products
    """

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

        print(f"Products with pairings:  {with_pairings:,} ({coverage_pct:.1f}%)")
        print(f"Total products:          {total:,}")
        print(f"Remaining unpaired:      {remaining:,} ({100-coverage_pct:.1f}%)")

        if coverage_pct >= 99:
            print(f"\n🎉 SUCCESS! {coverage_pct:.1f}% COVERAGE ACHIEVED!")
        elif coverage_pct >= 95:
            print(f"\n✅ EXCELLENT! {coverage_pct:.1f}% coverage (near-100%)")
        else:
            print(f"\n📈 Good progress: {coverage_pct:.1f}% coverage")

    print("\n\n" + "=" * 80)
    print("✅ COMPLETE - Rule-based pairing finished")
    print("=" * 80)

    return True


if __name__ == "__main__":
    print("🚀 Starting rule-based pairing...\n")
    success = generate_rule_based_pairs()

    if success:
        print("\n✅ Phase 5: Update API to use outfit_recommendations_unified view")
    else:
        print("\n❌ Failed to generate rule-based pairs")
