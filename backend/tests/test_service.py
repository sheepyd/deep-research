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

    async def astream(self, _messages):
        yield SimpleNamespace(content=self.response)


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


class SerialOnlyRepo(FakeRepo):
    def __init__(self) -> None:
        super().__init__()
        self._active_calls = 0
        self.max_active_calls = 0

    async def _enter(self) -> None:
        self._active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self._active_calls)
        await asyncio.sleep(0.01)

    async def _leave(self) -> None:
        self._active_calls -= 1

    async def get_task(self, task_id):
        await self._enter()
        try:
            return await super().get_task(task_id)
        finally:
            await self._leave()

    async def update_task(self, task, **changes):
        await self._enter()
        try:
            return await super().update_task(task, **changes)
        finally:
            await self._leave()

    async def append_event(self, *, task_id, event_type, payload, step=None):
        await self._enter()
        try:
            return await super().append_event(task_id=task_id, event_type=event_type, payload=payload, step=step)
        finally:
            await self._leave()


class FakeDeleteRepo:
    def __init__(self, status: str) -> None:
        self.task = type("Task", (), {"id": "task-1", "status": status})()
        self.deleted_task = None

    async def get_task(self, _task_id):
        return self.task

    async def delete_task(self, task):
        self.deleted_task = task


class FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_chunk_text() -> None:
    chunks = ResearchService._chunk_text("a b c d e f", size=3)
    assert chunks


@pytest.mark.asyncio
async def test_clarify_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.research.service.create_llm",
        lambda *_args, **_kwargs: FakeLLM("Question one?\nQuestion two?"),
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
        lambda *_args, **_kwargs: FakeLLM("brief content"),
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

        async def astream(self, messages):
            result = await self.ainvoke(messages)
            yield result

    monkeypatch.setattr("app.research.service.create_search_client", lambda *_args, **_kwargs: FakeSearchClient())
    monkeypatch.setattr("app.research.service.create_llm", lambda *_args, **_kwargs: RetryAwareLLM())

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

        async def astream(self, messages):
            result = await self.ainvoke(messages)
            yield result

    monkeypatch.setattr("app.research.service.create_llm", lambda *_args, **_kwargs: RetryAwareLLM())

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


@pytest.mark.asyncio
async def test_delete_task_cancels_active_running_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FakeDeleteRepo(status="running")
    published: list[dict[str, object]] = []

    async def sleeper() -> None:
        await asyncio.sleep(10)

    service = ResearchService(settings=Settings(api_bearer_token="token"), stream_manager=StreamManager())
    worker = asyncio.create_task(sleeper())
    service._task_runs["task-1"] = worker

    async def fake_publish(task_id: str, payload: dict[str, object]) -> None:
        published.append({"task_id": task_id, "payload": payload})

    monkeypatch.setattr("app.research.service.AsyncSessionLocal", lambda: FakeSessionContext())
    monkeypatch.setattr("app.research.service.ResearchRepository", lambda _session: repo)
    monkeypatch.setattr(service.stream_manager, "publish", fake_publish)

    result = await service.delete_task("task-1")

    assert result.deleted is True
    assert worker.cancelled()
    assert repo.deleted_task is repo.task
    assert published == [
        {
            "task_id": "task-1",
            "payload": {"event": "done", "data": {"task_id": "task-1", "status": "deleted"}},
        }
    ]
    assert "task-1" not in service._task_runs


@pytest.mark.asyncio
async def test_delete_task_allows_stale_running_task_without_active_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeDeleteRepo(status="running")
    published: list[dict[str, object]] = []

    service = ResearchService(settings=Settings(api_bearer_token="token"), stream_manager=StreamManager())

    async def fake_publish(task_id: str, payload: dict[str, object]) -> None:
        published.append({"task_id": task_id, "payload": payload})

    monkeypatch.setattr("app.research.service.AsyncSessionLocal", lambda: FakeSessionContext())
    monkeypatch.setattr("app.research.service.ResearchRepository", lambda _session: repo)
    monkeypatch.setattr(service.stream_manager, "publish", fake_publish)

    result = await service.delete_task("task-1")

    assert result.deleted is True
    assert repo.deleted_task is repo.task
    assert published == [
        {
            "task_id": "task-1",
            "payload": {"event": "done", "data": {"task_id": "task-1", "status": "deleted"}},
        }
    ]


