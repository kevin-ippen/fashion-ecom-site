# Hybrid Search Flexibility Design

## Use Cases & Filter Strategies

### 1. **Personalized Recommendations** (Most Restrictive)
**Widget**: Homepage "Recommended for You"
**Filters**: Price range, preferred categories, preferred colors
```python
filters = {
    "master_category IN": persona["preferred_categories"],
    "base_color IN": persona["color_prefs"],
    "price >=": persona["min_price"] * 0.8,
    "price <=": persona["max_price"] * 1.2
}
search(hybrid_index, user_embedding, filters=filters)
```

---

### 2. **Similar Items** (Moderate)
**Widget**: Product page "You May Also Like"
**Filters**: Same category, similar price range (±30%)
```python
filters = {
    "master_category": product.master_category,
    "price >=": product.price * 0.7,
    "price <=": product.price * 1.3
}
search(hybrid_index, product_embedding, filters=filters)
```

---

### 3. **Visually Similar** (Minimal)
**Widget**: Product page "Similar Styles"
**Filters**: None or just category
```python
filters = {
    "master_category": product.master_category  # Optional
}
search(image_index, product_image_embedding, filters=filters)
```

---

### 4. **Complete the Look** (Cross-Category)
**Widget**: Product page "Complete the Look"
**Filters**: Different category, similar style/season
```python
filters = {
    "master_category !=": product.master_category,  # Different category
    "season": product.season
}
search(hybrid_index, product_embedding, filters=filters)
```

---

## Flexible API Design

### Service Layer
```python
# services/vector_search_service.py

class VectorSearchService:
    def search(
        self,
        index_name: str,
        query_vector: List[float],
        num_results: int = 20,
        filters: Optional[Dict[str, Any]] = None,  # ✅ Optional!
        columns: Optional[List[str]] = None,
        boost_rules: Optional[Dict[str, float]] = None  # ✅ Post-search boosting
    ) -> List[Dict]:
        """
        Flexible vector search with optional filters and boosting

        Args:
            index_name: Which index to search (image/text/hybrid)
            query_vector: 512-dim embedding
            num_results: How many results to return
            filters: Optional filters (None = no filtering)
            columns: Which columns to return
            boost_rules: Optional score boosting rules
        """
        # Apply filters only if provided
        results = self.index.similarity_search(
            query_vector=query_vector,
            num_results=num_results,
            filters=filters or {},  # Empty dict = no filters
            columns=columns or self.default_columns
        )

        # Apply optional boosting
        if boost_rules:
            results = self._apply_boosting(results, boost_rules)

        return results
```

---

### Route Layer
```python
# routes/v1/search.py

@router.get("/recommendations/{user_id}")
async def get_recommendations(
    user_id: str,
    limit: int = 20,
    restrict_category: bool = True,   # ✅ Configurable!
    restrict_price: bool = True,      # ✅ Configurable!
    restrict_color: bool = False,     # ✅ Configurable!
):
    """
    Personalized recommendations with configurable filtering
    """
    persona = get_persona(user_id)
    user_embedding = get_user_embedding(user_id)

    # Build filters based on flags
    filters = {}

    if restrict_category:
        filters["master_category IN"] = persona["preferred_categories"]

    if restrict_price:
        filters["price >="] = persona["min_price"] * 0.8
        filters["price <="] = persona["max_price"] * 1.2

    if restrict_color:
        filters["base_color IN"] = persona["color_prefs"]

    # Flexible search
    results = vector_search_service.search(
        index_name="vs_hybrid_search",
        query_vector=user_embedding,
        num_results=limit,
        filters=filters if filters else None  # None = unrestricted
    )

    return results


@router.get("/products/{product_id}/similar")
async def get_similar_products(
    product_id: str,
    similarity_type: str = "visual",  # visual, semantic, hybrid
    same_category: bool = True,
    limit: int = 12
):
    """
    Similar products with flexible similarity type
    """
    product = get_product(product_id)

    # Choose index based on type
    index_map = {
        "visual": "vs_image_search",
        "semantic": "vs_text_search",
        "hybrid": "vs_hybrid_search"
    }
    index_name = index_map[similarity_type]

    # Get product embedding
    product_embeddings = get_product_embeddings(product_id)
    query_vector = {
        "visual": product_embeddings["image_embedding"],
        "semantic": product_embeddings["text_embedding"],
        "hybrid": product_embeddings["hybrid_embedding"]
    }[similarity_type]

    # Optional category filter
    filters = None
    if same_category:
        filters = {"master_category": product.master_category}

    results = vector_search_service.search(
        index_name=index_name,
        query_vector=query_vector,
        num_results=limit,
        filters=filters
    )

    return results


@router.get("/products/{product_id}/complete-look")
async def get_complete_look(
    product_id: str,
    limit: int = 8
):
    """
    Cross-category recommendations to complete the look
    """
    product = get_product(product_id)
    product_embeddings = get_product_embeddings(product_id)

    # Find items in DIFFERENT categories
    filters = {
        "master_category !=": product.master_category,
        "product_id !=": product_id  # Exclude self
    }

    # Use hybrid for best cross-modal matching
    results = vector_search_service.search(
        index_name="vs_hybrid_search",
        query_vector=product_embeddings["hybrid_embedding"],
        num_results=limit,
        filters=filters
    )

    return results
```

