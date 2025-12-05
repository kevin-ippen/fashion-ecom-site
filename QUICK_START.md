# Quick Start Guide

## Problem: Backend Running But Frontend Not Connecting

### Issue
✅ Backend is running on port 8000
❌ Frontend is NOT running on port 3000

### Solution: Start Both Servers

## Step-by-Step Setup

### Terminal 1: Backend (FastAPI)

```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site

# Install Python dependencies (if not already done)
pip install -r requirements.txt

# Start backend
uvicorn app:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Terminal 2: Frontend (React + Vite)

```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site/frontend

# Install Node dependencies (first time only)
npm install

# Start frontend dev server
npm run dev
```

**Expected output:**
```
  VITE v5.0.11  ready in 500 ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: use --host to expose
  ➜  press h to show help
```

## Verify Setup

### 1. Check Backend
```bash
curl http://localhost:8000/
# Should return: {"app":"Fashion Ecommerce API","version":"1.0.0",...}

curl http://localhost:8000/api/v1/healthcheck
# Should return: {"status":"healthy","timestamp":"..."}
```

### 2. Check Frontend
Open browser: http://localhost:3000

You should see the Fashion Ecommerce homepage.

### 3. Check API Communication
The frontend at http://localhost:3000 will make API calls to http://localhost:8000/api/v1/*

Vite dev server automatically proxies `/api` requests to port 8000.

## How It Works

```
Browser (http://localhost:3000)
    ↓
Vite Dev Server (port 3000)
    ↓ proxy /api/* requests
FastAPI Backend (port 8000)
    ↓
Databricks Unity Catalog
```

## Common Issues

### Issue: "Port 3000 already in use"
```bash
# Find process using port 3000
lsof -ti:3000

# Kill it
kill -9 $(lsof -ti:3000)

# Or use a different port
npm run dev -- --port 3001
```

### Issue: "Port 8000 already in use"
```bash
# Find process using port 8000
lsof -ti:8000

# Kill it
kill -9 $(lsof -ti:8000)
```

### Issue: "Module not found" errors in frontend
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Issue: CORS errors
The backend is configured with `CORS_ORIGINS: ["*"]` which allows all origins.
If you still see CORS errors, make sure:
1. Backend is running on port 8000
2. Frontend is running on port 3000
3. Check browser console for actual error

### Issue: API calls returning 404
Check that API endpoints use the correct path:
- ✅ `/api/v1/products`
- ❌ `/products`
- ❌ `/api/products`

## Environment Variables

### Backend (.env in root)
```bash
DATABRICKS_HOST=your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...
```

### Frontend
No environment variables needed for local development.
Vite proxy handles API routing automatically.

## Production Build

### Build Frontend
```bash
cd frontend
npm run build
```

Built files go to `frontend/dist/`

### Run Production
```bash
# From root
uvicorn app:app --host 0.0.0.0 --port 8000
```

FastAPI will serve the built frontend files automatically.

## Quick Test Commands

```bash
# Terminal 1: Start backend
uvicorn app:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend && npm run dev

# Terminal 3: Test endpoints
curl http://localhost:8000/api/v1/healthcheck
curl http://localhost:8000/api/v1/users

# Browser: Open
open http://localhost:3000
```

## Troubleshooting Checklist

- [ ] Backend running on port 8000?
- [ ] Frontend running on port 3000?
- [ ] `npm install` completed successfully?
- [ ] No console errors in browser?
- [ ] Backend accessible at http://localhost:8000/docs?
- [ ] Frontend accessible at http://localhost:3000?
- [ ] API calls visible in Network tab?
- [ ] Vite proxy forwarding requests?

## Success Indicators

✅ Backend: Visit http://localhost:8000/docs - See Swagger UI
✅ Frontend: Visit http://localhost:3000 - See homepage
✅ API: Open browser console → Network tab → See `/api/v1/*` calls
✅ Data: Products load on homepage
✅ Personas: Can select and switch personas

---

## TL;DR

```bash
# Terminal 1
uvicorn app:app --reload --port 8000

# Terminal 2
cd frontend && npm install && npm run dev

# Browser
open http://localhost:3000
```

**Both servers must be running for the app to work!**
