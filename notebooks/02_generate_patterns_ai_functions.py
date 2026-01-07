"""
Phase 2: Generate Outfit Patterns using Databricks AI Functions

Uses ai_query() SQL function to generate patterns - no endpoint setup needed!

Reference: https://docs.databricks.com/aws/en/large-language-models/ai-functions
"""

from databricks.sdk import WorkspaceClient
import json
import time

w = WorkspaceClient()

def generate_patterns_with_ai_functions():
    """
    Generate outfit patterns using Databricks AI Functions (ai_query)
    """

    print("=" * 80)
    print("Phase 2: Generating Outfit Patterns with AI Functions")
    print("=" * 80)

    # Load anchors
    print("\n📂 Loading anchor products...")
    with open("data/anchor_products.json", 'r') as f:
        anchors = json.load(f)

    print(f"✅ Loaded {len(anchors)} anchor products")

    # Step 1: Load anchors into temp table
    print("\n📊 Creating temporary anchor table for batch processing...")

    # Build INSERT statements
    insert_values = []
    for anchor in anchors:
        insert_values.append(f"""
            ({anchor['product_id']},
             '{anchor['product_display_name'].replace("'", "''")}',
             '{anchor['master_category']}',
             '{anchor['sub_category']}',
             '{anchor['gender']}',
             '{anchor['base_color'].replace("'", "''")}',
             '{anchor['color_family']}',
             '{anchor['season']}',
             '{anchor['usage']}',
             {anchor['price']},
             '{anchor['price_tier']}')
        """)

    # Create and populate temp table
    create_temp_query = f"""
    CREATE OR REPLACE TEMP VIEW anchor_products_temp AS
    SELECT * FROM VALUES
    {','.join(insert_values[:50])}  -- Start with first 50 for testing
    AS t(product_id, product_display_name, master_category, sub_category,
         gender, base_color, color_family, season, usage, price, price_tier)
    """

    execution = w.statement_execution.execute_statement(
        statement=create_temp_query,
        warehouse_id="148ccb90800933a1"
    )

    print("✅ Temporary anchor table created (first 50 anchors)")

    # Step 2: Test ai_query with a single product
    print("\n🧪 Testing ai_query with sample anchor...")

    test_anchor = anchors[0]
    test_prompt = f"""You are a professional fashion stylist. Generate 3 outfit pairing patterns for this product.

Product: {test_anchor['product_display_name']}
Category: {test_anchor['master_category']} / {test_anchor['sub_category']}
Color: {test_anchor['base_color']} ({test_anchor['color_family']} family)
Gender: {test_anchor['gender']}
Season: {test_anchor['season']}
Style: {test_anchor['usage']}
Price: ${test_anchor['price']:.2f} ({test_anchor['price_tier']} tier)

Generate 3 outfit patterns. For each pattern, specify what item types pair well.

Output format (JSON):
{{
  "patterns": [
    {{
      "name": "Pattern name",
      "items": [
        {{"role": "bottom", "categories": ["Jeans", "Chinos"], "colors": ["Navy", "Black"], "required": true}},
        {{"role": "footwear", "categories": ["Sneakers"], "colors": ["White"], "required": true}}
      ],
      "confidence": 0.8
    }}
  ]
}}

Respond with ONLY the JSON, no other text."""

    test_query = f"""
    SELECT ai_query(
        'databricks-meta-llama-3-1-405b-instruct',
        '{test_prompt.replace("'", "''")}'
    ) as pattern_json
    """

    try:
        print(f"   Calling ai_query for product: {test_anchor['product_display_name'][:50]}...")
        execution = w.statement_execution.execute_statement(
            statement=test_query,
            warehouse_id="148ccb90800933a1"
        )
        result = execution.result

        if result and result.data_array:
            pattern_response = result.data_array[0][0]
            print(f"   ✅ Pattern generated successfully!")
            print(f"   Sample response (first 200 chars): {pattern_response[:200]}...")

            # Try to parse JSON
            try:
                # Clean response
                response = pattern_response.strip()
                if response.startswith("```json"):
                    response = response[7:]
                if response.startswith("```"):
                    response = response[3:]
                if response.endswith("```"):
                    response = response[:-3]
                response = response.strip()

                patterns = json.loads(response)
                print(f"   ✅ JSON parsed successfully - {len(patterns.get('patterns', []))} patterns found")
            except json.JSONDecodeError as e:
                print(f"   ⚠️  JSON parse warning: {e}")

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        print("\n⚠️  AI Functions may not be available or model name incorrect")
        print("   Try checking available models with: SELECT ai_query('databricks-meta-llama-3-1-405b-instruct', 'test')")
        return False

    # Step 3: Batch generate patterns for all anchors
    print("\n\n⏳ Generating patterns for all anchors (this will take 10-15 minutes)...")
    print("Processing in batches of 10 to avoid timeouts...\n")

    batch_size = 10
    all_patterns = []

    for batch_start in range(0, len(anchors), batch_size):
        batch_end = min(batch_start + batch_size, len(anchors))
        batch_anchors = anchors[batch_start:batch_end]

        print(f"📦 Batch {batch_start//batch_size + 1}/{(len(anchors)-1)//batch_size + 1}: Processing anchors {batch_start+1}-{batch_end}...")

        for i, anchor in enumerate(batch_anchors, 1):
            try:
                # Build prompt
                prompt = f"""You are a professional fashion stylist. Generate 3 outfit pairing patterns for this product.

Product: {anchor['product_display_name']}
Category: {anchor['master_category']} / {anchor['sub_category']}
Color: {anchor['base_color']} ({anchor['color_family']} family)
Gender: {anchor['gender']}
Season: {anchor['season']}
Style: {anchor['usage']}
Price: ${anchor['price']:.2f} ({anchor['price_tier']} tier)

Generate 3 outfit patterns that specify what item TYPES pair well (not specific products).

Output ONLY valid JSON:
{{
  "patterns": [
    {{
      "name": "Pattern name (2-4 words)",
      "description": "Brief style description",
      "items": [
        {{"role": "bottom|footwear|accessory", "categories": ["Category/Subcategory"], "colors": ["Color1", "Color2"], "required": true}},
        {{"role": "footwear", "categories": ["Footwear/Sneakers"], "colors": ["White", "Black"], "required": true}}
      ],
      "confidence": 0.7-1.0
    }}
  ]
}}

Rules: Be specific about categories, choose compatible colors, match style (casual with casual)."""

                # Call ai_query
                query = f"""
                SELECT ai_query(
                    'databricks-meta-llama-3-1-405b-instruct',
                    '{prompt.replace("'", "''")}'
                ) as pattern_json
                """

                execution = w.statement_execution.execute_statement(
                    statement=query,
                    warehouse_id="148ccb90800933a1"
                )
                result = execution.result

                if result and result.data_array:
                    pattern_response = result.data_array[0][0]

                    # Parse response
                    try:
                        response = pattern_response.strip()
                        if response.startswith("```json"):
                            response = response[7:]
                        if response.startswith("```"):
                            response = response[3:]
                        if response.endswith("```"):
                            response = response[:-3]
                        response = response.strip()

                        data = json.loads(response)
                        patterns = data.get('patterns', [])

                        # Add anchor metadata
                        for pattern in patterns:
                            pattern['anchor_id'] = anchor['product_id']
                            pattern['anchor_category'] = anchor['master_category']
                            pattern['anchor_subcategory'] = anchor['sub_category']

                        all_patterns.extend(patterns)
                        print(f"  [{batch_start + i}/{len(anchors)}] ✅ {anchor['product_display_name'][:40]:40} → {len(patterns)} patterns")

                    except json.JSONDecodeError as e:
                        print(f"  [{batch_start + i}/{len(anchors)}] ⚠️  JSON parse error: {anchor['product_display_name'][:40]}")
                        continue

                # Small delay between requests
                time.sleep(0.5)

            except Exception as e:
                print(f"  [{batch_start + i}/{len(anchors)}] ❌ Error: {str(e)[:60]}")
                continue

        # Checkpoint save after each batch
        if all_patterns and batch_start % 50 == 0:
            checkpoint_file = f"data/outfit_patterns_checkpoint_batch{batch_start}.json"
            with open(checkpoint_file, 'w') as f:
                json.dump(all_patterns, f, indent=2)
            print(f"  💾 Checkpoint saved: {checkpoint_file}")

    # Step 4: Save final patterns
    print(f"\n\n💾 Saving all patterns...")
    output_file = "data/outfit_patterns.json"
    with open(output_file, 'w') as f:
        json.dump(all_patterns, f, indent=2)

    print(f"✅ Saved {len(all_patterns)} patterns to: {output_file}")

    # Step 5: Load into Unity Catalog
    print(f"\n📊 Creating Unity Catalog table...")

    create_table_query = """
    CREATE TABLE IF NOT EXISTS main.fashion_sota.outfit_patterns (
      anchor_id INT,
      anchor_category STRING,
      anchor_subcategory STRING,
      pattern_name STRING,
      pattern_description STRING,
      pattern_json STRING,
      confidence DOUBLE,
      item_count INT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
    )
    """

    execution = w.statement_execution.execute_statement(
        statement=create_table_query,
        warehouse_id="148ccb90800933a1"
    )

    print("✅ Table created: main.fashion_sota.outfit_patterns")
    print("⚠️  Note: Use Spark to bulk load pattern data from JSON")

    # Statistics
    print(f"\n\n" + "=" * 80)
    print("📊 Pattern Generation Summary")
    print("=" * 80)
    print(f"  Total anchors processed:     {len(anchors)}")
    print(f"  Patterns generated:          {len(all_patterns)}")
    print(f"  Avg patterns per anchor:     {len(all_patterns) / len(anchors):.1f}")
    print(f"  Success rate:                {len(all_patterns) / (len(anchors) * 3) * 100:.1f}%")

    # Sample patterns
    if all_patterns:
        print(f"\n\n🔍 Sample Generated Patterns:")
        print("=" * 80)
        for i, pattern in enumerate(all_patterns[:3], 1):
            print(f"\n{i}. {pattern.get('name', 'Unnamed')}")
            print(f"   Anchor: {pattern['anchor_id']} ({pattern['anchor_category']}/{pattern['anchor_subcategory']})")
            print(f"   Items: {len(pattern.get('items', []))}, Confidence: {pattern.get('confidence', 0):.2f}")

    print("\n\n" + "=" * 80)
    print("✅ Phase 2 COMPLETE - Outfit patterns generated with AI Functions")
    print("=" * 80)
    print("\n📝 Next Steps:")
    print("  1. Review patterns in data/outfit_patterns.json")
    print("  2. Run Phase 3: Build PatternPairingService")
    print("  3. Test pattern application on sample products")

    return all_patterns


if __name__ == "__main__":
    print("🚀 Starting pattern generation with AI Functions...\n")
    patterns = generate_patterns_with_ai_functions()

    if patterns:
        print(f"\n✅ SUCCESS - {len(patterns)} patterns ready for application")
    else:
        print(f"\n❌ FAILED - Check AI Functions availability")
