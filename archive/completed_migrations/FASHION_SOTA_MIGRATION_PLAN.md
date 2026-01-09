# Fashion SOTA Schema Migration Guide

> **Goal**: Refactor the fashion e-commerce app to use production-ready Unity Catalog tables in `main.fashion_sota`

**Status**: 🏗️ Ready to Execute
**Impact**: High - Core data layer migration
**Estimated Time**: 1-2 hours (includes Lakebase table sync setup)

---

## 📊 Current State (main.fashion_demo)

### Unity Catalog Tables
- **Schema**: `main.fashion_demo`
- **Products**: `main.fashion_demo.products` (44,424 products)
- **Embeddings**: `main.fashion_demo.product_embeddings_multimodal`
- **Images**: `/Volumes/main/fashion_demo/raw_data/images/{product_id}.jpg`

### Vector Search Indexes (3 separate)
- `main.fashion_demo.vs_image_search` - Image embeddings only
- `main.fashion_demo.vs_text_search` - Text embeddings only
- `main.fashion_demo.vs_hybrid_search` - Combined embeddings

### Lakebase (PostgreSQL) Synced Tables
- **Schema**: `fashion_demo`
- **Tables**:
  - `fashion_demo.productsdb` - Product catalog
  - `fashion_demo.usersdb` - User accounts
  - `fashion_demo.user_style_featuresdb` - User preferences

### Model Serving
- **CLIP Endpoint**: `siglip-multimodal-endpoint` (512-dim embeddings)

---

## 🎯 Target State (main.fashion_sota)

### Unity Catalog Tables ✨
- **Schema**: `main.fashion_sota`
- **Products**: `main.fashion_sota.products_with_images` (43,916 products)
  - Contains all product metadata + validated image paths
  - Denormalized for performance (no joins needed)
- **Embeddings**: `main.fashion_sota.product_embeddings` (43,916 products)
  - Columns: `product_id`, `embedding` (512-dim hybrid), `image_embedding`, `text_embedding`, plus **all product metadata denormalized**
  - No joins required - everything in one table!

### Vector Search Index (1 unified) ⚡
- **Index**: `main.fashion_sota.product_embeddings_index`
- **Endpoint**: `fashion-vector-search` (✅ ONLINE)
- **Source**: `main.fashion_sota.product_embeddings`
- **Embedding Column**: `embedding` (512-dim FashionCLIP 2.0, L2-normalized)
- **Sync Type**: Delta Sync (continuous updates)

### Lakebase (PostgreSQL) Synced Tables 🗄️
- **Schema**: `fashion_sota` (new)
- **Tables**:
  - `fashion_sota.products` - Synced from `main.fashion_sota.product_embeddings`
    - Contains all product metadata + embeddings denormalized
    - Primary key: `product_id`
  - `fashion_sota.users` - User accounts (reuse or recreate)
  - `fashion_sota.user_preferences` - User style preferences

### Model Serving (No Change) 🤖
- **CLIP Endpoint**: `siglip-multimodal-endpoint` (512-dim, works with FashionCLIP 2.0)

### Images 📸
- **Volume**: `/Volumes/main/fashion_sota/product_images/{product_id}.jpg`
- **Source**: Validated images from `products_with_images` table

---

## 🔄 Migration Steps

### Step 1: Create Lakebase Synced Tables

#### 1.1 Create Lakebase Schema
```sql
-- In Databricks SQL
CREATE SCHEMA IF NOT EXISTS lakebase.fashion_sota;
```

#### 1.2 Sync Products Table from product_embeddings
```sql
-- Create Lakebase foreign table synced with Unity Catalog
CREATE FOREIGN TABLE lakebase.fashion_sota.products
USING lakebase.lakebase_catalog
OPTIONS (
  table 'main.fashion_sota.product_embeddings',
  sync_mode 'SNAPSHOT'  -- or 'CONTINUOUS' for real-time updates
);

-- Verify sync
SELECT COUNT(*) FROM lakebase.fashion_sota.products;
-- Expected: 43,916 rows
```

**Why sync from `product_embeddings` instead of `products_with_images`?**
- `product_embeddings` has **everything denormalized** (metadata + embeddings)
- No joins needed in app queries
- Single source of truth for product catalog + vector search

