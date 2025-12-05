# FastAPI + Databricks Lakebase: Building Low-Latency Data Products

A practical guide for building production-ready FastAPI applications with Databricks Lakebase PostgreSQL for low-latency data product APIs.

## Core Concepts

**Lakebase PostgreSQL** provides a managed PostgreSQL database in Databricks with:
- Direct SQL query access (sub-second latency)
- Synced tables from Unity Catalog (one-way replication)
- OAuth-based authentication via Databricks SDK
- Ideal for operational APIs requiring fast queries on analytics data

**Key Architecture Pattern**: Analytics data in Unity Catalog → Synced to Lakebase → FastAPI queries via async SQLAlchemy

## Project Structure

```
app/
├── main.py                    # FastAPI app initialization
├── config/
│   ├── database.py           # Async DB session management
│   └── settings.py           # Environment configuration
├── routes/
│   └── v1/
│       ├── lakebase.py       # Resource lifecycle endpoints
│       └── orders.py         # Business logic endpoints
├── models/
│   ├── orders.py             # Pydantic models + SQLAlchemy ORM
│   └── lakebase.py           # Resource management models
└── requirements.txt
```

## Critical Dependencies

```txt
databricks-sdk>=0.60.0   # Databricks API + OAuth
fastapi                   # Web framework
sqlalchemy               # ORM with async support
sqlmodel                 # Combines SQLAlchemy + Pydantic
asyncpg                  # Async PostgreSQL driver
uvicorn                  # ASGI server
```

## Database Connection Pattern

### config/database.py
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from databricks.sdk import WorkspaceClient

# Get OAuth token for database authentication
w = WorkspaceClient()
token = w.dbutils.secrets.get(scope="my-scope", key="db-token")

# Connection string format for Lakebase
DATABASE_URL = f"postgresql+asyncpg://token:{token}@{instance_host}:5432/{database_name}"

# Engine with connection pooling
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,           # Adjust based on expected load
    max_overflow=20,        # Extra connections under load
    pool_pre_ping=True,     # Verify connections before use
    echo=False              # Set True for SQL debugging
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  # Important for async operations
)

# Dependency for route injection
async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

**Key Decisions**:
- Always use async engine and sessions for non-blocking I/O
- OAuth tokens expire - refresh mechanism needed for long-running apps
- Connection pooling critical for concurrent request handling
- `expire_on_commit=False` prevents lazy-loading issues in async context

## API Design Patterns

### 1. Resource Lifecycle Management

**Pattern**: Separate endpoints for infrastructure vs. data operations

```python
# POST for creation (not idempotent)
@router.post("/resources/create-lakebase-resources")
async def create_lakebase_resources(
    create_resources: bool = Query(..., description="Cost acknowledgment flag"),
    capacity: str = Query("CU_1"),
    node_count: int = Query(1)
):
    # Check existence before creating
    try:
        existing = w.database.get_database_instance(name=instance_name)
        return {"message": "Already exists"}
    except:
        pass  # Not found, proceed with creation
    
    # Create and wait for provisioning
    instance = w.database.create_database_instance_and_wait(...)
    
    return {
        "instance": instance.name,
        "message": "Resources provisioning asynchronously"
    }

# DELETE for cleanup (idempotent)
@router.delete("/resources/delete-lakebase-resources")
async def delete_lakebase_resources(
    confirm_deletion: bool = Query(...)
):
    # Delete in order: synced_table → catalog → instance
    # Track successes and failures separately
    # Return detailed status for each resource
```

**Best Practices**:
- Use confirmation flags for destructive operations
- Check resource existence before creation (avoid duplicates)
- Use `_and_wait` methods for synchronous provisioning when needed
- Return resource URLs/IDs for async monitoring
- Delete dependent resources first (tables before catalogs)

### 2. Pagination Strategies

**Choose based on use case**:

#### Page-Based (Traditional UI with page numbers)
```python
@router.get("/orders/pages")
async def get_orders_by_page(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    include_count: bool = Query(True),  # Optional total count
    db: AsyncSession = Depends(get_async_db)
):
    # Count total (expensive on large tables)
    if include_count:
        total_count = await db.scalar(select(func.count(Order.o_orderkey)))
        total_pages = (total_count + page_size - 1) // page_size
    
    # Fetch page with +1 to detect has_next
    offset = (page - 1) * page_size
    orders = await db.execute(
        select(Order)
        .order_by(Order.o_orderkey)
        .offset(offset)
        .limit(page_size + 1)
    )
    all_orders = orders.scalars().all()
    
    return {
        "orders": all_orders[:page_size],
        "pagination": {
            "has_next": len(all_orders) > page_size,
            "has_previous": page > 1
        }
    }
```

**Pros**: Simple, supports random access, shows total pages  
**Cons**: OFFSET slow on large datasets, count query expensive  
**Use when**: Small-medium datasets, traditional UI needs

