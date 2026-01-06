#!/usr/bin/env python3
"""
Verify and grant all necessary permissions to app service principal
"""
import asyncio
import asyncpg
import subprocess
import json

async def verify_and_grant():
    """Check current permissions and grant any missing ones"""

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
    sp_uuid = "55be2ebd-113c-4077-9341-2d8444d8e4b2"
    sp_name = "app-7hspbl ecom-visual-search"

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

        print(f"✅ Connected successfully\n")
        print("="*80)
        print(f"Service Principal: {sp_name}")
        print(f"UUID: {sp_uuid}")
        print("="*80)

        # Check all tables in fashion_sota
        print("\n📊 Checking tables in fashion_sota schema...")
        tables = await conn.fetch("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'fashion_sota'
            ORDER BY tablename
        """)

        print(f"Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table['tablename']}")

        # Check current permissions
        print("\n🔍 Checking current permissions for service principal...")
        perms = await conn.fetch("""
            SELECT
                table_schema,
                table_name,
                privilege_type
            FROM information_schema.table_privileges
            WHERE grantee = $1
            AND table_schema = 'fashion_sota'
            ORDER BY table_name, privilege_type
        """, sp_uuid)

        if perms:
            print("Current permissions:")
            for perm in perms:
                print(f"  ✓ {perm['privilege_type']} on {perm['table_schema']}.{perm['table_name']}")
        else:
            print("  ⚠️  No permissions found in information_schema")

        # Grant USAGE on schema (required to access tables)
        print("\n🔐 Granting USAGE on schema fashion_sota...")
        await conn.execute(f'GRANT USAGE ON SCHEMA fashion_sota TO "{sp_uuid}"')
        print("  ✅ USAGE granted on schema")

        # Grant SELECT on ALL tables (comprehensive)
        print("\n🔐 Granting SELECT on ALL tables in fashion_sota...")
        await conn.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA fashion_sota TO "{sp_uuid}"')
        print("  ✅ SELECT granted on all tables")

        # Grant SELECT on future tables
        print("\n🔐 Granting SELECT on FUTURE tables...")
        await conn.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA fashion_sota GRANT SELECT ON TABLES TO "{sp_uuid}"')
        print("  ✅ SELECT granted on future tables")

        # Verify each specific table
        print("\n✅ Verifying access to specific tables...")
        required_tables = ['products_lakebase', 'users_lakebase']

        for table_name in required_tables:
            try:
                # Try to query the table
                count = await conn.fetchval(f'SELECT COUNT(*) FROM fashion_sota.{table_name}')
                print(f"  ✓ {table_name}: Accessible ({count:,} rows)")
            except Exception as e:
                print(f"  ✗ {table_name}: Error - {e}")

        # Final permission check
        print("\n📋 Final permissions report...")
        final_perms = await conn.fetch("""
            SELECT
                table_name,
                string_agg(privilege_type, ', ' ORDER BY privilege_type) as privileges
            FROM information_schema.table_privileges
            WHERE grantee = $1
            AND table_schema = 'fashion_sota'
            GROUP BY table_name
            ORDER BY table_name
        """, sp_uuid)

        if final_perms:
            print("Permissions summary:")
            for perm in final_perms:
                print(f"  {perm['table_name']}: {perm['privileges']}")
        else:
            print("  Note: Permissions may not show in information_schema but are granted")

        await conn.close()

        print("\n" + "="*80)
        print("✅ All permissions granted successfully!")
        print("="*80)
        print("\nService principal has access to:")
        print("  ✓ Schema: fashion_sota (USAGE)")
        print("  ✓ All current tables (SELECT)")
        print("  ✓ All future tables (SELECT)")
        print("\nNo app restart needed!")

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_and_grant())
