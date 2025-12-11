# Fashion E-Commerce Site - Databricks Context

> **Purpose**: Comprehensive context for Databricks Assistant working on ML enrichment, data pipelines, and feature development

## 🎯 Project Overview

A modern e-commerce storefront with **AI-powered visual search and personalized recommendations** built entirely on Databricks platform.

### High-Level Architecture

```
User Request
    ↓
React Frontend (Databricks Apps)
    ↓
FastAPI Backend (Python)
    ↓
├─ Lakebase (PostgreSQL) ← Product catalog queries
├─ Model Serving ← CLIP embeddings (text/image)
├─ Vector Search ← Similarity search
└─ Unity Catalog ← Data/models/volumes
```

### Key Capabilities
- ✅ **Text Search**: "red leather jacket" → semantic product matching
- ✅ **Image Search**: Upload photo → visually similar products
- ✅ **Personalized Recs**: User-specific product suggestions
- ✅ **Cross-Modal**: Text query → image index (and vice versa)
- 🚧 **Visual Attribute Extraction**: SmolVLM extracting material/style/pattern from images

---

## 📊 Data Assets (Unity Catalog)

### Catalog & Schema
- **Catalog**: `main`
- **Schema**: `fashion_demo`

### Core Tables

#### 1. Products Table (Source)
**Table**: `main.fashion_demo.products`
**Rows**: 44,424 products
**Purpose**: Master product catalog

**Schema**:
```sql
product_id              INT           -- Primary key
product_display_name    STRING        -- "Nike Air Max 270"
master_category         STRING        -- Apparel, Footwear, Accessories (7 values)
sub_category            STRING        -- Topwear, Shoes, Watches (45 values)
article_type            STRING        -- Tshirts, Sneakers, Watches (143 values)
base_color              STRING        -- Black, White, Red, etc. (46 values)
price                   DOUBLE        -- Product price
image_path              STRING        -- /Volumes/main/fashion_demo/raw_data/images/{product_id}.jpg
gender                  STRING        -- Men, Women, Boys, Girls, Unisex
season                  STRING        -- Summer, Winter, Fall, Spring
year                    INT           -- 2011-2018
usage                   STRING        -- Casual, Formal, Sports, etc.
```

**Data Quality**:
- All products have images (44,424 JPGs in UC Volumes)
- Price range: $0.50 - $9,999
- Categories: 60% Apparel, 30% Footwear, 10% Accessories

---

#### 2. Multimodal Embeddings Table (Primary ML Asset)
**Table**: `main.fashion_demo.product_embeddings_multimodal`
**Rows**: 44,417 products (99.98% coverage)
**Purpose**: **SINGLE SOURCE for all Vector Search indexes**

**Schema**:
```sql
-- Product Metadata (joined from products table)
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

-- CLIP Embeddings (all 512-dim, L2-normalized)
image_embedding         ARRAY<DOUBLE>    -- From product images
text_embedding          ARRAY<DOUBLE>    -- From text descriptions
hybrid_embedding        ARRAY<DOUBLE>    -- 50% image + 50% text

-- Metadata
embedding_model         STRING           -- "clip-vit-base-patch32"
embedding_dimension     INT              -- 512
updated_at              TIMESTAMP
```

**Embedding Statistics**:
- Image embeddings: 44,412 valid (99.99%)
- Text embeddings: 44,417 valid (100%)
- All embeddings L2-normalized (norm ≈ 1.0)
- Embedding space: CLIP ViT-B/32 (shared text-image space)

**Delta Properties**:
- ✅ Change Data Feed: ENABLED (for Vector Search auto-sync)
- ✅ Optimized with Z-ORDER by (master_category, article_type)

---

#### 3. Image Embeddings Table (Legacy - for reference)
**Table**: `main.fashion_demo.product_image_embeddings`
**Rows**: 44,424
**Purpose**: Original image-only embeddings (pre-multimodal)

**Note**: Use `product_embeddings_multimodal` for new development

---

#### 4. User Style Features Table
**Table**: `main.fashion_demo.user_style_features`
**Rows**: 10,000 users
**Purpose**: User behavioral embeddings for personalized recommendations

