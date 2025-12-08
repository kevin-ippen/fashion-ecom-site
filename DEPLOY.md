# 🚀 Deployment Guide - Clean Version

**Current Setup**: OAuth-first authentication with PAT token fallback

---

## ✅ Current State

### **Authentication Strategy**
1. **OAuth** (preferred) - Uses service principal (`DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET`)
   - Auto-injected by Databricks Apps
   - Bypasses IP ACL restrictions
   - Generates temporary access tokens

2. **PAT Token** (fallback) - Uses `LAKEBASE_PASSWORD`
   - Injected from Databricks Apps resource
   - Requires app resource setup in UI

### **Configuration Files**
- **[app.yaml](app.yaml)** - Defines `valueFrom: lakebase-token` for secret injection
- **[core/config.py](core/config.py)** - OAuth-first authentication logic
- **[core/database.py](core/database.py)** - Lazy initialization for OAuth token generation
- **[app.py](app.py)** - Clean startup logging

---

## 📋 Setup Steps

### **1. Add Secret Resource in Databricks Apps UI**

1. Go to **Databricks Apps** > **Your App** > **Resources** tab
2. Click **"Add Resource"** > **"Secret"**
3. Configure:
   - **Resource Key**: `lakebase-token` ⚠️ Must match app.yaml!
   - **Scope**: `redditscope`
   - **Key**: `redditkey`
   - **Permission**: `Can read`
4. Click **"Save"**

### **2. Deploy the App**

```bash
# Push latest code
git push origin refactor/lakebase-tables

# Deploy (via CLI or UI)
databricks apps deploy <your-app-name>
databricks apps restart <your-app-name>
```

### **3. Verify**

Check startup logs at `https://your-app-url/logz`:

**Expected:**
```
================================================================================
FASHION ECOMMERCE APP STARTING
Version: 1.0.0
================================================================================

AUTHENTICATION STATUS:
  OAuth (Service Principal): ✓ Available
  PAT Token (LAKEBASE_PASSWORD): ✓ Available

DATABASE CONNECTION:
  Host: instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net
  Database: main
  User: kevin.ippen@databricks.com
  SSL: require

AUTHENTICATION STRATEGY:
  1. OAuth (preferred - bypasses IP ACL)
  2. PAT token (fallback)
================================================================================
```

Test API:
```bash
curl https://your-app-url/api/v1/products?page=1&page_size=5
```

---

## 🔍 How It Works

### **Authentication Flow**

1. **First Request** → `get_async_db()` called
2. **Lazy Init** → `get_engine()` creates engine
3. **OAuth Attempt** → `settings.lakebase_url` tries OAuth:
   - Calls `WorkspaceClient()` (uses `DATABRICKS_CLIENT_ID`/`CLIENT_SECRET`)
   - Generates temporary access token
   - Uses token for database connection
4. **Fallback** → If OAuth fails, uses `LAKEBASE_PASSWORD`

### **Key Code Locations**

**config.py** (lines 57-110):
```python
def _get_oauth_token(self):
    """Generate OAuth token using service principal"""
    client_id = os.getenv("DATABRICKS_CLIENT_ID")
    client_secret = os.getenv("DATABRICKS_CLIENT_SECRET")
    # ... generates token ...

@property
def lakebase_url(self):
    # Try OAuth first
    oauth_result = self._get_oauth_token()
    if oauth_result:
        username, password = oauth_result  # OAuth token
    else:
        username = self.LAKEBASE_USER
        password = self.LAKEBASE_PASSWORD  # PAT fallback
```

**database.py** (lines 17-44):
```python
def get_engine():
    """Lazy initialization - called at request time"""
    # Creates engine with settings.lakebase_url
    # This ensures OAuth token is generated fresh for each connection
```

---

## 🐛 Troubleshooting

### **If OAuth is not available:**
```
AUTHENTICATION STATUS:
  OAuth (Service Principal): ✗ Not configured
  PAT Token (LAKEBASE_PASSWORD): ✓ Available

AUTHENTICATION STRATEGY:
  Using PAT token from LAKEBASE_PASSWORD
```

**This is OK!** The app will use the PAT token from the app resource.

### **If neither is available:**
```
❌ No authentication configured!
```

**Fix**: Add the Secret resource in Databricks Apps UI (see Step 1 above).

### **If database connection fails:**

Check logs for specific error:
- `Failed to decode token` → Token is invalid or expired
- `Connection timeout` → Network/firewall issue
- `Permission denied` → Service principal lacks database access

---

## 📁 File Structure (After Cleanup)

```
fashion-ecom-site/
├── app.yaml                              # Databricks Apps config (valueFrom)
├── app.py                                # FastAPI app with clean logging
├── core/
│   ├── config.py                         # OAuth-first auth logic
│   └── database.py                       # Lazy initialization
├── repositories/
│   └── lakebase.py                       # Database queries
├── routes/
│   └── v1/                               # API endpoints
├── frontend/                             # React app
├── README.md                             # Main documentation
├── DATABRICKS_APPS_RESOURCES_SETUP.md    # Detailed resource setup guide
└── FASHION_ECOM-SITE_CONTEXT.md          # Project context
```

---

## ✅ Checklist

- [x] Code cleaned up (removed 20+ outdated MD files)
- [x] app.py updated with clean logging
- [x] config.py uses OAuth-first strategy
- [x] database.py has lazy initialization
- [x] app.yaml uses `valueFrom` pattern
- [ ] Add Secret resource in Databricks Apps UI
- [ ] Deploy and restart app
- [ ] Verify OAuth or PAT token is working
- [ ] Test API endpoints

---

## 🎯 Next Steps

1. **Add the Secret resource** in Databricks Apps UI (if not done)
2. **Deploy** the latest code
3. **Check logs** - Verify authentication is working
4. **Test API** - Confirm database queries succeed

That's it! The code is now clean and ready to deploy. 🚀
