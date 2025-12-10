# Search & Recommendation Quality Improvements

## Current State Analysis

### System Architecture
- **CLIP Model**: ViT-B/32 (512-dimensional embeddings)
- **Vector Indexes**: 3 separate indexes (image, text, hybrid)
- **Similarity Metric**: L2 (cosine similarity after normalization)
- **Text Descriptions**: Concatenated attributes (name + category + color + gender + season + usage + year)
- **User Embeddings**: Generated from interaction history (30-33 interactions per persona)
- **Recommendation Logic**: 60% vector similarity + 40% rule-based (category/color/price match)

### Current Performance
Based on production logs:
- **Text Search Scores**: 52.77% to 54.70% (narrow 2% range)
- **Image Search Scores**: 67.34% to 69.52% (narrow 2.5% range)
- **Recommendations**: 64.38% to 65.00% (very narrow 0.6% range)

**Interpretation**: Narrow score ranges suggest either:
1. ✅ High-quality embeddings finding truly relevant items (all good matches)
2. ⚠️  Lack of differentiation between very relevant and somewhat relevant results
3. ⚠️  Limited diversity in catalog or search space

---

## Problem Areas

### 1. Text Search Quality Issues

**Current Limitations:**
```python
# Text descriptions are shallow concatenations:
"product_name Apparel Accessories Black Men Summer Casual 2018"
```

**Problems:**
- ❌ No material information ("leather", "cotton", "wool")
- ❌ No style descriptors ("minimalist", "vintage", "sporty")
- ❌ No fit/silhouette info ("slim fit", "oversized", "tailored")
- ❌ No occasion context ("office wear", "party", "athletic")
- ❌ No brand positioning ("luxury", "budget", "premium")
- ❌ Limited semantic richness for CLIP to understand

**Impact:**
- Query "leather jacket" → Can't find leather products (material not in description)
- Query "professional office wear" → Misses formal shirts (no "office" or "professional" tags)
- Query "cozy winter sweater" → Limited understanding of "cozy" feeling

---

### 2. Personalization Quality Issues

**Current User Embeddings:**
- Generated from 30-33 interactions per user
- Based on aggregate behavior (no temporal or sequential patterns)
- No negative signals (what users explicitly disliked)
- No contextual factors (time of day, season, occasion)

**Persona Data Limitations:**
```json
{
  "preferred_categories": ["Accessories", "Apparel"],  // Very broad!
  "color_prefs": ["Black", "Brown", "Purple", "Blue", "White"],  // 5 colors = 50%+ of catalog
  "price_range": {"min": 24, "max": 33}  // Narrow but may filter out good items
}
```

**Problems:**
- ⚠️  Category filter too restrictive (Accessories + Apparel = most items)
- ⚠️  Color preferences too broad (5 colors = not very personalized)
- ⚠️  No negative preferences ("never show me XYZ")
- ⚠️  No style progression (user tastes evolve over time)
- ⚠️  All results from same 2 categories (no diversity)

**Current Hybrid Scoring:**
```python
# 60% vector + 40% rules
product.similarity_score = 0.6 * vector_score + 0.4 * rule_score

# Rule scoring:
if category_match: rule_score += 0.3
if color_match: rule_score += 0.4
if price_match: rule_score += 0.3 * price_score
```

**Problems:**
- ⚠️  Fixed weights (not learned from user behavior)
- ⚠️  Simple additive scoring (no interactions between factors)
- ⚠️  No temporal decay (old interactions = recent interactions)
- ⚠️  No diversity penalty (all results can be similar)

---

### 3. Result Quality Issues

**Narrow Score Ranges:**
- Text: 52.77% to 54.70% (only 2% spread)
- Image: 67.34% to 69.52% (only 2.5% spread)
- Recs: 64.38% to 65.00% (only 0.6% spread!)

**Possible Causes:**
1. **Embedding saturation**: CLIP embeddings cluster tightly for similar items
2. **Index limitations**: Delta Sync HNSW may not explore diverse enough
3. **Filter side effects**: Heavy filtering reduces diversity
4. **Catalog homogeneity**: Too many similar products in catalog
5. **Query specificity**: User queries too generic

