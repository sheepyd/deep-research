from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ClarifyRequest(BaseModel):
    query: str = Field(min_length=3)
    provider: str
    thinking_model: str
    language: str = "zh-CN"


class ClarifyResponse(BaseModel):
    questions: list[str]


class ResearchTaskCreateRequest(BaseModel):
    query: str = Field(min_length=3)
    questions: list[str] = Field(min_length=1)
    answers: list[str] = Field(default_factory=list)
    parent_task_id: Optional[str] = None
    research_iteration: int = Field(default=1, ge=1)
    follow_up_request: Optional[str] = None
    provider: str
    thinking_model: str
    task_model: str
    search_provider: str
    language: str = "zh-CN"
    max_results: int = Field(default=5, ge=1, le=10)


class ResearchTaskCreateResponse(BaseModel):
    task_id: str
    status: str


class ResearchTaskDeleteResponse(BaseModel):
    deleted: bool


class ResearchTaskFollowUpRequest(BaseModel):
    follow_up_request: str = Field(min_length=3)
    max_results: Optional[int] = Field(default=None, ge=1, le=10)


class ResearchTaskSummary(BaseModel):
    id: str
    parent_task_id: Optional[str]
    research_iteration: int
    status: str
    query: str
    follow_up_request: Optional[str]
    provider: str
    thinking_model: str
    task_model: str
    search_provider: str
    language: str
    current_step: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class SourcePayload(BaseModel):
    id: int
    source_type: str
    title: Optional[str]
    url: str
    content: str
    meta_json: dict[str, object]

    model_config = ConfigDict(from_attributes=True)


class EventPayload(BaseModel):
    id: int
    sequence: int
    event_type: str
    step: Optional[str]
    payload_json: dict[str, object]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResearchTaskDetail(BaseModel):
    id: str
    parent_task_id: Optional[str]
    research_iteration: int
    status: str
    query: str
    clarify_questions: list[str]
    clarify_answers: list[str]
    clarified_brief: Optional[str]
    follow_up_request: Optional[str]
    provider: str
    thinking_model: str
    task_model: str
    search_provider: str
    language: str
    max_results: int
    current_step: Optional[str]
    report_plan: Optional[str]
    final_report: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]
    sources: list[SourcePayload]
    events: list[EventPayload]

    model_config = ConfigDict(from_attributes=True)
