#!/bin/bash
# Frontend Build Script for Fashion Ecommerce Site

set -e  # Exit on error

echo "=================================="
echo "Fashion Ecommerce - Frontend Build"
echo "=================================="
echo ""

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Check if frontend directory exists
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "❌ Error: frontend/ directory not found"
    exit 1
fi

cd "$FRONTEND_DIR"

echo "📂 Working directory: $FRONTEND_DIR"
echo ""

# Step 1: Check Node.js version
echo "Step 1: Checking Node.js version..."
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed"
    echo "   Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v)
echo "✅ Node.js version: $NODE_VERSION"
echo ""

# Step 2: Check npm
echo "Step 2: Checking npm..."
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed"
    exit 1
fi

NPM_VERSION=$(npm -v)
echo "✅ npm version: $NPM_VERSION"
echo ""

# Step 3: Install dependencies
echo "Step 3: Installing dependencies..."
if [ ! -d "node_modules" ]; then
    echo "📦 Installing packages (this may take a few minutes)..."
    npm install
    echo "✅ Dependencies installed"
else
    echo "✅ node_modules/ exists, skipping install"
    echo "   (Run 'rm -rf node_modules && npm install' to reinstall)"
fi
echo ""

# Step 4: Build the frontend
echo "Step 4: Building frontend..."
echo "🔨 Running: npm run build"
npm run build

# Step 5: Verify build
echo ""
echo "Step 5: Verifying build..."

if [ -f "dist/index.html" ]; then
    echo "✅ dist/index.html exists"
else
    echo "❌ Error: dist/index.html not found"
    exit 1
fi

if [ -d "dist/assets" ]; then
    echo "✅ dist/assets/ directory exists"

    # Count files in assets
    ASSET_COUNT=$(ls -1 dist/assets | wc -l)
    echo "   Found $ASSET_COUNT asset file(s)"

    # List assets
    echo "   Assets:"
    ls -lh dist/assets/ | tail -n +2 | awk '{print "   - " $9 " (" $5 ")"}'
else
    echo "❌ Error: dist/assets/ directory not found"
    exit 1
fi

echo ""
echo "=================================="
echo "✅ Build Complete!"
echo "=================================="
echo ""
echo "Build output location: $FRONTEND_DIR/dist/"
echo ""
echo "Next steps:"
echo "1. Start backend: uvicorn app:app --reload --port 8000"
echo "2. Visit: http://localhost:8000"
echo ""
echo "Or for development:"
echo "1. Terminal 1: uvicorn app:app --reload --port 8000"
echo "2. Terminal 2: cd frontend && npm run dev"
echo "3. Visit: http://localhost:3000"
echo ""
