# Notebook Inventory & Organization

> Analysis of which notebooks are actively used vs. exploratory research

## 🎯 Production Notebooks (Used)

These notebooks implement the **Pattern-Based Outfit Pairing** system currently in production:

### Core Pipeline (Executed in Order)
1. **01_select_anchor_products.py** → Selects ~200 representative anchor products using stratified sampling
   - Input: All products from `main.fashion_sota.products_lakebase`
   - Output: `data/anchor_products.json` (72KB)
   - Status: ✅ Completed

2. **02_generate_outfit_patterns.py** → Generates 5-10 reusable patterns per anchor using GenAI
   - Input: `data/anchor_products.json`
   - Output: `data/outfit_patterns.json` (153KB)
   - Status: ✅ Completed

3. **04_batch_apply_patterns.py** → Applies patterns to all products via similarity matching
   - Input: `data/outfit_patterns.json` + product catalog
   - Output: `data/pattern_based_recommendations.json`, `data/pattern_recs_for_uc.json`
   - Status: ⚠️ Incomplete (output files are only 2B)

### Alternative Implementations (Testing/Comparison)
4. **02_generate_patterns_ai_functions.py** → Pattern generation using Databricks AI Functions
   - Purpose: Alternative to REST API approach
   - Status: Tested, not used in final pipeline

5. **02_test_pattern_generation.py** → Unit tests for pattern generation
   - Purpose: Validate pattern quality
   - Status: Testing notebook

6. **03_generate_patterns_rest_api.py** → Pattern generation using REST API endpoints
   - Purpose: Alternative approach to AI Functions
   - Status: Tested, not used in final pipeline

7. **05_rule_based_pairing.py** → Deterministic rule-based pairing fallback
   - Purpose: Backup approach when pattern matching fails
   - Status: Implemented in `OutfitCompatibilityService` instead

### Reference Notebooks
8. **migrate_to_lakebase.ipynb** → Migration guide from fashion_demo to fashion_sota
   - Purpose: Historical reference for schema migration
   - Status: Keep for reference

9. **QUICK_SETUP_64_WORKERS.md** → Setup documentation for parallel processing
   - Purpose: Documentation for scaling pattern generation
   - Status: Keep as documentation

---

## 🔬 Research/Exploratory Notebooks (Archive Candidates)

These were exploratory research, superseded approaches, or experiments:

### Lookbook-Based Approach (Superseded)
- **generate_outfit_pairs_from_lookbook.py**
  - Original approach: Extract pairings from 29 lookbook images
  - Result: Only 2.4% coverage (1,086 products)
  - Superseded by: Pattern-based approach
  - → **Archive**

### External Dataset Research (Not Used)
- **deepfashion2_complete_the_look.py**
  - Research on DeepFashion2 dataset for outfit completion
  - Not integrated into production
  - → **Archive**

- **complementarity.py**
  - Research on complementarity metrics for outfit pairing
  - Not integrated into production
  - → **Archive**

### Multimodal Model Experiments (Not Used)
- **latent_feature_extraction_qwen.py**
  - Experiment with Qwen multimodal model for feature extraction
  - Not integrated into production
  - → **Archive**

### Attribute Extraction Pipeline (Not Used)
- **smolvlm_batch_attribute_extraction.py** (v1)
- **smolvlm_batch_attribute_extraction_endpoint.py** (v2 - endpoint version)
- **smolvlm_batch_attribute_extraction_fixed.py** (v3 - bug fixes)
- **smolvlm_batch_attribute_extraction_optimized.py** (v4 - optimized)
  - SmolVLM experiments for extracting product attributes
  - Results: Not integrated into production workflow
  - → **Archive all 4 versions**

### Unknown/Untitled
- **RepEng.ipynb**
  - Unknown purpose (likely exploratory)
  - → **Archive**

---

## 📊 Summary

| Category | Count | Action |
|----------|-------|--------|
| **Production Pipeline** | 3 | Keep & Rename (01, 02, 04) |
| **Alternative Implementations** | 4 | Keep (useful for testing) |
| **Reference** | 2 | Keep (migration + docs) |
| **Research/Exploratory** | 10 | Archive |
| **Total** | 19 | |

---

## ✨ Proposed Reorganization

### Keep in `notebooks/` (Rename for clarity)
```
notebooks/
├── production/
│   ├── 01_select_anchor_products.py          (KEEP - Step 1)
│   ├── 02_generate_outfit_patterns.py        (KEEP - Step 2)
│   └── 03_apply_patterns_to_catalog.py       (RENAME from 04_batch_apply_patterns.py)
│
├── alternative_approaches/
│   ├── 02a_generate_patterns_ai_functions.py (RENAME - AI Functions version)
│   ├── 02b_generate_patterns_rest_api.py     (RENAME - REST API version)
│   ├── 02_test_pattern_generation.py         (KEEP - Testing)
│   └── 05_rule_based_pairing.py              (KEEP - Fallback approach)
│
├── reference/
│   ├── migrate_to_lakebase.ipynb             (KEEP - Migration guide)
│   └── QUICK_SETUP_64_WORKERS.md             (KEEP - Setup docs)
│
└── README.md                                  (NEW - This inventory)
```

### Archive to `archive/notebooks_research/`
```
archive/notebooks_research/
├── lookbook_approach/
│   └── generate_outfit_pairs_from_lookbook.py
│
├── external_datasets/
│   ├── deepfashion2_complete_the_look.py
│   └── complementarity.py
│
├── multimodal_experiments/
│   └── latent_feature_extraction_qwen.py
│
├── smolvlm_attribute_extraction/
│   ├── smolvlm_batch_attribute_extraction.py
│   ├── smolvlm_batch_attribute_extraction_endpoint.py
│   ├── smolvlm_batch_attribute_extraction_fixed.py
│   └── smolvlm_batch_attribute_extraction_optimized.py
│
└── misc/
    └── RepEng.ipynb
```

---

## 🔍 Data Flow Verification

**Current Data Files** (what's actually being used):
- ✅ `data/anchor_products.json` (72KB) - 200 anchor products
- ✅ `data/outfit_patterns.json` (153KB) - Patterns for anchors
- ⚠️ `data/pattern_based_recommendations.json` (2B) - INCOMPLETE
- ⚠️ `data/pattern_recs_for_uc.json` (2B) - INCOMPLETE

**Issue**: Step 3 (04_batch_apply_patterns.py) appears incomplete. Output files are only 2 bytes.

**Recommendation**:
1. Review `04_batch_apply_patterns.py` for errors
2. Re-run to complete the pattern application
3. Verify output files are populated

---

## 🎬 Next Actions

1. **Immediate**: Archive 10 research notebooks
2. **Soon**: Reorganize remaining 9 notebooks into subdirectories
3. **Fix**: Complete pattern application pipeline (Step 3)
4. **Document**: Create README.md in notebooks/ with usage instructions

---

_Analysis Date: 2026-01-08_
_Generated during codebase cleanup initiative_