**Impact:**
- Hard to rank results meaningfully (all ~53% similar)
- Top result ≈ bottom result in perceived quality
- Users see repetitive, homogeneous results

---

## Improvement Strategies

### Quick Wins (1-2 days)

#### 1. **Enrich Text Descriptions with Inferred Attributes**

**Goal**: Add semantic richness to product descriptions.

**Implementation**:
```python
# Create enriched descriptions using attribute inference
def enrich_product_description(product):
    """Add inferred attributes based on existing fields"""

    base = f"{product['product_display_name']} {product['article_type']}"
    enrichments = []

    # Infer style from article_type
    if 'shirt' in article_type.lower():
        if 'formal' in base.lower():
            enrichments.append("professional office wear dress shirt")
        elif 'casual' in base.lower():
            enrichments.append("everyday casual weekend wear")

    # Infer occasion from usage + season
    if product['usage'] == 'Formal' and product['season'] == 'Winter':
        enrichments.append("elegant winter formal event attire")

    # Infer material from article_type (heuristic)
    if 'jacket' in article_type.lower():
        enrichments.append("outerwear layering piece")
    if 'dress' in article_type.lower():
        enrichments.append("elegant feminine dress")

    # Add brand positioning based on price
    if product['price'] > 100:
        enrichments.append("premium luxury designer")
    elif product['price'] < 30:
        enrichments.append("affordable budget everyday")

    return f"{base} {' '.join(enrichments)}"
```

**Benefit**: Better matches for queries like "office wear", "cozy", "luxury"

**Effort**: Low (can run as one-time script to regenerate text embeddings)

---

#### 2. **Implement Query Expansion**

**Goal**: Expand user queries with synonyms and related terms.

**Implementation**:
```python
QUERY_SYNONYMS = {
    "leather": ["leather", "genuine leather", "faux leather", "pleather"],
    "cozy": ["cozy", "comfortable", "soft", "warm", "plush"],
    "professional": ["professional", "office", "formal", "business", "work"],
    "athletic": ["athletic", "sport", "gym", "workout", "active"],
    "vintage": ["vintage", "retro", "classic", "timeless", "throwback"]
}

def expand_query(query: str) -> str:
    """Expand query with synonyms"""
    words = query.lower().split()
    expanded = []

    for word in words:
        expanded.append(word)
        if word in QUERY_SYNONYMS:
            expanded.extend(QUERY_SYNONYMS[word][:2])  # Add top 2 synonyms

    return " ".join(expanded)

# Usage:
query = "cozy sweater"
expanded = expand_query(query)  # "cozy comfortable warm sweater"
embedding = await clip_service.get_text_embedding(expanded)
```

**Benefit**: Broader semantic coverage without changing embeddings

**Effort**: Low (just preprocessing before CLIP encoding)

---

#### 3. **Add Diversity to Results**

**Goal**: Avoid showing 20 nearly identical products.

**Implementation**:
```python
def diversify_results(products: List[Dict], diversity_window: int = 5) -> List[Dict]:
    """
    Apply Maximal Marginal Relevance (MMR) to diversify results

    Args:
        products: Results sorted by similarity score
        diversity_window: Look at top N products for diversity

    Returns:
        Reordered products with better diversity
    """
    if len(products) <= diversity_window:
        return products

    # Keep top result as-is (highest relevance)
    selected = [products[0]]
    remaining = products[1:]

    while len(selected) < len(products) and remaining:
        # For each remaining product, calculate diversity from selected
        best_idx = 0
        best_score = -1

        for i, candidate in enumerate(remaining):
            # Relevance score (from Vector Search)
            relevance = candidate.get('similarity_score', 0.5)

            # Diversity: how different from already selected items
            diversity = min([
                calculate_diversity(candidate, selected_product)
                for selected_product in selected[-diversity_window:]
            ])

            # MMR: balance relevance and diversity (λ = 0.5)
            mmr_score = 0.5 * relevance + 0.5 * diversity

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        selected.append(remaining.pop(best_idx))

    return selected

def calculate_diversity(prod1: Dict, prod2: Dict) -> float:
    """Calculate how different two products are"""
    diversity = 0.0

    # Different category = +0.3
    if prod1.get('master_category') != prod2.get('master_category'):
        diversity += 0.3

    # Different color = +0.3
    if prod1.get('base_color') != prod2.get('base_color'):
        diversity += 0.3

    # Different article type = +0.4
    if prod1.get('article_type') != prod2.get('article_type'):
        diversity += 0.4

    return diversity
```

