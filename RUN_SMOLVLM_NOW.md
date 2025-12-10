# Run SmolVLM Extraction - Quickest Path

## 🚀 Fastest Way: Use Databricks UI (5 minutes)

Since SDK authentication isn't set up, here's the **quickest way** to get this running:

### Step 1: Open Databricks Workspace
Go to: https://adb-984752964297111.11.azuredatabricks.net

### Step 2: Import Notebook

1. Click **Workspace** in left sidebar
2. Navigate to your user folder: `/Users/kevin.ippen@databricks.com/`
3. Right-click → **Import**
4. **Upload File**: Select `notebooks/smolvlm_batch_attribute_extraction.py`
5. Click **Import**

### Step 3: Create GPU Cluster

1. Click **Compute** in left sidebar
2. Click **Create Compute**
3. Configure:
   ```
   Name: smolvlm-test
   Access Mode: Single User
   Databricks Runtime: 14.3 LTS ML (GPU)
   Node Type: g5.xlarge (filter by "GPU")
   Workers: 0 (Single Node)
   Terminate after: 60 minutes idle
   ```
4. Click **Create Compute**
5. Wait ~5 minutes for cluster to start

### Step 4: Run Notebook

1. Open the imported notebook
2. Click **Connect** dropdown at top
3. Select **smolvlm-test** cluster
4. Wait for cluster to be ready (green indicator)
5. Click **Run All** at top
6. Monitor progress

### ⏱️ Timeline:
- Cluster start: 5 minutes
- Dependencies install: 2 minutes
- Model loading: 3 minutes
- Processing 100 products: 8-12 minutes
- **Total: ~18-22 minutes**

### 💰 Cost: ~$1-2

---

## 📊 What to Watch For

### During Execution:

**Cell 1-5**: Setup (should complete in ~5 minutes)
```
✅ Libraries imported successfully
✅ Configuration loaded
✅ SmolVLM-2.2B loaded successfully
```

**Cell: Test Single Image** (should show extraction for 1 product)
```json
{
  "material": "...",
  "pattern": "...",
  "formality": "...",
  "extraction_success": true
}
```

**Cell: Process 100 Products** (takes ~10 minutes)
```
🔄 Starting attribute extraction...
✅ Extraction complete!
   Processed: 100 products
   Time: X.X minutes
   Speed: XX products/minute
```

### Quality Report (Key Metrics):

**Success Rate** (target: >85%)
```
✅ Success Rate: 92.0% (92/100)
```

**Material Distribution** (should be diverse)
```
material          count
knit fabric       35
woven fabric      28
leather           12
denim             8
...
unknown           7    ← Should be <15
```

**Confidence** (target: high+medium >75%)
```
confidence        count
high              65
medium            27
low               8     ← Should be <25
```

---

## ✅ Success Criteria

### GOOD Results (Proceed to Full Catalog):
- ✅ Success rate > 85%
- ✅ "unknown" material < 15%
- ✅ High+medium confidence > 75%
- ✅ Sample extractions look accurate
- ✅ Consistency checks pass:
  - Watches → 90%+ metal
  - T-shirts → 85%+ knit fabric

### NEEDS REFINEMENT:
- ⚠️ Success rate 70-85%
- ⚠️ "unknown" material 15-25%
- ⚠️ Some systematic errors

### RECONSIDER APPROACH:
- ❌ Success rate < 70%
- ❌ "unknown" material > 30%
- ❌ Most extractions look wrong

---

## 📋 After Test Completes

### If Results Are Good:

1. **Scale to Full Catalog**:
   - Edit notebook, change:
     ```python
     SAMPLE_SIZE = None  # Process all 44,424
     ```
   - Update cluster:
     ```
     Node Type: g5.2xlarge
     Workers: 2-4
     ```
   - Run again (~2-3 hours, $6-10)

2. **Join Tables**:
   - Run SQL: `notebooks/join_enriched_attributes.sql`

3. **Generate New Embeddings**:
   - I'll help you create this notebook

4. **A/B Test**:
   - Compare search quality

### If Results Need Work:
- Review error logs
- Adjust prompts
- Re-run test

---

## 🆘 Troubleshooting

### Issue: Cluster won't start
**Solution**: Check quota limits, try different region or instance type

### Issue: Module not found
**Solution**: Cell 1 installs dependencies, make sure it completed successfully

### Issue: CUDA out of memory
**Solution**: Reduce `BATCH_SIZE` from 8 to 4 in configuration cell

### Issue: Too many "unknown" materials
**Causes**:
- Images are low quality
- Products are jewelry/accessories (harder to determine)
- Model temperature too conservative

**Solution**:
- Filter by confidence (use high/medium only)
- May need prompt adjustments

---

## 💡 Alternative: Set Up SDK Authentication (Future Use)

If you want to submit jobs via SDK in the future:

### Option A: Personal Access Token

1. In Databricks UI: **Settings** → **User Settings** → **Access Tokens**
2. Click **Generate New Token**
3. Copy token
4. Set environment variable:
   ```bash
   export DATABRICKS_TOKEN="your-token-here"
   ```
5. Re-run: `python3 scripts/submit_smolvlm_job.py`

### Option B: Databricks CLI

```bash
# Install CLI
pip install databricks-cli

# Configure
databricks configure --token

# Then SDK will use CLI config
python3 scripts/submit_smolvlm_job.py
```

---

## 📞 Need Help?

**Check job status**:
- Databricks UI → **Workflows** → **Job Runs**

**Check cluster logs**:
- **Compute** → Your cluster → **Event Log** tab

**Check notebook output**:
- Scroll through cells for error messages
- Red cells = errors (click to expand)

---

## ⏭️ Next Steps After Test

Once you have good results from 100 products, let me know and I'll help you:

1. ✅ Scale to full catalog (44K products)
2. ✅ Join tables and create enriched descriptions
3. ✅ Generate new CLIP embeddings
4. ✅ Update Vector Search indexes
5. ✅ Set up A/B testing

---

**Ready?** Go ahead and import the notebook in Databricks UI!

Let me know what you see in the results and we'll proceed from there.
