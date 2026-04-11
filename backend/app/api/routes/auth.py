from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings

router = APIRouter()


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class SessionResponse(BaseModel):
    authenticated: bool
    subject: str | None = None
    auth_mode: str | None = None


@router.get("/session", response_model=SessionResponse)
async def get_session_status(request: Request) -> SessionResponse:
    subject = request.session.get("subject")
    if isinstance(subject, str) and subject:
        return SessionResponse(authenticated=True, subject=subject, auth_mode="session")
    return SessionResponse(authenticated=False)


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    if payload.password != settings.web_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    request.session.clear()
    request.session["subject"] = settings.web_username
    return SessionResponse(authenticated=True, subject=settings.web_username, auth_mode="session")


@router.post("/logout", response_model=SessionResponse)
async def logout(request: Request) -> SessionResponse:
    request.session.clear()
    return SessionResponse(authenticated=False)
