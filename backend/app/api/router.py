from fastapi import APIRouter, Depends

from app.api.deps import require_api_token
from app.api.routes import health, mcp, providers, research

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
protected_router = APIRouter(dependencies=[Depends(require_api_token)])
protected_router.include_router(providers.router, tags=["providers"])
protected_router.include_router(research.router, prefix="/research", tags=["research"])
protected_router.include_router(mcp.router, tags=["mcp"])
api_router.include_router(protected_router)
