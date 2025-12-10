# SmolVLM Batch Extraction - Quick Start Guide

## 🚀 Ready to Run!

I've created a complete batch processing notebook: `notebooks/smolvlm_batch_attribute_extraction.py`

---

## ⚙️ Cluster Setup

### Recommended Cluster Configuration (for 100 product test)

```yaml
Cluster Mode: Single Node or Small Cluster
Instance Type: g5.xlarge (1x NVIDIA A10G GPU)
Databricks Runtime: 14.3 LTS ML or higher (GPU-enabled)
Workers: 0-2 (for 100 products, single node is fine)

Cost: ~$1-2/hour
Test Duration: ~10-15 minutes for 100 products
```

### For Full Catalog (44,424 products)

```yaml
Cluster Mode: Standard
Instance Type: g5.2xlarge or g5.4xlarge
Workers: 2-4 workers
Databricks Runtime: 14.3 LTS ML (GPU-enabled)

Cost: ~$3-6 total
Duration: ~2-3 hours
```

---

## 📋 Step-by-Step Instructions

### Step 1: Create GPU Cluster

1. Go to **Compute** in Databricks workspace
2. Click **Create Compute**
3. Settings:
   - **Cluster Name**: `smolvlm-extraction`
   - **Cluster Mode**: Single Node (for test)
   - **Databricks Runtime**: **14.3 LTS ML (GPU)** or later
   - **Node Type**: `g5.xlarge` (NVIDIA A10G, 24GB GPU RAM)
   - **Autoscaling**: Disabled for test
   - **Terminate after**: 60 minutes of inactivity

4. Click **Create Compute**

**Note**: Make sure to select **ML runtime with GPU** - it has CUDA pre-installed!

---

### Step 2: Upload Notebook

1. Go to **Workspace**
2. Navigate to your user folder
3. Click **Import**
4. Upload `notebooks/smolvlm_batch_attribute_extraction.py`

---

### Step 3: Attach to Cluster

1. Open the notebook
2. Click **Connect** dropdown at top
3. Select your `smolvlm-extraction` cluster
4. Wait for cluster to start (~5 minutes first time)

---

### Step 4: Run Test (100 Products)

The notebook is pre-configured for 100 products test:

```python
# In cell "Configuration"
SAMPLE_SIZE = 100  # ✅ Already set for testing
```

**Run the notebook**:
- Option 1: Click **Run All** at top
- Option 2: Run cells one by one (recommended for first time)

**What happens**:
1. **Install dependencies** (~2 minutes)
2. **Load SmolVLM-2.2B** (~3 minutes)
   - Downloads model (~5GB)
   - Loads to GPU memory
3. **Test single image** (~5 seconds)
   - Validates setup is working
4. **Process 100 products** (~8-12 minutes)
   - 3 prompts per image
   - ~8-10 products/minute
5. **Quality analysis** (instant)
   - Success rate
   - Attribute distributions
   - Sample results

**Total time**: ~15-20 minutes

---

## 🔍 What to Look For in Test Results

### 1. **Success Rate** (Target: >90%)

```
✅ Success Rate: 95.0% (95/100)
```

**Good**: 90%+ success
**Acceptable**: 80-90% (some images may be unclear)
**Problem**: <80% (check error logs)

---

### 2. **Material Distribution** (Should be diverse)

```
Material               Count
leather                12
denim                  8
knit fabric            35
woven fabric           28
synthetic              5
metal                  3
canvas                 2
unknown                7
```

**Look for**:
- ✅ Diverse materials (not all "unknown")
- ✅ "unknown" < 15%
- ✅ Knit fabric should be high (t-shirts, sweaters common)

**Red flags**:
- ❌ >30% "unknown" → model struggling
- ❌ All same material → model bias

---

### 3. **Pattern Distribution** (Should match catalog)

```
Pattern                Count
solid color            72
striped                8
floral print           5
geometric              3
checkered              4
polka dots             2
abstract print         1
no clear pattern       5
```

