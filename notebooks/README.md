# Notebooks Directory

> Organized collection of notebooks for the fashion e-commerce outfit pairing system

## 📁 Directory Structure

```
notebooks/
├── production/              # Core pipeline (execute in order)
├── alternative_approaches/  # Alternative implementations & testing
├── reference/              # Migration guides & documentation
└── NOTEBOOK_INVENTORY.md   # Detailed analysis of all notebooks
```

---

## 🎯 Production Pipeline

**Location**: `production/`

These notebooks implement the **Pattern-Based Outfit Pairing** system currently in production.

### Execution Order

| # | Notebook | Purpose | Input | Output | Status |
|---|----------|---------|-------|--------|--------|
| 1 | `01_select_anchor_products.py` | Select ~200 representative products | Product catalog | `data/anchor_products.json` (72KB) | ✅ Complete |
| 2 | `02_generate_outfit_patterns.py` | Generate 5-10 patterns per anchor using GenAI | Anchor products | `data/outfit_patterns.json` (153KB) | ✅ Complete |
| 3 | `03_apply_patterns_to_catalog.py` | Apply patterns to all products via similarity | Patterns + catalog | `data/pattern_recs_*.json` | ⚠️ Incomplete |

**Current Issue**: Step 3 output files are only 2 bytes. Needs re-execution.

### How to Run

```bash
# Step 1: Select anchor products (stratified sampling)
databricks workspace import notebooks/production/01_select_anchor_products.py

# Step 2: Generate patterns using Llama 3.1 70B
databricks workspace import notebooks/production/02_generate_outfit_patterns.py

# Step 3: Apply patterns to entire catalog
databricks workspace import notebooks/production/03_apply_patterns_to_catalog.py
```

---

## 🔀 Alternative Approaches

**Location**: `alternative_approaches/`

These notebooks provide alternative implementations and testing utilities.

| Notebook | Purpose | When to Use |
|----------|---------|-------------|
| `02a_generate_patterns_ai_functions.py` | Pattern generation using Databricks AI Functions | If AI Functions are preferred over REST API |
| `02b_generate_patterns_rest_api.py` | Pattern generation using REST API endpoints | If direct REST API calls are preferred |
| `02_test_pattern_generation.py` | Unit tests for pattern generation | To validate pattern quality before batch processing |
| `05_rule_based_pairing.py` | Deterministic rule-based pairing | Fallback when pattern matching fails |

---

## 📚 Reference

**Location**: `reference/`

| File | Purpose | When to Use |
|------|---------|-------------|
| `migrate_to_lakebase.ipynb` | Migration guide from fashion_demo to fashion_sota | When migrating schemas or understanding architecture |
| `QUICK_SETUP_64_WORKERS.md` | Setup documentation for parallel processing | When scaling pattern generation across multiple workers |

---

## 🔬 Archived Research (Not in Use)

**Location**: `archive/notebooks_research/`

9 notebooks were archived during the 2026-01-08 cleanup:

- **Lookbook Approach** (1): Superseded by pattern-based approach
- **External Datasets** (2): DeepFashion2 and complementarity research
- **Multimodal Experiments** (1): Qwen model experiments
- **SmolVLM Attribute Extraction** (4): v1, v2, v3, v4 iterations
- **Misc** (1): Unknown exploratory work

See [`NOTEBOOK_INVENTORY.md`](NOTEBOOK_INVENTORY.md) for detailed analysis.

---

## 🚀 Quick Start

### For New Developers

1. **Understand the approach**: Read [OUTFIT_PAIRING_PATTERN_APPROACH.md](../OUTFIT_PAIRING_PATTERN_APPROACH.md)
2. **Review completed work**: Check data files in `data/`:
   - `anchor_products.json` - 200 representative products
   - `outfit_patterns.json` - Generated patterns
3. **Run production pipeline**: Execute notebooks in `production/` directory in order
4. **Test alternatives**: Try implementations in `alternative_approaches/`

### For Troubleshooting

1. **Check outputs**: Verify data files are populated (not 2 bytes)
2. **Review logs**: Check Databricks job logs for errors
3. **Run tests**: Execute `02_test_pattern_generation.py` to validate patterns
4. **Fallback**: Use `05_rule_based_pairing.py` for deterministic pairings

---

## 📊 Data Flow

```
Products Catalog (44K products)
         ↓
[01] Select Anchors (stratified sampling)
         ↓
Anchor Products (200 products) → data/anchor_products.json
         ↓
[02] Generate Patterns (GenAI)
         ↓
Outfit Patterns (200 × 5-10) → data/outfit_patterns.json
         ↓
[03] Apply to Catalog (similarity matching)
         ↓
Pattern Recommendations (44K × 3-5) → data/pattern_recs_*.json
         ↓
Production API (RecommendationsService)
```

---

## 🔧 Maintenance

### When to Re-run

- **Product catalog updated**: Re-run step 1 to include new products
- **Pattern quality issues**: Re-run step 2 with improved prompts
- **Coverage gaps**: Re-run step 3 to regenerate recommendations
- **Schema changes**: Update notebooks and re-run full pipeline

### Monitoring

- **Data file sizes**: Should be > 1KB (not 2 bytes)
- **Coverage metrics**: Track % of products with recommendations
- **Pattern quality**: Sample-check pattern reasonableness
- **API performance**: Monitor recommendation endpoint latency

---

## 📝 Related Documentation

- [OUTFIT_PAIRING_PATTERN_APPROACH.md](../OUTFIT_PAIRING_PATTERN_APPROACH.md) - Strategy & methodology
- [OUTFIT_PAIRING_100_PERCENT_PLAN.md](../OUTFIT_PAIRING_100_PERCENT_PLAN.md) - Original implementation plan
- [NOTEBOOK_INVENTORY.md](NOTEBOOK_INVENTORY.md) - Detailed notebook analysis
- [DATA_INVENTORY.md](../DATA_INVENTORY.md) - Complete data schema

---

_Last Updated: 2026-01-08_
_Reorganized during codebase cleanup initiative_
