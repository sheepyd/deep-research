import asyncio
import secrets
import time
from collections import defaultdict
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


def _client_key(request: Request) -> str:
    """Extract client identifier from request, preferring X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


class _LoginLimiter:
    """In-memory per-client login throttle.

    Keeps a short sliding window of failure timestamps. When the number of
    failures within window_seconds reaches max_attempts the client is
    locked out until the oldest failure in the window falls out of it.
    """

    _instance: "_LoginLimiter | None" = None

    def __init__(self, settings: Settings) -> None:
        self.max_attempts = max(1, settings.login_max_attempts)
        self.window_seconds = max(1, settings.login_window_seconds)
        self._failures: dict[str, list[float]] = defaultdict(list)

    @classmethod
    def instance(cls, settings: Settings) -> "_LoginLimiter":
        current = cls._instance
        if current is None or (
            current.max_attempts != max(1, settings.login_max_attempts)
            or current.window_seconds != max(1, settings.login_window_seconds)
        ):
            cls._instance = cls(settings)
        return cls._instance

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        samples = self._failures.get(key, [])
        self._failures[key] = [ts for ts in samples if ts > cutoff]
        if not self._failures[key]:
            self._failures.pop(key, None)

    def is_locked(self, key: str) -> bool:
        now = time.monotonic()
        self._prune(key, now)
        return len(self._failures.get(key, [])) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        self._prune(key, now)
        self._failures[key].append(now)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


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
    key = _client_key(request)
    limiter = _LoginLimiter.instance(settings)
    if limiter.is_locked(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
        )

    provided = payload.password.encode("utf-8")
    expected = settings.web_password.encode("utf-8")
    if not secrets.compare_digest(provided, expected):
        limiter.record_failure(key)
        await asyncio.sleep(settings.login_min_delay_seconds)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    limiter.reset(key)
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