**Schema**:
```sql
user_id             STRING              -- User identifier
user_embedding      ARRAY<DOUBLE>       -- 512-dim preference vector
segment             STRING              -- budget, athletic, luxury, etc.
num_interactions    INT                 -- Total user interactions
category_prefs      ARRAY<STRING>       -- ["Apparel", "Footwear"]
color_prefs         ARRAY<STRING>       -- ["Black", "White", "Blue"]
avg_price           DOUBLE              -- Average purchase price
min_price           DOUBLE              -- Min price in history
max_price           DOUBLE              -- Max price in history
```

**User Embeddings**:
- Generated from interaction history (views, clicks, purchases)
- Same 512-dim CLIP space as products
- Used for: Vector Search with user embedding → personalized products

---

#### 5. Extracted Visual Attributes Table (IN PROGRESS)
**Table**: `main.fashion_demo.product_extracted_attributes`
**Status**: 🚧 Being populated via SmolVLM-2.2B batch processing
**Purpose**: Rich visual attributes extracted from product images

**Schema** (when complete):
```sql
product_id              INT
product_display_name    STRING
-- Original metadata...

-- EXTRACTED ATTRIBUTES (from SmolVLM-2.2B)
material                STRING          -- leather, denim, knit, woven, synthetic, metal, canvas
pattern                 STRING          -- solid, striped, floral, geometric, polka dots, checkered
confidence_material     STRING          -- high, medium, low
formality               STRING          -- formal, business casual, casual, athletic
style_keywords          ARRAY<STRING>   -- ["vintage", "modern", "minimalist"]
visual_details          ARRAY<STRING>   -- ["has pockets", "has zipper", "has buttons"]
collar_type             STRING          -- crew neck, v-neck, collar, hooded
sleeve_length           STRING          -- short, long, sleeveless
fit_type                STRING          -- fitted, regular, loose, oversized

-- Metadata
extraction_success      BOOLEAN
extraction_errors       ARRAY<STRING>
extraction_timestamp    TIMESTAMP
```

**Use Case**: Generate enriched text descriptions for improved CLIP embeddings
```python
# Current text description:
"Nike Men Tshirt Black Casual Summer"

# ENRICHED with visual attributes:
"Nike Men Tshirt Black Casual Summer knit fabric solid color crew neck
short sleeve athletic sporty has logo comfortable"
```

---

### Unity Catalog Volumes

#### Images Volume
**Path**: `/Volumes/main/fashion_demo/raw_data/images/`
**Contents**: 44,424 product images (JPG format)
**Naming**: `{product_id}.jpg` (e.g., `15970.jpg`)
**Access**: Direct file access in notebooks, HTTP via Files API in apps

**Files API URL Pattern**:
```
https://{workspace_url}/ajax-api/2.0/fs/files/Volumes/main/fashion_demo/raw_data/images/{product_id}.jpg
```

---

## 🤖 Model Serving Endpoints

### 1. CLIP Multimodal Encoder (Primary)
**Endpoint Name**: `clip-multimodal-encoder`
**UC Model**: `main.fashion_demo.clip_multimodal_encoder`
**Base Model**: `openai/clip-vit-base-patch32`
**Capability**: Generate embeddings from text OR images
**Workload Size**: Large (64 concurrent requests)
**Scale to Zero**: ✅ Enabled

**Input Formats**:
```python
# Text input
{
  "dataframe_records": [{"text": "red leather jacket"}]
}

# Image input
{
  "dataframe_records": [{"image": "base64_encoded_jpg"}]
}
```

**Output Format**:
```python
{
  "predictions": [[0.013, 0.053, -0.026, ...]]  # 512-dim array
}
```

**URL**: `https://{workspace}/serving-endpoints/clip-multimodal-encoder/invocations`

---

### 2. CLIP Image Encoder (Legacy)
**Endpoint Name**: `clip-image-encoder`
**Purpose**: Image-only encoding (pre-multimodal)
**Status**: Active but use `clip-multimodal-encoder` for new work

---

