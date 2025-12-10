# SmolVLM-2.2B Attribute Extraction Plan

## Dataset Understanding

### What We Have (Structured Data)

**Product Count**: 44,424 products

**Existing Attributes**:
```python
{
  # Identifiers
  'product_id': 15970,
  'product_display_name': "Puma Men Slick 3HD Yellow Black Watches",

  # Taxonomy (Good!)
  'master_category': "Accessories",        # 7 unique values
  'sub_category': "Watches",               # 45 unique values
  'article_type': "Watches",               # 143 unique values

  # Visual Attributes (Basic)
  'base_color': "Yellow",                  # 46 unique values

  # Context (Limited)
  'gender': "Men",                         # Men, Women, Boys, Girls, Unisex
  'season': "Summer",                      # Summer, Winter, Fall, Spring
  'usage': "Casual",                       # Casual, Formal, Sports
  'year': 2012,                            # 2011-2018

  # Business
  'price': 3246.0,
  'image_path': "/Volumes/main/fashion_demo/raw_data/images/15970.jpg"
}
```

### What We're Missing (Can Extract from Images!)

**Critical Gaps**:
- ❌ **Material**: leather, cotton, denim, silk, polyester, wool, canvas
- ❌ **Pattern**: solid, striped, floral, geometric, plaid, polka dot
- ❌ **Fit/Silhouette**: slim, regular, oversized, fitted, loose, tailored
- ❌ **Details**: pockets, buttons, zippers, collar types, sleeve length
- ❌ **Texture**: smooth, rough, shiny, matte, ribbed, woven
- ❌ **Style Descriptors**: vintage, modern, minimalist, bohemian, sporty
- ❌ **Formality Granularity**: "Casual" is too broad (athletic casual vs smart casual)
- ❌ **Occasion Specificity**: office, gym, party, date, outdoor, beach

---

## SmolVLM-2.2B Capabilities

### Model Specifications

- **Size**: 2.2B parameters
- **Architecture**: Vision-Language Model (multimodal)
- **Input**: Image + Text (prompt)
- **Output**: Natural language text
- **Strengths**: Fast inference, efficient, good at basic visual understanding
- **Limitations**: Smaller than GPT-4V/Claude/Llama-Vision, less nuanced

### What SmolVLM Can Realistically Do

#### ✅ **High Confidence (90%+ accuracy)**:
1. **Basic Materials** - obvious visual textures
   - Leather (shiny, textured)
   - Denim (woven blue fabric)
   - Knit/Wool (textured, soft appearance)
   - Metal (watches, jewelry - shiny, reflective)

2. **Clear Patterns**
   - Solid color
   - Stripes (horizontal/vertical)
   - Floral prints
   - Geometric patterns
   - Polka dots

3. **Obvious Style Categories**
   - Athletic/Sporty (activewear appearance)
   - Formal (suits, dress shirts, ties)
   - Casual (t-shirts, jeans)
   - Vintage (older styling cues)

4. **Basic Details**
   - Collar types (crew neck, V-neck, polo collar)
   - Sleeve length (short, long, sleeveless)
   - Visible pockets
   - Buttons vs zipper

#### ⚠️ **Medium Confidence (70-80% accuracy)**:
5. **Fabric Textures** - requires inference
   - Cotton (can guess from weave, but not certain)
   - Synthetic vs natural (ambiguous)
   - Canvas (textured appearance)

6. **Fit/Silhouette** - depends on model/angle
   - Slim vs regular (only if model wearing it clearly)
   - Oversized (if visually obvious)
   - Note: Flat-lay images make this hard!

7. **Formality Level**
   - Business casual vs casual (subtle differences)
   - Semi-formal (requires context)

8. **Complex Patterns**
   - Plaid/checkered (similar to stripes)
   - Animal print (if distinctive)
   - Abstract patterns (harder to name)

#### ❌ **Low Confidence (<70% accuracy)**:
9. **Subtle Material Details**
   - Silk vs satin (visually similar)
   - Cotton blend percentages
   - Performance fabrics (unless labeled)
   - Cashmere vs wool (too similar)

