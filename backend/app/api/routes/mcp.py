import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_research_service
from app.core.config import Settings, get_settings
from app.core.sse import format_sse
from app.research.schemas import ClarifyRequest, ResearchTaskCreateRequest
from app.research.service import ResearchService

router = APIRouter(prefix="/mcp")

SERVER_INFO = {"name": "deep-research", "version": "0.3.0"}
PROTOCOL_VERSION = "2025-03-26"
POST_ENDPOINT_PATH = "/api/v1/mcp/sse/messages"


@dataclass
class McpSession:
    session_id: str
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)


class McpSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, McpSession] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> McpSession:
        session = McpSession(session_id=str(uuid4()))
        async with self._lock:
            self._sessions[session.session_id] = session
        return session

    async def get(self, session_id: str) -> Optional[McpSession]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def close(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)


session_manager = McpSessionManager()


def _tool_descriptors() -> list[dict[str, Any]]:
    return [
        {
            "name": "deep-research.run",
            "description": "Run a deep research workflow and return a cited report. Uses MCP defaults when model settings are omitted.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "provider": {"type": "string"},
                    "thinking_model": {"type": "string"},
                    "task_model": {"type": "string"},
                    "search_provider": {"type": "string"},
                    "language": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
                    "questions": {"type": "array", "items": {"type": "string"}},
                    "answers": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["query"],
            },
        },
        {
            "name": "deep-research.follow-up",
            "description": "Start another research round from a completed task using follow-up instructions.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "follow_up_request": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["task_id", "follow_up_request"],
            },
        },
        {
            "name": "deep-research.get-task",
            "description": "Fetch a research task detail payload including report, events, and sources.",
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
        },
        {
            "name": "deep-research.list-tasks",
            "description": "List recent research tasks.",
            "inputSchema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            },
        },
        {
            "name": "deep-research.clarify",
            "description": "Generate clarification questions for a research topic before starting a task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "provider": {"type": "string"},
                    "thinking_model": {"type": "string"},
                    "language": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    ]


