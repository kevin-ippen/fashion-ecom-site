# Setup and Testing Guide

## Quick Start Overview

This fashion ecommerce demo consists of:
- **Backend**: FastAPI (Python) connected to Databricks Unity Catalog
- **Frontend**: React + TypeScript with Vite

## Prerequisites

### Required
- Python 3.9+
- Node.js 18+
- Databricks workspace with:
  - Unity Catalog access
  - SQL Warehouse
  - Tables: `main.fashion_demo.products`, `main.fashion_demo.users`, etc.
  - UC Volume: `/Volumes/main/fashion_demo/raw_data/images/`

### Optional (for full functionality)
- Databricks Model Serving endpoint (CLIP embeddings)

## Backend Setup

### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the `backend` directory:

```bash
cp .env.example .env
```

Edit `.env` with your Databricks credentials:

```env
DATABRICKS_HOST=your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi1234567890abcdef...
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/abc123def456

# Optional - for CLIP integration
CLIP_ENDPOINT=https://your-workspace.cloud.databricks.com/serving-endpoints/clip-endpoint/invocations
```

**How to get these values:**
- `DATABRICKS_HOST`: Your workspace URL (without https://)
- `DATABRICKS_TOKEN`: Generate from User Settings > Developer > Access Tokens
- `DATABRICKS_HTTP_PATH`: Get from SQL Warehouse > Connection Details

### 3. Test Backend Connection

Start the backend server:

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Visit http://localhost:8000/docs to see the interactive API documentation.

### 4. Test API Endpoints

#### Health Check
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

#### List Products
```bash
curl "http://localhost:8000/api/products?page=1&page_size=5"
```

#### Get Personas
```bash
curl http://localhost:8000/api/users
```

#### Get Recommendations
```bash
curl "http://localhost:8000/api/search/recommendations/user_001?limit=5"
```

## Frontend Setup

### 1. Install Node Dependencies

```bash
cd frontend
npm install
```

### 2. Start Development Server

```bash
npm run dev
```

The frontend will be available at http://localhost:3000

The Vite dev server is configured to proxy API requests to the backend at `localhost:8000`.

### 3. Build for Production

```bash
npm run build
```

The built files will be in `frontend/dist/`.

## Testing the Application

### Test Flow 1: Browse Products
1. Navigate to http://localhost:3000
2. Click "Shop Now" or go to Products page
3. Try different filters (gender, category, color, etc.)
4. Use pagination to browse multiple pages
5. Click on a product to view details

### Test Flow 2: Persona Experience
1. Click "Select Persona" in the header
2. Choose a persona (e.g., "Luxury Fashionista")
3. Observe personalized recommendations on the home page
4. Note the personalization badges on product cards
5. Click "View Profile" to see persona details
6. View purchase history and preferences

### Test Flow 3: Search
1. Go to the Search page
2. **Text Search**:
   - Try "casual shirt"
   - Try "formal shoes"
   - Try "summer dress"
3. **Image Search**:
   - Upload a fashion image
   - View similar products
   - Note similarity scores (if persona is active)

### Test Flow 4: Shopping Cart
1. Add products to cart from any page
2. Adjust quantities in cart
3. Remove items
4. View total with shipping and tax
5. Click "Proceed to Checkout" (mock checkout)
6. See success message

### Test Flow 5: Product Detail
1. Click any product
2. View full details and images
3. Adjust quantity
4. Add to cart
5. View "Similar Products" section
6. Note personalization info (if persona active)

## Common Issues and Solutions

### Backend Issues

#### Issue: Import Errors
```
ModuleNotFoundError: No module named 'backend'
```
**Solution**: Run uvicorn from the `backend` directory:
```bash
cd backend
python -m uvicorn app.main:app --reload
```

#### Issue: Database Connection Failed
```
Error connecting to Databricks
```
**Solution**:
- Verify your `.env` credentials
- Check that SQL Warehouse is running
- Test connection in Databricks SQL editor

#### Issue: Images Not Loading
```
404: Image not found
```
**Solution**:
- Verify UC Volume path in config
- Check that images exist in `/Volumes/main/fashion_demo/raw_data/images/`
- Ensure you have read access to the volume

### Frontend Issues

#### Issue: API Calls Failing
```
Network Error / CORS Error
```
**Solution**:
- Ensure backend is running on port 8000
- Check Vite proxy configuration in `vite.config.ts`
- Verify no firewall blocking localhost

#### Issue: Build Fails
```
Type errors or module not found
```
**Solution**:
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

#### Issue: Hot Reload Not Working
**Solution**:
- Restart the Vite dev server
- Clear browser cache
- Check no syntax errors in console

## Testing Without Databricks Connection

If you don't have Databricks credentials yet, you can:

### 1. Mock Backend Mode

Create a simple mock server in `backend/mock_server.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/api/products")
def products():
    return {
        "products": [
            {
                "product_id": "1",
                "product_display_name": "Test Product",
                "price": 29.99,
                "base_color": "Blue",
                "master_category": "Apparel",
                "image_url": "https://via.placeholder.com/300x400"
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 24,
        "has_more": False
    }

@app.get("/api/users")
def users():
    # Return personas from data/personas.json
    import json
    with open("../data/personas.json") as f:
        data = json.load(f)
    return data["personas"]
```

Run with:
```bash
uvicorn mock_server:app --reload --port 8000
```

### 2. Frontend Component Testing

Test individual React components in isolation without API calls.

## Performance Tips

### Backend
- Use SQL Warehouse's auto-scaling for variable load
- Enable query result caching in Databricks
- Consider adding Redis for API response caching

### Frontend
- Images lazy-load automatically
- React Query caches API responses (5 min default)
- Cart and persona state persist to localStorage

## Deployment to Databricks Apps

### 1. Prepare for Deployment

```bash
# Build frontend
cd frontend
npm run build

# The backend will serve the built frontend
```

### 2. Update databricks.yml

Verify the configuration is correct for your workspace.

### 3. Deploy

```bash
databricks apps create fashion-ecom-app --config databricks.yml
```

### 4. Access Your App

The app will be available at:
```
https://your-workspace.cloud.databricks.com/apps/fashion-ecom-app
```

## Next Steps

After basic testing, you can:
1. Connect CLIP model serving endpoint for real semantic search
2. Add more personas with different profiles
3. Customize UI theme and branding
4. Add analytics tracking
5. Implement A/B testing for recommendations

## Support

For issues:
1. Check backend logs: `uvicorn` console output
2. Check frontend console: Browser DevTools
3. Check network tab for API calls
4. Verify Databricks connectivity with `databricks-cli`

## Feature Checklist

- ✅ Product catalog with filtering
- ✅ Pagination
- ✅ Product detail pages
- ✅ User personas (5 types)
- ✅ Personalized recommendations
- ✅ Text search (basic)
- ✅ Image upload search (ready for CLIP)
- ✅ Shopping cart
- ✅ Mock checkout
- ✅ User profile pages
- ⏳ CLIP integration (ready, needs endpoint)
- ⏳ Real-time similarity scoring (ready, needs CLIP)