#### Cursor-Based (Efficient for large datasets)
```python
@router.get("/orders/stream")
async def get_orders_by_cursor(
    cursor: int = Query(0, ge=0),  # Start after this key
    page_size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_db)
):
    # WHERE key > cursor ensures we skip already-seen records
    orders = await db.execute(
        select(Order)
        .where(Order.o_orderkey > cursor)
        .order_by(Order.o_orderkey)
        .limit(page_size + 1)
    )
    all_orders = orders.scalars().all()
    
    has_next = len(all_orders) > page_size
    actual_orders = all_orders[:page_size]
    
    return {
        "orders": actual_orders,
        "pagination": {
            "next_cursor": actual_orders[-1].o_orderkey if has_next else None,
            "has_next": has_next
        }
    }
```

**Pros**: O(1) performance at any scale, efficient index usage  
**Cons**: No random access, no total count, cursor must be stable  
**Use when**: Large datasets (millions+), infinite scroll, data exports

### 3. Query Patterns

#### Single Record Lookup (Primary Key)
```python
@router.get("/{order_key}")
async def read_order(order_key: int, db: AsyncSession = Depends(get_async_db)):
    # Input validation
    if order_key <= 0:
        raise HTTPException(400, "Invalid order key")
    
    # Single query by PK (indexed)
    result = await db.execute(
        select(Order).where(Order.o_orderkey == order_key)
    )
    order = result.scalars().first()
    
    if not order:
        raise HTTPException(404, f"Order {order_key} not found")
    
    return order
```

#### Aggregations (Counts, Sums)
```python
@router.get("/count")
async def get_order_count(db: AsyncSession = Depends(get_async_db)):
    # Use scalar() for single value results
    count = await db.scalar(select(func.count(Order.o_orderkey)))
    return {"total_orders": count}
```

#### Updates (Write Operations)
```python
@router.post("/{order_key}/status")
async def update_order_status(
    order_key: int,
    status_data: OrderStatusUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    # Fetch existing record
    order = await db.scalar(
        select(Order).where(Order.o_orderkey == order_key)
    )
    
    if not order:
        raise HTTPException(404, "Order not found")
    
    # Update and commit
    order.o_orderstatus = status_data.o_orderstatus
    await db.commit()
    await db.refresh(order)  # Get updated values
    
    return {
        "o_orderkey": order_key,
        "o_orderstatus": order.o_orderstatus,
        "message": "Updated successfully"
    }
```

**Performance Tips**:
- Always use WHERE clauses on indexed columns
- Limit result sets (never return unbounded queries)
- Use `scalars().first()` for single results, `.all()` for lists
- Call `commit()` explicitly for writes, `refresh()` to reload

## Data Modeling

### Combined SQLModel + Pydantic Pattern
```python
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import date

# ORM Model (database table)
class Order(SQLModel, table=True):
    __tablename__ = "orders_synced"
    
    o_orderkey: int = Field(primary_key=True)
    o_custkey: int
    o_orderstatus: str
    o_totalprice: float
    o_orderdate: date
    o_orderpriority: str
    o_clerk: str
    o_shippriority: int
    o_comment: str

# Response Model (API output)
class OrderRead(SQLModel):
    o_orderkey: int
    o_custkey: int
    o_orderstatus: str
    o_totalprice: float
    o_orderdate: date
    # Exclude sensitive fields like comments if needed

# Update Model (API input)
class OrderStatusUpdate(SQLModel):
    o_orderstatus: str = Field(
        ..., 
        regex="^[A-Z]$",  # Validate single char
        description="New order status"
    )

# Pagination Response
class OrderListResponse(SQLModel):
    orders: list[OrderRead]
    pagination: PaginationInfo
```

**Pattern Benefits**:
- Single source of truth for table schema
- Type safety between DB and API layers
- Automatic OpenAPI docs generation
- Validation on input, serialization on output

## Error Handling & Logging

```python
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

@router.get("/orders/{order_key}")
async def get_order(order_key: int, db: AsyncSession = Depends(get_async_db)):
    try:
        # Business logic validation
        if order_key <= 0:
            raise HTTPException(400, "Invalid order key")
        
        # Database operation
        result = await db.execute(...)
        order = result.scalars().first()
        
        if not order:
            raise HTTPException(404, f"Order {order_key} not found")
        
        return order
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
        
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Unexpected error fetching order {order_key}: {e}")
        raise HTTPException(500, "Internal server error")
```

**Logging Best Practices**:
- Use structured logging with context (user_id, request_id)
- Log at appropriate levels: ERROR for failures, INFO for operations, DEBUG for details
- Never log sensitive data (tokens, PII)
- Include operation timing for performance monitoring

## Environment Configuration

