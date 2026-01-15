#!/usr/bin/env python3
"""
Execute Lakebase setup SQL script using Databricks SDK

Requires environment variables:
- SQL_WAREHOUSE_ID: Databricks SQL Warehouse ID
"""
import os
import sys
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

# SQL Warehouse ID (from environment)
WAREHOUSE_ID = os.getenv("SQL_WAREHOUSE_ID", "")
if not WAREHOUSE_ID:
    print("Error: SQL_WAREHOUSE_ID environment variable not set")
    sys.exit(1)

# Read SQL script
script_path = "scripts/setup_lakebase_fashion_sota_v2.sql"
with open(script_path, 'r') as f:
    sql_content = f.read()

# Split into individual statements (basic splitting on semicolons)
# Skip comments and empty lines
statements = []
current_statement = []

for line in sql_content.split('\n'):
    line = line.strip()

    # Skip comments
    if line.startswith('--') or not line:
        continue

    current_statement.append(line)

    # Check if line ends with semicolon (end of statement)
    if line.endswith(';'):
        statement = ' '.join(current_statement)
        if statement and not statement.startswith('/*'):
            statements.append(statement)
        current_statement = []

print(f"Found {len(statements)} SQL statements to execute")
print(f"Using warehouse: {WAREHOUSE_ID}")
print("=" * 80)

# Initialize Databricks client
w = WorkspaceClient()

# Execute each statement
executed = 0
failed = 0

for i, statement in enumerate(statements, 1):
    # Show preview of statement
    preview = statement[:100].replace('\n', ' ')
    print(f"\n[{i}/{len(statements)}] Executing: {preview}...")

    try:
        # Execute statement (wait_timeout must be 0s or 5s-50s)
        result = w.statement_execution.execute_statement(
            warehouse_id=WAREHOUSE_ID,
            statement=statement,
            wait_timeout="50s"  # Maximum allowed wait time
        )

        # Check result
        if result.status.state == StatementState.SUCCEEDED:
            print(f"✅ Success")

            # Show result if available
            if result.result and result.result.data_array:
                row_count = len(result.result.data_array)
                if row_count > 0:
                    print(f"   Returned {row_count} rows")
                    # Show first few rows
                    for row in result.result.data_array[:3]:
                        print(f"   {row}")

            executed += 1
        else:
            print(f"❌ Failed: {result.status.state}")
            if result.status.error:
                print(f"   Error: {result.status.error.message}")
            failed += 1

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        failed += 1

        # Stop after too many failures
        if failed >= 3:
            print("\n⚠️  Too many failures. Aborting.")
            sys.exit(1)

print("\n" + "=" * 80)
print(f"Execution complete: {executed} succeeded, {failed} failed")
print("=" * 80)

if failed == 0:
    print("\n✅ Lakebase setup successful!")
    print("\nNext steps:")
    print("1. Test database connection")
    print("2. Test vector search")
    print("3. Test API endpoints")
else:
    print(f"\n⚠️  Setup completed with {failed} failures. Review errors above.")
    sys.exit(1)
