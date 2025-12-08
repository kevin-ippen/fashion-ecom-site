# Lakebase Migration Guide

## Overview

This guide walks you through migrating your Unity Catalog tables to Lakebase PostgreSQL synced tables using the [migrate_to_lakebase.ipynb](notebooks/migrate_to_lakebase.ipynb) notebook.

## What Are Synced Tables?

**Synced tables** are read-only Postgres tables in Lakebase that automatically synchronize data from Unity Catalog tables. They provide:

- **Low-latency reads** (~10ms vs ~100ms for SQL Warehouse)
- **Automatic synchronization** using managed Lakeflow pipelines
- **SQL joins** with other Postgres tables
- **Unity Catalog governance** maintained

## Migration Notebook

The notebook [notebooks/migrate_to_lakebase.ipynb](notebooks/migrate_to_lakebase.ipynb) automates the entire migration process.

### Features

✅ **Pre-migration checks**
   - Validates source tables exist
   - Checks Change Data Feed (CDF) status
   - Auto-switches to SNAPSHOT mode if CDF not enabled

✅ **Flexible sync modes**
   - SNAPSHOT: Full refresh on demand
   - TRIGGERED: Incremental refresh on demand
   - CONTINUOUS: Real-time incremental updates

✅ **Automatic pipeline creation**
   - Creates and manages Lakeflow pipelines
   - Configures staging tables

✅ **Status monitoring**
   - Waits for tables to reach ONLINE status
   - Provides detailed status reports
   - Shows sync progress

✅ **Error handling**
   - Graceful failure handling
   - Detailed error messages
   - Rollback support

## Tables Being Migrated

| Source Table | Synced Table | Primary Key | Sync Mode |
|--------------|--------------|-------------|-----------|
| `productsdb` | `products_synced` | `product_id` | TRIGGERED |
| `usersdb` | `users_synced` | `user_id` | TRIGGERED |
| `product_image_embeddingsdb` | `product_embeddings_synced` | `product_id` | TRIGGERED |
| `user_style_featuresdb` | `user_features_synced` | `user_id` | TRIGGERED |

## Prerequisites

### 1. Databricks Permissions

You need:
- `CAN USE` permission on the Lakebase database instance
- `USE CATALOG` and `USE SCHEMA` on source catalog/schema
- `CREATE TABLE` permission on target catalog/schema

### 2. Change Data Feed (Optional but Recommended)

For TRIGGERED or CONTINUOUS sync modes, enable CDF on source tables:

```sql
ALTER TABLE main.fashion_demo.productsdb
SET TBLPROPERTIES (delta.enableChangeDataFeed = true);

ALTER TABLE main.fashion_demo.usersdb
SET TBLPROPERTIES (delta.enableChangeDataFeed = true);

ALTER TABLE main.fashion_demo.product_image_embeddingsdb
SET TBLPROPERTIES (delta.enableChangeDataFeed = true);

ALTER TABLE main.fashion_demo.user_style_featuresdb
SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
```

**Note**: The notebook can auto-enable CDF for you (see the "Enable Change Data Feed" cell).

### 3. Storage Location

The notebook creates staging tables in:
- Catalog: `main`
- Schema: `fashion_demo_staging`

This schema will be created automatically if it doesn't exist.

## How to Run

### Step 1: Open the Notebook

1. Upload [notebooks/migrate_to_lakebase.ipynb](notebooks/migrate_to_lakebase.ipynb) to your Databricks workspace
2. Attach it to a cluster (any cluster with DBR 13.3+ and Databricks SDK installed)

### Step 2: Review Configuration

Check the configuration cell and update if needed:

```python
# Configuration
SOURCE_CATALOG = "main"
SOURCE_SCHEMA = "fashion_demo"

TARGET_CATALOG = "main"
TARGET_SCHEMA = "fashion_demo_lakebase"  # New schema for synced tables
DATABASE_INSTANCE_NAME = "instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c"
LOGICAL_DATABASE_NAME = "databricks_postgres"

PIPELINE_STORAGE_CATALOG = "main"
PIPELINE_STORAGE_SCHEMA = "fashion_demo_staging"

DEFAULT_SYNC_MODE = SyncedTableSchedulingPolicy.TRIGGERED
```

### Step 3: Run Pre-Migration Checks

Run the "Pre-Migration Checks" cell. This validates:
- Source tables exist
- CDF is enabled (for TRIGGERED/CONTINUOUS modes)
- Permissions are correct

