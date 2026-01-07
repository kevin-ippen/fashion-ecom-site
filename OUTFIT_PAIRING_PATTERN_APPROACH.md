# Outfit Pairing: Pattern-Based Approach (Revised)

## Problem
- Current coverage: 2.4% (1,086 products)
- After lookbook matching: ~48% (21,326 products)
- Remaining gap: ~23,000 products (52%)

## Insight
**Similar products should have similar outfit patterns!**

A blue men's denim shirt can use the same pairing patterns as other casual men's tops:
- Pattern: Casual top → Chinos/Jeans + Sneakers + Watch
- Apply to: All casual men's topwear

This means we DON'T need to process 23,000 products individually!

---

## Revised Strategy: Pattern-Based Pairing

### Phase 1: Select 100-200 Representative Products

Use **stratified sampling + clustering** to pick "anchor" products that represent the diversity of our catalog.

**Selection Criteria**:
```
Dimensions:
- Category/Subcategory (Topwear, Bottomwear, Shoes, etc.)
- Gender (Men, Women, Unisex)
- Color family (Neutral, Warm, Cool, Bright)
- Price tier (Budget <$30, Mid $30-80, Premium $80+)
- Season (Summer, Winter, All-season)
- Usage (Casual, Formal, Sports, Party)

Result: ~100-200 anchor products covering all combinations
```

**Example Representatives**:
```
Anchor 1: Men's Blue Casual Cotton Shirt (Summer, Mid-price)
Anchor 2: Men's Black Formal Shirt (All-season, Premium)
Anchor 3: Women's Floral Dress (Summer, Budget)
Anchor 4: Men's Running Shoes (Sports, Mid-price)
... 196 more
```

**Implementation**:
```sql
-- Use k-means clustering on product features
WITH product_features AS (
  SELECT
    product_id,
    master_category,
    sub_category,
    gender,
    CASE
      WHEN base_color IN ('Black', 'White', 'Grey', 'Navy', 'Beige') THEN 'Neutral'
      WHEN base_color IN ('Red', 'Orange', 'Yellow', 'Pink') THEN 'Warm'
      WHEN base_color IN ('Blue', 'Green', 'Purple') THEN 'Cool'
      ELSE 'Bright'
    END as color_family,
    CASE
      WHEN price < 30 THEN 'Budget'
      WHEN price < 80 THEN 'Mid'
      ELSE 'Premium'
    END as price_tier,
    season,
    usage
  FROM main.fashion_sota.products_lakebase
  WHERE product_id NOT IN (
    -- Exclude products already paired
    SELECT DISTINCT product_id FROM paired_products_view
  )
),
clustered AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY master_category, sub_category, gender, color_family, price_tier, season, usage
      ORDER BY RANDOM()
    ) as rn
  FROM product_features
)
SELECT * FROM clustered
WHERE rn = 1  -- One representative per cluster
LIMIT 200
```

### Phase 2: Generate Outfit Patterns (GenAI)

For each anchor product, generate **5-10 reusable outfit patterns** using Llama 3.1 70B.

**Pattern Structure**:
```json
{
  "anchor_product": {
    "id": 12345,
    "name": "Roadster Men Blue Denim Shirt",
    "category": "Apparel/Topwear",
    "attributes": {"color": "Blue", "style": "Casual", "season": "Summer"}
  },
  "patterns": [
    {
      "pattern_id": "P1",
      "name": "Classic Casual",
      "items": [
        {
          "role": "bottom",
          "required": true,
          "category": "Apparel/Bottomwear",
          "subcategory": ["Jeans", "Chinos"],
          "colors": ["Navy", "Black", "Khaki"],
          "style": "Casual"
        },
        {
          "role": "footwear",
          "required": true,
          "category": "Footwear/Shoes",
          "subcategory": ["Sneakers", "Casual Shoes"],
          "colors": ["White", "Black", "Brown"],
          "style": "Casual"
        },
        {
          "role": "accessory",
          "required": false,
          "category": "Accessories/Watches",
          "colors": ["Silver", "Black"],
          "style": "Casual"
        }
      ],
      "confidence": 0.95
    },
    {
      "pattern_id": "P2",
      "name": "Summer Smart Casual",
      "items": [...]
    },
    // ... 3-8 more patterns
  ]
}
```

**GenAI Prompt**:
```
You are a professional fashion stylist. Generate 5 reusable outfit patterns for this product:

Product: Roadster Men Blue Denim Shirt
- Category: Apparel / Topwear
- Color: Blue
- Style: Casual
- Season: Summer
- Gender: Men
- Price: $29.99

For each pattern, specify what types of products would pair well (NOT specific product IDs).
Define:
- Required items (bottom, footwear)
- Optional items (accessories)
- Compatible categories, subcategories, colors, styles

Output JSON format: [see above]

Focus on patterns that would work for ANY blue casual men's shirt, not just this one.
```

