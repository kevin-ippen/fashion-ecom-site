# ML-Powered Improvements - Implementation Summary

**Date**: January 10, 2026
**Deployment**: 01f0edd482ca180b8895e402e330766b
**Status**: ✅ DEPLOYED

---

## Overview

Replaced basic SQL RANDOM() recommendations with intelligent ML-powered personalization and added business discovery features.

---

## Part 1: Intelligent Recommendations 🤖

### What Changed

**Before**: Homepage recommendations used SQL RANDOM() with basic filters
```python
# Old approach
filters = {"min_price": 1500} if persona == "luxury" else {}
products = await repo.get_products(sort_by="RANDOM", filters=filters)
```

**After**: Multi-signal ML-powered recommendation engine
```python
# New approach
user_embedding = get_user_embedding(user_id)  # 512-dim behavioral vector
recommendations = await intelligent_recommendations_service.get_recommendations(
    user=user,
    user_embedding=user_embedding,
    persona_style=persona_style,
    vector_search_service=vector_search_service,
    apply_diversity=True  # MMR algorithm
)
```

### How It Works

**1. Vector Similarity (60% weight)**
- Uses user's behavioral embedding (512-dim) from `user_style_features` table
- Performs Vector Search against product hybrid embeddings
- Finds products similar to user's preferences in embedding space

**2. Business Rules (40% weight)**
- **Category Match (35%)**: Prefers user's favorite categories
- **Color Preference (25%)**: Boosts products in user's preferred colors
- **Price Affinity (25%)**: Scores products 0.5x-2x user's average price
- **Recency Boost (15%)**: Slight boost for newer products (2017-2018)

**3. Diversity via MMR**
- Maximal Marginal Relevance algorithm
- Balances relevance (70%) vs diversity (30%)
- Prevents "5 black t-shirts in a row" problem
- Uses category and color as diversity signals

### Combined Score Formula

```
combined_score = 0.6 * vector_similarity + 0.4 * business_score

where business_score = (
    0.35 * category_match +
    0.25 * color_preference +
    0.25 * price_affinity +
    0.15 * recency_boost
)
```

### API Endpoint

**No changes to API surface** - endpoint remains the same:
```
GET /api/v1/search/recommendations/{user_id}?limit=20
```

**Response includes**:
```json
{
  "products": [
    {
      "product_id": "12345",
      "similarity_score": 0.78,
      "combined_score": 0.82,
      "business_score": 0.65,
      "personalization_reason": "Matches your preferences"
    }
  ]
}
```

### Benefits

✅ **Actually uses ML**: Vector Search + user embeddings (previously unused)
✅ **Truly personalized**: Not just filtered random
✅ **Diverse results**: MMR prevents repetition
✅ **Business-aware**: Respects category/color/price preferences
✅ **Persona-compatible**: Maintains luxury/budget/athletic filters
✅ **Fallback safe**: Falls back to SQL RANDOM() if embedding unavailable

### Files Created/Modified

**New Services**:
- [services/intelligent_recommendations_service.py](services/intelligent_recommendations_service.py) - Core recommendation engine