**Benefit**: Users see varied results (not 20 black t-shirts)

**Effort**: Medium (needs embedding distance calculation or heuristics)

---

#### 4. **Implement Re-ranking with Business Rules**

**Goal**: Boost items based on business priorities.

**Implementation**:
```python
def rerank_with_business_rules(products: List[Dict], user_id: str = None) -> List[Dict]:
    """Apply business rules to boost/demote products"""

    for product in products:
        boost = 1.0

        # Boost new arrivals
        if product.get('year') == 2018:  # Most recent in dataset
            boost *= 1.15

        # Boost items with good margins (example: higher price = better margin)
        if product['price'] > 75:
            boost *= 1.1

        # Boost items low in stock (create urgency)
        # stock_level = get_stock_level(product['product_id'])
        # if stock_level < 10:
        #     boost *= 1.2

        # Demote out-of-season items
        current_season = get_current_season()  # Winter, Spring, Summer, Fall
        if product.get('season') and product['season'] != current_season:
            boost *= 0.9

        # Apply boost to similarity score
        product['similarity_score'] = product.get('similarity_score', 0.5) * boost
        product['boost_applied'] = boost

    # Re-sort by boosted scores
    products.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)

    return products
```

**Benefit**: Align results with business goals (revenue, inventory)

**Effort**: Low (just post-processing)

---

### Medium-Term Improvements (1-2 weeks)

#### 5. **Implement Weighted Hybrid Search**

**Goal**: Combine multiple embedding types with learned weights.

**Current State**: Using single index (hybrid, text, or image)

**Proposed**:
```python
async def weighted_hybrid_search(
    query: str,
    image_bytes: bytes = None,
    user_id: str = None,
    num_results: int = 20
) -> List[Dict]:
    """
    Combine multiple searches with learned weights

    Strategy: Run multiple searches in parallel and merge results
    """
    from asyncio import gather

    searches = []
    weights = []

    # Text search (always)
    if query:
        text_emb = await clip_service.get_text_embedding(query)
        searches.append(
            vector_search_service.search_hybrid(text_emb, num_results=num_results*2)
        )
        weights.append(0.4)  # 40% weight

    # Image search (if image provided)
    if image_bytes:
        image_emb = await clip_service.get_image_embedding(image_bytes)
        searches.append(
            vector_search_service.search_image(image_emb, num_results=num_results*2)
        )
        weights.append(0.3)  # 30% weight

    # User preference search (if user logged in)
    if user_id:
        user_features = await get_user_style_features(user_id)
        if user_features and user_features['user_embedding']:
            user_emb = np.array(json.loads(user_features['user_embedding']))
            searches.append(
                vector_search_service.search_hybrid(user_emb, num_results=num_results*2)
            )
            weights.append(0.3)  # 30% weight

    # Execute all searches in parallel
    all_results = await gather(*searches)

    # Merge with weighted Reciprocal Rank Fusion (RRF)
    return merge_results_rrf(all_results, weights, k=60)

def merge_results_rrf(
    all_results: List[List[Dict]],
    weights: List[float],
    k: int = 60
) -> List[Dict]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion

    RRF formula: score(d) = sum_r [ weight_r / (k + rank_r(d)) ]
    """
    product_scores = {}  # product_id -> (score, product_data)

    for search_idx, results in enumerate(all_results):
        weight = weights[search_idx]

        for rank, product in enumerate(results, start=1):
            pid = product['product_id']
            rrf_score = weight / (k + rank)

            if pid in product_scores:
                product_scores[pid] = (
                    product_scores[pid][0] + rrf_score,
                    product
                )
            else:
                product_scores[pid] = (rrf_score, product)

    # Sort by aggregated score
    merged = sorted(
        product_scores.values(),
        key=lambda x: x[0],
        reverse=True
    )

    # Return top results with combined scores
    return [
        {**product, 'similarity_score': score}
        for score, product in merged
    ]
```