If any checks fail, fix the issues before proceeding.

### Step 4: (Optional) Enable CDF

If you want TRIGGERED or CONTINUOUS mode but CDF is not enabled, uncomment and run the "Enable Change Data Feed" cell.

### Step 5: Create Synced Tables

Run the "Create Synced Tables" cell. This:
- Creates synced tables in `main.fashion_demo_lakebase`
- Creates Lakeflow pipelines for synchronization
- Starts the initial sync

Expected output:
```
🚀 Creating synced tables...

Creating synced table: products_synced
  Source: main.fashion_demo.productsdb
  Target: main.fashion_demo_lakebase.products_synced
  Primary Key: ['product_id']
  Timeseries Key: ingested_at
  Sync Mode: TRIGGERED
  ✅ Created synced table: main.fashion_demo_lakebase.products_synced
...
✅ Successfully created: 4 tables
❌ Failed: 0 tables
```

### Step 6: Monitor Sync Status

Run the "Monitor Sync Status" cell to wait for all tables to reach ONLINE status.

This may take 5-15 minutes depending on table size.

### Step 7: Check Final Status

Run the "Check Final Status" cell to see a summary:

```
📋 Final Status Report

Table                                    Status          Message
====================================================================================================
✅ products_synced                        ONLINE
✅ users_synced                           ONLINE
✅ product_embeddings_synced              ONLINE
✅ user_features_synced                   ONLINE
```

### Step 8: Test Queries

Optionally, run the test query cells to verify data is synced correctly.

## After Migration

### 1. Update FastAPI Configuration

Update [core/config.py](core/config.py):

```python
# Unity Catalog
CATALOG: str = "main"
SCHEMA: str = "fashion_demo_lakebase"  # ← Changed from "fashion_demo"
PRODUCTS_TABLE: str = "products_synced"  # ← Added "_synced"
USERS_TABLE: str = "users_synced"
EMBEDDINGS_TABLE: str = "product_embeddings_synced"
USER_FEATURES_TABLE: str = "user_style_featuresdb"  # ← Keep original or add "_synced"
```

### 2. Create Postgres Indexes

For better query performance, create indexes:

```sql
-- Connect to Lakebase with psql or SQL editor
\c databricks_postgres

-- Indexes for products
CREATE INDEX idx_products_category ON fashion_demo_lakebase.products_synced(master_category);
CREATE INDEX idx_products_subcategory ON fashion_demo_lakebase.products_synced(sub_category);
CREATE INDEX idx_products_price ON fashion_demo_lakebase.products_synced(price);
CREATE INDEX idx_products_gender ON fashion_demo_lakebase.products_synced(gender);
CREATE INDEX idx_products_color ON fashion_demo_lakebase.products_synced(base_color);

-- Indexes for embeddings (if you query by embedding_model)
CREATE INDEX idx_embeddings_model ON fashion_demo_lakebase.product_embeddings_synced(embedding_model);

-- Indexes for users
CREATE INDEX idx_users_segment ON fashion_demo_lakebase.users_synced(segment);
```

### 3. Grant Permissions (If Needed)

```sql
-- Grant SELECT to other users
GRANT USAGE ON SCHEMA fashion_demo_lakebase TO other_user;
GRANT SELECT ON ALL TABLES IN SCHEMA fashion_demo_lakebase TO other_user;
```

### 4. Update Connection String

Make sure your FastAPI app uses the correct PGPASSWORD (see [LAKEBASE_PASSWORD_SETUP.md](LAKEBASE_PASSWORD_SETUP.md)).

### 5. Test the App

Redeploy your Databricks App and test the API endpoints to ensure they work with the synced tables.

## Sync Modes Explained

### SNAPSHOT Mode
- **How it works**: Full table refresh on each run
- **When to use**: When >10% of table data changes regularly
- **Performance**: 10x more efficient than incremental for large changes
- **Trigger**: Manual, API, or scheduled
- **CDF required**: ❌ No

### TRIGGERED Mode
- **How it works**: Incremental refresh (only changes since last run)
- **When to use**: Balanced cost/performance, occasional updates
- **Performance**: Good for <10% data changes
- **Trigger**: Manual, API, or scheduled
- **CDF required**: ✅ Yes

### CONTINUOUS Mode
- **How it works**: Real-time incremental updates (runs continuously)
- **When to use**: Lowest lag required (e.g., transactions)
- **Performance**: Always running (higher cost)
- **Trigger**: Automatic
- **CDF required**: ✅ Yes

