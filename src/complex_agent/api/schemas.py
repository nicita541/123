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
    project_id: str | None = None


class ApprovalRequestModel(BaseModel):
    step_id: str
    action: str


class ProjectSelectRequest(BaseModel):
    path: str


class ProjectCreateRequest(BaseModel):
    root_path: str
    name: str | None = None


class ProjectRegistrationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mount_id: str = Field(min_length=8, max_length=64)
    host_path: str = Field(min_length=3, max_length=1024)
    container_path: str = Field(min_length=10, max_length=1024)


class ContinueTaskRequest(BaseModel):
    message: str = Field(min_length=1)


class RollbackRequest(BaseModel):
    confirm_created_deletions: bool = False


class SettingsUpdateRequest(BaseModel):
    ollama_base_url: str | None = None
    selected_model: str | None = None
    default_access_mode: str | None = None
    max_fix_iterations: int | None = None
    ui_preferences: dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    id: str | None = None
    name: str | None = None
    project_root: str
    exists: bool = True
    writable: bool = True
    warning: str | None = None


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
