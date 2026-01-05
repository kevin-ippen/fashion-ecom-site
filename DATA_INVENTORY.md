# Fashion E-Commerce App - Data Inventory

> Complete inventory of all tables, indexes, and data sources used by the application

## Overview

The application uses **two data access patterns**:
1. **Lakebase PostgreSQL** - Fast SQL queries for product catalog and user data
2. **Vector Search** - Similarity search for recommendations and search features

---

## 1. Lakebase PostgreSQL Tables

Lakebase provides a PostgreSQL interface to Unity Catalog tables for fast SQL access.

### Connection Details
- **Host**: Auto-injected via `PGHOST` env var (when Lakebase resource attached)
- **Database**: `main`
- **Schema**: `fashion_demo`
- **Authentication**: OAuth token as PostgreSQL password

### Tables Accessed via Lakebase

#### A. `fashion_demo.productsdb` (primary product catalog)
**Source Unity Catalog table**: `main.fashion_demo.products`
**Rows**: 44,424 products

**Schema**:
```sql
product_id              INT           -- Primary key
product_display_name    STRING        -- "Nike Air Max 270"
master_category         STRING        -- Apparel, Footwear, Accessories (7 values)
sub_category            STRING        -- Topwear, Shoes, Watches (45 values)
article_type            STRING        -- Tshirts, Sneakers, Watches (143 values)
base_color              STRING        -- Black, White, Red, etc. (46 values)
price                   DOUBLE        -- Product price ($0.50 - $9,999)
image_path              STRING        -- /Volumes/main/fashion_demo/raw_data/images/{id}.jpg
gender                  STRING        -- Men, Women, Boys, Girls, Unisex
season                  STRING        -- Summer, Winter, Fall, Spring
year                    INT           -- 2011-2018
usage                   STRING        -- Casual, Formal, Sports, etc.
```

**Used by**:
- `GET /api/v1/products` - Product listing with filters
- `GET /api/v1/products/{id}` - Product details
- `GET /api/v1/products/filters/options` - Available filter values
- `POST /api/v1/search/text` - Fallback text search (SQL LIKE)

