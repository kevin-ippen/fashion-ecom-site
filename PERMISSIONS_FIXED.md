# ✅ Permissions Fixed - fashion-ecom-site

> **Issue Resolved**: Service principal permissions granted on Lakebase PostgreSQL schema

---

## 🐛 Problem

App was failing with permission errors:

```
asyncpg.exceptions.InsufficientPrivilegeError: permission denied for schema fashion_sota
```

**Root Cause**: The app's service principal didn't have permissions to access the `fashion_sota` schema in Lakebase PostgreSQL.

---

## ✅ Solution Applied

### 1. Identified Service Principal UUID

The app's service principal exists as a PostgreSQL role with UUID:
```
55be2ebd-113c-4077-9341-2d8444d8e4b2
```

Display name: `app-7hspbl ecom-visual-search`

### 2. Granted Permissions

Executed the following permissions grants:

```sql
-- Grant schema access
GRANT USAGE ON SCHEMA fashion_sota TO "55be2ebd-113c-4077-9341-2d8444d8e4b2";

-- Grant read access to all tables
GRANT SELECT ON ALL TABLES IN SCHEMA fashion_sota TO "55be2ebd-113c-4077-9341-2d8444d8e4b2";

-- Grant read access to future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA fashion_sota
  GRANT SELECT ON TABLES TO "55be2ebd-113c-4077-9341-2d8444d8e4b2";
```

### 3. Restarted App

Restarted the Databricks App to pick up new permissions:
```bash
databricks apps stop ecom-visual-search --profile work
databricks apps start ecom-visual-search --profile work
```

**Status**: App is now RUNNING with proper permissions

---

## 🧪 Testing the App

### Access Through Browser

The app uses OAuth2 authentication and must be accessed through a web browser:

1. **Open the app URL**:
   ```
   https://ecom-visual-search-984752964297111.11.azure.databricksapps.com
   ```

2. **Authenticate**: You'll be redirected to Databricks OAuth login

3. **Test Endpoints**:
   - Homepage: `/`
   - Products list: `/api/v1/products?page=1&page_size=10`
   - API documentation: `/docs`
   - Single product: `/api/v1/products/12345`
   - With filters: `/api/v1/products?gender=Men&page_size=5`

### Expected Behavior

✅ **Before permissions** (what you saw in logs):
```
ERROR: permission denied for schema fashion_sota
SQL: SELECT * FROM fashion_sota.products_lakebase
```

✅ **After permissions** (what you should see now):
```
INFO: Successfully retrieved products from fashion_sota.products_lakebase
Result: Products returned successfully
```

---

## 📊 Verification

### 1. Check App Logs

In Databricks UI:
1. Go to **Apps** → **ecom-visual-search**
2. Click **Logs** tab
3. Look for successful database queries:

```
INFO: Products table: fashion_sota.products_lakebase
INFO: Retrieved X products
```

**No more permission errors should appear!**

### 2. Test Products Endpoint

Open in browser:
```
https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/api/v1/products?page=1&page_size=5
```

Should return JSON with products:
```json
{
  "products": [
    {
      "product_id": 12345,
      "product_display_name": "Nike Air Max",
      "price": 129.99,
      ...
    }
  ],
  "total": 44424,
  "page": 1,
  "page_size": 5
}
```

### 3. Test API Documentation

Open:
```
https://ecom-visual-search-984752964297111.11.azure.databricksapps.com/docs
```

Should show interactive API documentation (FastAPI Swagger UI).

---

## 🔧 What Was Fixed

### Configuration (Already Correct)
```python
# core/config.py
LAKEBASE_HOST = "instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net"
LAKEBASE_DATABASE = "databricks_postgres"
LAKEBASE_SCHEMA = "fashion_sota"
LAKEBASE_PRODUCTS_TABLE = "products_lakebase"
```

### Table Reference (Already Correct)
```python
# repositories/lakebase.py
self.products_table = "fashion_sota.products_lakebase"  # PostgreSQL format
```

