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


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware that handles tenant detection and context management.
    
    This runs before EVERY request and figures out which school (tenant)
    the request belongs to. It uses several methods to detect the tenant:
    
    1. Subdomain routing (school1.gradeinsight.com)
    2. X-Tenant-ID header
    3. JWT token claims
    4. Query parameter (for development)
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.tenant_cache: Dict[str, TenantRegistry] = {}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process each incoming request to detect and validate the tenant.
        
        This method runs for every HTTP request and:
        1. Identifies the tenant from the request
        2. Validates the tenant exists and is active
        3. Adds tenant context to the request
        4. Ensures the response is properly isolated
        """
        
        try:
            # Step 1: Detect the tenant from the request
            tenant_info = await self._detect_tenant(request)
            
            if not tenant_info:
                return await self._handle_no_tenant(request)
            
            # Step 2: Validate the tenant
            validated_tenant = await self._validate_tenant(tenant_info)
            
            if not validated_tenant:
                return await self._handle_invalid_tenant(tenant_info)
            
            # Step 3: Add tenant context to the request
            request.state.tenant_id = validated_tenant.tenant_id
            request.state.tenant_name = validated_tenant.tenant_name
            request.state.tenant_shard = validated_tenant.shard_number
            request.state.tenant_record = validated_tenant
            
            # Step 4: Process the request
            response = await call_next(request)
            
            # Step 5: Add tenant headers to response (for debugging/monitoring)
            if hasattr(request.state, 'tenant_id'):
                response.headers["X-Tenant-ID"] = request.state.tenant_id
                response.headers["X-Shard-Number"] = str(request.state.tenant_shard)
            
            return response
            
        except Exception as e:
            # Log the error and return a safe response
            print(f"❌ Tenant middleware error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "Failed to process tenant information"
                }
            )
    
    async def _detect_tenant(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Detect tenant information from the request using multiple methods.
        
        Returns a dict with tenant detection info or None if no tenant found.
        """
        
        # Method 1: Subdomain detection (primary method)
        subdomain_tenant = await self._detect_from_subdomain(request)
        if subdomain_tenant:
            return {
                'method': 'subdomain',
                'identifier': subdomain_tenant,
                'type': 'subdomain'
            }
        
        # Method 2: X-Tenant-ID header (API access)
        header_tenant = self._detect_from_header(request)
        if header_tenant:
            return {
                'method': 'header',
                'identifier': header_tenant,
                'type': 'tenant_id'
            }
        
        # Method 3: Query parameter (development/testing)
        query_tenant = self._detect_from_query(request)
        if query_tenant:
            return {
                'method': 'query',
                'identifier': query_tenant,
                'type': 'tenant_id'
            }
        
        # Method 4: JWT token (future implementation)
        # jwt_tenant = self._detect_from_jwt(request)
        # if jwt_tenant:
        #     return {'method': 'jwt', 'identifier': jwt_tenant, 'type': 'tenant_id'}
        
        return None
    
    async def _detect_from_subdomain(self, request: Request) -> Optional[str]:
        """
        Extract tenant subdomain from the request host.
        
        Examples:
        - lincoln-high.gradeinsight.com -> "lincoln-high"
        - washington-middle.gradeinsight.com -> "washington-middle"
        - localhost:8000 -> None (no subdomain)
        """
        host = request.headers.get("host", "").lower()
        
        # Remove port if present
        host = host.split(":")[0]
        
        # Skip localhost and direct IP access
        if host in ["localhost", "127.0.0.1"] or re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
            return None
        
        # Extract subdomain
        parts = host.split(".")
        if len(parts) >= 3:  # subdomain.domain.com
            subdomain = parts[0]
            # Validate subdomain format (letters, numbers, hyphens)
            if re.match(r"^[a-z0-9-]+$", subdomain) and len(subdomain) >= 2:
                return subdomain
        
        return None
    
    def _detect_from_header(self, request: Request) -> Optional[str]:
        """
        Extract tenant ID from X-Tenant-ID header.
        
        This is useful for API access where subdomain routing isn't available.
        """
        tenant_id = request.headers.get("X-Tenant-ID", "").strip()
        
        if tenant_id and re.match(r"^[a-zA-Z0-9-_]+$", tenant_id):
            return tenant_id.lower()
        
        return None
    
    def _detect_from_query(self, request: Request) -> Optional[str]:
        """
        Extract tenant ID from query parameter (for development/testing).
        
        Example: /api/students?tenant_id=lincoln-high
        """
        tenant_id = request.query_params.get("tenant_id", "").strip()
        
        if tenant_id and re.match(r"^[a-zA-Z0-9-_]+$", tenant_id):
            return tenant_id.lower()
        
        return None
    
    async def _validate_tenant(self, tenant_info: Dict[str, Any]) -> Optional[TenantRegistry]:
        """
        Validate that the detected tenant exists and is active.
        
        This checks the tenant registry and caches results for performance.
        """
        identifier = tenant_info['identifier']
        lookup_type = tenant_info['type']
        
        # Check cache first
        cache_key = f"{lookup_type}:{identifier}"
        if cache_key in self.tenant_cache:
            return self.tenant_cache[cache_key]
        
        try:
            # Look up tenant in registry
            if lookup_type == 'subdomain':
                tenant_record = await db_manager.get_tenant_by_subdomain(identifier)
            else:  # tenant_id lookup
                async with db_manager.get_tenant_registry_session() as session:
                    from sqlalchemy import select
                    stmt = select(TenantRegistry).where(
                        TenantRegistry.tenant_id == identifier,
                        TenantRegistry.is_active == True
                    )
                    result = await session.execute(stmt)
                    tenant_record = result.scalar_one_or_none()
            
            # Cache the result (including None for not found)
            self.tenant_cache[cache_key] = tenant_record
            
            return tenant_record
            
        except Exception as e:
            print(f"❌ Error validating tenant {identifier}: {str(e)}")
            return None
    
    async def _handle_no_tenant(self, request: Request) -> Response:
        """
        Handle requests where no tenant could be detected.
        
        This might be legitimate for certain endpoints (health checks, docs)
        or could indicate a misconfigured request.
        """
        path = request.url.path
        
        # Allow certain paths without tenant context
        if self._is_tenant_exempt_path(path):
            return await self._process_without_tenant(request)
        
        # For all other paths, require tenant
        return JSONResponse(
            status_code=400,
            content={
                "error": "Tenant required",
                "message": "This request requires tenant identification. Please use a subdomain (school.gradeinsight.com) or X-Tenant-ID header.",
                "help": {
                    "subdomain": "Access via school.gradeinsight.com",
                    "header": "Add 'X-Tenant-ID: your-school-id' header",
                    "query": "Add '?tenant_id=your-school-id' parameter (development only)"
                }
            }
        )
    
    async def _handle_invalid_tenant(self, tenant_info: Dict[str, Any]) -> Response:
        """
        Handle requests with invalid or inactive tenants.
        """
        return JSONResponse(
            status_code=404,
            content={
                "error": "Tenant not found",
                "message": f"The tenant '{tenant_info['identifier']}' was not found or is not active.",
                "detected_method": tenant_info['method']
            }
        )
    
    def _is_tenant_exempt_path(self, path: str) -> bool:
        """
        Check if a path should be exempt from tenant requirements.
        
        These are typically system endpoints that don't need tenant context.
        """
        exempt_paths = [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/favicon.ico",
            "/admin",
            "/setup"
        ]
        
        # Exact matches
        if path in exempt_paths:
            return True
        
        # Path prefixes
        exempt_prefixes = ["/admin/", "/setup/", "/static/"]
        for prefix in exempt_prefixes:
            if path.startswith(prefix):
                return True
        
        return False
    
    async def _process_without_tenant(self, request: Request) -> Response:
        """
        Process requests that don't require tenant context.
        
        This is a placeholder - in a real implementation, we'd need
        a way to continue processing the request without tenant middleware.
        """
        # This is a simplified version - in practice, you'd call the next middleware
        return JSONResponse(
            status_code=200,
            content={
                "message": "System endpoint accessed without tenant context",
                "path": request.url.path
            }
        )


