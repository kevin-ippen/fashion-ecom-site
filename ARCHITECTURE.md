# Fashion E-Commerce Site Architecture

A modern fashion e-commerce application powered by Databricks, featuring AI-driven visual search, semantic text search, and personalized recommendations using CLIP embeddings and Vector Search.

## System Overview

```
                                    +---------------------------+
                                    |     Databricks Apps       |
                                    |   (Hosted Deployment)     |
                                    +---------------------------+
                                               |
                     +-------------------------+-------------------------+
                     |                                                   |
            +--------v--------+                                 +--------v--------+
            |    Frontend     |                                 |     Backend     |
            |   React + Vite  |  <-- REST API -->                |    FastAPI      |
            |   TailwindCSS   |                                 |    Python 3.11  |
            +-----------------+                                 +--------+--------+
                                                                         |
                    +----------------------------------------------------+--------------------+
                    |                        |                           |                    |
           +--------v--------+      +--------v--------+         +--------v--------+  +-------v--------+
           |    Lakebase     |      |  Vector Search  |         |  Model Serving  |  |  UC Volumes    |
           |   (PostgreSQL)  |      |    Endpoint     |         |  (FashionCLIP)  |  | (Images)       |
           +-----------------+      +-----------------+         +-----------------+  +----------------+
                    |                        |                           |
           +--------v--------+      +--------v--------+         +--------v--------+
           | fashion_sota    |      | product_        |         | fashionclip-    |
           | .products       |      | embeddings_     |         | endpoint        |
           | .users          |      | us_relevant_idx |         | (512-dim)       |
           +-----------------+      +-----------------+         +-----------------+
```

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React 18, Vite, TailwindCSS, React Query | Modern SPA with responsive design |
| Backend | FastAPI, Python 3.11, Pydantic | Async REST API |
| Database | Lakebase (PostgreSQL) | Low-latency OLTP queries |
| Data Lake | Unity Catalog (Delta Lake) | Source of truth for products/embeddings |
| Vector Search | Databricks Vector Search | Similarity search on embeddings |
| ML Model | FashionCLIP (ViT-B/32) | 512-dim multimodal embeddings |
| Hosting | Databricks Apps | Managed deployment with OAuth |

---

## Frontend Architecture

**Location**: [frontend/](frontend/)

### Pages

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | [Home.tsx](frontend/src/pages/Home.tsx) | Landing page with featured products |
| `/products` | [Products.tsx](frontend/src/pages/Products.tsx) | Product catalog with filters |
| `/products/:id` | [ProductDetail.tsx](frontend/src/pages/ProductDetail.tsx) | Product page with "Similar Products" |
| `/search` | [Search.tsx](frontend/src/pages/Search.tsx) | Text and image search |
| `/profile/:userId` | [UserProfile.tsx](frontend/src/pages/UserProfile.tsx) | User profile with recommendations |
| `/cart` | [Cart.tsx](frontend/src/pages/Cart.tsx) | Shopping cart |

### Key Components

- **[SmartSearch](frontend/src/components/search/SmartSearch.tsx)**: Text input + image upload for search
- **[ProductCard](frontend/src/components/product/ProductCard.tsx)**: Product display with quick view
- **[FilterDrawer](frontend/src/components/filters/FilterDrawer.tsx)**: Faceted filtering (category, color, price)
- **[PersonaSelector](frontend/src/components/user/PersonaSelector.tsx)**: Demo persona switching

### State Management

- **[cartStore.ts](frontend/src/stores/cartStore.ts)**: Zustand store for cart state
- **[personaStore.ts](frontend/src/stores/personaStore.ts)**: Zustand store for demo personas
- **React Query**: Server state caching for API data

---

## Backend Architecture

**Location**: Root directory (FastAPI app)

### Entry Point

[app.py](app.py) - FastAPI application with:
- CORS middleware
- Static file serving for frontend
- OAuth authentication via Databricks Apps

### API Routes

**Prefix**: `/api/v1`

