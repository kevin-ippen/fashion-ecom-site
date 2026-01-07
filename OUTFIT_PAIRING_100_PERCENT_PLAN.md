# Plan: Achieve 100% Outfit Pairing Coverage

## Current State

**Coverage Gap Analysis**:
- **Total products**: 44,424
- **Products with pairings**: 1,086 (2.4%)
- **Products WITHOUT pairings**: 43,338 (97.6%)
- **Existing pairs**: 64,190 pairs from lookbook analysis

**Top Unpaired Categories**:
1. Apparel / Topwear: 15,067 products
2. Footwear / Shoes: 7,290 products
3. Accessories / Bags: 3,031 products
4. Accessories / Watches: 2,537 products
5. Apparel / Bottomwear: 2,517 products

**Problem**: Only 1,086 products from the 29 lookbook images have matches in our catalog. We need to generate ~43,000 products worth of pairings.

---

## Solution: Hybrid GenAI + Rule-Based Pairing

### Approach Overview

**3-Tier Strategy**:
1. **Tier 1 (Best)**: Existing lookbook pairs (1,086 products) ✅
2. **Tier 2 (Good)**: GenAI-powered batch pairing (targeted categories)
3. **Tier 3 (Fallback)**: Rule-based algorithmic pairing (remaining products)

---

## Tier 2: GenAI Batch Pairing (Recommended)

### Model Selection: **Llama 3.1 70B** (via Databricks Foundation Model serving)

**Why Llama 3.1 70B**:
- ✅ Cost-effective ($0.001/1K tokens - ~$50 for entire dataset)
- ✅ Fast (provisioned throughput endpoints)
- ✅ Smart enough for outfit logic
- ✅ Already available in Databricks
- ✅ Can process 500-1000 products in parallel batches

**Alternative**: Claude Haiku via Bedrock ($0.25/1M tokens - even cheaper but requires AWS integration)

### Process Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. Extract Unpaired Products (43,338)                     │
│     - Group by category + gender                           │
│     - Batch into chunks of 100 products                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Create Context Catalog                                  │
│     - For each product, build "pairable candidates" list   │
│     - Filter by OutfitCompatibilityService rules           │
│     - Result: ~500-1000 candidates per product             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. GenAI Batch Processing (Llama 3.1 70B)                 │
│     - Input: Source product + candidate list               │
│     - Prompt: "Select 3-5 products that would pair well"  │
│     - Output: Ranked list of product IDs with scores      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Validate & Write to Table                               │
│     - Apply compatibility filters (double-check)           │
│     - Write to outfit_recommendations_synthetic table      │
│     - Union with lookbook pairs for queries                │
└─────────────────────────────────────────────────────────────┘
```

### Prompt Engineering

**System Prompt**:
```
You are a professional fashion stylist. Given a product and a list of candidates,
select 3-5 items that would pair well to create a complete, stylish outfit.

