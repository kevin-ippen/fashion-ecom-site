# How to View Databricks Apps Logs

## Important: Logging Configuration for Databricks Apps

**Databricks Apps only captures logs written to `stdout` or `stderr`.**

Our app is now configured to write all logs to `stdout` using Python's `StreamHandler`:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Explicitly log to stdout
    ]
)
```

This ensures all diagnostic messages appear in the Databricks Apps UI and `/logz` endpoint.

---

## Two Ways to View Logs

### 1. Databricks Apps UI (Recommended)

**Steps:**
1. Go to your Databricks workspace
2. Navigate to **Apps** in the left sidebar
3. Find your app (e.g., "ecom-visual-search")
4. Click on the app name
5. Click the **"Logs"** tab

**What you'll see:**
- Real-time logs from your application
- All `logger.info()`, `logger.warning()`, `logger.error()` messages
- Startup diagnostic messages showing authentication configuration
- Database connection attempts and errors

### 2. /logz Endpoint

**Direct access via URL:**
```
https://your-app-url.azuredatabricksapps.com/logz
```

For example:
```
https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/logz
```

**What you'll see:**
- Text-based log viewer in your browser
- Same logs as the Databricks Apps UI
- Useful for quick checks without navigating the UI

---

## What Logs to Look For

### On App Startup

After deploying and restarting the app, look for these messages at the top of the logs:

```
================================================================================
FASHION ECOMMERCE APP STARTING
App Version: 1.0.0
Logs visible at: <your-app-url>/logz or Databricks Apps UI > Logs tab
================================================================================

