from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    mode: str = "review"


class PlanRequest(BaseModel):
    task: str
    mode: str = "review"
    project_path: str | None = None


class ApprovalRequestModel(BaseModel):
    step_id: str
    action: str


class ApiMessage(BaseModel):
    role: str
    content: str


class ApiResponse(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)