Consider:
- Color harmony (neutrals go with everything, avoid clashing combinations)
- Category compatibility (top + bottom + shoes + 1-2 accessories)
- Season appropriateness (winter items with winter items)
- Gender consistency (men's with men's, women's with women's)
- Usage context (casual with casual, formal with formal)
- Price point balance (don't mix very cheap with very expensive)
```

**Example Prompt** (for a Men's Blue Topwear):
```
Source Product:
- ID: 12345
- Name: "Roadster Men Blue Denim Shirt"
- Category: Apparel / Topwear
- Color: Blue
- Gender: Men
- Season: Summer
- Usage: Casual
- Price: $29.99

Candidate Products (select 3-5 that pair well):
1. [15678] U.S. Polo Assn. Men Navy Chinos (Bottomwear, Navy, $39.99, Casual)
2. [23456] Peter England Men Black Formal Trousers (Bottomwear, Black, $49.99, Formal)
3. [34567] Puma Men White Sneakers (Footwear/Shoes, White, $69.99, Casual)
4. [45678] Fossil Men Brown Leather Wallet (Accessories/Wallets, Brown, $39.99, Casual)
5. [56789] Titan Men Black Analog Watch (Accessories/Watches, Black, $129.99, Casual)
... (500 more candidates)

Response Format (JSON):
{
  "selected_pairs": [
    {"product_id": 15678, "score": 0.95, "reason": "Navy chinos complement blue denim for casual outfit"},
    {"product_id": 34567, "score": 0.90, "reason": "White sneakers complete the casual summer look"},
    {"product_id": 45678, "score": 0.75, "reason": "Brown leather adds warm accent"},
    {"product_id": 56789, "score": 0.70, "reason": "Black watch adds sophistication"}
  ]
}
```

### Implementation Steps

**Phase 1: Build Infrastructure** (2-3 hours)
1. ✅ Create `OutfitCompatibilityService` (DONE)
2. Create `GenAIPairingService` class
3. Set up Llama 3.1 70B endpoint (or use existing)
4. Create UC table: `main.fashion_sota.outfit_recommendations_synthetic`

**Phase 2: Generate Candidate Lists** (1 hour compute)
1. For each unpaired product, query compatible candidates
2. Apply OutfitCompatibilityService filters
3. Store in intermediate table with 500-1000 candidates per product

**Phase 3: Batch GenAI Processing** (4-6 hours compute)
1. Process in batches of 100 products
2. Call Llama 3.1 70B for each product
3. Parse JSON responses
4. Validate outputs
5. Write to synthetic pairings table
6. Checkpoint progress (resume on failure)

**Phase 4: Merge & Deploy** (30 mins)
1. Create unified view:
   ```sql
   CREATE VIEW outfit_recommendations_all AS
   SELECT *, 'lookbook' as source FROM outfit_recommendations_filtered
   UNION ALL
   SELECT *, 'synthetic' as source FROM outfit_recommendations_synthetic
   ```
2. Update API to query unified view
3. Test coverage = 100%

### Cost Estimation

**Llama 3.1 70B Pricing**: ~$0.001/1K tokens

**Token Usage**:
- Per product: ~1,500 tokens (500 input + 1000 candidates summary)
- Total: 43,338 products × 1,500 tokens = 65M tokens
- **Total cost**: $65 (very affordable!)

**Compute Time**:
- Throughput: ~100 products/minute (with batching)
- Total time: ~7 hours

---

## Tier 3: Rule-Based Algorithmic Pairing (Fallback)

If GenAI fails or takes too long, use deterministic rules:

### Algorithm

```python
def generate_rule_based_pairings(source_product):
    """
    Generate 3-5 outfit pairings using similarity + compatibility rules
    """
    candidates = []

    # 1. Get products that pass compatibility filters
    compatible = filter_by_compatibility_rules(source_product)

    # 2. Score each candidate
    for candidate in compatible:
        score = 0.0

        # Same gender: +30 points
        if candidate.gender == source_product.gender:
            score += 0.30

        # Same season: +20 points
        if candidate.season == source_product.season:
            score += 0.20

        # Same usage: +20 points
        if candidate.usage == source_product.usage:
            score += 0.20

        # Color compatibility: +15 points
        if is_color_compatible(source_product.color, candidate.color):
            score += 0.15

        # Category pairing strength: +15 points
        score += get_category_pairing_strength(source_product.category, candidate.category)

        candidates.append((candidate, score))

    # 3. Sort by score and return top 3-5
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:5]
```

**Pros**: Deterministic, no LLM cost, fast
**Cons**: Less intelligent than GenAI, may produce mediocre pairs

---

## Recommended Implementation Plan

### **Option A: GenAI-First (RECOMMENDED)**

**Timeline**: 1-2 days development + 7 hours compute

**Steps**:
1. Build GenAIPairingService (use Llama 3.1 70B)
2. Process high-priority categories first:
   - Apparel / Topwear (15,067)
   - Footwear / Shoes (7,290)
   - Apparel / Bottomwear (2,517)
3. Use rule-based fallback for accessories/personal care
4. Merge into unified view
5. Deploy to production

**Benefits**:
- High-quality, intelligent pairings
- Can explain recommendations ("Complete the casual look")
- Only $65 cost
- 100% coverage guaranteed

### **Option B: Rule-Based Only (FASTER)**

**Timeline**: 4-6 hours development + 1 hour compute

**Steps**:
1. Extend OutfitCompatibilityService with scoring
2. Batch process all 43,338 products
3. Generate top 5 pairs per product
4. Deploy

**Benefits**:
- No LLM dependency
- Very fast
- Free (compute only)

**Tradeoffs**:
- Lower quality pairings
- Less explainable
- May still have some bad matches

---

## Recommendation

**Go with Option A (GenAI-First)** because:

1. **Cost is negligible**: $65 for entire dataset
2. **Quality matters**: Users will notice bad outfit suggestions
3. **Explainability**: Can show "why" items pair well
4. **Scale**: Llama 3.1 70B can handle this easily
5. **Timeline**: 1-2 days is acceptable for 100% coverage

**Next Steps**:
1. ✅ Approve plan
2. Create `GenAIPairingService` implementation
3. Set up Llama 3.1 70B endpoint
4. Create synthetic pairings table
5. Run batch processing job
6. Test and deploy

---

## Monitoring & Quality Control

**During Processing**:
- Log pairing scores for each product
- Sample 100 random pairings for manual review
- Track category distribution (ensure diversity)
- Monitor for duplicate pairs

**Post-Deployment**:
- A/B test lookbook vs synthetic pairings
- Track click-through rates on recommendations
- Monitor "Complete the Look" section views
- Collect user feedback

**Quality Thresholds**:
- Min pairing score: 0.60 (60% confidence)
- Max same-category pairs: 1 per outfit
- Color clash rate: <5%
- User engagement lift: +10% target

---

## Files to Create

1. `/services/genai_pairing_service.py` - GenAI pairing logic
2. `/notebooks/generate_synthetic_pairings.py` - Batch processing script
3. `/notebooks/evaluate_pairing_quality.py` - Quality validation
4. SQL migration for `outfit_recommendations_synthetic` table

---

**Status**: 📋 **Plan Ready - Awaiting Approval**

**Estimated Total Time**: 1-2 days development + 7 hours compute
**Estimated Total Cost**: $65 (Llama 3.1 70B) + compute (~$20)
**Expected Coverage**: 100% (44,424 products)
