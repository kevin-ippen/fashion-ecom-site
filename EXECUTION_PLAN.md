# Execution Plan: SmolVLM Attribute Extraction

## 📋 Complete Workflow

This document outlines the complete workflow from attribute extraction to updated search results.

---

## Phase 1: Extract Visual Attributes (YOU ARE HERE)

### Step 1: Create GPU Cluster in Databricks

1. Navigate to **Compute** → **Create Compute**
2. Configure cluster:
   ```yaml
   Name: smolvlm-extraction
   Mode: Single Node (for 100 product test)
   Runtime: 14.3 LTS ML (GPU)
   Node Type: g5.xlarge (NVIDIA A10G)
   Terminate after: 60 minutes idle
   ```
3. Click **Create Compute** (takes ~5 minutes to start)

### Step 2: Upload Notebook

1. Go to **Workspace** → Your user folder
2. **Import** → Upload `notebooks/smolvlm_batch_attribute_extraction.py`
3. Attach to `smolvlm-extraction` cluster

### Step 3: Run Extraction (100 Products Test)

1. Open the notebook
2. Verify configuration cell shows:
   ```python
   SAMPLE_SIZE = 100  # Test with 100 products
   ```
3. Click **Run All**
4. Wait ~15-20 minutes

**Output Tables Created**:
- `main.fashion_demo.product_extracted_attributes` - Raw extracted attributes
- `main.fashion_demo.products_enriched_descriptions` - With rich descriptions

### Step 4: Analyze Test Results

Review the quality reports in the notebook:

**Success Criteria**:
- ✅ Success rate > 85%
- ✅ Material "unknown" < 15%
- ✅ Confidence high+medium > 75%
- ✅ Consistency checks pass:
  - Watches → 90%+ metal
  - T-shirts → 85%+ knit fabric

**Decision Point**:
- **If good** → Proceed to Phase 2
- **If issues** → Refine prompts and re-run

---

## Phase 2: Join with Products Table

### Step 5: Create Final Enriched Table

1. Open SQL editor in Databricks
2. Run `notebooks/join_enriched_attributes.sql`
   - Creates `main.fashion_demo.products_with_visual_attributes`
   - Joins original products + extracted attributes
   - Generates rich text descriptions
   - Enables Change Data Feed for Vector Search

**Output**: `main.fashion_demo.products_with_visual_attributes` with columns:
```sql
-- Original product fields
product_id, product_display_name, master_category, article_type, ...

-- Extracted visual attributes
material, pattern, formality_level, style_keywords, visual_details,
collar_type, sleeve_length, fit_type,

-- Quality metadata
extraction_success, confidence_material, extraction_timestamp,

-- Descriptions for embedding
baseline_description,          -- Original (for A/B test baseline)
rich_text_description          -- Enriched (for new embeddings)
```

### Step 6: Validate Join Quality

Run validation queries from the SQL file:

```sql
-- Check enrichment coverage
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN material IS NOT NULL THEN 1 ELSE 0 END) as has_material,
  ROUND(100.0 * SUM(CASE WHEN material IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as coverage_pct
FROM main.fashion_demo.products_with_visual_attributes;
```

**Expected**: 80-90% coverage for material attribute

---

## Phase 3: Generate New CLIP Embeddings

### Step 7: Generate Text Embeddings from Rich Descriptions

**Option A: Update Existing Notebook**

Modify `multimodal_clip_implementation.py`:

```python
# Change text description source
text_descriptions = spark.sql(f"""
    SELECT
        product_id,
        -- Use RICH TEXT DESCRIPTION instead of basic concat
        rich_text_description as text_description
    FROM main.fashion_demo.products_with_visual_attributes
    WHERE extraction_success = true
      AND confidence_material IN ('high', 'medium')
""")

# Generate text embeddings using CLIP
text_embeddings = text_descriptions.withColumn(
    "text_embedding",
    generate_text_embeddings_udf(F.col("text_description"))
)

# Save to new table for A/B testing
text_embeddings.write.mode("overwrite").saveAsTable(
    "main.fashion_demo.product_embeddings_multimodal_enriched"
)
```

