# Lakebase Permissions - FINAL SOLUTION

**Date**: 2026-01-09
**Issue**: `InsufficientPrivilegeError: permission denied for schema fashion_sota`
**Status**: ✅ RESOLVED

---

## Root Cause Analysis

The app was failing with PostgreSQL permission errors because **Lakebase requires native PostgreSQL grants**, not just Unity Catalog permissions.

### Key Learning: Two Separate Permission Layers

When connecting to Lakebase via PostgreSQL client (SQLAlchemy/asyncpg):

```
┌─────────────────────────────────────────────────────────────┐
│  Unity Catalog Layer                                        │
│  - Controls access to UC objects (schemas, tables, volumes) │
│  - Managed via Databricks SDK (w.grants.update())           │
│  - Grants: USAGE, SELECT, etc.                              │
└─────────────────────────────────────────────────────────────┘
                           ↓
                  NOT SUFFICIENT FOR
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL Layer (Inside Lakebase)                         │
│  - Controls PostgreSQL database access                       │
│  - Managed via native PostgreSQL GRANT statements           │
│  - Grants: USAGE ON SCHEMA, SELECT ON TABLE                 │
└─────────────────────────────────────────────────────────────┘
```

**Both layers must be configured for the app to access Lakebase tables.**

---

## The Solution

### 1. Connect to Lakebase PostgreSQL Directly

Used Python's `asyncpg` library to connect as an admin user:

```python
import asyncpg
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
token = w.config.oauth_token().access_token

conn = await asyncpg.connect(
    host="instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net",
    port=5432,
    user="kevin.ippen@databricks.com",  # Admin user
    password=token,  # OAuth token
    database="databricks_postgres",
    ssl='require'
)
```

### 2. Grant Native PostgreSQL Privileges

Ran standard PostgreSQL `GRANT` statements:

```python
app_pg_role = "55be2ebd-113c-4077-9341-2d8444d8e4b2"  # Service principal client ID

# Grant schema usage
await conn.execute(f'GRANT USAGE ON SCHEMA fashion_sota TO "{app_pg_role}"')

# Grant table select
await conn.execute(f'GRANT SELECT ON TABLE fashion_sota.products_lakebase TO "{app_pg_role}"')
await conn.execute(f'GRANT SELECT ON TABLE fashion_sota.users_lakebase TO "{app_pg_role}"')
```

### 3. Verify Permissions

```python
# Check privileges
has_schema_usage = await conn.fetchval(
    f"SELECT has_schema_privilege('{app_pg_role}', 'fashion_sota', 'USAGE')"
)
# Result: True ✅

has_products_select = await conn.fetchval(
    f"SELECT has_table_privilege('{app_pg_role}', 'fashion_sota.products_lakebase', 'SELECT')"
)
# Result: True ✅

has_users_select = await conn.fetchval(
    f"SELECT has_table_privilege('{app_pg_role}', 'fashion_sota.users_lakebase', 'SELECT')"
)
# Result: True ✅
```

---

## What Didn't Work (and Why)

### ❌ Attempt 1: Unity Catalog Grants via Databricks SQL

```python
# These grants apply to UC layer, NOT PostgreSQL layer
w.grants.update(
    securable_type=SecurableType.SCHEMA,
    full_name="main.fashion_sota",
    changes=[PermissionsChange(principal=sp_id, add=[Privilege.USAGE])]
)
```

**Why it failed**: UC grants control access to Unity Catalog objects, but don't apply to the PostgreSQL database inside Lakebase.

### ❌ Attempt 2: Adding UC Permissions to app.yaml

```yaml
# app.yaml (INCORRECT APPROACH)
resources:
  uc_securable:
    - securable_type: SCHEMA
      securable_full_name: main.fashion_sota
      permission: USAGE
```

**Why it failed**: This broke the app entirely. UC permissions in app.yaml don't translate to PostgreSQL grants and caused conflicts.

### ❌ Attempt 3: PostgreSQL GRANT via Databricks SQL Warehouse

```sql
-- Run via Databricks SQL warehouse
GRANT USAGE ON SCHEMA fashion_sota TO `55be2ebd-113c-4077-9341-2d8444d8e4b2`;
```

