# Troubleshooting Databricks Secret Injection

## Current Issue

The PAT token works and the secret exists, but `LAKEBASE_PASSWORD` isn't being injected into the app's environment variables.

## Step 1: Check Startup Logs

After deploying the latest code (commit 94d61fa), check your app logs for these lines on startup:

```
=============================================================================
FASHION ECOMMERCE APP STARTING
=============================================================================
DATABRICKS_HOST: SET
DATABRICKS_TOKEN: SET (starts with: https://...)
LAKEBASE_PASSWORD: SET (starts with: dapi...) or NOT SET  ← KEY LINE
✓ Will use LAKEBASE_PASSWORD for database authentication
=============================================================================
```

**If you see `LAKEBASE_PASSWORD: NOT SET`** → The secret isn't being injected from app.yaml

## Step 2: Verify app.yaml Syntax

Check that [app.yaml](app.yaml) has exactly this:

```yaml
env:
  - name: LAKEBASE_PASSWORD
    value: ${secrets.redditscope.redditkey}
```

**Common issues:**
- Extra spaces or tabs
- Wrong secret scope name
- Wrong key name
- Syntax errors in YAML

## Step 3: Verify Secret Permissions

Even though you've granted permissions, double-check:

```bash
# List ACLs for the secret scope
databricks secrets list-acls --scope redditscope

# Should show your app service principal with READ permission
```

## Step 4: Alternative Approach - Fetch Secret in Code

If app.yaml secret injection isn't working, we can fetch the secret directly in Python code:

### Option A: Using Databricks SDK (Recommended)

Update `core/config.py` to fetch the secret at runtime:

```python
@property
def lakebase_url(self) -> str:
    import logging
    logger = logging.getLogger(__name__)

    # Try environment variable first
    password = self.LAKEBASE_PASSWORD or self.DATABRICKS_TOKEN

    # If still not set, try fetching from secrets API
    if not password:
        try:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            password = w.dbutils.secrets.get(scope="redditscope", key="redditkey")
            logger.info("✓ Retrieved LAKEBASE_PASSWORD from Databricks secrets API")
        except Exception as e:
            logger.error(f"Failed to fetch secret: {e}")
            password = ""

    return f"postgresql+asyncpg://{self.LAKEBASE_USER}:{password}@{self.LAKEBASE_HOST}:{self.LAKEBASE_PORT}/{self.LAKEBASE_DATABASE}"
```

### Option B: Set as Environment Variable in App Settings

Instead of using app.yaml, set the environment variable directly in Databricks App settings:

1. Go to your app in Databricks workspace
2. Click "Settings" or "Environment Variables"
3. Add:
   - Name: `LAKEBASE_PASSWORD`
   - Value: `<paste your PAT here>`
4. Restart the app

**Pros:** Direct and simple
**Cons:** Token visible in UI, not using secrets management

## Step 5: Verify Secret Contents

Make sure the secret contains the right value:

```bash
# Get the secret value (will be displayed in terminal!)
databricks secrets get --scope redditscope --key redditkey

# Should output something like:
# dapi1234567890abcdef...
```

**Check:**
- Starts with `dapi` (Databricks Personal Access Token)
- No extra spaces or newlines
- Not expired

## Step 6: Test Secret Access from App

If you can't get logs, try this temporary debug endpoint:

Add to `routes/v1/healthcheck.py`:

```python
@router.get("/debug-secret")
async def debug_secret():
    """Temporary endpoint to test secret access"""
    import os
    from databricks.sdk import WorkspaceClient

    # Try environment variable
    env_value = os.getenv("LAKEBASE_PASSWORD")

    # Try secrets API
    try:
        w = WorkspaceClient()
        api_value = w.dbutils.secrets.get(scope="redditscope", key="redditkey")
        api_status = f"✓ Got secret (starts with: {api_value[:8]}...)"
    except Exception as e:
        api_status = f"❌ Failed: {str(e)}"

    return {
        "env_variable": "✓ Set" if env_value else "❌ Not set",
        "env_preview": env_value[:8] + "..." if env_value else None,
        "secrets_api": api_status
    }
```

Then visit `/api/v1/debug-secret` to see what's available.

**IMPORTANT:** Remove this endpoint after debugging (it exposes token info)!

## Step 7: Check Databricks Apps Version

Some versions of Databricks Apps might have bugs with secret injection. Check:

```bash
databricks --version
```

Make sure you're on a recent version (0.200.0+).

## Step 8: Alternative - Use Service Principal Token

Instead of a Personal Access Token, use a Service Principal token:

1. Create a service principal in Databricks
2. Generate a token for the service principal
3. Store token in secret: `databricks secrets put-secret --scope redditscope --key redditkey --string-value "dapi..."`
4. Grant the service principal access to Lakebase database

Service principal tokens don't expire unless explicitly revoked.

## Next Steps

1. **Deploy the latest code** (commit 94d61fa) - has startup logging
2. **Restart the app**
3. **Check startup logs** for the diagnostic output
4. **Share the log output** showing:
   - Is `LAKEBASE_PASSWORD` SET or NOT SET?
   - What are the first 8 characters?

Based on that, we'll know if it's:
- ❌ Secret injection not working → Use Option A (fetch in code)
- ✓ Secret is set but invalid → Check token validity/permissions
- ✓ Secret is set and valid → Check database name/host/permissions

## Common Databricks Apps Secret Issues

1. **Scope not accessible:** App doesn't have READ permission on scope
2. **Wrong syntax:** Typo in scope/key name
3. **Timing issue:** Secret added after app started (need restart)
4. **Databricks Apps version:** Older versions might not support secret injection
5. **Service principal:** If running as service principal, need different auth method

## Test Matrix

| Test | Command | Expected Result |
|------|---------|----------------|
| Secret exists | `databricks secrets get --scope redditscope --key redditkey` | Shows token starting with `dapi` |
| ACL permission | `databricks secrets list-acls --scope redditscope` | Shows app principal with READ |
| Env var set | Check startup logs | `LAKEBASE_PASSWORD: SET (starts with: dapi...)` |
| Token valid | Test with psql manually | Connection succeeds |
| Database access | Service principal permissions | Can connect to database: main |

Work through this matrix to identify exactly where the issue is!