**Cost**: 200 products × $0.002 per call = **$0.40** (negligible!)

### Phase 3: Apply Patterns to Similar Products

For each unpaired product, find its nearest anchor and apply patterns.

**Pattern Matching Algorithm**:
```python
def find_outfit_recommendations(target_product):
    """
    Apply outfit patterns from similar anchor products
    """
    # 1. Find 3 nearest anchor products
    anchors = find_similar_anchors(
        target_product,
        dimensions=['category', 'color_family', 'gender', 'usage'],
        top_k=3
    )

    # 2. Collect all patterns from anchors (weighted by similarity)
    patterns = []
    for anchor, similarity in anchors:
        for pattern in anchor.patterns:
            patterns.append({
                'pattern': pattern,
                'weight': similarity * pattern.confidence
            })

    # 3. Sort patterns by weight, take top 3-5
    patterns.sort(key=lambda x: x['weight'], reverse=True)
    selected_patterns = patterns[:5]

    # 4. For each pattern, find matching products in catalog
    recommendations = []
    for pattern_info in selected_patterns:
        pattern = pattern_info['pattern']

        for item_spec in pattern.items:
            # Query catalog for products matching specification
            matches = query_products(
                category=item_spec.category,
                subcategory=item_spec.subcategory,
                colors=item_spec.colors,
                style=item_spec.style,
                gender=target_product.gender,
                limit=10
            )

            # Add color compatibility filtering
            matches = filter_color_compatible(
                matches,
                source_color=target_product.color
            )

            # Add diversity (max 1 item per pattern)
            if matches:
                recommendations.append(matches[0])

    # 5. Deduplicate and diversify
    recommendations = deduplicate(recommendations)
    recommendations = diversify_by_category(recommendations, max_per_category=2)

    return recommendations[:4]
```

**Similarity Matching**:
```sql
-- Option 1: Metadata-based (fast, deterministic)
SELECT anchor_id, SUM(score) as similarity
FROM (
  SELECT anchor_id,
    CASE WHEN a.master_category = t.master_category THEN 10 ELSE 0 END +
    CASE WHEN a.sub_category = t.sub_category THEN 20 ELSE 0 END +
    CASE WHEN a.color_family = t.color_family THEN 15 ELSE 0 END +
    CASE WHEN a.gender = t.gender THEN 10 ELSE 0 END +
    CASE WHEN a.usage = t.usage THEN 15 ELSE 0 END as score
  FROM anchor_products a
  CROSS JOIN target_product t
)
GROUP BY anchor_id
ORDER BY similarity DESC
LIMIT 3

-- Option 2: Embedding-based (more accurate, uses FashionCLIP)
SELECT anchor_id, cosine_similarity(anchor_embedding, target_embedding) as similarity
FROM anchor_embeddings
ORDER BY similarity DESC
LIMIT 3
```

### Phase 4: Diversity & Randomization

Add controlled randomness to avoid repetitive recommendations.

**Diversity Mechanisms**:

1. **Pattern Rotation**: Don't always use top pattern
   ```python
   # Instead of always taking pattern[0], rotate
   pattern_idx = (target_product.id % len(patterns))
   selected_pattern = sorted_patterns[pattern_idx]
   ```

2. **Color Variation**: Allow slight color deviations
   ```python
   # If pattern says "Navy", also consider "Dark Blue", "Indigo"
   color_variations = expand_color_palette(pattern.colors)
   ```

3. **Random Sampling**: Pick random items from matches
   ```python
   # Instead of always picking matches[0]
   if len(matches) > 1:
       selected = random.choice(matches[:3])  # Top 3 candidates
   ```

4. **Category Diversity**: Ensure variety
   ```python
   # Max 2 items from same category in one recommendation set
   recommendations = diversify_by_category(recommendations, max_per_category=2)
   ```

---

## Implementation Plan

### Step 1: Select Anchors (2 hours)
```python
# notebook: select_anchor_products.py
- Run clustering query
- Export ~200 anchor products
- Store in: main.fashion_sota.outfit_pattern_anchors
```

### Step 2: Generate Patterns (1 hour compute, $0.40 cost)
```python
# notebook: generate_outfit_patterns.py
- Call Llama 3.1 70B for each anchor
- Parse JSON patterns
- Store in: main.fashion_sota.outfit_patterns
- Schema: (anchor_id, pattern_json, confidence)
```