**Why it failed**: This applied UC grants, not native PostgreSQL grants inside the Lakebase instance.

---

## The Working Solution

### Connect Directly to Lakebase PostgreSQL

**Must use native PostgreSQL client** (psql, asyncpg, etc.) to connect to the Lakebase instance:

```python
import asyncpg

conn = await asyncpg.connect(
    host="<lakebase-instance-host>",
    port=5432,
    user="<admin-user>@databricks.com",  # Must be admin/owner
    password="<oauth-token>",
    database="databricks_postgres",
    ssl='require'
)

# Run native PostgreSQL GRANT statements
await conn.execute('GRANT USAGE ON SCHEMA fashion_sota TO "<service-principal-id>"')
await conn.execute('GRANT SELECT ON TABLE fashion_sota.products_lakebase TO "<service-principal-id>"')
```

---

## Final Configuration

### App Service Principal

- **Name**: `app-7hspbl ecom-visual-search`
- **Client ID**: `55be2ebd-113c-4077-9341-2d8444d8e4b2`
- **Service Principal ID**: `142985553565381`

### Lakebase Connection

- **Instance**: `retail-consumer-goods`
- **Host**: `instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net`
- **Database**: `databricks_postgres`
- **Schema**: `fashion_sota`
- **Tables**: `products_lakebase`, `users_lakebase`

### PostgreSQL User (for app connections)

- **Role Name**: `55be2ebd-113c-4077-9341-2d8444d8e4b2` (service principal client ID)
- **Privileges**:
  - `USAGE` on schema `fashion_sota` ✅
  - `SELECT` on table `fashion_sota.products_lakebase` ✅
  - `SELECT` on table `fashion_sota.users_lakebase` ✅

### App Configuration (app.yaml)

```yaml
command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

resources:
  uc_securable:
    # Only declare Volume permissions, NOT schema/table permissions
    - securable_type: VOLUME
      securable_full_name: main.fashion_sota.product_images
      privilege: READ_VOLUME
```

**CRITICAL**: Do not add SCHEMA/TABLE UC permissions to app.yaml for Lakebase tables!

---

## Verification Steps

### 1. Check PostgreSQL Privileges

```python
import asyncpg
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
token = w.config.oauth_token().access_token

conn = await asyncpg.connect(
    host="instance-51628d83-d2d1-4cba-af04-af2b5624ddc0.database.azuredatabricks.net",
    port=5432,
    user="kevin.ippen@databricks.com",
    password=token,
    database="databricks_postgres",
    ssl='require'
)

app_role = "55be2ebd-113c-4077-9341-2d8444d8e4b2"

# Verify privileges
print(await conn.fetchval(f"SELECT has_schema_privilege('{app_role}', 'fashion_sota', 'USAGE')"))
# Expected: True

print(await conn.fetchval(f"SELECT has_table_privilege('{app_role}', 'fashion_sota.products_lakebase', 'SELECT')"))
# Expected: True

print(await conn.fetchval(f"SELECT has_table_privilege('{app_role}', 'fashion_sota.users_lakebase', 'SELECT')"))
# Expected: True
```

### 2. Check App Deployment

```bash
databricks apps get ecom-visual-search --output json | jq '{
  name,
  deployment_id: .active_deployment.deployment_id,
  status: .active_deployment.status.state,
  deployed_at: .active_deployment.update_time
}'
```

Expected output:
```json
{
  "name": "ecom-visual-search",
  "deployment_id": "01f0ed8ddc901d5493c99336dc742933",
  "status": "SUCCEEDED",
  "deployed_at": "2026-01-09T19:04:53Z"
}
```

### 3. Test API Endpoints

The following endpoints should now work without permission errors:

```bash
# Products endpoint (queries fashion_sota.products_lakebase)
GET /api/v1/products?page=1&page_size=10

# Users/personas endpoint (queries fashion_sota.users_lakebase)
GET /api/v1/users/personas

# Recommendations (queries both tables + vector search)
GET /api/v1/search/recommendations/user_001305?limit=10
```

