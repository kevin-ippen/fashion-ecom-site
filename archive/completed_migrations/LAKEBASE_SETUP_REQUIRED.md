# ⚠️ Lakebase Setup Required

> **Code migration complete!** Next step: Sync Unity Catalog tables to Lakebase

---

## ✅ What's Done

All code has been updated to use `main.fashion_sota`:

- ✅ `core/config.py` - Updated to fashion_sota schema
- ✅ `services/vector_search_service.py` - Simplified to unified index
- ✅ `routes/v1/products.py` - New image volume path
- ✅ `app.yaml` - Updated volume permissions

**Backup created**: `core/config_fashion_demo_backup.py` (for rollback if needed)

---

## 🚨 Action Required: Set Up Lakebase Tables

The app now expects these Lakebase tables to exist:
- `lakebase.fashion_sota.products` (from `main.fashion_sota.product_embeddings`)
- `lakebase.fashion_sota.users` (new or migrated from fashion_demo)
- `lakebase.fashion_sota.user_preferences` (new)

### Option 1: Run SQL Script (Recommended)

```bash
# Execute the Lakebase setup script
databricks sql -e <your-sql-warehouse-id> -f scripts/setup_lakebase_fashion_sota_v2.sql --profile work
```

**What this does**:
1. Creates `lakebase.fashion_sota` schema
2. Syncs `products` table from Unity Catalog (43,916 products)
3. Creates `users` and `user_preferences` tables
4. Sets up indexes for performance
5. Grants permissions to app service principal

**Expected output**:
```
✅ Schema created: lakebase.fashion_sota
✅ Products synced: 43,916 rows
✅ Users table ready
✅ Preferences table ready
```

### Option 2: Manual Setup via Databricks SQL

1. **Open Databricks SQL Editor**
2. **Copy contents of** `scripts/setup_lakebase_fashion_sota_v2.sql`
3. **Replace placeholders**:
   - `{app_service_principal}` with your app's SP name
4. **Run the script**
5. **Verify tables exist**:
   ```sql
   SELECT COUNT(*) FROM lakebase.fashion_sota.products;
   -- Expected: 43,916
   ```

---

## 🧪 Testing After Lakebase Setup

Once Lakebase tables are synced, test the app:

### 1. Test Database Connection
```bash
python -c "
from core.database import get_sync_engine
from sqlalchemy import text

engine = get_sync_engine()
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM fashion_sota.products'))
    count = result.scalar()
    print(f'✅ Connected to Lakebase! Products: {count}')
    assert count == 43916, f'Expected 43,916 products, got {count}'
"
```

### 2. Test Vector Search
```python
# test_vector_search.py
import asyncio
import numpy as np
from services.vector_search_service import vector_search_service

async def test():
    # Generate random normalized vector
    query = np.random.randn(512).astype(np.float32)
    query = query / np.linalg.norm(query)

    # Test search
    results = await vector_search_service.search(query, num_results=5)

    print(f"✅ Vector Search works!")
    print(f"   Index: {vector_search_service.index_name}")
    print(f"   Results: {len(results)}")
    print(f"   First product: {results[0]['product_display_name']}")

    assert len(results) == 5, f"Expected 5 results, got {len(results)}"

if __name__ == "__main__":
    asyncio.run(test())
```

```bash
python test_vector_search.py
```

### 3. Test API Endpoints
```bash
# Start the app
uvicorn app:app --reload --port 8000 &

# Wait for startup
sleep 3

# Test products endpoint
echo "Testing /api/v1/products..."
curl -s http://localhost:8000/api/v1/products?page=1&page_size=5 | jq '.total, .products | length'
# Expected: 43916, 5

# Test text search
echo "Testing /api/v1/search..."
curl -s -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "red summer dress", "num_results": 10}' \
  | jq '.results | length'
# Expected: 10

echo "✅ All API tests passed!"
```

### 4. Test Image URLs
```bash
# Test that images are accessible
PRODUCT_ID=34029
IMAGE_URL="https://adb-984752964297111.11.azuredatabricks.net/ajax-api/2.0/fs/files/Volumes/main/fashion_sota/product_images/${PRODUCT_ID}.jpg"

echo "Testing image URL: $IMAGE_URL"
curl -I -H "Authorization: Bearer $(databricks auth token --host https://adb-984752964297111.11.azuredatabricks.net)" "$IMAGE_URL"
# Expected: HTTP/2 200 OK
```

---

## 📋 Pre-Flight Checklist

Before deploying to Databricks Apps:

- [ ] Lakebase tables synced (43,916 products)
- [ ] Database connection test passes
- [ ] Vector search test passes
- [ ] API endpoints return correct data
- [ ] Image URLs accessible (with auth)
- [ ] No Python import errors
- [ ] Volume permissions granted in app.yaml

---

## 🔧 Troubleshooting

### Problem: "Table does not exist: fashion_sota.products"
**Solution**: Run the Lakebase setup script first!
```bash
databricks sql -e <warehouse-id> -f scripts/setup_lakebase_fashion_sota_v2.sql --profile work
```

### Problem: "Module 'main.fashion_sota' is specified but does not exist"
**Solution**: Check that `VS_INDEX` in config.py is correct:
```python
VS_INDEX: str = "main.fashion_sota.product_embeddings_index"
```

Verify index exists:
```bash
databricks vector-search-indexes get main.fashion_sota.product_embeddings_index --profile work
```

### Problem: Vector search returns 0 results
**Solution**: Check index is ONLINE:
```python
from databricks.vector_search.client import VectorSearchClient
vsc = VectorSearchClient()
index = vsc.get_index("main.fashion_sota.product_embeddings_index")
print(index.describe())  # Should show status='ONLINE'
```

### Problem: Images not loading (403/404)
**Solution**: Verify volume permissions in app.yaml:
```yaml
resources:
  uc_securable:
    - securable_type: VOLUME
      securable_full_name: main.fashion_sota.product_images
      privilege: READ_VOLUME
```

---

## 🔄 Rollback (If Needed)

If you encounter issues and need to rollback:

```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site

# Restore old config
cp core/config_fashion_demo_backup.py core/config.py

# Revert other files
git checkout services/vector_search_service.py
git checkout routes/v1/products.py
git checkout app.yaml

# Restart app
uvicorn app:app --reload
```

---

## 📚 Reference Files

- **Migration Plan**: [FASHION_SOTA_MIGRATION_PLAN.md](./FASHION_SOTA_MIGRATION_PLAN.md)
- **Quick Start**: [MIGRATION_QUICK_START.md](./MIGRATION_QUICK_START.md)
- **SQL Script**: [scripts/setup_lakebase_fashion_sota_v2.sql](./scripts/setup_lakebase_fashion_sota_v2.sql)
- **Summary**: [FASHION_SOTA_SUMMARY.md](./FASHION_SOTA_SUMMARY.md)

---

## 🚀 Next Steps

1. **Run Lakebase setup script** (see Option 1 above)
2. **Run all tests** (see Testing section above)
3. **Deploy to Databricks Apps** (if all tests pass)
4. **Monitor logs** for any errors
5. **Verify frontend works** with new backend

---

**Status**: Code migration ✅ | Lakebase setup ⏳ | Ready to test once Lakebase synced

**Last Updated**: 2026-01-05
