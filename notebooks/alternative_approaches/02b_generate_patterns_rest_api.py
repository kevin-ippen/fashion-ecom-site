"""
Phase 2: Generate Outfit Patterns using Direct REST API

Uses direct REST API calls to Foundation Model endpoints - much faster than ai_query!

Model: databricks-gpt-oss-20b (fast, good quality)
"""

import json
import requests
import time
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()


def generate_patterns_with_rest_api():
    """Generate patterns using direct REST API calls"""

    print("=" * 80)
    print("Phase 2: Generating Outfit Patterns with REST API")
    print("=" * 80)

    # Configuration
    endpoint_url = "https://adb-984752964297111.11.azuredatabricks.net/serving-endpoints/databricks-gpt-oss-20b/invocations"
    token = w.config.oauth_token().access_token

    # Load anchors
    print("\n📂 Loading anchor products...")
    with open("data/anchor_products.json", 'r') as f:
        anchors = json.load(f)

    print(f"✅ Loaded {len(anchors)} anchor products")

    # Generate patterns
    all_patterns = []
    failed_anchors = []

    print(f"\n⏳ Generating patterns for {len(anchors)} anchors...")
    print("Using: databricks-gpt-oss-20b\n")

    for i, anchor in enumerate(anchors, 1):
        try:
            # Build prompt
            prompt = f"""You are a fashion stylist. Generate 3 outfit pairing patterns for this product.

Product: {anchor['product_display_name']}
Category: {anchor['master_category']} / {anchor['sub_category']}
Color: {anchor['base_color']} ({anchor['color_family']} family)
Gender: {anchor['gender']}
Season: {anchor['season']}
Style: {anchor['usage']}
Price: ${anchor['price']:.2f}

For each pattern, specify what item TYPES pair well (not specific products). Include 2-3 items per pattern.

Output ONLY valid JSON in this exact format:
{{
  "patterns": [
    {{
      "name": "Casual Weekend",
      "description": "Relaxed style for casual outings",
      "items": [
        {{
          "role": "bottom",
          "categories": ["Apparel/Bottomwear"],
          "subcategories": ["Jeans", "Chinos"],
          "colors": ["Navy", "Black", "Khaki"],
          "required": true,
          "style": "Casual"
        }},
        {{
          "role": "footwear",
          "categories": ["Footwear/Shoes"],
          "subcategories": ["Sneakers", "Casual Shoes"],
          "colors": ["White", "Black"],
          "required": true,
          "style": "Casual"
        }}
      ],
      "confidence": 0.85
    }}
  ]
}}

Important:
- Output ONLY the JSON object, no other text
- No markdown code blocks
- Match gender (men's with men's)
- Match style (casual with casual, formal with formal)
- Choose compatible colors"""

            # Call API
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional fashion stylist. Always respond with valid JSON only, no other text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 1500,
                "temperature": 0.7
            }

            response = requests.post(endpoint_url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()

                # Extract content
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']

                    # Parse patterns from response
                    # Handle reasoning + text format
                    if isinstance(content, list):
                        # Find the text part
                        for item in content:
                            if item.get('type') == 'text':
                                content = item['text']
                                break

                    # Clean response
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()

                    # Parse JSON
                    try:
                        data = json.loads(content)
                        patterns = data.get('patterns', [])

                        # Add anchor metadata
                        for pattern in patterns:
                            pattern['anchor_id'] = anchor['product_id']
                            pattern['anchor_category'] = anchor['master_category']
                            pattern['anchor_subcategory'] = anchor['sub_category']

                        all_patterns.extend(patterns)

                        print(f"  [{i}/{len(anchors)}] ✅ {anchor['product_display_name'][:45]:45} → {len(patterns)} patterns")

                    except json.JSONDecodeError as e:
                        print(f"  [{i}/{len(anchors)}] ⚠️  JSON parse error: {anchor['product_display_name'][:45]}")
                        # print(f"      Content preview: {content[:100]}")
                        failed_anchors.append(anchor['product_id'])

                else:
                    print(f"  [{i}/{len(anchors)}] ⚠️  No content: {anchor['product_display_name'][:45]}")
                    failed_anchors.append(anchor['product_id'])

            else:
                print(f"  [{i}/{len(anchors)}] ❌ API error {response.status_code}: {anchor['product_display_name'][:45]}")
                failed_anchors.append(anchor['product_id'])

            # Rate limiting
            if i % 10 == 0:
                time.sleep(1)

            # Checkpoint every 50
            if i % 50 == 0:
                checkpoint_file = f"data/patterns_checkpoint_{i}.json"
                with open(checkpoint_file, 'w') as f:
                    json.dump(all_patterns, f, indent=2)
                print(f"  💾 Checkpoint saved: {checkpoint_file}")

        except Exception as e:
            print(f"  [{i}/{len(anchors)}] ❌ Exception: {str(e)[:60]}")
            failed_anchors.append(anchor['product_id'])
            continue

    # Save final patterns
    print(f"\n\n💾 Saving all patterns...")
    output_file = "data/outfit_patterns.json"
    with open(output_file, 'w') as f:
        json.dump(all_patterns, f, indent=2)

    print(f"✅ Saved {len(all_patterns)} patterns to: {output_file}")

    # Statistics
    print(f"\n\n" + "=" * 80)
    print("📊 Pattern Generation Summary")
    print("=" * 80)
    print(f"  Total anchors processed:     {len(anchors)}")
    print(f"  Successful:                  {len(anchors) - len(failed_anchors)}")
    print(f"  Failed:                      {len(failed_anchors)}")
    print(f"  Total patterns generated:    {len(all_patterns)}")
    print(f"  Avg patterns per anchor:     {len(all_patterns) / len(anchors):.1f}")
    print(f"  Success rate:                {(len(anchors) - len(failed_anchors)) / len(anchors) * 100:.1f}%")

    if failed_anchors:
        print(f"\n⚠️  Failed anchor IDs ({len(failed_anchors)}): {failed_anchors[:10]}{'...' if len(failed_anchors) > 10 else ''}")

    # Sample patterns
    if all_patterns:
        print(f"\n\n🔍 Sample Generated Patterns:")
        print("=" * 80)
        for i, pattern in enumerate(all_patterns[:3], 1):
            print(f"\n{i}. {pattern.get('name', 'Unnamed')}")
            print(f"   Anchor: {pattern['anchor_id']} ({pattern['anchor_category']}/{pattern['anchor_subcategory']})")
            print(f"   Description: {pattern.get('description', 'N/A')[:60]}")
            print(f"   Items: {len(pattern.get('items', []))}")
            print(f"   Confidence: {pattern.get('confidence', 0):.2f}")

    print("\n\n" + "=" * 80)
    print("✅ Phase 2 COMPLETE - Outfit patterns generated")
    print("=" * 80)
    print("\n📝 Next Steps:")
    print("  1. Review patterns in data/outfit_patterns.json")
    print("  2. Run Phase 3: Build PatternPairingService")
    print("  3. Apply patterns to remaining products")

    return all_patterns


if __name__ == "__main__":
    print("🚀 Starting pattern generation with REST API...\n")
    patterns = generate_patterns_with_rest_api()

    if patterns:
        print(f"\n✅ SUCCESS - {len(patterns)} patterns ready for application")
    else:
        print(f"\n❌ FAILED - No patterns generated")
