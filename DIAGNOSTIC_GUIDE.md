# Diagnostic Guide - Vector Search Score Issues

## Overview
Added detailed logging to diagnose why search results show the same similarity scores.

**Commit**: 5259725

---

## 🔍 **What to Look For in Logs**

After redeploying with the latest code, search for these log patterns:

### 1. Score Extraction Debug Info
```
📊 First result score debugging:
   Row length: 13, Columns: 12
   Last element (score): 0.923456 (type: <class 'float'>)
   Product dict keys: ['product_id', 'product_display_name', ..., 'score']
```

**What This Tells Us**:
- ✅ `Row length > Columns` → Score is being appended
- ✅ `Last element` has a float value → Score exists
- ✅ `'score'` in Product dict keys → Score extracted successfully

### 2. Score Statistics
```
📈 Score statistics: min=0.8234, max=0.9876, unique=10
```

**What This Tells Us**:
- ✅ `unique > 1` → Scores vary across results (GOOD!)
- ❌ `unique = 1` → All products have same score (PROBLEM!)

### 3. Missing Score Warnings
```
⚠️  Row 0: No score found! Row length=12, Columns=12
```

**What This Tells Us**:
- ❌ Vector Search isn't appending scores
- Possible index configuration issue

---

## 🎯 **Expected vs Problem Scenarios**

### ✅ **Good Scenario** (Scores Working)
```
2025-12-10 XX:XX:XX - 📊 First result score debugging:
2025-12-10 XX:XX:XX -    Row length: 13, Columns: 12
2025-12-10 XX:XX:XX -    Last element (score): 0.9234 (type: <class 'float'>)
2025-12-10 XX:XX:XX - 📈 Score statistics: min=0.7123, max=0.9234, unique=20
2025-12-10 XX:XX:XX - ✅ Semantic text search returned 20 results
```
→ Scores extracted, vary across products ✅

### ❌ **Problem Scenario 1** (All Same Score)
```
2025-12-10 XX:XX:XX - 📊 First result score debugging:
2025-12-10 XX:XX:XX -    Row length: 13, Columns: 12
2025-12-10 XX:XX:XX -    Last element (score): 0.8500 (type: <class 'float'>)
2025-12-10 XX:XX:XX - 📈 Score statistics: min=0.8500, max=0.8500, unique=1
```
→ Score extracted but ALL products have 0.85 ❌

**Root Cause**: Vector Search may be returning constant scores, or index has issue

### ❌ **Problem Scenario 2** (No Scores)
```
2025-12-10 XX:XX:XX - ⚠️  Row 0: No score found! Row length=12, Columns=12
2025-12-10 XX:XX:XX - ⚠️  No scores found in any of the 20 products!
```
→ No scores being appended by Vector Search ❌

**Root Cause**: Index not configured for similarity scoring

---

## 🔧 **Potential Issues & Solutions**

### Issue 1: All Scores Are 0.85
**Symptom**: `unique=1` and score is 0.85

**Root Cause**: Code defaults to 0.85 when score missing
```python
product.similarity_score = p.get("score", 0.85)  # ← Default!
```

**Solution**: Vector Search isn't returning scores. Check:
1. Index configuration
2. Embedding column exists in source table
3. Delta sync is working

**Fix**:
```sql
-- Verify index has embedding column
DESCRIBE DETAIL main.fashion_demo.vs_hybrid_search;

-- Check source table has embeddings
SELECT
  product_id,
  size(hybrid_embedding) as embedding_size,
  hybrid_embedding[0] as first_value
FROM main.fashion_demo.product_embeddings_multimodal
LIMIT 5;
```

### Issue 2: Scores Don't Vary Much
**Symptom**: `unique > 1` but `max - min < 0.1`

**Root Cause**: All products genuinely similar to query, OR embeddings are too similar

**Solution**: Test with very different queries
```bash
# Should give very different results
curl /api/v1/search/text -d '{"query": "red dress"}'
curl /api/v1/search/text -d '{"query": "black shoes"}'
curl /api/v1/search/text -d '{"query": "blue hat"}'
```

### Issue 3: Row Length Matches Columns
**Symptom**: `Row length=12, Columns=12` (equal!)

**Root Cause**: Vector Search not appending scores

**Solution**: Check index type and configuration
- Delta Sync indexes should auto-append scores
- Check if using Direct Access (doesn't support similarity)

---

## 🧪 **Manual Testing Script**

Use the included test script to diagnose locally:

```bash
# In the Databricks App environment
python test_vector_search_scores.py
```

This will:
1. Generate a CLIP embedding for "red dress"
2. Query the hybrid Vector Search index
3. Show detailed score information
4. Inspect raw Vector Search response format

---

## 📊 **What Data to Collect**

Please share these log sections after redeploying:

### For Text Search
Search for "party shirt" and share:
```
Logs containing:
- "📊 First result score debugging"
- "📈 Score statistics"
- "✅ Semantic text search returned"
```

### For Image Search
Upload any image and share:
```
Logs containing:
- "📊 First result score debugging"
- "📈 Score statistics"
- "✅ Image search returned"
```

### For Recommendations
View any user's recommendations and share:
```
Logs containing:
- "📊 First result score debugging"
- "📈 Score statistics"
- "Returning X personalized recommendations"
```

---

## 🔍 **Index Verification Queries**

If scores still not working, run these in Databricks SQL:

### 1. Check Index Status
```sql
-- Verify indexes exist and are ONLINE
SHOW VECTOR SEARCH INDEXES IN main.fashion_demo;
```

### 2. Verify Embedding Data
```sql
-- Check if embeddings exist
SELECT
  COUNT(*) as total_products,
  COUNT(hybrid_embedding) as with_hybrid_embedding,
  COUNT(image_embedding) as with_image_embedding,
  COUNT(text_embedding) as with_text_embedding
FROM main.fashion_demo.product_embeddings_multimodal;
```

Expected: All counts should be ~44,417

### 3. Check Embedding Quality
```sql
-- Sample embeddings
SELECT
  product_id,
  product_display_name,
  size(hybrid_embedding) as embedding_dim,
  hybrid_embedding[0] as first_value,
  hybrid_embedding[511] as last_value
FROM main.fashion_demo.product_embeddings_multimodal
LIMIT 10;
```

Expected:
- `embedding_dim = 512`
- Values between -1.0 and 1.0
- Not all zeros

### 4. Check Index Sync Status
```sql
-- For Delta Sync indexes
DESCRIBE DETAIL main.fashion_demo.vs_hybrid_search;
```

Look for `pipeline_status` - should be `READY` or `RUNNING`

---

## 🚀 **Next Steps**

1. **Redeploy** app with commit 5259725

2. **Test search** (text, image, recommendations)

3. **Share logs** showing:
   - Score debugging info
   - Score statistics
   - Any warnings

4. **If still broken**, run verification queries above

5. **Additional test**: Run `test_vector_search_scores.py` in app environment

---

## 📝 **Quick Reference**

### Search Endpoints to Test
```bash
# Text search
POST /api/v1/search/text
{"query": "red dress", "limit": 10}

# Image search
POST /api/v1/search/image
(Upload image file)

# Recommendations
GET /api/v1/search/recommendations/user_007598?limit=10
```

### Log Patterns to Find
- `📊` = Score extraction details
- `📈` = Score statistics
- `⚠️` = Warnings about missing scores
- `✅` = Success messages

### Key Metrics
- **Row length** vs **Columns**: Should be `N+1` vs `N`
- **unique scores**: Should be > 1
- **score range**: Should vary (e.g., 0.70-0.95)

---

## ✅ **Success Criteria**

Search is working correctly when logs show:

```
✅ Row length > Columns (score appended)
✅ Score is float type
✅ unique > 1 (scores vary)
✅ min/max range > 0.1 (meaningful variation)
✅ No "No score found" warnings
```

Once you see these, search results should display varying match percentages! 🎉
