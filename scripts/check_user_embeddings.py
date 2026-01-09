"""
Check user embedding status in database
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os
import json

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

async def check_embeddings():
    """Check user embedding status"""
    engine = create_async_engine(connection_string, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check usersdb table
        print("=== Checking fashion_demo.usersdb ===")
        result = await session.execute(text("""
            SELECT
                user_id,
                segment,
                num_interactions
            FROM fashion_demo.usersdb
            ORDER BY user_id
            LIMIT 10
        """))
        users = result.fetchall()
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"  - {user[0]}: {user[1]} ({user[2]} interactions)")

        # Check user_style_featuresdb table
        print("\n=== Checking fashion_demo.user_style_featuresdb ===")
        result = await session.execute(text("""
            SELECT
                user_id,
                segment,
                CASE
                    WHEN user_embedding IS NULL THEN 'NO EMBEDDING'
                    ELSE 'HAS EMBEDDING'
                END as embedding_status,
                num_interactions
            FROM fashion_demo.user_style_featuresdb
            WHERE user_id IN (
                SELECT user_id FROM fashion_demo.usersdb LIMIT 10
            )
            ORDER BY user_id
        """))
        features = result.fetchall()
        print(f"Found {len(features)} users with style features:")
        for feature in features:
            print(f"  - {feature[0]}: {feature[1]} - {feature[2]} ({feature[3]} interactions)")

        # Check if embeddings exist
        result = await session.execute(text("""
            SELECT
                COUNT(*) as total_users,
                COUNT(user_embedding) as users_with_embedding
            FROM fashion_demo.user_style_featuresdb
        """))
        counts = result.fetchone()
        print(f"\n=== Summary ===")
        print(f"Total users in user_style_featuresdb: {counts[0]}")
        print(f"Users with embeddings: {counts[1]}")
        print(f"Coverage: {counts[1]/counts[0]*100:.1f}%")

        # Sample an embedding
        print("\n=== Sample Embedding ===")
        result = await session.execute(text("""
            SELECT
                user_id,
                user_embedding
            FROM fashion_demo.user_style_featuresdb
            WHERE user_embedding IS NOT NULL
            LIMIT 1
        """))
        sample = result.fetchone()
        if sample:
            print(f"User: {sample[0]}")
            embedding = sample[1]
            if isinstance(embedding, str):
                embedding = json.loads(embedding)
            print(f"Embedding type: {type(embedding)}")
            print(f"Embedding length: {len(embedding) if embedding else 0}")
            if embedding:
                print(f"First 5 values: {embedding[:5]}")

asyncio.run(check_embeddings())
