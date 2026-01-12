"""
Create 5 improved personas with meaningful embeddings derived from actual product embeddings.

Strategy: For each persona, sample products matching their style criteria, fetch their
actual FashionCLIP embeddings from the product_embeddings table, and average them to
create a "taste profile" embedding that represents what products this persona likes.

This makes vector search meaningful - the user embedding will be similar to products
they would actually prefer.

Runs locally using Lakebase PostgreSQL + Databricks SQL for embeddings.
"""
import asyncio
import asyncpg
import numpy as np
from databricks import sdk
from databricks.sdk import WorkspaceClient
import json as json_module

# Get OAuth token
workspace_client = sdk.WorkspaceClient()
token = workspace_client.config.oauth_token().access_token

# Lakebase connection details
PGHOST = "instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net"
PGPORT = 5432
PGDATABASE = "databricks_postgres"
PGUSER = "kevin.ippen@databricks.com"

# SQL Warehouse for fetching embeddings
SQL_WAREHOUSE_ID = "148ccb90800933a1"

# 5 high-quality personas (adjusted for actual price range $0-300)
# Each persona has DIVERSE category sampling to avoid footwear-only results
PERSONAS = {
    "luxury": {
        "user_id": "user_luxury_001",
        "style_profile": "luxury",
        "description": "Luxury Fashion Enthusiast",
        "price_range": (200, 300),  # Top 20% of products
        "avg_price": 250,
        "preferred_categories": ["Apparel", "Accessories", "Footwear"],
        # Category weights for sampling (ensures diversity)
        "category_weights": {"Apparel": 0.50, "Accessories": 0.25, "Footwear": 0.25},
        "color_prefs": ["Black", "White", "Grey", "Navy Blue", "Beige"],
        # Sub-category preferences for more specific filtering
        "preferred_subcategories": ["Topwear", "Bottomwear", "Watches", "Bags", "Shoes"],
    },
    "urban_casual": {
        "user_id": "user_casual_002",
        "style_profile": "urban_casual",
        "description": "Urban Casual Style",
        "price_range": (100, 200),  # Middle-high range
        "avg_price": 150,
        "preferred_categories": ["Apparel", "Footwear", "Accessories"],
        "category_weights": {"Apparel": 0.60, "Footwear": 0.25, "Accessories": 0.15},
        "color_prefs": ["Blue", "Black", "White", "Grey", "Olive"],
        "preferred_subcategories": ["Topwear", "Bottomwear", "Shoes", "Flip Flops"],
    },
    "athletic": {
        "user_id": "user_athletic_003",
        "style_profile": "athletic",
        "description": "Athletic Lifestyle",
        "price_range": (80, 180),  # Mid range
        "avg_price": 130,
        "preferred_categories": ["Apparel", "Footwear"],
        "category_weights": {"Apparel": 0.60, "Footwear": 0.40},
        "color_prefs": ["Black", "Grey", "Blue", "Red", "White"],
        "preferred_subcategories": ["Topwear", "Bottomwear", "Sports Shoes", "Shoes"],
    },
    "budget_savvy": {
        "user_id": "user_budget_004",
        "style_profile": "budget_savvy",
        "description": "Budget-Conscious Shopper",
        "price_range": (10, 100),  # Low range
        "avg_price": 55,
        "preferred_categories": ["Apparel", "Footwear", "Accessories"],
        "category_weights": {"Apparel": 0.50, "Footwear": 0.30, "Accessories": 0.20},
        "color_prefs": ["Blue", "Black", "White", "Grey", "Red"],
        "preferred_subcategories": ["Topwear", "Bottomwear", "Flip Flops", "Sandal"],
    },
    "professional": {
        "user_id": "user_professional_005",
        "style_profile": "professional",
        "description": "Business Professional",
        "price_range": (150, 300),  # Upper range
        "avg_price": 225,
        "preferred_categories": ["Apparel", "Accessories", "Footwear"],
        "category_weights": {"Apparel": 0.55, "Accessories": 0.30, "Footwear": 0.15},
        "color_prefs": ["Black", "Navy Blue", "Grey", "White", "Brown"],
        "preferred_subcategories": ["Topwear", "Bottomwear", "Watches", "Belts", "Formal Shoes"],
    },
}

# Excluded Indian garments
EXCLUDED_SUBCATEGORIES = [
    "Saree", "Kurta", "Kurtas", "Dupatta", "Churidar", "Salwar",
    "Lehenga Choli", "Kameez", "Dhoti", "Patiala", "Kurta Sets",
    "Sarees", "Salwar and Dupatta", "Lehenga"
]


async def fetch_product_embeddings(product_ids: list) -> dict:
    """
    Fetch actual product embeddings from Databricks product_embeddings table.

    Args:
        product_ids: List of product IDs to fetch embeddings for

    Returns:
        Dict mapping product_id -> embedding (numpy array)
    """
    if not product_ids:
        return {}

    w = WorkspaceClient()

    # Build query for batch fetch
    ids_str = ",".join([f"'{pid}'" for pid in product_ids])
    query = f"""
    SELECT product_id, embedding
    FROM main.fashion_sota.product_embeddings
    WHERE product_id IN ({ids_str})
    """

    try:
        result = w.statement_execution.execute_statement(
            statement=query,
            warehouse_id=SQL_WAREHOUSE_ID
        )

        embeddings = {}
        if result.result and result.result.data_array:
            for row in result.result.data_array:
                product_id = int(float(row[0]))
                embedding_data = row[1]

                # Parse embedding (stored as array<double> or JSON string)
                if isinstance(embedding_data, str):
                    embedding_list = json_module.loads(embedding_data)
                else:
                    embedding_list = embedding_data

                embeddings[product_id] = np.array(embedding_list, dtype=np.float32)

        return embeddings
    except Exception as e:
        print(f"  ⚠️  Error fetching embeddings: {e}")
        return {}