**Code locations**:
- [repositories/lakebase.py:80-88](file:///Users/kevin.ippen/projects/fashion-ecom-site/repositories/lakebase.py#L80-L88) - `get_products()`
- [repositories/lakebase.py:131-139](file:///Users/kevin.ippen/projects/fashion-ecom-site/repositories/lakebase.py#L131-L139) - `get_product_by_id()`
- [repositories/lakebase.py:217-240](file:///Users/kevin.ippen/projects/fashion-ecom-site/repositories/lakebase.py#L217-L240) - `search_products_by_text()`

---

#### B. `fashion_demo.usersdb` (user personas)
**Source Unity Catalog table**: `main.fashion_demo.users`
**Rows**: 5 demo personas

**Schema**:
```sql
user_id                 STRING        -- "user_001", etc.
name                    STRING        -- Display name
segment                 STRING        -- budget, athletic, luxury, etc.
avg_price_point         DOUBLE        -- User's average price preference
preferred_categories    ARRAY<STRING> -- ["Apparel", "Accessories"]
```

**Used by**:
- `GET /api/v1/users` - List all personas
- `GET /api/v1/users/{id}` - Get persona details

**Code locations**:
- [repositories/lakebase.py:157-163](file:///Users/kevin.ippen/projects/fashion-ecom-site/repositories/lakebase.py#L157-L163) - `get_users()`
- [repositories/lakebase.py:165-173](file:///Users/kevin.ippen/projects/fashion-ecom-site/repositories/lakebase.py#L165-L173) - `get_user_by_id()`

---

#### C. `fashion_demo.user_style_featuresdb` (user behavioral embeddings)
**Source Unity Catalog table**: `main.fashion_demo.user_style_features`
**Rows**: 10,000 users (5 personas + 9,995 synthetic)

**Schema**:
```sql
user_id                 STRING              -- User identifier
user_embedding          ARRAY<DOUBLE>       -- 512-dim behavioral vector
segment                 STRING              -- User segment
num_interactions        INT                 -- Total interactions
category_prefs          ARRAY<STRING>       -- Preferred categories
color_prefs             ARRAY<STRING>       -- Preferred colors
avg_price               DOUBLE              -- Average purchase price
min_price               DOUBLE              -- Min price in history
max_price               DOUBLE              -- Max price in history
```

**Used by**:
- `GET /api/v1/search/recommendations/{user_id}` - Personalized recommendations
- `GET /api/v1/users/{id}/profile` - User profile with preferences

**Code locations**:
- [repositories/lakebase.py:175-183](file:///Users/kevin.ippen/projects/fashion-ecom-site/repositories/lakebase.py#L175-L183) - `get_user_style_features()`
- Used in recommendation logic to get user embedding for Vector Search

---

## 2. Unity Catalog Tables (Direct Access)

Some tables are accessed directly via Unity Catalog, not through Lakebase.

### `main.fashion_demo.product_embeddings_multimodal` (embeddings source)
**Rows**: 44,417 products (99.98% coverage)
**Purpose**: **PRIMARY SOURCE** for all Vector Search indexes

**Schema**:
```sql
-- Product metadata (denormalized from products table)
product_id              INT
product_display_name    STRING
master_category         STRING
sub_category            STRING
article_type            STRING
base_color              STRING
price                   DOUBLE
image_path              STRING
gender                  STRING
season                  STRING
year                    INT
usage                   STRING

-- CLIP Embeddings (512-dimensional, L2-normalized)
image_embedding         ARRAY<DOUBLE>    -- From product images
text_embedding          ARRAY<DOUBLE>    -- From text descriptions
hybrid_embedding        ARRAY<DOUBLE>    -- 50% image + 50% text

-- Metadata
embedding_model         STRING           -- "clip-vit-base-patch32"
embedding_dimension     INT              -- 512
updated_at              TIMESTAMP
```

**Delta Table Properties**:
- ✅ Change Data Feed: ENABLED (auto-syncs to Vector Search)
- ✅ Optimized: Z-ORDER BY (master_category, article_type)

**Used by**:
- Vector Search indexes (all 3 indexes built on this table)
- Delta Sync automatically propagates changes to indexes

**NOT directly queried by the app** - only accessed via Vector Search indexes

---

## 3. Vector Search Indexes

All indexes are built on `main.fashion_demo.product_embeddings_multimodal` using Delta Sync.

### Vector Search Endpoint
**Name**: `fashion_vector_search`
**Endpoint ID**: `4d329fc8-1924-4131-ace8-14b542f8c14b`

---

### Index A: `main.fashion_demo.vs_image_search`
**Embedding column**: `image_embedding`
**Dimension**: 512
**Similarity metric**: L2 (with normalized vectors = cosine similarity)

**Used by**:
- `POST /api/v1/search/image` - Image upload search
- Cross-modal text-to-image search

**Query example**:
```python
# Upload image → find visually similar products
image_emb = await clip_service.get_image_embedding(image_bytes)
results = await vector_search_service.search_image(image_emb, num_results=20)
```

**Code location**:
- [services/vector_search_service.py:198-220](file:///Users/kevin.ippen/projects/fashion-ecom-site/services/vector_search_service.py#L198-L220) - `search_image()`

---

### Index B: `main.fashion_demo.vs_text_search`
**Embedding column**: `text_embedding`
**Dimension**: 512

**Used by**:
- `POST /api/v1/search/text` - Text query search
- Cross-modal image-to-text search

**Query example**:
```python
# Text query → find semantically matching products
text_emb = await clip_service.get_text_embedding("red leather jacket")
results = await vector_search_service.search_text(text_emb, num_results=20)
```

**Code location**:
- [services/vector_search_service.py:222-244](file:///Users/kevin.ippen/projects/fashion-ecom-site/services/vector_search_service.py#L222-L244) - `search_text()`

---

### Index C: `main.fashion_demo.vs_hybrid_search` (PRIMARY INDEX)
**Embedding column**: `hybrid_embedding` (50% image + 50% text)
**Dimension**: 512

**Used by**:
- `GET /api/v1/search/recommendations/{user_id}` - **Personalized recommendations** (primary use case)
- Hybrid text+image search
- Best overall search quality

**Query example**:
```python
# User embedding → personalized product recommendations
user_features = await get_user_style_features(user_id)
user_emb = np.array(json.loads(user_features['user_embedding']))
results = await vector_search_service.search_hybrid(
    user_emb,
    num_results=20,
    filters={
        "master_category": ["Apparel", "Accessories"],  # User preferences
        "price": {"$gte": 20, "$lte": 100}
    }
)
```

**Code location**:
- [services/vector_search_service.py:246-268](file:///Users/kevin.ippen/projects/fashion-ecom-site/services/vector_search_service.py#L246-L268) - `search_hybrid()`

---

## 4. Model Serving Endpoints

### `siglip-multimodal-endpoint` (unified endpoint)
**Model**: SigLIP multimodal encoder
**Unity Catalog model**: `main.fashion_demo.clip_multimodal_encoder`
**Dimension**: 512

**Capabilities**:
- Generate text embeddings
- Generate image embeddings
- Single unified endpoint for both modalities

**Used by**:
- All search endpoints (text/image/hybrid)
- Generates query embeddings on-the-fly

**Input formats**:
```python
# Text
{"dataframe_records": [{"text": "red dress"}]}

# Image (base64)
{"dataframe_records": [{"image": "base64_encoded_jpg_string"}]}
```

**Output format**:
```python
{"predictions": [[0.013, 0.053, -0.026, ...]]}  # 512-dim array
```

**Code location**:
- [services/clip_service.py](file:///Users/kevin.ippen/projects/fashion-ecom-site/services/clip_service.py) - Full implementation

---

## 5. Unity Catalog Volumes

### `main.fashion_demo.raw_data` (images volume)
**Path**: `/Volumes/main/fashion_demo/raw_data/images/`
**Contents**: 44,424 product images (JPG format)
**Naming**: `{product_id}.jpg` (e.g., `15970.jpg`)

**Used by**:
- `GET /api/v1/images/{path}` - Serve product images to frontend
- Backend reads from volume, proxies to frontend

**Access methods**:
1. **In notebooks**: Direct file access via `/Volumes/...`
2. **In Databricks Apps**: Files API URL
   ```
   https://{workspace}/ajax-api/2.0/fs/files/Volumes/main/fashion_demo/raw_data/images/{id}.jpg
   ```

**Code location**:
- [routes/v1/images.py](file:///Users/kevin.ippen/projects/fashion-ecom-site/routes/v1/images.py) - Image serving endpoint

---

## 6. Future Tables (In Development)

### `main.fashion_demo.product_extracted_attributes`
**Status**: 🚧 Being populated via SmolVLM batch processing
**Purpose**: Rich visual attributes extracted from product images

**Planned schema**:
```sql
product_id              INT
material                STRING          -- leather, denim, knit, etc.
pattern                 STRING          -- solid, striped, floral, etc.
formality               STRING          -- formal, casual, athletic
style_keywords          ARRAY<STRING>   -- ["vintage", "modern", "minimalist"]
visual_details          ARRAY<STRING>   -- ["has pockets", "has zipper"]
collar_type             STRING          -- crew neck, v-neck, collar
sleeve_length           STRING          -- short, long, sleeveless
fit_type                STRING          -- fitted, regular, loose
extraction_success      BOOLEAN
extraction_timestamp    TIMESTAMP
```

**Intended use**:
- Enrich text descriptions for better semantic search
- Generate richer CLIP text embeddings
- Improve search quality (narrow score ranges → wider differentiation)

---

## Data Flow Summary

### User Product Browsing
```
Frontend Request
    ↓
GET /api/v1/products
    ↓
Lakebase PostgreSQL
    ↓
fashion_demo.productsdb
    ↓
Results with filters/pagination
```

### Text Search
```
User text query
    ↓
POST /api/v1/search/text
    ↓
SigLIP Model Serving (text → 512-dim embedding)
    ↓
Vector Search: vs_text_search index
    ↓
Queries: product_embeddings_multimodal.text_embedding
    ↓
Top 20 products by similarity
```

### Image Search
```
User uploads image
    ↓
POST /api/v1/search/image
    ↓
SigLIP Model Serving (image → 512-dim embedding)
    ↓
Vector Search: vs_image_search index
    ↓
Queries: product_embeddings_multimodal.image_embedding
    ↓
Visually similar products
```

### Personalized Recommendations
```
User selects persona
    ↓
GET /api/v1/search/recommendations/{user_id}
    ↓
Lakebase: fashion_demo.user_style_featuresdb (get user embedding)
    ↓
Vector Search: vs_hybrid_search index (with filters)
    ↓
Queries: product_embeddings_multimodal.hybrid_embedding
    ↓
Apply business rules (60% vector + 40% category/color/price match)
    ↓
Personalized top 20 products
```

---

## Configuration Reference

All table names and endpoints are configured in [core/config.py](file:///Users/kevin.ippen/projects/fashion-ecom-site/core/config.py):

```python
# Lakebase PostgreSQL
LAKEBASE_SCHEMA = "fashion_demo"
LAKEBASE_PRODUCTS_TABLE = "productsdb"
LAKEBASE_USERS_TABLE = "usersdb"
LAKEBASE_USER_FEATURES_TABLE = "user_style_featuresdb"

# Unity Catalog
UC_MULTIMODAL_TABLE = "main.fashion_demo.product_embeddings_multimodal"

# Model Serving
CLIP_ENDPOINT_NAME = "siglip-multimodal-endpoint"
CLIP_UC_MODEL = "main.fashion_demo.clip_multimodal_encoder"

# Vector Search
VS_ENDPOINT_NAME = "fashion_vector_search"
VS_IMAGE_INDEX = "main.fashion_demo.vs_image_search"
VS_TEXT_INDEX = "main.fashion_demo.vs_text_search"
VS_HYBRID_INDEX = "main.fashion_demo.vs_hybrid_search"
```

---

## Quick Query Examples

### Check product count
```sql
-- In Lakebase
SELECT COUNT(*) FROM fashion_demo.productsdb;

-- In Unity Catalog
SELECT COUNT(*) FROM main.fashion_demo.products;
```

### Check embeddings coverage
```sql
SELECT
    COUNT(*) as total_products,
    COUNT(image_embedding) as has_image_emb,
    COUNT(text_embedding) as has_text_emb,
    COUNT(hybrid_embedding) as has_hybrid_emb
FROM main.fashion_demo.product_embeddings_multimodal;
```

### Check user embeddings
```sql
SELECT
    user_id,
    segment,
    num_interactions,
    array_length(category_prefs) as num_category_prefs
FROM fashion_demo.user_style_featuresdb
WHERE user_id LIKE 'user_00%'
LIMIT 5;
```

---

## Summary Statistics

| Asset Type | Name | Rows | Dimension | Access Method |
|------------|------|------|-----------|---------------|
| Table | productsdb | 44,424 | - | Lakebase SQL |
| Table | usersdb | 5 | - | Lakebase SQL |
| Table | user_style_featuresdb | 10,000 | 512 | Lakebase SQL |
| Table | product_embeddings_multimodal | 44,417 | 512 × 3 | Unity Catalog (via Vector Search) |
| Index | vs_image_search | 44,417 | 512 | Vector Search API |
| Index | vs_text_search | 44,417 | 512 | Vector Search API |
| Index | vs_hybrid_search | 44,417 | 512 | Vector Search API |
| Volume | images | 44,424 files | - | Files API / Direct |
| Endpoint | siglip-multimodal-endpoint | - | 512 | Model Serving API |

---

**Last Updated**: 2025-12-31
**Version**: 1.0
