from secrets import token_hex

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
    guest_enabled: bool = False


@router.get("/session", response_model=SessionResponse)
async def get_session_status(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    subject = request.session.get("subject")
    if isinstance(subject, str) and subject:
        auth_mode = "guest" if subject.startswith("guest:") else "session"
        return SessionResponse(
            authenticated=True,
            subject=subject,
            auth_mode=auth_mode,
            guest_enabled=settings.allow_guest_access,
        )
    return SessionResponse(authenticated=False, guest_enabled=settings.allow_guest_access)


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
    return SessionResponse(
        authenticated=True,
        subject=settings.web_username,
        auth_mode="session",
        guest_enabled=settings.allow_guest_access,
    )


@router.post("/guest", response_model=SessionResponse)
async def login_as_guest(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    if not settings.allow_guest_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guest access is disabled")

    request.session.clear()
    subject = f"guest:{token_hex(8)}"
    request.session["subject"] = subject
    return SessionResponse(
        authenticated=True,
        subject=subject,
        auth_mode="guest",
        guest_enabled=True,
    )


@router.post("/logout", response_model=SessionResponse)
async def logout(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    request.session.clear()
    return SessionResponse(authenticated=False, guest_enabled=settings.allow_guest_access)
