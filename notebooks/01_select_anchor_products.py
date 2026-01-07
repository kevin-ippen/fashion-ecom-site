"""
Phase 1: Select Anchor Products for Pattern Generation

Selects ~200 representative products using stratified sampling across:
- Category/Subcategory
- Gender
- Color family (Neutral, Warm, Cool, Bright)
- Price tier (Budget, Mid, Premium)
- Season
- Usage

These anchors will be used to generate reusable outfit patterns.
"""

from databricks.sdk import WorkspaceClient
import json

w = WorkspaceClient()

def select_anchor_products():
    """
    Select representative anchor products using stratified sampling
    """

    print("=" * 80)
    print("Phase 1: Selecting Anchor Products")
    print("=" * 80)

    # Step 1: Create anchor selection query
    anchor_selection_query = """
    CREATE OR REPLACE TABLE main.fashion_sota.outfit_pattern_anchors AS

    WITH paired_products AS (
      -- Products already paired (exclude from anchors to focus on gap)
      SELECT DISTINCT CAST(product_1_id AS INT) as product_id
      FROM main.fashion_sota.outfit_recommendations_filtered
      UNION
      SELECT DISTINCT CAST(product_2_id AS INT) as product_id
      FROM main.fashion_sota.outfit_recommendations_filtered
    ),

    product_features AS (
      SELECT
        p.product_id,
        p.product_display_name,
        p.master_category,
        p.sub_category,
        p.gender,
        p.base_color,
        p.season,
        p.usage,
        p.price,

        -- Derived features for clustering
        CASE
          WHEN p.base_color IN ('Black', 'White', 'Grey', 'Navy', 'Beige', 'Cream',
                                'Tan', 'Khaki', 'Off White', 'Silver', 'Charcoal')
          THEN 'Neutral'
          WHEN p.base_color IN ('Red', 'Orange', 'Yellow', 'Pink', 'Maroon', 'Coral', 'Peach')
          THEN 'Warm'
          WHEN p.base_color IN ('Blue', 'Green', 'Purple', 'Teal', 'Turquoise', 'Olive')
          THEN 'Cool'
          ELSE 'Bright'
        END as color_family,

        CASE
          WHEN p.price < 30 THEN 'Budget'
          WHEN p.price < 80 THEN 'Mid'
          ELSE 'Premium'
        END as price_tier,

        -- Normalize season (handle "All season", NULL, etc.)
        COALESCE(
          CASE
            WHEN p.season IN ('Summer', 'Winter', 'Spring', 'Fall') THEN p.season
            ELSE 'All-Season'
          END,
          'All-Season'
        ) as season_normalized,

        -- Normalize usage
        COALESCE(
          CASE
            WHEN p.usage IN ('Casual', 'Formal', 'Sports', 'Party', 'Travel') THEN p.usage
            ELSE 'Casual'
          END,
          'Casual'
        ) as usage_normalized

      FROM main.fashion_sota.products_lakebase p
      LEFT JOIN paired_products pp ON p.product_id = pp.product_id
      WHERE pp.product_id IS NULL  -- Focus on unpaired products
        AND p.master_category IS NOT NULL
        AND p.sub_category IS NOT NULL
        AND p.gender IS NOT NULL
    ),

    clustered AS (
      SELECT
        *,
        -- Assign row number within each "cluster" (stratified sampling)
        ROW_NUMBER() OVER (
          PARTITION BY
            master_category,
            sub_category,
            gender,
            color_family,
            price_tier,
            season_normalized,
            usage_normalized
          ORDER BY RANDOM()  -- Random selection within cluster
        ) as cluster_rank
      FROM product_features
    ),

    anchors AS (
      -- Take 1 representative from each cluster
      SELECT *
      FROM clustered
      WHERE cluster_rank = 1
    ),

    top_anchors AS (
      -- Prioritize diverse categories (ensure we cover major categories)
      SELECT
        *,
        ROW_NUMBER() OVER (
          PARTITION BY master_category, sub_category
          ORDER BY cluster_rank
        ) as category_rank
      FROM anchors
    )

    SELECT
      product_id,
      product_display_name,
      master_category,
      sub_category,
      gender,
      base_color,
      color_family,
      season,
      season_normalized,
      usage,
      usage_normalized,
      price,
      price_tier
    FROM top_anchors
    WHERE category_rank <= 5  -- Max 5 anchors per category/subcategory
    LIMIT 250  -- Target ~200-250 anchors
    """

    print("\n📊 Running anchor selection query...")
    print("This will take 30-60 seconds...\n")

    execution = w.statement_execution.execute_statement(
        statement=anchor_selection_query,
        warehouse_id="148ccb90800933a1"
    )
    result = execution.result

    print("✅ Anchor products table created: main.fashion_sota.outfit_pattern_anchors")

    # Step 2: Get statistics
    stats_query = """
    SELECT
      COUNT(*) as total_anchors,
      COUNT(DISTINCT master_category) as unique_categories,
      COUNT(DISTINCT sub_category) as unique_subcategories,
      COUNT(DISTINCT gender) as unique_genders,
      COUNT(DISTINCT color_family) as unique_color_families,
      COUNT(DISTINCT price_tier) as unique_price_tiers,
      COUNT(DISTINCT season_normalized) as unique_seasons,
      COUNT(DISTINCT usage_normalized) as unique_usages
    FROM main.fashion_sota.outfit_pattern_anchors
    """

    print("\n📈 Analyzing anchor diversity...")
    execution = w.statement_execution.execute_statement(
        statement=stats_query,
        warehouse_id="148ccb90800933a1"
    )
    result = execution.result

    if result and result.data_array:
        row = result.data_array[0]
        total = int(row[0]) if row[0] else 0

        print(f"\n📊 Anchor Selection Results:")
        print(f"  Total anchors selected:     {total}")
        print(f"  Unique categories:          {row[1]}")
        print(f"  Unique subcategories:       {row[2]}")
        print(f"  Unique genders:             {row[3]}")
        print(f"  Unique color families:      {row[4]}")
        print(f"  Unique price tiers:         {row[5]}")
        print(f"  Unique seasons:             {row[6]}")
        print(f"  Unique usages:              {row[7]}")

    # Step 3: Show distribution by category
    distribution_query = """
    SELECT
      master_category,
      sub_category,
      COUNT(*) as anchor_count
    FROM main.fashion_sota.outfit_pattern_anchors
    GROUP BY master_category, sub_category
    ORDER BY master_category, anchor_count DESC
    """

    print("\n\n📋 Anchor Distribution by Category:")
    print("=" * 80)
    execution = w.statement_execution.execute_statement(
        statement=distribution_query,
        warehouse_id="148ccb90800933a1"
    )
    result = execution.result

    if result and result.data_array:
        print(f"{'Category':<25} {'Subcategory':<25} {'Anchors':>10}")
        print("-" * 70)
        for row in result.data_array:
            category = row[0] if row[0] else "Unknown"
            subcategory = row[1] if row[1] else "Unknown"
            count = int(row[2]) if row[2] else 0
            print(f"{category:<25} {subcategory:<25} {count:>10}")

    # Step 4: Sample a few anchors
    sample_query = """
    SELECT
      product_id,
      product_display_name,
      master_category,
      sub_category,
      gender,
      color_family,
      price_tier,
      season_normalized,
      usage_normalized
    FROM main.fashion_sota.outfit_pattern_anchors
    LIMIT 10
    """

    print("\n\n🔍 Sample Anchor Products:")
    print("=" * 80)
    execution = w.statement_execution.execute_statement(
        statement=sample_query,
        warehouse_id="148ccb90800933a1"
    )
    result = execution.result

    if result and result.data_array:
        for i, row in enumerate(result.data_array, 1):
            print(f"\n{i}. Product ID: {row[0]}")
            print(f"   Name: {row[1]}")
            print(f"   Category: {row[2]} / {row[3]}")
            print(f"   Attributes: {row[4]} | {row[5]} | {row[6]} | {row[7]} | {row[8]}")

    # Step 5: Export anchor list for pattern generation
    export_query = """
    SELECT
      product_id,
      product_display_name,
      master_category,
      sub_category,
      gender,
      base_color,
      color_family,
      season_normalized as season,
      usage_normalized as usage,
      price,
      price_tier
    FROM main.fashion_sota.outfit_pattern_anchors
    ORDER BY master_category, sub_category, product_id
    """

    print("\n\n💾 Exporting anchor products for pattern generation...")
    execution = w.statement_execution.execute_statement(
        statement=export_query,
        warehouse_id="148ccb90800933a1"
    )
    result = execution.result

    anchors = []
    if result and result.data_array:
        for row in result.data_array:
            anchors.append({
                "product_id": int(row[0]) if row[0] else 0,
                "product_display_name": row[1],
                "master_category": row[2],
                "sub_category": row[3],
                "gender": row[4],
                "base_color": row[5],
                "color_family": row[6],
                "season": row[7],
                "usage": row[8],
                "price": float(row[9]) if row[9] else 0.0,
                "price_tier": row[10]
            })

    # Save to JSON file
    output_file = "data/anchor_products.json"
    with open(output_file, 'w') as f:
        json.dump(anchors, f, indent=2)

    print(f"✅ Exported {len(anchors)} anchors to: {output_file}")

    print("\n" + "=" * 80)
    print("✅ Phase 1 COMPLETE - Anchor products selected")
    print("=" * 80)
    print("\n📝 Next Steps:")
    print("  1. Review anchor diversity above")
    print("  2. Run Phase 2: Generate outfit patterns (02_generate_outfit_patterns.py)")
    print(f"  3. Anchors available in: {output_file}")

    return anchors


if __name__ == "__main__":
    print("🚀 Starting anchor product selection...\n")
    anchors = select_anchor_products()
    print(f"\n✅ SUCCESS - {len(anchors)} anchor products ready for pattern generation")
