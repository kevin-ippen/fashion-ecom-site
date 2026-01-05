# Fashion E-Commerce Site - Lessons Learned

> Key patterns, gotchas, and best practices discovered during development

## Table of Contents
1. [Databricks Apps Authentication](#databricks-apps-authentication)
2. [Vector Search Integration](#vector-search-integration)
3. [CLIP Model Serving](#clip-model-serving)
4. [Lakebase PostgreSQL](#lakebase-postgresql)
5. [Search Quality Challenges](#search-quality-challenges)
6. [Performance Optimization](#performance-optimization)
7. [Development Workflow](#development-workflow)

---

## Databricks Apps Authentication

### ✅ The Correct Way: Resource-Based Secrets

**Problem**: Environment variable substitution like `${secrets.scope.key}` does NOT work in Databricks Apps.

**Solution**: Use App Resources declared in the UI

```yaml
# app.yaml
env:
  - name: LAKEBASE_PASSWORD
    valueFrom: lakebase-token  # References resource key
```

**In Databricks Apps UI:**
1. Go to Resources tab
2. Add Secret resource
   - **Resource Key**: `lakebase-token` (must match `valueFrom`)
   - **Scope**: `your-scope`
   - **Key**: `your-key`
   - **Permission**: Can read
3. Deploy and restart

**Auto-Injected Variables:**
- `DATABRICKS_HOST`
- `DATABRICKS_CLIENT_ID`
- `DATABRICKS_CLIENT_SECRET`

**Use for OAuth M2M:**
```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()  # Automatically uses injected credentials
```

### Key Insight
> Always use service principal OAuth M2M for Databricks APIs in production. PAT tokens should only be for local development.

---

## Vector Search Integration

### Score Handling Gotcha

**Problem**: Vector Search appends similarity score as LAST element, not as a named column.

**Wrong:**
```python
results = index.similarity_search(...)
for row in results.get("result", {}).get("data_array", []):
    score = row["similarity_score"]  # ❌ Key doesn't exist
```

**Right:**
```python
results = index.similarity_search(
    columns=["product_id", "name", "price", ...]  # Specify columns
)
for row in results.get("result", {}).get("data_array", []):
    score = row[-1]  # ✅ Score is last element
    product_id = row[0]
    name = row[1]
```

### Filter Syntax

```python
# IN operator (list values)
filters = {
    "master_category": ["Apparel", "Footwear"],  # List = IN
}

# Range operators (nested dict)
filters = {
    "price": {"$gte": 50, "$lte": 200}
}

# Combined
filters = {
    "master_category": ["Apparel"],
    "price": {"$gte": 50, "$lte": 200},
    "base_color": ["Black", "Blue"]
}
```

### Delta Sync Best Practices

**Enable Change Data Feed:**
```sql
ALTER TABLE main.fashion_demo.product_embeddings_multimodal
SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
```

**Optimize for queries:**
```sql
OPTIMIZE main.fashion_demo.product_embeddings_multimodal
ZORDER BY (master_category, article_type);
```

**Auto-sync happens within minutes** - no manual refresh needed!

### Key Insight
> Use a single "multimodal" table with multiple embedding columns (image, text, hybrid) rather than separate tables. Easier maintenance and guaranteed consistency.

---

## CLIP Model Serving

### Response Format Handling

**SigLIP endpoint returns consistent format:**

```python
# siglip-multimodal-endpoint (unified)
{"predictions": [[0.01, 0.02, ...]]}  # Nested array for both text and image
```

**Solution**: Robust parsing with fallbacks

```python
def _parse_embedding(result, is_nested=True):
    if isinstance(result, dict) and "predictions" in result:
        predictions = result["predictions"]
        if is_nested and isinstance(predictions[0], list):
            embedding = np.array(predictions[0])
        elif isinstance(predictions[0], (int, float)):
            embedding = np.array(predictions)
        # ... more fallbacks

    # Always normalize for cosine similarity
    embedding = embedding / np.linalg.norm(embedding)
    return embedding
```

### Input Format

```python
# Text
payload = {"dataframe_records": [{"text": "query string"}]}

# Image (base64 encoded)
image_b64 = base64.b64encode(image_bytes).decode("utf-8")
payload = {"dataframe_records": [{"image": image_b64}]}
```

### Timeout Handling

**Critical**: Model Serving endpoints scale to zero → first request is slow

```python
timeout = aiohttp.ClientTimeout(total=120)  # 2 minutes for cold start
async with aiohttp.ClientSession(timeout=timeout) as session:
    async with session.post(url, json=payload, headers=headers) as response:
        # ...
```

### Key Insight
> Always L2-normalize CLIP embeddings before storing or querying. Vector Search uses L2 distance, which equals cosine similarity only when vectors are normalized.

---

## Lakebase PostgreSQL

### OAuth Token as Password

**Pattern**: Databricks OAuth token serves as PostgreSQL password

```python
def lakebase_sqlalchemy_url(self) -> str:
    # Get fresh OAuth token
    token = workspace_client.config.oauth_token().access_token

    # Use as PostgreSQL password
    return (
        f"postgresql+asyncpg://{user}:{token}@"
        f"{host}:{port}/{database}"
    )
```

### Auto-Injected Environment Variables

When Lakebase resource is attached to app:
- `PGHOST` - Lakebase host
- `PGPORT` - Port (5432)
- `PGDATABASE` - Database name (usually "main")
- `PGUSER` - Service principal ID

### Schema Naming

**Important**: Lakebase appends `db` suffix to table names

```python
# Unity Catalog
table_name = "main.fashion_demo.products"

# Lakebase PostgreSQL (synced)
postgres_schema = "fashion_demo"
postgres_table = "productsdb"  # Note the "db" suffix!

# Query
query = f"SELECT * FROM {postgres_schema}.{postgres_table}"
```

### Connection Pooling

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    settings.lakebase_sqlalchemy_url,
    echo=False,
    pool_pre_ping=True,  # Validate connections
    pool_size=10,
    max_overflow=20
)
```

### Key Insight
> Lakebase is NOT a full Unity Catalog mirror - only synced tables appear. Always check what's been synced using `\dt` in psql or query `information_schema.tables`.

---

## Search Quality Challenges

### Narrow Score Ranges

**Problem**: All results scored 52-55% (text) or 67-70% (image) → hard to differentiate

**Root Causes:**
1. **Generic text descriptions**: "Nike Tshirt Black Men Casual Summer"
   - Missing: material, style, fit, occasion
2. **Catalog homogeneity**: Similar products cluster tightly in embedding space
3. **No diversity penalty**: Top 20 results often very similar

**Solutions Implemented:**
- Visual attribute extraction (SmolVLM) to enrich descriptions
- Maximal Marginal Relevance (MMR) for diversity
- Re-ranking with business rules

### Text Description Enrichment

**Before:**
```
"Nike Men Tshirt Black Casual Summer 2018"
```

**After (with SmolVLM attributes):**
```
"Nike Men Tshirt Black Casual Summer 2018 knit fabric solid color
crew neck short sleeve athletic sporty has logo comfortable"
```

**Impact**: Wider score ranges, better semantic matching

### Personalization Over-Filtering

**Problem**: User preferences too restrictive

```json
{
  "preferred_categories": ["Accessories", "Apparel"],  // Too broad
  "color_prefs": ["Black", "Brown", "Purple", "Blue", "White"]  // 50%+ of catalog
}
```

**Solution**:
- Soft preferences (boost, don't filter)
- Negative preferences (what users DON'T want)
- Price ranges as guidelines, not hard limits

### Key Insight
> CLIP embeddings are great for visual similarity but need rich text descriptions for semantic search. Don't rely on concatenated attributes alone.

---

## Performance Optimization

### Async/Await Patterns

**Parallel Model Serving calls:**
```python
from asyncio import gather

# Generate multiple embeddings in parallel
text_emb, image_emb = await gather(
    clip_service.get_text_embedding(query),
    clip_service.get_image_embedding(image_bytes)
)
```

### React Query Caching

```typescript
// Cache search results for 5 minutes
const { data } = useQuery({
  queryKey: ['search', query, filters],
  queryFn: () => searchProducts(query, filters),
  staleTime: 5 * 60 * 1000,  // 5 minutes
  cacheTime: 10 * 60 * 1000  // 10 minutes
});
```

### Image Loading

```typescript
// Lazy load images with intersection observer
<img
  loading="lazy"
  src={imageUrl}
  alt={product.name}
/>
```

### Vector Search Optimization

```python
# Specify only needed columns (reduces response size)
results = index.similarity_search(
    query_vector=embedding,
    columns=[
        "product_id", "product_display_name", "price",
        "image_path", "master_category"
    ],  # Don't fetch embeddings!
    num_results=20
)
```

### Key Insight
> Vector Search is fast (200-500ms) but Model Serving can be slow (cold start 5-10s). Always implement proper loading states and timeouts.

---

## Development Workflow

### Local Development Setup

```bash
# 1. Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env with personal credentials
cat > .env << EOF
DATABRICKS_HOST=your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...
EOF

uvicorn app:app --reload --port 8000

# 2. Frontend (separate terminal)
cd frontend
npm install
npm run dev  # Runs on port 3000, proxies /api/* to backend
```

### Testing Vector Search Locally

```python
# Test notebook
from databricks.vector_search.client import VectorSearchClient

client = VectorSearchClient()
index = client.get_index("main.fashion_demo.vs_hybrid_search")

# Simple test
results = index.similarity_search(
    query_text="red dress",  # Can use text directly!
    num_results=5
)
print(results)
```

### Debugging Model Serving Endpoints

```bash
# Get OAuth token
databricks auth token

# Test endpoint
curl -X POST \
  https://workspace.databricks.com/serving-endpoints/siglip-multimodal-endpoint/invocations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dataframe_records": [{"text": "red dress"}]}'
```

### Deployment Checklist

- [ ] Frontend built: `cd frontend && npm run build`
- [ ] Requirements frozen: `pip freeze > requirements.txt`
- [ ] app.yaml updated with correct resources
- [ ] Environment variables reviewed
- [ ] Lakebase resource attached to app
- [ ] Secret resources configured in UI
- [ ] Deploy: `databricks apps deploy <app-name>`
- [ ] Test endpoints: `curl https://app-url/health`

### Key Insight
> Always test locally first. Debugging in Databricks Apps is harder - use extensive logging and check `/logz` endpoint.

---

## Common Pitfalls

### 1. Embedding Dimension Mismatch
```python
# ❌ Wrong: Using different CLIP models
text_emb = clip_vit_b32(text)  # 512-dim
image_emb = clip_vit_l14(image)  # 768-dim
similarity = cosine(text_emb, image_emb)  # ERROR!

# ✅ Right: Same model for all embeddings
text_emb = clip_vit_b32(text)  # 512-dim
image_emb = clip_vit_b32(image)  # 512-dim
```

### 2. Forgot to Normalize Embeddings
```python
# ❌ Wrong: Raw embeddings
embedding = model.encode(text)
store_in_database(embedding)

# ✅ Right: Normalize first
embedding = model.encode(text)
embedding = embedding / np.linalg.norm(embedding)
store_in_database(embedding)
```

### 3. Vector Search Filter Syntax Errors
```python
# ❌ Wrong: Using SQL syntax
filters = {"price": "< 100"}  # Doesn't work!

# ✅ Right: Use MongoDB-style operators
filters = {"price": {"$lt": 100}}
```

### 4. Not Handling Cold Starts
```python
# ❌ Wrong: Short timeout
timeout = aiohttp.ClientTimeout(total=5)  # Fails on cold start

# ✅ Right: Long timeout for first request
timeout = aiohttp.ClientTimeout(total=120)
```

---

## Best Practices Summary

### Data Engineering
- ✅ Use Delta Lake with Change Data Feed for Vector Search
- ✅ Optimize tables with Z-ORDER on frequently filtered columns
- ✅ Keep embeddings in single multimodal table
- ✅ Version your embeddings (include model name + date)

### Model Serving
- ✅ Always normalize embeddings (L2 norm)
- ✅ Use same CLIP model for all modalities
- ✅ Handle cold starts with long timeouts
- ✅ Implement retry logic with exponential backoff

### Vector Search
- ✅ Specify only needed columns in results
- ✅ Use hybrid embeddings for best quality
- ✅ Apply diversity to prevent repetitive results
- ✅ Test filters carefully (MongoDB syntax)

### Application Development
- ✅ Use async/await for parallel operations
- ✅ Implement proper error handling and logging
- ✅ Cache expensive operations (React Query, TTL caches)
- ✅ Use Pydantic for type safety and validation

### Databricks Apps
- ✅ Use App Resources for secrets (not env var substitution)
- ✅ Rely on OAuth M2M for service-to-service auth
- ✅ Test locally before deploying
- ✅ Monitor logs via `/logz` endpoint

---

## Future Improvements

### Technical
1. **Fine-tune CLIP on fashion domain** - Better semantic understanding
2. **Learning-to-Rank** - Learn optimal ranking from user behavior
3. **Collaborative filtering** - "Users who liked X also liked Y"
4. **A/B testing framework** - Measure impact of changes

### Business
1. **Real-time analytics** - Track search quality metrics
2. **User feedback loop** - Learn from likes/dislikes
3. **Dynamic re-ranking** - Adjust for inventory, margins
4. **Cross-sell recommendations** - Complete-the-look

---

## Resources

### Official Documentation
- [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps/)
- [Vector Search](https://docs.databricks.com/en/generative-ai/vector-search.html)
- [Model Serving](https://docs.databricks.com/en/machine-learning/model-serving/)
- [Unity Catalog](https://docs.databricks.com/en/data-governance/unity-catalog/)

### Research Papers
- [CLIP (Contrastive Language-Image Pre-training)](https://arxiv.org/abs/2103.00020)
- [Maximal Marginal Relevance](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf)

### Tools
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Query](https://tanstack.com/query/latest)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

---

**Last Updated**: 2025-12-31
**Contributors**: Development team