**Benefit**: Better results by combining multiple signals

**Effort**: Medium (needs careful weight tuning)

---

#### 6. **Add Negative Filtering for Personalization**

**Goal**: Learn what users DON'T want.

**Implementation**:
```python
# Extend personas with negative preferences
{
  "user_id": "user_006327",
  "preferred_categories": ["Accessories", "Apparel"],
  "disliked_categories": ["Footwear"],  # NEW
  "color_prefs": ["Black", "Brown"],
  "disliked_colors": ["Pink", "Yellow"],  # NEW
  "style_avoid": ["Flashy", "Loud patterns"],  # NEW
  "max_price_ever": 50  # Never show items > $50
}

# Apply in search:
async def get_recommendations_with_negatives(user_id: str, limit: int = 20):
    persona = get_persona(user_id)

    # Build filters including negatives
    filters = {}

    # Positive filters
    if persona.get("preferred_categories"):
        filters["master_category"] = persona["preferred_categories"]

    # Add filters to EXCLUDE unwanted items
    # Note: Vector Search doesn't support NOT IN, so we filter post-search
    results = await vector_search_service.search_hybrid(...)

    # Post-filter negatives
    filtered_results = [
        p for p in results
        if p['master_category'] not in persona.get('disliked_categories', [])
        and p['base_color'] not in persona.get('disliked_colors', [])
        and p['price'] <= persona.get('max_price_ever', float('inf'))
    ]

    return filtered_results[:limit]
```

**Benefit**: More accurate personalization by avoiding bad matches

**Effort**: Medium (needs persona schema update + UI for collecting dislikes)

---

#### 7. **Implement Query Understanding**

**Goal**: Detect user intent and adjust search strategy.

**Implementation**:
```python
def understand_query_intent(query: str) -> Dict:
    """Classify query type and extract intent"""

    query_lower = query.lower()
    intent = {
        'type': 'general',  # general, specific_item, occasion, style, color
        'attributes': {},
        'strategy': 'hybrid'  # Which index/search to use
    }

    # Detect specific item searches
    specific_items = ['jacket', 'dress', 'shoes', 'shirt', 'pants', 'jeans']
    if any(item in query_lower for item in specific_items):
        intent['type'] = 'specific_item'
        intent['strategy'] = 'text'  # Text index better for specific items

    # Detect occasion-based searches
    occasions = ['office', 'party', 'wedding', 'gym', 'casual', 'formal']
    if any(occ in query_lower for occ in occasions):
        intent['type'] = 'occasion'
        intent['strategy'] = 'hybrid'  # Need both semantic + visual

    # Detect style-based searches
    styles = ['vintage', 'modern', 'minimalist', 'bohemian', 'athletic']
    if any(style in query_lower for style in styles):
        intent['type'] = 'style'
        intent['strategy'] = 'image'  # Visual similarity more important

    # Detect color-focused searches
    colors = ['red', 'black', 'white', 'blue', 'green']
    for color in colors:
        if color in query_lower:
            intent['attributes']['color'] = color
            # Add color filter to Vector Search

    return intent

# Usage in search endpoint:
async def search_by_text(request: SearchRequest):
    # Understand intent
    intent = understand_query_intent(request.query)

    # Generate embedding
    embedding = await clip_service.get_text_embedding(request.query)

    # Choose search strategy based on intent
    if intent['strategy'] == 'text':
        results = await vector_search_service.search_text(embedding)
    elif intent['strategy'] == 'image':
        results = await vector_search_service.search_image(embedding)
    else:  # hybrid
        results = await vector_search_service.search_hybrid(embedding)

    # Apply attribute filters if detected
    if intent['attributes'].get('color'):
        filters = {'base_color': intent['attributes']['color']}
        results = [r for r in results if r['base_color'] == filters['base_color']]

    return results
```