#### 1.3 Create Users Table (Option A: Reuse)
```sql
-- Copy existing users from fashion_demo
CREATE FOREIGN TABLE lakebase.fashion_sota.users
USING lakebase.lakebase_catalog
OPTIONS (
  table 'main.fashion_demo.users',  -- Reuse if schema matches
  sync_mode 'SNAPSHOT'
);
```

#### 1.3 Create Users Table (Option B: Fresh Start)
```sql
-- Create new users table in Unity Catalog first
CREATE TABLE main.fashion_sota.users (
  user_id STRING PRIMARY KEY,
  email STRING NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  preferences MAP<STRING, STRING>
);

-- Then sync to Lakebase
CREATE FOREIGN TABLE lakebase.fashion_sota.users
USING lakebase.lakebase_catalog
OPTIONS (
  table 'main.fashion_sota.users',
  sync_mode 'CONTINUOUS'
);
```

---

### Step 2: Update App Configuration

#### 2.1 Update `core/config.py`
```python
# Unity Catalog (source metadata)
CATALOG: str = "main"
SCHEMA: str = "fashion_sota"  # Changed from fashion_demo

# Lakebase synced tables (Postgres side)
LAKEBASE_SCHEMA: str = "fashion_sota"  # Changed from fashion_demo
LAKEBASE_PRODUCTS_TABLE: str = "products"  # Changed from productsdb
LAKEBASE_USERS_TABLE: str = "users"  # Changed from usersdb
LAKEBASE_USER_FEATURES_TABLE: str = "user_preferences"  # Changed naming

# Unity Catalog - Source Tables (for embeddings)
UC_MULTIMODAL_TABLE: str = "main.fashion_sota.product_embeddings"  # Changed

# Vector Search Indexes (SIMPLIFIED - only 1 index now!)
VS_INDEX: str = "main.fashion_sota.product_embeddings_index"  # New unified index

# Remove these (no longer needed):
# VS_IMAGE_INDEX: str = "main.fashion_demo.vs_image_search"
# VS_TEXT_INDEX: str = "main.fashion_demo.vs_text_search"
# VS_HYBRID_INDEX: str = "main.fashion_demo.vs_hybrid_search"
```

#### 2.2 Update `app.yaml` (Volume Permissions)
```yaml
command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

resources:
  uc_securable:
    # Grant app service principal READ access to fashion_sota volumes
    - securable_type: VOLUME
      securable_full_name: main.fashion_sota.product_images  # Changed
      privilege: READ_VOLUME
```

---

### Step 3: Update Services

#### 3.1 Update `services/vector_search_service.py`

**Before** (3 separate indexes):
```python
self.image_index = settings.VS_IMAGE_INDEX
self.text_index = settings.VS_TEXT_INDEX
self.hybrid_index = settings.VS_HYBRID_INDEX
```

**After** (1 unified index):
```python
self.index_name = settings.VS_INDEX  # Single index for all queries
```

**Simplify search methods**:
```python
async def search(
    self,
    query_vector: np.ndarray,
    num_results: int = 20,
    filters: Optional[Dict[str, Any]] = None,
    columns: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Vector similarity search on unified product_embeddings_index

    Args:
        query_vector: Normalized embedding (512 dims) - works for text, image, or hybrid
        num_results: Number of results to return
        filters: Optional filters (e.g., {"master_category": "Apparel", "price >=": 50})
        columns: Columns to return (all metadata denormalized in embeddings table)

    Returns:
        List of product dictionaries with similarity scores
    """
    # Get index
    index = self._get_index(self.index_name)

    # Default columns (all available since metadata is denormalized)
    if columns is None:
        columns = [
            "product_id",
            "product_display_name",
            "master_category",
            "sub_category",
            "article_type",
            "base_color",
            "price",
            "image_path",
            "gender",
            "season",
            "usage",
            "year",
            "brand"  # Added - available in fashion_sota
        ]

    # Perform search (no need for separate image/text/hybrid methods!)
    results = await loop.run_in_executor(
        None,
        lambda: index.similarity_search(
            query_vector=query_vector.tolist(),
            columns=columns,
            num_results=num_results,
            filters=filters or {}
        )
    )

    # Parse results...
    return products
```

**Remove deprecated methods**:
```python
# DELETE THESE - no longer needed with unified index:
# async def search_image(...)
# async def search_text(...)
# async def search_hybrid(...)
# async def search_cross_modal(...)
```

#### 3.2 Update `routes/v1/products.py` (Image URLs)

