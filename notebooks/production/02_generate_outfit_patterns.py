"""
Phase 2: Generate Outfit Patterns with Llama 3.1 70B

For each anchor product, generate 3-7 reusable outfit patterns.
Patterns define RULES for what pairs well, not specific products.

Cost: 214 anchors × $0.002 = ~$0.43
Time: ~10-15 minutes
"""

import json
import requests
from databricks.sdk import WorkspaceClient
from typing import List, Dict, Any
import time

w = WorkspaceClient()


class LlamaPatternGenerator:
    """Generate outfit patterns using Llama 3.1 70B"""

    def __init__(self):
        self.workspace_host = w.config.host
        self.token = w.config.oauth_token().access_token

        # Llama 3.1 70B endpoint (Foundation Models API)
        # Replace with your actual endpoint name if different
        self.endpoint_name = "databricks-meta-llama-3-1-70b-instruct"
        self.endpoint_url = f"{self.workspace_host}/serving-endpoints/{self.endpoint_name}/invocations"

    def generate_patterns(self, anchor: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate outfit patterns for an anchor product

        Args:
            anchor: Anchor product dict with attributes

        Returns:
            List of outfit pattern dicts
        """

        # Build prompt
        prompt = self._build_prompt(anchor)

        # Call Llama 3.1 70B
        try:
            response = self._call_llama(prompt)
            patterns = self._parse_response(response, anchor)
            return patterns

        except Exception as e:
            print(f"❌ Error generating patterns for {anchor['product_id']}: {e}")
            return []

    def _build_prompt(self, anchor: Dict[str, Any]) -> str:
        """Build prompt for pattern generation"""

        prompt = f"""You are a professional fashion stylist. Generate outfit pairing patterns for this product.

Product Details:
- ID: {anchor['product_id']}
- Name: {anchor['product_display_name']}
- Category: {anchor['master_category']} / {anchor['sub_category']}
- Color: {anchor['base_color']} ({anchor['color_family']} family)
- Gender: {anchor['gender']}
- Season: {anchor['season']}
- Style: {anchor['usage']}
- Price: ${anchor['price']:.2f} ({anchor['price_tier']} tier)

Generate 3-5 outfit patterns that would work well with this product. Each pattern should specify:
1. What types of items pair well (categories, not specific products)
2. Compatible colors for each item type
3. Whether each item is required or optional
4. Style consistency (casual with casual, formal with formal)

Output ONLY valid JSON (no markdown, no explanation), in this exact format:

{{
  "patterns": [
    {{
      "name": "Pattern name (2-4 words)",
      "description": "Brief description of the outfit style",
      "items": [
        {{
          "role": "bottom|footwear|accessory",
          "required": true|false,
          "categories": ["Category/Subcategory", "Category/Subcategory"],
          "colors": ["Color1", "Color2", "Color3"],
          "style": "Casual|Formal|Sports|Party",
          "notes": "Brief styling notes"
        }}
      ],
      "confidence": 0.7-1.0
    }}
  ]
}}

Rules:
- Focus on patterns that apply to ANY product like this one, not just this specific product
- Include 2-4 items per pattern (don't need full outfit, just key pairs)
- Be specific about categories (e.g., "Apparel/Bottomwear" or "Footwear/Sneakers")
- Choose compatible colors (neutrals go with everything, avoid clashing combos)
- Match style consistency (casual items with casual items)
- Set confidence based on how universal the pattern is (0.7-1.0)

Important: Return ONLY the JSON object, nothing else."""

        return prompt

    def _call_llama(self, prompt: str) -> str:
        """Call Llama 3.1 70B endpoint"""

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional fashion stylist who creates outfit pairing rules. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.7
        }

        response = requests.post(
            self.endpoint_url,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            raise Exception(f"Llama API error: {response.status_code} - {response.text}")

        result = response.json()

        # Extract response text (format varies by endpoint)
        if "choices" in result:
            return result["choices"][0]["message"]["content"]
        elif "predictions" in result:
            return result["predictions"][0]["candidates"][0]["text"]
        else:
            raise Exception(f"Unexpected response format: {result}")

    def _parse_response(self, response: str, anchor: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Llama response into pattern dicts"""

        try:
            # Remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            # Parse JSON
            data = json.loads(response)

            # Extract patterns
            if "patterns" in data:
                patterns = data["patterns"]
            else:
                patterns = [data]  # Single pattern case

            # Add anchor reference
            for pattern in patterns:
                pattern["anchor_id"] = anchor["product_id"]
                pattern["anchor_category"] = anchor["master_category"]
                pattern["anchor_subcategory"] = anchor["sub_category"]

            return patterns

        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parse error for anchor {anchor['product_id']}: {e}")
            print(f"Response: {response[:200]}...")
            return []


def generate_all_patterns():
    """Generate patterns for all anchor products"""

    print("=" * 80)
    print("Phase 2: Generating Outfit Patterns with Llama 3.1 70B")
    print("=" * 80)

    # Load anchors
    print("\n📂 Loading anchor products...")
    with open("data/anchor_products.json", 'r') as f:
        anchors = json.load(f)

    print(f"✅ Loaded {len(anchors)} anchor products")

    # Initialize generator
    print("\n🤖 Initializing Llama 3.1 70B pattern generator...")
    generator = LlamaPatternGenerator()

    # Generate patterns
    all_patterns = []
    failed_anchors = []

    print(f"\n⏳ Generating patterns for {len(anchors)} anchors...")
    print("This will take ~10-15 minutes...\n")

    for i, anchor in enumerate(anchors, 1):
        try:
            # Generate patterns
            patterns = generator.generate_patterns(anchor)

            if patterns:
                all_patterns.extend(patterns)
                print(f"✅ [{i}/{len(anchors)}] Generated {len(patterns)} patterns for: {anchor['product_display_name'][:50]}")
            else:
                print(f"⚠️  [{i}/{len(anchors)}] No patterns generated for: {anchor['product_display_name'][:50]}")
                failed_anchors.append(anchor['product_id'])

            # Rate limiting (if needed)
            if i % 10 == 0:
                time.sleep(1)  # Brief pause every 10 requests

        except Exception as e:
            print(f"❌ [{i}/{len(anchors)}] Error for anchor {anchor['product_id']}: {e}")
            failed_anchors.append(anchor['product_id'])
            continue

    # Save patterns
    print(f"\n\n💾 Saving patterns...")
    output_file = "data/outfit_patterns.json"
    with open(output_file, 'w') as f:
        json.dump(all_patterns, f, indent=2)

    print(f"✅ Saved {len(all_patterns)} patterns to: {output_file}")

    # Save to Unity Catalog table
    print(f"\n📊 Writing patterns to Unity Catalog...")

    # Prepare data for insertion
    patterns_data = []
    for pattern in all_patterns:
        patterns_data.append({
            "anchor_id": pattern["anchor_id"],
            "anchor_category": pattern["anchor_category"],
            "anchor_subcategory": pattern["anchor_subcategory"],
            "pattern_name": pattern.get("name", "Unnamed Pattern"),
            "pattern_description": pattern.get("description", ""),
            "pattern_json": json.dumps(pattern),
            "confidence": pattern.get("confidence", 0.7),
            "item_count": len(pattern.get("items", []))
        })

    # Create table with patterns
    create_table_query = f"""
    CREATE OR REPLACE TABLE main.fashion_sota.outfit_patterns (
      anchor_id INT,
      anchor_category STRING,
      anchor_subcategory STRING,
      pattern_name STRING,
      pattern_description STRING,
      pattern_json STRING,
      confidence DOUBLE,
      item_count INT
    )
    """

    execution = w.statement_execution.execute_statement(
        statement=create_table_query,
        warehouse_id="148ccb90800933a1"
    )

    # Note: For actual data insertion, you'd want to use Spark or bulk insert
    # This is a placeholder - in production, use Spark DataFrame or COPY INTO
    print("✅ Table created: main.fashion_sota.outfit_patterns")
    print("⚠️  Note: Pattern data saved to JSON. Use Spark to bulk load into table.")

    # Statistics
    print(f"\n\n" + "=" * 80)
    print("📊 Pattern Generation Summary")
    print("=" * 80)
    print(f"  Total anchors processed:     {len(anchors)}")
    print(f"  Successful:                  {len(anchors) - len(failed_anchors)}")
    print(f"  Failed:                      {len(failed_anchors)}")
    print(f"  Total patterns generated:    {len(all_patterns)}")
    print(f"  Avg patterns per anchor:     {len(all_patterns) / len(anchors):.1f}")

    if failed_anchors:
        print(f"\n⚠️  Failed anchor IDs: {failed_anchors[:10]}{'...' if len(failed_anchors) > 10 else ''}")

    # Sample patterns
    print(f"\n\n🔍 Sample Generated Patterns:")
    print("=" * 80)
    for i, pattern in enumerate(all_patterns[:3], 1):
        print(f"\n{i}. Pattern: {pattern.get('name', 'Unnamed')}")
        print(f"   Anchor: {pattern['anchor_id']} ({pattern['anchor_category']}/{pattern['anchor_subcategory']})")
        print(f"   Description: {pattern.get('description', 'N/A')[:60]}")
        print(f"   Items: {len(pattern.get('items', []))}")
        print(f"   Confidence: {pattern.get('confidence', 0):.2f}")

    print("\n\n" + "=" * 80)
    print("✅ Phase 2 COMPLETE - Outfit patterns generated")
    print("=" * 80)
    print("\n📝 Next Steps:")
    print("  1. Review sample patterns above")
    print("  2. Run Phase 3: Build PatternPairingService")
    print(f"  3. Patterns available in: {output_file}")

    return all_patterns


if __name__ == "__main__":
    print("🚀 Starting outfit pattern generation...\n")
    patterns = generate_all_patterns()
    print(f"\n✅ SUCCESS - {len(patterns)} patterns ready for application")
