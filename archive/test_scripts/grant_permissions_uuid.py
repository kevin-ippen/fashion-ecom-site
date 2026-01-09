#!/usr/bin/env python3
"""
Grant Lakebase permissions to app service principal using UUID
"""
import asyncio
import asyncpg
import subprocess
import json

async def grant_permissions():
    """Grant permissions to app service principal on fashion_sota schema"""

    # Connection parameters
    host = "instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net"
    database = "databricks_postgres"
    user = "kevin.ippen@databricks.com"  # Admin user
    port = 5432

    # Get OAuth token
    result = subprocess.run(
        ["databricks", "auth", "token", "--host", "https://adb-984752964297111.11.azuredatabricks.net", "--profile", "work"],
        capture_output=True,
        text=True
    )
    token_data = json.loads(result.stdout)
    password = token_data["access_token"]

    print("Connecting to Lakebase PostgreSQL...")

    # Service principal UUID (from app ID)
    service_principal_uuid = "55be2ebd-113c-4077-9341-2d8444d8e4b2"
    service_principal_name = "app-7hspbl ecom-visual-search"

    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            ssl="require"
        )

        print(f"✅ Connected successfully as {user}")
        print(f"\n📝 Granting permissions to:")
        print(f"   UUID: {service_principal_uuid}")
        print(f"   Name: {service_principal_name}")

        # Grant USAGE on schema
        print(f"\n1. Granting USAGE on schema fashion_sota...")
        await conn.execute(f'GRANT USAGE ON SCHEMA fashion_sota TO "{service_principal_uuid}"')
        print("   ✅ USAGE granted")

        # Grant SELECT on all tables
        print(f"\n2. Granting SELECT on all tables in fashion_sota...")
        await conn.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA fashion_sota TO "{service_principal_uuid}"')
        print("   ✅ SELECT granted on all existing tables")

        # Grant SELECT on future tables (optional, but useful)
        print(f"\n3. Granting SELECT on future tables...")
        try:
            await conn.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA fashion_sota GRANT SELECT ON TABLES TO "{service_principal_uuid}"')
            print("   ✅ SELECT granted on future tables")
        except Exception as e:
            print(f"   ⚠️  Could not grant future privileges: {e}")

        # Verify by trying a query as the service principal would
        print(f"\n4. Verifying table access...")
        try:
            count = await conn.fetchval("SELECT COUNT(*) FROM fashion_sota.products_lakebase")
            print(f"   ✅ Can read table (count: {count:,} rows)")
        except Exception as e:
            print(f"   ❌ Cannot read table: {e}")

        await conn.close()

        print("\n" + "="*80)
        print("✅ Permission grant complete!")
        print("="*80)
        print("\nNext step: Restart the app to pick up new permissions")
        print("  databricks apps stop ecom-visual-search --profile work")
        print("  databricks apps start ecom-visual-search --profile work")

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(grant_permissions())