**Option B: Create New Embedding Notebook** (Recommended)

Create `notebooks/generate_enriched_embeddings.py`:

```python
# Load products with rich descriptions
products = spark.table("main.fashion_demo.products_with_visual_attributes")

# Filter to high-quality extractions only
products_filtered = products.filter(
    (F.col("extraction_success") == True) &
    (F.col("confidence_material").isin(["high", "medium"]))
)

# Generate CLIP text embeddings
products_with_embeddings = products_filtered.withColumn(
    "text_embedding_enriched",
    generate_clip_text_embedding_udf(F.col("rich_text_description"))
)

# Also generate baseline embeddings for comparison
products_with_embeddings = products_with_embeddings.withColumn(
    "text_embedding_baseline",
    generate_clip_text_embedding_udf(F.col("baseline_description"))
)

# Combine with existing image embeddings
final_embeddings = products_with_embeddings.join(
    spark.table("main.fashion_demo.product_image_embeddings"),
    on="product_id",
    how="inner"
)

# Create hybrid embeddings (50% image + 50% enriched text)
final_embeddings = final_embeddings.withColumn(
    "hybrid_embedding_enriched",
    create_hybrid_embedding_udf(
        F.col("image_embedding"),
        F.col("text_embedding_enriched"),
        F.lit(0.5)  # 50/50 weight
    )
)

# Save
final_embeddings.write.mode("overwrite").saveAsTable(
    "main.fashion_demo.product_embeddings_multimodal_v2"
)
```

---

## Phase 4: Update Vector Search Indexes

### Step 8: Create New Vector Search Indexes (A/B Test)

**Option A: Create Separate Indexes for A/B Testing**

```sql
-- Original indexes (baseline)
main.fashion_demo.vs_text_search
main.fashion_demo.vs_image_search
main.fashion_demo.vs_hybrid_search

-- New enriched indexes (treatment)
main.fashion_demo.vs_text_search_enriched
main.fashion_demo.vs_image_search_enriched  -- Same as baseline
main.fashion_demo.vs_hybrid_search_enriched
```

**Create via Python**:
```python
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Create enriched hybrid index
vsc.create_delta_sync_index(
    endpoint_name="fashion_vector_search",
    index_name="main.fashion_demo.vs_hybrid_search_enriched",
    source_table_name="main.fashion_demo.product_embeddings_multimodal_v2",
    pipeline_type="TRIGGERED",
    primary_key="product_id",
    embedding_dimension=512,
    embedding_vector_column="hybrid_embedding_enriched"
)

# Wait for sync to complete
vsc.get_index("main.fashion_demo.vs_hybrid_search_enriched").sync()
```

**Option B: Update Existing Indexes** (Simpler, no A/B test)

Just update the source table:
```python
# Vector Search Delta Sync will auto-update indexes
# when source table changes (if Change Data Feed enabled)

# Or manually trigger sync:
vsc.get_index("main.fashion_demo.vs_hybrid_search").sync()
```

---

## Phase 5: A/B Test Search Quality

### Step 9: Implement A/B Testing in API

Update `routes/v1/search.py`:

```python
def get_search_variant(user_id: str) -> str:
    """Route 50% users to enriched, 50% to baseline"""
    import hashlib
    hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    return "enriched" if (hash_value % 2) == 0 else "baseline"

@router.post("/text", response_model=SearchResponse)
async def search_by_text(request: SearchRequest):
    # Determine variant
    variant = get_search_variant(request.user_id or "anonymous")

    # Use appropriate index
    if variant == "enriched":
        index_name = "main.fashion_demo.vs_hybrid_search_enriched"
    else:
        index_name = "main.fashion_demo.vs_hybrid_search"

    # Search
    results = await vector_search_service.search(
        query_vector=text_embedding,
        index_name=index_name,
        num_results=request.limit
    )

    # Log for analysis
    log_search_event(
        user_id=request.user_id,
        query=request.query,
        variant=variant,
        results=results
    )

    return SearchResponse(products=results, ...)
```