**Benefit**: Smarter routing to appropriate search method

**Effort**: Medium (needs intent classification logic)

---

### Long-Term Improvements (2-4 weeks)

#### 8. **Fine-tune CLIP on Fashion Domain**

**Goal**: Adapt CLIP to understand fashion-specific concepts better.

**Current**: Using generic CLIP ViT-B/32 trained on general images

**Problem**: CLIP doesn't understand:
- Fashion-specific terms ("boyfriend jeans", "peplum top", "A-line dress")
- Material textures in images ("silk" vs "cotton" appearance)
- Fit and silhouette nuances ("slim fit" vs "regular fit")

**Approach**:
```python
# 1. Create fashion-specific training dataset
# - Image-text pairs from your catalog
# - Add human annotations for difficult cases
# - Include fashion-specific attributes

# 2. Fine-tune CLIP using contrastive loss
# Option A: Use Databricks Foundation Model Training
# Option B: Use existing fine-tuning libraries (OpenCLIP, etc.)

# 3. Register fine-tuned model in Unity Catalog
# 4. Deploy to Model Serving
# 5. Update endpoints in config.py
```

**Dataset Creation**:
```sql
-- Create training dataset with rich descriptions
CREATE OR REPLACE TABLE main.fashion_demo.clip_training_data AS
SELECT
  product_id,
  image_path,
  CONCAT(
    product_display_name, ' ',
    article_type, ' ',
    base_color, ' color ',
    CASE
      WHEN price < 30 THEN 'affordable budget '
      WHEN price > 100 THEN 'luxury premium designer '
      ELSE 'mid-range '
    END,
    gender, ' ',
    season, ' season ',
    usage, ' wear ',
    master_category, ' ',
    sub_category
  ) as rich_description
FROM main.fashion_demo.products
WHERE image_path IS NOT NULL;
```

**Benefits**:
- Much better understanding of fashion domain
- Higher quality embeddings → better differentiation
- Wider score ranges (easier to rank meaningfully)

**Effort**: High (needs ML expertise, compute resources, eval dataset)

**ROI**: Very high if you have resources

---

#### 9. **Implement Learning-to-Rank (LTR)**

**Goal**: Learn optimal ranking from user behavior.

**Current**: Fixed weights (60% vector + 40% rules)

**Proposed**: Train a ranking model on user interactions

**Implementation**:
```python
# 1. Collect training data
# - Search query
# - Retrieved products (with features)
# - User clicks, add-to-cart, purchases (labels)

# 2. Extract features for each product
def extract_ranking_features(product, query, user_id):
    return {
        # Vector Search features
        'vector_similarity': product['score'],

        # Query-product match features
        'query_product_name_match': jaccard_similarity(query, product['product_display_name']),
        'query_category_match': query.lower() in product['master_category'].lower(),

        # Product popularity features
        'click_rate': get_click_rate(product['product_id']),
        'conversion_rate': get_conversion_rate(product['product_id']),
        'avg_rating': get_avg_rating(product['product_id']),

        # User-product match features
        'user_category_affinity': user_category_score(user_id, product['master_category']),
        'user_price_match': price_match_score(user_id, product['price']),
        'user_color_match': product['base_color'] in get_user_colors(user_id),

        # Business features
        'margin': get_margin(product['product_id']),
        'stock_level': get_stock_level(product['product_id']),
        'is_new_arrival': product['year'] == 2018,
        'is_on_sale': check_if_on_sale(product['product_id']),
    }

# 3. Train ranking model (LightGBM or XGBoost)
from lightgbm import LGBMRanker

ranker = LGBMRanker(
    objective='lambdarank',
    metric='ndcg',
    n_estimators=100
)

ranker.fit(
    X_train,  # Features
    y_train,  # Labels (clicks=1, no-click=0, purchase=2)
    group=query_groups  # Group by query
)

# 4. Use in production
def rerank_with_ltr(products, query, user_id):
    features = [
        extract_ranking_features(p, query, user_id)
        for p in products
    ]

    scores = ranker.predict(features)

    # Re-sort by LTR scores
    ranked_products = sorted(
        zip(products, scores),
        key=lambda x: x[1],
        reverse=True
    )

    return [p for p, _ in ranked_products]
```

