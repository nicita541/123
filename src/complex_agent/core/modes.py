from __future__ import annotations

from enum import Enum


class AgentMode(str, Enum):
    CHAT = "chat"
    PLAN = "plan"
    REVIEW = "review"
    DEV = "dev"
    AUTO = "auto"
    AUDIT = "audit"


class TaskStatus(str, Enum):
    CREATED = "created"
    DRAFT = "draft"
    PLANNING = "planning"
    PLANNED = "planned"
    PROPOSING = "proposing"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    APPLYING = "applying"
    VERIFYING = "verifying"
    NEEDS_FIX = "needs_fix"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class LocalRole(str, Enum):
    OWNER = "owner"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class Visibility(str, Enum):
    PRIVATE = "private"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    REJECTED = "rejected"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
