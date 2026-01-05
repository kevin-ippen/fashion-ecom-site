# Fashion SOTA Deployment Options

> **Code migration complete!** Now choose your deployment approach.

---

## ✅ What's Done

All code updated to use `main.fashion_sota` schema:
- ✅ Configuration, services, routes updated
- ✅ Vector search simplified (unified index)
- ✅ Image paths updated
- ✅ Committed and pushed to GitHub

---

## 🎯 Deployment Options

### Option 1: Direct Unity Catalog (Quick Start - Recommended)

**Use this if**: You want to deploy immediately without Lakebase setup

**How it works**: App queries Unity Catalog tables directly via Databricks SQL

**Setup**:
1. Update `core/config.py` to bypass Lakebase
2. Use serverless SQL warehouse for queries
3. Deploy to Databricks Apps

**Pros**:
- ✅ No Lakebase instance needed
- ✅ Faster deployment (ready now)
- ✅ Simpler architecture
- ✅ Direct access to UC tables

**Cons**:
- ⚠️ Higher latency per query (~200-500ms vs ~10-50ms with Lakebase)
- ⚠️ More expensive for high-traffic apps
- ⚠️ No local PostgreSQL connection for development

**When to use**: POC, demos, low-traffic production (<100 req/s)

---

### Option 2: With Lakebase (Production-Grade)

**Use this if**: You need low-latency, high-throughput data access

**How it works**: Unity Catalog tables synced to Lakebase PostgreSQL

**Prerequisites**:
1. ✅ Databricks Lakebase database instance created
2. ✅ Unity Catalog registered with Lakebase
3. ✅ App service principal has Lakebase permissions

**Setup**:
1. Create Lakebase database instance (Databricks UI)
2. Register Unity Catalog with Lakebase
3. Sync tables using Lakebase foreign tables
4. Deploy app with Lakebase connection

**Pros**:
- ✅ Ultra-low latency (~10-50ms queries)
- ✅ PostgreSQL-compatible (standard SQL)
- ✅ Better for high-traffic production
- ✅ Local development friendly

**Cons**:
- ⚠️ Requires Lakebase instance ($$$)
- ⚠️ Additional setup steps
- ⚠️ Data sync delay (continuous or snapshot)

**When to use**: High-traffic production (>100 req/s), cost-optimized at scale

---

## 🚀 Quick Start: Option 1 (Direct UC)

Since Lakebase isn't set up yet, let's use direct Unity Catalog access:

### 1. Verify Vector Search Index

```bash
databricks vector-search-indexes get main.fashion_sota.product_embeddings_index --profile work
```

Expected: `status='ONLINE'`, `num_vectors=43916`

### 2. Create Minimal Tables in Unity Catalog

```sql
-- Run in Databricks SQL
-- Create users table (if not exists)
CREATE TABLE IF NOT EXISTS main.fashion_sota.users (
  user_id STRING PRIMARY KEY,
  email STRING NOT NULL,
  name STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  preferences MAP<STRING, STRING>
)
USING DELTA
COMMENT 'User accounts';

-- Create user preferences table
CREATE TABLE IF NOT EXISTS main.fashion_sota.user_preferences (
  user_id STRING NOT NULL,
  preference_type STRING NOT NULL,
  value STRING NOT NULL,
  score FLOAT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT pk_prefs PRIMARY KEY (user_id, preference_type, value)
)
USING DELTA
COMMENT 'User preferences and interactions';

-- Verify
SELECT COUNT(*) as product_count FROM main.fashion_sota.product_embeddings;
-- Expected: 43,916
```

### 3. Update App to Use Direct UC (Skip Lakebase)

The app already points to `main.fashion_sota` in config. Just ensure you're **NOT** using Lakebase repository for products.

Update repository to query UC directly:

```python
# In repositories/lakebase.py or create repositories/unity_catalog.py
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

class UnityCatalogRepository:
    """Query Unity Catalog tables directly via SQL"""

    def __init__(self, warehouse_id: str):
        self.warehouse_id = warehouse_id
        self.w = WorkspaceClient()

    async def get_products(self, limit=24, offset=0, filters=None):
        """Query products from main.fashion_sota.product_embeddings"""

        where_clauses = []
        if filters:
            if filters.get("gender"):
                where_clauses.append(f"gender = '{filters['gender']}'")
            if filters.get("master_category"):
                where_clauses.append(f"master_category = '{filters['master_category']}'")
            # Add more filters...

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT
                product_id,
                product_display_name,
                master_category,
                sub_category,
                article_type,
                base_color,
                price,
                image_path,
                gender,
                season,
                usage,
                year,
                brand
            FROM main.fashion_sota.product_embeddings
            {where_clause}
            ORDER BY product_display_name
            LIMIT {limit} OFFSET {offset}
        """

        result = self.w.statement_execution.execute_statement(
            warehouse_id=self.warehouse_id,
            statement=query,
            wait_timeout="30s"
        )

        if result.status.state == StatementState.SUCCEEDED:
            return result.result.data_array
        else:
            raise Exception(f"Query failed: {result.status.error}")
```

### 4. Test Locally

```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site

# Set environment variables
export DATABRICKS_HOST="https://adb-984752964297111.11.azuredatabricks.net"
export SQL_WAREHOUSE_ID="148ccb90800933a1"  # Or your preferred warehouse

# Test vector search
python3 -c "
from services.vector_search_service import vector_search_service
import numpy as np
import asyncio

async def test():
    vec = np.random.randn(512).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    results = await vector_search_service.search(vec, num_results=5)
    print(f'✅ Vector search works! Got {len(results)} results')

asyncio.run(test())
"

# Start app
uvicorn app:app --reload --port 8000
```

### 5. Deploy to Databricks Apps

```bash
# Ensure app.yaml is correct
cat app.yaml

# Deploy
databricks apps deploy fashion-ecom-site --profile work
```

---

## 📋 Decision Matrix

| Factor | Direct UC (Option 1) | With Lakebase (Option 2) |
|--------|---------------------|-------------------------|
| **Setup Time** | 10 minutes | 2-3 hours |
| **Query Latency** | 200-500ms | 10-50ms |
| **Cost** | Higher per query | Lower at scale |
| **Best For** | POC, demos | Production |
| **Dev Experience** | Databricks-native | PostgreSQL-like |
| **Prerequisites** | ✅ UC tables | ✅ Lakebase instance |

---

## 🔧 Lakebase Setup (Option 2 - Later)

If you decide to set up Lakebase later:

### 1. Create Lakebase Instance

In Databricks UI:
- Go to **Data** → **Lakebase**
- Click **Create Database Instance**
- Name: `fashion-sota-db`
- Size: Small (can scale later)
- Wait for provisioning (~10 minutes)

### 2. Register Unity Catalog

```sql
-- In Databricks SQL
REGISTER UNITY CATALOG main WITH LAKEBASE DATABASE INSTANCE fashion_sota_db;

-- Verify
SHOW CATALOGS IN LAKEBASE;
```

### 3. Run Sync Script

```bash
databricks sql -e <warehouse-id> -f scripts/setup_lakebase_fashion_sota_v2.sql --profile work
```

### 4. Update App Config

Enable Lakebase in `.env`:
```env
ENABLE_LAKEBASE=true
PGHOST=<lakebase-host>
PGPORT=5432
PGUSER=<service-principal>
PGDATABASE=main
```

---

## 🎯 Recommendation

**Start with Option 1 (Direct UC)** for now:

1. ✅ Faster to production
2. ✅ Lower complexity
3. ✅ No additional infrastructure
4. ✅ Can migrate to Lakebase later if needed

**Migrate to Option 2 (Lakebase)** if:
- App traffic grows (>100 req/s)
- Query latency becomes an issue
- Cost optimization needed at scale

---

## 📚 Next Steps (Option 1 - Direct UC)

1. Create UC tables for users/preferences (see SQL above)
2. Test vector search locally
3. Update repository to query UC directly (or use existing Lakebase repo with UC connection string)
4. Deploy to Databricks Apps
5. Test in production

---

**Current Status**: Code ready ✅ | Choose deployment path ⏳

**Recommended**: Option 1 (Direct UC) - get to production fast, optimize later

Let me know which option you prefer, and I'll help with the specific setup!
