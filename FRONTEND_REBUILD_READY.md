# Frontend Rebuild - Ready to Execute

## Status: ✅ No Changes Needed!

### Good News: Frontend is Already Dynamic

The frontend **fetches personas from the API** at runtime, so updating `personas.json` on the backend automatically updates the frontend. No hardcoded user IDs found!

**Evidence**:
- [frontend/src/components/user/PersonaSelector.tsx:16](frontend/src/components/user/PersonaSelector.tsx#L16)
  ```typescript
  const { data: personas, isLoading } = useQuery({
    queryKey: ['personas'],
    queryFn: usersApi.listPersonas,  // ✅ Fetches from API
  });
  ```

**No hardcoded references** to:
- `user_001`, `user_002`, `user_003`, `user_004`, `user_005` (old IDs)

---

## Updated Personas (from data/personas.json)

The backend now uses **real user IDs** from the database:

| Old ID | New ID | Name | Segment |
|--------|--------|------|---------|
| user_001 | **user_006327** | Budget-Conscious Shopper | budget |
| user_002 | **user_007598** | Athletic Performance | athletic |
| user_003 | **user_008828** | Luxury Fashionista | luxury |
| user_004 | **user_001328** | Casual Accessories Lover | casual |
| user_005 | **user_009809** | Vintage Style Enthusiast | vintage |

---

## Build Script: BUILD_FRONTEND.sh

**Location**: `/Users/kevin.ippen/projects/fashion-ecom-site/BUILD_FRONTEND.sh`

**What it does**:
1. ✅ Checks Node.js/npm versions
2. ✅ Installs dependencies (if needed, skips if `node_modules/` exists)
3. ✅ Runs `npm run build` (TypeScript compile + Vite build)
4. ✅ Verifies build output (`dist/index.html`, `dist/assets/`)
5. ✅ Shows next steps

**Output location**: `frontend/dist/`

---

## How to Execute

### Option 1: Run the Script (Recommended)

```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site
chmod +x BUILD_FRONTEND.sh
./BUILD_FRONTEND.sh
```

**Expected output**:
```
==================================
Fashion Ecommerce - Frontend Build
==================================

Step 1: Checking Node.js version...
✅ Node.js version: v18.x.x

Step 2: Checking npm...
✅ npm version: 9.x.x

Step 3: Installing dependencies...
✅ node_modules/ exists, skipping install

Step 4: Building frontend...
🔨 Running: npm run build
...

Step 5: Verifying build...
✅ dist/index.html exists
✅ dist/assets/ directory exists
   Found X asset file(s)

==================================
✅ Build Complete!
==================================

Build output location: .../frontend/dist/
```

### Option 2: Manual Build (Alternative)

```bash
cd /Users/kevin.ippen/projects/fashion-ecom-site/frontend
npm install  # if needed
npm run build
```

---

## What Gets Built

**TypeScript Files** (`src/`) → **JavaScript Bundles** (`dist/assets/`)

**Key Files**:
- `dist/index.html` - Main HTML entry point
- `dist/assets/index-[hash].js` - Bundled JavaScript
- `dist/assets/index-[hash].css` - Bundled CSS
- `dist/vite.svg` - Favicon

**Assets are hashed** for cache busting (e.g., `index-D2y37GRj.css`)

---

## Testing After Build

### 1. Test Personas Load Correctly

Start the app and check personas:

```bash
# Backend
uvicorn app:app --reload --port 8000

# Frontend (dev mode)
cd frontend && npm run dev
# Visit: http://localhost:3000
```

**Or serve production build**:
```bash
# Backend serves frontend at root
uvicorn app:app --port 8000
# Visit: http://localhost:8000
```

**Open persona selector** and verify:
- ✅ All 5 personas appear
- ✅ User IDs are `user_006327`, `user_007598`, etc. (new IDs)
- ✅ Names: "Budget-Conscious Shopper", "Athletic Performance", etc.
- ✅ Clicking a persona loads recommendations

### 2. Test Recommendations Work

1. Select a persona (e.g., "Luxury Fashionista")
2. Go to Home or Products page
3. Verify personalized products appear
4. Check console logs for:
   ```
   Getting recommendations for user user_008828 - Luxury Fashionista
   Persona preferences: categories=['Accessories', 'Apparel', 'Footwear'], colors=['Black', 'White', 'Brown', 'Blue', 'Grey']
   ```

### 3. Test Search Still Works

- Text search: Type "dress" → Should return results
- Image search: Upload an image → Should return similar products

---

## Troubleshooting

### Issue: "npm: command not found"

**Solution**: Install Node.js
```bash
# macOS
brew install node

# Or download from: https://nodejs.org/
```

### Issue: "node_modules/ taking too long"

**Solution**: Skip if already installed
```bash
# The script automatically skips if node_modules/ exists
# To force reinstall:
cd frontend
rm -rf node_modules
npm install
```

### Issue: "Build fails with TypeScript errors"

**Solution**: Check for missing dependencies
```bash
cd frontend
npm install
npm run build
```

**Common errors**:
- Missing `@types/*` packages → Run `npm install`
- Outdated packages → Run `npm update`

### Issue: "Personas not showing up"

**Possible causes**:
1. Backend not running → Start: `uvicorn app:app --port 8000`
2. API endpoint failing → Check logs
3. CORS issue → Backend should allow frontend origin

**Debug**:
```bash
# Check personas API
curl http://localhost:8000/api/v1/users | jq

# Should return:
# [
#   {"user_id": "user_006327", "name": "Budget-Conscious Shopper", ...},
#   {"user_id": "user_007598", "name": "Athletic Performance", ...},
#   ...
# ]
```

---

## Deployment

### For Databricks Apps

The frontend `dist/` directory is served by FastAPI:

```python
# app.py
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
```

**After building**:
1. Build frontend: `./BUILD_FRONTEND.sh`
2. Commit changes: `git add frontend/dist && git commit`
3. Deploy: `databricks apps deploy`

**Or let Databricks build**:
- Add build step to `app.yaml` (if supported)
- Or build locally and commit `dist/`

---

## Summary

✅ **Frontend is ready** - No code changes needed
✅ **Build script exists** - `./BUILD_FRONTEND.sh`
✅ **Personas are dynamic** - Fetched from API at runtime
✅ **Just run the script** - `./BUILD_FRONTEND.sh`

**After building, commit and push**:
```bash
git add frontend/dist
git commit -m "build: Rebuild frontend with updated personas"
git push
```
