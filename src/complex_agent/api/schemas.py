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


class ProjectSelectRequest(BaseModel):
    path: str


class ProjectResponse(BaseModel):
    project_root: str
    exists: bool = True
    writable: bool = True


class WorkspaceFile(BaseModel):
    path: str
    name: str
    directory: str
    extension: str


class ChangedFile(BaseModel):
    path: str
    status: str


class WorkspaceResponse(BaseModel):
    project_root: str
    git_branch: str | None = None
    important_directories: list[str] = Field(default_factory=list)
    files: list[WorkspaceFile] = Field(default_factory=list)
    changed_files: list[ChangedFile] = Field(default_factory=list)
    tool_count: int
    enabled_tool_count: int
    status: str = "ready"


class FileListResponse(BaseModel):
    files: list[WorkspaceFile] = Field(default_factory=list)
    count: int


class FilePreviewResponse(BaseModel):
    path: str
    content: str
    truncated: bool = False


class GitDiffResponse(BaseModel):
    diff: str
    changed_files: list[ChangedFile] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    type: str
    title: str
    step_id: str | None = None
    action: str | None = None
    status: str | None = None


class TimelineResponse(BaseModel):
    task_id: str
    events: list[TimelineEvent] = Field(default_factory=list)


class ApiMessage(BaseModel):
    role: str
    content: str


class ApiResponse(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
