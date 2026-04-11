from dataclasses import dataclass
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


@dataclass
class AuthContext:
    subject: str
    auth_mode: str


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session


def get_research_service(request: Request) -> ResearchService:
    return request.app.state.research_service


def get_stream_manager(request: Request) -> StreamManager:
    return request.app.state.stream_manager


def require_api_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    session_subject = request.session.get("subject")
    if isinstance(session_subject, str) and session_subject:
        return AuthContext(subject=session_subject, auth_mode="session")

    if settings.allow_bearer_auth and settings.api_bearer_token:
        if credentials is not None and credentials.credentials == settings.api_bearer_token:
            return AuthContext(subject=settings.web_username, auth_mode="bearer")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
