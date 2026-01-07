# Product Recommendations Feature

**Date**: January 6, 2026
**Deployment**: 01f0eb62d7db10698dcf168e93370911
**Status**: ✅ DEPLOYED

## Overview

Added two recommendation endpoints for "you might also like" functionality:

1. **Similar Products** - Visual similarity using FashionCLIP embeddings
2. **Complete the Look** - Outfit pairings from brand lookbook analysis

## Endpoints

### 1. GET /api/v1/products/{product_id}/similar

Returns visually similar products based on FashionCLIP embeddings.

**Query Parameters**:
- `limit`: Number of recommendations (default: 6, max: 20)

**Example**:
```
GET /api/v1/products/12345/similar?limit=6
```

**Response**:
```json
{
  "products": [
    {
      "product_id": "12346",
      "product_display_name": "Similar Red Dress",
      "master_category": "Apparel",
      "sub_category": "Topwear",
      "base_color": "Red",
      "price": 1299.0,
      "image_url": "https://.../12346.jpg",
      "similarity_score": 0.87
    }
  ],
  "total": 6,
  "page": 1,
  "page_size": 6,
  "has_more": false
}
```

**Algorithm**:
1. Retrieve source product metadata from Lakebase PostgreSQL
2. Get source product embedding from `main.fashion_sota.product_embeddings`
3. Search vector index for similar products (5x limit for filtering pool)
4. Apply category compatibility filtering
5. Diversify by color (best effort, aim for 2+ colors)
6. Enrich with full product data from Lakebase

**Category Compatibility Rules**:
- ❌ Don't recommend same sub-category within same master category
  - No Topwear + Topwear
  - No Bottomwear + Bottomwear
  - No Shoes + Shoes
  - No Bags + Bags
- ✅ Allow cross-category recommendations
  - Apparel + Accessories ✓
  - Apparel + Footwear ✓
  - Footwear + Accessories ✓

**Diversity Strategy**:
- Round-robin through available colors
- Aim for minimum 2 different colors
- Best effort (returns what's available if diversity goals can't be met)

### 2. GET /api/v1/products/{product_id}/complete-the-look

Returns complementary products based on outfit pairings from brand lookbooks.

**Query Parameters**:
- `limit`: Number of recommendations (default: 4, max: 12)

**Example**:
```
GET /api/v1/products/12345/complete-the-look?limit=4
```

**Response**:
```json
{
  "products": [
    {
      "product_id": "67890",
      "product_display_name": "Matching Blue Jeans",
      "master_category": "Apparel",
      "sub_category": "Bottomwear",
      "base_color": "Blue",
      "price": 899.0,
      "image_url": "https://.../67890.jpg",
      "personalization_reason": "Paired together in 12 outfits"
    }
  ],
  "total": 4,
  "page": 1,
  "page_size": 4,
  "has_more": false
}
```

**Algorithm**:
1. Query `main.fashion_sota.outfit_recommendations_filtered` table
2. Get top-N products by co-occurrence count (how many times they appear together)
3. Sort by co-occurrence first, then average lookbook similarity
4. Enrich with full product data from Lakebase
5. Add personalization reason showing co-occurrence count

**Data Source**:
- Table: `main.fashion_sota.outfit_recommendations_filtered`
- Source: 29 brand lookbook images, 1,029 segmented items
- Coverage: 70.5% of products (21,333 products have recommendations)
- Quality: Outlier products (watches, ties) filtered out

## Implementation Details

### New Service: recommendations_service.py

**Key Components**:
- `INCOMPATIBLE_CATEGORIES`: Dict mapping incompatible category pairs
- `is_compatible()`: Check if two products can be recommended together
- `diversify_by_color()`: Round-robin color selection for diversity
- `get_similar_products()`: Main recommendation logic

### Updated Routes: routes/v1/products.py

**New Endpoints**:
- `GET /{product_id}/similar` - Visual similarity
- `GET /{product_id}/complete-the-look` - Outfit pairings

**Dependencies**:
- `recommendations_service` - Category filtering and diversity
- `vector_search_service` - Embedding similarity search
- `lakebase_repo` - Full product metadata retrieval
- Databricks SQL Statement Execution - Query outfit recommendations table

## Data Flow

### Similar Products (Visual Similarity)
```
Source Product ID
  ↓
Lakebase: Get metadata (category, subcategory)
  ↓
UC Table: Get embedding (main.fashion_sota.product_embeddings)
  ↓
Vector Search: Find similar (main.fashion_sota.product_embeddings_index)
  ↓
Filter: Category compatibility
  ↓
Diversify: Color round-robin
  ↓
Enrich: Full metadata from Lakebase
  ↓
Response: 6 similar products
```

### Complete the Look (Outfit Pairings)
```
Source Product ID
  ↓
UC Table: Query outfit recommendations (main.fashion_sota.outfit_recommendations_filtered)
  ↓
Sort: By co-occurrence count DESC
  ↓
Enrich: Full metadata from Lakebase
  ↓
Response: 4 complementary products with outfit context
```

## Configuration

No configuration changes needed. Uses existing:
- `settings.VS_INDEX` - main.fashion_sota.product_embeddings_index
- `settings.VS_ENDPOINT_NAME` - fashion-vector-search
- `settings.LAKEBASE_SCHEMA` - fashion_sota
- `settings.LAKEBASE_PRODUCTS_TABLE` - products_lakebase

## Testing

### Test Similar Products
```bash
curl "https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/api/v1/products/12345/similar?limit=6"
```

### Test Complete the Look
```bash
curl "https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/api/v1/products/12345/complete-the-look?limit=4"
```

### Expected Behavior
- **Similar products**: Returns 6 visually similar items, avoiding duplicate categories
- **Complete the look**: Returns 4 complementary items from outfit pairings
- **Fallback**: Returns empty array if no recommendations found (graceful degradation)
- **Errors**: 404 if product not found, 500 if service error

## Coverage

### Similar Products
- **Coverage**: 100% of products in vector index (43,916 products)
- **Quality**: High visual similarity (cosine similarity in embedding space)
- **Diversity**: Best-effort color diversification

### Complete the Look
- **Coverage**: 70.5% of products (21,333 products with outfit pairings)
- **Quality**: High (based on real brand lookbook styling)
- **Data**: 2.8M product pairs from 29 lookbook images
- **Filtering**: Outlier products removed (watches, ties)

## Future Enhancements

From INSPO_UPDATE.md recommendations:

1. **Expand lookbook data**
   - Current: 29 images with 1,029 items
   - Target: 100+ images with 5,000+ items
   - Would improve coverage to 90%+

2. **Spatial clustering**
   - Extract individual outfits from multi-model scenes
   - Reduce nonsensical pairings from same image

3. **Hybrid recommendations**
   - Combine visual similarity + outfit pairings
   - Weighted approach for best of both worlds

4. **Metadata filtering**
   - Gender matching (Men's with Men's)
   - Price range compatibility
   - Color harmony rules

5. **Minimum similarity threshold**
   - Filter matches below 0.45 similarity
   - Reduce noise in recommendations

## API Documentation

Interactive API docs available at:
https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/docs

## Deployment

**Commit**: `15f4dbf`
**Deployment ID**: `01f0eb62d7db10698dcf168e93370911`
**Status**: ✅ RUNNING
**Time**: 2026-01-07 00:50:48 UTC

## Related Files

- [services/recommendations_service.py](services/recommendations_service.py) - Recommendation logic
- [routes/v1/products.py](routes/v1/products.py) - API endpoints
- [services/vector_search_service.py](services/vector_search_service.py) - Vector search
- [repositories/lakebase.py](repositories/lakebase.py) - Database access