**Benefits**:
- Learns from actual user behavior
- Automatically balances multiple signals
- Adapts over time as behavior changes

**Effort**: High (needs logging infrastructure, training pipeline, monitoring)

**ROI**: Very high for mature products with traffic

---

#### 10. **Add Collaborative Filtering Signals**

**Goal**: "Users who liked X also liked Y"

**Current**: Only using content-based (embeddings) + rules

**Proposed**: Add collaborative signals

**Implementation**:
```python
# 1. Build user-item interaction matrix
user_interactions = spark.sql("""
  SELECT
    user_id,
    product_id,
    COUNT(*) as num_interactions,
    SUM(CASE WHEN action = 'purchase' THEN 3
             WHEN action = 'add_to_cart' THEN 2
             WHEN action = 'view' THEN 1
             ELSE 0 END) as interaction_score
  FROM main.fashion_demo.user_interactions
  GROUP BY user_id, product_id
""")

# 2. Train matrix factorization model (ALS)
from pyspark.ml.recommendation import ALS

als = ALS(
    userCol="user_id",
    itemCol="product_id",
    ratingCol="interaction_score",
    coldStartStrategy="drop",
    rank=50,
    maxIter=10
)

model = als.fit(user_interactions)

# 3. Generate collaborative recommendations
cf_recs = model.recommendForAllUsers(numItems=50)

# 4. Combine with content-based
def hybrid_recommendations(user_id, query=None):
    # Get collaborative filtering recs
    cf_items = get_cf_recommendations(user_id, n=50)

    # Get content-based recs (Vector Search)
    if query:
        embedding = clip_service.get_text_embedding(query)
    else:
        embedding = get_user_embedding(user_id)

    cb_items = vector_search_service.search_hybrid(embedding, num_results=50)

    # Merge: 50% CF + 50% CB
    return merge_results_rrf(
        [cf_items, cb_items],
        weights=[0.5, 0.5]
    )
```

**Benefits**:
- Discovers unexpected but relevant items
- Works even when product descriptions are poor
- Captures implicit preferences

**Effort**: High (needs interaction data, training infrastructure)

---

## Quick Diagnostic Tests

Before implementing improvements, run these tests to understand current quality:

### Test 1: Query Diversity Analysis
```python
# Test how different queries perform
test_queries = [
    "red dress",
    "professional office wear",
    "cozy winter sweater",
    "athletic performance shoes",
    "luxury designer handbag",
    "casual weekend outfit",
]

for query in test_queries:
    results = await search_by_text(query, limit=10)

    # Analyze diversity
    unique_categories = len(set(r['master_category'] for r in results))
    unique_colors = len(set(r['base_color'] for r in results))
    score_range = max(r['score'] for r in results) - min(r['score'] for r in results)

    print(f"\nQuery: '{query}'")
    print(f"  Unique categories: {unique_categories}/10")
    print(f"  Unique colors: {unique_colors}/10")
    print(f"  Score range: {score_range:.4f}")
```

### Test 2: User Preference Coverage
```python
# Test if user preferences are too broad
for persona in personas:
    user_id = persona['user_id']

    # Get recommendations
    recs = await get_recommendations(user_id, limit=20)

    # Check diversity
    category_dist = Counter(r['master_category'] for r in recs)
    color_dist = Counter(r['base_color'] for r in recs)

    print(f"\nUser: {persona['name']}")
    print(f"  Category distribution: {dict(category_dist)}")
    print(f"  Color distribution: {dict(color_dist)}")
    print(f"  Are results too homogeneous? {len(category_dist) <= 2}")
```