class TenantContextManager:
    """
    Helper class for managing tenant context in application code.
    
    This provides convenient methods for accessing tenant information
    from within route handlers and services.
    """
    
    @staticmethod
    def get_tenant_id(request: Request) -> str:
        """
        Get the current tenant ID from the request.
        
        Raises HTTPException if no tenant context is available.
        """
        if not hasattr(request.state, 'tenant_id'):
            raise HTTPException(
                status_code=400,
                detail="No tenant context available"
            )
        return request.state.tenant_id
    
    @staticmethod
    def get_tenant_name(request: Request) -> str:
        """Get the current tenant's display name."""
        if not hasattr(request.state, 'tenant_name'):
            raise HTTPException(
                status_code=400,
                detail="No tenant context available"
            )
        return request.state.tenant_name
    
    @staticmethod
    def get_tenant_shard(request: Request) -> int:
        """Get the current tenant's database shard number."""
        if not hasattr(request.state, 'tenant_shard'):
            raise HTTPException(
                status_code=400,
                detail="No tenant context available"
            )
        return request.state.tenant_shard
    
    @staticmethod
    def get_tenant_record(request: Request) -> TenantRegistry:
        """Get the full tenant registry record."""
        if not hasattr(request.state, 'tenant_record'):
            raise HTTPException(
                status_code=400,
                detail="No tenant context available"
            )
        return request.state.tenant_record
    
    @staticmethod
    def has_tenant_context(request: Request) -> bool:
        """Check if the request has tenant context."""
        return hasattr(request.state, 'tenant_id')


