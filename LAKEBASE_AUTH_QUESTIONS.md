# Lakebase Authentication Questions for Internal Documentation

**Context**: Fashion ecommerce Databricks App attempting to connect to Lakebase PostgreSQL database. Both OAuth and PAT token authentication are failing with different errors.

---

## 🎯 KEY FINDINGS - ROOT CAUSE IDENTIFIED

### ❌ What Was Wrong:
1. **Wrong database name**: Using `main` instead of `databricks_postgres`
2. **Wrong password type**: Using Databricks PAT token (`dapi...`) instead of Lakebase PostgreSQL password

### ✅ Correct Configuration (from Lakebase UI):

**Connection Parameters**:
```
host:     instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net
user:     kevin.ippen@databricks.com
dbname:   databricks_postgres  ← NOT "main"
port:     5432
sslmode:  require
password: ${PGPASSWORD}         ← NOT a Databricks PAT token!
```

**PSQL Example**:
```bash
psql "host=instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net \
user=kevin.ippen@databricks.com \
dbname=databricks_postgres \
port=5432 \
sslmode=require"
```

**JDBC Connection String**:
```
jdbc:postgresql://kevin.ippen%40databricks.com:${PGPASSWORD}@instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net:5432/databricks_postgres?sslmode=require
```