## Triggering Manual Refreshes (TRIGGERED Mode)

For tables in TRIGGERED mode, you can manually trigger a refresh after updating source data:

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()

# Trigger refresh
synced_table = w.database.get_synced_database_table(
    name="main.fashion_demo_lakebase.products_synced"
)
# Then trigger the underlying pipeline via Workflows API
```

Or use the notebook's helper function:
```python
trigger_sync_refresh("main.fashion_demo_lakebase.products_synced")
```

## Monitoring

### Check Sync Status

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()

status = w.database.get_synced_database_table(
    name="main.fashion_demo_lakebase.products_synced"
)
print(f"Status: {status.data_synchronization_status.detailed_state}")
print(f"Message: {status.data_synchronization_status.message}")
```

### View Pipeline Logs

1. Go to **Workflows** in Databricks UI
2. Find the pipeline for your synced table (e.g., `synced_table_main_fashion_demo_lakebase_products_synced`)
3. Click on the latest run to view logs

## Troubleshooting

### Issue: "Change Data Feed not enabled"

**Solution**: Enable CDF on the source table:
```sql
ALTER TABLE main.fashion_demo.productsdb
SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
```

Or use SNAPSHOT mode instead (edit the notebook's `TABLES_TO_MIGRATE` configuration).

### Issue: "Synced table already exists"

**Solution**: The table was already created. To recreate:
1. Delete from Unity Catalog using the cleanup cell in the notebook
2. Drop the table in Postgres: `DROP TABLE fashion_demo_lakebase.products_synced;`
3. Re-run the creation cell

### Issue: Sync stuck in "PROVISIONING" or "INITIALIZING"

**Solution**: Wait 5-10 minutes. Initial sync can take time for large tables.

Check pipeline logs in Workflows UI for errors.

### Issue: "Failed to decode token" when connecting

**Solution**: You need the correct PGPASSWORD, not a Databricks PAT token.

See [LAKEBASE_PASSWORD_SETUP.md](LAKEBASE_PASSWORD_SETUP.md) for details.

### Issue: Sync fails with "duplicate key" error

**Solution**: Your source table has duplicate primary keys.

Either:
- Clean up duplicates in the source table
- Add a `timeseries_key` in the notebook config to auto-deduplicate

## Cleanup

To delete synced tables:

1. Set `ENABLE_CLEANUP = True` in the cleanup cell
2. Run the cleanup cell to delete from Unity Catalog
3. Connect to Postgres and drop tables:

```sql
DROP TABLE IF EXISTS fashion_demo_lakebase.products_synced;
DROP TABLE IF EXISTS fashion_demo_lakebase.users_synced;
DROP TABLE IF EXISTS fashion_demo_lakebase.product_embeddings_synced;
DROP TABLE IF EXISTS fashion_demo_lakebase.user_features_synced;
```

## Performance Tips

### Update Rate
- CONTINUOUS mode: ~1,200 rows/second per CU
- Bulk writes: ~15,000 rows/second per CU

### Table Limits
- Max 20 synced tables per source table
- Each sync uses up to 16 database connections
- Total logical data size limit: 2 TB per instance

### Optimize Costs
- Use SNAPSHOT mode if >10% of data changes
- Use TRIGGERED mode for occasional updates (not more often than every 5 minutes)
- Use CONTINUOUS mode only for real-time requirements

## Data Type Mapping

| Delta Type | Postgres Type |
|------------|---------------|
| BIGINT | BIGINT |
| STRING | TEXT |
| DOUBLE | DOUBLE PRECISION |
| TIMESTAMP | TIMESTAMP WITH TIME ZONE |
| ARRAY | JSONB |
| MAP | JSONB |
| STRUCT | JSONB |

**Note**: Complex types (ARRAY, MAP, STRUCT) are stored as JSONB in Postgres, which means you can query them using Postgres JSON functions.

Example:
```sql
-- Query an array column
SELECT product_id,
       jsonb_array_elements_text(image_embedding::jsonb) as embedding_value
FROM fashion_demo_lakebase.product_embeddings_synced
LIMIT 10;
```

## References

- [Databricks Lakebase Documentation](https://docs.databricks.com/en/database/)
- [Synced Tables Documentation](https://docs.databricks.com/en/database/synced-tables.html)
- [Lakeflow Pipelines](https://docs.databricks.com/en/lakeflow/)
- [LAKEBASE_PASSWORD_SETUP.md](LAKEBASE_PASSWORD_SETUP.md) - Setting up authentication