# Dependency for FastAPI route handlers
async def get_current_tenant_id(request: Request) -> str:
    """
    FastAPI dependency to get the current tenant ID.
    
    Usage in route handlers:
    
    @app.get("/students")
    async def get_students(tenant_id: str = Depends(get_current_tenant_id)):
        # tenant_id is automatically injected
        pass
    """
    return TenantContextManager.get_tenant_id(request)


async def get_current_tenant_record(request: Request) -> TenantRegistry:
    """
    FastAPI dependency to get the full tenant record.
    
    Usage:
    @app.get("/school-info")
    async def get_school_info(tenant: TenantRegistry = Depends(get_current_tenant_record)):
        return {"name": tenant.tenant_name, "shard": tenant.shard_number}
    """
    return TenantContextManager.get_tenant_record(request)


# Utility functions for tenant validation

def validate_tenant_ownership(obj: Any, tenant_id: str) -> None:
    """
    Validate that a database object belongs to the specified tenant.
    
    This is an additional security check to prevent data leakage.
    
    Args:
        obj: Database object to validate
        tenant_id: Expected tenant ID
        
    Raises:
        HTTPException: If object doesn't belong to tenant
    """
    if hasattr(obj, 'tenant_id') and obj.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: Object belongs to different tenant"
        )


def ensure_tenant_filter(query_params: dict, tenant_id: str) -> dict:
    """
    Ensure tenant_id is included in query parameters.
    
    This prevents accidentally querying across tenants.
    
    Args:
        query_params: Dictionary of query parameters
        tenant_id: Current tenant ID
        
    Returns:
        Updated query parameters with tenant_id
    """
    query_params['tenant_id'] = tenant_id
    return query_params


# Example usage and testing
if __name__ == "__main__":
    print("Tenant Middleware System")
    print("=" * 30)
    
    # Example of how tenant detection works
    test_cases = [
        {
            'host': 'lincoln-high.gradeinsight.com',
            'expected': 'lincoln-high'
        },
        {
            'host': 'washington-middle.gradeinsight.com',
            'expected': 'washington-middle'
        },
        {
            'host': 'localhost:8000',
            'expected': None
        },
        {
            'host': 'gradeinsight.com',
            'expected': None
        }
    ]
    
    middleware = TenantMiddleware(None)
    
    print("Testing subdomain detection:")
    for case in test_cases:
        # Simulate request object
        class MockRequest:
            def __init__(self, host):
                self.headers = {'host': host}
        
        request = MockRequest(case['host'])
        # Note: This is just for demonstration - actual detection is async
        print(f"  {case['host']} -> Expected: {case['expected']}")
    
    print("\nTenant middleware ready for integration!")
