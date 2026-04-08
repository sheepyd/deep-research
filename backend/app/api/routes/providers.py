from fastapi import APIRouter
from fastapi import Depends

from app.core.config import Settings, get_settings
from app.research.providers import get_provider_catalog

router = APIRouter()


@router.get("/providers")
async def list_providers(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return get_provider_catalog(settings)
