#!/usr/bin/env python3
"""
Check available roles in Lakebase PostgreSQL
"""
import asyncio
import asyncpg
import subprocess
import json

async def check_roles():
    """List all roles and their permissions"""

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

        # List all roles
        print("📋 All roles in PostgreSQL:")
        roles = await conn.fetch("SELECT rolname FROM pg_roles ORDER BY rolname")
        for role in roles:
            print(f"   - {role['rolname']}")

        # Check current user
        print(f"\n👤 Current user:")
        current_user = await conn.fetchval("SELECT current_user")
        print(f"   {current_user}")

        # Check schema permissions
        print(f"\n🔐 Schema permissions on fashion_sota:")
        schema_perms = await conn.fetch("""
            SELECT
                grantee,
                privilege_type
            FROM information_schema.schema_privileges
            WHERE schema_name = 'fashion_sota'
            ORDER BY grantee, privilege_type
        """)

        if schema_perms:
            for perm in schema_perms:
                print(f"   {perm['grantee']}: {perm['privilege_type']}")
        else:
            print("   (no explicit permissions found)")

        # Check table permissions
        print(f"\n📊 Table permissions on products_lakebase:")
        table_perms = await conn.fetch("""
            SELECT
                grantee,
                privilege_type
            FROM information_schema.table_privileges
            WHERE table_schema = 'fashion_sota' AND table_name = 'products_lakebase'
            ORDER BY grantee, privilege_type
        """)

        if table_perms:
            for perm in table_perms:
                print(f"   {perm['grantee']}: {perm['privilege_type']}")
        else:
            print("   (no explicit permissions found)")

        # Check if we can select from the table
        print(f"\n🧪 Testing SELECT access...")
        try:
            count = await conn.fetchval("SELECT COUNT(*) FROM fashion_sota.products_lakebase")
            print(f"   ✅ Can read table (count: {count:,})")
        except Exception as e:
            print(f"   ❌ Cannot read table: {e}")

        await conn.close()

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_roles())
