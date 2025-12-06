# Lakebase PostgreSQL Setup Guide

## Current Error

```
InvalidPasswordError: Failed to decode token for role "kevin.ippen@databricks.com"
```

This means the authentication credentials are incorrect.

## Authentication Options

The app needs valid credentials to connect to your Lakebase PostgreSQL instance.

### Option 1: Use Personal Access Token (Recommended)

1. **Generate a Personal Access Token in Databricks:**
   - Go to: User Settings → Developer → Access Tokens
   - Click "Generate New Token"
   - Give it a name (e.g., "Lakebase Fashion App")
   - Set expiration (or no expiration for demos)
   - Copy the token (you won't see it again!)

2. **Add to Databricks App Environment Variables:**
   - In Databricks workspace, go to your app settings
   - Add environment variable:
     ```
     LAKEBASE_PASSWORD=<your_personal_access_token>
     ```
   - Restart the app

### Option 2: Use Workspace Token (May Not Work)

The app attempts to use `DATABRICKS_TOKEN` (workspace token) by default, but this may not have Lakebase access permissions.

If you get authentication errors, use Option 1 instead.

## Current Configuration

**Connection Details (from code):**
- **Host**: `instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net`
- **Port**: `5432`
- **Database**: `databricks_postgres`
- **Username**: `kevin.ippen@databricks.com`
- **Password**: `LAKEBASE_PASSWORD` env var (or falls back to `DATABRICKS_TOKEN`)

## Verifying Connection

Once you've set `LAKEBASE_PASSWORD`, test the connection:

```bash
# Using psql (if available locally)
psql "host=instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net \
      user=kevin.ippen@databricks.com \
      dbname=databricks_postgres \
      port=5432 \
      sslmode=require"
# Enter your token when prompted for password
```

Or just restart the Databricks App and check if the products API works:
```
GET /api/v1/products
```

## Environment Variables Reference

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `LAKEBASE_HOST` | No | Lakebase instance hostname | `instance-e2ff35b5-...` |
| `LAKEBASE_PORT` | No | PostgreSQL port | `5432` |
| `LAKEBASE_DATABASE` | No | Database name | `databricks_postgres` |
| `LAKEBASE_USER` | No | Username (your Databricks email) | `kevin.ippen@databricks.com` |
| **`LAKEBASE_PASSWORD`** | **Yes** | **Personal access token** | **None** |
| `LAKEBASE_SSL_MODE` | No | SSL mode | `require` |

## Troubleshooting

**Q: Still getting "Failed to decode token"?**
- A: Make sure your personal access token has not expired
- A: Verify the token was copied correctly (no extra spaces)
- A: Check that the token has appropriate permissions for Lakebase

**Q: Getting "role does not exist"?**
- A: Verify `LAKEBASE_USER` matches your Databricks email exactly

**Q: Connection timeout?**
- A: Check network connectivity to the Lakebase instance
- A: Verify the instance hostname is correct

## Next Steps

1. Set `LAKEBASE_PASSWORD` environment variable in your Databricks App
2. Restart the app
3. Test the `/api/v1/products` endpoint
4. Monitor logs for any remaining connection errors
