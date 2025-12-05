# Frontend Build Instructions

## Quick Start (One Command)

From the **project root**:
```bash
./BUILD_FRONTEND.sh
```

This automated script will:
1. ✅ Check Node.js and npm are installed
2. ✅ Install dependencies
3. ✅ Build the frontend
4. ✅ Verify the build succeeded

---

## Manual Build (Step by Step)

### Prerequisites
- Node.js 18+ ([download here](https://nodejs.org/))
- npm (comes with Node.js)

### Step 1: Navigate to Frontend Directory
```bash
cd frontend
```

### Step 2: Install Dependencies
```bash
npm install
```

**What this does:**
- Reads `package.json`
- Downloads all packages to `node_modules/`
- Creates `package-lock.json` for version locking
- Takes 1-3 minutes depending on internet speed

**Expected output:**
```
added 250 packages in 45s
```

**Common issues:**
- `npm: command not found` → Install Node.js
- `EACCES: permission denied` → Don't use sudo, fix npm permissions
- `network timeout` → Check internet connection or try `npm install --verbose`

### Step 3: Build for Production
```bash
npm run build
```

**What this does:**
- Runs TypeScript compiler (`tsc`) to check for errors
- Runs Vite build to bundle the app
- Outputs to `dist/` directory
- Minifies JavaScript and CSS
- Generates hashed filenames for caching

**Expected output:**
```
vite v5.0.11 building for production...
✓ 234 modules transformed.
dist/index.html                   0.46 kB │ gzip:  0.30 kB
dist/assets/index-CRnX73c-.js   378.64 kB │ gzip: 98.12 kB
dist/assets/index-D2y37GRj.css   24.19 kB │ gzip:  6.45 kB
✓ built in 2.34s
```

**Common issues:**
- TypeScript errors → Fix the errors shown, then rebuild
- Out of memory → Increase Node.js memory: `NODE_OPTIONS="--max-old-space-size=4096" npm run build`
- Build fails → Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`

### Step 4: Verify Build Output
```bash
ls -la dist/
```

**Expected structure:**
```
dist/
├── index.html              # Entry point (464 bytes)
└── assets/
    ├── index-[hash].js     # JavaScript bundle (~378KB)
    └── index-[hash].css    # CSS bundle (~24KB)
```

**Verify files exist:**
```bash
test -f dist/index.html && echo "✅ index.html exists" || echo "❌ Missing"
test -d dist/assets && echo "✅ assets/ exists" || echo "❌ Missing"
```

---

## Development Mode (Hot Reload)

For development, use the dev server instead of building:

```bash
npm run dev
```

**What this does:**
- Starts Vite dev server on port 3000
- Enables hot module replacement (HMR)
- Shows errors in browser overlay
- Proxies `/api/*` requests to backend on port 8000

**Access:** http://localhost:3000

**To use:**
1. Terminal 1: `uvicorn app:app --reload --port 8000` (backend)
2. Terminal 2: `npm run dev` (frontend)

---

## Production vs Development

### Production Mode (Built)
```bash
npm run build
uvicorn app:app --port 8000
```
- ✅ Single server (port 8000)
- ✅ Optimized bundles
- ✅ Fast load times
- ✅ Ready for deployment
- ❌ No hot reload

**Access:** http://localhost:8000

### Development Mode (Dev Server)
```bash
# Terminal 1
uvicorn app:app --reload --port 8000

# Terminal 2
npm run dev
```
- ✅ Hot reload on changes
- ✅ Better error messages
- ✅ Source maps for debugging
- ✅ Fast rebuild times
- ❌ Two servers needed

**Access:** http://localhost:3000

---

## Build Output Details

### index.html
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Fashion Ecommerce</title>
    <script type="module" src="/assets/index-[hash].js"></script>
    <link rel="stylesheet" href="/assets/index-[hash].css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
```

### Assets Directory
- **JavaScript bundle**: All React code, components, libraries minified
- **CSS bundle**: All Tailwind CSS, component styles minified
- **Hash in filename**: Enables long-term caching (e.g., `index-CRnX73c-.js`)

---

## Troubleshooting

### Issue: "npm: command not found"
**Solution:** Install Node.js from https://nodejs.org/

Verify installation:
```bash
node -v  # Should show v18.x.x or higher
npm -v   # Should show 9.x.x or higher
```

### Issue: "Cannot find module"
**Solution:** Reinstall dependencies:
```bash
rm -rf node_modules package-lock.json
npm install
```

### Issue: Build fails with TypeScript errors
**Solution:** Fix the TypeScript errors shown in the output, then rebuild.

Common fixes:
- Missing types: `npm install -D @types/[package-name]`
- Wrong import: Check file paths and exports
- Type mismatch: Update types or add type assertion

### Issue: Build succeeds but app is blank
**Causes:**
1. JavaScript errors (check browser console)
2. Wrong base path in vite.config.ts
3. Missing environment variables

**Debug:**
```bash
# Check if files exist
ls -lh dist/assets/

# Start server and check browser console (F12)
uvicorn app:app --port 8000

# Check network tab for 404s
```

### Issue: Assets return 404
**Cause:** Backend not configured to serve static files

**Solution:** Check `app.py` has:
```python
app.mount("/assets", StaticFiles(directory="frontend/dist/assets"))
```

### Issue: "ENOSPC: System limit for number of file watchers reached"
**Solution (Linux only):**
```bash
echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

---

## Clean Build

To completely clean and rebuild:

```bash
# Remove all build artifacts
rm -rf dist node_modules package-lock.json

# Reinstall and rebuild
npm install
npm run build
```

---

## Build for Databricks Apps

Before deploying to Databricks:

```bash
# 1. Clean build
rm -rf dist
npm run build

# 2. Verify
ls -lh dist/
ls -lh dist/assets/

# 3. Test locally
uvicorn app:app --port 8000
# Visit http://localhost:8000

# 4. Deploy
databricks apps create fashion-ecom-app --source-code-path .
```

---

## Scripts Available

All scripts defined in `package.json`:

```bash
npm run dev      # Start dev server (port 3000)
npm run build    # Build for production
npm run preview  # Preview production build locally
npm run lint     # Run ESLint
```

---

## Performance Tips

### Optimize Build Time
```bash
# Use more CPU cores
npm run build -- --parallel

# Skip type checking (faster, but risky)
npm run build -- --mode production --no-types
```

### Optimize Bundle Size
```bash
# Analyze bundle
npm run build -- --report

# Check what's in the bundle
npx vite-bundle-visualizer
```

### Cache Dependencies
```bash
# Use npm ci for faster installs in CI/CD
npm ci  # Uses package-lock.json exactly
```

---

## Summary

**Quick commands:**
```bash
# Development (recommended for local work)
npm run dev

# Production (for deployment)
npm run build
```

**After building, the backend serves:**
- Frontend: `http://localhost:8000/`
- API: `http://localhost:8000/api/v1/`
- Docs: `http://localhost:8000/docs`

**Files to commit:**
- ✅ `package.json`
- ✅ `package-lock.json`
- ❌ `node_modules/` (gitignored)
- ❌ `dist/` (gitignored)
