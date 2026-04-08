from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ResearchEvent, ResearchSource, ResearchTask
from app.research.providers import SearchDocument


class ResearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _normalize_task_id(task_id: Union[str, UUID]) -> UUID:
        return task_id if isinstance(task_id, UUID) else UUID(str(task_id))

    async def create_task(
        self,
        *,
        query: str,
        clarify_questions: list[str],
        clarify_answers: list[str],
        clarified_brief: str,
        parent_task_id: Optional[Union[str, UUID]],
        research_iteration: int,
        follow_up_request: Optional[str],
        provider: str,
        thinking_model: str,
        task_model: str,
        search_provider: str,
        language: str,
        max_results: int,
    ) -> ResearchTask:
        task = ResearchTask(
            query=query,
            clarify_questions=clarify_questions,
            clarify_answers=clarify_answers,
            clarified_brief=clarified_brief,
            parent_task_id=self._normalize_task_id(parent_task_id) if parent_task_id else None,
            research_iteration=research_iteration,
            follow_up_request=follow_up_request,
            provider=provider,
            thinking_model=thinking_model,
            task_model=task_model,
            search_provider=search_provider,
            language=language,
            max_results=max_results,
            status="queued",
            current_step="queued",
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_task(self, task_id: Union[str, UUID]) -> Optional[ResearchTask]:
        task_uuid = self._normalize_task_id(task_id)
        result = await self.session.execute(select(ResearchTask).where(ResearchTask.id == task_uuid))
        return result.scalar_one_or_none()

    async def update_task(self, task: ResearchTask, **changes) -> ResearchTask:
        for key, value in changes.items():
            setattr(task, key, value)
        if "status" in changes and changes["status"] in {"completed", "failed"}:
            task.completed_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def append_event(
        self,
        *,
        task_id: Union[str, UUID],
        event_type: str,
        payload: dict[str, object],
        step: Optional[str] = None,
    ) -> ResearchEvent:
        task_uuid = self._normalize_task_id(task_id)
        current_sequence = await self.session.scalar(
            select(func.coalesce(func.max(ResearchEvent.sequence), 0)).where(
                ResearchEvent.task_id == task_uuid
            )
        )
        event = ResearchEvent(
            task_id=task_uuid,
            sequence=int(current_sequence or 0) + 1,
            event_type=event_type,
            step=step,
            payload_json=payload,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def replace_sources(self, task_id: Union[str, UUID], sources: list[SearchDocument]) -> None:
        task_uuid = self._normalize_task_id(task_id)
        await self.session.execute(delete(ResearchSource).where(ResearchSource.task_id == task_uuid))
        self.session.add_all(
            [
                ResearchSource(
                    task_id=task_uuid,
                    source_type="web",
                    title=item.title,
                    url=item.url,
                    content=item.content,
                    meta_json=item.metadata,
                )
                for item in sources
            ]
        )
        await self.session.commit()

    async def list_events(self, task_id: Union[str, UUID]) -> list[ResearchEvent]:
        task_uuid = self._normalize_task_id(task_id)
        result = await self.session.execute(
            select(ResearchEvent)
            .where(ResearchEvent.task_id == task_uuid)
            .order_by(ResearchEvent.sequence.asc())
        )
        return list(result.scalars().all())

    async def list_sources(self, task_id: Union[str, UUID]) -> list[ResearchSource]:
        task_uuid = self._normalize_task_id(task_id)
        result = await self.session.execute(
            select(ResearchSource)
            .where(ResearchSource.task_id == task_uuid)
            .order_by(ResearchSource.id.asc())
        )
        return list(result.scalars().all())

    async def list_tasks(self, limit: int = 20) -> list[ResearchTask]:
        result = await self.session.execute(
            select(ResearchTask).order_by(ResearchTask.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