### 3. SmolVLM-2.2B (In Development)
**Purpose**: Visual attribute extraction from product images
**Model**: `HuggingFaceTB/SmolVLM-Instruct`
**Status**: 🚧 Batch processing via Databricks jobs (not deployed endpoint)
**Use**: Extract material, pattern, style, formality from images

---

## 🔍 Vector Search

### Vector Search Endpoint
**Endpoint Name**: `fashion_vector_search`
**Endpoint ID**: `4d329fc8-1924-4131-ace8-14b542f8c14b`
**Index Type**: Delta Sync (auto-updates from source Delta table)

### Vector Search Indexes (3 Total)

All indexes built on: `main.fashion_demo.product_embeddings_multimodal`

#### Index 1: Image Search
**Index Name**: `main.fashion_demo.vs_image_search`
**Embedding Column**: `image_embedding`
**Use Case**: Visual similarity search (upload image → find similar products)
**Similarity Metric**: L2 distance (with L2-normalized vectors = cosine similarity)

#### Index 2: Text Search
**Index Name**: `main.fashion_demo.vs_text_search`
**Embedding Column**: `text_embedding`
**Use Case**: Semantic text search ("red dress" → matching products)

#### Index 3: Hybrid Search (Most Used)
**Index Name**: `main.fashion_demo.vs_hybrid_search`
**Embedding Column**: `hybrid_embedding`
**Use Case**:
- Default for recommendations (user embedding → products)
- Best overall quality (combines visual + semantic info)
- Cross-modal queries (text → image or image → text)

### Query Pattern
```python
from databricks.vector_search.client import VectorSearchClient

client = VectorSearchClient()
index = client.get_index(index_name="main.fashion_demo.vs_hybrid_search")

results = index.similarity_search(
    query_vector=[0.01, 0.02, ...],  # 512-dim embedding
    columns=[
        "product_id", "product_display_name", "master_category",
        "sub_category", "article_type", "base_color", "price",
        "image_path", "gender", "season", "usage", "year"
    ],
    num_results=20,
    filters={
        "master_category": ["Apparel", "Footwear"],        # IN operator (list)
        "price": {"$gte": 50, "$lte": 200}                 # Range (nested dict)
    }
)

# Results include similarity score as last element in each row
# row = [product_id, name, ..., similarity_score]
```

**Important**:
- Score is auto-appended as LAST element (not a column)
- To get score: `score = row[-1]`
- Typical score ranges: 0.50-0.70 (higher = more similar)

---

## 🔌 API Endpoints (FastAPI Backend)

### Base URL
- **Local Dev**: `http://localhost:8000`
- **Databricks Apps**: `https://{app-url}`

### Endpoint Structure
All endpoints under `/api/v1/`

### Search Endpoints

#### Text Search
**Endpoint**: `POST /api/v1/search/text`
**Body**:
```json
{
  "query": "red summer dress",
  "limit": 20,
  "user_id": "user_001"
}
```
**Flow**: Query → CLIP text embedding → Vector Search hybrid index → Results

---

#### Image Search
**Endpoint**: `POST /api/v1/search/image`
**Body**: `multipart/form-data` with image file
**Flow**: Image → CLIP image embedding → Vector Search image index → Results

---

#### Recommendations
**Endpoint**: `GET /api/v1/search/recommendations/{user_id}`
**Query Params**:
- `limit` (int, default=20)
- `restrict_category` (bool, default=True)
- `restrict_price` (bool, default=True)
- `restrict_color` (bool, default=False)

**Flow**:
1. Load user embedding from `user_style_features`
2. Build filters based on user preferences
3. Vector Search hybrid index with user embedding + filters
4. Apply rule-based scoring (60% vector + 40% rules)
5. Return personalized products

---

### Product Endpoints

#### List Products
**Endpoint**: `GET /api/v1/products`
**Query Params**: `limit`, `offset`, `gender`, `category`, `min_price`, `max_price`
**Data Source**: Lakebase PostgreSQL (synced from UC tables)

#### Get Product Details
**Endpoint**: `GET /api/v1/products/{product_id}`
**Returns**: Full product info + image URL

---

### User Endpoints

#### List Personas
**Endpoint**: `GET /api/v1/users`
**Returns**: 5 demo personas (Budget, Athletic, Luxury, Professional, Gen-Z)

#### Get User Profile
**Endpoint**: `GET /api/v1/users/{user_id}/profile`
**Returns**: User preferences, purchase history, style features

---

## 🚧 Current ML Workstreams

### 1. Visual Attribute Extraction (IN PROGRESS)
**Goal**: Extract rich semantic attributes from product images to improve search quality

**Approach**:
- **Model**: SmolVLM-2.2B (vision-language model)
- **Method**: Batch processing on GPU cluster (2-8 workers, T4 GPUs)
- **Processing**: 3 prompts per image (material, style, garment details)
- **Output**: `product_extracted_attributes` table

**Attributes Being Extracted**:
```python
# Tier 1: High confidence
material = ["leather", "denim", "knit fabric", "woven fabric", "synthetic", "metal", "canvas"]
pattern = ["solid color", "striped", "floral print", "geometric", "polka dots", "checkered"]
formality = ["formal", "business casual", "casual", "athletic"]
collar = ["crew neck", "v-neck", "collar", "hooded", "turtleneck"]
sleeves = ["short sleeve", "long sleeve", "sleeveless"]

# Tier 2: Medium confidence
style_keywords = ["athletic", "vintage", "modern", "minimalist", "bohemian", "professional"]
visual_details = ["has pockets", "has buttons", "has zipper", "has hood", "has logo"]
fit = ["fitted", "regular", "loose", "oversized", "cannot determine"]
```

**Status**:
- ✅ Notebooks created: `smolvlm_batch_attribute_extraction.py`
- ✅ Optimized for distributed GPU processing (mapInPandas)
- ✅ Prompts engineered for consistent JSON output
- 🚧 Test run: 100 products
- 🚧 Full run: 44,424 products (~4 hours on 8 workers)

**Next Steps**:
1. Complete test extraction (100 products)
2. Validate quality (success rate >85%)
3. Scale to full catalog
4. Generate enriched text descriptions
5. Regenerate CLIP text embeddings
6. A/B test search quality improvement

---

### 2. Search Quality Improvements (PLANNED)
**Goal**: Improve search precision and result diversity

**Strategies**:
- ✅ Enrich text descriptions (with visual attributes)
- 🚧 Query expansion (synonyms, related terms)
- 🚧 Result diversity (MMR algorithm)
- 🚧 Re-ranking with business rules
- 🚧 Weighted hybrid search (multiple signals)

**Expected Impact**:
- Precision: +20-30%
- Score distribution: 2% → 10-15% range (better differentiation)
- CTR: +15-25%

---

### 3. Complete-the-Look Recommendations (PLANNED)
**Goal**: "Customers who bought X also bought Y" style recommendations

**Approach**:
- Use DeepFashion2 or FashionGen models
- Complementary item detection (shirt → pants, shoes)
- Category compatibility rules

**Notebook**: `deepfashion2_complete_the_look.py` (created)

---

## 🛠️ Tech Stack

### Data & ML
- **Databricks Runtime**: 14.3 LTS ML (with GPU support for SmolVLM)
- **Delta Lake**: All tables
- **Unity Catalog**: Data governance
- **MLflow**: Model tracking & serving
- **Vector Search**: Similarity search
- **Lakebase**: Fast SQL access (UC → PostgreSQL sync)

### Backend
- **FastAPI**: Python web framework
- **Pydantic**: Data validation
- **SQLAlchemy + asyncpg**: Database access
- **aiohttp**: Async HTTP (for Model Serving calls)

### Frontend
- **React 18** + TypeScript
- **Vite**: Build tool
- **Tailwind CSS**: Styling
- **TanStack Query**: Server state
- **Zustand**: Client state

---

## 📈 Performance Characteristics

### Vector Search Query Latency
- **Typical**: 200-500ms for 20 results
- **With filters**: +50-100ms
- **Cold start** (endpoint): +5-10 seconds (scale-to-zero)