10. **Fit on Flat-Lay Images**
    - Can't determine fit if product not worn
    - Most product photos are flat-lay!

11. **Occasion Specificity**
    - "Office appropriate" requires cultural context
    - "Date night" vs "party" (very subjective)

12. **Brand Quality Signals**
    - Premium vs budget (unless obvious stitching/details)

---

## Realistic Attribute Taxonomy

Based on SmolVLM capabilities, here's what we should extract:

### Tier 1: High Confidence Attributes (Extract Always)

```python
TIER_1_TAXONOMY = {
    "material_primary": [
        "leather", "denim", "knit fabric", "woven fabric",
        "synthetic", "metal", "canvas", "unknown"
    ],

    "pattern": [
        "solid color", "striped", "floral print", "geometric pattern",
        "polka dots", "checkered", "abstract print", "no clear pattern"
    ],

    "formality": [
        "formal", "business casual", "casual", "athletic"
    ],

    "collar_style": [
        "crew neck", "V-neck", "collar", "hooded", "turtleneck",
        "no collar", "other"
    ],

    "sleeve_length": [
        "short sleeve", "long sleeve", "sleeveless",
        "three-quarter sleeve", "not applicable"
    ]
}
```

### Tier 2: Medium Confidence Attributes (Extract with Caveat)

```python
TIER_2_TAXONOMY = {
    "style_keywords": [
        # Only extract if visually obvious
        "athletic", "sporty", "vintage", "modern", "minimalist",
        "bohemian", "streetwear", "professional"
    ],

    "visual_details": [
        # Only if clearly visible
        "has pockets", "has buttons", "has zipper",
        "has hood", "has drawstrings", "has logo"
    ],

    "fit_type": [
        # Only if model is wearing it clearly
        "fitted", "regular", "loose", "oversized",
        "cannot determine"  # Default for flat-lay
    ]
}
```

### Tier 3: Contextual Attributes (Infer from Tier 1+2)

```python
TIER_3_DERIVED = {
    "occasion": {
        # Derive from formality + style
        ("formal", "professional"): ["office", "business meeting", "formal event"],
        ("casual", "athletic"): ["gym", "sports", "active wear"],
        ("casual", "minimalist"): ["everyday", "weekend", "casual outing"],
        # ... more rules
    },

    "season_refined": {
        # Combine with existing 'season' field
        "short sleeve + light fabric": "summer appropriate",
        "long sleeve + heavy fabric": "winter appropriate",
    }
}
```

---

## Sample Product Analysis

Let's think through what SmolVLM would see for different product types:

### Example 1: "Puma Men Slick 3HD Yellow Black Watches"
**Category**: Accessories > Watches
**What SmolVLM Can Extract**:
- ✅ Material: "metal" (watch casing)
- ✅ Pattern: "solid color with yellow accents"
- ✅ Style: "sporty", "athletic brand"
- ❌ Fit: N/A (not applicable to watches)
- ❌ Occasion: Could infer "athletic", "casual wear"

**Rich Description**:
```
"Puma Men Slick 3HD Yellow Black Watches metal sporty athletic brand
casual wear yellow accents modern design"
```