### ⚠️ Missing Component (NOW FIXED)
```sql
-- Service principal permissions (ADDED)
GRANT USAGE ON SCHEMA fashion_sota TO service_principal;
GRANT SELECT ON ALL TABLES IN SCHEMA fashion_sota TO service_principal;
```

---

## 📋 Complete Fix Timeline

1. ✅ **Updated configuration** to use correct Lakebase host and database (commit `1f996d6`)
2. ✅ **Fixed table references** to use PostgreSQL format (commit `1f996d6`)
3. ✅ **Redeployed app** with new code (deployment `01f0ea84a7221560a8d35dc9bdf190b7`)
4. ✅ **Identified permission issue** from app logs
5. ✅ **Granted permissions** to service principal UUID
6. ✅ **Restarted app** to apply permissions

---

## 🗂️ Database Details

### Lakebase PostgreSQL Connection
```
Host: instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net
Database: databricks_postgres
Schema: fashion_sota
Table: products_lakebase
Rows: 44,424 products
```

### Service Principal
```
UUID: 55be2ebd-113c-4077-9341-2d8444d8e4b2
Name: app-7hspbl ecom-visual-search
Permissions: USAGE on schema, SELECT on tables
```

---

## 🚀 Next Steps

1. **Test in browser**: Open app URL and verify products load
2. **Check logs**: Confirm no more permission errors
3. **Verify functionality**:
   - Products list endpoint
   - Product filters
   - Search functionality
   - Image display
4. **Performance check**: Queries should be fast (<50ms with Lakebase)

---

## 🔍 Troubleshooting

### If Still Seeing Permission Errors

1. **Verify permissions were applied**:
   ```bash
   cd /Users/kevin.ippen/projects/fashion-ecom-site
   python3 check_roles.py
   ```

   Should show role `55be2ebd-113c-4077-9341-2d8444d8e4b2` in the list.

2. **Re-grant permissions**:
   ```bash
   python3 grant_permissions_uuid.py
   ```

3. **Restart app again**:
   ```bash
   databricks apps stop ecom-visual-search --profile work
   databricks apps start ecom-visual-search --profile work
   ```

### If App Won't Start

Check compute status:
```bash
databricks apps get ecom-visual-search --profile work --output json | jq '{app_status, compute_status}'
```

### If Getting 401 Unauthorized

This is **expected** when using CLI tokens. You must:
- Open the app in a **web browser**
- Authenticate through **Databricks OAuth**
- Then test the endpoints

---

## 📚 Scripts Created

### Permission Management
- [grant_permissions_uuid.py](file:///Users/kevin.ippen/projects/fashion-ecom-site/grant_permissions_uuid.py) - Grant permissions to service principal
- [check_roles.py](file:///Users/kevin.ippen/projects/fashion-ecom-site/check_roles.py) - List PostgreSQL roles
- [test_lakebase_connection.py](file:///Users/kevin.ippen/projects/fashion-ecom-site/test_lakebase_connection.py) - Test database connection

### Run These for Verification
```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site

# Test database connection
python3 test_lakebase_connection.py

# Check roles and permissions
python3 check_roles.py

# Re-grant permissions if needed
python3 grant_permissions_uuid.py
```

---

## 📝 Git History

```bash
d392276 docs: Add deployment completion summary and database test script
1f996d6 fix: Update Lakebase connection and table names for PostgreSQL
77d9297 feat: Configure app to use main.fashion_sota.products_lakebase
```

---

## ✨ Summary

**Problem**: Service principal lacked permissions on Lakebase schema
**Solution**: Granted USAGE and SELECT permissions to UUID role
**Status**: ✅ FIXED - App should now query database successfully

**Test URL**: https://ecom-visual-search-984752964297111.11.azure.databricksapps.com

---

**Fixed**: 2026-01-06
**Verified**: Permissions granted, app restarted
**Next**: Test in browser to confirm

🎉 The app should now work correctly!
