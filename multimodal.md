Multimodal CLIP Implementation Summary
🎯 Goal
Implement comprehensive multimodal search using CLIP's shared text-image embedding space for:

Semantic text search ("vintage leather jacket" finds matching images)
Visual image search (upload photo, find similar products)
Hybrid search (text + image combined)
Cross-modal search (text query searches image embeddings)
Latent feature extraction and analysis
📊 Current State
Existing Assets
Tables:

main.fashion_demo.products (44,424 products)

Columns: product_id, product_display_name, master_category, sub_category, article_type, base_color, price, image_path, gender, season, year, usage
main.fashion_demo.product_image_embeddings (44,424 rows)

Columns: product_id, image_embedding (512 dims), embedding_model, embedding_dimension, created_at
Model: clip-vit-b-32 (IMAGE ONLY)
main.fashion_demo.product_embeddings_enriched (44,424 rows) ✅ CREATED

All product metadata + image_embedding
Ready for Vector Search index
main.fashion_demo.user_style_features (5 users)

Columns: user_id, segment, user_embedding (512 dims), color_prefs, category_prefs, price ranges
Model Serving Endpoints:

clip-image-encoder - IMAGE ONLY (currently deployed)
Model: main.fashion_demo.clip_image_encoder v1
Input: base64 image
Output: 512-dim embedding
Status: READY
Vector Search:

Endpoint: fashion_vector_search (ID: 4d329fc8-1924-4131-ace8-14b542f8c14b)
Current Index: main.fashion_demo.product_embeddings_index
❌ Problem: Built on product_image_embeddings (only has product_id + embedding)
❌ Missing: All product metadata columns
❌ Error: "Requested columns not present in index"
🚨 Critical Issues Found
Issue 1: Vector Search Index Missing Columns
Error:

Requested columns to fetch are not present in index: 
sub_category, product_display_name, usage, price, year, 
season, image_path, base_color, article_type, master_category, gender
Root Cause: Index built on product_image_embeddings which only has:

product_id
image_embedding
embedding_model, embedding_dimension, created_at
Solution: Rebuild index on product_embeddings_enriched table

Issue 2: Invalid Filter Syntax
Error:

Invalid operator used in filter: price <= 
Root Cause: Wrong filter format {"price >= ": 50, "price <= ": 100}

Solution: Use correct Vector Search filter syntax

Issue 3: Text Embeddings Don't Exist
Current: Only image embeddings (from product photos) Needed: Text embeddings (from product descriptions) for semantic text search

🏗️ Target Architecture
New Table: main.fashion_demo.product_embeddings_multimodal
Schema:

CREATE TABLE main.fashion_demo.product_embeddings_multimodal (
  -- Product metadata (from products table)
  product_id INT,
  product_display_name STRING,
  master_category STRING,
  sub_category STRING,
  article_type STRING,
  base_color STRING,
  price DOUBLE,
  image_path STRING,
  gender STRING,
  season STRING,
  year INT,
  usage STRING,
  
  -- Embeddings (all 512 dims, same CLIP space)
  image_embedding ARRAY<DOUBLE>,      -- From CLIP image encoder
  text_embedding ARRAY<DOUBLE>,       -- From CLIP text encoder (NEW!)
  hybrid_embedding ARRAY<DOUBLE>,     -- 0.5*text + 0.5*image (NEW!)
  
  -- Metadata
  embedding_model STRING,             -- "clip-vit-b-32"
  embedding_dimension INT,            -- 512
  updated_at TIMESTAMP
);
Row Count: 44,424 products

New Model Endpoint: clip-multimodal-encoder
Capabilities:

✅ Text encoding: {"text": "red dress"} → 512-dim embedding
✅ Image encoding: {"image": "base64..."} → 512-dim embedding
✅ Same embedding space (text and image embeddings are comparable!)
Deployment:

class CLIPMultimodalEncoder(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        from transformers import CLIPProcessor, CLIPModel
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    
    def predict(self, context, model_input):
        if "text" in model_input:
            features = self.model.get_text_features(...)
        elif "image" in model_input:
            features = self.model.get_image_features(...)
        return normalized_features
New Vector Search Indexes (3 total)
All on same source table: main.fashion_demo.product_embeddings_multimodal

Index 1: Image Search

Name: main.fashion_demo.vs_image_search
Embedding Column: image_embedding
Use Case: Visual similarity search
Index 2: Text Search

Name: main.fashion_demo.vs_text_search
Embedding Column: text_embedding
Use Case: Semantic text search
Index 3: Hybrid Search

Name: main.fashion_demo.vs_hybrid_search
Embedding Column: hybrid_embedding
Use Case: Combined text + image queries
All indexes return: All product metadata columns (no joins needed!)

🔧 App Changes Required
File 1: services/clip_service.py
Current: CLIPService (image only) New: CLIPMultimodalService (text + image + hybrid)

Key Changes:

class CLIPMultimodalService:
    def __init__(self):
        self.endpoint_name = "clip-multimodal-encoder"  # NEW endpoint
        self.embedding_dim = 512
    
    async def get_text_embedding(self, text: str) -> np.ndarray:
        """NEW: Generate text embedding"""
        payload = {"dataframe_records": [{"text": text}]}
        # Call endpoint, parse response, normalize
        return embedding  # 512 dims
    
    async def get_image_embedding(self, image_bytes: bytes) -> np.ndarray:
        """EXISTING: Generate image embedding"""
        # Same as before
        return embedding  # 512 dims
    
    async def get_hybrid_embedding(self, text: str, image_bytes: bytes, 
                                   text_weight: float = 0.5) -> np.ndarray:
        """NEW: Generate hybrid embedding"""
        text_emb = await self.get_text_embedding(text)
        image_emb = await self.get_image_embedding(image_bytes)
        hybrid = text_weight * text_emb + (1 - text_weight) * image_emb
        return hybrid / np.linalg.norm(hybrid)  # Normalize!
File 2: services/vector_search_service.py
Key Changes:

class VectorSearchService:
    def __init__(self):
        # No single index name - pass index_name to similarity_search()
        self.endpoint_name = "fashion_vector_search"
        self.embedding_dim = 512
    
    async def similarity_search(
        self,
        query_vector: np.ndarray,
        num_results: int = 20,
        index_name: str = "main.fashion_demo.vs_hybrid_search",  # NEW param
        filters: Optional[Dict] = None
    ):
        # Get index dynamically
        index = self._client.get_index(index_name=index_name)  # Use keyword arg!
        
        # Request ALL product columns (now available!)
        columns = [
            "product_id", "product_display_name", "master_category",
            "sub_category", "article_type", "base_color", "price",
            "image_path", "gender", "season", "usage", "year"
        ]
        
        results = index.similarity_search(
            query_vector=query_vector.tolist(),
            columns=columns,
            num_results=num_results,
            filters=filters  # Now supported!
        )
        
        return products  # Complete product data!
File 3: routes/v1/search.py
New Endpoints:

@router.post("/text")
async def search_by_text_semantic(request: SearchRequest):
    """Semantic text search using CLIP text embeddings"""
    # Generate text embedding
    text_embedding = await clip_service.get_text_embedding(request.query)
    
    # Search in IMAGE index (cross-modal!)
    products = await vector_search_service.similarity_search(
        query_vector=text_embedding,
        index_name="main.fashion_demo.vs_image_search",  # Text → Image!
        num_results=request.limit
    )
    return SearchResponse(products=products, search_type="semantic_text")

@router.post("/image")
async def search_by_image(image: UploadFile, limit: int = 20):
    """Visual image search"""
    image_bytes = await image.read()
    image_embedding = await clip_service.get_image_embedding(image_bytes)
    
    products = await vector_search_service.similarity_search(
        query_vector=image_embedding,
        index_name="main.fashion_demo.vs_image_search",
        num_results=limit
    )
    return SearchResponse(products=products, search_type="image")

@router.post("/hybrid")
async def search_hybrid(query: str, image: Optional[UploadFile] = None, 
                       text_weight: float = 0.5):
    """Hybrid search combining text + image"""
    if image:
        image_bytes = await image.read()
        hybrid_emb = await clip_service.get_hybrid_embedding(
            query, image_bytes, text_weight
        )
    else:
        hybrid_emb = await clip_service.get_text_embedding(query)
    
    products = await vector_search_service.similarity_search(
        query_vector=hybrid_emb,
        index_name="main.fashion_demo.vs_hybrid_search",
        num_results=20
    )
    return SearchResponse(products=products, search_type="hybrid")

@router.get("/recommendations/{user_id}")
async def get_recommendations(user_id: str, limit: int = 20):
    """Personalized recommendations using user embeddings"""
    # Get user embedding from user_style_features
    user_features = await repo.get_user_style_features(user_id)
    user_embedding = np.array(user_features["user_embedding"])
    
    # Search in HYBRID index (best of both worlds!)
    products = await vector_search_service.similarity_search(
        query_vector=user_embedding,
        index_name="main.fashion_demo.vs_hybrid_search",
        num_results=limit
    )
    return SearchResponse(products=products, search_type="personalized")
File 4: data/personas.json
Updated with real user IDs:

{
  "personas": [
    {"user_id": "user_006327", "name": "Budget-Conscious Shopper", ...},
    {"user_id": "user_007598", "name": "Athletic Performance", ...},
    {"user_id": "user_008828", "name": "Luxury Fashionista", ...},
    {"user_id": "user_001328", "name": "Casual Accessories Lover", ...},
    {"user_id": "user_009809", "name": "Vintage Style Enthusiast", ...}
  ]
}
📋 Implementation Steps
Phase 1: Deploy CLIP Multimodal Encoder (2-3 hours)
Step 1: Create MLflow model wrapper

class CLIPMultimodalEncoder(mlflow.pyfunc.PythonModel):
    # Handles both text and image inputs
    # Returns 512-dim embeddings in shared space
Step 2: Register model to Unity Catalog

mlflow.pyfunc.log_model(
    artifact_path="clip_model",
    python_model=CLIPMultimodalEncoder(),
    registered_model_name="main.fashion_demo.clip_multimodal_encoder"
)
Step 3: Create Model Serving endpoint

Name: clip-multimodal-encoder
Model: main.fashion_demo.clip_multimodal_encoder v1
Workload: Small
Scale to zero: Enabled
Phase 2: Generate Text Embeddings (1-2 hours)
Step 4: Create rich text descriptions

CREATE TEMP VIEW product_text_descriptions AS
SELECT 
  product_id,
  CONCAT_WS(' ',
    product_display_name,
    article_type,
    base_color,
    master_category,
    gender,
    season,
    CASE WHEN price < 30 THEN 'affordable'
         WHEN price < 70 THEN 'mid-range'
         WHEN price < 120 THEN 'premium'
         ELSE 'luxury' END
  ) as text_content
FROM main.fashion_demo.products;
Step 5: Generate text embeddings using pandas UDF

@pandas_udf(ArrayType(DoubleType()))
def generate_text_embedding_udf(texts: pd.Series) -> pd.Series:
    # Call clip-multimodal-encoder with text input
    # Returns 512-dim embeddings
Step 6: Create multimodal table

CREATE TABLE main.fashion_demo.product_embeddings_multimodal AS
SELECT 
  p.*,
  img.image_embedding,
  txt.text_embedding,
  NULL as hybrid_embedding  -- Computed next
FROM main.fashion_demo.products p
JOIN main.fashion_demo.product_image_embeddings img ON p.product_id = img.product_id
JOIN text_embeddings txt ON p.product_id = txt.product_id;
Phase 3: Create Hybrid Embeddings (30 mins)
Step 7: Compute hybrid embeddings

@udf(ArrayType(DoubleType()))
def create_hybrid_embedding(image_emb, text_emb):
    img_arr = np.array(image_emb)
    txt_arr = np.array(text_emb)
    hybrid = 0.5 * img_arr + 0.5 * txt_arr
    return (hybrid / np.linalg.norm(hybrid)).tolist()

spark.sql("""
    UPDATE main.fashion_demo.product_embeddings_multimodal
    SET hybrid_embedding = create_hybrid_embedding(image_embedding, text_embedding)
""")
Phase 4: Create Vector Search Indexes (30 mins)
Step 8: Create 3 indexes via Databricks UI

Go to: Compute → Vector Search → fashion_vector_search → Create Index

Index 1:

Name: main.fashion_demo.vs_image_search
Source: main.fashion_demo.product_embeddings_multimodal
Primary Key: product_id
Embedding Column: image_embedding
Dimension: 512
Index 2:

Name: main.fashion_demo.vs_text_search
Source: main.fashion_demo.product_embeddings_multimodal
Primary Key: product_id
Embedding Column: text_embedding
Dimension: 512
Index 3:

Name: main.fashion_demo.vs_hybrid_search
Source: main.fashion_demo.product_embeddings_multimodal
Primary Key: product_id
Embedding Column: hybrid_embedding
Dimension: 512
Wait: 5-10 minutes for all indexes to sync

Phase 5: Update App Code (1 hour)
Step 9: Update services/clip_service.py

Replace CLIPService with CLIPMultimodalService
Add get_text_embedding() method
Add get_hybrid_embedding() method
Update endpoint_name to "clip-multimodal-encoder"
Step 10: Update services/vector_search_service.py

Add index_name parameter to similarity_search()
Fix: Use client.get_index(index_name=...) (keyword arg!)
Keep full columns list (all product fields now available)
Remove hardcoded index name from init
Step 11: Update routes/v1/search.py

Update text search to use CLIP text embeddings
Update image search to use vs_image_search index
Add hybrid search endpoint
Update recommendations to use vs_hybrid_search index
Pass index_name to vector_search_service.similarity_search()
Step 12: Update data/personas.json

Use real user IDs: user_006327, user_007598, user_008828, user_001328, user_009809
These users have embeddings in user_style_features table
Step 13: Rebuild frontend

cd frontend
npm run build
Step 14: Redeploy app

🎯 Expected Capabilities After Implementation
1. Semantic Text Search
Query: "vintage leather jacket" Process: Text → CLIP text encoder → 512-dim embedding → Search image index Result: Products that LOOK like vintage leather jackets (cross-modal!)

2. Visual Image Search
Query: Upload photo of dress Process: Image → CLIP image encoder → 512-dim embedding → Search image index Result: Visually similar dresses

3. Hybrid Search
Query: "red dress" + inspiration photo Process: Text + Image → Hybrid embedding (0.5 + 0.5) → Search hybrid index Result: Red dresses that look like the photo

4. Personalized Recommendations
Query: user_008828 (Luxury Fashionista) Process: User embedding (512 dims) → Search hybrid index Result: Products matching user's visual + semantic style

5. Cross-Modal Understanding
Query: Compare image with text descriptions Process: cosine_similarity(image_emb, text_emb("formal wear")) Result: "This is formal wear" (zero-shot classification)

🐛 Bug Fixes Included
Fix 1: Vector Search Index Columns
Before: Index only had product_id After: Index has all product metadata Impact: No joins needed, filters work

Fix 2: get_index() Method Call
Before: client.get_index(self.index_name) (positional arg) After: client.get_index(index_name=self.index_name) (keyword arg) Impact: Fixes "Index name must be specified" error

Fix 3: OAuth Authentication
Before: VectorSearchClient() with no auth After: VectorSearchClient(personal_access_token=token) Impact: Fixes "Please specify token" error

Fix 4: CLIP Response Parsing
Before: Expected nested array After: Handles flat array {"predictions": [0.012, 0.013, ...]} Impact: Fixes embedding extraction

Fix 5: User IDs
Before: Fake users (user_001 through user_005) After: Real users with embeddings (user_006327, etc.) Impact: Recommendations actually work

📦 Deliverables
Data Assets
✅ main.fashion_demo.product_embeddings_enriched (44K products, image embeddings + metadata)
⏳ main.fashion_demo.product_embeddings_multimodal (44K products, text + image + hybrid)
⏳ Vector Search indexes: vs_image_search, vs_text_search, vs_hybrid_search
Code Assets
✅ services/clip_service.py (multimodal version in notebook)
✅ services/vector_search_service.py (fixed version in notebook)
✅ routes/v1/search.py (multimodal version in notebook)
✅ data/personas.json (real user IDs in notebook)
Model Assets
✅ main.fashion_demo.clip_image_encoder v1 (deployed)
⏳ main.fashion_demo.clip_multimodal_encoder (to be deployed)
🚀 Quick Start for New Thread
Context: "We're implementing multimodal CLIP search for fashion e-commerce. We have image embeddings for 44K products. Need to add text embeddings and rebuild Vector Search indexes. See MULTIMODAL_CLIP_IMPLEMENTATION_SUMMARY for full details."

Next Steps:

Deploy clip-multimodal-encoder endpoint
Generate text embeddings for all products
Create hybrid embeddings
Create 3 Vector Search indexes
Update app code (4 files)
Test and deploy
Estimated Time: 4-6 hours total Estimated Cost: ~$10-15 for embeddings + compute

📞 Key Contacts & Resources
Notebooks:

03_image_embeddings_pipeline - How image embeddings were created
04_vector_search_setup - Current Vector Search setup
This notebook - Multimodal implementation plan
Tables:

Products: main.fashion_demo.products
Image embeddings: main.fashion_demo.product_image_embeddings
Enriched: main.fashion_demo.product_embeddings_enriched
Target: main.fashion_demo.product_embeddings_multimodal
Endpoints:

Vector Search: fashion_vector_search (4d329fc8-1924-4131-ace8-14b542f8c14b)
Current CLIP: clip-image-encoder (image only)
Target CLIP: clip-multimodal-encoder (text + image)
App Repo: /Users/kevin.ippen@databricks.com/fashion-ecom-site/

✅ Success Criteria
Text search "red dress" returns relevant products (no keywords needed)
Image upload finds visually similar products
Hybrid search combines text + image
Each persona gets different recommendations
No "columns not present" errors
No "index name must be specified" errors
Cross-modal search works (text finds images)
Latent features can be analyzed
When all checked: Ship it! 🚀


--------

Update to be blended into this doc

%md
## 🚀 Multimodal CLIP Pipeline - Current Status

### ✅ Completed Steps

1. **Setup & Configuration**
   - ✅ Switched to classic cluster (authentication works natively)
   - ✅ Installed packages: mlflow, transformers, torch, pillow, databricks-vectorsearch
   - ✅ Configured for Large endpoint (64 concurrency, 500 batch size, 64 partitions)

2. **Model Development**
   - ✅ Defined `CLIPMultimodalEncoder` class (handles text OR image inputs)
   - ✅ Registered model version 7 with **text-only signature**
   - ✅ Model accepts: `{"text": "query string"}`

3. **Text Description Creation**
   - ✅ Created rich text descriptions for 44,417 products
   - ✅ Combines 8 attributes: name, type, color, category, gender, season, price tier, usage
   - ✅ Average 15.2 words per description
   - ✅ 74.9% unique descriptions

4. **Latent Feature Assessment**
   - ✅ Analyzed attribute diversity: 143 article types, 46 colors, 45 subcategories
   - ✅ Confirmed sufficient richness for premium retail experience
   - ✅ CLIP's zero-shot understanding fills semantic gaps

5. **Embedding Generation Function**
   - ✅ Defined optimized pandas UDF with:
     - Native `WorkspaceClient()` authentication (classic cluster)
     - Batch size: 500 texts per request
     - Concurrent requests: 4 per partition
     - 64 partitions for max parallelism

### ⏳ In Progress

6. **Model Serving Endpoint Update**
   - 🔄 Updating `clip-multimodal-encoder` endpoint to version 7
   - Current: Version 5 (requires text + image)
   - Target: Version 7 (text-only signature)
   - Status: **IN_PROGRESS** (5-10 minutes)
   - Once ready: Will accept `{"dataframe_records": [{"text": "..."}, ...]}`

### 📋 Next Steps (After Endpoint Ready)

7. **Generate Text Embeddings** (~5-10 minutes)
   ```python
   # Run cell 20 to:
   # - Generate 44,417 text embeddings using CLIP
   # - Process in parallel (64 partitions × 4 concurrent requests)
   # - Save to: main.fashion_demo.product_embeddings_multimodal_text_temp
   ```

8. **Create Multimodal Table** (~2 minutes)
   ```sql
   CREATE TABLE main.fashion_demo.product_embeddings_multimodal AS
   SELECT 
     p.*,                    -- All product metadata
     img.image_embedding,    -- From existing table
     txt.text_embedding,     -- From step 7
     NULL as hybrid_embedding -- Computed in step 9
   FROM products p
   JOIN product_image_embeddings img ON p.product_id = img.product_id
   JOIN text_embeddings txt ON p.product_id = txt.product_id
   ```

9. **Generate Hybrid Embeddings** (~1 minute)
   ```python
   # Compute: hybrid = normalize(0.5 * image_emb + 0.5 * text_emb)
   # Update multimodal table with hybrid embeddings
   ```

10. **Create Vector Search Indexes** (~10 minutes)
    - `main.fashion_demo.vs_image_search` (image_embedding column)
    - `main.fashion_demo.vs_text_search` (text_embedding column)
    - `main.fashion_demo.vs_hybrid_search` (hybrid_embedding column)

11. **Test & Validate** (~5 minutes)
    - Test semantic text search
    - Test visual image search
    - Test hybrid search
    - Test personalized recommendations

### ⏱️ Estimated Time Remaining

- **Endpoint update**: 5-10 minutes (in progress)
- **Embedding generation**: 5-10 minutes
- **Table creation**: 3 minutes
- **Index creation**: 10 minutes
- **Testing**: 5 minutes

**Total**: ~25-35 minutes

### 🎯 Success Criteria

- ✅ Text descriptions created (44,417 products)
- ⏳ Text embeddings generated (512 dims each)
- ⏳ Hybrid embeddings computed
- ⏳ 3 Vector Search indexes created
- ⏳ Cross-modal search working (text finds images)
- ⏳ All 44,424 products searchable

### 💡 Key Optimizations Applied

1. **Classic Cluster**: Native authentication, no workarounds
2. **Large Endpoint**: 64 concurrency for max throughput
3. **Batch Size 500**: 5x larger than default (100)
4. **64 Partitions**: Matches endpoint concurrency
5. **Concurrent Requests**: 4 per partition (256 total potential)
6. **Result**: 6-10x faster than sequential approach (5-10 min vs 30-60 min)

---

**🔔 Action Required**: Wait for endpoint update to complete, then run cell 20 to generate embeddings!