| Route | File | Description |
|-------|------|-------------|
| `/products` | [routes/v1/products.py](routes/v1/products.py) | Product CRUD, filtering, similar products |
| `/search` | [routes/v1/search.py](routes/v1/search.py) | Text, image, and cross-modal search |
| `/users` | [routes/v1/users.py](routes/v1/users.py) | User profiles and personas |
| `/images` | [routes/v1/images.py](routes/v1/images.py) | Product image proxy |
| `/healthcheck` | [routes/v1/healthcheck.py](routes/v1/healthcheck.py) | Health and readiness probes |

### Key Endpoints

```
GET  /api/v1/products                    # List products with filters
GET  /api/v1/products/{id}               # Get product details
GET  /api/v1/products/{id}/similar       # Get visually similar products (Vector Search)
GET  /api/v1/products/filters            # Get filter options

POST /api/v1/search/text                 # Semantic text search (CLIP)
POST /api/v1/search/image                # Visual image search (CLIP)
POST /api/v1/search/cross-modal          # Cross-modal search
GET  /api/v1/search/recommendations/{id} # Personalized recommendations

GET  /api/v1/users/personas              # List demo personas
GET  /api/v1/users/{id}                  # Get user profile
```

---

## Services Layer

### [CLIPService](services/clip_service.py)
Generates 512-dimensional embeddings using FashionCLIP model serving endpoint.

```python
# Text embedding (for semantic search)
embedding = await clip_service.get_text_embedding("red summer dress")

# Image embedding (for visual search)
embedding = await clip_service.get_image_embedding(image_bytes)

# Hybrid embedding (weighted combination)
embedding = await clip_service.get_hybrid_embedding(text="dress", image=bytes, text_weight=0.5)
```

### [VectorSearchService](services/vector_search_service.py)
Queries the Vector Search index for similarity search.

```python
# Find similar products
results = await vector_search_service.search(
    query_vector=embedding,
    index_name="main.fashion_sota.product_embeddings_index",
    num_results=20,
    filters={"gender": "Women"}
)
```

### [RecommendationsService](services/recommendations_service.py)
Generates "Similar Products" recommendations with:
- Category compatibility filtering
- Color diversity (min 2 colors in results)
- Enrichment from Lakebase for full product details

### [IntelligentRecommendationsService](services/intelligent_recommendations_service.py)
ML-powered personalized recommendations using:
- User taste embeddings (pre-computed)
- MMR (Maximal Marginal Relevance) for diversity
- Persona-specific filtering

---

## Data Layer

### Lakebase (PostgreSQL)
**Purpose**: Low-latency OLTP queries for the web application

**Schema**: `fashion_sota`

| Table | Rows | Description |
|-------|------|-------------|
| `products_lakebase` | 43,916 | Product catalog (synced from UC) |
| `users_lakebase` | ~6 | Demo personas with taste embeddings |

**Repository**: [repositories/lakebase.py](repositories/lakebase.py)

### Unity Catalog (Delta Lake)
**Purpose**: Source of truth, ML training, batch processing

**Catalog**: `main.fashion_sota`

| Table | Description |
|-------|-------------|
| `product_embeddings` | Products + 512-dim CLIP embeddings |
| `users` | User accounts |
| `user_preferences` | User style preferences |

### Database Connection
[core/database.py](core/database.py) - Async SQLAlchemy with OAuth token injection

```python
# Connection string built dynamically with OAuth token
url = f"postgresql+asyncpg://{user}:{oauth_token}@{host}:{port}/{database}"
```

---

## Embeddings & Vector Search

### Where Embeddings Are Used

| Feature | Embedding Source | Index | Description |
|---------|-----------------|-------|-------------|
| Similar Products | Pre-calculated IDs (batch) | Lakebase JOIN | Find visually similar items |
| Complete the Look | Pre-calculated IDs (batch) | Lakebase JOIN | Outfit pairing recommendations |
| Text Search | CLIP text encoder (real-time) | `product_embeddings_us_relevant_index` | Semantic search |
| Image Search | CLIP image encoder (real-time) | `product_embeddings_us_relevant_index` | Visual similarity |
| Personalized Recs | User taste embedding (stored) | `product_embeddings_us_relevant_index` | User-to-product matching |

### Pre-Calculated Recommendations (Batch Inference)

Product recommendations are pre-computed via batch inference for optimal performance:

```
products_lakebase table:
├── similar_product_ids: JSONB        # [12345, 67890, ...] - visually similar
├── complete_the_set_ids: JSONB       # [55555, 66666, ...] - outfit pairings
└── recommendations_updated_at: TIMESTAMP

Performance:
├── With pre-calculated: ~5ms (simple JOIN)
└── Without (fallback): ~500ms (Vector Search + SQL warehouse)
```

**API Behavior**:
1. `/products/{id}/similar` - Checks `similar_product_ids` first, falls back to Vector Search
2. `/products/{id}/complete-the-look` - Checks `complete_the_set_ids` first, falls back to lookbook query

**Batch Inference Pipeline** (Databricks notebook):
- Runs daily/weekly to refresh recommendations
- Uses Vector Search for similar products
- Uses lookbook co-occurrence data for outfit pairings
- Writes results to Lakebase via batch UPDATE

See: [scripts/add_precomputed_recommendations_columns.sql](scripts/add_precomputed_recommendations_columns.sql)

### Embedding Pipeline

```
1. Product Images
   └── FashionCLIP Image Encoder → 512-dim image embedding

2. Product Text (name + category + color)
   └── FashionCLIP Text Encoder → 512-dim text embedding

3. Hybrid Embedding = 0.6 * image_embedding + 0.4 * text_embedding
   └── Stored in product_embeddings.embedding column

4. User Taste Embedding
   └── Weighted average of liked products' embeddings
   └── Stored in users_lakebase.taste_embedding column
```

### Vector Search Index

```
Index: main.fashion_sota.product_embeddings_us_relevant_index
├── Endpoint: one-env-shared-endpoint-15
├── Source Table: main.fashion_sota.product_embeddings_us_relevant
├── Primary Key: product_id
├── Embedding Column: embedding (512 dimensions)
├── Pipeline Type: DELTA_SYNC (auto sync)
└── Status: Online
```

**Sync Command** (if needed):
```bash
databricks vector-search-indexes sync-index "main.fashion_sota.product_embeddings_us_relevant_index" --profile work
```

---

## Databricks Assets

### Model Serving Endpoint

| Endpoint | Model | Input | Output |
|----------|-------|-------|--------|
| `fashionclip-endpoint` | FashionCLIP (ViT-B/32) | text + image (base64) | 512-dim embedding |

**Invocation**:
```python
POST /serving-endpoints/fashionclip-endpoint/invocations
{
  "dataframe_records": [{"text": "red dress", "image": "base64..."}]
}
```

### Vector Search Endpoint

| Endpoint | Indexes |
|----------|---------|
| `one-env-shared-endpoint-15` | `product_embeddings_us_relevant_index` |

### UC Volumes

| Volume | Path | Content |
|--------|------|---------|
| Product Images | `/Volumes/main/fashion_sota/product_images/` | {product_id}.jpg files |

### SQL Warehouse

| ID | Purpose |
|----|---------|
| `148ccb90800933a1` | Ad-hoc queries, schema validation |

---

## Configuration

[core/config.py](core/config.py) - Pydantic settings with environment variable support

### Key Settings

```python
# Schema
CATALOG = "main"
SCHEMA = "fashion_sota"

# Lakebase
LAKEBASE_HOST = os.getenv("PGHOST")
LAKEBASE_DATABASE = "databricks_postgres"
LAKEBASE_SCHEMA = "fashion_sota"

# Vector Search
VS_ENDPOINT_NAME = "one-env-shared-endpoint-15"
VS_INDEX = "main.fashion_sota.product_embeddings_us_relevant_index"

# Model Serving
CLIP_ENDPOINT_NAME = "fashionclip-endpoint"
CLIP_EMBEDDING_DIM = 512
```

### Environment Variables (Databricks Apps)

```bash
DATABRICKS_HOST          # Workspace URL
DATABRICKS_CLIENT_ID     # Service principal
DATABRICKS_CLIENT_SECRET # Service principal secret
PGHOST                   # Lakebase host (auto-injected)
PGUSER                   # Lakebase user (auto-injected)
```

---

## Deployment

### Databricks Apps

[app.yaml](app.yaml) - Deployment configuration

