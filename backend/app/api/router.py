from fastapi import APIRouter

from app.api.routes import auth, health, mcp, providers, research

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(providers.router, tags=["providers"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
api_router.include_router(mcp.router, tags=["mcp"])
