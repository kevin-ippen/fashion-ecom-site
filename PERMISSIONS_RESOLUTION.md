# Permissions Resolution - Complete Fix

**Date**: 2026-01-09
**App**: ecom-visual-search
**Deployment**: 01f0ed87f4931962ab7993aa9d8d2a23
**Status**: ✅ ALL ISSUES RESOLVED

---

## Issues Identified

Based on log analysis, the app was experiencing **two separate permission issues** causing 500 errors:

### Issue 1: Model Serving Endpoint - 403 PERMISSION_DENIED
```
CLIP Model Serving endpoint error: HTTP 403
POST /api/v1/search/text → 500 Internal Server Error
```
**Root Cause**: Service principal lacked `CAN_QUERY` permission on `fashionclip-endpoint`

### Issue 2: Database Schema Access - InsufficientPrivilegeError
```
asyncpg.exceptions.InsufficientPrivilegeError: permission denied for schema fashion_sota
SELECT * FROM fashion_sota.users_lakebase WHERE user_id = $1
GET /api/v1/users/{id} → 500 Internal Server Error
```
**Root Cause**: Missing PostgreSQL-level grants on Lakebase schema and tables

---

## Solutions Applied

### 1. Model Serving Endpoint Permission ✅

**Granted via SDK**:
```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.iam import AccessControlRequest, PermissionLevel

w = WorkspaceClient()
w.serving_endpoints.update_permissions(
    serving_endpoint_id="522f11c3f6164ad4b09d2d372499e99d",  # fashionclip-endpoint
    access_control_list=[
        AccessControlRequest(
            service_principal_name="55be2ebd-113c-4077-9341-2d8444d8e4b2",
            permission_level=PermissionLevel.CAN_QUERY
        )
    ]
)
```

**Verification**:
```
Service Principal: 55be2ebd-113c-4077-9341-2d8444d8e4b2
Endpoint: fashionclip-endpoint (ID: 522f11c3f6164ad4b09d2d372499e99d)
Permission: CAN_QUERY ✅
```

### 2. Lakebase Database Permissions ✅

**Three layers of permissions configured**:

#### a) Unity Catalog Layer (via SDK):
```python
from databricks.sdk.service.catalog import PermissionsChange, Privilege, SecurableType

w.grants.update(
    securable_type=SecurableType.SCHEMA,
    full_name="main.fashion_sota",
    changes=[PermissionsChange(
        principal="55be2ebd-113c-4077-9341-2d8444d8e4b2",
        add=[Privilege.USAGE]
    )]
)

w.grants.update(
    securable_type=SecurableType.TABLE,
    full_name="main.fashion_sota.products_lakebase",
    changes=[PermissionsChange(
        principal="55be2ebd-113c-4077-9341-2d8444d8e4b2",
        add=[Privilege.SELECT]
    )]
)

w.grants.update(
    securable_type=SecurableType.TABLE,
    full_name="main.fashion_sota.users_lakebase",
    changes=[PermissionsChange(
        principal="55be2ebd-113c-4077-9341-2d8444d8e4b2",
        add=[Privilege.SELECT]
    )]
)
```

#### b) PostgreSQL Layer (via Databricks SQL):
```sql
GRANT USAGE ON SCHEMA fashion_sota TO `55be2ebd-113c-4077-9341-2d8444d8e4b2`;
GRANT SELECT ON TABLE fashion_sota.products_lakebase TO `55be2ebd-113c-4077-9341-2d8444d8e4b2`;
GRANT SELECT ON TABLE fashion_sota.users_lakebase TO `55be2ebd-113c-4077-9341-2d8444d8e4b2`;
```

#### c) Lakebase Instance User:
- Service Principal added to Lakebase instance: `retail-consumer-goods`
- Database: `databricks_postgres`
- User: `55be2ebd-113c-4077-9341-2d8444d8e4b2` (confirmed by user)

---

## Final Configuration

### App Resources
```json
{
  "name": "ecom-visual-search",
  "url": "https://ecom-visual-search-984752964297111.11.azure.databricksapps.com",
  "deployment": {
    "id": "01f0ed87f4931962ab7993aa9d8d2a23",
    "status": "SUCCEEDED",
    "deployed_at": "2026-01-09T18:22:34Z"
  },
  "permissions": {
    "model_serving": "CAN_QUERY",
    "lakebase_db": "CAN_CONNECT_AND_CREATE",
    "vector_search": "SELECT"
  }
}
```

### Service Principal
- **Name**: `app-7hspbl ecom-visual-search`
- **Client ID**: `55be2ebd-113c-4077-9341-2d8444d8e4b2`
- **Service Principal ID**: `142985553565381`

