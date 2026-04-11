from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, require_api_auth
from app.core.config import Settings, get_settings
from app.research.providers import get_provider_catalog

router = APIRouter()


@router.get("/providers")
async def list_providers(
    _auth: AuthContext = Depends(require_api_auth),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return get_provider_catalog(settings)
