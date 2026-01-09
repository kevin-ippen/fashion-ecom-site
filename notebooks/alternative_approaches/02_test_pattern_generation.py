"""
Test Pattern Generation (5 anchors only)

Tests the Llama pattern generation on a small sample before running full batch.
"""

import json
import sys
import importlib.util

# Load the pattern generation module dynamically
spec = importlib.util.spec_from_file_location(
    "generate_patterns",
    "/Users/kevin.ippen/projects/fashion-ecom-site/notebooks/02_generate_outfit_patterns.py"
)
generate_patterns_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_patterns_module)
LlamaPatternGenerator = generate_patterns_module.LlamaPatternGenerator

def test_pattern_generation():
    """Test pattern generation on 5 sample anchors"""

    print("=" * 80)
    print("Testing Pattern Generation (5 anchors)")
    print("=" * 80)

    # Load anchors
    print("\n📂 Loading anchor products...")
    with open("data/anchor_products.json", 'r') as f:
        anchors = json.load(f)

    # Take 5 diverse samples
    test_anchors = anchors[:5]

    print(f"✅ Testing with {len(test_anchors)} sample anchors:\n")
    for anchor in test_anchors:
        print(f"  - {anchor['product_display_name'][:50]}")
        print(f"    {anchor['master_category']}/{anchor['sub_category']} | {anchor['gender']} | {anchor['color_family']}")

    # Initialize generator
    print("\n🤖 Initializing Llama pattern generator...")
    try:
        generator = LlamaPatternGenerator()
        print("✅ Generator initialized")
    except Exception as e:
        print(f"❌ Failed to initialize generator: {e}")
        return False

    # Generate patterns for test anchors
    print(f"\n⏳ Generating patterns...\n")
    all_patterns = []

    for i, anchor in enumerate(test_anchors, 1):
        try:
            print(f"[{i}/{len(test_anchors)}] Processing: {anchor['product_display_name'][:50]}...")
            patterns = generator.generate_patterns(anchor)

            if patterns:
                all_patterns.extend(patterns)
                print(f"  ✅ Generated {len(patterns)} patterns")

                # Show first pattern as sample
                if patterns:
                    p = patterns[0]
                    print(f"     Sample: {p.get('name', 'Unnamed')} (confidence: {p.get('confidence', 0):.2f})")
                    print(f"     Items: {len(p.get('items', []))} item types")
            else:
                print(f"  ⚠️  No patterns generated")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue

    # Summary
    print(f"\n\n" + "=" * 80)
    print("Test Results")
    print("=" * 80)
    print(f"  Anchors tested:              {len(test_anchors)}")
    print(f"  Patterns generated:          {len(all_patterns)}")
    print(f"  Avg patterns per anchor:     {len(all_patterns) / len(test_anchors):.1f}")

    if all_patterns:
        print(f"\n✅ TEST PASSED - Pattern generation working!")
        print(f"\n📋 Sample Pattern Details:")
        print("-" * 80)

        sample = all_patterns[0]
        print(json.dumps(sample, indent=2))

        print(f"\n📝 Ready to run full generation (214 anchors)")
        print(f"   Estimated cost: ~$0.43")
        print(f"   Estimated time: 10-15 minutes")
        print(f"\n   Run: python3 notebooks/02_generate_outfit_patterns.py")
        return True
    else:
        print(f"\n❌ TEST FAILED - No patterns generated")
        print(f"   Check Llama endpoint access and configuration")
        return False


if __name__ == "__main__":
    print("🧪 Starting pattern generation test...\n")
    success = test_pattern_generation()
    sys.exit(0 if success else 1)
