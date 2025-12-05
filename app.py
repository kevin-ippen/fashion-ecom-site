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

# Create FastAPI app
app = FastAPI(
    title="Fashion Ecommerce - Visual Search Demo",
    description="A modern ecommerce storefront with AI-powered visual search and personalized recommendations, built on Databricks",
    version="1.0.0",
)

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
    """Cleanup on shutdown"""
    from repositories.lakebase import lakebase_repo
    lakebase_repo.close()
