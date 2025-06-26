from fastapi import Request, HTTPException, APIRouter
from starlette.middleware.base import BaseHTTPMiddleware
import uuid

# Add this router
router = APIRouter(
    prefix="/tenant",
    tags=["tenant"]
)

@router.get("/info")
async def get_tenant_info(request: Request):
    """Get current tenant information"""
    tenant_id = getattr(request.state, 'tenant_id', None)
    return {"tenant_id": str(tenant_id) if tenant_id else None}

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Example: Get tenant_id from custom header "X-Tenant-ID"
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
        request.state.tenant_id = tenant_id

        # Continue processing request
        response = await call_next(request)
        return response

