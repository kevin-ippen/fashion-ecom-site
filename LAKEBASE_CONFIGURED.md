# ✅ Lakebase Configuration Complete!

> **App now points to `main.fashion_sota.products_lakebase`**

---

## What Changed

### Configuration Updated
**File**: [core/config.py](file:///Users/kevin.ippen/projects/fashion-ecom-site/core/config.py)

```python
# Unity Catalog Tables - Using Lakebase-synced tables
UC_PRODUCTS_TABLE = "main.fashion_sota.products_lakebase"  # ← Lakebase-synced!
UC_PRODUCT_EMBEDDINGS_TABLE = "main.fashion_sota.product_embeddings"
UC_USERS_TABLE = "main.fashion_sota.users"
UC_USER_PREFERENCES_TABLE = "main.fashion_sota.user_preferences"
```

### Repository Updated
**File**: [repositories/lakebase.py](file:///Users/kevin.ippen/projects/fashion-ecom-site/repositories/lakebase.py)

- All queries now use fully qualified UC table names
- Removed schema prefix (was causing double-prefixing)
- Tables reference:
  - `self.products_table` = `main.fashion_sota.products_lakebase`
  - `self.embeddings_table` = `main.fashion_sota.product_embeddings`
  - `self.users_table` = `main.fashion_sota.users`
  - `self.user_features_table` = `main.fashion_sota.user_preferences`

---

## Table Schema: products_lakebase

```
product_id              INT
gender                  STRING
master_category         STRING
sub_category            STRING
article_type            STRING
base_color              STRING
season                  STRING
year                    STRING (nullable)
usage                   STRING
product_display_name    STRING
price                   FLOAT/DECIMAL
image_path              STRING
ingested_at             TIMESTAMP
migrated_at             TIMESTAMP
source_table            STRING
```

**Note**: This table is synced from Lakebase PostgreSQL and appears as a Unity Catalog table.

---

## Testing

### 1. Verify Table Access

```bash
# Check table exists and row count
databricks sql -w 148ccb90800933a1 --profile work <<SQL
SELECT COUNT(*) as product_count
FROM main.fashion_sota.products_lakebase;
SQL
```

Expected output: ~44,000 products

### 2. Test Sample Query

```bash
# Get sample products
databricks sql -w 148ccb90800933a1 --profile work <<SQL
SELECT
  product_id,
  product_display_name,
  master_category,
  price,
  gender
FROM main.fashion_sota.products_lakebase
LIMIT 10;
SQL
```

### 3. Test API Endpoints (Local)

```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site

# Start app
uvicorn app:app --reload --port 8000 &

# Wait for startup
sleep 3

# Test products endpoint
curl -s http://localhost:8000/api/v1/products?page=1&page_size=5 | jq '.total, .products | length'
# Expected: <total_count>, 5

# Test with filters
curl -s http://localhost:8000/api/v1/products?gender=Men&page_size=10 | jq '.products | length'
# Expected: 10

# Test single product
curl -s http://localhost:8000/api/v1/products/12345 | jq '.product_display_name, .price'

# Clean up
pkill -f "uvicorn app:app"
```

---

## Deployment Checklist

Before deploying to Databricks Apps:

- [x] Config updated to use `products_lakebase`
- [x] Repository queries updated
- [x] Image paths point to `fashion_sota/product_images`
- [x] Vector search uses unified index
- [ ] App tested locally (run tests above)
- [ ] Verify `products_lakebase` table accessible
- [ ] Verify vector search index online
- [ ] Update app permissions if needed

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│ Fashion E-Commerce App (Databricks Apps)       │
└─────────────────┬───────────────────────────────┘
                  │
     ┌────────────┴────────────┐
     │                         │
     v                         v
┌─────────────────┐   ┌──────────────────────────┐
│ Lakebase Tables │   │ Vector Search            │
│ (via UC)        │   │                          │
├─────────────────┤   ├──────────────────────────┤
│ products_       │   │ product_embeddings_index │
│   lakebase      │   │ (unified, 43.9K vectors) │
│ users           │   └──────────────────────────┘
│ user_prefs      │
└─────────────────┘
```

**Key Points**:
- `products_lakebase` is a **Unity Catalog table** (not direct PostgreSQL)
- It's synced from Lakebase PostgreSQL (likely via foreign table)
- App queries it via Databricks SQL (using existing `LakebaseRepository`)
- No direct PostgreSQL connection needed in app

---

## Comparison: Before vs After

| Aspect | Before | After |
|--------|--------|-------|
| **Products Table** | `fashion_demo.productsdb` | `main.fashion_sota.products_lakebase` |
| **Schema** | fashion_demo | fashion_sota |
| **Table Location** | Separate Lakebase schema | UC table (Lakebase-backed) |
| **Query Path** | PostgreSQL direct | Databricks SQL → UC |
| **Product Count** | 44,424 | ~44,000 (Lakebase-synced) |

---

## Next Steps

### 1. Local Testing (Now)
```bash
# Test locally first
cd /Users/kevin.ippen/projects/fashion-ecom-site
python3 -m pytest tests/ -v  # If you have tests
# OR
uvicorn app:app --reload  # Manual testing
```

### 2. Deploy to Databricks Apps (After Local Tests Pass)
```bash
databricks apps deploy fashion-ecom-site --profile work
```

### 3. Monitor Deployment
```bash
# Check app status
databricks apps list --profile work | grep fashion-ecom-site

# View logs
databricks apps logs fashion-ecom-site --profile work
```

---

## Rollback (If Needed)

If something doesn't work:

```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site

# Restore previous config
git checkout HEAD~1 core/config.py repositories/lakebase.py

# Restart app
pkill -f uvicorn
uvicorn app:app --reload
```

Or use the backup:
```bash
cp core/config_fashion_demo_backup.py core/config.py
```

---

## Troubleshooting

### Error: "Table does not exist: main.fashion_sota.products_lakebase"

**Check**:
```bash
databricks tables get main.fashion_sota.products_lakebase --profile work
```

If not found, the Lakebase sync may not be complete. Check with your Databricks admin.

### Error: "Permission denied on table"

**Fix**: Grant app service principal permissions:
```sql
GRANT SELECT ON TABLE main.fashion_sota.products_lakebase TO `<app-service-principal>`;
```

### Products not loading

**Debug**:
1. Check table has data: `SELECT COUNT(*) FROM main.fashion_sota.products_lakebase`
2. Check column names match schema
3. Verify SQL warehouse is running
4. Check app logs for query errors

---

## Summary

✅ **Configuration**: Updated to use `main.fashion_sota.products_lakebase`
✅ **Repository**: All queries use fully qualified UC table names
✅ **Vector Search**: Points to unified `product_embeddings_index`
✅ **Image Volume**: Uses `fashion_sota/product_images`

**Status**: Ready for local testing → deployment

---

**Last Updated**: 2026-01-05
**Commit**: (will be added after commit)