**Before**:
```python
def get_image_url(product_id) -> str:
    return f"{WORKSPACE_HOST}/ajax-api/2.0/fs/files/Volumes/main/fashion_demo/raw_data/images/{pid}.jpg"
```

**After**:
```python
def get_image_url(product_id) -> str:
    return f"{WORKSPACE_HOST}/ajax-api/2.0/fs/files/Volumes/main/fashion_sota/product_images/{pid}.jpg"
```

#### 3.3 Update `services/clip_service.py` (No Changes Needed! ✅)
- CLIP endpoint stays the same: `siglip-multimodal-endpoint`
- Embedding dimension stays 512
- FashionCLIP 2.0 is backward compatible

---

### Step 4: Update Repositories

#### 4.1 Update `repositories/lakebase.py`

**Key Changes**:
1. Schema changes from `fashion_demo` to `fashion_sota`
2. Table names change (remove `db` suffix)
3. All product metadata now available (denormalized)

```python
class LakebaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.schema = settings.LAKEBASE_SCHEMA  # Now "fashion_sota"

    async def get_products(
        self,
        limit: int = 24,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "product_display_name",
        sort_order: str = "ASC"
    ) -> List[Dict[str, Any]]:
        """Get products from fashion_sota.products (denormalized embeddings table)"""

        # Build query
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
                brand  -- Now available!
            FROM {self.schema}.{settings.PRODUCTS_TABLE}
            {where_clause}
            ORDER BY {sort_by} {sort_order}
            LIMIT :limit OFFSET :offset
        """

        return await self._execute_query(query, params)
```

---

### Step 5: Test & Validate

#### 5.1 Verify Lakebase Tables
```sql
-- Check products synced correctly
SELECT COUNT(*) FROM lakebase.fashion_sota.products;
-- Expected: 43,916

-- Sample product data
SELECT
    product_id,
    product_display_name,
    master_category,
    price,
    image_path
FROM lakebase.fashion_sota.products
LIMIT 5;

-- Check metadata completeness
SELECT
    COUNT(*) as total,
    COUNT(DISTINCT master_category) as categories,
    COUNT(DISTINCT gender) as genders,
    COUNT(DISTINCT brand) as brands,
    MIN(price) as min_price,
    MAX(price) as max_price
FROM lakebase.fashion_sota.products;
```

#### 5.2 Verify Vector Search Index
```python
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()
index = vsc.get_index("main.fashion_sota.product_embeddings_index")

# Check index status
print(index.describe())
# Expected: status='ONLINE', num_vectors=43916

# Test search
results = index.similarity_search(
    query_vector=[0.1] * 512,  # Dummy vector
    num_results=5
)
print(f"Search works! Got {len(results['result']['data_array'])} results")
```

#### 5.3 Test App Endpoints
```bash
# Start app locally
cd /Users/kevin.ippen/projects/fashion-ecom-site
uvicorn app:app --reload --port 8000

# Test products endpoint
curl http://localhost:8000/api/v1/products?page=1&page_size=10

# Test search endpoint
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "red summer dress", "num_results": 10}'

# Test image upload search
curl -X POST http://localhost:8000/api/v1/search/image \
  -F "image=@test_image.jpg" \
  -F "num_results=10"
```

---

## 📝 Migration Checklist

### Pre-Migration
- [x] Review current architecture (main.fashion_demo)
- [x] Verify `main.fashion_sota.product_embeddings` exists (43,916 rows)
- [x] Confirm `fashion-vector-search` endpoint is online
- [x] Backup current configuration files

### Execute Migration
- [ ] **Step 1**: Create Lakebase schema and synced tables
  - [ ] Create `lakebase.fashion_sota` schema
  - [ ] Sync `fashion_sota.products` from `main.fashion_sota.product_embeddings`
  - [ ] Create/sync `fashion_sota.users` table
  - [ ] Verify row counts match expected values

- [ ] **Step 2**: Update configuration files
  - [ ] Update `core/config.py` (schema, tables, indexes)
  - [ ] Update `app.yaml` (volume permissions)
  - [ ] Update `.env` if needed

- [ ] **Step 3**: Refactor services
  - [ ] Update `services/vector_search_service.py` (unified index)
  - [ ] Update `routes/v1/products.py` (image URLs)
  - [ ] Update `repositories/lakebase.py` (schema names)

- [ ] **Step 4**: Test everything
  - [ ] Verify Lakebase tables accessible
  - [ ] Test vector search queries
  - [ ] Test product listing endpoint
  - [ ] Test search endpoints (text, image, hybrid)
  - [ ] Verify images load correctly

