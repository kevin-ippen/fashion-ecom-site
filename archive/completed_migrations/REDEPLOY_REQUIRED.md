# ⚠️ Redeploy Required - Lakebase Connection Fixed

> **Issue**: Deployed app is using OLD code with wrong table names and connection settings

---

## 🐛 Problem Identified

From your app logs:
```
Query: SELECT * FROM fashion_sota.products
Error: External authorization failed
```

**Issues**:
1. ❌ Querying `fashion_sota.products` (old table name)
2. ✅ Should query `fashion_sota.products_lakebase` (correct table name)
3. ❌ Database connection using wrong parameters

**Root Cause**: Deployed app hasn't been updated with latest code changes.

---

## ✅ Fixes Applied (Commit 77d9297 + new)

### 1. Lakebase Connection Parameters
```python
# core/config.py
LAKEBASE_HOST = "instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net"
LAKEBASE_DATABASE = "databricks_postgres"  # Changed from "main"
LAKEBASE_SCHEMA = "fashion_sota"
LAKEBASE_PRODUCTS_TABLE = "products_lakebase"  # Changed from "products"
```

### 2. Repository Query Format
```python
# repositories/lakebase.py
self.products_table = "fashion_sota.products_lakebase"  # Correct!
self.users_table = "fashion_sota.users"
self.user_features_table = "fashion_sota.user_preferences"
```

### 3. Added Logging
```python
logger.info(f"Products table: {self.products_table}")
# Will log: "Products table: fashion_sota.products_lakebase"
```

---

## 🚀 Redeploy Steps

### 1. Verify Latest Code is Committed
```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site
git log --oneline -1
# Should show: "fix: Update Lakebase connection and table names for PostgreSQL"
```

### 2. Redeploy to Databricks Apps
```bash
# Deploy latest code
databricks apps deploy fashion-ecom-site --profile work

# Wait for deployment
databricks apps get fashion-ecom-site --profile work

# Check logs
databricks apps logs fashion-ecom-site --profile work --follow
```

### 3. Verify in Logs
After redeployment, you should see:
```
LakebaseRepository initialized:
  Products table: fashion_sota.products_lakebase
  Users table: fashion_sota.users
  Preferences table: fashion_sota.user_preferences
```

Instead of the old:
```
Query: SELECT * FROM fashion_sota.products  ← OLD (wrong)
```

---

## 🔍 Verify Lakebase Tables Exist

Before redeploying, confirm the tables exist in your Lakebase PostgreSQL instance:

```bash
psql "host=instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net \
      user=kevin.ippen@databricks.com \
      dbname=databricks_postgres \
      port=5432 \
      sslmode=require"
```

Then in psql:
```sql
-- List schemas
\dn

-- List tables in fashion_sota schema
\dt fashion_sota.*

-- Expected tables:
-- fashion_sota.products_lakebase
-- fashion_sota.users (if created)
-- fashion_sota.user_preferences (if created)

-- Check product count
SELECT COUNT(*) FROM fashion_sota.products_lakebase;
-- Expected: ~44,000

-- Sample query
SELECT product_id, product_display_name, price
FROM fashion_sota.products_lakebase
LIMIT 5;
```

---

## 🔧 If Tables Don't Exist in PostgreSQL

If `fashion_sota.products_lakebase` doesn't exist in your Lakebase PostgreSQL, you need to sync it:

### Option A: Via Databricks SQL
```sql
-- Create schema in Lakebase
CREATE SCHEMA IF NOT EXISTS fashion_sota;

-- Sync from Unity Catalog (if you have sync capabilities)
-- This depends on your Lakebase setup
```

### Option B: Use Unity Catalog Table Directly

If the Lakebase PostgreSQL tables don't exist yet, switch the app to query Unity Catalog directly instead of PostgreSQL:

```python
# In core/config.py, add flag to bypass Lakebase:
USE_LAKEBASE: bool = False  # Set to False to query UC directly

# Then update repository to check this flag and use Databricks SQL
```

---

## 🔐 Auth Issue: "External authorization failed"

This error suggests:
1. **Lakebase instance is paused** - Resume it in Databricks UI
2. **Service principal lacks permissions** - Grant permissions to app SP
3. **OAuth token issue** - Verify token has correct scopes

### Check Instance Status
```bash
# List Lakebase instances
databricks lakebase instances list --profile work

# Check if your instance is RUNNING
databricks lakebase instances get <instance-id> --profile work
```

If PAUSED, resume it:
```bash
databricks lakebase instances start <instance-id> --profile work
```

### Grant Permissions (if needed)
```sql
-- In your Lakebase PostgreSQL
GRANT USAGE ON SCHEMA fashion_sota TO <app-service-principal>;
GRANT SELECT ON ALL TABLES IN SCHEMA fashion_sota TO <app-service-principal>;
```

---

## 📋 Pre-Deployment Checklist

Before redeploying:

- [x] Latest code committed and pushed
- [ ] Lakebase instance is RUNNING (not paused)
- [ ] Table `fashion_sota.products_lakebase` exists in PostgreSQL
- [ ] App service principal has SELECT permission on tables
- [ ] Environment variables set correctly in app.yaml

---

## 🧪 Test After Redeploy

Once redeployed, test the products endpoint:

```bash
# Get your app URL
APP_URL=$(databricks apps get fashion-ecom-site --profile work --output json | jq -r '.url')

# Test products endpoint
curl "${APP_URL}/api/v1/products?page=1&page_size=5"

# Should return products successfully (not 500 error)
```

---

## 🔄 Quick Fix Summary

**Problem**: App queries wrong table (`fashion_sota.products` instead of `fashion_sota.products_lakebase`)

**Fix**:
1. ✅ Updated `LAKEBASE_PRODUCTS_TABLE = "products_lakebase"`
2. ✅ Updated `LAKEBASE_DATABASE = "databricks_postgres"`
3. ✅ Updated repository to use correct PostgreSQL schema.table format
4. ⏳ **Redeploy app** to pick up new code

**Next**: Redeploy and monitor logs!

---

**Last Updated**: 2026-01-05
**Status**: Fix committed, awaiting redeploy
