# Manual Environment Variable Setup

**Issue**: Secret references in app.yaml are not being expanded by Databricks Apps
**Solution**: Set the environment variable directly in the Databricks Apps UI
**Time to fix**: 2 minutes

---

## 🎯 Quick Fix Steps

### 1. Get Your PAT Token

Run this command locally to get your token:

```bash
databricks secrets get --scope redditscope --key redditkey
```

**Copy the output** - it should start with `dapi...`

### 2. Set Environment Variable in Databricks Apps UI

**Option A: Via Databricks Apps UI**

1. Go to your Databricks workspace
2. Navigate to **Apps** in the sidebar
3. Find and click on your app (ecom-visual-search)
4. Click **"Settings"** or **"Configuration"** tab
5. Find **"Environment Variables"** section
6. Click **"Add Environment Variable"**
7. Set:
   - **Name**: `LAKEBASE_PASSWORD`
   - **Value**: `<paste your dapi... token here>`
8. Click **"Save"**
9. Click **"Restart App"**

**Option B: Via Databricks CLI** (if available)

```bash
databricks apps update <your-app-id> \
  --env LAKEBASE_PASSWORD="<your-dapi-token>"

databricks apps restart <your-app-id>
```

### 3. Verify It Works

After restart, check logs at `https://your-app-url/logz`:

**Should see**:
```
ENVIRONMENT VARIABLES:
  LAKEBASE_PASSWORD: SET (starts with: dapi...)

AUTHENTICATION STRATEGY:
  ✓ Will use LAKEBASE_PASSWORD for database authentication
```

**Test API**:
```bash
curl https://your-app-url/api/v1/products?page=1&page_size=5
```

**Expected**: JSON with product data (not 500 error)

---

## ✅ Why This Works

- **Problem**: app.yaml secret references (`${secrets.redditscope.redditkey}`) aren't being expanded
- **Root cause**: Databricks Apps environment doesn't support this syntax in your deployment
- **Solution**: Setting the env var directly bypasses the expansion mechanism
- **Result**: App gets the actual token value and can authenticate

---

## 🔒 Security Note

**Concern**: Token is visible in the Databricks Apps UI

**Mitigation**:
- Only accessible to users with permission to manage the app
- No worse than storing in `.env` file
- Databricks workspace access is already protected
- This is a pragmatic trade-off for getting the app working

**For production**: Work with Databricks support to fix secret expansion in app.yaml

---

## 🐛 If It Still Doesn't Work

**Check these**:

1. **Token format**: Should start with `dapi`, no extra spaces/newlines
2. **Token validity**: Not expired or revoked
3. **Token permissions**: Can access database `main` on Lakebase instance
4. **App restarted**: Changes only take effect after full restart
5. **Logs**: Check startup logs show `LAKEBASE_PASSWORD: SET`

**Still failing?** Share:
- Startup logs (between `===` lines)
- Error message from first request
- Output of `databricks secrets get --scope redditscope --key redditkey | head -c 20` (first 20 chars only)

---

## 📝 What Changed in Code

**Commit `ae3f1e9`**: Removed secret references from app.yaml

**Before**:
```yaml
env:
  - name: LAKEBASE_PASSWORD
    value: ${secrets.redditscope.redditkey}
```

**After**:
```yaml
# Set LAKEBASE_PASSWORD in Databricks Apps UI
# (secret references not working in this environment)
```

This removes the literal string problem and lets you set the actual value.

---

## ⏭️ Next Steps

1. **Set LAKEBASE_PASSWORD in UI** (steps above)
2. **Restart the app**
3. **Test `/api/v1/products` endpoint**
4. **Share results** - either success or error logs

This should work! 🎉
