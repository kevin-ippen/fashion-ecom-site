# Recommendations & Search Architecture

## Current Implementation Status

### 🎯 Recommendations (Implemented)
**Status**: ✅ **Working** - Rule-based personalization using user profiles

**Endpoint**: `GET /api/v1/search/recommendations/{user_id}`

**How It Works**:
1. **Load User Persona** from `data/personas.json`
2. **Filter by Price Range**: User's 25th-75th percentile ± 20%
3. **Score Products** based on:
   - **Color Match** (+0.3): Does product color match user preferences?
   - **Price Match** (+0.2): How close is price to user's average?
   - **Base Score** (0.5): All products start here
4. **Sort by Score** and return top N products

**Example**:
```python
# User: "Luxury Fashionista"
# Preferences: High-end brands, $100-$500, prefers Black/White/Gold

filters = {
    "min_price": persona["p25_price"] * 0.8,  # $80
    "max_price": persona["p75_price"] * 1.2   # $600
}

# Score each product
score = 0.5  # Base
if product.color in ["Black", "White", "Gold"]:
    score += 0.3  # Color match
if abs(product.price - $300) < $100:
    score += 0.2  # Price match

# Result: score = 0.5 + 0.3 + 0.2 = 1.0 (perfect match!)
```

**Personalization Reasons** shown to user:
- "Matches your preference for Black items"
- "Within your typical price range ($100-$500)"

**Data Source**:
- User preferences: `ecom.fashion_demo.user_style_featuresdb`
- Products: `ecom.fashion_demo.productsdb`

---

### 🔍 Text Search (Basic Implementation)
**Status**: ⚠️ **Partially Implemented** - Simple keyword matching only

**Endpoint**: `POST /api/v1/search/text`

**How It Works**:
```python
# Simple PostgreSQL ILIKE search
SELECT *
FROM ecom.fashion_demo.productsdb
WHERE LOWER(product_display_name) ILIKE '%{query}%'
   OR LOWER(article_type) ILIKE '%{query}%'
   OR LOWER(sub_category) ILIKE '%{query}%'
LIMIT 20
```

**Example**:
```bash
Query: "red dress"
Returns: All products with "red" OR "dress" in name/category
```

**Current Limitation**: No semantic understanding - "scarlet gown" won't match "red dress"

---

### 🖼️ Image Search (Not Implemented)
**Status**: ❌ **Placeholder** - Returns random products

**Endpoint**: `POST /api/v1/search/image`

**Current Implementation**:
```python
# TODO: Implement CLIP image embedding generation
# For now, return random products with mock similarity scores
products = await repo.get_products(limit=limit)
for p in products:
    p.similarity_score = random.uniform(0.7, 0.95)  # Fake score
```

**What It Should Do**:
1. User uploads image
2. Generate CLIP embedding for uploaded image
3. Compare with product image embeddings in database
4. Return most similar products (cosine similarity)

---

## 🚀 Intended Architecture (With CLIP Model Serving)

### Overview
Recommendations and search **share the same vector similarity infrastructure**:
- Both use **CLIP embeddings** (768-dimensional vectors)
- Both compare embeddings using **cosine similarity**
- Both return products ranked by similarity score

### CLIP Model Serving Endpoint

