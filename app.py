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
    """Log configuration on startup for debugging"""
    logger.info("=" * 80)
    logger.info("FASHION ECOMMERCE APP STARTING")
    logger.info(f"Version: {settings.APP_VERSION}")
    logger.info("=" * 80)

    # Check environment variables
    client_id = os.getenv("DATABRICKS_CLIENT_ID")
    client_secret = os.getenv("DATABRICKS_CLIENT_SECRET")
    lakebase_pwd = os.getenv("LAKEBASE_PASSWORD")

    logger.info("AUTHENTICATION STATUS:")
    logger.info(f"  OAuth (Service Principal): {'✓ Available' if client_id and client_secret else '✗ Not configured'}")
    logger.info(f"  PAT Token (LAKEBASE_PASSWORD): {'✓ Available' if lakebase_pwd else '✗ Not set'}")

    logger.info("")
    logger.info("DATABASE CONNECTION:")
    logger.info(f"  Host: {settings.LAKEBASE_HOST}")
    logger.info(f"  Database: {settings.LAKEBASE_DATABASE}")
    logger.info(f"  User: {settings.LAKEBASE_USER}")
    logger.info(f"  SSL: {settings.LAKEBASE_SSL_MODE}")

    logger.info("")
    logger.info("AUTHENTICATION STRATEGY:")
    if client_id and client_secret:
        logger.info("  1. OAuth (preferred - bypasses IP ACL)")
        logger.info("  2. PAT token (fallback)")
    elif lakebase_pwd:
        logger.info("  Using PAT token from LAKEBASE_PASSWORD")
    else:
        logger.error("  ❌ No authentication configured!")

    logger.info("=" * 80)

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
