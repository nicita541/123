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
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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