### 🔧 Fixes Applied:
1. ✅ Updated [core/config.py:29](core/config.py#L29) - Changed database name to `databricks_postgres`
2. ⏳ **TODO**: Get the correct `PGPASSWORD` from Lakebase UI and update secret scope

### 📋 Next Steps:
1. **Find PGPASSWORD** in Lakebase UI (see [LAKEBASE_PASSWORD_SETUP.md](LAKEBASE_PASSWORD_SETUP.md))
2. **Update secret**: Replace the `dapi...` token in `redditscope/redditkey` with the actual PGPASSWORD
3. **Test locally** with psql before redeploying
4. **Redeploy** Databricks App with correct credentials

---

## 🔍 Core Questions

### 1. What credentials does Lakebase PostgreSQL accept?

**Current behavior**: We're attempting to use:
1. OAuth tokens generated via `/api/2.0/token/generate` (fails - endpoint doesn't exist)
2. Databricks PAT tokens (format: `dapi...`) (fails - "Failed to decode token")

**Our implementation** ([core/config.py:88-110](core/config.py#L88-L110)):
```python
@property
def lakebase_url(self) -> str:
    """Build PostgreSQL connection URL for Lakebase.

    Tries OAuth first (bypasses IP ACL), falls back to PAT token.
    """
    # Try OAuth first (preferred - bypasses IP ACL)
    oauth_result = self._get_oauth_token()
    if oauth_result:
        username, password = oauth_result
    else:
        # Fallback to PAT token
        username = self.LAKEBASE_USER
        password = self.LAKEBASE_PASSWORD or ""
        if password:
            logger.info("✓ Using PAT token from LAKEBASE_PASSWORD")
        else:
            logger.error("❌ No authentication available")

    return (
        f"postgresql+asyncpg://{username}:{password}@"
        f"{self.LAKEBASE_HOST}:{self.LAKEBASE_PORT}/{self.LAKEBASE_DATABASE}"
    )
```

**Questions**:
- ❓ Can Databricks PAT tokens be used directly as PostgreSQL passwords for Lakebase?
- ❓ Is there a separate Lakebase-specific password or token format?
- ❓ Should we be using a different credential type entirely (service principal token, SQL Warehouse token, etc.)?

---

### 2. OAuth Token Generation - Does `/api/2.0/token/generate` work with Databricks Apps?

**Current error**:
```
OAuth token generation failed: No API found for 'POST /token/generate'
```

**Our OAuth implementation** ([core/config.py:57-86](core/config.py#L57-L86)):
```python
def _get_oauth_token(self) -> Optional[tuple[str, str]]:
    """Generate OAuth token using service principal (bypasses IP ACL).

    Returns:
        Tuple of (username, token) if successful, None otherwise
    """
    client_id = os.getenv("DATABRICKS_CLIENT_ID")
    client_secret = os.getenv("DATABRICKS_CLIENT_SECRET")

    if not (client_id and client_secret):
        return None

    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()

        token_response = w.api_client.do(
            'POST',
            '/api/2.0/token/generate',  # ⚠️ This endpoint doesn't exist!
            data={'lifetime_seconds': 3600, 'comment': 'Lakebase access'}
        )
        oauth_token = token_response.get('access_token')

        if oauth_token:
            logger.info("✓ Using OAuth token (bypasses IP ACL)")
            return (client_id, oauth_token)
    except Exception as e:
        logger.warning(f"OAuth token generation failed: {e}")

    return None
```

**Environment available**:
```
DATABRICKS_CLIENT_ID: ✓ Available (service principal)
DATABRICKS_CLIENT_SECRET: ✓ Available (service principal)
```

**Questions**:
- ❓ Is `/api/2.0/token/generate` available in Databricks Apps environments?
- ❓ Should we use a different API endpoint for token generation?
- ❓ Can service principals generate temporary tokens that work with Lakebase?
- ❓ Is there a Databricks SDK method specifically for Lakebase authentication?

---

### 3. PAT Token Authentication - Why is Lakebase rejecting valid Databricks PAT tokens?

**Current error**:
```
asyncpg.exceptions.InvalidPasswordError: Failed to decode token for role "kevin.ippen@databricks.com"
and native postgres login was either not attempted due to configuration or failed.
```

**What we know works**:
- ✅ PAT token is successfully injected from Databricks Apps resource
- ✅ Token format is correct (starts with `dapi`)
- ✅ Token value: `dapi9218...` (truncated for security)
- ✅ Username is correct: `kevin.ippen@databricks.com`
- ✅ Database host is correct: `instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net`
- ✅ Connection string format is correct for PostgreSQL

**Our secret injection** ([app.yaml:10-12](app.yaml#L10-L12)):
```yaml
env:
  - name: LAKEBASE_PASSWORD
    valueFrom: lakebase-token  # Injects from Databricks Apps resource
```

**Databricks Apps Resource Configuration**:
- Resource Type: Secret
- Resource Key: `lakebase-token` (matches app.yaml)
- Scope: `redditscope`
- Key: `redditkey`
- Permission: Can read

**Startup logs showing successful injection**:
```
AUTHENTICATION STATUS:
  OAuth (Service Principal): ✓ Available
  PAT Token (LAKEBASE_PASSWORD): ✓ Available

DATABASE CONNECTION:
  Host: instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net
  Database: main
  User: kevin.ippen@databricks.com
  SSL: require

AUTHENTICATION STRATEGY:
  Using PAT token from LAKEBASE_PASSWORD
```

**Questions**:
- ❓ What type of password should be in the secret scope for Lakebase authentication?
- ❓ Is there a UI in Databricks to generate/retrieve Lakebase-specific credentials?
- ❓ Does the PAT token need specific Lakebase permissions or scopes?
- ❓ Should we be using the PAT token as the password directly, or does it need transformation?
- ❓ The error mentions "native postgres login" - does Lakebase support native PostgreSQL user/password auth?

---

## 🏗️ Implementation Details

### Database Connection Setup

**Lazy initialization pattern** ([core/database.py:17-44](core/database.py#L17-L44)):
```python
_engine: Optional[create_async_engine] = None
_session_factory: Optional[async_sessionmaker] = None

def get_engine():
    """Get or create the database engine (lazy initialization)"""
    global _engine
    if _engine is None:
        logger.info("🔄 Creating database engine (lazy initialization)")

        # Prepare SSL context for asyncpg
        connect_args = {}
        if settings.LAKEBASE_SSL_MODE != "disable":
            ssl_context = ssl.create_default_context()
            if settings.LAKEBASE_SSL_MODE == "require":
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_context

        # Create engine with current lakebase_url (includes OAuth logic)
        # This is called at REQUEST TIME, not IMPORT TIME
        _engine = create_async_engine(
            settings.lakebase_url,  # This will try OAuth first!
            connect_args=connect_args,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=settings.DEBUG,
        )
        logger.info(f"✅ Database engine created with OAuth support")

    return _engine

async def get_async_db():
    """
    Dependency for FastAPI route injection
    Yields an async database session
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Why lazy initialization?**
We initialize the database engine on first request (not at app startup) so that OAuth token generation happens with fresh credentials at request time, not at import time.

---

## 🔧 Configuration

### Current Lakebase Settings ([core/config.py:23-32](core/config.py#L23-L32)):
```python
# Lakebase PostgreSQL
LAKEBASE_HOST: str = os.getenv(
    "LAKEBASE_HOST",
    "instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net"
)
LAKEBASE_PORT: int = 5432
LAKEBASE_DATABASE: str = os.getenv("LAKEBASE_DATABASE", "main")
LAKEBASE_USER: str = os.getenv("LAKEBASE_USER", "kevin.ippen@databricks.com")
LAKEBASE_PASSWORD: Optional[str] = os.getenv("LAKEBASE_PASSWORD")
LAKEBASE_SSL_MODE: str = os.getenv("LAKEBASE_SSL_MODE", "require")
```

### Connection String Format:
```
postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}
```

**Actual connection string** (with token):
```
postgresql+asyncpg://kevin.ippen@databricks.com:dapi9218...@instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net:5432/main
```

---

## 📊 Complete Error Trace

**Full error from latest deployment** (2025-12-08 16:30):
```
INFO:     172.25.0.1:0 - "GET /api/v1/products?page=1&page_size=5 HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "/databricks/python3/lib/python3.11/site-packages/sqlalchemy/pool/base.py", line 148, in __init__
    self._checkout()
  File "/databricks/python3/lib/python3.11/site-packages/sqlalchemy/pool/base.py", line 285, in _checkout
    fairy = _ConnectionFairy._checkout(self, self._fairy_cache.popleft())
  File "/databricks/python3/lib/python3.11/site-packages/sqlalchemy/pool/base.py", line 1056, in _checkout
    fairy._reset(pool, connection_record)
  File "/databricks/python3/lib/python3.11/site-packages/sqlalchemy/pool/base.py", line 1256, in _reset
    pool._dialect.do_rollback(fairy)
  File "/databricks/python3/lib/python3.11/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py", line 980, in do_rollback
    await connection.rollback()
asyncpg.exceptions.InvalidPasswordError: Failed to decode token for role "kevin.ippen@databricks.com"
and native postgres login was either not attempted due to configuration or failed.
```

---

## 🎯 What We Need to Know

### Immediate Questions:
1. **What is the correct credential format for Lakebase PostgreSQL authentication?**
2. **Can we use Databricks PAT tokens, or do we need Lakebase-specific credentials?**
3. **If PAT tokens work, what permissions/scopes are required?**
4. **Is there a Databricks UI to generate Lakebase passwords?**
5. **Does OAuth work with Lakebase, and if so, what's the correct endpoint?**

### Alternative Authentication Methods to Try:
- ❓ Service principal direct authentication (without token generation)?
- ❓ SQL Warehouse connection strings repurposed for Lakebase?
- ❓ Databricks SDK methods specifically for Lakebase?
- ❓ M2M OAuth tokens?
- ❓ Native PostgreSQL user/password (if supported)?

### Permissions Questions:
- ❓ Does the service principal need `CONNECT` permission on Lakebase database?
- ❓ Are there Unity Catalog grants required for Lakebase access?
- ❓ Do we need to grant permissions on the Lakebase instance itself?

---

## 📁 Complete Implementation Files

### Key Files:
1. **[app.yaml](app.yaml)** - Secret injection configuration
2. **[core/config.py](core/config.py)** - Authentication logic (OAuth-first strategy)
3. **[core/database.py](core/database.py)** - Database engine with lazy initialization
4. **[app.py](app.py)** - Startup logging showing auth status

### Authentication Flow:
```
1. App starts → app.py logs environment status
2. First API request → get_async_db() called
3. Lazy init → get_engine() creates engine
4. Engine creation → calls settings.lakebase_url
5. lakebase_url property:
   a. Try _get_oauth_token() → FAILS (endpoint not found)
   b. Fallback to LAKEBASE_PASSWORD → PAT token available
   c. Build connection string with PAT token
6. asyncpg tries to connect → FAILS (token decode error)
```

---

## 🚀 Deployment Context

**Environment**: Databricks Apps (Azure)
**Host**: `instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net`
**Database**: `main`
**User**: `kevin.ippen@databricks.com`
**Service Principal**: Available via DATABRICKS_CLIENT_ID/CLIENT_SECRET
**PAT Token**: Successfully injected from secret scope `redditscope/redditkey`

---

## ✅ Next Steps

Once we understand the correct authentication method:
1. Update [core/config.py](core/config.py) authentication logic
2. Update [app.yaml](app.yaml) if different secrets are needed
3. Configure correct permissions in Unity Catalog/Lakebase
4. Update [DEPLOY.md](DEPLOY.md) with correct setup steps
5. Test connection and verify database queries work

---

**Please provide**:
- Documentation links for Lakebase authentication
- Examples of working Lakebase connection strings from Databricks Apps
- Required permissions/grants for service principals
- Correct API endpoints for token generation (if supported)
