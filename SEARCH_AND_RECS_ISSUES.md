# Search & Recommendations Issues - Diagnosis and Fixes

## Issues Identified

### 1. 🚨 **Bad Recommendations** - Not matching user personas

**Symptoms**:
- Recommendations don't make sense for the selected persona
- Products shown don't match user's stated preferences
- Personalization reasons are misleading

**Root Causes**:

#### A. **Category Mismatch**
**Problem**: Personas use categories that don't exist in the database

Personas have:
```json
"preferred_categories": ["Topwear", "Casual Shoes", "Accessories"]
```

But database likely has:
```sql
-- Actual master_category values might be:
"Apparel", "Footwear", "Personal Care", "Free Items", "Sporting Goods"
```

**Impact**: The recommendation filter `master_category = "Topwear"` returns **zero results**

**Current Code** ([routes/v1/search.py:124-131](routes/v1/search.py#L124-L131)):
```python
filters = {}
min_price = persona["p25_price"] * 0.8
max_price = persona["p75_price"] * 1.2
filters["min_price"] = min_price
filters["max_price"] = max_price

# ❌ NO category filtering! Should filter by preferred categories
products_data = await repo.get_products(
    limit=limit * 2,
    filters=filters
)
```

**Why it's broken**: The code filters by price only, not categories. So:
- **Budget-Conscious Casual** (wants Topwear) gets same results as...
- **Luxury Fashionista** (wants Accessories) gets same results as...
- **Athletic Performance** (wants Sports gear)

All personas get the same products (just filtered by price), which makes no sense!

#### B. **Case-Sensitive Color Matching**
**Problem**: Color names might not match exactly

Personas have:
```json
"color_prefs": ["Blue", "Grey", "Black", "White"]
```

Database might have:
```
"blue", "grey", "black", "white"  (lowercase)
"Navy Blue", "Sky Blue" (different variations)
```

**Current Code** ([routes/v1/search.py:145](routes/v1/search.py#L145)):
```python
color_match = p["base_color"] in preferred_colors if p["base_color"] else False
# ❌ Case-sensitive exact match! "Blue" != "blue"
```

**Impact**: Color matching fails silently, so personalization score is always low

#### C. **No Category Filtering in Query**
**Problem**: Products aren't filtered by user's preferred categories at all

The recommendations should:
1. Filter by price range ✅ (working)
2. Filter by preferred categories ❌ (NOT implemented)
3. Score by color match ⚠️ (broken due to case sensitivity)

**Result**: Every persona gets random products within their price range

---

### 2. 🚨 **Text Search Returns "No Results Found"**

**Symptoms**:
- Search for "dress" → No results
- Search for "shoes" → No results
- ANY search query → No results

**Root Causes**:

#### A. **NULL Values in Database Columns**
**Problem**: ILIKE search doesn't handle NULL values

**Current Code** ([repositories/lakebase.py:219-227](repositories/lakebase.py#L219-227)):
```sql
SELECT *
FROM fashion_demo.productsdb
WHERE LOWER(product_display_name) ILIKE '%dress%'
   OR LOWER(article_type) ILIKE '%dress%'
   OR LOWER(sub_category) ILIKE '%dress%'
LIMIT 20
```

**If any column has NULL**:
```sql
LOWER(NULL) ILIKE '%dress%'  -- Returns NULL, not FALSE
NULL OR NULL OR NULL          -- Returns NULL
WHERE NULL                    -- Excludes the row
```

**Impact**: Products with NULL in ANY of the 3 columns are excluded even if other columns match

#### B. **Possible Schema/Table Issues**
The query uses:
```python
FROM {self.schema}.{settings.PRODUCTS_TABLE}
# Resolves to: fashion_demo.productsdb
```

**Potential Issues**:
- Schema might be wrong (should be `ecom.fashion_demo`?)
- Table might be empty
- Permissions issue

#### C. **Empty Results Logging**
No logging to debug why search fails. We don't know if:
- Query executed successfully but returned 0 rows
- Query threw an error
- Database connection failed

---

## Recommended Fixes

### Fix 1: Proper Recommendations with Category Filtering

**Step 1**: Query database to understand actual category values:

```sql
-- Find out what master_category values actually exist
SELECT DISTINCT master_category, COUNT(*) as count
FROM fashion_demo.productsdb
WHERE master_category IS NOT NULL
GROUP BY master_category
ORDER BY count DESC;

-- Find out what sub_category values exist
SELECT DISTINCT sub_category, COUNT(*) as count
FROM fashion_demo.productsdb
WHERE sub_category IS NOT NULL
GROUP BY sub_category
ORDER BY count DESC;

-- Find out color values
SELECT DISTINCT base_color, COUNT(*) as count
FROM fashion_demo.productsdb
WHERE base_color IS NOT NULL
GROUP BY base_color
ORDER BY count DESC
LIMIT 50;
```

**Step 2**: Update personas.json to match actual database values:

```json
{
  "user_id": "user_001",
  "name": "Budget-Conscious Casual",
  "preferred_categories": ["Apparel"],  // ← Use actual DB values
  "preferred_sub_categories": ["Topwear", "Casual"],  // ← Add this
  "color_prefs": ["blue", "grey", "black", "white"],  // ← Lowercase to match DB
  ...
}
```

**Step 3**: Add category filtering to recommendations:

```python
# routes/v1/search.py - recommendations endpoint

filters = {}

# Price filter (existing)
filters["min_price"] = persona["p25_price"] * 0.8
filters["max_price"] = persona["p75_price"] * 1.2

# ✅ ADD: Category filter
if persona.get("preferred_categories"):
    # Filter by first preferred category (or loop through all)
    filters["master_category"] = persona["preferred_categories"][0]

products_data = await repo.get_products(
    limit=limit * 3,  # Get more for color filtering
    filters=filters
)

# Normalize colors for matching
preferred_colors = set(c.lower() for c in persona["color_prefs"])

for p in products_data:
    product_color = (p["base_color"] or "").lower()
    color_match = product_color in preferred_colors

    # ... rest of scoring logic
```

**Step 4**: Add category matching to score:

```python
# Add category bonus
score = 0.3  # Base score

# ✅ Category match (if sub_category matches preferred)
if p.get("sub_category") in persona.get("preferred_sub_categories", []):
    score += 0.2

# ✅ Color match (normalized)
if color_match:
    score += 0.3

# ✅ Price match
price_diff = abs(p["price"] - persona["avg_price"])
price_range = persona["max_price"] - persona["min_price"]
if price_range > 0:
    price_score = 1 - (price_diff / price_range)
    score += 0.2 * max(0, price_score)
```

---

### Fix 2: Robust Text Search with NULL Handling

**Update `search_products_by_text()` in repositories/lakebase.py**:

```python
async def search_products_by_text(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search products by text query with NULL handling"""

    # Log the search query
    logger.info(f"Searching for: '{query}' in schema: {self.schema}.{settings.PRODUCTS_TABLE}")

    sql_query = f"""
        SELECT *
        FROM {self.schema}.{settings.PRODUCTS_TABLE}
        WHERE
            (product_display_name IS NOT NULL AND LOWER(product_display_name) ILIKE :query)
            OR (article_type IS NOT NULL AND LOWER(article_type) ILIKE :query)
            OR (sub_category IS NOT NULL AND LOWER(sub_category) ILIKE :query)
            OR (master_category IS NOT NULL AND LOWER(master_category) ILIKE :query)
            OR (usage IS NOT NULL AND LOWER(usage) ILIKE :query)
        LIMIT :limit
    """

    results = await self._execute_query(sql_query, {"query": f"%{query.lower()}%", "limit": limit})

    # Log results count
    logger.info(f"Search returned {len(results)} results")

    return results
```

**Key Changes**:
1. ✅ Added `IS NOT NULL` checks before LOWER() to handle NULLs properly
2. ✅ Added more searchable columns (master_category, usage)
3. ✅ Added logging to debug search issues
4. ✅ Still case-insensitive with LOWER()

---

## Testing Plan

### Test Recommendations

```bash
# Test each persona
curl https://your-app/api/v1/search/recommendations/user_001 | jq
curl https://your-app/api/v1/search/recommendations/user_002 | jq
curl https://your-app/api/v1/search/recommendations/user_003 | jq

# Verify:
# 1. Each persona gets DIFFERENT products
# 2. Products match the persona's preferred categories
# 3. Products match the persona's color preferences
# 4. Prices are within the persona's range
# 5. Personalization reasons make sense
```

### Test Text Search

```bash
# Test common queries
curl -X POST https://your-app/api/v1/search/text \
  -H "Content-Type: application/json" \
  -d '{"query": "dress", "limit": 10}' | jq

curl -X POST https://your-app/api/v1/search/text \
  -H "Content-Type: application/json" \
  -d '{"query": "shoes", "limit": 10}' | jq

curl -X POST https://your-app/api/v1/search/text \
  -H "Content-Type: application/json" \
  -d '{"query": "blue", "limit": 10}' | jq

# Verify:
# 1. Returns results (not empty)
# 2. Results are relevant to the query
# 3. Check logs for "Search returned X results"
```

---

## Database Investigation Queries

Run these to understand your data:

```sql
-- Check if table exists and has data
SELECT COUNT(*) FROM fashion_demo.productsdb;

-- Check for NULLs in search columns
SELECT
    COUNT(*) as total_products,
    COUNT(product_display_name) as has_name,
    COUNT(article_type) as has_article_type,
    COUNT(sub_category) as has_sub_category,
    COUNT(base_color) as has_color,
    COUNT(master_category) as has_master_category
FROM fashion_demo.productsdb;

-- Find actual category values
SELECT DISTINCT master_category
FROM fashion_demo.productsdb
WHERE master_category IS NOT NULL
ORDER BY master_category;

-- Find actual color values (top 20)
SELECT base_color, COUNT(*) as count
FROM fashion_demo.productsdb
WHERE base_color IS NOT NULL
GROUP BY base_color
ORDER BY count DESC
LIMIT 20;

-- Test a simple search manually
SELECT product_id, product_display_name, article_type, base_color, price
FROM fashion_demo.productsdb
WHERE LOWER(product_display_name) ILIKE '%dress%'
LIMIT 5;
```

---

## Summary

**Recommendations Issues**:
1. ❌ Not filtering by preferred categories at all
2. ❌ Case-sensitive color matching fails
3. ❌ All personas get same products (just different price ranges)

**Text Search Issues**:
1. ❌ NULL values break ILIKE search
2. ❌ No logging to debug failures
3. ❌ Might be wrong schema/table

**Priority Fixes**:
1. **High**: Add NULL handling to text search
2. **High**: Add category filtering to recommendations
3. **Medium**: Fix case-sensitive color matching
4. **Medium**: Map persona categories to actual DB values
5. **Low**: Add comprehensive logging