### CLIP Embedding Generation
- **Text**: 50-100ms per embedding
- **Image**: 150-300ms per embedding
- **Batch**: ~10-20 images/sec (on GPU)

### SmolVLM Attribute Extraction
- **Single image**: 3-5 seconds (3 prompts)
- **Throughput**: 20 products/minute per T4 GPU worker
- **Full catalog**: ~4 hours on 8-worker cluster

---

## 🎯 Key Success Metrics

### Search Quality
- **Current Score Range**: 52-55% (text), 67-70% (image)
- **Target**: 10-15% range (better differentiation)
- **Success Rate** (attribute extraction): >85%

### User Engagement
- **CTR**: Baseline → Target +15-25%
- **Conversion**: Baseline → Target +10-15%
- **Time to first click**: Baseline → Target -20%

### Data Quality
- **Embedding coverage**: 99.98% (44,417/44,424)
- **Image availability**: 100% (44,424/44,424)
- **Attribute extraction**: Target 85-90% success rate

---

## 🔐 Authentication

### Databricks SDK/API
- **Method**: OAuth M2M (service principal)
- **Env Vars**: `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`
- **Token**: Auto-refresh via unified auth

### Model Serving
- **Auth**: Bearer token (from Databricks OAuth)
- **Headers**: `Authorization: Bearer {token}`

### Lakebase
- **Auth**: OAuth token as PostgreSQL password
- **Connection**: `postgresql+asyncpg://user:token@host:5432/main`

---

## 📁 Important File Locations

### Notebooks
- `notebooks/smolvlm_batch_attribute_extraction.py` - Visual attribute extraction
- `notebooks/join_enriched_attributes.sql` - Join extracted attributes to products
- `notebooks/cpu_distributed_attribute_extraction.py` - CPU-based alternative
- `notebooks/deepfashion2_complete_the_look.py` - Complete-the-look recommendations

### Backend Code
- `app.py` - FastAPI entrypoint
- `routes/v1/search.py` - Search endpoints
- `routes/v1/products.py` - Product endpoints
- `services/clip_service.py` - CLIP Model Serving integration
- `services/vector_search_service.py` - Vector Search integration
- `repositories/lakebase.py` - Database access

### Documentation
- `RECOMMENDATIONS_ARCHITECTURE.md` - Search/recommendations design
- `SEARCH_QUALITY_IMPROVEMENTS.md` - Improvement strategies
- `SMOLVLM_ATTRIBUTE_EXTRACTION_PLAN.md` - Extraction project plan
- `CLIP_EMBEDDINGS_UPDATE.md` - Embeddings reference
- `README.md` - Project overview

---

## 🚀 Quick Reference: Common Tasks

### Query Vector Search
```python
from databricks.vector_search.client import VectorSearchClient

client = VectorSearchClient()
index = client.get_index("main.fashion_demo.vs_hybrid_search")

results = index.similarity_search(
    query_vector=embedding.tolist(),
    columns=["product_id", "product_display_name", "price", "base_color"],
    num_results=20,
    filters={"price": {"$gte": 50, "$lte": 100}}
)
```

### Generate CLIP Embedding
```python
from services.clip_service import clip_service

# Text
text_emb = await clip_service.get_text_embedding("red dress")

# Image
with open("image.jpg", "rb") as f:
    image_emb = await clip_service.get_image_embedding(f.read())
```

### Read Product Data
```python
products = spark.table("main.fashion_demo.products")
products.filter("price < 50").show()
```

### Access User Embeddings
```python
user_features = spark.table("main.fashion_demo.user_style_features")
user = user_features.filter("user_id = 'user_006327'").first()
user_embedding = user["user_embedding"]  # 512-dim array
```

---

## 📞 Support & Resources

- **Databricks Docs**: https://docs.databricks.com
- **Vector Search Docs**: https://docs.databricks.com/en/generative-ai/vector-search.html
- **Model Serving Docs**: https://docs.databricks.com/en/machine-learning/model-serving/
- **CLIP Paper**: https://arxiv.org/abs/2103.00020

---

**Last Updated**: 2025-12-10
**Version**: 1.0