### Post-Migration
- [ ] Deploy to Databricks Apps (if applicable)
- [ ] Update documentation
- [ ] Monitor logs for errors
- [ ] Performance benchmark (compare with old schema)

---

## 🎁 Benefits of This Migration

### 1. Simplified Architecture
- **Before**: 3 separate vector indexes (image, text, hybrid)
- **After**: 1 unified index (handles all modalities)

### 2. Denormalized Data = Faster Queries
- **Before**: Join `products` + `embeddings` tables
- **After**: All metadata in `product_embeddings` (no joins!)

### 3. Production-Ready Data
- **Before**: `fashion_demo` (44K products, some without images)
- **After**: `fashion_sota` (43.9K products, **all validated with images**)

### 4. Better Metadata
- **Added fields**: `brand`, `usage`, enhanced `article_type`
- **Quality**: Cleaner data from SmolVLM attribute extraction

### 5. Future-Proof for Inspiration Search
- **Inspo embeddings** ready at `main.fashion_sota.inspo_embeddings` (~6K images)
- **Style clusters** available for advanced filtering
- **Shop The Look** infrastructure in place

---

## 🚨 Breaking Changes

### API Responses
- **Product IDs**: May differ between fashion_demo and fashion_sota
  - Old: IDs from original Kaggle dataset
  - New: Filtered to products with validated images
- **Image URLs**: Path changes from `/raw_data/images/` to `/product_images/`
- **New Fields**: `brand` now available (was missing in fashion_demo)

### Vector Search
- **Index Names**: Update hardcoded index names in any scripts/notebooks
- **Filters**: Review filter logic (some products removed during quality filtering)

### Lakebase Tables
- **Schema**: All queries must update `fashion_demo.*` → `fashion_sota.*`
- **Table Names**: `productsdb` → `products` (removed `db` suffix)

---

## 📞 Coordination & Next Steps

### Immediate (Do First)
1. **Create Lakebase synced tables** (Step 1)
2. **Update config.py** with new schema/tables (Step 2.1)
3. **Test locally** with new configuration

### Short Term (This Week)
1. **Refactor services** to use unified vector index
2. **Update image URLs** to point to fashion_sota volume
3. **Deploy to Databricks Apps** if applicable

### Future Enhancements (Later)
1. **Enable Inspiration Search** once inspo embeddings complete
2. **Add Style Cluster Filtering** using `product_style_affinity` table
3. **Implement "Shop The Look"** using segmented product matching

---

## 🔧 Rollback Plan (If Needed)

If migration causes issues, rollback is simple:

```python
# In core/config.py, revert to:
SCHEMA: str = "fashion_demo"
LAKEBASE_SCHEMA: str = "fashion_demo"
LAKEBASE_PRODUCTS_TABLE: str = "productsdb"
VS_IMAGE_INDEX: str = "main.fashion_demo.vs_image_search"
VS_TEXT_INDEX: str = "main.fashion_demo.vs_text_search"
VS_HYBRID_INDEX: str = "main.fashion_demo.vs_hybrid_search"
```

```yaml
# In app.yaml, revert to:
resources:
  uc_securable:
    - securable_type: VOLUME
      securable_full_name: main.fashion_demo.raw_data
      privilege: READ_VOLUME
```

No data loss since we're just changing pointers, not modifying source tables.

---

## 📚 Reference: Data Schema Comparison

| Aspect | fashion_demo (Old) | fashion_sota (New) |
|--------|-------------------|-------------------|
| **Products** | 44,424 | 43,916 (validated images) |
| **Schema** | main.fashion_demo | main.fashion_sota |
| **Product Table** | `products` | `product_embeddings` (denormalized) |
| **Embeddings** | `product_embeddings_multimodal` | `product_embeddings` (same table as products!) |
| **Vector Indexes** | 3 separate (image/text/hybrid) | 1 unified index |
| **Vector Endpoint** | `fashion_vector_search` | `fashion-vector-search` (same) |
| **Image Volume** | `/raw_data/images/` | `/product_images/` |
| **Lakebase Schema** | `fashion_demo` | `fashion_sota` |
| **Lakebase Products** | `productsdb` | `products` |
| **Additional Data** | - | Inspo embeddings, style clusters |

---

**Last Updated**: 2026-01-05
**Next Review**: After Lakebase sync completes
**Owner**: Fashion SOTA Team
