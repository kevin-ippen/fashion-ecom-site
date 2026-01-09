"""
Phase 4: Batch Apply Patterns to All Unpaired Products

Uses neighborhood-based pattern application to generate recommendations
for all products that don't have outfit pairings yet.

Expected: ~23,000 products × 4 recs = ~92,000 new outfit pairs
"""

import json
import asyncio
from databricks.sdk import WorkspaceClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys

sys.path.insert(0, '/Users/kevin.ippen/projects/fashion-ecom-site')

from services.neighborhood_pattern_service import neighborhood_pattern_service
from services.vector_search_service import vector_search_service
from repositories.lakebase import LakebaseRepository
from core.config import settings

w = WorkspaceClient()


async def batch_apply_patterns():
    """Apply patterns to all unpaired products"""

    print("=" * 80)
    print("Phase 4: Batch Pattern Application")
    print("=" * 80)

    # Step 1: Load patterns and anchors
    print("\n📂 Loading patterns and anchors...")

    with open("data/outfit_patterns.json", 'r') as f:
        patterns = json.load(f)

    with open("data/anchor_products.json", 'r') as f:
        anchors = json.load(f)

    neighborhood_pattern_service.load_patterns(patterns)
    neighborhood_pattern_service.load_anchors(anchors)

    print(f"✅ Loaded {len(patterns)} patterns and {len(anchors)} anchors")

    # Step 2: Get unpaired products
    print("\n📊 Querying unpaired products...")

    unpaired_query = """
    WITH paired_products AS (
      SELECT DISTINCT CAST(product_1_id AS INT) as product_id
      FROM main.fashion_sota.outfit_recommendations_filtered
      UNION
      SELECT DISTINCT CAST(product_2_id AS INT) as product_id
      FROM main.fashion_sota.outfit_recommendations_filtered
    )
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
      AND p.master_category IN ('Apparel', 'Footwear', 'Accessories')
    LIMIT 100  -- Start with 100 for testing
    """

    execution = w.statement_execution.execute_statement(
        statement=unpaired_query,
        warehouse_id=settings.SQL_WAREHOUSE_ID
    )
    result = execution.result

    if not result or not result.data_array:
        print("❌ No unpaired products found")
        return

    unpaired_products = []
    for row in result.data_array:
        unpaired_products.append({
            'product_id': int(row[0]) if row[0] else 0,
            'product_display_name': row[1],
            'master_category': row[2],
            'sub_category': row[3],
            'gender': row[4],
            'base_color': row[5],
            'season': row[6],
            'usage': row[7],
            'price': float(row[8]) if row[8] else 0.0
        })

    print(f"✅ Found {len(unpaired_products)} unpaired products to process")

    # Step 3: Setup Lakebase connection
    print("\n🔗 Connecting to Lakebase...")

    # Get fresh OAuth token
    token = w.config.oauth_token().access_token

    # Build connection URL with token
    connection_url = (
        f"postgresql+asyncpg://{settings.LAKEBASE_USER}:{token}@"
        f"{settings.LAKEBASE_HOST}:{settings.LAKEBASE_PORT}/{settings.LAKEBASE_DATABASE}"
    )

    engine = create_async_engine(
        connection_url,
        echo=False,
        pool_pre_ping=True
    )

    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    print("✅ Connected to Lakebase")

    # Step 4: Process products in batches
    print(f"\n⏳ Processing {len(unpaired_products)} products...")
    print("Generating 4 recommendations per product\n")

    all_recommendations = []
    failed_products = []

    batch_size = 10
    total = len(unpaired_products)

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = unpaired_products[batch_start:batch_end]

        print(f"📦 Batch {batch_start//batch_size + 1}/{(total-1)//batch_size + 1}: Products {batch_start+1}-{batch_end}")

        for i, product in enumerate(batch, 1):
            try:
                async with async_session() as session:
                    repo = LakebaseRepository(session)

                    # Generate recommendations
                    recommendations = await neighborhood_pattern_service.generate_recommendations(
                        target_product=product,
                        vector_search_service=vector_search_service,
                        lakebase_repo=repo,
                        limit=4
                    )

                    if recommendations:
                        # Convert to pairing format
                        for rec in recommendations:
                            all_recommendations.append({
                                'source_product_id': product['product_id'],
                                'source_product_name': product['product_display_name'],
                                'source_category': product['master_category'],
                                'recommended_product_id': rec.get('product_id'),
                                'recommended_product_name': rec.get('product_display_name'),
                                'recommended_category': rec.get('master_category'),
                                'pattern_name': rec.get('pattern_name', 'Unknown'),
                                'confidence': rec.get('anchor_similarity', 0.7)
                            })

                        print(f"  [{batch_start + i}/{total}] ✅ {product['product_display_name'][:45]:45} → {len(recommendations)} recs")
                    else:
                        print(f"  [{batch_start + i}/{total}] ⚠️  No recs: {product['product_display_name'][:45]}")
                        failed_products.append(product['product_id'])

            except Exception as e:
                print(f"  [{batch_start + i}/{total}] ❌ Error: {product['product_display_name'][:45]}")
                print(f"      {str(e)[:60]}")
                failed_products.append(product['product_id'])
                continue

        # Checkpoint every batch
        if all_recommendations and batch_end % 50 == 0:
            checkpoint_file = f"data/pattern_recs_checkpoint_{batch_end}.json"
            with open(checkpoint_file, 'w') as f:
                json.dump(all_recommendations, f, indent=2)
            print(f"  💾 Checkpoint saved: {checkpoint_file}")

    # Step 5: Save results
    print(f"\n\n💾 Saving all recommendations...")
    output_file = "data/pattern_based_recommendations.json"
    with open(output_file, 'w') as f:
        json.dump(all_recommendations, f, indent=2)

    print(f"✅ Saved {len(all_recommendations)} recommendations to: {output_file}")

    # Step 6: Write to Unity Catalog
    print(f"\n📊 Writing to Unity Catalog table...")

    # Create table
    create_table_query = """
    CREATE TABLE IF NOT EXISTS main.fashion_sota.outfit_recommendations_pattern_based (
      product_1_id STRING,
      product_1_name STRING,
      product_1_category STRING,
      product_2_id STRING,
      product_2_name STRING,
      product_2_category STRING,
      pattern_name STRING,
      confidence DOUBLE,
      source STRING,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
    )
    """

    execution = w.statement_execution.execute_statement(
        statement=create_table_query,
        warehouse_id=settings.SQL_WAREHOUSE_ID
    )

    print("✅ Table created: main.fashion_sota.outfit_recommendations_pattern_based")

    # Format recommendations for insertion
    print("📝 Preparing data for bulk insert...")

    # For now, save to JSON - in production would use Spark for bulk load
    formatted_recs = []
    for rec in all_recommendations:
        formatted_recs.append({
            'product_1_id': str(rec['source_product_id']),
            'product_1_name': rec['source_product_name'],
            'product_1_category': rec['source_category'],
            'product_2_id': str(rec['recommended_product_id']),
            'product_2_name': rec['recommended_product_name'],
            'product_2_category': rec['recommended_category'],
            'pattern_name': rec['pattern_name'],
            'confidence': rec['confidence'],
            'source': 'pattern_based'
        })

    with open("data/pattern_recs_for_uc.json", 'w') as f:
        json.dump(formatted_recs, f, indent=2)

    print(f"✅ Data prepared for UC table: data/pattern_recs_for_uc.json")
    print("⚠️  Note: Use Spark to bulk load this data into the table")

    # Statistics
    print(f"\n\n" + "=" * 80)
    print("📊 Batch Processing Summary")
    print("=" * 80)
    print(f"  Total products processed:    {len(unpaired_products)}")
    print(f"  Successful:                  {len(unpaired_products) - len(failed_products)}")
    print(f"  Failed:                      {len(failed_products)}")
    print(f"  Total recommendations:       {len(all_recommendations)}")
    print(f"  Avg recs per product:        {len(all_recommendations) / len(unpaired_products):.1f}")
    print(f"  Success rate:                {(len(unpaired_products) - len(failed_products)) / len(unpaired_products) * 100:.1f}%")

    if failed_products:
        print(f"\n⚠️  Failed product IDs ({len(failed_products)}): {failed_products[:10]}{'...' if len(failed_products) > 10 else ''}")

    print("\n\n" + "=" * 80)
    print("✅ Phase 4 COMPLETE - Pattern-based recommendations generated")
    print("=" * 80)
    print("\n📝 Next Steps:")
    print("  1. Load data into UC table with Spark")
    print("  2. Run Phase 5: Create unified view")
    print("  3. Update API to use unified view")
    print("  4. Verify 100% coverage!")

    await engine.dispose()

    return all_recommendations


if __name__ == "__main__":
    print("🚀 Starting batch pattern application...\n")
    recommendations = asyncio.run(batch_apply_patterns())

    if recommendations:
        print(f"\n✅ SUCCESS - {len(recommendations)} recommendations generated")
    else:
        print(f"\n❌ FAILED - No recommendations generated")
