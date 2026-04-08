from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_research_service, get_stream_manager
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


@router.post("/clarify", response_model=ClarifyResponse)
async def clarify_topic(
    payload: ClarifyRequest,
    service: ResearchService = Depends(get_research_service),
) -> ClarifyResponse:
    try:
        questions = await service.clarify_questions(payload)
        return ClarifyResponse(questions=questions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks", response_model=ResearchTaskCreateResponse)
async def create_task(
    payload: ResearchTaskCreateRequest,
    service: ResearchService = Depends(get_research_service),
) -> ResearchTaskCreateResponse:
    task = await service.create_task(payload)
    return ResearchTaskCreateResponse(task_id=str(task.id), status=task.status)


@router.post("/tasks/{task_id}/follow-up", response_model=ResearchTaskCreateResponse)
async def create_follow_up_task(
    task_id: str,
    payload: ResearchTaskFollowUpRequest,
    service: ResearchService = Depends(get_research_service),
) -> ResearchTaskCreateResponse:
    task = await service.create_follow_up_task(
        parent_task_id=task_id,
        follow_up_request=payload.follow_up_request,
        max_results=payload.max_results,
    )
    return ResearchTaskCreateResponse(task_id=str(task.id), status=task.status)


@router.get("/tasks", response_model=list[ResearchTaskSummary])
async def list_tasks(
    limit: int = 20,
    session: AsyncSession = Depends(get_db),
    service: ResearchService = Depends(get_research_service),
) -> list[ResearchTaskSummary]:
    return await service.list_task_summaries(session, limit=limit)


@router.get("/tasks/{task_id}", response_model=ResearchTaskDetail)
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_db),
    service: ResearchService = Depends(get_research_service),
) -> ResearchTaskDetail:
    task = await service.get_task_detail(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/tasks/{task_id}", response_model=ResearchTaskDeleteResponse)
async def delete_task(
    task_id: str,
    service: ResearchService = Depends(get_research_service),
) -> ResearchTaskDeleteResponse:
    return await service.delete_task(task_id)


@router.get("/tasks/{task_id}/stream")
async def stream_task(
    task_id: str,
    session: AsyncSession = Depends(get_db),
    service: ResearchService = Depends(get_research_service),
    stream_manager: StreamManager = Depends(get_stream_manager),
) -> StreamingResponse:
    generator = service.stream_task_events(
        session=session,
        stream_manager=stream_manager,
        task_id=task_id,
    )
    return StreamingResponse(generator, media_type="text/event-stream")
