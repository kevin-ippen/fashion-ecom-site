"""
FastAPI application for Fashion Ecommerce Demo
Optimized for Databricks Apps deployment
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from core.config import settings
from routes import api_router
import os
import logging
import sys

# Configure logging for Databricks Apps
# IMPORTANT: Databricks Apps only captures logs written to stdout/stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Explicitly log to stdout for Databricks Apps
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Fashion Ecommerce - Visual Search Demo",
    description="A modern ecommerce storefront with AI-powered visual search and personalized recommendations, built on Databricks",
    version="1.0.0",
)

# Startup event to log environment configuration
@app.on_event("startup")
async def startup_event():
    """Log configuration on startup for debugging

    Note: These logs are written to stdout and will appear in:
    - Databricks Apps UI > Your App > Logs tab
    - https://your-app-url/logz endpoint
    """
    print("=" * 80)  # Also use print() to ensure visibility in stdout
    logger.info("=" * 80)
    logger.info("FASHION ECOMMERCE APP STARTING")
    logger.info("App Version: 1.0.0")
    logger.info("Logs visible at: <your-app-url>/logz or Databricks Apps UI > Logs tab")
    logger.info("=" * 80)

    # Check environment variables
    db_host = os.getenv("DATABRICKS_HOST", "NOT SET")
    db_token = os.getenv("DATABRICKS_TOKEN", "NOT SET")
    lakebase_pwd = os.getenv("LAKEBASE_PASSWORD", "NOT SET")

    # Helper to detect literal secret references
    def is_literal_reference(value: str) -> bool:
        return value.startswith("${") and value.endswith("}")

    logger.info("ENVIRONMENT VARIABLES:")
    logger.info(f"  DATABRICKS_HOST: {'SET' if db_host != 'NOT SET' else 'NOT SET'}")

    if db_token != "NOT SET":
        if is_literal_reference(db_token):
            logger.warning(f"  DATABRICKS_TOKEN: LITERAL REFERENCE (not expanded): {db_token[:20]}...")
        else:
            logger.info(f"  DATABRICKS_TOKEN: SET (starts with: {db_token[:8]}...)")
    else:
        logger.info(f"  DATABRICKS_TOKEN: NOT SET")

    if lakebase_pwd != "NOT SET":
        if is_literal_reference(lakebase_pwd):
            logger.warning(f"  LAKEBASE_PASSWORD: LITERAL REFERENCE (not expanded): {lakebase_pwd[:25]}...")
            logger.warning(f"  ⚠️  app.yaml secret injection FAILED - env var contains literal string!")
        else:
            logger.info(f"  LAKEBASE_PASSWORD: SET (starts with: {lakebase_pwd[:8]}...)")
    else:
        logger.info(f"  LAKEBASE_PASSWORD: NOT SET")

    # Log which token will be used
    logger.info("")
    logger.info("AUTHENTICATION STRATEGY:")
    if lakebase_pwd != "NOT SET" and not is_literal_reference(lakebase_pwd):
        logger.info("  ✓ Will use LAKEBASE_PASSWORD for database authentication")
    elif db_token != "NOT SET" and not is_literal_reference(db_token):
        logger.warning("  ⚠️  LAKEBASE_PASSWORD not valid - falling back to DATABRICKS_TOKEN")
    else:
        logger.warning("  ⚠️  No valid environment variables found")
        logger.info("  → Will attempt to fetch from Databricks Secrets API")

    logger.info("")
    logger.info("SECRETS API FALLBACK:")
    logger.info("  Scope: redditscope")
    logger.info("  Key: redditkey")
    logger.info("  This will be used if env vars are not valid")
    logger.info("=" * 80)
    print("=" * 80)  # Close with print() too

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# Include API router - automatically prefixed with /api for Databricks Apps auth
app.include_router(api_router)

# Check if frontend is built
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
frontend_built = os.path.exists(frontend_dist)

# Serve frontend if built, otherwise serve API info at root
if frontend_built:
    from fastapi.responses import FileResponse

    # Mount static assets
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    # Serve frontend at root and all other non-API routes
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend for all non-API routes (SPA routing)"""
        # Don't interfere with API or health routes
        if full_path.startswith("api/") or full_path == "health":
            return {"error": "Not found"}

        # Serve index.html for all routes (including root)
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "Frontend not built"}
else:
    # Development mode - no frontend built, show API info at root
    @app.get("/")
    async def root():
        """Root endpoint - API info (dev mode only)"""
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/docs",
            "api": "/api/v1",
            "note": "Frontend not built. Run 'cd frontend && npm run build' or use dev server on port 3000"
        }


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown - close database connections"""
    from core.database import engine
    await engine.dispose()
