import asyncio
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.api.routes.mcp import _sse_session_stream, session_manager
from app.core.config import Settings


class FakeService:
    class FakeDetail:
        def __init__(self, payload):
            self.payload = payload

        def model_dump(self, mode="python"):
            return self.payload

    async def list_task_summaries(self, session, *, owner_id, limit=20):
        return [
            {
                "id": str(uuid4()),
                "parent_task_id": None,
                "research_iteration": 1,
                "status": "completed",
                "query": "topic",
                "follow_up_request": None,
                "provider": "openai",
                "thinking_model": "gpt-5.4-mini",
                "task_model": "gpt-5.4-mini",
                "search_provider": "tavily",
                "language": "zh-CN",
                "current_step": "completed",
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-01T00:00:00Z",
                "completed_at": "2026-04-01T00:00:00Z",
            }
        ]

    async def clarify_questions(self, payload):
        return ["Q1", "Q2"]

    async def create_task(self, payload, *, owner_id):
        return type("Task", (), {"id": str(uuid4()), "status": "queued"})()

    async def create_follow_up_task(self, parent_task_id, follow_up_request, max_results=None, owner_id="admin"):
        return type("Task", (), {"id": str(uuid4()), "status": "queued"})()

    async def run_task_inline(self, payload, *, owner_id):
        return self.FakeDetail(
            {
                "id": str(uuid4()),
                "parent_task_id": payload.parent_task_id,
                "research_iteration": payload.research_iteration,
                "status": "completed",
                "query": payload.query,
                "clarify_questions": payload.questions,
                "clarify_answers": payload.answers,
                "clarified_brief": "brief",
                "follow_up_request": payload.follow_up_request,
                "provider": payload.provider,
                "thinking_model": payload.thinking_model,
                "task_model": payload.task_model,
                "search_provider": payload.search_provider,
                "language": payload.language,
                "max_results": payload.max_results,
                "current_step": "completed",
                "report_plan": "plan",
                "final_report": "report",
                "error_message": None,
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-01T00:00:00Z",
                "completed_at": "2026-04-01T00:00:00Z",
                "sources": [],
                "events": [],
            }
        )

    async def run_follow_up_inline(self, parent_task_id, follow_up_request, max_results=None, owner_id="admin"):
        return self.FakeDetail(
            {
                "id": str(uuid4()),
                "parent_task_id": parent_task_id,
                "research_iteration": 2,
                "status": "completed",
                "query": "topic",
                "clarify_questions": ["Q1", "Q2"],
                "clarify_answers": ["A1", "A2"],
                "clarified_brief": "brief",
                "follow_up_request": follow_up_request,
                "provider": "openai",
                "thinking_model": "gpt-5.4-mini",
                "task_model": "gpt-5.4-mini",
                "search_provider": "searxng",
                "language": "zh-CN",
                "max_results": max_results or 5,
                "current_step": "completed",
                "report_plan": "plan",
                "final_report": "report",
                "error_message": None,
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-01T00:00:00Z",
                "completed_at": "2026-04-01T00:00:00Z",
                "sources": [],
                "events": [],
            }
        )

    async def get_task_detail(self, session, task_id, *, owner_id):
        return {
            "id": task_id,
            "parent_task_id": None,
            "research_iteration": 1,
            "status": "completed",
            "query": "topic",
            "clarify_questions": ["Q1", "Q2"],
            "clarify_answers": ["A1", "A2"],
            "clarified_brief": "brief",
            "follow_up_request": None,
            "provider": "openai",
            "thinking_model": "gpt-5.4-mini",
            "task_model": "gpt-5.4-mini",
            "search_provider": "searxng",
            "language": "zh-CN",
            "max_results": 5,
            "current_step": "completed",
            "report_plan": "plan",
            "final_report": "report",
            "error_message": None,
            "created_at": "2026-04-01T00:00:00Z",
            "updated_at": "2026-04-01T00:00:00Z",
            "completed_at": "2026-04-01T00:00:00Z",
            "sources": [],
            "events": [],
        }

    async def delete_task(self, task_id, *, owner_id):
        return {"deleted": True}

    def stream_task_events(self, session, stream_manager, task_id, owner_id):
        async def iterator():
            yield b"event: infor\ndata: {}\n\n"
            yield b"event: done\ndata: {\"task_id\": \"%s\"}\n\n" % task_id.encode()

        return iterator()


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-session-secret")
    app.state.research_service = FakeService()
    app.state.stream_manager = object()
    app.include_router(api_router, prefix="/api/v1")
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_login_and_session_cookie(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"password": "change-me"})
    assert response.status_code == 200
    assert response.json()["authenticated"] is True

    session_response = client.get("/api/v1/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is True


def test_list_tasks(client: TestClient) -> None:
    response = client.get("/api/v1/research/tasks", headers={"Authorization": "Bearer change-me"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["status"] == "completed"


def test_create_task_requires_questions(client: TestClient) -> None:
    response = client.post(
        "/api/v1/research/tasks",
        headers={"Authorization": "Bearer change-me"},
        json={
            "query": "topic",
            "answers": [],
            "provider": "openai",
            "thinking_model": "gpt-5.4-mini",
            "task_model": "gpt-5.4-mini",
            "search_provider": "tavily",
            "language": "zh-CN",
            "max_results": 5,
        },
    )
    assert response.status_code == 422


def test_create_follow_up_task(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/research/tasks/{uuid4()}/follow-up",
        headers={"Authorization": "Bearer change-me"},
        json={"follow_up_request": "继续研究竞争格局"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"


def test_delete_task(client: TestClient) -> None:
    response = client.delete(
        f"/api/v1/research/tasks/{uuid4()}",
        headers={"Authorization": "Bearer change-me"},
    )
    assert response.status_code == 200
    assert response.json() == {"deleted": True}


def test_mcp_tools_list(client: TestClient) -> None:
    response = client.post(
        "/api/v1/mcp",
        headers={"Authorization": "Bearer change-me"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["tools"]


def test_mcp_streamable_http_run_tool(client: TestClient) -> None:
    response = client.post(
        "/api/v1/mcp",
        headers={"Authorization": "Bearer change-me"},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "deep-research.run",
                "arguments": {
                    "query": "topic",
                    "provider": "openai",
                    "thinking_model": "gpt-5.4-mini",
                    "task_model": "gpt-5.4-mini",
                    "search_provider": "tavily",
                },
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_mcp_sse_transport_session_flow() -> None:
    session = await session_manager.create("admin")
    stream = _sse_session_stream(session.session_id, Settings(api_bearer_token="token", sse_keepalive_seconds=1))

    first_event = (await asyncio.wait_for(anext(stream), timeout=1)).decode()
    assert "sessionId" in first_event
    assert session.session_id in first_event

    await session.queue.put({"jsonrpc": "2.0", "id": 3, "result": {"tools": []}})
    second_event = (await asyncio.wait_for(anext(stream), timeout=1)).decode()
    assert '"tools": []' in second_event

    await stream.aclose()
