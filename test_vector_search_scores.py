"""
Diagnostic script to test Vector Search score parsing
Run this in the Databricks App environment to verify data formats
"""
import asyncio
import numpy as np
from services.vector_search_service import VectorSearchService
from services.clip_service import CLIPService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_search_scores():
    """Test Vector Search and verify score extraction"""

    print("=" * 80)
    print("VECTOR SEARCH SCORE DIAGNOSTIC")
    print("=" * 80)

    # Initialize services
    clip_service = CLIPService()
    vs_service = VectorSearchService()

    # Test 1: Generate text embedding
    print("\n1. Testing CLIP Text Embedding")
    print("-" * 80)
    text = "red dress"
    print(f"Query: '{text}'")

    try:
        embedding = await clip_service.get_text_embedding(text)
        print(f"✅ Generated embedding: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}")
        print(f"First 5 values: {embedding[:5]}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # Test 2: Search hybrid index
    print("\n2. Testing Vector Search (Hybrid Index)")
    print("-" * 80)

    try:
        results = await vs_service.search_hybrid(
            query_vector=embedding,
            num_results=5,
            filters=None
        )

        print(f"✅ Got {len(results)} results")

        if results:
            print("\nResult Details:")
            for i, product in enumerate(results[:5], 1):
                score = product.get("score", "MISSING")
                product_id = product.get("product_id")
                name = product.get("product_display_name", "")[:50]

                print(f"\n  Result {i}:")
                print(f"    Product ID: {product_id}")
                print(f"    Name: {name}")
                print(f"    Score: {score}")
                print(f"    Score Type: {type(score)}")

                if score != "MISSING":
                    print(f"    ✅ Score exists!")
                else:
                    print(f"    ❌ Score is MISSING!")
                    print(f"    Available keys: {list(product.keys())}")

            # Check if all scores are the same
            scores = [p.get("score") for p in results if p.get("score") is not None]
            if scores:
                unique_scores = set(scores)
                print(f"\n  Unique scores: {len(unique_scores)}")
                print(f"  Score range: {min(scores):.4f} to {max(scores):.4f}")

                if len(unique_scores) == 1:
                    print(f"  ⚠️  WARNING: All products have the same score!")
                else:
                    print(f"  ✅ Scores vary across products")
        else:
            print("❌ No results returned")

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Raw Vector Search response inspection
    print("\n3. Inspecting Raw Vector Search Response")
    print("-" * 80)

    try:
        # Get index directly
        index = vs_service._get_index(vs_service.hybrid_index)

        # Define columns
        columns = [
            "product_id",
            "product_display_name",
            "master_category",
            "price"
        ]

        # Query directly
        raw_results = index.similarity_search(
            query_vector=embedding.tolist(),
            columns=columns,
            num_results=3
        )

        print(f"Raw response keys: {raw_results.keys()}")

        if "result" in raw_results:
            result = raw_results["result"]
            print(f"Result keys: {result.keys()}")

            if "data_array" in result:
                data_array = result["data_array"]
                print(f"Number of rows: {len(data_array)}")

                if data_array:
                    print(f"\nFirst row:")
                    row = data_array[0]
                    print(f"  Row length: {len(row)}")
                    print(f"  Columns requested: {len(columns)}")
                    print(f"  Row values: {row}")

                    if len(row) > len(columns):
                        print(f"\n  ✅ Row has extra element (likely score)")
                        print(f"  Last element (score): {row[-1]} (type: {type(row[-1])})")
                    else:
                        print(f"\n  ❌ Row length matches columns - no score appended!")

            if "manifest" in raw_results:
                manifest = raw_results["manifest"]
                if "columns" in manifest:
                    manifest_cols = [c["name"] for c in manifest["columns"]]
                    print(f"\nManifest columns: {manifest_cols}")

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_search_scores())
