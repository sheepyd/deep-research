import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, Optional

from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.sse import format_sse
from app.db.session import AsyncSessionLocal
from app.research.prompts import (
    BUILD_BRIEF_PROMPT,
    CLARIFY_PROMPT,
    FINAL_REPORT_PROMPT,
    REPORT_PLAN_PROMPT,
    SEARCH_QUERY_PROMPT,
    SEARCH_SUMMARY_PROMPT,
)
from app.research.providers import (
    SearchDocument,
    create_llm,
    create_search_client,
    parse_json_response,
)
from app.research.repository import ResearchRepository
from app.research.schemas import (
    ClarifyRequest,
    ResearchTaskCreateRequest,
    ResearchTaskDeleteResponse,
    ResearchTaskDetail,
    ResearchTaskSummary,
)
from app.research.streaming import StreamManager

logger = logging.getLogger(__name__)


class WorkflowState(dict):
    task_id: str
    parent_task_id: Optional[str]
    research_iteration: int
    query: str
    questions: list[str]
    answers: list[str]
    follow_up_request: str
    language: str
    provider: str
    thinking_model: str
    task_model: str
    search_provider: str
    max_results: int
    brief: str
    previous_report: str
    previous_plan: str
    report_plan: str
    search_tasks: list[dict[str, str]]
    learnings: list[str]
    sources: list[SearchDocument]
    final_report: str


