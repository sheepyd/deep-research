import pytest

from app.core.config import Settings
from app.research.providers import (
    DEFAULT_PROVIDER_CATALOG,
    SearxngSearchClient,
    TavilySearchClient,
    create_search_client,
    get_provider_catalog,
)


def test_provider_catalog_shape() -> None:
    assert "openai" in DEFAULT_PROVIDER_CATALOG["llm_providers"]
    assert "tavily" in DEFAULT_PROVIDER_CATALOG["search_providers"]


def test_provider_catalog_uses_env_model_list() -> None:
    settings = Settings(
        api_bearer_token="token",
        openai_model_list="gpt-5.4-mini,gpt-5.4",
        google_model_list="gemini-2.5-flash",
    )
    catalog = get_provider_catalog(settings)
    assert catalog["llm_providers"]["openai"]["models"] == ["gpt-5.4-mini", "gpt-5.4"]
    assert catalog["llm_providers"]["google"]["models"] == ["gemini-2.5-flash"]


def test_create_searxng_client() -> None:
    settings = Settings(api_bearer_token="token", searxng_base_url="http://searxng.local")
    client = create_search_client(settings, "searxng")
    assert isinstance(client, SearxngSearchClient)


def test_create_tavily_requires_key() -> None:
    settings = Settings(api_bearer_token="token", tavily_api_key="tavily-key")
    client = create_search_client(settings, "tavily")
    assert isinstance(client, TavilySearchClient)