**Expected**: Mostly "solid color" (fashion products are often solid)

**Red flags**:
- ❌ Too many "no clear pattern" (>20%)
- ❌ Patterns don't match when you visually inspect

---

### 4. **Formality Distribution**

```
Formality              Count
casual                 68
formal                 12
business casual        15
athletic               5
```

**Look for**:
- ✅ Matches your catalog composition
- ✅ Distribution makes sense (most fashion is casual)

---

### 5. **Confidence Levels** (Target: >70% high/medium)

```
Confidence             Count
high                   65
medium                 27
low                    8
```

**Good**: High + Medium > 80%
**Acceptable**: High + Medium > 70%
**Problem**: Low > 30%

---

### 6. **Consistency Checks**

The notebook includes validation queries:

#### Check 1: Watches Should Be Metal
```sql
SELECT product_display_name, material
FROM product_extracted_attributes
WHERE article_type = 'Watches'
```

**Expected**: 95%+ should be "metal"

#### Check 2: T-Shirts Should Be Knit
```sql
SELECT product_display_name, material
FROM product_extracted_attributes
WHERE article_type = 'Tshirts'
```

**Expected**: 90%+ should be "knit fabric"

#### Check 3: Formal Shirts
```sql
SELECT product_display_name, formality, collar_type
FROM product_extracted_attributes
WHERE article_type = 'Shirts' AND usage = 'Formal'
```

**Expected**: Should be "formal" or "business casual" with "collar"

---

## 📊 Sample Results to Review

The notebook shows 20 sample extractions. Here's what GOOD results look like:

### Example 1: Leather Jacket
```json
{
  "product": "Roadster Men Leather Jacket",
  "material": "leather",
  "pattern": "solid color",
  "formality": "casual",
  "style_keywords": ["modern", "urban"],
  "details": ["has zipper", "has pockets"],
  "collar": "collar",
  "sleeves": "long sleeve",
  "fit": "fitted",
  "confidence": "high"
}
```
✅ **Accurate**: Correctly identified leather, zipper, fitted

### Example 2: Casual T-Shirt
```json
{
  "product": "Puma Men Tshirt",
  "material": "knit fabric",
  "pattern": "solid color",
  "formality": "casual",
  "style_keywords": ["athletic", "sporty"],
  "details": ["has logo"],
  "collar": "crew neck",
  "sleeves": "short sleeve",
  "fit": "regular",
  "confidence": "high"
}
```
✅ **Accurate**: Knit fabric for t-shirt, athletic style for Puma

### Example 3: Floral Dress
```json
{
  "product": "Women's Floral Summer Dress",
  "material": "woven fabric",
  "pattern": "floral print",
  "formality": "casual",
  "style_keywords": ["bohemian", "feminine"],
  "details": ["none visible"],
  "collar": "scoop neck",
  "sleeves": "sleeveless",
  "fit": "cannot determine",
  "confidence": "medium"
}
```
✅ **Good**: Correctly identified floral, fit "cannot determine" for flat-lay is appropriate

---

## ⚠️ Common Issues & Solutions

### Issue 1: Model Download Fails
```
Error: Connection timeout downloading model
```

**Solution**: Run this cell again. Model is 5GB, may take time on first run.

---

### Issue 2: GPU Out of Memory
```
CUDA out of memory
```

**Solution**:
- Check cluster has GPU: `g5.xlarge` or better
- Reduce `BATCH_SIZE` from 8 to 4 in configuration

---

### Issue 3: Image Path Not Found
```
FileNotFoundError: /Volumes/main/fashion_demo/...
```

**Solution**:
- Check images are in Unity Catalog Volumes
- Update `image_path` column if needed
- For local testing, images should be at path in database

---

### Issue 4: Too Many "unknown" Materials (>20%)
```
Material: unknown (45%)
```

**Possible causes**:
- Images are low quality/blurry
- Products are jewelry/accessories (hard to determine material from image)
- Model temperature too low (try 0.2 instead of 0.1)