---

## Best Practices

### 1. Keep app.yaml Simple for Lakebase

```yaml
# ✅ CORRECT - Only declare Volume permissions
resources:
  uc_securable:
    - securable_type: VOLUME
      securable_full_name: main.fashion_sota.product_images
      privilege: READ_VOLUME
```

```yaml
# ❌ WRONG - Don't add SCHEMA/TABLE for Lakebase
resources:
  uc_securable:
    - securable_type: SCHEMA
      securable_full_name: main.fashion_sota
      permission: USAGE  # This breaks Lakebase connection!
```

### 2. Manage PostgreSQL Grants Separately

- Use native PostgreSQL GRANT statements
- Connect via asyncpg, psql, or other PostgreSQL client
- Grant privileges to service principal client ID as the role name
- Run grants as admin user with proper permissions

### 3. Document Service Principal Permissions

Keep a record of:
- Service principal client ID
- PostgreSQL role name (same as client ID)
- Granted privileges (USAGE, SELECT, etc.)
- Lakebase instance and database names

---

## Implementation Improvements (Future)

Based on the Databricks Lakebase documentation, consider implementing:

### 1. Background Token Refresh

```python
async def refresh_token_background():
    """Refresh OAuth tokens every 50 minutes"""
    while True:
        await asyncio.sleep(50 * 60)  # 50 minutes
        cred = workspace_client.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[database_instance.name],
        )
        postgres_password = cred.token
```

### 2. SQLAlchemy Event Handler for Token Injection

```python
@event.listens_for(engine.sync_engine, "do_connect")
def provide_token(dialect, conn_rec, cargs, cparams):
    """Inject fresh token for each new connection"""
    global postgres_password
    cparams["password"] = postgres_password
```

### 3. Connection Pool Configuration

```python
engine = create_async_engine(
    url,
    pool_size=5,           # Base connections
    max_overflow=10,       # Additional under load
    pool_recycle=3600,     # Recycle every hour
    pool_pre_ping=False,   # Disable (tokens handle this)
)
```

See `LAKEBASE_CONNECTION_GUIDE.md` (from Databricks docs) for full implementation details.

---

## Troubleshooting

### Issue: Permission Denied After Grants

**Symptom**: Still see `InsufficientPrivilegeError` after running GRANT statements

**Solution**:
1. Verify you connected to the correct Lakebase instance
2. Check you're granting to the correct role (service principal client ID)
3. Verify grants were applied: `SELECT has_schema_privilege(...)`
4. Restart the app to clear connection pools

### Issue: app.yaml Changes Break App

**Symptom**: App stops working after adding UC permissions to app.yaml

**Solution**:
1. Revert app.yaml to simple version (only VOLUME permissions)
2. Manage Lakebase permissions via native PostgreSQL GRANT statements
3. Don't declare SCHEMA/TABLE in app.yaml for Lakebase tables

### Issue: Token Expiration

**Symptom**: App works initially but fails after 1 hour

**Solution**:
1. Implement background token refresh (see Future Improvements)
2. Use `workspace_client.database.generate_database_credential()` for Lakebase tokens
3. Set up SQLAlchemy event handler to inject fresh tokens

---

## Summary

✅ **Final Status**: ALL PERMISSIONS WORKING

**Deployment**: 01f0ed8ddc901d5493c99336dc742933 - SUCCEEDED

**Permissions Applied**:
- ✅ Native PostgreSQL grants on Lakebase instance
  - `GRANT USAGE ON SCHEMA fashion_sota`
  - `GRANT SELECT ON TABLE fashion_sota.products_lakebase`
  - `GRANT SELECT ON TABLE fashion_sota.users_lakebase`
- ✅ Unity Catalog grants (via SDK, separate from app.yaml)
- ✅ Model Serving endpoint access (CAN_QUERY)
- ✅ Vector Search index access (SELECT)
- ✅ Volume access (READ_VOLUME)

**Key Takeaway**:
For Lakebase access via PostgreSQL clients, **native PostgreSQL GRANT statements are required**. Unity Catalog permissions alone are not sufficient.
