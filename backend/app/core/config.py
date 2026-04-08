from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    api_bearer_token: str = "change-me"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    database_url: str = (
        "postgresql+asyncpg://deep_research:deep_research@localhost:5432/deep_research"
    )
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model_list: str = "gpt-5.4-mini,gpt-5.4,gpt-5"
    google_api_key: Optional[str] = None
    google_model_list: str = "gemini-2.5-flash,gemini-2.5-pro"
    anthropic_api_key: Optional[str] = None
    anthropic_model_list: str = "claude-3-5-sonnet-latest,claude-3-7-sonnet-latest"
    tavily_api_key: Optional[str] = None
    searxng_base_url: str = "http://localhost:8080"
    research_concurrency: int = 3
    sse_keepalive_seconds: int = 15
    mcp_ai_provider: Optional[str] = None
    mcp_thinking_model: Optional[str] = None
    mcp_task_model: Optional[str] = None
    mcp_search_provider: Optional[str] = None
    mcp_language: str = "zh-CN"
    mcp_max_results: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