@pytest.mark.asyncio
async def test_summarize_search_results_returns_insufficient_evidence_without_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.research.service.create_llm",
        lambda *_args, **_kwargs: pytest.fail("LLM should not be called when there are no sources"),
    )

    service = ResearchService(settings=Settings(api_bearer_token="token"), stream_manager=StreamManager())
    repo = FakeRepo()

    payload, meta = await service._summarize_search_results_with_retry(
        repo=repo,
        task_id="task-1",
        provider="openai",
        model="gpt-5.4-mini",
        query="rag技术的发展情况",
        research_goal="总结发展脉络",
        docs=[],
        language="zh-CN",
    )

    assert payload["learning"] == "检索结果不足，当前不能基于证据得出可靠结论。"
    assert meta["compression_mode"] == "no-sources"


@pytest.mark.asyncio
async def test_generate_final_report_returns_insufficient_evidence_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.research.service.create_llm",
        lambda *_args, **_kwargs: pytest.fail("LLM should not be called when learnings are insufficient"),
    )

    service = ResearchService(settings=Settings(api_bearer_token="token"), stream_manager=StreamManager())
    repo = FakeRepo()
    state = {
        "task_id": "task-1",
        "query": "rag技术的发展情况",
        "provider": "openai",
        "task_model": "gpt-5.4-mini",
        "language": "zh-CN",
        "report_plan": "# plan",
        "learnings": ["检索结果不足，当前不能基于证据得出可靠结论。"],
    }

    report, meta = await service._generate_final_report_with_retry(repo, state)

    assert "当前报告未生成可信结论" in report
    assert meta["compression_mode"] == "insufficient-evidence"


@pytest.mark.asyncio
async def test_generate_search_queries_falls_back_when_model_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.research.service.create_llm",
        lambda *_args, **_kwargs: FakeLLM("[]"),
    )

    service = ResearchService(settings=Settings(api_bearer_token="token"), stream_manager=StreamManager())
    repo = FakeRepo()
    state = {
        "task_id": "task-1",
        "query": "RAG 技术的发展情况",
        "brief": "研究 RAG 技术的发展情况",
        "provider": "openai",
        "thinking_model": "gpt-5.4-mini",
        "language": "zh-CN",
        "report_plan": "# plan",
    }

    result = await service._generate_search_queries(repo, state)

    assert len(result["search_tasks"]) == 3
    assert any("fallback query generation" in str(event["payload"].get("text", "")) for event in repo.events)


def test_normalize_search_tasks_filters_invalid_entries() -> None:
    tasks = ResearchService._normalize_search_tasks(
        [
            {"query": "RAG 发展", "research_goal": "goal-1"},
            {"query": "  RAG 发展  ", "research_goal": "goal-2"},
            {"query": "", "research_goal": "goal-3"},
            {"foo": "bar"},
            "bad-item",
        ]
    )

    assert tasks == [{"query": "RAG 发展", "research_goal": "goal-1"}]


@pytest.mark.asyncio
async def test_emit_progress_serializes_repo_access_per_task() -> None:
    service = ResearchService(settings=Settings(api_bearer_token="token"), stream_manager=StreamManager())
    repo = SerialOnlyRepo()

    await asyncio.gather(
        service._emit_progress(repo, "task-1", "search-task", "start", name="q1", role="researcher"),
        service._emit_progress(repo, "task-1", "search-task", "start", name="q2", role="researcher"),
        service._emit_progress(repo, "task-1", "search-task", "end", name="q3", role="researcher"),
    )

    assert repo.max_active_calls == 1
