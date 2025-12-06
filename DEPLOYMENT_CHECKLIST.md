# Databricks App Deployment Checklist

## ✅ Pre-Deployment Checklist

### 1. Verify Databricks Secret Exists

Check that your PAT is stored in Databricks secrets:

```bash
# List secrets in your scope
databricks secrets list-secrets --scope redditscope
```

**Expected output:**
```
Key             Last Updated
redditkey       2024-XX-XX
```

If the secret doesn't exist, create it:
```bash
databricks secrets put-secret --scope redditscope --key redditkey --string-value "dapi..."
```

### 2. Verify App Configuration

Check [app.yaml](app.yaml) contains:
```yaml
env:
  - name: LAKEBASE_PASSWORD
    value: ${secrets.redditscope.redditkey}
```

✅ **This has been configured** in commit `42fa53a`

### 3. Verify Secret Permissions

Make sure your app (or service principal running it) has READ access to the secret scope:

```bash
# Check ACLs for the scope
databricks secrets list-acls --scope redditscope
```

If your app doesn't have access, grant it:
```bash
databricks secrets put-acl --scope redditscope --principal <your-service-principal> --permission READ
```

## 🚀 Deployment Steps

### Step 1: Deploy the Updated Code

```bash
# Make sure you're on the refactor/lakebase-tables branch
git checkout refactor/lakebase-tables
git pull origin refactor/lakebase-tables

# Deploy to Databricks (method depends on your setup)
# Option A: Using Databricks CLI
databricks apps deploy /path/to/app

# Option B: Through Databricks UI
# - Go to your app in the workspace
# - Click "Update" or "Redeploy"
# - Confirm deployment
```

### Step 2: Restart the App

After deployment, **restart the app** to pick up the new environment variable:

```bash
# Via CLI
databricks apps restart <app-name>

# Or via UI:
# - Go to your app
# - Click "Restart"
```

### Step 3: Verify Configuration

Once the app is running, check the configuration endpoint:

```bash
curl https://your-app-url/api/v1/config-check
```

**Expected output:**
```json
{
  "lakebase_config": {
    "password_source": "LAKEBASE_PASSWORD",
    "lakebase_password": "✓ Set (starts with: dapi...)",
    "databricks_token": "✓ Set (starts with: dapi...)"
  },
  "warnings": []
}
```

✅ **Good signs:**
- `password_source: "LAKEBASE_PASSWORD"` (not DATABRICKS_TOKEN)
- `lakebase_password: "✓ Set (starts with: dapi...)"`
- `warnings: []` (empty array)

❌ **Bad signs:**
- `password_source: "❌ NONE"`
- `lakebase_password: "❌ NOT SET"`
- Warnings about missing password

### Step 4: Test Database Connection

Try accessing the products API:

```bash
curl https://your-app-url/api/v1/products?page=1&page_size=5
```

**Expected:** JSON response with products
**If fails:** Check app logs for authentication errors

## 📊 Verification Commands

### Check App Logs

```bash
# View recent logs
databricks apps logs <app-name> --tail 100

# Look for these messages:
# ✅ Success: "✓ Lakebase auth: Using LAKEBASE_PASSWORD (starts with: dapi...)"
# ❌ Error: "⚠️ LAKEBASE AUTHENTICATION ERROR: No password/token found!"
```

### Test Database Connection Manually

From a machine with network access to Lakebase:

```bash
psql "host=instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net \
      user=kevin.ippen@databricks.com \
      dbname=main \
      port=5432 \
      sslmode=require"
# When prompted for password, paste your PAT
```

If this works, your token is valid and has Lakebase permissions.

## 🐛 Troubleshooting

### Issue: "password_source: ❌ NONE"

**Problem:** App isn't reading the secret

**Solutions:**
1. Verify secret exists: `databricks secrets list-secrets --scope redditscope`
2. Check app has READ permissions on secret scope
3. Restart the app after deployment
4. Check for typos in scope/key names in app.yaml

### Issue: "Failed to decode token"

**Problem:** Token is invalid or lacks permissions

**Solutions:**
1. Verify token hasn't expired
2. Check token has Lakebase permissions
3. Test token manually with psql (see above)
4. Generate a new PAT and update the secret:
   ```bash
   databricks secrets put-secret --scope redditscope --key redditkey --string-value "dapi..."
   ```

### Issue: "role 'kevin.ippen@databricks.com' does not exist"

**Problem:** Username doesn't match Lakebase configuration

**Solutions:**
1. Verify your Databricks email is correct
2. Check Lakebase instance permissions
3. Make sure your user has access to the Lakebase instance

## 📝 Environment Variables Reference

After deployment, these should be set in your app:

| Variable | Source | Value |
|----------|--------|-------|
| `DATABRICKS_HOST` | workspace | `${workspace.host}` |
| `DATABRICKS_TOKEN` | workspace | `${workspace.token}` |
| `LAKEBASE_PASSWORD` | **secret** | **`${secrets.redditscope.redditkey}`** |

## ✅ Success Criteria

Your deployment is successful when:

1. ✅ `/api/v1/config-check` shows `password_source: "LAKEBASE_PASSWORD"`
2. ✅ `/api/v1/healthcheck` returns `{"status": "healthy"}`
3. ✅ `/api/v1/products` returns product data (not 500 error)
4. ✅ App logs show: `✓ Lakebase auth: Using LAKEBASE_PASSWORD`
5. ✅ No authentication errors in logs

## 🎯 Next Steps After Successful Deployment

1. Test all API endpoints:
   - Products: `/api/v1/products`
   - Search: `/api/v1/search/text`
   - Users: `/api/v1/users`
   - Recommendations: `/api/v1/search/recommendations/{user_id}`

2. Test the frontend at: `https://your-app-url/`

3. Monitor logs for any issues

4. (Optional) Merge `refactor/lakebase-tables` to `main`