### Test 3: Embedding Quality Check
```python
# Check if embeddings differentiate well
random_products = sample(all_products, 100)

# Compute pairwise similarities
similarities = []
for i, p1 in enumerate(random_products):
    for j, p2 in enumerate(random_products[i+1:], i+1):
        # Get embeddings from index
        emb1 = get_product_embedding(p1['product_id'])
        emb2 = get_product_embedding(p2['product_id'])

        sim = cosine_similarity(emb1, emb2)
        similarities.append({
            'product1': p1['product_display_name'],
            'product2': p2['product_display_name'],
            'similarity': sim,
            'same_category': p1['master_category'] == p2['master_category']
        })

# Analyze
same_cat_sims = [s['similarity'] for s in similarities if s['same_category']]
diff_cat_sims = [s['similarity'] for s in similarities if not s['same_category']]

print(f"Same category avg similarity: {np.mean(same_cat_sims):.3f}")
print(f"Different category avg similarity: {np.mean(diff_cat_sims):.3f}")
print(f"Separation: {np.mean(same_cat_sims) - np.mean(diff_cat_sims):.3f}")
# Want separation > 0.1 for good differentiation
```

---

## Recommended Action Plan

### Phase 1: Quick Wins (This Week)
1. **Enrich text descriptions** with inferred attributes (1 day)
2. **Add query expansion** with synonyms (0.5 day)
3. **Implement diversity** in results (MMR) (1 day)
4. **Add re-ranking** with business rules (0.5 day)

**Expected Impact**: +15-20% improvement in relevance

---

### Phase 2: Medium-Term (Next 2 Weeks)
5. **Weighted hybrid search** combining multiple signals (3 days)
6. **Negative filtering** for personalization (2 days)
7. **Query intent understanding** (3 days)

**Expected Impact**: +20-30% improvement in relevance

---

### Phase 3: Long-Term (Next Month)
8. **Fine-tune CLIP** on fashion domain (1-2 weeks)
9. **Learning-to-Rank** from user interactions (1 week)
10. **Collaborative filtering** integration (1 week)

**Expected Impact**: +40-50% improvement in relevance

---

## Monitoring & Evaluation

### Metrics to Track
1. **Relevance Metrics**:
   - Click-through rate (CTR) on search results
   - Time to first click
   - Bounce rate after search

2. **Diversity Metrics**:
   - Unique categories in top 10
   - Unique colors in top 10
   - Intra-list similarity (avg pairwise distance)

3. **Business Metrics**:
   - Add-to-cart rate from search
   - Conversion rate from search
   - Average order value (AOV)

4. **Technical Metrics**:
   - Search latency (p50, p95, p99)
   - Score distribution (min, max, std)
   - Embedding quality (separation)

### A/B Testing Framework
```python
# Implement variant routing
def get_search_variant(user_id: str) -> str:
    """Route users to different search variants"""
    hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    variant_id = hash_value % 100

    if variant_id < 50:
        return "control"  # Baseline
    else:
        return "treatment"  # New algorithm

# Log results for analysis
def log_search_event(user_id, query, variant, results, interactions):
    event = {
        'timestamp': datetime.now(),
        'user_id': user_id,
        'query': query,
        'variant': variant,
        'results_shown': [r['product_id'] for r in results],
        'clicks': interactions['clicks'],
        'add_to_carts': interactions['add_to_carts'],
        'purchases': interactions['purchases']
    }
    spark.createDataFrame([event]).write.mode("append").saveAsTable(
        "main.fashion_demo.search_events"
    )
```

---

## Summary

Your current system has a solid foundation with CLIP + Vector Search, but there's significant room for improvement:

**Biggest Opportunities**:
1. 🎯 **Enrich text descriptions** - Biggest bang for buck
2. 🎯 **Add diversity to results** - Improves user experience immediately
3. 🎯 **Implement weighted hybrid search** - Better quality through signal combination
4. 🎯 **Fine-tune CLIP** - Long-term investment for domain adaptation

**Start With**: Phase 1 quick wins (1 week effort, 15-20% improvement expected)

**Measure**: CTR, diversity, conversion rate before/after each change

Want to start with any specific improvement? I can help implement it!