### Example 2: Typical Shirt
**Category**: Apparel > Topwear > Shirts
**What SmolVLM Can Extract**:
- ✅ Material: "woven fabric" (can't tell if cotton specifically)
- ✅ Pattern: "checkered" or "solid"
- ✅ Collar: "collar" (dress shirt collar)
- ✅ Sleeve: "long sleeve"
- ✅ Formality: "formal" or "business casual"
- ⚠️ Fit: "cannot determine" (if flat-lay)
- ✅ Details: "has buttons"

**Rich Description**:
```
"Formal shirt woven checkered fabric long sleeve collar buttons
business casual office wear professional"
```

### Example 3: Casual T-Shirt
**Category**: Apparel > Topwear > Tshirts
**What SmolVLM Can Extract**:
- ✅ Material: "knit fabric" (t-shirt jersey)
- ✅ Pattern: "solid color"
- ✅ Collar: "crew neck"
- ✅ Sleeve: "short sleeve"
- ✅ Formality: "casual"
- ⚠️ Fit: "regular" (if clear) or "cannot determine"
- ❌ Material specificity: Can't tell if 100% cotton vs blend

**Rich Description**:
```
"Casual t-shirt knit fabric solid color crew neck short sleeve
everyday wear weekend casual comfortable"
```

### Example 4: Women's Dress
**Category**: Apparel > Apparel > Dresses
**What SmolVLM Can Extract**:
- ⚠️ Material: "woven fabric" (could be many things)
- ✅ Pattern: "floral print" or "solid"
- ✅ Sleeve: "sleeveless" or specific type
- ✅ Formality: "casual" to "formal" (depends on styling)
- ❌ Fit: Hard to tell silhouette without model
- ✅ Style: Could infer "bohemian" if floral, "elegant" if solid

**Rich Description**:
```
"Casual dress floral print sleeveless bohemian style
summer wear weekend party casual outing feminine"
```

---

## Prompt Engineering Strategy

### Principles for SmolVLM

1. **Be Specific, Not Broad**: Ask for concrete visual features, not subjective judgments
2. **Structured Output**: Request JSON for easy parsing
3. **Confidence Indicators**: Ask model to indicate certainty
4. **Fallback Values**: Always have "unknown"/"cannot determine" options
5. **One Category at a Time**: Don't overwhelm small model with too many attributes

### Recommended Prompts

#### Prompt Template 1: Material & Pattern (High Priority)
```python
PROMPT_MATERIAL_PATTERN = """Analyze this fashion product image.

Identify:
1. PRIMARY MATERIAL: What is the main material? Choose ONE:
   - leather (shiny, textured animal hide)
   - denim (blue woven cotton fabric)
   - knit fabric (stretchy, soft like t-shirt/sweater)
   - woven fabric (structured like dress shirt)
   - synthetic/athletic (performance fabric, shiny)
   - metal (jewelry, watches)
   - canvas (thick woven fabric)
   - unknown (cannot determine)

2. PATTERN: What pattern is visible? Choose ONE:
   - solid color (no pattern)
   - striped (lines/stripes)
   - floral print (flowers)
   - geometric (shapes/patterns)
   - polka dots (dots)
   - checkered/plaid (grid pattern)
   - abstract print (unclear pattern)
   - no clear pattern

3. CONFIDENCE: How confident are you? (high/medium/low)

Respond ONLY with JSON:
{
  "material": "...",
  "pattern": "...",
  "confidence": "..."
}
"""
```

#### Prompt Template 2: Style & Formality
```python
PROMPT_STYLE_FORMALITY = """Analyze this fashion product image.

Identify:
1. FORMALITY LEVEL: How formal is this item? Choose ONE:
   - formal (suits, gowns, very dressy)
   - business casual (office appropriate but not suit)
   - casual (everyday wear like t-shirts, jeans)
   - athletic (sportswear, activewear)

2. STYLE KEYWORDS: What style best describes it? Choose UP TO 3:
   - athletic/sporty
   - vintage/retro
   - modern/contemporary
   - minimalist/simple
   - bohemian/hippie
   - streetwear/urban
   - professional/corporate
   - elegant/sophisticated
   - none of these

3. VISIBLE DETAILS: What details can you see? List any that apply:
   - has pockets
   - has buttons
   - has zipper
   - has hood
   - has logo
   - has drawstrings
   - none clearly visible

Respond ONLY with JSON:
{
  "formality": "...",
  "style_keywords": ["...", "..."],
  "details": ["...", "..."]
}
"""
```

#### Prompt Template 3: Garment-Specific (if Apparel)
```python
PROMPT_GARMENT_DETAILS = """Analyze this clothing item image.

Identify:
1. COLLAR/NECKLINE: What type? Choose ONE:
   - crew neck (round, close to neck)
   - V-neck (V-shaped neckline)
   - collar (dress shirt collar)
   - hooded (has hood)
   - turtleneck (high collar)
   - scoop neck (low round)
   - no collar/not visible
   - not applicable

2. SLEEVE LENGTH: Choose ONE:
   - short sleeve
   - long sleeve
   - sleeveless
   - three-quarter sleeve
   - not applicable (not a top)

3. FIT (if person wearing it): Choose ONE:
   - fitted (tight, form-fitting)
   - regular (standard fit)
   - loose/relaxed
   - oversized (intentionally large)
   - cannot determine (flat-lay or unclear)

Respond ONLY with JSON:
{
  "collar": "...",
  "sleeves": "...",
  "fit": "..."
}
"""
```

### Multi-Stage Approach

**Why Multiple Prompts?**
- SmolVLM (2.2B) is small → easier to focus on one task at a time
- Reduces hallucination risk
- Allows confidence filtering per attribute
- Can skip irrelevant prompts (e.g., skip garment details for accessories)

**Execution Strategy**:
```python
async def extract_attributes_staged(image_bytes, article_type):
    """Extract attributes using multiple focused prompts"""

    # Stage 1: Always run (high priority)
    material_pattern = await query_smolvlm(image_bytes, PROMPT_MATERIAL_PATTERN)

    # Stage 2: Always run
    style_formality = await query_smolvlm(image_bytes, PROMPT_STYLE_FORMALITY)

    # Stage 3: Only if apparel (skip for accessories, footwear)
    garment_details = None
    if article_type in ["Topwear", "Bottomwear", "Dress", "Outerwear"]:
        garment_details = await query_smolvlm(image_bytes, PROMPT_GARMENT_DETAILS)

    # Combine results
    return {
        "material": material_pattern.get("material"),
        "pattern": material_pattern.get("pattern"),
        "formality": style_formality.get("formality"),
        "style_keywords": style_formality.get("style_keywords", []),
        "details": style_formality.get("details", []),
        "collar": garment_details.get("collar") if garment_details else None,
        "sleeves": garment_details.get("sleeves") if garment_details else None,
        "fit": garment_details.get("fit") if garment_details else "cannot determine",
        "confidence_material": material_pattern.get("confidence"),
    }
```

---

## Validation Strategy

### How Do We Know If It's Working?

#### 1. Manual Spot Checks
```python
# Test on diverse samples
test_cases = [
    ("leather jacket", {"material": "leather", "formality": "casual"}),
    ("formal shirt", {"formality": "formal", "collar": "collar"}),
    ("athletic t-shirt", {"formality": "athletic", "style_keywords": ["athletic"]}),
    ("floral dress", {"pattern": "floral print"}),
]

for product_name, expected in test_cases:
    extracted = extract_attributes(product)
    accuracy = compare(extracted, expected)
    print(f"{product_name}: {accuracy}% match")
```

#### 2. Cross-Validation with Existing Data
```python
# Use existing attributes to validate
# Example: If usage="Sports", expect formality="athletic"
# Example: If season="Summer", expect sleeves="short sleeve" or "sleeveless"

def validate_consistency(product, extracted_attrs):
    """Check if extracted attributes make sense with existing data"""
    issues = []

    # Check: Sports usage should be athletic formality
    if product['usage'] == 'Sports' and extracted_attrs['formality'] != 'athletic':
        issues.append("Usage=Sports but formality not athletic")

    # Check: Watches should be metal
    if product['article_type'] == 'Watches' and extracted_attrs['material'] != 'metal':
        issues.append("Watch but material not metal")

    # Check: Tshirts should be knit
    if product['article_type'] == 'Tshirts' and extracted_attrs['material'] != 'knit fabric':
        issues.append("T-shirt but material not knit")

    return issues
```

#### 3. Confidence Filtering
```python
# Only use extractions with high confidence
def filter_by_confidence(extracted_attrs):
    """Only keep attributes where model was confident"""
    filtered = {}

    if extracted_attrs.get('confidence_material') in ['high', 'medium']:
        filtered['material'] = extracted_attrs['material']

    # Always keep pattern (usually high accuracy)
    filtered['pattern'] = extracted_attrs['pattern']

    return filtered
```

#### 4. Aggregate Statistics
```python
# After processing 100 products:
# - What % have "unknown" material? (Should be <20%)
# - What % have "solid color"? (Should match visual inspection)
# - What % of Watches are "metal"? (Should be >95%)
```

---

## Processing Pipeline Design

### Architecture

```
Products (44,424)
    ↓
Load images (batch 100)
    ↓
SmolVLM extraction (3 prompts per image)
    ↓
JSON parsing + validation
    ↓
Confidence filtering
    ↓
Consistency checking (with existing metadata)
    ↓
Save to: main.fashion_demo.product_extracted_attributes
    ↓
Generate rich descriptions
    ↓
Regenerate CLIP text embeddings
    ↓
Update Vector Search indexes (auto-sync)
```

### Cost & Time Estimates

**SmolVLM on Databricks**:
- Deployment: GPU instance (g5.xlarge or similar)
- Cost: ~$1-2/hour for GPU instance
- Throughput: ~10-20 images/second (3 prompts each)
- Total processing: 44,424 products × 3 prompts = 133K inferences
  - At 15 images/sec: ~2 hours
  - Cost: ~$2-4 total

**vs. VLM API**:
- Llama 3.2 90B Vision: $0.001/image × 44,424 = $44
- Much better quality, but 10-20x more expensive

---

## Next Steps

1. **Deploy SmolVLM-2.2B to Databricks Model Serving** (Day 1)
   - Use HuggingFace model: `HuggingFaceTB/SmolVLM-Instruct`
   - Create endpoint with GPU backend
   - Test single inference

2. **Test Prompts on Sample Products** (Day 1-2)
   - Run 3 prompt templates on 20 diverse products
   - Manual validation of accuracy
   - Refine prompts based on errors

3. **Build Batch Processing Pipeline** (Day 2)
   - Spark UDF for calling SmolVLM
   - Batch processing with error handling
   - Save intermediate results

4. **Process Full Catalog** (Day 2-3)
   - Run on all 44,424 products
   - Confidence filtering
   - Consistency validation

5. **Generate Rich Descriptions** (Day 3)
   - Combine extracted attributes with existing metadata
   - Create new text descriptions

6. **Regenerate Embeddings & Test** (Day 3)
   - Generate new CLIP text embeddings
   - Update Vector Search indexes
   - A/B test search quality

---

## Success Criteria

**Tier 1 (Must Have)**:
- ✅ Material extraction: >75% accuracy
- ✅ Pattern extraction: >85% accuracy
- ✅ Formality extraction: >70% accuracy

**Tier 2 (Nice to Have)**:
- ✅ Style keywords: >60% relevance
- ✅ Visual details: >70% accuracy

**Business Impact**:
- 📈 Search precision: +20%
- 📈 Score distribution: 2% → 8%+ range
- 📈 User engagement: +10% CTR

---

## Questions to Answer Together

Before we proceed, let's align on:

1. **Model Hosting**: Do you want to deploy SmolVLM yourself, or use an API?
   - Self-host: More control, lower per-inference cost, requires GPU
   - API: Easier, but may not have SmolVLM (could use Llama 3.2 11B Vision instead)

2. **Prompt Strategy**: Multi-stage (3 separate prompts) or single comprehensive prompt?
   - Multi-stage: More accurate per attribute, 3x API calls
   - Single: Faster, cheaper, but may reduce accuracy

3. **Validation Approach**: Manual review sample size?
   - Suggest: 50 products (diverse categories) for initial validation

4. **Processing Order**: Which categories first?
   - Suggest: Start with Apparel > Topwear (shirts, t-shirts) - most common, clearest attributes

5. **Failure Handling**: What to do if extraction fails or confidence is low?
   - Suggest: Keep existing basic description, flag for manual review

Ready to start? What are your thoughts on these questions?