### Step 10: Collect Metrics

Track these metrics for both variants:

```sql
CREATE TABLE main.fashion_demo.search_events (
  event_id STRING,
  timestamp TIMESTAMP,
  user_id STRING,
  query STRING,
  variant STRING,  -- "baseline" or "enriched"
  results_shown ARRAY<INT>,
  clicked_product_ids ARRAY<INT>,
  added_to_cart ARRAY<INT>,
  purchased ARRAY<INT>,
  time_to_first_click FLOAT
);
```

**Key Metrics**:
- **Click-through rate (CTR)**: % of searches with clicks
- **Precision**: % of clicks on relevant items
- **Score distribution**: Range of similarity scores
- **Conversion rate**: % of searches → purchase
- **Time to first click**: User engagement speed

### Step 11: Analyze A/B Test Results

After 1 week of data:

```sql
SELECT
  variant,
  COUNT(*) as searches,
  SUM(CASE WHEN SIZE(clicked_product_ids) > 0 THEN 1 ELSE 0 END) as searches_with_click,
  ROUND(100.0 * SUM(CASE WHEN SIZE(clicked_product_ids) > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as ctr_pct,
  SUM(CASE WHEN SIZE(purchased) > 0 THEN 1 ELSE 0 END) as conversions,
  ROUND(100.0 * SUM(CASE WHEN SIZE(purchased) > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as conversion_rate_pct,
  ROUND(AVG(time_to_first_click), 2) as avg_time_to_click_sec
FROM main.fashion_demo.search_events
GROUP BY variant;
```

**Expected Improvements**:
- CTR: +15-25%
- Conversion rate: +10-15%
- Time to first click: -10-20% (faster)

---

## Phase 6: Production Rollout

### Step 12: If A/B Test is Successful

1. **Update default indexes**:
   ```python
   # In core/config.py
   VS_HYBRID_INDEX: str = "main.fashion_demo.vs_hybrid_search_enriched"
   ```

2. **Remove A/B testing logic**:
   ```python
   # Just use enriched index for all users
   results = await vector_search_service.search_hybrid(...)
   ```

3. **Decommission baseline indexes** (optional):
   ```sql
   -- Keep for historical comparison
   -- Or drop to save storage
   DROP INDEX main.fashion_demo.vs_hybrid_search;
   ```

4. **Monitor production metrics**:
   - Ensure improvements hold
   - Watch for edge cases
   - Iterate on prompts if needed

---

## Timeline & Cost Summary

| Phase | Duration | Cost | Status |
|-------|----------|------|--------|
| **Phase 1: Extract Attributes (100 test)** | 20 min | ~$1 | Ready to run |
| **Phase 2: Join Tables** | 5 min | Free | SQL ready |
| **Phase 3: Generate Embeddings** | 1-2 hours | ~$2-3 | Need to code |
| **Phase 4: Update Indexes** | 30 min | Free | Delta Sync |
| **Phase 5: A/B Test** | 1 week | Free | Track metrics |
| **Phase 6: Production Rollout** | 1 day | Free | Monitor |
| **TOTAL (if scaling to full 44K)** | ~4 hours + 1 week testing | **$6-10** | |

---

## Current Status: Ready to Execute Phase 1

**You are here** → Run the SmolVLM notebook on 100 products

**Next**: After you review test results, I'll help with Phase 3 (embedding generation)

---

## Quick Commands

### Check Progress
```sql
-- How many products extracted?
SELECT COUNT(*) FROM main.fashion_demo.product_extracted_attributes;

-- Success rate?
SELECT
  SUM(CASE WHEN extraction_success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate_pct
FROM main.fashion_demo.product_extracted_attributes;
```

### Troubleshooting
```bash
# Check GPU availability
nvidia-smi

# Check cluster logs
# Go to: Compute → Your Cluster → Event Log

# Check notebook logs
# Scroll to bottom of each cell for error messages
```

---

Ready to run Phase 1? Let me know what you see in the test results!