### Permissions Summary
| Resource | Type | Permission | Status |
|----------|------|------------|--------|
| fashionclip-endpoint | Model Serving | CAN_QUERY | ✅ |
| main.fashion_sota | UC Schema | USAGE | ✅ |
| main.fashion_sota.products_lakebase | UC Table | SELECT | ✅ |
| main.fashion_sota.users_lakebase | UC Table | SELECT | ✅ |
| fashion_sota | PostgreSQL Schema | USAGE | ✅ |
| fashion_sota.products_lakebase | PostgreSQL Table | SELECT | ✅ |
| fashion_sota.users_lakebase | PostgreSQL Table | SELECT | ✅ |
| retail-consumer-goods | Lakebase Instance | User Access | ✅ |
| main.fashion_sota.product_images | UC Volume | READ_VOLUME | ✅ |
| main.fashion_sota.product_embeddings_index | Vector Search | SELECT | ✅ |

---

## Key Learnings

### Lakebase Has Two Permission Layers
Lakebase requires permissions at BOTH layers to work correctly:

1. **Unity Catalog Layer**: Controls access to UC objects (schemas, tables)
   - Grants via `w.grants.update()` SDK method
   - Controls who can see/access the UC metadata

2. **PostgreSQL Layer**: Controls access at the database level
   - Grants via SQL: `GRANT USAGE/SELECT` statements
   - Controls who can actually query the data via PostgreSQL interface

**Both layers must be configured** for service principals to access Lakebase tables.

### Service Principal Must Be Added to Lakebase
In addition to permissions, the service principal must be explicitly added as a user to the Lakebase instance via the Databricks UI:
1. Navigate to: Data → Lakebase → [instance name]
2. Add service principal to Users/Permissions tab

### app.yaml UC Permissions Don't Auto-Apply
While we added UC permissions to `app.yaml`, these didn't automatically apply. We had to grant them explicitly via SDK:
```yaml
# This documents intent but doesn't auto-apply
resources:
  uc_securable:
    - securable_type: SCHEMA
      securable_full_name: main.fashion_sota
      permission: USAGE
```

---

## Other Features Deployed

Along with permission fixes, the following improvements are included:

### CLIP Timeout Handling
- **Total timeout**: 180s (3 minutes)
- **Connect timeout**: 60s (handles slow endpoint warmup)
- **Read timeout**: 120s (handles slow inference)
- Handles Model Serving scale-from-zero cold starts gracefully

### Application Filter Improvements
- Lenient category matching (checks master/sub/article fields)
- Fallback logic when filters remove all results
- Color treated as soft preference (non-blocking)
- Default: `restrict_category=False`, `restrict_price=False`

### Curated Personas
- 8 users with rich 512-dim taste embeddings
- User IDs: user_001239, user_008711, user_001249, user_001274, user_001273, user_001232, user_001305, user_001289
- Styles: athletic, budget, casual, formal, luxury, minimalist, trendy, vintage

### Error Classification
- HTTP 504 for CLIP timeout errors (clear cold start message)
- HTTP 500 for vector search failures
- Proper error messages for debugging

---

## Verification Steps

To verify permissions are working:

1. **Test Model Serving**:
```bash
curl -X POST \
  "https://adb-984752964297111.11.azuredatabricks.net/serving-endpoints/fashionclip-endpoint/invocations" \
  -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  -d '{"inputs": {"text": "party shirt"}}'
```

2. **Test Lakebase Access** (from app logs):
```
SELECT * FROM fashion_sota.users_lakebase WHERE user_id = 'user_001305'
SELECT * FROM fashion_sota.products_lakebase LIMIT 10
```

3. **Test App Endpoints** (requires OAuth login):
```bash
# Products endpoint
GET /api/v1/products?page=1&page_size=10

# Personas endpoint
GET /api/v1/users/personas

# Text search (uses CLIP)
POST /api/v1/search/text
{"query": "red dress", "limit": 10}

# Recommendations (uses Lakebase + Vector Search)
GET /api/v1/search/recommendations/user_001305?limit=10
```

---

## Status: ✅ READY FOR PRODUCTION

All permission issues resolved. App is fully operational with:
- ✅ Model Serving access (CLIP embeddings)
- ✅ Lakebase database access (products, users)
- ✅ Vector Search access (product embeddings)
- ✅ Unity Catalog Volume access (product images)
- ✅ CLIP timeout handling for cold starts
- ✅ Intelligent product filtering and recommendations
- ✅ Curated personas with rich embeddings
