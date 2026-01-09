#!/usr/bin/env python3
"""
Test Lakebase PostgreSQL connection and list tables
"""
import asyncio
import asyncpg
import os

async def test_connection():
    """Test connection to Lakebase and list tables in fashion_sota schema"""

    # Connection parameters from config
    host = "instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net"
    database = "databricks_postgres"
    user = "kevin.ippen@databricks.com"
    port = 5432

    # Get OAuth token
    import subprocess
    import json
    result = subprocess.run(
        ["databricks", "auth", "token", "--host", "https://adb-984752964297111.11.azuredatabricks.net", "--profile", "work"],
        capture_output=True,
        text=True
    )
    token_data = json.loads(result.stdout)
    password = token_data["access_token"]

    print(f"Connecting to Lakebase PostgreSQL...")
    print(f"  Host: {host}")
    print(f"  Database: {database}")
    print(f"  User: {user}")

    try:
        # Connect to Lakebase
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            ssl="require"
        )

        print("✅ Connected successfully!")

        # List all schemas
        print("\n📁 Available schemas:")
        schemas = await conn.fetch("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name")
        for row in schemas:
            print(f"  - {row['schema_name']}")

        # Check if fashion_sota schema exists
        fashion_schemas = [s['schema_name'] for s in schemas if 'fashion' in s['schema_name'].lower()]
        if fashion_schemas:
            print(f"\n🔍 Fashion-related schemas: {fashion_schemas}")

            # List tables in each fashion schema
            for schema in fashion_schemas:
                tables = await conn.fetch("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = $1
                    ORDER BY table_name
                """, schema)

                print(f"\n📊 Tables in {schema} schema:")
                if tables:
                    for row in tables:
                        # Get row count for each table
                        try:
                            count_result = await conn.fetchval(f'SELECT COUNT(*) FROM "{schema}"."{row["table_name"]}"')
                            print(f"  - {row['table_name']} ({count_result:,} rows)")
                        except Exception as e:
                            print(f"  - {row['table_name']} (error counting: {e})")
                else:
                    print("  (no tables found)")
        else:
            print("\n⚠️  No fashion-related schemas found!")

        await conn.close()

    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
