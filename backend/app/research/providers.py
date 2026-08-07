import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)

DEFAULT_PROVIDER_CATALOG = {
    "llm_providers": {
        "openai": {
            "label": "OpenAI",
            "models": ["gpt-5.4-mini", "gpt-5.4", "gpt-5"],
        },
        "google": {
            "label": "Google Gemini",
            "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
        },
        "anthropic": {
            "label": "Anthropic",
            "models": ["claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest"],
        },
    },
    "search_providers": {
        "tavily": {"label": "Tavily"},
        "searxng": {"label": "SearxNG"},
    },
}


def _parse_model_list(value: str, fallback: List[str]) -> List[str]:
    models = [item.strip() for item in value.split(",") if item.strip()]
    return models or fallback


def get_provider_catalog(settings: Settings) -> dict[str, object]:
    return {
        "llm_providers": {
            "openai": {
                "label": "OpenAI",
                "models": _parse_model_list(
                    settings.openai_model_list,
                    DEFAULT_PROVIDER_CATALOG["llm_providers"]["openai"]["models"],
                ),
            },
            "google": {
                "label": "Google Gemini",
                "models": _parse_model_list(
                    settings.google_model_list,
                    DEFAULT_PROVIDER_CATALOG["llm_providers"]["google"]["models"],
                ),
            },
            "anthropic": {
                "label": "Anthropic",
                "models": _parse_model_list(
                    settings.anthropic_model_list,
                    DEFAULT_PROVIDER_CATALOG["llm_providers"]["anthropic"]["models"],
                ),
            },
        },
        "search_providers": DEFAULT_PROVIDER_CATALOG["search_providers"],
    }


@dataclass
class SearchDocument:
    title: str
    url: str
    content: str
    metadata: dict[str, object]


class TavilySearchClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def search(self, query: str, max_results: int, language: str) -> list[SearchDocument]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                headers={"Content-Type": "application/json"},
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": max_results,
                    "topic": "general",
                    "include_raw_content": "markdown",
                },
            )
            response.raise_for_status()
            payload = response.json()
        documents: list[SearchDocument] = []
        for item in payload.get("results", []):
            content = item.get("raw_content") or item.get("content") or ""
            if not item.get("url") or not content:
                continue
            documents.append(
                SearchDocument(
                    title=item.get("title") or item["url"],
                    url=item["url"],
                    content=content,
                    metadata={"language": language, "score": item.get("score")},
                )
            )
        return documents


class SearxngSearchClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def search(self, query: str, max_results: int, language: str) -> list[SearchDocument]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{self.base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "language": language,
                },
            )
            response.raise_for_status()
            payload = response.json()
        documents: list[SearchDocument] = []
        for item in payload.get("results", [])[:max_results]:
            content = item.get("content") or ""
            if not item.get("url") or not content:
                continue
            documents.append(
                SearchDocument(
                    title=item.get("title") or item["url"],
                    url=item["url"],
                    content=content,
                    metadata={"engine": item.get("engine")},
                )
            )
        return documents


def create_llm(
    settings: Settings,
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> BaseChatModel:
    if not model or not model.strip():
        raise ValueError("Model name must not be empty")
    if provider == "openai":
        return ChatOpenAI(
            model=model.strip(),
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or settings.openai_base_url,
            temperature=0,
        )
    if provider == "google":
        return ChatGoogleGenerativeAI(
            model=model.strip(),
            google_api_key=api_key or settings.google_api_key,
            temperature=0,
        )
    if provider == "anthropic":
        return ChatAnthropic(
            model=model.strip(),
            api_key=api_key or settings.anthropic_api_key,
            temperature=0,
        )
    raise ValueError(f"Unsupported provider: {provider}")


def create_search_client(
    settings: Settings,
    provider: str,
    api_key: str | None = None,
    base_url: str | None = None,
):
    if provider == "tavily":
        key = api_key or settings.tavily_api_key
        if not key:
            raise ValueError("Tavily API key is required")
        return TavilySearchClient(key)
    if provider == "searxng":
        return SearxngSearchClient(base_url or settings.searxng_base_url)
    raise ValueError(f"Unsupported search provider: {provider}")


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _FENCE_RE.search(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _extract_first_json_object(text: str) -> Optional[str]:
    """Best-effort extraction of the first balanced {...} or [...] JSON block.

    Models frequently wrap JSON in prose (``Here is the answer: {...}``).
    We scan for the first ``{`` or ``[`` and mirror braces/brackets until the
    scope closes, accounting for string literals. Returns None if no valid block
    is found.
    """
    open_ch = ""
    close_ch = ""
    start = -1
    for index, char in enumerate(text):
        if char in "{[":
            start = index
            open_ch = char
            close_ch = "}" if char == "{" else "]"
            break
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    end = -1
    for offset, char in enumerate(text[start:]):
        if escape:
            escape = False
            continue
        if char == "\\" and in_string:
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == open_ch:
            depth += 1
        elif char == close_ch:
            depth -= 1
            if depth == 0:
                end = start + offset
                break
    if end == -1:
        return None
    return text[start: end + 1]


def parse_json_response(content: str) -> object:
    text = _strip_code_fence(content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        extracted = _extract_first_json_object(text)
        if extracted is not None:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                pass
        logger.debug("Failed to parse JSON response: %s", text[:200])
        raise


def parse_json_list_or_none(content: str) -> Optional[list]:
    """Parse content as a JSON list, tolerating prose wrapping and fences.

    Returns None when the content cannot be parsed as a JSON list. Used by
    search query generation so that invalid model output can transparently fall
    back to the supervisor's fallback query plan.
    """
    try:
        parsed = parse_json_response(content)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None
