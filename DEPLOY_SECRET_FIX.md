# Deploy Secret Authentication Fix

## What Changed

The app now has an **automatic three-tier authentication fallback** that eliminates secret injection issues:

1. **LAKEBASE_PASSWORD** env var (from app.yaml) - preferred
2. **DATABRICKS_TOKEN** env var (workspace token) - fallback #1
3. **Databricks Secrets API** (direct fetch) - fallback #2 ← **NEW**

If the app.yaml secret reference `${secrets.redditscope.redditkey}` doesn't work, the app will automatically fetch the secret directly from the Databricks Secrets API using the Databricks SDK.

## Changes Made

**File: [core/config.py](core/config.py:56-114)**

The `lakebase_url` property now implements the three-tier fallback strategy. When building the database connection URL, it:

1. Checks if `LAKEBASE_PASSWORD` is set
2. If not, checks if `DATABRICKS_TOKEN` is set
3. If neither, calls `WorkspaceClient().dbutils.secrets.get(scope="redditscope", key="redditkey")`

## How to Deploy

### Step 1: Deploy the Code

```bash
# From your local machine
cd /Users/kevin.ippen/projects/fashion-ecom-site

# Make sure you have the latest code
git status

# Deploy to Databricks (adjust command based on your setup)
# Option A: Using Databricks CLI
databricks apps deploy <your-app-name>

# Option B: Via Databricks UI
# - Go to your app in the workspace
# - Click "Update" or "Redeploy"
# - Select the branch with these changes
```

### Step 2: Restart the App

```bash
# Via CLI
databricks apps restart <your-app-name>

# Or via UI
# - Go to your app
# - Click "Restart"
```

### Step 3: Check the Logs

Look for these SUCCESS messages in your app startup logs:

```
✓ Using LAKEBASE_PASSWORD environment variable
  (starts with: dapi...)
```

**OR** (if app.yaml secret injection didn't work):

```
⚠️  No environment variables set - attempting to fetch from Databricks Secrets API
✓ Successfully fetched password from Databricks Secrets API
  (starts with: dapi...)
```

### Step 4: Test the API

```bash
# Test products endpoint
curl https://your-app-url/api/v1/products?page=1&page_size=5

# Check configuration
curl https://your-app-url/api/v1/config-check
```

## Expected Behavior

### ✅ Success Indicators

1. **Logs show authentication succeeded:**
   - `✓ Using LAKEBASE_PASSWORD environment variable` OR
   - `✓ Successfully fetched password from Databricks Secrets API`

2. **Database connection works:**
   - `/api/v1/products` returns product data (not 500 error)
   - `/api/v1/config-check` shows password source

3. **No authentication errors:**
   - No `InvalidPasswordError` in logs
   - No `Failed to decode token` messages

### ❌ Potential Issues

**If you see:** `❌ Failed to fetch secret from Databricks Secrets API`

**Possible causes:**
1. Service principal doesn't have READ permission on `redditscope`
2. Secret `redditkey` doesn't exist in scope `redditscope`
3. Databricks SDK not configured properly

**To fix:**
```bash
# Verify secret exists
databricks secrets list-secrets --scope redditscope

# Verify permissions
databricks secrets list-acls --scope redditscope

# Grant permission if needed
databricks secrets put-acl --scope redditscope --principal <your-app-principal> --permission READ
```

## Why This Works

The previous approach relied on app.yaml secret injection:

```yaml
env:
  - name: LAKEBASE_PASSWORD
    value: ${secrets.redditscope.redditkey}
```

This **should** work but has proven unreliable in some Databricks Apps environments.

The new approach **bypasses this entirely** by fetching the secret at runtime using the Databricks SDK, which:
- Uses the app's service principal identity
- Accesses the Secrets API directly
- Doesn't depend on environment variable injection
- Is more reliable and explicit

## Rollback Plan

If this doesn't work, you can revert to the previous version:

```bash
git log --oneline -5  # Find the commit hash before this change
git revert <commit-hash>
git push
# Redeploy the app
```

Then we can investigate alternative approaches (e.g., setting env var directly in app settings).

## Questions?

If you still see authentication errors after deploying:

1. **Share the startup logs** - Look for the section with `===` lines showing authentication status
2. **Share any error messages** - Especially `InvalidPasswordError` or Secrets API errors
3. **Run config-check endpoint** - `curl https://your-app-url/api/v1/config-check`

This will help diagnose if the issue is:
- Secret access permissions
- Token validity
- Database configuration
- Something else entirely