**Solution**:
- Filter by confidence: only use high/medium confidence
- Review failed extractions manually
- May need to fine-tune prompts

---

### Issue 5: JSON Parsing Errors
```
JSON parse error: Expecting value
```

**This is normal** for some responses. The notebook handles this gracefully:
- Sets `extraction_success = False`
- Uses default values
- Logs error for review

**If >10% JSON errors**:
- SmolVLM may not be following JSON format
- Try adjusting prompt wording
- Increase `max_new_tokens` in config

---

## ✅ Decision Point: Proceed to Full Catalog?

After reviewing 100 product test results, decide:

### ✅ **PROCEED** if:
- Success rate > 85%
- Material distribution looks reasonable
- Consistency checks pass (watches=metal, tshirts=knit)
- Sample results visually match products
- Confidence: high+medium > 75%

### 🔄 **REFINE PROMPTS** if:
- Success rate 70-85%
- Too many "unknown" (15-25%)
- Some systematic errors (e.g., all dresses classified as "casual" when some are formal)

### ❌ **RECONSIDER APPROACH** if:
- Success rate < 70%
- >30% "unknown" materials
- Consistency checks fail badly
- Model seems to be guessing randomly

---

## 🚀 Proceeding to Full Catalog

If test looks good, scale to full catalog:

### 1. Update Configuration
```python
SAMPLE_SIZE = None  # Process all 44,424 products
NUM_PARTITIONS = 8  # Increase parallelism
```

### 2. Scale Cluster
```yaml
Instance Type: g5.2xlarge (better GPU)
Workers: 2-4 workers
```

### 3. Run Full Extraction
- Click **Run All**
- Estimated time: 2-3 hours
- Estimated cost: $4-8

### 4. Monitor Progress
- Watch cell outputs for progress
- Check GPU utilization: `nvidia-smi` in terminal
- Monitor for errors

---

## 📈 After Full Extraction

### Next Steps:

1. **Validate Full Results**
   - Run all validation queries
   - Check distribution across all categories
   - Sample 50-100 products manually

2. **Generate CLIP Embeddings**
   - Use enriched descriptions
   - Run `multimodal_clip_implementation.py` notebook
   - Generate new text embeddings with rich descriptions

3. **Update Vector Search**
   - Delta Sync will auto-update indexes
   - Or manually sync if needed

4. **A/B Test**
   - 50% traffic: baseline (old descriptions)
   - 50% traffic: enriched (new descriptions)
   - Measure: CTR, precision, score distribution

---

## 💡 Tips for Best Results

1. **Run during off-peak hours** - GPU clusters are cheaper
2. **Monitor first 100 products** - catch errors early
3. **Check diverse product types** - not just t-shirts
4. **Review low-confidence extractions** - may need manual correction
5. **Save intermediate results** - checkpoint every 10K products

---

## 📞 Need Help?

**Common questions**:

**Q: Can I pause and resume?**
A: Yes! Results are saved to Unity Catalog table. You can process in batches by adding LIMIT and OFFSET.

**Q: What if some extractions fail?**
A: Normal! The notebook flags failed extractions. You can:
- Re-run just failed products with adjusted prompts
- Use baseline descriptions for failed products
- Manually correct critical products (e.g., hero items)

**Q: How do I know if it's working?**
A: Watch for:
- ✅ GPU utilization 80%+ (run `nvidia-smi`)
- ✅ Steady progress (~8-10 products/minute)
- ✅ Success rate staying >85%

---

## 📝 Checklist

Before running full catalog:

- [ ] Test with 100 products completed
- [ ] Success rate > 85%
- [ ] Consistency checks passed
- [ ] Sample results reviewed and look good
- [ ] Cluster sized appropriately (g5.2xlarge or better)
- [ ] Monitoring plan in place
- [ ] Backup plan if something fails (can resume from checkpoint)

---

Ready to run the test? Let me know what you see in the results!