```python
# config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Lakebase Configuration
    lakebase_instance_name: str
    lakebase_database_name: str
    lakebase_catalog_name: str
    lakebase_host: str
    lakebase_port: int = 5432
    
    # Storage Configuration
    synced_table_storage_catalog: str
    synced_table_storage_schema: str
    
    # App Configuration
    app_env: str = "development"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

## Testing Strategy

### Unit Tests (Business Logic)
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_order_count(client: AsyncClient):
    response = await client.get("/api/v1/orders/count")
    assert response.status_code == 200
    assert "total_orders" in response.json()
    assert isinstance(response.json()["total_orders"], int)
```

### Integration Tests (Database)
```python
@pytest.mark.asyncio
async def test_update_order_status(client: AsyncClient, test_db):
    # Create test order
    test_order_key = 999999
    
    # Update status
    response = await client.post(
        f"/api/v1/orders/{test_order_key}/status",
        json={"o_orderstatus": "F"}
    )
    
    assert response.status_code == 200
    assert response.json()["o_orderstatus"] == "F"
```

## Deployment Considerations

### Environment Variables
```bash
# Required for Lakebase connection
LAKEBASE_INSTANCE_NAME=my-instance
LAKEBASE_DATABASE_NAME=my_db
LAKEBASE_HOST=xxxxx.cloud.databricks.com
DATABRICKS_TOKEN=dapi...

# Required for resource creation
SYNCED_TABLE_STORAGE_CATALOG=main
SYNCED_TABLE_STORAGE_SCHEMA=default
```

### Databricks App Deployment
```yaml
# databricks.yml
resources:
  apps:
    my_api:
      name: orders-api
      description: "FastAPI orders management"
      resources:
        - name: lakebase-instance
          permissions:
            - principal: app-service-principal
              permissions: ["CAN_CONNECT"]
```

### Required Permissions
- **Workspace**: App service principal creation
- **Unity Catalog**: CREATE on metastore, USE on storage catalog/schema
- **Lakebase**: CAN_CONNECT on instance, database role with SELECT/UPDATE on tables
- **Source Data**: SELECT on source tables (e.g., `samples.tpch.orders`)

## Common Gotchas

1. **OAuth Token Expiration**: Tokens expire after 1 hour. Implement refresh logic or use service principals with long-lived tokens.

2. **Async Session Scope**: Never share sessions across requests. Always use dependency injection with `Depends(get_async_db)`.

3. **Connection Pool Exhaustion**: Monitor pool usage. Increase `pool_size` and `max_overflow` if seeing connection timeouts.

4. **Synced Table Lag**: Synced tables are eventually consistent (minutes delay). Not suitable for real-time writes, use for read-optimized analytics queries.

5. **Query Performance**: Always have indexes on filter/join columns. Use EXPLAIN ANALYZE in PostgreSQL to verify query plans.

6. **Resource Costs**: Lakebase instances incur continuous costs. Delete test resources promptly. Consider auto-shutdown for dev environments.

7. **Large Responses**: Paginate all list endpoints. Never return unbounded queries. Set `le=1000` on page_size query params.

## Performance Optimization Checklist

- [ ] Use cursor-based pagination for large datasets
- [ ] Implement connection pooling with appropriate sizing
- [ ] Add indexes on frequently queried columns
- [ ] Use async/await consistently (no blocking operations)
- [ ] Cache expensive aggregations (counts, sums) when acceptable
- [ ] Implement query timeouts to prevent long-running queries
- [ ] Monitor slow query logs and optimize problematic queries
- [ ] Use `select()` with specific columns instead of `SELECT *`
- [ ] Batch operations when possible (bulk inserts/updates)
- [ ] Consider read replicas for high-read workloads (readable secondaries)

## Cost Management

**Resource Lifecycle Pattern**:
```
1. Create → Provision (minutes) → Active (billing)
2. Use → Query data (minimal cost per query)
3. Delete → Cleanup (stop billing)
```

**Cost Optimization**:
- Use smallest capacity tier sufficient for workload (`CU_1` for dev/test)
- Enable auto-pause for development environments
- Monitor query patterns and optimize expensive queries
- Delete unused instances (main cost driver)
- Synced table pipelines have minimal incremental cost

## Quick Reference

### HTTP Methods
- `GET`: Retrieve data (idempotent, cacheable)
- `POST`: Create/update resources, non-idempotent operations
- `DELETE`: Remove resources (idempotent)

### SQLAlchemy Async Patterns
```python
# Single result
result = await db.scalar(select(Model).where(...))

# Multiple results
results = await db.execute(select(Model).where(...))
items = results.scalars().all()

# Write operations
await db.commit()
await db.refresh(instance)
```

### Response Models
```python
# Success: Return data with 200
return {"data": result}

# Created: Return resource with 201
return JSONResponse(content={"id": new_id}, status_code=201)

# Error: Raise HTTPException
raise HTTPException(status_code=404, detail="Not found")
```

---

**For more examples**: See [databricks-apps-cookbook](https://github.com/databricks/databricks-apps-cookbook) repository.