### Step 3: Build Pattern Application Service (3 hours dev)
```python
# services/pattern_pairing_service.py
class PatternPairingService:
    def get_recommendations(self, product_id):
        # Find similar anchors
        # Apply patterns
        # Query matching products
        # Diversify
        # Return top 4
```

### Step 4: Batch Process Remaining Products (2 hours compute)
```python
# notebook: apply_patterns_batch.py
- For all unpaired products
- Apply pattern matching
- Write to: main.fashion_sota.outfit_recommendations_pattern_based
```

### Step 5: Create Final Unified View (10 mins)
```sql
CREATE VIEW main.fashion_sota.outfit_recommendations_final AS

-- Tier 1: High-confidence lookbook pairs
SELECT *, 'lookbook_curated' as source, 1.0 as confidence
FROM main.fashion_sota.outfit_recommendations_filtered

UNION ALL

-- Tier 2: Algorithmic lookbook pairs
SELECT *, 'lookbook_algorithmic' as source, 0.8 as confidence
FROM main.fashion_sota.outfit_recommendations_from_lookbook

UNION ALL

-- Tier 3: Pattern-based pairs
SELECT *, 'pattern_based' as source, 0.7 as confidence
FROM main.fashion_sota.outfit_recommendations_pattern_based
```

### Step 6: Update API & Deploy (30 mins)
```python
# routes/v1/products.py
# Change query from outfit_recommendations_filtered
# to outfit_recommendations_final
```

---

## Expected Outcomes

**Coverage**:
- Lookbook (existing): 1,086 products (2.4%)
- Lookbook (algorithmic): ~21,326 products (48%)
- Pattern-based: ~23,000 products (52%)
- **Total: 100% coverage** ✅

**Quality Tiers**:
- Tier 1 (Lookbook curated): Very high quality, manually verified
- Tier 2 (Lookbook algorithmic): High quality, co-occurrence based
- Tier 3 (Pattern-based): Good quality, rule + GenAI hybrid

**Cost**:
- Anchor selection: Free (SQL query)
- Pattern generation: $0.40 (200 products × $0.002)
- Pattern application: Free (deterministic matching)
- **Total: $0.40** (vs $35-65 for direct GenAI) 🎉

**Timeline**:
- Day 1: Select anchors + generate patterns (3 hours)
- Day 2: Build service + batch process (5 hours)
- Day 3: Test + deploy (2 hours)
- **Total: ~10 hours over 2-3 days**

**Maintenance**:
- Re-run anchor selection quarterly (catalog changes)
- Regenerate patterns for new anchors
- No per-product GenAI calls needed!

---

## Quality Control

**Pattern Validation**:
```python
# After generating patterns, validate:
1. Each pattern has 2-4 items
2. Required items (bottom, footwear) are present
3. Color combinations don't clash
4. Categories are compatible
5. Confidence scores are reasonable (0.5-1.0)
```

**Sample Testing**:
```python
# Test pattern application on 100 random products
for product in test_sample:
    recommendations = pattern_service.get_recommendations(product.id)

    # Validate:
    assert len(recommendations) == 4
    assert no_duplicates(recommendations)
    assert category_diversity(recommendations)
    assert color_compatible(product, recommendations)

    # Manual review sample
    if random() < 0.1:
        print(f"Product: {product.name}")
        print(f"Recommendations: {recommendations}")
        input("Looks good? (y/n)")
```

**A/B Testing**:
```python
# In production, split traffic:
- 50% users: outfit_recommendations_filtered (old)
- 50% users: outfit_recommendations_final (new)

# Compare metrics:
- Click-through rate on recommendations
- Add-to-cart rate
- "Complete the Look" section views
- User engagement time on product pages
```

---

## Advantages of Pattern Approach

✅ **Scalable**: Works for any catalog size
✅ **Maintainable**: Re-run anchor selection when catalog changes
✅ **Cost-effective**: $0.40 vs $35-65
✅ **Fast**: 3 hours vs 7+ hours
✅ **Explainable**: "Based on classic casual outfit pattern"
✅ **Quality**: Combines human curation + GenAI intelligence + algorithmic matching
✅ **Flexible**: Easy to tweak patterns without reprocessing everything

---

## Next Steps

1. ✅ **Approve approach**
2. Select anchor products (run clustering query)
3. Generate outfit patterns (call Llama 3.1 70B)
4. Build PatternPairingService
5. Batch process remaining products
6. Test quality on sample
7. Deploy to production

**Ready to proceed with Phase 1: Anchor Selection?**
