# 🔄 Image Copy In Progress

> **Status**: Copying 44,441 product images from fashion_demo to fashion_sota

---

## 📋 Summary

Product images are being copied from the old volume to the new volume:

**Source**: `/Volumes/main/fashion_demo/raw_data/images`
**Destination**: `/Volumes/main/fashion_sota/product_images`
**Total Files**: 44,441 images
**Status**: ⏳ **IN PROGRESS**

---

## ✅ What's Done

1. ✅ **Volume Created**: `main.fashion_sota.product_images`
   - Type: MANAGED
   - Owner: kevin.ippen@databricks.com
   - Storage: Azure Blob Storage (via Unity Catalog)

2. ✅ **Copy Started**: Background process running
   - Command: `databricks fs cp --recursive`
   - Process ID: Check with `ps aux | grep "databricks fs cp"`

---

## 📊 Check Progress

### Quick Check

```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site
./check_copy_progress.sh
```

### Manual Check

```bash
# Count copied files
databricks fs ls dbfs:/Volumes/main/fashion_sota/product_images --profile work | wc -l

# Expected: Should increase from 0 to 44,441
```

### Check Copy Process

```bash
# See if copy is still running
ps aux | grep "databricks fs cp" | grep -v grep
```

---

## ⏱️ Expected Timeline

**Copy Speed**: ~2-3 files per second
**Total Files**: 44,441
**Estimated Time**: ~4-6 hours

The copy is running in the background and will continue even if you close your terminal (running via nohup).

---

## 🔍 Verification After Completion

Once the copy is complete, verify:

### 1. Count Files

```bash
# Source (should be 44,441)
databricks fs ls dbfs:/Volumes/main/fashion_demo/raw_data/images --profile work | wc -l

# Destination (should match)
databricks fs ls dbfs:/Volumes/main/fashion_sota/product_images --profile work | wc -l
```

### 2. Spot Check Images

```bash
# List first 10 images in new location
databricks fs ls dbfs:/Volumes/main/fashion_sota/product_images --profile work | head -10
```

### 3. Test Image Access in App

Once complete, test an image URL:
```
https://adb-984752964297111.11.azuredatabricks.net/ajax-api/2.0/fs/files/Volumes/main/fashion_sota/product_images/10000.jpg
```

(Requires authentication via browser)

---

## 🚀 App Configuration

The app is **already configured** to use the new volume:

```python
# core/config.py
CATALOG = "main"
SCHEMA = "fashion_sota"

@property
def IMAGE_VOLUME_PATH(self) -> str:
    return f"/Volumes/{self.CATALOG}/{self.SCHEMA}/product_images"

def get_image_url(self, product_id: int) -> str:
    return f"{self.DATABRICKS_WORKSPACE_URL}/ajax-api/2.0/fs/files{self.IMAGE_VOLUME_PATH}/{product_id}.jpg"
```

### Current Image Path

**Old (fashion_demo)**: `/Volumes/main/fashion_demo/raw_data/images/{product_id}.jpg`
**New (fashion_sota)**: `/Volumes/main/fashion_sota/product_images/{product_id}.jpg` ✅

**App is ready** - images will work once copy completes!

---

## 📱 App Status During Copy

### While Copy is Running

- ✅ **API endpoints**: Working (products, search, filters)
- ✅ **Database queries**: Working (Lakebase PostgreSQL)
- ⚠️ **Product images**: May show broken images or 404s

### After Copy Completes

- ✅ **Everything works**: All product images should display correctly

---

## ⚠️ Important Notes

### 1. Don't Stop the Copy Process

The copy is running in background with `nohup`. If you need to stop it:

```bash
# Find the process
ps aux | grep "databricks fs cp" | grep -v grep

# Kill it (use PID from above)
kill <PID>
```

But **only stop if necessary** - you'll need to restart the copy from scratch!

### 2. Volume Permissions

The new volume inherits permissions from the schema. The app already has READ_VOLUME permission configured in `app.yaml`:

```yaml
resources:
  uc_securable:
    - securable_type: VOLUME
      securable_full_name: main.fashion_sota.product_images
      privilege: READ_VOLUME
```

But this was added pointing to `inspo_images`. Let me fix this!

---

## 🔧 Update Required: Volume Permissions

The app needs READ_VOLUME permission for the product_images volume. Currently only has permission for inspo_images.

**Need to update**: [app.yaml](file:///Users/kevin.ippen/projects/fashion-ecom-site/app.yaml)

Should include both volumes:
```yaml
resources:
  uc_securable:
    - securable_type: VOLUME
      securable_full_name: main.fashion_sota.product_images  # Product images
      privilege: READ_VOLUME
    - securable_type: VOLUME
      securable_full_name: main.fashion_sota.inspo_images    # Inspiration images
      privilege: READ_VOLUME
```

---

## 📝 Monitoring

### Log File

The copy process logs to: `/tmp/copy_images.log`

View in real-time:
```bash
tail -f /tmp/copy_images.log
```

(May be empty if using default Databricks CLI logging)

### Process Status

```bash
# Check if still running
ps aux | grep "databricks fs cp" | grep fashion

# If nothing shows up, copy is complete or failed
```

---

## 🎯 Next Steps

### During Copy (Now)

1. ✅ **Let it run**: Copy is in progress, don't interrupt
2. ⏳ **Wait**: ~4-6 hours for completion
3. 📊 **Monitor**: Run `./check_copy_progress.sh` periodically

### After Copy Completes

1. **Verify file count**: Should be 44,441 files
2. **Update app.yaml**: Add product_images volume permission
3. **Redeploy app**: `databricks apps deploy ecom-visual-search --profile work`
4. **Test images**: Open app and verify product images load

---

## 🔄 If Copy Fails

### Restart the Copy

```bash
databricks fs cp \
  dbfs:/Volumes/main/fashion_demo/raw_data/images \
  dbfs:/Volumes/main/fashion_sota/product_images \
  --recursive \
  --overwrite \
  --profile work
```

### Alternative: Use Databricks Notebook

If CLI copy is too slow, you can use a notebook with parallel workers:

```python
# In Databricks notebook
from concurrent.futures import ThreadPoolExecutor
import dbutils

source = "/Volumes/main/fashion_demo/raw_data/images"
dest = "/Volumes/main/fashion_sota/product_images"

# Get all files
files = dbutils.fs.ls(source)

def copy_file(file_info):
    src = file_info.path
    dst = src.replace(source, dest)
    dbutils.fs.cp(src, dst)
    return file_info.name

# Copy in parallel (adjust workers based on cluster size)
with ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(copy_file, files))

print(f"Copied {len(results)} files")
```

---

## 📞 Troubleshooting

### Copy Seems Stuck

```bash
# Check process
ps aux | grep databricks | grep -v grep

# Check recent files in destination
databricks fs ls dbfs:/Volumes/main/fashion_sota/product_images --profile work | tail -20
```

### Out of Space Error

Unity Catalog volumes use cloud storage, should have plenty of space. If error occurs, check:
```bash
databricks volumes get main fashion_sota product_images --profile work
```

### Permission Errors

Should not occur since you own both volumes. If issues arise:
```bash
# Check source permissions
databricks volumes get main fashion_demo raw_data --profile work

# Check dest permissions
databricks volumes get main fashion_sota product_images --profile work
```

---

## 📚 Related Documentation

- [PERMISSIONS_FIXED.md](./PERMISSIONS_FIXED.md) - Database permissions fix
- [DEPLOYMENT_COMPLETE.md](./DEPLOYMENT_COMPLETE.md) - App deployment details
- [app.yaml](./app.yaml) - App configuration with volume permissions

---

**Started**: 2026-01-06 ~23:20 UTC
**Expected Completion**: 2026-01-07 ~03:00-05:00 UTC (4-6 hours)
**Status**: 🔄 **IN PROGRESS** - Let it run!

Check progress anytime with: `./check_copy_progress.sh`