**Configuration** ([core/config.py:58](core/config.py#L58)):
```python
CLIP_ENDPOINT: Optional[str] = os.getenv("CLIP_ENDPOINT")
# Example: https://your-workspace.cloud.databricks.com/serving-endpoints/clip-model/invocations
```

**What CLIP Does**:
- **Input**: Text query OR image bytes
- **Output**: 768-dimensional embedding vector
- **Model**: Pre-trained CLIP (Contrastive Language-Image Pre-training)

**CLIP is multimodal** - it understands both text AND images in the same vector space:
```
Text: "red summer dress"     → [0.23, -0.41, 0.88, ..., 0.15]  (768 dims)
Image: [photo of red dress]  → [0.21, -0.43, 0.90, ..., 0.13]  (768 dims)
                                      ↑ Very similar vectors!
```

### Unified Search Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Input                                │
├─────────────────────────────────────────────────────────────┤
│   "red dress"       │    [image upload]   │   User Profile  │
│   (text query)      │    (image bytes)    │   (preferences) │
└─────────┬───────────┴──────────┬──────────┴────────┬────────┘
          │                      │                    │
          ▼                      ▼                    ▼
    ┌─────────────┐        ┌─────────────┐     ┌──────────────┐
    │ CLIP Model  │        │ CLIP Model  │     │ User Feature │
    │ (Text Mode) │        │ (Image Mode)│     │  Embedding   │
    └──────┬──────┘        └──────┬──────┘     └──────┬───────┘
           │                      │                    │
           └──────────┬───────────┴────────────────────┘
                      ▼
              [768-dim vector]
                      │
                      ▼
         ┌────────────────────────────┐
         │  Vector Similarity Search  │
         │                            │
         │  Compare with Product      │
         │  Embeddings in Database    │
         │  (Cosine Similarity)       │
         └────────────┬───────────────┘
                      ▼
              Ranked Products
              (sorted by similarity)
```

### Shared Components

**1. Product Embeddings Table**
```sql
-- ecom.fashion_demo.product_image_embeddingsdb
CREATE TABLE product_image_embeddingsdb (
    product_id VARCHAR,
    image_embedding JSONB,           -- 768 floats
    embedding_model VARCHAR,         -- "clip-ViT-B/32"
    embedding_dimension INT,         -- 768
    created_at TIMESTAMP
);
```

**2. Vector Similarity Function**
```python
def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    return dot_product / (norm1 * norm2)
```

**3. Unified Search Service** (would be created):
```python
class VectorSearchService:
    def __init__(self, clip_endpoint: str):
        self.clip_endpoint = clip_endpoint

    async def search_by_text(self, query: str, limit: int = 20):
        # 1. Generate text embedding via CLIP
        query_embedding = await self._get_text_embedding(query)

        # 2. Compare with all product embeddings
        products = await self._vector_similarity_search(query_embedding, limit)

        return products

    async def search_by_image(self, image_bytes: bytes, limit: int = 20):
        # 1. Generate image embedding via CLIP
        query_embedding = await self._get_image_embedding(image_bytes)

        # 2. Compare with all product embeddings (same function!)
        products = await self._vector_similarity_search(query_embedding, limit)

        return products

    async def get_recommendations(self, user_id: str, limit: int = 20):
        # 1. Get user's embedding (from user_style_featuresdb)
        user_embedding = await self._get_user_embedding(user_id)

        # 2. Compare with all product embeddings (same function!)
        products = await self._vector_similarity_search(user_embedding, limit)

        # 3. Add rule-based filters (price range, color preferences)
        products = self._apply_user_filters(products, user_id)

        return products

    async def _vector_similarity_search(self, query_embedding: List[float], limit: int):
        """Shared vector search - used by text, image, AND recommendations"""
        # Get all product embeddings from database
        product_embeddings = await repo.get_product_embeddings()

        # Calculate similarity scores
        scored_products = []
        for product in product_embeddings:
            similarity = cosine_similarity(query_embedding, product.embedding)
            scored_products.append((product, similarity))

        # Sort by similarity and return top N
        scored_products.sort(key=lambda x: x[1], reverse=True)
        return scored_products[:limit]
```

---

## Implementation Plan

### Phase 1: Text Search with CLIP ✅ Ready
1. Configure `CLIP_ENDPOINT` in environment
2. Create service to call CLIP model serving endpoint
3. Update `/search/text` to use CLIP embeddings
4. Compare query embedding with product embeddings
5. Return products ranked by cosine similarity

**Code Location**: [routes/v1/search.py:15-46](routes/v1/search.py#L15-L46)

### Phase 2: Image Search with CLIP 🚧 Needs Implementation
1. Use same CLIP endpoint (image mode)
2. Upload image → Generate embedding
3. Compare with product embeddings (same logic as text!)
4. Return products ranked by similarity

**Code Location**: [routes/v1/search.py:49-84](routes/v1/search.py#L49-L84)

### Phase 3: Hybrid Recommendations 🎯 Enhance Current
1. Keep current rule-based filtering (price, color)
2. Add vector similarity using user embeddings
3. Combine scores: `0.6 * vector_similarity + 0.4 * rule_score`
4. Provide better explanations: "Similar to items you liked before"

**Code Location**: [routes/v1/search.py:87-170](routes/v1/search.py#L87-L170)

---

## Database Schema

### Product Embeddings
```sql
-- Already exists in ecom.fashion_demo
SELECT
    product_id,
    image_embedding,        -- JSONB array of 768 floats
    embedding_model,        -- "clip-ViT-B/32"
    embedding_dimension,    -- 768
    created_at
FROM ecom.fashion_demo.product_image_embeddingsdb
LIMIT 5;
```

### User Style Features
```sql
-- Already exists in ecom.fashion_demo
SELECT
    user_id,
    user_embedding,         -- JSONB array of floats (user's style vector)
    segment,                -- "Luxury Fashionista", etc.
    category_prefs,         -- Array of preferred categories
    color_prefs,            -- Array of preferred colors
    min_price,
    max_price,
    avg_price
FROM ecom.fashion_demo.user_style_featuresdb
LIMIT 5;
```

---

## Key Insights

### Why CLIP is Perfect for This Use Case

1. **Multimodal**: Same model handles text AND images
2. **Pretrained**: Already understands fashion items ("dress", "sneakers", etc.)
3. **Semantic**: Understands "red summer dress" ≈ "scarlet sundress"
4. **Fast**: Single endpoint for all embedding generation

### Shared Infrastructure Benefits

1. **One Model**: Text search, image search, and recommendations all use same CLIP model
2. **One Function**: `vector_similarity_search()` works for all three features
3. **One Database**: All embeddings stored in same table structure
4. **Consistent UX**: Same similarity scores across features

### Current vs. Intended

| Feature | Current | Intended |
|---------|---------|----------|
| **Text Search** | PostgreSQL ILIKE (keyword match) | CLIP embeddings + vector similarity |
| **Image Search** | Random products (placeholder) | CLIP embeddings + vector similarity |
| **Recommendations** | Rule-based (price + color) | Hybrid: rules + user embedding similarity |
| **Model Serving** | Not connected | CLIP endpoint for all embeddings |
| **Similarity Metric** | N/A | Cosine similarity (shared) |

---

## Example Request Flow

### Scenario: User searches "red summer dress"

**Current (Basic Text Search)**:
```
User → "red summer dress"
  ↓
PostgreSQL ILIKE search
  ↓
Returns: Products with "red" OR "summer" OR "dress" in name
  ↓
Limited results, no semantic understanding
```

**Intended (CLIP-Based Search)**:
```
User → "red summer dress"
  ↓
POST to CLIP endpoint: {"input": "red summer dress", "mode": "text"}
  ↓
CLIP returns: [0.23, -0.41, 0.88, ..., 0.15]  (768 dims)
  ↓
Compare with ALL product embeddings in database
  ↓
Calculate cosine similarity for each product
  ↓
Sort by similarity:
  1. Red Sundress (0.92)
  2. Scarlet Summer Gown (0.89)
  3. Coral Maxi Dress (0.85)
  ...
  ↓
Return top 20 products
```

Notice: "Scarlet Gown" matches even though it doesn't contain "red" or "dress" - semantic understanding!

---

## Configuration

### Required Environment Variables

```bash
# CLIP Model Serving Endpoint
CLIP_ENDPOINT=https://your-workspace.cloud.databricks.com/serving-endpoints/clip-model/invocations

# Databricks authentication (for calling model serving)
DATABRICKS_HOST=your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
```

### Model Serving Payload Format

**Text Mode**:
```json
{
  "inputs": ["red summer dress"],
  "mode": "text"
}
```

**Image Mode**:
```json
{
  "inputs": ["<base64-encoded-image>"],
  "mode": "image"
}
```

**Response**:
```json
{
  "predictions": [
    [0.23, -0.41, 0.88, ..., 0.15]  // 768 floats
  ]
}
```

---

## Performance Considerations

### Vector Search Optimization

**Current Approach** (Basic):
```python
# Load ALL embeddings into memory, calculate similarity
# O(N) where N = total products (~44,000)
```

**Better Approach** (For Scale):
1. **pgvector Extension**: PostgreSQL extension for vector similarity
2. **Vector Index**: HNSW or IVFFlat index for fast approximate search
3. **Filtering**: Apply filters (price, category) BEFORE vector search

**With pgvector**:
```sql
-- Install pgvector extension
CREATE EXTENSION vector;

-- Add vector column
ALTER TABLE product_image_embeddingsdb
ADD COLUMN embedding vector(768);

-- Create HNSW index for fast similarity search
CREATE INDEX ON product_image_embeddingsdb
USING hnsw (embedding vector_cosine_ops);

-- Fast similarity query
SELECT product_id, 1 - (embedding <=> '[0.23,-0.41,...]') AS similarity
FROM product_image_embeddingsdb
WHERE price BETWEEN 50 AND 150
ORDER BY embedding <=> '[0.23,-0.41,...]'
LIMIT 20;
```

This reduces search time from **seconds** to **milliseconds** for large datasets.

---

## Summary

**Answer to your question**:
> "Is that a shared service with search where we're just feeding in embeddings and/or search terms and getting back an inference?"

**Yes, exactly!**

The intended architecture uses a **shared CLIP model serving endpoint** for all three features:

1. **Text Search**: Query text → CLIP → embedding → similarity search → products
2. **Image Search**: Uploaded image → CLIP → embedding → similarity search → products
3. **Recommendations**: User profile → user embedding → similarity search → products

All three use the **same vector similarity function** to compare embeddings. The only difference is **what you're comparing**:
- Text search: Query embedding vs. Product embeddings
- Image search: Image embedding vs. Product embeddings
- Recommendations: User embedding vs. Product embeddings

**Current Status**:
- ✅ Recommendations: Rule-based (working)
- ⚠️ Text Search: Basic keyword matching (no CLIP yet)
- ❌ Image Search: Placeholder (not implemented)

**To enable full CLIP integration**, you need to:
1. Deploy CLIP model to Model Serving endpoint
2. Set `CLIP_ENDPOINT` environment variable
3. Implement service to call CLIP endpoint
4. Update search routes to use embeddings

**Data is ready**: Product embeddings already exist in `ecom.fashion_demo.product_image_embeddingsdb` (44,424 products with 768-dim CLIP embeddings)!
