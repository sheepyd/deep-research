import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_db, get_research_service, get_stream_manager, require_api_auth
from app.research.schemas import (
    ClarifyRequest,
    ClarifyResponse,
    ResearchTaskCreateRequest,
    ResearchTaskCreateResponse,
    ResearchTaskDeleteResponse,
    ResearchTaskFollowUpRequest,
    ResearchTaskDetail,
    ResearchTaskSummary,
)
from app.research.service import ResearchService
from app.research.streaming import StreamManager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/clarify", response_model=ClarifyResponse)
async def clarify_topic(
    payload: ClarifyRequest,
    auth: AuthContext = Depends(require_api_auth),
    service: ResearchService = Depends(get_research_service),
) -> ClarifyResponse:
    try:
        questions = await service.clarify_questions(payload)
        return ClarifyResponse(questions=questions)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to clarify research topic for %s", auth.subject)
        raise HTTPException(status_code=500, detail="Unable to generate clarification questions")


@router.post("/tasks", response_model=ResearchTaskCreateResponse)
async def create_task(
    payload: ResearchTaskCreateRequest,
    auth: AuthContext = Depends(require_api_auth),
    service: ResearchService = Depends(get_research_service),
) -> ResearchTaskCreateResponse:
    task = await service.create_task(payload, owner_id=auth.subject)
    return ResearchTaskCreateResponse(task_id=str(task.id), status=task.status)


@router.post("/tasks/{task_id}/follow-up", response_model=ResearchTaskCreateResponse)
async def create_follow_up_task(
    task_id: str,
    payload: ResearchTaskFollowUpRequest,
    auth: AuthContext = Depends(require_api_auth),
    service: ResearchService = Depends(get_research_service),
) -> ResearchTaskCreateResponse:
    task = await service.create_follow_up_task(
        parent_task_id=task_id,
        follow_up_request=payload.follow_up_request,
        max_results=payload.max_results,
        owner_id=auth.subject,
    )
    return ResearchTaskCreateResponse(task_id=str(task.id), status=task.status)


@router.get("/tasks", response_model=list[ResearchTaskSummary])
async def list_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require_api_auth),
    session: AsyncSession = Depends(get_db),
    service: ResearchService = Depends(get_research_service),
) -> list[ResearchTaskSummary]:
    return await service.list_task_summaries(session, owner_id=auth.subject, limit=limit)


@router.get("/tasks/{task_id}", response_model=ResearchTaskDetail)
async def get_task(
    task_id: str,
    auth: AuthContext = Depends(require_api_auth),
    session: AsyncSession = Depends(get_db),
    service: ResearchService = Depends(get_research_service),
) -> ResearchTaskDetail:
    task = await service.get_task_detail(session, task_id, owner_id=auth.subject)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/tasks/{task_id}", response_model=ResearchTaskDeleteResponse)
async def delete_task(
    task_id: str,
    auth: AuthContext = Depends(require_api_auth),
    service: ResearchService = Depends(get_research_service),
) -> ResearchTaskDeleteResponse:
    return await service.delete_task(task_id, owner_id=auth.subject)


@router.get("/tasks/{task_id}/stream")
async def stream_task(
    task_id: str,
    auth: AuthContext = Depends(require_api_auth),
    session: AsyncSession = Depends(get_db),
    service: ResearchService = Depends(get_research_service),
    stream_manager: StreamManager = Depends(get_stream_manager),
) -> StreamingResponse:
    generator = service.stream_task_events(
        session=session,
        stream_manager=stream_manager,
        task_id=task_id,
        owner_id=auth.subject,
    )
    return StreamingResponse(generator, media_type="text/event-stream")