ENVIRONMENT VARIABLES:
  DATABRICKS_HOST: SET
  DATABRICKS_TOKEN: SET (starts with: https://...)
  LAKEBASE_PASSWORD: SET (starts with: dapi...) or NOT SET

AUTHENTICATION STRATEGY:
  ✓ Will use LAKEBASE_PASSWORD for database authentication

If no token is set, the app will attempt to fetch from Databricks Secrets API
  Scope: redditscope
  Key: redditkey
================================================================================
```

### Key Indicators

**✅ SUCCESS - Environment Variable Set:**
```
LAKEBASE_PASSWORD: SET (starts with: dapi...)
✓ Will use LAKEBASE_PASSWORD for database authentication
```

**✅ SUCCESS - Secrets API Fallback:**
```
LAKEBASE_PASSWORD: NOT SET
⚠️  LAKEBASE_PASSWORD not set - falling back to DATABRICKS_TOKEN
⚠️  No environment variables set - attempting to fetch from Databricks Secrets API
✓ Successfully fetched password from Databricks Secrets API
✓ Lakebase auth: Using Databricks Secrets API (redditscope.redditkey) (starts with: dapi...)
```

**❌ FAILURE - No Authentication:**
```
LAKEBASE_PASSWORD: NOT SET
DATABRICKS_TOKEN: NOT SET
❌ NO AUTHENTICATION TOKEN AVAILABLE! App will fail to connect to database.
```

### Database Connection Logs

When the first request hits the database, you'll see logs from `core/config.py`:

```
✓ Lakebase auth: Using LAKEBASE_PASSWORD (env var) (starts with: dapi...)
```

Or if using the fallback:

```
⚠️  No environment variables set - attempting to fetch from Databricks Secrets API
✓ Successfully fetched password from Databricks Secrets API
```

### Error Logs

If authentication fails, you'll see:

```
ERROR: Exception in ASGI application
...
asyncpg.exceptions.InvalidPasswordError: Failed to decode token
```

This means:
- Token is set but invalid/expired
- Token format is wrong (should start with `dapi`)
- Token doesn't have permissions for the database

---

## Troubleshooting Missing Logs

### If you don't see startup logs:

**Problem:** Logs might be configured to write to a file instead of stdout/stderr.

**Solution:** We've explicitly configured `StreamHandler(sys.stdout)` in [app.py](app.py#L19-L20), so this should not be an issue.

### If logs are being truncated:

**Problem:** Azure Databricks does not persist logs when app compute shuts down.

**Solutions:**
1. Check logs immediately after app starts (before compute shuts down)
2. For persistent logging, consider:
   - Integrating with external logging services (e.g., Azure Application Insights)
   - Writing logs to Unity Catalog volumes or tables

### If you only see some logs:

**Problem:** Log level might be too high (only showing WARNING and ERROR).

**Solution:** Our app is set to `logging.INFO` level, which shows all info, warning, and error messages.

---

## Testing Log Output

### Quick Test

After deploying, immediately check logs for the startup banner:

1. **Deploy the app**
2. **Restart the app** (to trigger startup event)
3. **Within 1-2 minutes**, check logs via:
   - Databricks Apps UI > Logs tab, OR
   - Visit `https://your-app-url/logz`
4. **Look for** the `FASHION ECOMMERCE APP STARTING` banner

### If Startup Logs Don't Appear

Possible causes:
1. **App didn't restart** - Force restart from Databricks Apps UI
2. **Logs not yet flushed** - Wait 30-60 seconds and refresh
3. **Old code still running** - Verify latest commit is deployed
4. **Logging misconfigured** - Check that [app.py](app.py) has `StreamHandler(sys.stdout)`

---

## Log Levels

Our app uses these log levels:

| Level | When Used | Example |
|-------|-----------|---------|
| `INFO` | Normal operations | `✓ Using LAKEBASE_PASSWORD environment variable` |
| `WARNING` | Potential issues | `⚠️  LAKEBASE_PASSWORD not set - falling back to DATABRICKS_TOKEN` |
| `ERROR` | Failures | `❌ Failed to fetch secret from Databricks Secrets API` |

All levels will appear in the logs (we're using `logging.INFO` as the minimum level).

---

## Best Practices

1. **Check logs immediately after deployment** - Before compute shuts down
2. **Use /logz for quick checks** - Faster than navigating UI
3. **Look for the startup banner** - Confirms latest code is running
4. **Verify authentication messages** - Shows which token source is used
5. **Monitor for errors** - Database connection failures will be logged

---

## Related Files

- [app.py](app.py#L14-L23) - Logging configuration with StreamHandler
- [core/config.py](core/config.py#L56-L114) - Database authentication with detailed logging
- [core/database.py](core/database.py) - Database connection with error logging
- [SECRET_TROUBLESHOOTING.md](SECRET_TROUBLESHOOTING.md) - Troubleshooting secret injection

---

## Example Log Session

Here's what a successful startup looks like:

```
2025-12-07 15:30:45 - __main__ - INFO - ================================================================================
2025-12-07 15:30:45 - __main__ - INFO - FASHION ECOMMERCE APP STARTING
2025-12-07 15:30:45 - __main__ - INFO - App Version: 1.0.0
2025-12-07 15:30:45 - __main__ - INFO - Logs visible at: <your-app-url>/logz or Databricks Apps UI > Logs tab
2025-12-07 15:30:45 - __main__ - INFO - ================================================================================
2025-12-07 15:30:45 - __main__ - INFO - ENVIRONMENT VARIABLES:
2025-12-07 15:30:45 - __main__ - INFO -   DATABRICKS_HOST: SET
2025-12-07 15:30:45 - __main__ - INFO -   DATABRICKS_TOKEN: SET (starts with: https://...)
2025-12-07 15:30:45 - __main__ - INFO -   LAKEBASE_PASSWORD: SET (starts with: dapi1234...)
2025-12-07 15:30:45 - __main__ - INFO -
2025-12-07 15:30:45 - __main__ - INFO - AUTHENTICATION STRATEGY:
2025-12-07 15:30:45 - __main__ - INFO -   ✓ Will use LAKEBASE_PASSWORD for database authentication
2025-12-07 15:30:45 - __main__ - INFO -
2025-12-07 15:30:45 - __main__ - INFO - If no token is set, the app will attempt to fetch from Databricks Secrets API
2025-12-07 15:30:45 - __main__ - INFO -   Scope: redditscope
2025-12-07 15:30:45 - __main__ - INFO -   Key: redditkey
2025-12-07 15:30:45 - __main__ - INFO - ================================================================================

[First database request]
2025-12-07 15:30:50 - core.config - INFO - ✓ Using LAKEBASE_PASSWORD environment variable
2025-12-07 15:30:50 - core.config - INFO - ✓ Lakebase auth: Using LAKEBASE_PASSWORD (env var) (starts with: dapi1234...)

[Successful database query]
2025-12-07 15:30:51 - uvicorn.access - INFO - 200 GET /api/v1/products?page=1&page_size=5
```

This shows:
- ✅ App started successfully
- ✅ Environment variables are set
- ✅ Authentication token is available
- ✅ Database connection succeeded
- ✅ API request returned 200 OK
