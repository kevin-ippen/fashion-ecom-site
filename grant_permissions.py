#!/usr/bin/env python3
"""
Grant Lakebase permissions to app service principal
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

    # Service principal name from app
    service_principal = "app-7hspbl ecom-visual-search"

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
        print(f"\n📝 Granting permissions to: {service_principal}")

        # Grant USAGE on schema
        print(f"\n1. Granting USAGE on schema fashion_sota...")
        await conn.execute(f'GRANT USAGE ON SCHEMA fashion_sota TO "{service_principal}"')
        print("   ✅ USAGE granted")

        # Grant SELECT on all tables
        print(f"\n2. Granting SELECT on all tables in fashion_sota...")
        await conn.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA fashion_sota TO "{service_principal}"')
        print("   ✅ SELECT granted on all existing tables")

        # Grant SELECT on future tables (optional, but useful)
        print(f"\n3. Granting SELECT on future tables...")
        await conn.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA fashion_sota GRANT SELECT ON TABLES TO "{service_principal}"')
        print("   ✅ SELECT granted on future tables")

        # Verify permissions
        print(f"\n4. Verifying permissions...")
        perms = await conn.fetch("""
            SELECT
                grantee,
                privilege_type,
                table_schema,
                table_name
            FROM information_schema.table_privileges
            WHERE grantee = $1 AND table_schema = 'fashion_sota'
            ORDER BY table_name, privilege_type
        """, service_principal)

        if perms:
            print(f"\n✅ Permissions granted successfully:")
            for perm in perms:
                print(f"   - {perm['privilege_type']} on {perm['table_schema']}.{perm['table_name']}")
        else:
            print("\n⚠️  No table-level permissions found in information_schema")
            print("   (Schema-level USAGE may still be granted)")

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
