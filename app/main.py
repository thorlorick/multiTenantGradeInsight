"""
FastAPI Main Application for Multi-Tenant Grade Insight

This is the entry point for the entire application.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database.connection import initialize_database, db_manager
from app.middleware.tenant import TenantMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle application startup and shutdown events.
    """
    # Startup
    print("🚀 Starting Multi-Tenant Grade Insight...")
    await initialize_database()
    print("✅ Application startup complete!")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down application...")
    await db_manager.close_all_connections()
    print("✅ Application shutdown complete!")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Multi-tenant grade management system for schools",
    lifespan=lifespan
)

# Add CORS middleware
if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add tenant middleware (this runs for every request)
app.add_middleware(TenantMiddleware)

# Templates for serving HTML
templates = Jinja2Templates(directory="templates")

# Static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Serve the main dashboard page.
    """
    return templates.TemplateResponse(
        "dashboard.html", 
        {"request": request}
    )


# Health check endpoint (no tenant required)
@app.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version
    }


# Import and include API routes
from app.api.routes import dashboard_api, students, grades, tenant

app.include_router(dashboard_api.router)
app.include_router(students.router)
app.include_router(grades.router)
app.include_router(tenants.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
