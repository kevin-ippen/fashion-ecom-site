"""
Analyze persona and product data to understand recommendation issues
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import json
import numpy as np

# Get OAuth token
from databricks import sdk
workspace_client = sdk.WorkspaceClient()
token = workspace_client.config.oauth_token().access_token

# Lakebase connection
PGHOST = "instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net"
PGPORT = 5432
PGDATABASE = "databricks_postgres"
PGUSER = "kevin.ippen@databricks.com"

# Build connection string
connection_string = f"postgresql+asyncpg://{PGUSER}:{token}@{PGHOST}:{PGPORT}/{PGDATABASE}"

# Curated persona IDs to analyze
CURATED_PERSONA_IDS = {
    "athletic": "user_001239",
    "budget": "user_008711",
    "casual": "user_001249",
    "formal": "user_001274",
    "luxury": "user_001273",
    "minimalist": "user_001232",
    "trendy": "user_001305",
    "vintage": "user_001289"
}

async def analyze_data():
    """Analyze persona and product data"""
    engine = create_async_engine(connection_string, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("=" * 80)
        print("PERSONA DATA ANALYSIS")
        print("=" * 80)

        # Check each curated user
        for persona_name, user_id in CURATED_PERSONA_IDS.items():
            print(f"\n{'=' * 80}")
            print(f"PERSONA: {persona_name.upper()} ({user_id})")
            print(f"{'=' * 80}")

            # Get user data
            result = await session.execute(text("""
                SELECT
                    user_id,
                    style_profile,
                    preferred_categories,
                    color_prefs,
                    avg_price,
                    min_price,
                    max_price,
                    num_interactions
                FROM fashion_sota.users_lakebase
                WHERE user_id = :user_id
            """), {"user_id": user_id})

            user = result.fetchone()
            if not user:
                print(f"❌ User {user_id} not found!")
                continue

            print(f"\nUser Profile:")
            print(f"  Style: {user[1]}")
            print(f"  Categories: {user[2]}")
            print(f"  Colors: {user[3]}")
            print(f"  Price Range: ${user[5]:.0f} - ${user[6]:.0f} (avg: ${user[4]:.0f})")
            print(f"  Interactions: {user[7]}")

            # Get user embedding
            result = await session.execute(text("""
                SELECT user_embedding
                FROM fashion_sota.users_lakebase
                WHERE user_id = :user_id
            """), {"user_id": user_id})

            embedding_row = result.fetchone()
            if embedding_row and embedding_row[0]:
                embedding = np.array(embedding_row[0], dtype=np.float32)
                norm = np.linalg.norm(embedding)
                print(f"  Embedding: {len(embedding)}-dim, L2 norm = {norm:.4f}")
            else:
                print(f"  ❌ No embedding found!")

        # Check product distribution
        print(f"\n{'=' * 80}")
        print("PRODUCT DATA ANALYSIS")
        print(f"{'=' * 80}")

        # Overall distribution
        print("\n--- Category Distribution ---")
        result = await session.execute(text("""
            SELECT master_category, COUNT(*) as count
            FROM fashion_sota.products_lakebase
            GROUP BY master_category
            ORDER BY count DESC
        """))
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]:,} products")

        # Sub-category distribution (top 30)
        print("\n--- Sub-Category Distribution (Top 30) ---")
        result = await session.execute(text("""
            SELECT sub_category, COUNT(*) as count
            FROM fashion_sota.products_lakebase
            GROUP BY sub_category
            ORDER BY count DESC
            LIMIT 30
        """))
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]:,} products")

        # Check for Indian garments
        print("\n--- Indian Garments Analysis ---")
        result = await session.execute(text("""
            SELECT sub_category, COUNT(*) as count
            FROM fashion_sota.products_lakebase
            WHERE sub_category IN ('Saree', 'Kurta', 'Kurtas', 'Dupatta', 'Churidar', 'Salwar',
                                   'Lehenga Choli', 'Kameez', 'Dhoti', 'Patiala')
            GROUP BY sub_category
            ORDER BY count DESC
        """))
        indian_garments = result.fetchall()
        total_indian = sum(row[1] for row in indian_garments)
        print(f"  Total Indian Garments: {total_indian:,}")
        for row in indian_garments:
            print(f"    {row[0]}: {row[1]:,} products")

        # Check luxury products (price >= 1500)
        print("\n--- Luxury Products (price >= $1500) Analysis ---")
        result = await session.execute(text("""
            SELECT master_category, COUNT(*) as count
            FROM fashion_sota.products_lakebase
            WHERE price >= 1500
            GROUP BY master_category
            ORDER BY count DESC
        """))
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]:,} products")

        result = await session.execute(text("""
            SELECT sub_category, COUNT(*) as count
            FROM fashion_sota.products_lakebase
            WHERE price >= 1500
            GROUP BY sub_category
            ORDER BY count DESC
            LIMIT 20
        """))
        print("\n  Top Sub-Categories:")
        for row in result.fetchall():
            print(f"    {row[0]}: {row[1]:,} products")

        # Check budget products (price < 1500)
        print("\n--- Budget Products (price < $1500) Analysis ---")
        result = await session.execute(text("""
            SELECT master_category, COUNT(*) as count
            FROM fashion_sota.products_lakebase
            WHERE price < 1500
            GROUP BY master_category
            ORDER BY count DESC
        """))
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]:,} products")

        # Check price distribution
        print("\n--- Price Distribution ---")
        result = await session.execute(text("""
            SELECT
                COUNT(*) as total,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY price) as p25,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY price) as p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY price) as p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY price) as p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY price) as p95
            FROM fashion_sota.products_lakebase
        """))
        stats = result.fetchone()
        print(f"  Total Products: {stats[0]:,}")
        print(f"  Price Range: ${stats[1]:.0f} - ${stats[2]:.0f}")
        print(f"  Average: ${stats[3]:.0f}")
        print(f"  P25: ${stats[4]:.0f}")
        print(f"  P50 (Median): ${stats[5]:.0f}")
        print(f"  P75: ${stats[6]:.0f}")
        print(f"  P90: ${stats[7]:.0f}")
        print(f"  P95: ${stats[8]:.0f}")

        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)

asyncio.run(analyze_data())
