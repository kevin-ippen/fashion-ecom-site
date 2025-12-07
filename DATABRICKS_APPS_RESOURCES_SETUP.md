# Databricks Apps Resources Setup - The Correct Way

**CRITICAL**: This is the CORRECT way to handle secrets in Databricks Apps!

---

## 🎯 **Why Previous Approaches Failed**

**Wrong approach** (doesn't work):
```yaml
env:
  - name: LAKEBASE_PASSWORD
    value: ${secrets.redditscope.redditkey}  # ❌ NOT EXPANDED!
```

**Problem**: Databricks Apps **do not expand** `${secrets.scope.key}` syntax. The env var gets the **literal string**, not the secret value.

**Correct approach** (works):
```yaml
env:
  - name: LAKEBASE_PASSWORD
    valueFrom: lakebase-token  # ✅ References app resource
```

**Solution**: Declare resources in Apps UI, reference them with `valueFrom`. Databricks injects actual values at runtime.

---

## 📋 **Step-by-Step Resource Setup**

### **Step 1: Access Your Databricks App**

1. Go to your Databricks workspace
2. Navigate to **Apps** in the left sidebar
3. Find and click on your app (e.g., "ecom-visual-search")

### **Step 2: Add Secret Resource**

1. In your app page, find the **"Resources"** tab or section
2. Click **"Add Resource"**
3. Select **"Secret"**
4. Configure:
   - **Resource Key**: `lakebase-token` (this name goes in app.yaml `valueFrom`)
   - **Scope**: `redditscope`
   - **Key**: `redditkey`
   - **Permission**: `Can read`
5. Click **"Save"** or **"Add"**

**What this does**: Grants your app permission to read the secret and makes it available for injection.

### **Step 3: Update app.yaml**

Your [app.yaml](app.yaml) is already updated to use `valueFrom`:

```yaml
env:
  - name: LAKEBASE_PASSWORD
    valueFrom: lakebase-token  # Matches resource key from Step 2
```

**Important**: The `valueFrom` value **must exactly match** the resource key you set in Step 2.

### **Step 4: Deploy and Restart**

1. **Deploy latest code**:
   ```bash
   databricks apps deploy <your-app-name>
   ```

2. **Or via UI**: Update > Deploy

3. **Restart the app** (required for env changes to take effect)

### **Step 5: Verify**

Check logs at `https://your-app-url/logz`:

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

**Expected**: JSON with product data ✅

---

## 🔐 **How Databricks Apps Inject Secrets**

### **Auto-Injected Variables** (always available):

Your app automatically receives these from the platform:

- `DATABRICKS_HOST` - Workspace URL
- `DATABRICKS_CLIENT_ID` - Service principal client ID
- `DATABRICKS_CLIENT_SECRET` - Service principal client secret

**Use these for OAuth authentication** (preferred over PAT tokens):

```python
from databricks.sdk import WorkspaceClient

# Uses auto-injected service principal credentials
w = WorkspaceClient()
secret = w.dbutils.secrets.get(scope="redditscope", key="redditkey")
```

### **Resource-Injected Variables** (via `valueFrom`):

Variables you configure with `valueFrom` in app.yaml:

- `LAKEBASE_PASSWORD` - From the secret resource we added
- `DATABRICKS_WAREHOUSE_ID` - If you add a SQL Warehouse resource

---

## ✅ **Recommended Authentication Pattern**

### **For Lakebase PostgreSQL** (your current use case):

Use the PAT token from the secret resource:

```python
# In core/config.py
LAKEBASE_PASSWORD = os.getenv("LAKEBASE_PASSWORD")  # Injected via valueFrom
```

### **For Databricks APIs** (SDK, Secrets, etc.):

Use service principal OAuth (auto-injected credentials):

```python
from databricks.sdk import WorkspaceClient

# Automatically uses DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET
w = WorkspaceClient()
```

**Why**: Service principal auth is more secure, doesn't require PAT token storage, and is the recommended pattern for Databricks Apps.

---

## 🐛 **Troubleshooting**

### **If env var is still not set after adding resource:**

**Check these**:

1. **Resource key matches**: `valueFrom: lakebase-token` in app.yaml matches resource key in UI
2. **App restarted**: Changes only take effect after restart
3. **Secret exists**: Scope `redditscope` and key `redditkey` exist
4. **Permissions**: Service principal has `Can read` on the secret scope
5. **Deploy succeeded**: Check deployment logs for errors

### **Common errors:**

**Error**: `LAKEBASE_PASSWORD: NOT SET`
- **Cause**: Resource not added or `valueFrom` doesn't match resource key
- **Fix**: Verify resource key in Apps UI matches `valueFrom` in app.yaml

**Error**: `Permission denied accessing secret`
- **Cause**: Service principal lacks permission
- **Fix**: Grant `Can read` permission on secret scope to app's service principal

### **How to verify resources are configured:**

1. In Apps UI, go to your app
2. Check **"Resources"** tab
3. Should see: `lakebase-token` → Secret → `redditscope.redditkey` → `Can read`
4. Check **"Environment"** tab after deployment
5. Should see `LAKEBASE_PASSWORD` listed (value hidden for security)

---

## 📚 **Additional Resources (Optional)**

### **If you need SQL Warehouse access:**

1. **Add SQL Warehouse resource**:
   - Resource Key: `sql-warehouse`
   - Select your warehouse
   - Permission: `Can use`

2. **Reference in app.yaml**:
   ```yaml
   env:
     - name: DATABRICKS_WAREHOUSE_ID
       valueFrom: sql-warehouse
   ```

3. **Use in code**:
   ```python
   from databricks import sql

   conn = sql.connect(
       server_hostname=os.getenv("DATABRICKS_HOST"),
       http_path=os.getenv("DATABRICKS_WAREHOUSE_ID"),
       auth_type="databricks-oauth",  # Uses auto-injected service principal
       client_id=os.getenv("DATABRICKS_CLIENT_ID"),
       client_secret=os.getenv("DATABRICKS_CLIENT_SECRET"),
   )
   ```

---

## 🎉 **Summary**

**What you need to do**:

1. ✅ **Add Secret resource** in Databricks Apps UI
   - Resource Key: `lakebase-token`
   - Scope: `redditscope`, Key: `redditkey`
   - Permission: `Can read`

2. ✅ **app.yaml already updated** (commit `ae3f1e9`)
   - Uses `valueFrom: lakebase-token`

3. ✅ **Deploy and restart**
   - `databricks apps deploy <your-app-name>`
   - Restart the app

4. ✅ **Test the API**
   - `curl https://your-app-url/api/v1/products`

**This is the correct, supported way to use secrets in Databricks Apps!** 🚀

---

## 📖 **References**

- Databricks Apps Documentation: https://docs.databricks.com/en/dev-tools/databricks-apps/
- App Resources: https://docs.databricks.com/en/dev-tools/databricks-apps/app-resources.html
- Authentication: https://docs.databricks.com/en/dev-tools/auth.html