async def create_personas():
    """Create 5 personas with meaningful embeddings derived from actual products"""
    print("=" * 80)
    print("CREATING 5 IMPROVED PERSONAS WITH REAL EMBEDDINGS")
    print("=" * 80)
    print()
    print("Strategy: Sample products per category → Fetch actual embeddings → Average")
    print()

    # Connect to Lakebase
    conn = await asyncpg.connect(
        host=PGHOST,
        port=PGPORT,
        database=PGDATABASE,
        user=PGUSER,
        password=token
    )

    try:
        for persona_name, config in PERSONAS.items():
            print(f"Creating persona: {persona_name.upper()}")
            print(f"  User ID: {config['user_id']}")
            print(f"  Style: {config['style_profile']}")
            print(f"  Price Range: ${config['price_range'][0]}-${config['price_range'][1]}")
            print()

            min_price, max_price = config['price_range']
            category_weights = config.get('category_weights', {})
            total_samples = 100  # Sample more products for better embedding

            all_product_ids = []

            # Sample products per category based on weights
            for category, weight in category_weights.items():
                num_samples = int(total_samples * weight)

                query = """
                    SELECT product_id
                    FROM fashion_sota.products_lakebase
                    WHERE price >= $1
                      AND price <= $2
                      AND master_category = $3
                      AND sub_category != ALL($4)
                    ORDER BY RANDOM()
                    LIMIT $5
                """

                products = await conn.fetch(
                    query, min_price, max_price, category,
                    EXCLUDED_SUBCATEGORIES, num_samples
                )

                category_ids = [p['product_id'] for p in products]
                all_product_ids.extend(category_ids)
                print(f"  Sampled {len(category_ids)} {category} products (target: {num_samples})")

            print(f"  Total sampled: {len(all_product_ids)} products")

            if not all_product_ids:
                print(f"  ❌ No products found for {persona_name}!")
                continue

            # Fetch actual embeddings from product_embeddings table
            print(f"  Fetching actual product embeddings from Databricks...")
            embeddings_dict = await fetch_product_embeddings(all_product_ids)

            if not embeddings_dict:
                print(f"  ⚠️  No embeddings found, falling back to random embedding")
                taste_embedding = np.random.randn(512).astype(np.float32)
                taste_embedding = taste_embedding / np.linalg.norm(taste_embedding)
            else:
                # Average all embeddings to create taste profile
                embeddings_list = list(embeddings_dict.values())
                taste_embedding = np.mean(embeddings_list, axis=0).astype(np.float32)
                # Normalize to unit length for cosine similarity
                taste_embedding = taste_embedding / np.linalg.norm(taste_embedding)
                print(f"  ✅ Created embedding from {len(embeddings_list)} product embeddings")

            print(f"  Generated {len(taste_embedding)}-dim embedding (L2 norm = {np.linalg.norm(taste_embedding):.6f})")

            # Build color/brand prefs as JSON
            color_prefs = {color: 1.0 / len(config["color_prefs"]) for color in config["color_prefs"]}
            brand_prefs = {}

            # Insert/update user
            await conn.execute("""
                INSERT INTO fashion_sota.users_lakebase (
                    user_id, style_profile, preferred_categories, color_prefs, brand_prefs,
                    min_price, max_price, avg_price, p25_price, p75_price,
                    num_interactions, taste_embedding
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    style_profile = EXCLUDED.style_profile,
                    preferred_categories = EXCLUDED.preferred_categories,
                    color_prefs = EXCLUDED.color_prefs,
                    brand_prefs = EXCLUDED.brand_prefs,
                    min_price = EXCLUDED.min_price,
                    max_price = EXCLUDED.max_price,
                    avg_price = EXCLUDED.avg_price,
                    p25_price = EXCLUDED.p25_price,
                    p75_price = EXCLUDED.p75_price,
                    num_interactions = EXCLUDED.num_interactions,
                    taste_embedding = EXCLUDED.taste_embedding
            """,
                config['user_id'],
                config['style_profile'],
                json_module.dumps(config['preferred_categories']),
                json_module.dumps(color_prefs),
                json_module.dumps(brand_prefs),
                float(config['price_range'][0]),
                float(config['price_range'][1]),
                float(config['avg_price']),
                float(config['avg_price'] * 0.7),
                float(config['avg_price'] * 1.3),
                1000,
                json_module.dumps(taste_embedding.tolist())
            )

            print(f"  ✅ Created/updated {config['user_id']}")
            print()

        # Verify
        print("=" * 80)
        print("VERIFICATION")
        print("=" * 80)
        print()

        for persona_name, config in PERSONAS.items():
            row = await conn.fetchrow("""
                SELECT user_id, style_profile, avg_price
                FROM fashion_sota.users_lakebase
                WHERE user_id = $1
            """, config['user_id'])

            if row:
                # Get embedding to check norm
                emb_row = await conn.fetchrow("""
                    SELECT taste_embedding
                    FROM fashion_sota.users_lakebase
                    WHERE user_id = $1
                """, config['user_id'])

                if emb_row and emb_row['taste_embedding']:
                    # Parse JSON embedding
                    embedding_list = json_module.loads(emb_row['taste_embedding']) if isinstance(emb_row['taste_embedding'], str) else emb_row['taste_embedding']
                    embedding = np.array(embedding_list, dtype=np.float32)
                    norm = np.linalg.norm(embedding)
                    normalized = "✅ NORMALIZED" if abs(norm - 1.0) < 0.01 else "❌ NOT NORMALIZED"

                    print(f"{persona_name}: {row['user_id']}")
                    print(f"  Style: {row['style_profile']}")
                    print(f"  Avg Price: ${row['avg_price']:.0f}")
                    print(f"  Embedding: {len(embedding)}-dim, L2 norm = {norm:.6f} {normalized}")
                    print()

        print("=" * 80)
        print("✅ SUCCESS! 5 personas created/updated in fashion_sota.users_lakebase")
        print("=" * 80)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(create_personas())
