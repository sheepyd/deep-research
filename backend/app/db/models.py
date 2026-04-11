import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parent_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="SET NULL"),
    )
    research_iteration: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    clarify_questions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    clarify_answers: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    clarified_brief: Mapped[Optional[str]] = mapped_column(Text)
    follow_up_request: Mapped[Optional[str]] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    thinking_model: Mapped[str] = mapped_column(String(128), nullable=False)
    task_model: Mapped[str] = mapped_column(String(128), nullable=False)
    search_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="zh-CN", nullable=False)
    max_results: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    current_step: Mapped[Optional[str]] = mapped_column(String(64))
    report_plan: Mapped[Optional[str]] = mapped_column(Text)
    final_report: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    events: Mapped[list["ResearchEvent"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    sources: Mapped[list["ResearchSource"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    parent_task: Mapped[Optional["ResearchTask"]] = relationship(
        remote_side=[id],
        backref="follow_up_tasks",
    )


class ResearchEvent(Base):
    __tablename__ = "research_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    step: Mapped[Optional[str]] = mapped_column(String(64))
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[ResearchTask] = relationship(back_populates="events")


class ResearchSource(Base):
    __tablename__ = "research_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="web")
    title: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)

    task: Mapped[ResearchTask] = relationship(back_populates="sources")
