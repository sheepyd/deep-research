import asyncio
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.research.providers import SearchDocument
from app.research.schemas import ClarifyRequest, ResearchTaskCreateRequest
from app.research.service import ResearchService
from app.research.streaming import StreamManager


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    async def ainvoke(self, _messages):
        return SimpleNamespace(content=self.response)


class FakeRepo:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.sources: list[SearchDocument] = []
        self.task = type("Task", (), {"current_step": None})()

    async def get_task(self, _task_id):
        return self.task

    async def update_task(self, task, **changes):
        for key, value in changes.items():
            setattr(task, key, value)
        return task

    async def append_event(self, *, task_id, event_type, payload, step=None):
        sequence = len(self.events) + 1
        event = {
            "task_id": task_id,
            "event_type": event_type,
            "payload": payload,
            "step": step,
            "sequence": sequence,
        }
        self.events.append(event)
        return SimpleNamespace(id=sequence, sequence=sequence)

    async def replace_sources(self, *, task_id, sources):
        self.sources = list(sources)


@pytest.mark.asyncio
async def test_chunk_text() -> None:
    chunks = ResearchService._chunk_text("a b c d e f", size=3)
    assert chunks


@pytest.mark.asyncio
async def test_clarify_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.research.service.create_llm",
        lambda _settings, _provider, _model: FakeLLM("Question one?\nQuestion two?"),
    )
    service = ResearchService(settings=Settings(api_bearer_token="token"), stream_manager=StreamManager())
    result = await service.clarify_questions(
        ClarifyRequest(
            query="test topic",
            provider="openai",
            thinking_model="gpt-5.4-mini",
            language="zh-CN",
        )
    )
    assert result == ["Question one?", "Question two?"]


@pytest.mark.asyncio
async def test_build_brief(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.research.service.create_llm",
        lambda _settings, _provider, _model: FakeLLM("brief content"),
    )
    service = ResearchService(settings=Settings(api_bearer_token="token"), stream_manager=StreamManager())
    payload = ResearchTaskCreateRequest(
        query="topic",
        questions=["q1", "q2"],
        answers=["a1", "a2"],
        provider="openai",
        thinking_model="gpt-5.4-mini",
        task_model="gpt-5.4-mini",
        search_provider="searxng",
        language="zh-CN",
        max_results=5,
    )
    state = {
        "task_id": "task-1",
        "query": payload.query,
        "questions": payload.questions,
        "answers": payload.answers,
        "provider": payload.provider,
        "thinking_model": payload.thinking_model,
        "language": payload.language,
    }

    result = await service._build_research_brief(FakeRepo(), state)
    assert result["brief"] == "brief content"


def test_format_clarify_pairs() -> None:
    text = ResearchService._format_clarify_pairs(["Question A"], ["Answer A"])
    assert "Question A" in text
    assert "Answer A" in text


@pytest.mark.asyncio
async def test_run_search_tasks_respects_concurrency_and_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    tracker = {"current": 0, "max_seen": 0}
    summary_calls = {"retry query": 0}

    class FakeSearchClient:
        async def search(self, query: str, _max_results: int, _language: str):
            tracker["current"] += 1
            tracker["max_seen"] = max(tracker["max_seen"], tracker["current"])
            await asyncio.sleep(0.02)
            tracker["current"] -= 1
            return [
                SearchDocument(
                    title=f"title-{query}",
                    url=f"https://example.com/{query}",
                    content=("content " + query + " ") * 200,
                    metadata={},
                )
            ]

    class RetryAwareLLM:
        async def ainvoke(self, messages):
            prompt = messages[0].content
            if "Search query: retry query" in prompt:
                summary_calls["retry query"] += 1
                if summary_calls["retry query"] == 1:
                    raise ValueError("context length exceeded")
            return SimpleNamespace(
                content='{"learning":"condensed learning","reasoning":"important evidence kept"}'
            )

    monkeypatch.setattr("app.research.service.create_search_client", lambda _settings, _provider: FakeSearchClient())
    monkeypatch.setattr("app.research.service.create_llm", lambda _settings, _provider, _model: RetryAwareLLM())

    service = ResearchService(
        settings=Settings(api_bearer_token="token", research_concurrency=2),
        stream_manager=StreamManager(),
    )
    repo = FakeRepo()
    state = {
        "task_id": "task-1",
        "provider": "openai",
        "task_model": "gpt-5.4-mini",
        "search_provider": "searxng",
        "language": "zh-CN",
        "max_results": 5,
        "search_tasks": [
            {"query": "first query", "research_goal": "goal-1"},
            {"query": "retry query", "research_goal": "goal-2"},
            {"query": "third query", "research_goal": "goal-3"},
        ],
    }

    result = await service._run_search_tasks(repo, state)

    assert tracker["max_seen"] == 2
    assert len(result["learnings"]) == 3
    assert len(repo.sources) == 3
    assert any(
        event["event_type"] == "progress"
        and event["payload"].get("attempt") == 2
        for event in repo.events
    )


@pytest.mark.asyncio
async def test_generate_final_report_retries_with_compression(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    class RetryAwareLLM:
        async def ainvoke(self, _messages):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ValueError("maximum context length exceeded")
            return SimpleNamespace(content="# Final Report")

    monkeypatch.setattr("app.research.service.create_llm", lambda _settings, _provider, _model: RetryAwareLLM())

    service = ResearchService(settings=Settings(api_bearer_token="token"), stream_manager=StreamManager())
    repo = FakeRepo()
    state = {
        "task_id": "task-1",
        "provider": "openai",
        "task_model": "gpt-5.4-mini",
        "language": "zh-CN",
        "report_plan": "# plan",
        "learnings": ["A" * 8000, "B" * 8000],
    }

    report, meta = await service._generate_final_report_with_retry(repo, state)

    assert report == "# Final Report"
    assert meta["attempt"] == 2
    assert meta["compressed_context"] is True
