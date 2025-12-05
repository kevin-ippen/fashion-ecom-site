
#!/usr/bin/env python3
"""
Integration test script for CLIP + Vector Search + Recommendations
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from services.clip_service import clip_service
from services.vector_search_service import vector_search_service
from services.recommendation_service import recommendation_service
from repositories.lakebase import lakebase_repo
import numpy as np


def test_clip_service():
    """Test CLIP service with a sample image"""
    print("\n=== Testing CLIP Service ===")
    
    products = lakebase_repo.get_products(limit=1)
    if not products:
        print("❌ No products found")
        return False
    
    sample_product = products[0]
    image_path = f'/Volumes/main/fashion_demo/raw_data/images/{sample_product["image_path"]}'
    
    print(f"Testing with image: {image_path}")
    
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        embedding = clip_service.get_embedding(image_bytes)
        
        print(f"✅ CLIP embedding generated: shape={embedding.shape}, dtype={embedding.dtype}")
        print(f"   Sample values: {embedding[:5]}")
        return True
        
    except Exception as e:
        print(f"❌ CLIP service failed: {e}")
        return False


def test_vector_search():
    """Test Vector Search"""
    print("\n=== Testing Vector Search ===")
    
    try:
        embeddings = lakebase_repo.get_product_embeddings()
        if not embeddings:
            print("❌ No embeddings found")
            return False
        
        sample_embedding = np.array(embeddings[0]['image_embedding'])
        print(f"Using sample embedding: shape={sample_embedding.shape}")
        
        results = vector_search_service.similarity_search(
            query_vector=sample_embedding,
            num_results=5
        )
        
        print(f"✅ Vector Search returned {len(results)} results")
        for i, result in enumerate(results[:3]):
            print(f"   {i+1}. Product ID: {result['product_id']}, Score: {result['score']:.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Vector Search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_end_to_end():
    """Test complete flow"""
    print("\n=== Testing End-to-End Flow ===")
    
    try:
        # Step 1: Get sample image
        products = lakebase_repo.get_products(limit=1)
        sample_product = products[0]
        image_path = f'/Volumes/main/fashion_demo/raw_data/images/{sample_product["image_path"]}'
        
        print(f"1. Loading image: {sample_product['product_display_name']}")
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        # Step 2: Generate embedding
        print("2. Generating CLIP embedding...")
        embedding = clip_service.get_embedding(image_bytes)
        
        # Step 3: Vector search
        print("3. Performing vector search...")
        search_results = vector_search_service.similarity_search(
            query_vector=embedding,
            num_results=10
        )
        
        # Step 4: Fetch product details
        print("4. Fetching product details...")
        product_ids = [r['product_id'] for r in search_results]
        scores = [r['score'] for r in search_results]
        
        products_data = []
        for product_id in product_ids:
            product = lakebase_repo.get_product_by_id(str(product_id))
            if product:
                products_data.append(product)
        
        # Step 5: Score with recommendations
        print("5. Scoring with recommendation service...")
        users = lakebase_repo.get_users()
        user_features = lakebase_repo.get_user_style_features(users[0]['user_id'])
        
        scored_products = recommendation_service.score_products(
            products=products_data,
            visual_scores=scores,
            user_preferences=user_features
        )
        
        print(f"\n✅ End-to-end test successful!")
        print(f"   Query image: {sample_product['product_display_name']}")
        print(f"   Found {len(scored_products)} similar products")
        print("\n   Top 5 matches:")
        for i, product in enumerate(scored_products[:5]):
            print(f"   {i+1}. {product['product_display_name']} (score: {product['final_score']:.3f})")
        
        return True
        
    except Exception as e:
        print(f"❌ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Fashion Ecom Site - Integration Tests")
    print("="*60)
    
    results = {
        "CLIP Service": test_clip_service(),
        "Vector Search": test_vector_search(),
        "End-to-End": test_end_to_end()
    }
    
    print("\n" + "="*60)
    print("Test Results Summary")
    print("="*60)
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:20s} {status}")
    
    all_passed = all(results.values())
    print("\n" + ("="*60))
    if all_passed:
        print("✅ All tests passed! Integration is working correctly.")
    else:
        print("❌ Some tests failed. Please review the errors above.")
    print("="*60 + "\n")