```yaml
command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

resources:
  uc_securable:
    - securable_type: VOLUME
      securable_full_name: main.fashion_sota.product_images
      privilege: READ_VOLUME
```

### Build & Deploy

```bash
# Build frontend
cd frontend && npm run build && cd ..

# Deploy to Databricks Apps
databricks apps deploy fashion-ecom --source-code-path . --profile work
```

---

## Data Flow Examples

### 1. Text Search: "red summer dress"

```
User types "red summer dress"
    │
    ▼
Frontend → POST /api/v1/search/text
    │
    ▼
CLIPService.get_text_embedding("red summer dress")
    │
    ▼
FashionCLIP Endpoint → 512-dim embedding
    │
    ▼
VectorSearchService.search(embedding, index="product_embeddings_index")
    │
    ▼
Vector Search returns top 20 products with similarity scores
    │
    ▼
Response with product details + image URLs
```

### 2. Similar Products

```
User views product #12345
    │
    ▼
Frontend → GET /api/v1/products/12345/similar
    │
    ▼
Fetch product embedding from Lakebase (products_lakebase)
    │
    ▼
VectorSearchService.search(product_embedding)
    │
    ▼
RecommendationsService.get_similar_products()
    ├── Filter out source product
    ├── Diversify by color
    └── Enrich with Lakebase data
    │
    ▼
Return 6 similar products
```

### 3. Personalized Recommendations

```
User selects "Luxury Emma" persona
    │
    ▼
Frontend → GET /api/v1/search/recommendations/{user_id}
    │
    ▼
Fetch user taste_embedding from users_lakebase
    │
    ▼
VectorSearchService.search(user_embedding)
    │
    ▼
IntelligentRecommendationsService
    ├── Apply MMR for diversity
    ├── Apply persona price filters
    └── Add personalization reasons
    │
    ▼
Return personalized product feed
```

---

## Project Structure

```
fashion-ecom-site/
├── app.py                    # FastAPI entry point
├── app.yaml                  # Databricks Apps config
├── core/
│   ├── config.py             # Settings & environment
│   └── database.py           # Async SQLAlchemy setup
├── routes/
│   └── v1/
│       ├── products.py       # Product endpoints
│       ├── search.py         # Search endpoints
│       ├── users.py          # User endpoints
│       └── images.py         # Image proxy
├── services/
│   ├── clip_service.py       # CLIP model client
│   ├── vector_search_service.py  # Vector Search client
│   ├── recommendations_service.py # Similar products
│   └── intelligent_recommendations_service.py # Personalized recs
├── repositories/
│   └── lakebase.py           # Database queries
├── models/
│   └── schemas.py            # Pydantic models
├── frontend/
│   ├── src/
│   │   ├── pages/            # React pages
│   │   ├── components/       # UI components
│   │   ├── stores/           # Zustand stores
│   │   └── api/              # API client
│   └── package.json
├── scripts/
│   └── create_product_embeddings_index.py  # Vector index setup
└── notebooks/
    └── production/           # Data pipeline notebooks
```

---

## Quick Reference

### Recreate Vector Search Index

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import *

w = WorkspaceClient()
w.vector_search_indexes.create_index(
    name="main.fashion_sota.product_embeddings_index",
    endpoint_name="fashion-vector-search",
    primary_key="product_id",
    index_type=VectorIndexType.DELTA_SYNC,
    delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
        source_table="main.fashion_sota.product_embeddings",
        embedding_vector_columns=[
            EmbeddingVectorColumn(name="embedding", embedding_dimension=512)
        ],
        pipeline_type=PipelineType.TRIGGERED
    )
)
```

### Check Index Status

```bash
databricks vector-search-indexes get-index "main.fashion_sota.product_embeddings_index" --profile work
```

### Sync Products to Lakebase

See [scripts/setup_lakebase_fashion_sota_v2.sql](scripts/setup_lakebase_fashion_sota_v2.sql)

---

## Version

- **App Version**: 2.0.0
- **Schema**: `main.fashion_sota`
- **Products**: 43,916 (quality filtered)
- **Embedding Dimension**: 512 (FashionCLIP ViT-B/32)
