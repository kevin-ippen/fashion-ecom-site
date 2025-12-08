# Lakebase Password Setup

## Critical Discovery

**The password for Lakebase is NOT a Databricks PAT token!**

Based on the Lakebase connection details, the authentication requires:
- Username: `kevin.ippen@databricks.com`
- Password: `${PGPASSWORD}` (a PostgreSQL password specific to Lakebase)
- Database: `databricks_postgres` (NOT `main`)

## What We Were Doing Wrong

### Before:
```python
# ❌ Wrong: Using Databricks PAT token (dapi...)
LAKEBASE_PASSWORD = os.getenv("LAKEBASE_PASSWORD")  # Was a dapi... token
```

### After:
```python
# ✅ Correct: Use Lakebase PostgreSQL password
LAKEBASE_PASSWORD = os.getenv("LAKEBASE_PASSWORD")  # Should be PGPASSWORD from Lakebase UI
```

## How to Get the Lakebase Password

### Option 1: Check Lakebase UI (Most Likely)

The Lakebase instance page should have:
1. Connection details (which you shared)
2. A section to **generate/view a PostgreSQL password**
3. Or a "Show Password" button near the connection examples

**Look for**:
- "Generate Password" button
- "Reset Password" option
- "Database Credentials" section
- "PostgreSQL Password" field

### Option 2: Set a New Password (If Supported)

Some Lakebase UIs allow you to:
1. Set a custom PostgreSQL password for your user
2. This password is then used as `PGPASSWORD`

### Option 3: Check Databricks Workspace Settings

The password might be in:
- Workspace admin settings
- SQL admin console
- Lakebase instance configuration page

## Where to Store the Password

Once you have the correct PGPASSWORD:

### 1. Update the Databricks Secret Scope

```bash
# Replace the current PAT token with the actual PGPASSWORD
databricks secrets put --scope redditscope --key redditkey
# Paste the PGPASSWORD when prompted (NOT a dapi... token)
```

### 2. Verify the Secret

```bash
# This should NOT start with "dapi"
databricks secrets get --scope redditscope --key redditkey
```

### 3. Redeploy the Databricks App

The app will automatically pick up the new password via the resource binding:

```yaml
env:
  - name: LAKEBASE_PASSWORD
    valueFrom: lakebase-token  # Points to redditscope/redditkey
```

## Testing the Connection

### Test with psql (from your local machine):

```bash
# Set the password in environment
export PGPASSWORD="<your-lakebase-password>"

# Connect
psql "host=instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net \
user=kevin.ippen@databricks.com \
dbname=databricks_postgres \
port=5432 \
sslmode=require"
```

If this works, then the password is correct and will work in the app.

## Updated Configuration

The [core/config.py](core/config.py#L29) has been updated:

```python
LAKEBASE_DATABASE: str = os.getenv("LAKEBASE_DATABASE", "databricks_postgres")
```

## Connection Examples from Lakebase UI

### PSQL:
```bash
psql "host=instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net \
user=kevin.ippen@databricks.com \
dbname=databricks_postgres \
port=5432 \
sslmode=require"
```

### JDBC:
```
jdbc:postgresql://kevin.ippen%40databricks.com:${PGPASSWORD}@instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net:5432/databricks_postgres?sslmode=require
```

Note: Both examples reference `${PGPASSWORD}` which must be set as an environment variable.

## Next Steps

1. **Find the PGPASSWORD** in the Lakebase UI
2. **Update the secret** in `redditscope/redditkey` with the correct password
3. **Test locally** with psql before deploying
4. **Redeploy** the Databricks App
5. **Verify** the app can connect to Lakebase

## Questions to Ask Your Lakebase Admin

If you can't find the password:
1. "Where do I find or generate the PostgreSQL password for my Lakebase instance?"
2. "Is there a 'Show Password' or 'Generate Password' option in the Lakebase UI?"
3. "Do I need to reset the password for user `kevin.ippen@databricks.com`?"
4. "Can you provide the PGPASSWORD that should be used for programmatic access?"

## OAuth Status

The OAuth approach (`/api/2.0/token/generate`) may not be necessary if the correct PGPASSWORD works. However, if you want to explore OAuth further after fixing the password issue, ask:
- "Does Lakebase support OAuth token authentication instead of passwords?"
- "What's the correct API endpoint for generating Lakebase access tokens?"
