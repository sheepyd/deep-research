from collections.abc import AsyncIterator
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.research.service import ResearchService
from app.research.streaming import StreamManager

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session


def get_research_service(request: Request) -> ResearchService:
    return request.app.state.research_service


def get_stream_manager(request: Request) -> StreamManager:
    return request.app.state.stream_manager


def require_api_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.api_bearer_token and (
        credentials is None or credentials.credentials != settings.api_bearer_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )
