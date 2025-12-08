# Lakebase Synced Tables Update Summary

**Date**: 2025-12-08
**Change**: Updated application to use Lakebase synced tables in `ecom.fashion_demo` catalog

---

## What Changed

### Tables Migrated to Lakebase

Your Unity Catalog tables have been synced to Lakebase PostgreSQL:

| Original Table | Synced Location | Status |
|----------------|-----------------|--------|
| `main.fashion_demo.productsdb` | `ecom.fashion_demo.productsdb` | ✅ Synced |
| `main.fashion_demo.usersdb` | `ecom.fashion_demo.usersdb` | ✅ Synced |
| `main.fashion_demo.product_image_embeddingsdb` | `ecom.fashion_demo.product_image_embeddingsdb` | ✅ Synced |
| `main.fashion_demo.user_style_featuresdb` | `ecom.fashion_demo.user_style_featuresdb` | ✅ Synced |

### Code Changes

#### 1. **[core/config.py](core/config.py#L35)**
```python
# Before
CATALOG: str = "main"

# After
CATALOG: str = "ecom"  # Lakebase database catalog
```

**Impact**: All database queries now target the Lakebase synced tables in the `ecom` catalog instead of the original `main` catalog.

#### 2. **[models/schemas.py](models/schemas.py)**
Updated docstrings to reflect new table locations:
- Line 10: `Product` model → `ecom.fashion_demo.productsdb (Lakebase synced)`
- Line 46: `User` model → `ecom.fashion_demo.usersdb (Lakebase synced)`
- Line 58: `UserStyleFeatures` model → `ecom.fashion_demo.user_style_featuresdb (Lakebase synced)`
- Line 90: `ProductImageEmbedding` model → `ecom.fashion_demo.product_image_embeddingsdb (Lakebase synced)`

**Impact**: Documentation now accurately reflects data source.

#### 3. **[DEPLOY.md](DEPLOY.md)**
Updated deployment guide to:
- Note Lakebase as data source
- Show correct catalog (`ecom.fashion_demo`)
- Reference migration guide

**Impact**: Future deployments will have correct documentation.

---

## Benefits of Lakebase Synced Tables

✅ **10x faster queries**: ~10ms response time vs ~100ms with SQL Warehouse
✅ **Automatic sync**: Tables stay up-to-date via Lakeflow pipelines
✅ **Native PostgreSQL**: Use standard Postgres indexes, joins, and queries
✅ **Unity Catalog governance**: Access control and lineage maintained
✅ **Cost optimization**: Lower latency without dedicated SQL Warehouse

---

## No Changes Required In

- **Database connection logic** ([core/database.py](core/database.py)) - Uses `settings.CATALOG` dynamically
- **API routes** - All use `settings.CATALOG` and `settings.SCHEMA`
- **Models/ORM** - SQLAlchemy models use dynamic table references
- **Authentication** - Still uses OAuth-first with PAT fallback
- **Deployment** - Same deployment process

---

## Configuration Reference

### Current Settings ([core/config.py](core/config.py))

```python
# Lakebase PostgreSQL Connection
LAKEBASE_HOST: str = "instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net"
LAKEBASE_PORT: int = 5432
LAKEBASE_DATABASE: str = "databricks_postgres"
LAKEBASE_USER: str = "kevin.ippen@databricks.com"
LAKEBASE_PASSWORD: Optional[str] = os.getenv("LAKEBASE_PASSWORD")  # From Databricks Apps resource
LAKEBASE_SSL_MODE: str = "require"

# Unity Catalog Tables (now Lakebase synced)
CATALOG: str = "ecom"  # Lakebase database catalog
SCHEMA: str = "fashion_demo"
PRODUCTS_TABLE: str = "productsdb"
USERS_TABLE: str = "usersdb"
EMBEDDINGS_TABLE: str = "product_image_embeddingsdb"
USER_FEATURES_TABLE: str = "user_style_featuresdb"
```

### Connection String Format

```
postgresql+asyncpg://kevin.ippen@databricks.com:{PGPASSWORD}@instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net:5432/databricks_postgres
```

---

## Testing

### Verify Tables Are Accessible

Run this in a Databricks notebook:

```sql
-- Check synced tables exist
SHOW TABLES IN ecom.fashion_demo;

-- Sample query
SELECT COUNT(*) FROM ecom.fashion_demo.productsdb;
```

### Test API Endpoints

```bash
# Test product list endpoint
curl https://your-app-url/api/v1/products?page=1&page_size=5

# Expected: Should return products from Lakebase synced tables
```

---

## Rollback Plan (If Needed)

If you need to revert to the original Unity Catalog tables:

1. **Update config.py**:
   ```python
   CATALOG: str = "main"  # Back to original
   ```

2. **Redeploy**:
   ```bash
   git add core/config.py
   git commit -m "rollback: Revert to main catalog"
   git push
   databricks apps deploy
   ```

**Note**: You can keep both versions running and switch between them by changing the `CATALOG` setting.

---

## Next Steps

### 1. Performance Optimization

Create indexes in Lakebase for frequently filtered columns:

```sql
-- Connect to Lakebase via psql or SQL editor
\c databricks_postgres

-- Create indexes
CREATE INDEX idx_products_category ON fashion_demo.productsdb(master_category);
CREATE INDEX idx_products_price ON fashion_demo.productsdb(price);
CREATE INDEX idx_products_gender ON fashion_demo.productsdb(gender);
CREATE INDEX idx_products_color ON fashion_demo.productsdb(base_color);
```

### 2. Monitor Sync Pipeline

Check the Lakeflow pipeline status in Databricks Workflows UI:
- Pipeline name pattern: `synced_table_ecom_fashion_demo_*`
- Verify tables are staying up-to-date

### 3. Grant Permissions (If Needed)

If other users need access to synced tables:

```sql
-- In PostgreSQL
GRANT USAGE ON SCHEMA fashion_demo TO other_user;
GRANT SELECT ON ALL TABLES IN SCHEMA fashion_demo TO other_user;
```

---

## Troubleshooting

### Issue: "Table not found" errors

**Cause**: App still pointing to old catalog
**Solution**: Verify `CATALOG = "ecom"` in [core/config.py](core/config.py)

### Issue: "Connection refused" to Lakebase

**Cause**: Missing or incorrect PGPASSWORD
**Solution**: See [LAKEBASE_PASSWORD_SETUP.md](LAKEBASE_PASSWORD_SETUP.md)

### Issue: Stale data in synced tables

**Cause**: Sync pipeline not running
**Solution**: Check pipeline status in Workflows UI, trigger manual refresh if needed

---

## References

- [LAKEBASE_MIGRATION_GUIDE.md](LAKEBASE_MIGRATION_GUIDE.md) - Full migration documentation
- [LAKEBASE_PASSWORD_SETUP.md](LAKEBASE_PASSWORD_SETUP.md) - Authentication setup
- [DEPLOY.md](DEPLOY.md) - Deployment guide
- [notebooks/migrate_to_lakebase.ipynb](notebooks/migrate_to_lakebase.ipynb) - Migration notebook
