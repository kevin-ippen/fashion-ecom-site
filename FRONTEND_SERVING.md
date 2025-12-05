# Frontend Serving Configuration

## Current Status

✅ **Frontend is built correctly**
- Location: `frontend/dist/`
- index.html exists
- assets/ directory exists with JS and CSS bundles

✅ **Backend configured to serve frontend**
- Static assets mounted at `/assets`
- SPA routing configured for React Router

## How It Works

### Development Mode (Two Servers)

```
Frontend Dev Server (Vite) → Port 3000
  ↓ (proxies /api/* requests)
Backend API (FastAPI) → Port 8000
```

**Commands:**
```bash
# Terminal 1: Backend
uvicorn app:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

**Access:** http://localhost:3000

### Production Mode (Single Server)

```
Browser → FastAPI (Port 8000)
  ↓
  ├─ /api/v1/* → API routes
  ├─ /assets/* → Static files (JS, CSS)
  └─ /* → index.html (SPA routing)
```

**Commands:**
```bash
# Build frontend
cd frontend && npm run build

# Start server (serves both API and frontend)
uvicorn app:app --host 0.0.0.0 --port 8000
```

**Access:** http://localhost:8000

## Route Priority (Important!)

The order matters in FastAPI:

1. **Root endpoint** (`/`) - Returns API info JSON
2. **Health check** (`/health`) - Returns health status
3. **API routes** (`/api/v1/*`) - All API endpoints
4. **Static assets** (`/assets/*`) - JS, CSS files
5. **Catch-all** (`/{full_path:path}`) - Serves index.html for SPA routing

### Why Order Matters

❌ **Wrong Order** (catch-all before specific routes):
```python
@app.get("/{full_path:path}")  # This catches everything!
async def serve_frontend(full_path: str):
    return FileResponse("index.html")

@app.get("/")  # Never reached!
async def root():
    return {"status": "ok"}

app.include_router(api_router)  # Never reached!
```

✅ **Correct Order** (specific routes first):
```python
@app.get("/")
async def root():
    return {"status": "ok"}

app.include_router(api_router)  # /api/v1/*

@app.get("/{full_path:path}")  # Last - catches remaining routes
async def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        return {"error": "Not found"}
    return FileResponse("index.html")
```

## File Structure

```
frontend/dist/
├── index.html              # SPA entry point
└── assets/
    ├── index-[hash].js     # React app bundle
    └── index-[hash].css    # Styles bundle
```

### index.html References

```html
<script type="module" src="/assets/index-[hash].js"></script>
<link rel="stylesheet" href="/assets/index-[hash].css">
```

Note: Paths start with `/assets/` which matches the FastAPI mount point.

## Testing

### Test API Endpoints
```bash
curl http://localhost:8000/
# Returns: {"app":"Fashion Ecommerce API",...}

curl http://localhost:8000/api/v1/healthcheck
# Returns: {"status":"healthy",...}

curl http://localhost:8000/api/v1/products
# Returns: Product list
```

### Test Frontend Serving
```bash
curl http://localhost:8000/products
# Returns: HTML content (index.html)

curl http://localhost:8000/assets/index-[hash].js
# Returns: JavaScript bundle

curl -I http://localhost:8000/assets/index-[hash].css
# Returns: 200 OK with CSS content-type
```

### Test SPA Routing
Visit these URLs in browser (all should load the app):
- http://localhost:8000/products
- http://localhost:8000/search
- http://localhost:8000/cart
- http://localhost:8000/profile/user_001

React Router will handle the actual routing client-side.

## Common Issues

### Issue: 404 on /assets/* files

**Problem:** Assets not being served

**Check:**
```bash
ls -la frontend/dist/assets/
```

**Solution:** Make sure frontend is built:
```bash
cd frontend && npm run build
```

### Issue: API routes returning HTML instead of JSON

**Problem:** Catch-all route is interfering with API routes

**Solution:** Ensure routes are in correct order (specific before catch-all)

### Issue: Blank page on production build

**Causes:**
1. Frontend not built
2. Assets path mismatch
3. JavaScript errors

**Debug:**
```bash
# Check if dist exists
ls -la frontend/dist/

# Check browser console for errors
# Open browser DevTools → Console tab

# Check network tab for 404s
# Open browser DevTools → Network tab
```

### Issue: CORS errors in production

**Problem:** Frontend and backend on different origins

**Solution:** In production, both are served from same origin (port 8000), so CORS shouldn't be an issue. If you see CORS errors, it means you're still using the dev server on port 3000.

## Databricks Apps Deployment

When deployed to Databricks Apps, the same configuration works:

```yaml
# app.yaml
command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Before deployment:**
```bash
# Build frontend
cd frontend && npm run build

# Test locally
uvicorn app:app --port 8000

# Visit http://localhost:8000
# Should see React app (not JSON)
```

**Deploy:**
```bash
databricks apps create fashion-ecom-app --source-code-path .
```

## Environment-Specific Behavior

### Development
- Frontend: Port 3000 (Vite dev server)
- Backend: Port 8000 (FastAPI)
- Hot reload: Both enabled
- Proxy: Vite proxies /api to port 8000

### Production
- Frontend + Backend: Port 8000 (FastAPI serves both)
- Hot reload: Disabled
- Assets: Pre-built and cached

## Checklist Before Deployment

- [ ] Frontend built: `npm run build`
- [ ] `frontend/dist/index.html` exists
- [ ] `frontend/dist/assets/` has JS and CSS files
- [ ] Backend serves API correctly: `curl http://localhost:8000/api/v1/healthcheck`
- [ ] Backend serves frontend: Visit `http://localhost:8000` in browser
- [ ] No 404s in browser Network tab
- [ ] React Router works: Navigate to different pages
- [ ] API calls work from frontend
- [ ] No CORS errors in console

## Summary

✅ Frontend built correctly at `frontend/dist/`
✅ Backend configured to serve frontend in production
✅ Route ordering fixed (specific routes before catch-all)
✅ SPA routing works for React Router
✅ Both development and production modes supported

**For local development:** Use two servers (ports 3000 + 8000)
**For production/deployment:** Use single server (port 8000)
