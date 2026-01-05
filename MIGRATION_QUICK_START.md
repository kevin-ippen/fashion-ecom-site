# Fashion SOTA Migration - Quick Start Guide

> **TL;DR**: 3-step migration from `fashion_demo` to `fashion_sota` schema

---

## 📋 Prerequisites

✅ Verify these exist before starting:

```sql
-- Check Unity Catalog table exists
SELECT COUNT(*) FROM main.fashion_sota.product_embeddings;
-- Expected: 43,916 rows

-- Check Vector Search index is online
SELECT * FROM system.vector_search_endpoints WHERE name = 'fashion-vector-search';
-- Expected: status='ONLINE'
```

---

## 🚀 3-Step Migration

### Step 1: Sync Lakebase Tables (10 min)

```bash
# Run the Lakebase setup script
databricks sql -e <sql-warehouse-id> -f scripts/setup_lakebase_fashion_sota_v2.sql
```

**What this does**:
- Creates `lakebase.fashion_sota` schema
- Syncs `products` table from `main.fashion_sota.product_embeddings`
- Creates `users` and `user_preferences` tables
- Sets up indexes and permissions

**Verify**:
```sql
SELECT COUNT(*) FROM lakebase.fashion_sota.products;
-- Expected: 43,916
```

---

### Step 2: Update App Configuration (2 min)

Replace `core/config.py` with updated version:

```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site
cp core/config_fashion_sota.py core/config.py
```

**Key changes**:
- `SCHEMA: "fashion_sota"` (was `fashion_demo`)
- `VS_INDEX: "main.fashion_sota.product_embeddings_index"` (unified index)
- Image volume path updated
- Simplified vector search (1 index instead of 3)

---

### Step 3: Update Vector Search Service (5 min)

Update `services/vector_search_service.py`:

**Replace initialization**:
```python
def __init__(self):
    self.endpoint_name = settings.VS_ENDPOINT_NAME  # fashion-vector-search
    self.index_name = settings.VS_INDEX  # Single unified index
    self.embedding_dim = settings.CLIP_EMBEDDING_DIM
```

**Remove separate index methods** (no longer needed):
```python
# DELETE these methods:
# - search_image()
# - search_text()
# - search_hybrid()
# - search_cross_modal()
```

**Keep only the unified search method**:
```python
async def search(
    self,
    query_vector: np.ndarray,
    num_results: int = 20,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Works for text, image, AND hybrid queries!"""
    index = self._get_index(self.index_name)
    # ... rest stays the same
```

---

## ✅ Test & Verify

### 1. Test Lakebase Connection
```bash
python -c "
from core.database import get_sync_engine
from core.config import settings
from sqlalchemy import text

engine = get_sync_engine()
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM fashion_sota.products'))
    print(f'Products: {result.scalar()}')  # Should be 43,916
"
```

### 2. Test Vector Search
```bash
python -c "
from services.vector_search_service import vector_search_service
import numpy as np
import asyncio

async def test():
    query = np.random.randn(512).astype(np.float32)
    query = query / np.linalg.norm(query)  # Normalize
    results = await vector_search_service.search(query, num_results=5)
    print(f'Vector Search works! Got {len(results)} results')
    print(f'First product: {results[0][\"product_display_name\"]}')

asyncio.run(test())
"
```

### 3. Test API Endpoints
```bash
# Start app
uvicorn app:app --reload --port 8000 &

# Test products endpoint
curl http://localhost:8000/api/v1/products?page=1&page_size=5 | jq '.products | length'
# Expected: 5

# Test search endpoint
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "red summer dress", "num_results": 10}' \
  | jq '.results | length'
# Expected: 10
```

---

## 🎯 What Changed

| Aspect | Before (fashion_demo) | After (fashion_sota) |
|--------|----------------------|---------------------|
| **Products** | 44,424 | 43,916 (validated) |
| **Schema** | `main.fashion_demo` | `main.fashion_sota` |
| **Vector Indexes** | 3 separate (image/text/hybrid) | 1 unified |
| **Lakebase Tables** | `productsdb`, `usersdb` | `products`, `users` |
| **Image Volume** | `/raw_data/images/` | `/product_images/` |
| **Data Structure** | Products + Embeddings (separate) | Denormalized (1 table) |

---

## 🐛 Troubleshooting

### Problem: Lakebase sync fails
**Solution**: Check Unity Catalog is registered
```sql
SHOW CATALOGS IN LAKEBASE;
-- If 'main' not listed:
REGISTER UNITY CATALOG main WITH LAKEBASE DATABASE INSTANCE <instance-name>;
```

### Problem: Vector Search returns 0 results
**Solution**: Check index status
```python
from databricks.vector_search.client import VectorSearchClient
vsc = VectorSearchClient()
index = vsc.get_index("main.fashion_sota.product_embeddings_index")
print(index.describe())  # Should show status='ONLINE'
```

### Problem: Images not loading
**Solution**: Update volume permissions in `app.yaml`
```yaml
resources:
  uc_securable:
    - securable_type: VOLUME
      securable_full_name: main.fashion_sota.product_images
      privilege: READ_VOLUME
```

### Problem: Wrong product count
**Solution**: Verify you're using the right table
```sql
SELECT COUNT(*) FROM main.fashion_sota.product_embeddings;
-- Should be 43,916 (not 44,424)
```

---

## 📚 Reference Docs

- **Lakebase UC Registration**: https://docs.databricks.com/aws/en/oltp/instances/register-uc
- **Lakebase Table Sync**: https://docs.databricks.com/aws/en/oltp/instances/sync-data/sync-table
- **Vector Search**: https://docs.databricks.com/en/generative-ai/vector-search.html

---

## 🔄 Rollback (If Needed)

```bash
# Restore original config
git checkout core/config.py

# Or manually change back in config.py:
SCHEMA = "fashion_demo"
LAKEBASE_SCHEMA = "fashion_demo"
VS_IMAGE_INDEX = "main.fashion_demo.vs_image_search"
VS_TEXT_INDEX = "main.fashion_demo.vs_text_search"
VS_HYBRID_INDEX = "main.fashion_demo.vs_hybrid_search"
```

---

## ✨ Benefits

1. **Faster Queries**: Denormalized data (no joins)
2. **Simpler Code**: 1 vector index instead of 3
3. **Better Data Quality**: 43,916 validated products with images
4. **Production Ready**: fashion_sota schema is optimized for serving
5. **Future Proof**: Ready for inspiration search and style clusters

---

**Migration Time**: ~15-20 minutes
**Downtime**: Zero (deploy on new schema, then switch)
**Rollback Time**: ~2 minutes (config change only)

Ready? Start with Step 1! 🚀
