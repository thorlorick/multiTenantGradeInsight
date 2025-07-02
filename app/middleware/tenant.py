"""
Tenant Middleware for Multi-Tenant Grade Insight

This middleware is the security backbone of our multi-tenant system. It:
1. Detects which tenant (school) is making each request
2. Ensures requests are properly isolated to that tenant's data
3. Prevents accidental cross-tenant data access
4. Provides tenant context to all downstream handlers
"""

import re
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.database.connection import db_manager
from app.database.models import TenantRegistry

import uuid

class TenantMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # Define paths that don't require tenant validation
        self.exempt_paths = [
            "/",              # Tenant selection page
            "/health",        # Health check endpoint
            "/static",        # Static files (CSS, JS, images)
            "/docs",          # FastAPI auto-generated docs (optional)
            "/redoc",         # ReDoc documentation (optional)
            "/openapi.json"   # OpenAPI schema (optional)
        ]

    async def dispatch(self, request: Request, call_next):
        # Check if path should be exempt from tenant validation
        path = request.url.path
        
        # Allow exempt paths (including static files)
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            return await call_next(request)
        
        # For all other paths, require tenant validation
        tenant_id_header = request.headers.get("X-Tenant-ID")

        if not tenant_id_header:
            # Tenant ID missing
            raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")

        try:
            # Validate UUID format (adjust if tenant IDs are not UUIDs)
            tenant_id = uuid.UUID(tenant_id_header)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tenant ID format")

        # Store tenant_id on request.state for downstream access
        request.state.tenant_id = str(tenant_id)  # Convert back to string for consistency

        # Continue processing request
        response = await call_next(request)
        return response

def get_current_tenant_id(request: Request) -> str:
    """
    Get the current tenant ID from the request state.
    This function should be called after the TenantMiddleware has processed the request.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        str: The tenant ID as a string
        
    Raises:
        HTTPException: If tenant ID is not found in request state
    """
    if not hasattr(request.state, 'tenant_id'):
        raise HTTPException(
            status_code=500, 
            detail="Tenant ID not found in request state. Ensure TenantMiddleware is properly configured."
        )
    
    return request.state.tenant_id
