from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import close_engine
from app.research.service import ResearchService
from app.research.streaming import StreamManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.stream_manager = StreamManager()
    app.state.research_service = ResearchService(
        settings=settings,
        stream_manager=app.state.stream_manager,
    )
    yield
    await close_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime()
    app = FastAPI(
        title="Deep Research API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=settings.session_cookie_name,
        same_site="lax",
        https_only=settings.session_cookie_secure,
        max_age=settings.session_max_age_seconds,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