**Updated Endpoints**:
- [routes/v1/search.py](routes/v1/search.py#L213-L253) - Recommendations endpoint now uses ML

---

## Part 2: Business Discovery Features 🎯

### New Endpoints

#### 1. Trending Products

```
GET /api/v1/products/trending?limit=20
```

**Returns**: Popular/trending products based on engagement signals

**Algorithm** (Demo):
- Mock trending score = base_random * price_boost * recency_boost * category_boost
- Category diversity: Max 40% from any single category
- Biased toward newer, higher-priced items (luxury appeal)

**In Production**: Would use real user interaction data:
```
trending_score = views + (add_to_cart * 3) + (purchases * 10)
```

**Example Response**:
```json
{
  "products": [
    {
      "product_id": "45231",
      "product_display_name": "Nike Air Max 270",
      "price": 2499.0,
      "trending_score": 1.82,
      "personalization_reason": "Trending now"
    }
  ],
  "total": 20,
  "page": 1,
  "page_size": 20
}
```

---

#### 2. Seasonal Collections

```
GET /api/v1/products/seasonal?season=Winter&limit=20
```

**Returns**: Products appropriate for current season (or specified season)

**Seasons**: Spring, Summer, Fall, Winter (auto-detected if not specified)

**Algorithm**:
- Season-based category preferences:
  - **Summer**: 50% Apparel (lightweight), 30% Footwear (sandals), 20% Accessories
  - **Winter**: 60% Apparel (sweaters, coats), 25% Footwear (boots), 15% Accessories
  - **Spring/Fall**: 50% Apparel, 30% Footwear, 20% Accessories

**Example Response**:
```json
{
  "products": [
    {
      "product_id": "23456",
      "product_display_name": "Cashmere Sweater",
      "season": "Winter",
      "personalization_reason": "Winter collection"
    }
  ]
}
```

---

#### 3. New Arrivals

```
GET /api/v1/products/new-arrivals?limit=20&min_year=2017
```

**Returns**: Recently added products (using year as proxy for demo)

**Algorithm**:
- Filters products by year >= min_year (default: 2017)
- Sorts by year DESC (newest first)
- Applies category diversity (max 40% per category)

**In Production**: Would use `creation_date` or `ingestion_date` timestamp

**Example Response**:
```json
{
  "products": [
    {
      "product_id": "34567",
      "product_display_name": "Leather Jacket",
      "year": 2018,
      "personalization_reason": "New arrival"
    }
  ]
}
```

---

## Part 3: Data Model Support

### Tables Used

1. **user_style_features** (10K users)
   - `user_embedding`: 512-dim behavioral vector (NOW USED!)
   - `preferred_categories`, `color_prefs`, `avg_price`
   - Previously only used for hybrid search query

2. **product_embeddings_multimodal** (44K products)
   - `hybrid_embedding`: 512-dim product vector
   - Accessed via Vector Search hybrid index

3. **products_lakebase** (44K products)
   - Full product metadata
   - Extended with `min_year`/`max_year` filters

### New Filters Added

Updated [repositories/lakebase.py](repositories/lakebase.py#L102-L108):
```python
if filters.get("min_year"):
    where_clauses.append("year >= :min_year")

if filters.get("max_year"):
    where_clauses.append("year <= :max_year")
```

---

## Testing

### Test Intelligent Recommendations

```bash
# Get recommendations for luxury persona
curl "https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/api/v1/search/recommendations/user_001?limit=20"

# Should return:
# - Products similar to user's embedding (vector search)
# - Boosted by category/color/price preferences
# - Diverse (not all same category/color)
# - Price >= $1500 (luxury filter)
```

**Expected Log Output**:
```
🤖 Intelligent recommendations for user user_001 (luxury persona)
User embedding loaded: shape=(512,), norm=1.0000
Vector search returned 60 candidates
Recommendations diversity: categories={'Apparel': 12, 'Footwear': 5, 'Accessories': 3}, colors={'Black': 4, 'White': 3, ...}
✅ Returning 20 intelligent ML-powered recommendations
```

### Test Trending Products

```bash
curl "https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/api/v1/products/trending?limit=20"

# Should return:
# - Mix of categories (max 40% from any single category)
# - Biased toward newer, higher-priced items
# - Marked with "Trending now"
```

### Test Seasonal Products

```bash
# Auto-detect season (currently Winter in January)
curl "https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/api/v1/products/seasonal?limit=20"

# Specify season
curl "https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/api/v1/products/seasonal?season=Summer&limit=20"

# Should return:
# - Season-appropriate products
# - More Apparel for Winter (sweaters, coats)
# - More Footwear for Summer (sandals)
```

### Test New Arrivals

```bash
curl "https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/api/v1/products/new-arrivals?limit=20&min_year=2017"

# Should return:
# - Products from 2017-2018
# - Category diversity
# - Marked with "New arrival"
```

---

## Impact Metrics

### Before vs After

| Metric | Before (SQL RANDOM) | After (ML-Powered) |
|--------|---------------------|-------------------|
| Uses user embeddings | ❌ No | ✅ Yes |
| Vector search | ❌ No | ✅ Yes |
| Business rules | ⚠️ Basic filters only | ✅ Multi-signal scoring |
| Diversity | ⚠️ Random chance | ✅ MMR algorithm |
| Personalization depth | ⚠️ Price/category filters | ✅ Behavioral + preferences |
| Discovery features | ❌ None | ✅ Trending, seasonal, new |

### User Experience Improvements

1. **More Relevant**: Products match user's behavioral patterns (embedding similarity)
2. **More Diverse**: MMR prevents repetition (no more "5 black t-shirts")
3. **More Discoverable**: Trending, seasonal, new arrivals provide exploration paths
4. **More Engaging**: Business rules balance ML with UX (category/color/price)

---

## Architecture

### Recommendation Flow

```
User selects persona
  ↓
GET /api/v1/search/recommendations/{user_id}
  ↓
Fetch user_embedding from user_style_features (Lakebase)
  ↓
Normalize embedding (L2 norm = 1)
  ↓
Build persona filters (luxury → min_price >= 1500)
  ↓
Vector Search: query_vector=user_embedding, filters=persona_filters
  ↓
For each candidate:
  - Calculate business_score (category, color, price, recency)
  - combined_score = 0.6 * similarity + 0.4 * business
  ↓
Sort by combined_score DESC
  ↓
Apply MMR for diversity (balance relevance vs novelty)
  ↓
Return top-N diverse, relevant, personalized products
```

### Business Features Flow

```
GET /api/v1/products/trending
  ↓
Fetch 5x limit products (for diversity pool)
  ↓
Calculate mock trending_score (price * recency * category)
  ↓
Sort by trending_score DESC
  ↓
Apply category diversity (max 40% per category)
  ↓
Return top-N trending products
```

---

## Configuration

### Tunable Parameters

**Intelligent Recommendations** ([intelligent_recommendations_service.py](services/intelligent_recommendations_service.py)):
```python
# Score weights
VECTOR_WEIGHT = 0.6           # Vector similarity contribution
BUSINESS_WEIGHT = 0.4         # Business rules contribution

# Business rule weights (sum to 1.0)
CATEGORY_WEIGHT = 0.35
COLOR_WEIGHT = 0.25
PRICE_WEIGHT = 0.25
RECENCY_WEIGHT = 0.15

# MMR diversity
MMR_LAMBDA = 0.7              # 70% relevance, 30% diversity
CANDIDATE_MULTIPLIER = 3      # Fetch 3x candidates for filtering
```

**Business Features** ([business_features_service.py](services/business_features_service.py)):
```python
# Category diversity
MAX_CATEGORY_PERCENT = 0.4    # Max 40% from any category

# Seasonal weights
SUMMER_APPAREL = 0.5
SUMMER_FOOTWEAR = 0.3
SUMMER_ACCESSORIES = 0.2

# Trending boosts
HIGH_PRICE_BOOST = 1.3        # Price > $2000
RECENT_YEAR_BOOST = 1.4       # Year >= 2018
```

---

## Next Steps

### Phase 2 Improvements

1. **Real Trending Data**
   - Log user interactions (views, add-to-cart, purchases)
   - Calculate actual trending scores
   - Time-decay for recency

2. **Better Seasonal Attributes**
   - Add seasonal tags to products
   - Extract seasonal attributes (SmolVLM: "heavy knit" → Winter)
   - Use climate/weather data for regional personalization

3. **Enhanced MMR**
   - Use actual product embeddings for similarity (not just category/color)
   - Add price diversity (mix of price points)
   - Add sub-category diversity

4. **Collaborative Filtering**
   - "Users who liked X also liked Y"
   - Find similar users by embedding similarity
   - Aggregate their liked products

5. **Learning-to-Rank**
   - Train ranking model on user interactions
   - Features: similarity, business rules, context
   - Continuous improvement from user feedback

---

## Documentation

### API Documentation
Interactive docs: https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/docs

### Code References
- **Intelligent Recommendations**: [services/intelligent_recommendations_service.py](services/intelligent_recommendations_service.py)
- **Business Features**: [services/business_features_service.py](services/business_features_service.py)
- **Recommendations Endpoint**: [routes/v1/search.py](routes/v1/search.py#L213-L253)
- **Business Endpoints**: [routes/v1/products.py](routes/v1/products.py#L559-L715)

### Related Documentation
- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) - Architecture overview
- [LESSONS_LEARNED.md](LESSONS_LEARNED.md) - Best practices
- [DATA_INVENTORY.md](DATA_INVENTORY.md) - Data assets

---

## Deployment

**Commit**: `7d5304a`
**Deployment ID**: `01f0edd482ca180b8895e402e330766b`
**Status**: ✅ RUNNING
**Time**: 2026-01-10 03:31:17 UTC

**Changes**:
- 5 files changed
- 795 insertions, 43 deletions
- 2 new services created

---

**Last Updated**: 2026-01-10
**Version**: 1.0