class ResearchService:
    def __init__(self, settings: Settings, stream_manager: StreamManager) -> None:
        self.settings = settings
        self.stream_manager = stream_manager
        self._task_locks: dict[str, asyncio.Lock] = {}
        self._task_runs: dict[str, asyncio.Task[None]] = {}

    async def clarify_questions(self, payload: ClarifyRequest) -> list[str]:
        llm = create_llm(self.settings, payload.provider, payload.thinking_model)
        messages = [
            HumanMessage(
                content=CLARIFY_PROMPT.format(query=payload.query, language=payload.language)
            )
        ]
        raw = ""
        async for chunk in llm.astream(messages):
            if chunk.content:
                raw += chunk.content
        lines = [line.strip("- ").strip() for line in str(raw).splitlines() if line.strip()]
        return lines[:5]

    async def create_task(self, payload: ResearchTaskCreateRequest, *, owner_id: str):
        if not payload.questions:
            raise ValueError("Clarify questions are required before starting research")
        async with AsyncSessionLocal() as session:
            repo = ResearchRepository(session)
            active_tasks = await repo.count_active_tasks_for_owner(owner_id)
            if active_tasks >= self.settings.max_active_tasks_per_owner:
                raise HTTPException(status_code=429, detail="Too many active tasks")
            task = await repo.create_task(
                owner_id=owner_id,
                query=payload.query,
                clarify_questions=payload.questions,
                clarify_answers=payload.answers,
                clarified_brief="",
                parent_task_id=payload.parent_task_id,
                research_iteration=payload.research_iteration,
                follow_up_request=payload.follow_up_request,
                provider=payload.provider,
                thinking_model=payload.thinking_model,
                task_model=payload.task_model,
                search_provider=payload.search_provider,
                language=payload.language,
                max_results=payload.max_results,
            )
        background_task = asyncio.create_task(self.run_task(task_id=str(task.id), payload=payload))
        self._task_runs[str(task.id)] = background_task
        return task

    async def create_follow_up_task(
        self,
        *,
        parent_task_id: str,
        follow_up_request: str,
        max_results: Optional[int] = None,
        owner_id: str,
    ):
        async with AsyncSessionLocal() as session:
            repo = ResearchRepository(session)
            parent_task = await repo.get_task(parent_task_id, owner_id=owner_id)
            if parent_task is None:
                raise HTTPException(status_code=404, detail="Parent task not found")
            if parent_task.status != "completed":
                raise HTTPException(status_code=409, detail="Parent task must be completed before re-research")
            payload = ResearchTaskCreateRequest(
                query=parent_task.query,
                questions=parent_task.clarify_questions,
                answers=parent_task.clarify_answers,
                parent_task_id=str(parent_task.id),
                research_iteration=(parent_task.research_iteration or 1) + 1,
                follow_up_request=follow_up_request,
                provider=parent_task.provider,
                thinking_model=parent_task.thinking_model,
                task_model=parent_task.task_model,
                search_provider=parent_task.search_provider,
                language=parent_task.language,
                max_results=max_results or parent_task.max_results,
            )
        return await self.create_task(payload, owner_id=owner_id)

    async def run_task_inline(self, payload: ResearchTaskCreateRequest, *, owner_id: str) -> ResearchTaskDetail:
        if not payload.questions:
            raise ValueError("Clarify questions are required before starting research")
        async with AsyncSessionLocal() as session:
            repo = ResearchRepository(session)
            active_tasks = await repo.count_active_tasks_for_owner(owner_id)
            if active_tasks >= self.settings.max_active_tasks_per_owner:
                raise HTTPException(status_code=429, detail="Too many active tasks")
            task = await repo.create_task(
                owner_id=owner_id,
                query=payload.query,
                clarify_questions=payload.questions,
                clarify_answers=payload.answers,
                clarified_brief="",
                parent_task_id=payload.parent_task_id,
                research_iteration=payload.research_iteration,
                follow_up_request=payload.follow_up_request,
                provider=payload.provider,
                thinking_model=payload.thinking_model,
                task_model=payload.task_model,
                search_provider=payload.search_provider,
                language=payload.language,
                max_results=payload.max_results,
            )
        await self.run_task(task_id=str(task.id), payload=payload)
        async with AsyncSessionLocal() as session:
            detail = await self.get_task_detail(session, str(task.id), owner_id=owner_id)
        if detail is None:
            raise HTTPException(status_code=500, detail="Task detail unavailable after inline execution")
        return detail

    async def run_follow_up_inline(
        self,
        *,
        parent_task_id: str,
        follow_up_request: str,
        max_results: Optional[int] = None,
        owner_id: str,
    ) -> ResearchTaskDetail:
        async with AsyncSessionLocal() as session:
            repo = ResearchRepository(session)
            parent_task = await repo.get_task(parent_task_id, owner_id=owner_id)
            if parent_task is None:
                raise HTTPException(status_code=404, detail="Parent task not found")
            if parent_task.status != "completed":
                raise HTTPException(status_code=409, detail="Parent task must be completed before re-research")
            payload = ResearchTaskCreateRequest(
                query=parent_task.query,
                questions=parent_task.clarify_questions,
                answers=parent_task.clarify_answers,
                parent_task_id=str(parent_task.id),
                research_iteration=(parent_task.research_iteration or 1) + 1,
                follow_up_request=follow_up_request,
                provider=parent_task.provider,
                thinking_model=parent_task.thinking_model,
                task_model=parent_task.task_model,
                search_provider=parent_task.search_provider,
                language=parent_task.language,
                max_results=max_results or parent_task.max_results,
            )
        return await self.run_task_inline(payload, owner_id=owner_id)

    async def get_task_detail(
        self,
        session: AsyncSession,
        task_id: str,
        *,
        owner_id: str,
    ) -> Optional[ResearchTaskDetail]:
        repo = ResearchRepository(session)
        task = await repo.get_task(task_id, owner_id=owner_id)
        if task is None:
            return None
        events = await repo.list_events(task_id)
        sources = await repo.list_sources(task_id)
        return ResearchTaskDetail(
            id=str(task.id),
            parent_task_id=str(task.parent_task_id) if task.parent_task_id else None,
            research_iteration=task.research_iteration,
            status=task.status,
            query=task.query,
            clarify_questions=task.clarify_questions,
            clarify_answers=task.clarify_answers,
            clarified_brief=task.clarified_brief,
            follow_up_request=task.follow_up_request,
            provider=task.provider,
            thinking_model=task.thinking_model,
            task_model=task.task_model,
            search_provider=task.search_provider,
            language=task.language,
            max_results=task.max_results,
            current_step=task.current_step,
            report_plan=task.report_plan,
            final_report=task.final_report,
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.completed_at,
            sources=sources,
            events=events,
        )

    async def list_task_summaries(
        self,
        session: AsyncSession,
        *,
        owner_id: str,
        limit: int = 20,
    ) -> list[ResearchTaskSummary]:
        repo = ResearchRepository(session)
        tasks = await repo.list_tasks_for_owner(owner_id=owner_id, limit=limit)
        return [
            ResearchTaskSummary(
                id=str(task.id),
                parent_task_id=str(task.parent_task_id) if task.parent_task_id else None,
                research_iteration=task.research_iteration,
                status=task.status,
                query=task.query,
                follow_up_request=task.follow_up_request,
                provider=task.provider,
                thinking_model=task.thinking_model,
                task_model=task.task_model,
                search_provider=task.search_provider,
                language=task.language,
                current_step=task.current_step,
                created_at=task.created_at,
                updated_at=task.updated_at,
                completed_at=task.completed_at,
            )
            for task in tasks
        ]

    async def delete_task(self, task_id: str, *, owner_id: str) -> ResearchTaskDeleteResponse:
        async with AsyncSessionLocal() as session:
            repo = ResearchRepository(session)
            task = await repo.get_task(task_id, owner_id=owner_id)
            if task is None:
                raise HTTPException(status_code=404, detail="Task not found")
            active_run = self._task_runs.get(task_id)
            if active_run is not None and not active_run.done():
                active_run.cancel()
                await asyncio.gather(active_run, return_exceptions=True)
            if task.status in {"queued", "running"}:
                await self.stream_manager.publish(
                    task_id,
                    {
                        "event": "done",
                        "data": {"task_id": task_id, "status": "deleted"},
                    },
                )
            await repo.delete_task(task)
        self._task_locks.pop(task_id, None)
        self._task_runs.pop(task_id, None)
        return ResearchTaskDeleteResponse(deleted=True)

    async def stream_task_events(
        self,
        *,
        session: AsyncSession,
        stream_manager: StreamManager,
        task_id: str,
        owner_id: str,
    ) -> AsyncIterator[bytes]:
        repo = ResearchRepository(session)
        task = await repo.get_task(task_id, owner_id=owner_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        yield format_sse("infor", {"name": "deep-research", "version": "0.1.0", "task_id": task_id})
        for event in await repo.list_events(task_id):
            yield format_sse(event.event_type, event.payload_json)
        if task.status in {"completed", "failed"}:
            return
        queue = await stream_manager.subscribe(task_id)
        try:
            while True:
                payload = await queue.get()
                yield format_sse(payload["event"], payload["data"])
                if payload["event"] == "done":
                    break
        finally:
            stream_manager.unsubscribe(task_id, queue)

    async def run_task(self, *, task_id: str, payload: ResearchTaskCreateRequest) -> None:
        self._task_lock(task_id)
        async with AsyncSessionLocal() as session:
            repo = ResearchRepository(session)
            task = await repo.get_task(task_id)
            if task is None:
                return
            await repo.update_task(task, status="running", current_step="clarify-questions")
            graph = self._build_graph(repo)
            state: dict[str, Any] = {
                "task_id": task_id,
                "parent_task_id": payload.parent_task_id,
                "research_iteration": payload.research_iteration,
                "query": payload.query,
                "questions": payload.questions,
                "answers": payload.answers,
                "follow_up_request": payload.follow_up_request or "",
                "language": payload.language,
                "provider": payload.provider,
                "thinking_model": payload.thinking_model,
                "task_model": payload.task_model,
                "search_provider": payload.search_provider,
                "max_results": payload.max_results,
                "brief": "",
                "previous_report": "",
                "previous_plan": "",
                "report_plan": "",
                "search_tasks": [],
                "learnings": [],
                "sources": [],
                "final_report": "",
            }
            try:
                if payload.parent_task_id:
                    parent = await repo.get_task(payload.parent_task_id)
                    if parent is not None:
                        state["previous_report"] = parent.final_report or ""
                        state["previous_plan"] = parent.report_plan or ""
                        await self._emit_reasoning(
                            repo,
                            task_id,
                            (
                                f"Supervisor started re-research round {payload.research_iteration} "
                                f"from parent task {payload.parent_task_id}."
                            ),
                            role="supervisor",
                        )
                result = await graph.ainvoke(state)
                await repo.update_task(
                    task,
                    status="completed",
                    current_step="completed",
                    report_plan=result["report_plan"],
                    final_report=result["final_report"],
                    error_message=None,
                )
                await self._emit_event(
                    repo=repo,
                    task_id=task_id,
                    event="done",
                    data={"task_id": task_id, "status": "completed"},
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Research task %s failed", task_id)
                await repo.update_task(
                    task,
                    status="failed",
                    current_step="failed",
                    error_message="Research task failed. Check server logs for details.",
                )
                await self._emit_event(
                    repo=repo,
                    task_id=task_id,
                    event="error",
                    data={"task_id": task_id, "message": "Research task failed. Check server logs."},
                )
                await self._emit_event(
                    repo=repo,
                    task_id=task_id,
                    event="done",
                    data={"task_id": task_id, "status": "failed"},
                )
            finally:
                self._task_locks.pop(task_id, None)
                self._task_runs.pop(task_id, None)

    def _build_graph(self, repo: ResearchRepository):
        graph = StateGraph(dict)

        async def clarify_questions_node(state: dict[str, Any]) -> dict[str, Any]:
            return await self._clarify_questions_stage(repo, state)

        async def build_research_brief_node(state: dict[str, Any]) -> dict[str, Any]:
            return await self._build_research_brief(repo, state)

        async def write_report_plan_node(state: dict[str, Any]) -> dict[str, Any]:
            return await self._write_report_plan(repo, state)

        async def generate_search_queries_node(state: dict[str, Any]) -> dict[str, Any]:
            return await self._generate_search_queries(repo, state)

        async def run_search_tasks_node(state: dict[str, Any]) -> dict[str, Any]:
            return await self._run_search_tasks(repo, state)

        async def synthesize_final_report_node(state: dict[str, Any]) -> dict[str, Any]:
            return await self._synthesize_final_report(repo, state)

        graph.add_node("clarify_questions", clarify_questions_node)
        graph.add_node("build_research_brief", build_research_brief_node)
        graph.add_node("write_report_plan", write_report_plan_node)
        graph.add_node("generate_search_queries", generate_search_queries_node)
        graph.add_node("run_search_tasks", run_search_tasks_node)
        graph.add_node("synthesize_final_report", synthesize_final_report_node)
        graph.set_entry_point("clarify_questions")
        graph.add_edge("clarify_questions", "build_research_brief")
        graph.add_edge("build_research_brief", "write_report_plan")
        graph.add_edge("write_report_plan", "generate_search_queries")
        graph.add_edge("generate_search_queries", "run_search_tasks")
        graph.add_edge("run_search_tasks", "synthesize_final_report")
        graph.add_edge("synthesize_final_report", END)
        return graph.compile()

    async def _clarify_questions_stage(
        self,
        repo: ResearchRepository,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        await self._emit_progress(
            repo,
            state["task_id"],
            "clarify-questions",
            "start",
            role="supervisor",
        )
        questions = [question.strip() for question in state["questions"] if question.strip()]
        if not questions:
            raise ValueError("Clarify questions are required before starting research")
        answers = list(state["answers"])
        if len(answers) < len(questions):
            answers.extend([""] * (len(questions) - len(answers)))
        await self._emit_reasoning(
            repo,
            state["task_id"],
            f"Captured {len(questions)} clarification questions before entering the research workflow.",
            role="supervisor",
        )
        await self._emit_progress(
            repo,
            state["task_id"],
            "clarify-questions",
            "end",
            {
                "questions": questions,
                "answers": answers,
            },
            role="supervisor",
        )
        return {**state, "questions": questions, "answers": answers}

    async def _build_research_brief(self, repo: ResearchRepository, state: dict[str, Any]) -> dict[str, Any]:
        llm = create_llm(
            self.settings,
            state["provider"],
            state["thinking_model"],
        )
        answers = self._format_clarify_pairs(state["questions"], state["answers"])
        response = await llm.ainvoke(
            [
                HumanMessage(
                    content=BUILD_BRIEF_PROMPT.format(
                        query=state["query"],
                        answers=answers,
                        previous_plan=state.get("previous_plan") or "(No previous plan)",
                        previous_report=state.get("previous_report") or "(No previous report)",
                        follow_up_request=state.get("follow_up_request") or "(No follow-up request)",
                        language=state["language"],
                    )
                )
            ]
        )
        brief = str(getattr(response, "content", "")).strip()
        task = await repo.get_task(state["task_id"])
        if task is not None:
            await repo.update_task(task, clarified_brief=brief)
        await self._emit_reasoning(
            repo,
            state["task_id"],
            "Supervisor condensed the topic and clarify answers into a research brief.",
            role="supervisor",
        )
        return {**state, "brief": brief}

    async def _write_report_plan(self, repo: ResearchRepository, state: dict[str, Any]) -> dict[str, Any]:
        await self._emit_progress(
            repo,
            state["task_id"],
            "report-plan",
            "start",
            role="supervisor",
        )
        llm = create_llm(
            self.settings,
            state["provider"],
            state["thinking_model"],
        )
        response = await llm.ainvoke(
            [HumanMessage(content=REPORT_PLAN_PROMPT.format(brief=state["brief"], language=state["language"]))]
        )
        report_plan = str(getattr(response, "content", "")).strip()
        await self._emit_message(repo, state["task_id"], report_plan)
        await self._emit_reasoning(
            repo,
            state["task_id"],
            "Supervisor produced the report plan and output structure for downstream research agents.",
            role="supervisor",
        )
        await self._emit_progress(
            repo,
            state["task_id"],
            "report-plan",
            "end",
            {"report_plan": report_plan},
            role="supervisor",
        )
        return {**state, "report_plan": report_plan}

    async def _generate_search_queries(
        self,
        repo: ResearchRepository,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        await self._emit_progress(
            repo,
            state["task_id"],
            "serp-query",
            "start",
            role="supervisor",
        )
        llm = create_llm(self.settings, state["provider"], state["thinking_model"])
        messages = [
            HumanMessage(
                content=SEARCH_QUERY_PROMPT.format(
                    plan=state["report_plan"],
                    language=state["language"],
                )
            )
        ]
        raw = ""
        async for chunk in llm.astream(messages):
            if chunk.content:
                raw += chunk.content
        search_tasks = parse_json_response(str(raw))
        if not isinstance(search_tasks, list):
            raise ValueError("Search task generation returned invalid payload")
        search_tasks = self._normalize_search_tasks(search_tasks)
        if not search_tasks:
            search_tasks = self._fallback_search_tasks(
                query=state["query"],
                brief=state["brief"],
                language=state["language"],
            )
            await self._emit_reasoning(
                repo,
                state["task_id"],
                "Supervisor received no usable search tasks from the model and switched to fallback query generation.",
                role="supervisor",
            )
        await self._emit_reasoning(
            repo,
            state["task_id"],
            f"Supervisor decomposed the plan into {len(search_tasks)} researcher search tasks.",
            role="supervisor",
        )
        await self._emit_progress(
            repo,
            state["task_id"],
            "serp-query",
            "end",
            {"tasks": search_tasks},
            role="supervisor",
        )
        return {**state, "search_tasks": search_tasks}

    async def _run_search_tasks(self, repo: ResearchRepository, state: dict[str, Any]) -> dict[str, Any]:
        search_client = create_search_client(self.settings, state["search_provider"])
        concurrency = max(1, int(self.settings.research_concurrency or 1))
        tasks_to_run = list(state["search_tasks"])
        await self._emit_reasoning(
            repo,
            state["task_id"],
            f"Supervisor dispatched {len(tasks_to_run)} researcher tasks with concurrency limit {concurrency}.",
            role="supervisor",
        )

        semaphore = asyncio.Semaphore(concurrency)

        async def run_search_task(task_spec: dict[str, str]) -> tuple[list[SearchDocument], str]:
            async with semaphore:
                return await self._execute_researcher_task(
                    repo=repo,
                    state=state,
                    search_client=search_client,
                    task_spec=task_spec,
                )

        results = await asyncio.gather(*(run_search_task(task) for task in tasks_to_run))
        all_sources: list[SearchDocument] = []
        learnings: list[str] = []
        for docs, learning in results:
            if learning:
                learnings.append(learning)
            all_sources.extend(docs)
        await repo.replace_sources(task_id=state["task_id"], sources=all_sources)
        return {**state, "learnings": learnings, "sources": all_sources}

    async def _synthesize_final_report(
        self,
        repo: ResearchRepository,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        await self._emit_progress(
            repo,
            state["task_id"],
            "final-report",
            "start",
            role="supervisor",
        )
        final_report, retry_meta = await self._generate_final_report_with_retry(repo, state)
        await self._stream_report_chunks(repo, state["task_id"], final_report)
        await self._emit_progress(
            repo,
            state["task_id"],
            "final-report",
            "end",
            {
                "final_report_length": len(final_report),
                "compression_mode": retry_meta["compression_mode"],
                "learning_count": retry_meta["learning_count"],
            },
            role="supervisor",
            attempt=retry_meta["attempt"],
            compressed_context=retry_meta["compressed_context"],
        )
        return {**state, "final_report": final_report}

    async def _execute_researcher_task(
        self,
        *,
        repo: ResearchRepository,
        state: dict[str, Any],
        search_client: Any,
        task_spec: dict[str, str],
    ) -> tuple[list[SearchDocument], str]:
        query = str(task_spec.get("query", "")).strip()
        research_goal = str(task_spec.get("research_goal", "")).strip()
        await self._emit_progress(
            repo,
            state["task_id"],
            "search-task",
            "start",
            name=query,
            role="researcher",
        )
        docs = await search_client.search(query, state["max_results"], state["language"])
        payload, retry_meta = await self._summarize_search_results_with_retry(
            repo=repo,
            task_id=state["task_id"],
            provider=state["provider"],
            model=state["task_model"],
            query=query,
            research_goal=research_goal,
            docs=docs,
            language=state["language"],
        )
        learning = str(payload.get("learning", "")).strip()
        reasoning = str(payload.get("reasoning", "")).strip()
        if reasoning:
            await self._emit_reasoning(
                repo,
                state["task_id"],
                f"[{query}] {reasoning}",
                role="researcher",
            )
        await self._emit_progress(
            repo,
            state["task_id"],
            "search-task",
            "end",
            {
                "query": query,
                "sources_count": len(docs),
                "learning": learning,
                "compression_mode": retry_meta["compression_mode"],
                "source_count_used": retry_meta["source_count_used"],
                "source_char_budget": retry_meta["source_char_budget"],
            },
            name=query,
            role="researcher",
            attempt=retry_meta["attempt"],
            compressed_context=retry_meta["compressed_context"],
        )
        return docs, learning

    async def _summarize_search_results_with_retry(
        self,
        *,
        repo: ResearchRepository,
        task_id: str,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        query: str,
        research_goal: str,
        docs: list[SearchDocument],
        language: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not docs:
            await self._emit_reasoning(
                repo,
                task_id,
                f"Researcher could not summarize '{query}' because the search provider returned no usable sources.",
                role="researcher",
            )
            return self._insufficient_search_summary(language), {
                "attempt": 1,
                "compression_mode": "no-sources",
                "compressed_context": False,
                "source_count_used": 0,
                "source_char_budget": 0,
            }

        retry_plans = self._build_search_retry_plans(len(docs))
        last_error: Optional[Exception] = None
        for attempt, plan in enumerate(retry_plans, start=1):
            sources_text, source_count_used = self._render_search_sources(
                docs=docs,
                max_docs=plan["max_docs"],
                per_doc_chars=plan["per_doc_chars"],
                total_chars=plan["total_chars"],
            )
            if source_count_used == 0:
                await self._emit_reasoning(
                    repo,
                    task_id,
                    f"Researcher could not summarize '{query}' because source snippets were empty after compression.",
                    role="researcher",
                )
                return self._insufficient_search_summary(language), {
                    "attempt": attempt,
                    "compression_mode": plan["label"],
                    "compressed_context": attempt > 1,
                    "source_count_used": 0,
                    "source_char_budget": plan["total_chars"],
                }
            try:
                llm = create_llm(self.settings, provider, model, api_key, base_url)
                messages = [
                    HumanMessage(
                        content=SEARCH_SUMMARY_PROMPT.format(
                            query=query,
                            research_goal=research_goal,
                            sources=sources_text,
                            language=language,
                        )
                    )
                ]
                raw = ""
                async for chunk in llm.astream(messages):
                    if chunk.content:
                        raw += chunk.content
                payload = parse_json_response(str(raw))
                if not isinstance(payload, dict):
                    raise ValueError("Search summary returned invalid payload")
                if attempt > 1:
                    await self._emit_reasoning(
                        repo,
                        task_id,
                        f"Researcher recovered on retry {attempt} for '{query}' using {plan['label']} context compression.",
                        role="researcher",
                    )
                return payload, {
                    "attempt": attempt,
                    "compression_mode": plan["label"],
                    "compressed_context": attempt > 1,
                    "source_count_used": source_count_used,
                    "source_char_budget": plan["total_chars"],
                }
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == len(retry_plans):
                    break
                await self._emit_reasoning(
                    repo,
                    task_id,
                    (
                        f"Researcher retry {attempt} for '{query}' failed "
                        f"({self._compact_error(exc)}). Retrying with tighter context compression."
                    ),
                    role="researcher",
                )
        assert last_error is not None
        raise ValueError(
            f"Search summary failed for '{query}' after {len(retry_plans)} attempts: {self._compact_error(last_error)}"
        ) from last_error

    async def _generate_final_report_with_retry(
        self,
        repo: ResearchRepository,
        state: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        if not self._has_actionable_learnings(state["learnings"]):
            await self._emit_reasoning(
                repo,
                state["task_id"],
                "Supervisor skipped final synthesis because the collected learnings were not evidence-backed.",
                role="supervisor",
            )
            return self._build_insufficient_evidence_report(state["query"], state["language"]), {
                "attempt": 1,
                "compression_mode": "insufficient-evidence",
                "compressed_context": False,
                "learning_count": 0,
            }

        retry_plans = self._build_final_report_retry_plans(len(state["learnings"]))
        last_error: Optional[Exception] = None
        for attempt, plan in enumerate(retry_plans, start=1):
            learnings_text, learning_count = self._render_learnings(
                state["learnings"],
                max_items=plan["max_items"],
                total_chars=plan["total_chars"],
            )
            try:
                llm = create_llm(self.settings, state["provider"], state["task_model"])
                messages = [
                    HumanMessage(
                        content=FINAL_REPORT_PROMPT.format(
                            plan=state["report_plan"],
                            learnings=learnings_text,
                            language=state["language"],
                        )
                    )
                ]
                raw = ""
                async for chunk in llm.astream(messages):
                    if chunk.content:
                        raw += chunk.content
                final_report = str(raw).strip()
                if attempt > 1:
                    await self._emit_reasoning(
                        repo,
                        state["task_id"],
                        f"Supervisor recovered final report generation on retry {attempt} with {plan['label']} learnings compression.",
                        role="supervisor",
                    )
                return final_report, {
                    "attempt": attempt,
                    "compression_mode": plan["label"],
                    "compressed_context": attempt > 1,
                    "learning_count": learning_count,
                }
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == len(retry_plans):
                    break
                await self._emit_reasoning(
                    repo,
                    state["task_id"],
                    (
                        f"Supervisor retry {attempt} for final report failed "
                        f"({self._compact_error(exc)}). Retrying with tighter learnings compression."
                    ),
                    role="supervisor",
                )
        assert last_error is not None
        raise ValueError(
            f"Final report generation failed after {len(retry_plans)} attempts: {self._compact_error(last_error)}"
        ) from last_error

    async def _stream_report_chunks(self, repo: ResearchRepository, task_id: str, report: str) -> None:
        for chunk in self._chunk_text(report, size=320):
            await self._emit_message(repo, task_id, chunk)

    @staticmethod
    def _format_clarify_pairs(questions: list[str], answers: list[str]) -> str:
        pairs: list[str] = []
        for index, question in enumerate(questions):
            answer = answers[index].strip() if index < len(answers) else ""
            pairs.append(f"- Question: {question}\n  Answer: {answer or '(No answer provided)'}")
        return "\n".join(pairs) if pairs else "- No extra clarifications"

    @staticmethod
    def _build_search_retry_plans(total_docs: int) -> list[dict[str, Any]]:
        max_docs = max(1, total_docs or 1)
        candidates = [
            {"label": "full", "max_docs": max_docs, "per_doc_chars": 4000, "total_chars": 16000},
            {"label": "compressed", "max_docs": min(max_docs, 4), "per_doc_chars": 2000, "total_chars": 9000},
            {"label": "aggressive", "max_docs": min(max_docs, 2), "per_doc_chars": 900, "total_chars": 3200},
        ]
        unique: list[dict[str, Any]] = []
        seen: set[tuple[int, int, int]] = set()
        for candidate in candidates:
            signature = (
                int(candidate["max_docs"]),
                int(candidate["per_doc_chars"]),
                int(candidate["total_chars"]),
            )
            if signature in seen:
                continue
            seen.add(signature)
            unique.append(candidate)
        return unique

    @staticmethod
    def _build_final_report_retry_plans(total_learnings: int) -> list[dict[str, Any]]:
        max_items = max(1, total_learnings or 1)
        candidates = [
            {"label": "full", "max_items": max_items, "total_chars": 14000},
            {"label": "compressed", "max_items": min(max_items, 8), "total_chars": 9000},
            {"label": "aggressive", "max_items": min(max_items, 5), "total_chars": 5000},
        ]
        unique: list[dict[str, Any]] = []
        seen: set[tuple[int, int]] = set()
        for candidate in candidates:
            signature = (int(candidate["max_items"]), int(candidate["total_chars"]))
            if signature in seen:
                continue
            seen.add(signature)
            unique.append(candidate)
        return unique

    @staticmethod
    def _render_search_sources(
        *,
        docs: list[SearchDocument],
        max_docs: int,
        per_doc_chars: int,
        total_chars: int,
    ) -> tuple[str, int]:
        if not docs:
            return "No usable sources were retrieved for this query.", 0
        remaining = total_chars
        rendered: list[str] = []
        used = 0
        for doc in docs[:max_docs]:
            if remaining <= 0:
                break
            snippet_budget = min(per_doc_chars, remaining)
            snippet = doc.content[:snippet_budget].strip()
            if not snippet:
                continue
            rendered.append(f"Title: {doc.title}\nURL: {doc.url}\nContent: {snippet}")
            remaining -= len(snippet)
            used += 1
        if not rendered:
            return "No usable source content remained after compression.", 0
        return "\n\n".join(rendered), used

    @staticmethod
    def _render_learnings(
        learnings: list[str],
        *,
        max_items: int,
        total_chars: int,
    ) -> tuple[str, int]:
        if not learnings:
            return "- No validated learnings were collected.", 0
        remaining = total_chars
        rendered: list[str] = []
        used = 0
        for learning in learnings[:max_items]:
            if remaining <= 0:
                break
            snippet = learning[:remaining].strip()
            if not snippet:
                continue
            rendered.append(f"- {snippet}")
            remaining -= len(snippet)
            used += 1
        if not rendered:
            return "- No validated learnings were collected.", 0
        return "\n".join(rendered), used

    @staticmethod
    def _normalize_search_tasks(tasks: list[object]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        seen_queries: set[str] = set()
        for item in tasks:
            if not isinstance(item, dict):
                continue
            query = str(item.get("query", "")).strip()
            if not query:
                continue
            query_key = query.casefold()
            if query_key in seen_queries:
                continue
            research_goal = str(item.get("research_goal", "")).strip() or "Gather relevant evidence for the topic."
            normalized.append({"query": query, "research_goal": research_goal})
            seen_queries.add(query_key)
        return normalized[:5]

    @staticmethod
    def _fallback_search_tasks(query: str, brief: str, language: str) -> list[dict[str, str]]:
        base = (query or brief).strip()
        if language.lower().startswith("zh"):
            return [
                {"query": f"{base} 发展历程 关键论文", "research_goal": "梳理该主题的重要论文、提出时间和技术演进。"},
                {"query": f"{base} 代表性框架 产品 应用", "research_goal": "收集代表性框架、产品和真实应用案例。"},
                {"query": f"{base} 挑战 局限 最新进展", "research_goal": "总结当前挑战、局限和最近阶段的重要进展。"},
            ]
        return [
            {"query": f"{base} evolution key papers", "research_goal": "Trace the main papers and milestones behind the topic."},
            {"query": f"{base} frameworks products applications", "research_goal": "Collect representative frameworks, products, and real-world uses."},
            {"query": f"{base} challenges limitations latest progress", "research_goal": "Summarize current limitations and recent progress."},
        ]

    @staticmethod
    def _insufficient_search_summary(language: str) -> dict[str, str]:
        if language.lower().startswith("zh"):
            return {
                "learning": "检索结果不足，当前不能基于证据得出可靠结论。",
                "reasoning": "搜索阶段没有返回可用网页正文，继续总结只会放大幻觉。",
            }
        return {
            "learning": "The retrieved evidence is insufficient to support a reliable conclusion.",
            "reasoning": "The search stage returned no usable source content, so further synthesis would be speculative.",
        }

    @staticmethod
    def _has_actionable_learnings(learnings: list[str]) -> bool:
        stripped = [item.strip() for item in learnings if item and item.strip()]
        if not stripped:
            return False
        blocked_markers = {
            "检索结果不足，当前不能基于证据得出可靠结论。",
            "The retrieved evidence is insufficient to support a reliable conclusion.",
        }
        return any(item not in blocked_markers for item in stripped)

    @staticmethod
    def _build_insufficient_evidence_report(query: str, language: str) -> str:
        if language.lower().startswith("zh"):
            return (
                f"# {query}\n\n"
                "## 执行结果\n\n"
                "当前报告未生成可信结论，因为检索阶段没有收集到足够的有效来源正文。\n\n"
                "## 为什么会这样\n\n"
                "- 搜索结果为空，或只返回了很短的摘要片段。\n"
                "- 证据不足时继续让模型总结，会产出看似通顺但没有事实支撑的内容。\n\n"
                "## 建议下一步\n\n"
                "- 检查搜索 provider 是否正常返回正文内容。\n"
                "- 换用更稳定的搜索源，或提高 `max_results`。\n"
                "- 缩小主题范围，例如改成“RAG 在 2020-2026 年的重要论文和产品演进”。\n"
            )
        return (
            f"# {query}\n\n"
            "## Result\n\n"
            "A reliable report could not be produced because the search stage did not collect enough usable source content.\n\n"
            "## Why\n\n"
            "- Search returned no results, or only very short snippets.\n"
            "- Continuing synthesis without evidence would produce fluent but unsupported text.\n\n"
            "## Next steps\n\n"
            "- Verify that the search provider returns full page content.\n"
            "- Try a more reliable search source, or increase `max_results`.\n"
            "- Narrow the topic scope before rerunning the task.\n"
        )

    @staticmethod
    def _compact_error(error: Exception) -> str:
        message = str(error).replace("\n", " ").strip()
        return message[:160] if message else error.__class__.__name__

    def _task_lock(self, task_id: str) -> asyncio.Lock:
        lock = self._task_locks.get(task_id)
        if lock is None:
            lock = asyncio.Lock()
            self._task_locks[task_id] = lock
        return lock

    async def _emit_progress(
        self,
        repo: ResearchRepository,
        task_id: str,
        step: str,
        status: str,
        extra: Optional[dict[str, object]] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
        attempt: Optional[int] = None,
        compressed_context: Optional[bool] = None,
    ) -> None:
        payload: dict[str, object] = {"step": step, "status": status}
        if name:
            payload["name"] = name
        if role:
            payload["role"] = role
        if attempt is not None:
            payload["attempt"] = attempt
        if compressed_context is not None:
            payload["compressed_context"] = compressed_context
        if extra:
            payload["data"] = extra
        async with self._task_lock(task_id):
            await self._emit_event_unlocked(repo=repo, task_id=task_id, event="progress", data=payload, step=step)
            task = await repo.get_task(task_id)
            if task is not None:
                await repo.update_task(task, current_step=step)

    async def _emit_reasoning(
        self,
        repo: ResearchRepository,
        task_id: str,
        text: str,
        role: Optional[str] = None,
    ) -> None:
        payload: dict[str, object] = {"type": "text", "text": text}
        if role:
            payload["role"] = role
        await self._emit_event(repo=repo, task_id=task_id, event="reasoning", data=payload)

    async def _emit_message(self, repo: ResearchRepository, task_id: str, text: str) -> None:
        await self._emit_event(repo=repo, task_id=task_id, event="message", data={"type": "text", "text": text})

    async def _emit_event(
        self,
        *,
        repo: ResearchRepository,
        task_id: str,
        event: str,
        data: dict[str, object],
        step: Optional[str] = None,
    ) -> None:
        async with self._task_lock(task_id):
            await self._emit_event_unlocked(
                repo=repo,
                task_id=task_id,
                event=event,
                data=data,
                step=step,
            )

    async def _emit_event_unlocked(
        self,
        *,
        repo: ResearchRepository,
        task_id: str,
        event: str,
        data: dict[str, object],
        step: Optional[str] = None,
    ) -> None:
        db_event = await repo.append_event(task_id=task_id, event_type=event, payload=data, step=step)
        await self.stream_manager.publish(
            task_id,
            {
                "id": db_event.id,
                "sequence": db_event.sequence,
                "event": event,
                "data": data,
            },
        )

    @staticmethod
    def _chunk_text(text: str, size: int) -> list[str]:
        chunks: list[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if len(candidate) > size and current:
                chunks.append(current + " ")
                current = word
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks
