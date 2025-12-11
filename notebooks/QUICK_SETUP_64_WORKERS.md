# ⚡ Quick Setup: 64 Workers for 45-70 Minute Processing

## Step 1: Create Databricks Cluster

### Azure (Recommended VMs)
```yaml
Cluster Name: cpu-extraction-64-spot
Databricks Runtime: 14.3 LTS
Worker Type: Standard_D4s_v5
Driver Type: Standard_D8s_v5
Workers: 64 (or auto-scale 32-64)
Spot Policy: Use spot with on-demand fallback
```

**Cluster Configuration JSON:**
```json
{
  "cluster_name": "cpu-extraction-64-spot",
  "spark_version": "14.3.x-scala2.12",
  "node_type_id": "Standard_D4s_v5",
  "driver_node_type_id": "Standard_D8s_v5",
  "num_workers": 64,
  "autoscale": {
    "min_workers": 32,
    "max_workers": 64
  },
  "azure_attributes": {
    "availability": "SPOT_WITH_FALLBACK_AZURE",
    "first_on_demand": 1,
    "spot_bid_max_price": -1
  },
  "spark_conf": {
    "spark.executor.memory": "12g",
    "spark.executor.cores": "4",
    "spark.sql.adaptive.enabled": "true"
  }
}
```

### AWS
```yaml
Worker Type: m6i.xlarge (4 cores, 16GB)
Driver Type: m6i.2xlarge (8 cores, 32GB)
Spot Policy: SPOT_WITH_FALLBACK
Workers: 64 (or auto-scale 32-64)
```

### GCP
```yaml
Worker Type: n2-standard-4 (4 cores, 16GB)
Driver Type: n2-standard-8 (8 cores, 32GB)
Preemptible: Yes
Workers: 64 (or auto-scale 32-64)
```

---

## Step 2: Code Configuration

In the notebook, set this preset:

```python
# In Configuration cell (line ~45):
CLUSTER_PRESET = "max_speed"  # Uncomment this line

# Everything else is auto-configured!
# - 256 partitions (4x workers)
# - INT8 quantization enabled
# - Optimal batch sizes
```

---

## Step 3: Run!

```python
# Test first with 100 samples (< 1 minute):
SAMPLE_SIZE = 100
# Run all cells

# Then full catalog (45-70 minutes):
SAMPLE_SIZE = None
# Run all cells
```

---

## Expected Results

### Performance
```
Workers: 64
Per-worker: 10-15 products/minute
Total: 640-960 products/minute

Timing:
- 100 products: 6-10 seconds
- 10,000 products: 10-16 minutes
- 44,424 products: 46-69 minutes
```

### Cost (with spot/preemptible)
```
Azure Spot: $2.03 for 44K products
AWS Spot: $3.04 for 44K products
GCP Preemptible: $2.56 for 44K products
```

---

## VM Cost Breakdown

### Azure Standard_D4s_v5 (64 workers)
```
On-demand: $0.192/hour × 64 = $12.29/hour
Spot (80% off): $0.038/hour × 64 = $2.43/hour

44K products (0.84 hours):
- On-demand: $10.32
- Spot: $2.04 ⭐
```

### AWS m6i.xlarge (64 workers)
```
On-demand: $0.192/hour × 64 = $12.29/hour
Spot (70% off): $0.058/hour × 64 = $3.71/hour

44K products (0.84 hours):
- On-demand: $10.32
- Spot: $3.12 ⭐
```

### GCP n2-standard-4 (64 workers)
```
Standard: $0.194/hour × 64 = $12.42/hour
Preemptible (75% off): $0.048/hour × 64 = $3.07/hour

44K products (0.84 hours):
- Standard: $10.43
- Preemptible: $2.58 ⭐
```

---

## Alternative: 32 Workers (Larger VMs)

**Same performance, easier management:**

```yaml
# Use 32 workers with 8 cores each instead of 64 with 4 cores
Worker Type: Standard_D8s_v5 (Azure) or c6i.2xlarge (AWS)
Workers: 32
Cost: Same as 64 smaller workers (~$2-4 with spot)
Benefit: Fewer workers to coordinate
```

---

## Monitoring

### What to Watch
```
Spark UI → Stages:
- Task duration: 12-17 minutes per task
- Completed tasks: 256 total
- Failed tasks: < 1%

Spark UI → Executors:
- CPU utilization: 70-90%
- Memory usage: < 10GB per executor
- GC time: < 5% of task time
```

### If Slow
```
✅ Check CPU utilization (should be high)
✅ Verify quantization enabled
✅ Check model loading time (< 30 sec)
✅ Increase NUM_PARTITIONS if stragglers
```

---

## Scaling Comparison

| Workers | Partitions | Time | Spot Cost | VM Type |
|---------|------------|------|-----------|---------|
| 8 | 32 | 6-9h | $7-10 | D4s_v5 |
| 16 | 64 | 3-4.5h | $2-4 | D4s_v5 |
| 32 | 128 | 1.5-2.5h | $2-4 | D4s_v5 |
| **64** | **256** | **45-70min** | **$2-4** | **D4s_v5** ⭐ |
| 128 | 512 | 30-40min | $3-5 | D2s_v5 |

---

## Troubleshooting

### Out of Memory
```python
# Reduce batch size:
BATCH_SIZE_PER_WORKER = 1  # Instead of 2
```

### Slow Performance (< 8 products/min/worker)
```python
# Increase partitions:
NUM_PARTITIONS = 512  # Instead of 256

# Verify quantization:
USE_QUANTIZATION = True  # Should be True
```

### Spot Interruptions
```yaml
# In cluster config:
azure_attributes:
  availability: SPOT_WITH_FALLBACK_AZURE
  first_on_demand: 1  # Keep driver on-demand
```

---

## Quick Commands

### Check Cluster Size
```python
# In notebook:
sc.defaultParallelism  # Should be ~256
spark.sparkContext._conf.get("spark.executor.instances")  # Should be 64
```

### Monitor Progress
```python
# Watch Spark UI:
# https://<databricks-instance>/#/setting/clusters/<cluster-id>/sparkUi
```

### Estimate Remaining Time
```python
# After first partition completes:
completed = products_with_attrs.count()  # Run this periodically
remaining = 44424 - completed
minutes_elapsed = (time.time() - start_time) / 60
rate = completed / minutes_elapsed
remaining_minutes = remaining / rate
print(f"Estimated completion: {remaining_minutes:.1f} minutes")
```

---

## Final Checklist

Before running full catalog:

- [ ] Cluster has 64 workers (or 32-64 auto-scale)
- [ ] VM type: Standard_D4s_v5 or equivalent
- [ ] Spot/preemptible enabled
- [ ] `CLUSTER_PRESET = "max_speed"` is set
- [ ] `USE_QUANTIZATION = True` is set
- [ ] Test run with `SAMPLE_SIZE = 100` completed successfully
- [ ] Spark UI shows 64 active executors
- [ ] Per-worker throughput is 10-15 products/minute

Then set `SAMPLE_SIZE = None` and run!

---

## Support

For detailed VM recommendations: **64_WORKER_SCALING_GUIDE.md**
For GPU vs CPU comparison: **GPU_vs_CPU_COMPARISON.md**
For optimization tips: **OPTIMIZATION_SUMMARY.md**