---

## Widget-Specific Configurations

### Homepage: "Recommended for You"
```python
# Restrictive - match user preferences closely
filters = {
    "master_category IN": persona["preferred_categories"],
    "price >=": persona["min_price"] * 0.8,
    "price <=": persona["max_price"] * 1.2
}
boost_rules = {
    "color_match": 0.15,      # Boost if color matches prefs
    "category_match": 0.10    # Boost if category matches prefs
}
```

### Product Page: "Similar Styles"
```python
# Less restrictive - visual similarity only
filters = {
    "master_category": product.master_category  # Keep same category
}
boost_rules = None  # Pure similarity
```

### Product Page: "You May Also Like" (Personalized)
```python
# Moderate - combine product + user preferences
filters = {
    "master_category": product.master_category,
    "price >=": min(product.price * 0.7, persona["min_price"]),
    "price <=": max(product.price * 1.3, persona["max_price"])
}
boost_rules = {
    "color_match": 0.10  # Slight boost for user color prefs
}
```

### Product Page: "Complete the Look"
```python
# Cross-category - find complementary items
filters = {
    "master_category !=": product.master_category,  # Different!
    "season": product.season  # Match season
}
boost_rules = None
```

---

## Configuration Presets

```python
# config.py or constants

WIDGET_PRESETS = {
    "homepage_recommendations": {
        "index": "vs_hybrid_search",
        "filters": "user_preferences",  # Category, price, color
        "boost": {"color": 0.15, "category": 0.10},
        "num_results": 20
    },

    "similar_styles": {
        "index": "vs_image_search",
        "filters": "category_only",  # Just same category
        "boost": None,
        "num_results": 12
    },

    "you_may_like": {
        "index": "vs_hybrid_search",
        "filters": "category_and_price",
        "boost": {"color": 0.10},
        "num_results": 12
    },

    "complete_look": {
        "index": "vs_hybrid_search",
        "filters": "cross_category",
        "boost": None,
        "num_results": 8
    },

    "search_results": {
        "index": "vs_hybrid_search",
        "filters": None,  # No restrictions for search
        "boost": None,
        "num_results": 20
    }
}
```

---

## Benefits of This Design

### ✅ Flexibility
- Each widget can choose its own restriction level
- Easy to A/B test different filtering strategies
- Can adjust per-widget without touching core logic

### ✅ Performance
- Optional filters = caller decides speed vs quality tradeoff
- Restrictive filters = faster (smaller search space)
- No filters = slower but more diverse results

### ✅ Explainability
- Can add personalization reasons based on which filters matched
- "Matches your category preferences" if category filter used
- "Similar to items you like" if no filters used

### ✅ Maintainability
- Single search function handles all use cases
- Widget-specific logic lives in routes, not service
- Easy to add new widgets with custom filter strategies

---

## Implementation Priority

1. **Core Service** - Flexible search with optional filters
2. **Basic Widgets** - Homepage recommendations, similar styles
3. **Advanced Widgets** - Complete the look, personalized variations
4. **A/B Testing** - Try different filter strategies per widget
5. **Analytics** - Track which filter strategies perform best

---

## Example: Product Page Widgets

```tsx
// ProductDetail.tsx
<div className="related-products">
  {/* Pure visual similarity - no restrictions */}
  <SimilarStylesWidget
    productId={productId}
    similarityType="visual"
    sameCategory={true}
  />

  {/* Personalized - moderate restrictions */}
  <YouMayLikeWidget
    productId={productId}
    userId={userId}
    restrictPrice={true}
    restrictColor={false}
  />

  {/* Cross-category - different items */}
  <CompleteLookWidget
    productId={productId}
    crossCategory={true}
  />
</div>
```

Each widget calls the same underlying service but with different filter parameters!