def _jsonrpc_payload(*, request_id: Any, result: Optional[dict[str, Any]] = None, error: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result or {}
    return payload


def _jsonrpc_result(result: dict[str, Any], *, request_id: Any) -> JSONResponse:
    return JSONResponse(_jsonrpc_payload(request_id=request_id, result=result))


def _jsonrpc_error(code: int, message: str, *, request_id: Any) -> JSONResponse:
    return JSONResponse(_jsonrpc_payload(request_id=request_id, error={"code": code, "message": message}))


def _tool_text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def _require_argument(arguments: dict[str, Any], key: str, *, fallback: Optional[str] = None) -> str:
    value = arguments.get(key, fallback)
    if value is None or str(value).strip() == "":
        raise HTTPException(status_code=400, detail=f"Missing required MCP setting: {key}")
    return str(value)


async def _build_run_payload(
    arguments: dict[str, Any],
    *,
    settings: Settings,
    service: ResearchService,
) -> ResearchTaskCreateRequest:
    query = _require_argument(arguments, "query")
    provider = _require_argument(arguments, "provider", fallback=settings.mcp_ai_provider)
    thinking_model = _require_argument(arguments, "thinking_model", fallback=settings.mcp_thinking_model)
    task_model = _require_argument(arguments, "task_model", fallback=settings.mcp_task_model)
    search_provider = _require_argument(arguments, "search_provider", fallback=settings.mcp_search_provider)
    language = str(arguments.get("language") or settings.mcp_language or "zh-CN")
    max_results = int(arguments.get("max_results") or settings.mcp_max_results or 5)

    questions = list(arguments.get("questions") or [])
    if not questions:
        questions = await service.clarify_questions(
            ClarifyRequest(
                query=query,
                provider=provider,
                thinking_model=thinking_model,
                language=language,
            )
        )
    answers = list(arguments.get("answers") or [])

    return ResearchTaskCreateRequest(
        query=query,
        questions=questions,
        answers=answers,
        provider=provider,
        thinking_model=thinking_model,
        task_model=task_model,
        search_provider=search_provider,
        language=language,
        max_results=max_results,
    )


async def _handle_mcp_request(
    body: dict[str, Any],
    *,
    service: ResearchService,
    session: AsyncSession,
    settings: Settings,
) -> dict[str, Any]:
    method = body.get("method")
    request_id = body.get("id")
    params = body.get("params") or {}

    if method == "initialize":
        return _jsonrpc_payload(
            request_id=request_id,
            result={
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": SERVER_INFO,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
            },
        )

    if method == "notifications/initialized":
        return _jsonrpc_payload(request_id=request_id, result={})

    if method == "ping":
        return _jsonrpc_payload(request_id=request_id, result={})

    if method == "tools/list":
        return _jsonrpc_payload(request_id=request_id, result={"tools": _tool_descriptors()})

    if method != "tools/call":
        return _jsonrpc_payload(
            request_id=request_id,
            error={"code": -32601, "message": f"Method not found: {method}"},
        )

    tool_name = params.get("name")
    arguments = params.get("arguments") or {}

    try:
        if tool_name == "deep-research.run":
            payload = await _build_run_payload(arguments, settings=settings, service=service)
            detail = await service.run_task_inline(payload)
            return _jsonrpc_payload(request_id=request_id, result=_tool_text(detail.model_dump(mode="json")))

        if tool_name == "deep-research.follow-up":
            detail = await service.run_follow_up_inline(
                parent_task_id=_require_argument(arguments, "task_id"),
                follow_up_request=_require_argument(arguments, "follow_up_request"),
                max_results=int(arguments["max_results"]) if arguments.get("max_results") is not None else None,
            )
            return _jsonrpc_payload(request_id=request_id, result=_tool_text(detail.model_dump(mode="json")))

        if tool_name == "deep-research.get-task":
            detail = await service.get_task_detail(session, _require_argument(arguments, "task_id"))
            if detail is None:
                return _jsonrpc_payload(request_id=request_id, error={"code": -32004, "message": "Task not found"})
            return _jsonrpc_payload(request_id=request_id, result=_tool_text(detail.model_dump(mode="json")))

        if tool_name == "deep-research.list-tasks":
            limit = int(arguments.get("limit") or 20)
            tasks = await service.list_task_summaries(session, limit=limit)
            return _jsonrpc_payload(
                request_id=request_id,
                result=_tool_text([task.model_dump(mode="json") for task in tasks]),
            )

        if tool_name == "deep-research.clarify":
            provider = _require_argument(arguments, "provider", fallback=settings.mcp_ai_provider)
            thinking_model = _require_argument(arguments, "thinking_model", fallback=settings.mcp_thinking_model)
            language = str(arguments.get("language") or settings.mcp_language or "zh-CN")
            questions = await service.clarify_questions(
                ClarifyRequest(
                    query=_require_argument(arguments, "query"),
                    provider=provider,
                    thinking_model=thinking_model,
                    language=language,
                )
            )
            return _jsonrpc_payload(request_id=request_id, result=_tool_text({"questions": questions}))
    except HTTPException as exc:
        return _jsonrpc_payload(request_id=request_id, error={"code": -32000, "message": exc.detail})
    except Exception as exc:  # noqa: BLE001
        return _jsonrpc_payload(request_id=request_id, error={"code": -32000, "message": str(exc)})

    return _jsonrpc_payload(request_id=request_id, error={"code": -32602, "message": f"Unknown tool: {tool_name}"})


async def _sse_session_stream(session_id: str, settings: Settings) -> AsyncIterator[bytes]:
    session = await session_manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="MCP session not found")

    yield format_sse(
        "endpoint",
        {
            "sessionId": session_id,
            "endpoint": f"{POST_ENDPOINT_PATH}?sessionId={session_id}",
            "protocolVersion": PROTOCOL_VERSION,
            "server": SERVER_INFO,
        },
    )
    try:
        while True:
            try:
                message = await asyncio.wait_for(session.queue.get(), timeout=settings.sse_keepalive_seconds)
                yield format_sse("message", message)
            except asyncio.TimeoutError:
                yield b": keepalive\n\n"
    finally:
        await session_manager.close(session_id)


@router.post("")
async def handle_streamable_http_mcp(
    request: Request,
    service: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    body = await request.json()
    payload = await _handle_mcp_request(body, service=service, session=session, settings=settings)
    return JSONResponse(payload)


@router.get("/sse")
async def open_sse_mcp(settings: Settings = Depends(get_settings)) -> StreamingResponse:
    session = await session_manager.create()
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(_sse_session_stream(session.session_id, settings), media_type="text/event-stream", headers=headers)


@router.post("/sse/messages")
async def handle_sse_mcp_message(
    request: Request,
    session_id: str = Query(..., alias="sessionId"),
    service: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    mcp_session = await session_manager.get(session_id)
    if mcp_session is None:
        raise HTTPException(status_code=404, detail="MCP session not found")
    body = await request.json()
    payload = await _handle_mcp_request(body, service=service, session=session, settings=settings)
    await mcp_session.queue.put(payload)
    return Response(status_code=202)


@router.delete("/sse")
async def close_sse_mcp(session_id: str = Query(..., alias="sessionId")) -> Response:
    await session_manager.close(session_id)
    return Response(status_code=204)
