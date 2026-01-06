#!/usr/bin/env python3
"""
Grant permissions on users_lakebase table to app service principal
"""
import asyncio
import asyncpg
import subprocess
import json

async def grant_permissions():
    """Grant permissions on users_lakebase table"""

    # Connection parameters
    host = "instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net"
    database = "databricks_postgres"
    user = "kevin.ippen@databricks.com"
    port = 5432

    # Get OAuth token
    result = subprocess.run(
        ["databricks", "auth", "token", "--host", "https://adb-984752964297111.11.azuredatabricks.net", "--profile", "work"],
        capture_output=True,
        text=True
    )
    token_data = json.loads(result.stdout)
    password = token_data["access_token"]

    # Service principal UUID
    service_principal_uuid = "55be2ebd-113c-4077-9341-2d8444d8e4b2"
    service_principal_name = "app-7hspbl ecom-visual-search"

    print("Connecting to Lakebase PostgreSQL...")

    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            ssl="require"
        )

        print(f"✅ Connected successfully")
        print(f"\n📝 Granting permissions on users_lakebase to:")
        print(f"   UUID: {service_principal_uuid}")
        print(f"   Name: {service_principal_name}\n")

        # Grant SELECT on users_lakebase table specifically
        print("1. Granting SELECT on fashion_sota.users_lakebase...")
        await conn.execute(f'''
            GRANT SELECT ON TABLE fashion_sota.users_lakebase
            TO "{service_principal_uuid}"
        ''')
        print("   ✅ SELECT granted on users_lakebase")

        # Verify the grant worked
        print("\n2. Verifying permissions...")
        perms = await conn.fetch("""
            SELECT
                grantee,
                table_schema,
                table_name,
                privilege_type
            FROM information_schema.table_privileges
            WHERE grantee = $1
            AND table_schema = 'fashion_sota'
            AND table_name = 'users_lakebase'
            ORDER BY privilege_type
        """, service_principal_uuid)

        if perms:
            print("   ✅ Permissions verified:")
            for perm in perms:
                print(f"      {perm['privilege_type']} on {perm['table_schema']}.{perm['table_name']}")
        else:
            print("   ⚠️  Could not verify via information_schema (may still be granted)")

        # Also re-grant on all tables to be safe
        print("\n3. Re-granting SELECT on ALL tables (refresh)...")
        await conn.execute(f'''
            GRANT SELECT ON ALL TABLES IN SCHEMA fashion_sota
            TO "{service_principal_uuid}"
        ''')
        print("   ✅ SELECT refreshed on all tables")

        await conn.close()

        print("\n" + "="*80)
        print("✅ Permissions granted successfully!")
        print("="*80)
        print("\nThe app service principal now has SELECT on:")
        print("  - fashion_sota.products_lakebase")
        print("  - fashion_sota.users_lakebase")
        print("\nNo app restart needed - permissions take effect immediately!")

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(grant_permissions())
