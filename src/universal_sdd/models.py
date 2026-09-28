from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentName(str, Enum):
    cursor = "cursor"
    codex = "codex"
    claude = "claude"
    gemini = "gemini"
    copilot = "copilot"
    mock = "mock"


PRIMARY_AGENTS = (
    AgentName.cursor,
    AgentName.codex,
    AgentName.claude,
    AgentName.gemini,
    AgentName.copilot,
)


class ProjectKind(str, Enum):
    new = "new"
    existing = "existing"


class RunStatus(str, Enum):
    not_started = "not_started"
    initializing = "initializing"
    ready = "ready"
    running = "running"
    paused = "paused"
    completed = "completed"
    blocked = "blocked"
    failed = "failed"


class ItemStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    in_progress = "in_progress"
    implemented = "implemented"
    verified = "verified"
    blocked = "blocked"
    invalidated = "invalidated"
    failed = "failed"


class DecisionStatus(str, Enum):
    open = "open"
    selected = "selected"
    deferred = "deferred"


class SDDConfig(BaseModel):
    schema_version: int = 1
    project_name: str
    project_kind: ProjectKind = ProjectKind.new
    prd_path: str = "PRD.md"
    primary_agent: AgentName
    created_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)
    autonomous_implementation: bool = True
    require_approval_for_spec_changes: bool = True
    require_approval_for_architecture_changes: bool = True
    max_repair_attempts: int = 3
    test_command: str | None = None
    lint_command: str | None = None
    typecheck_command: str | None = None
    require_resolved_clarifications: bool = True
    allow_unrestricted_agent: bool = False
    review_agent: AgentName | None = None
    require_distinct_review_agent: bool = False
    enable_headroom: bool = True
    max_review_files: int = 15


class ArchitectureOption(BaseModel):
    name: str
    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    fit: str = ""


class ArchitectureDecision(BaseModel):
    @field_validator("id", "category")
    @classmethod
    def safe_path_part(cls, value):
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("Unsafe artifact identifier")
        return value

    id: str
    category: str
    question: str
    rationale: str = ""
    requirements: list[str] = Field(default_factory=list)
    options: list[ArchitectureOption] = Field(default_factory=list)
    recommendation: str | None = None
    recommendation_reason: str = ""
    selected: str | None = None
    selected_reason: str = ""
    status: DecisionStatus = DecisionStatus.open
    researched_at: str | None = None


class Requirement(BaseModel):
    id: str
    title: str
    statement: str
    kind: Literal["functional", "non_functional", "constraint"] = "functional"
    priority: Literal["must", "should", "could"] = "must"
    source: str = "PRD"
    acceptance_criteria: list[str] = Field(default_factory=list)
    status: ItemStatus = ItemStatus.pending


class Task(BaseModel):
    @field_validator("skills")
    @classmethod
    def safe_skills(cls, values):
        import re
        lifecycle = {
            "implement-task", "review-task", "architecture-design", "create-feature-spec",
            "reconcile", "spec-drift", "verify-feature",
        }
        cleaned = []
        for value in values:
            value = str(value).strip()
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", value):
                raise ValueError(f"Unsafe skill name: {value}")
            if value in lifecycle:
                raise ValueError(f"Lifecycle skill cannot be selected by a task: {value}")
            if value not in cleaned:
                cleaned.append(value)
        if len(cleaned) > 8:
            raise ValueError("A task may name at most 8 skills")
        return cleaned

    id: str
    feature_id: str
    title: str
    description: str
    implements: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    check_paths: list[str] = Field(default_factory=list)
    check_command: str | None = None
    skills: list[str] = Field(default_factory=list)
    working_set: list[str] = Field(default_factory=list)
    last_findings: list[dict[str, Any]] = Field(default_factory=list)
    status: ItemStatus = ItemStatus.pending
    attempts: int = 0
    evidence: list[str] = Field(default_factory=list)


class Feature(BaseModel):
    @field_validator("id")
    @classmethod
    def safe_id(cls, value):
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("Unsafe feature identifier")
        return value

    id: str
    name: str
    summary: str
    requirements: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    test_matrix: list[str] = Field(default_factory=list)
    api_contract: str = ""
    ux_contract: str = ""
    target_files: list[str] = Field(default_factory=list)
    status: ItemStatus = ItemStatus.pending


class ProductModel(BaseModel):
    name: str
    summary: str
    users: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class DesignDocument(BaseModel):
    """Agent-authored descriptive design; never grants change approval."""
    status: Literal["draft", "documented", "not_applicable"] = "draft"
    summary: str = ""
    sections: dict[str, str] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    not_applicable_reason: str = ""

    @field_validator("not_applicable_reason")
    @classmethod
    def clean_reason(cls, value):
        return value.strip()


class SpecBundle(BaseModel):
    product: ProductModel
    requirements: list[Requirement] = Field(default_factory=list)
    architecture_summary: str = ""
    design_documents: dict[str, DesignDocument] = Field(default_factory=dict)
    features: list[Feature] = Field(default_factory=list)
    test_strategy: list[str] = Field(default_factory=list)
    security_principles: list[str] = Field(default_factory=list)
    release_criteria: list[str] = Field(default_factory=list)


class ProjectState(BaseModel):
    schema_version: int = 1
    run_status: RunStatus = RunStatus.not_started
    current_feature: str | None = None
    current_task: str | None = None
    active_run_id: str | None = None
    initialized: bool = False
    artifacts_generated: bool = False
    last_checkpoint: str | None = None
    pause_requested: bool = False
    stop_requested: bool = False
    tokens_used: int = 0
    tokens_this_run: int = 0
    updated_at: str = Field(default_factory=utcnow)


class VerificationResult(BaseModel):
    id: str
    task_id: str | None = None
    feature_id: str | None = None
    kind: Literal["test", "lint", "typecheck", "review", "traceability", "manual"]
    status: Literal["pass", "fail", "warning", "pending"]
    command: str | None = None
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utcnow)


class ChangeRequest(BaseModel):
    id: str
    description: str
    classification: Literal[
        "implementation_defect", "spec_defect", "requirement_change", "architecture_change", "unknown"
    ] = "unknown"
    affected_requirements: list[str] = Field(default_factory=list)
    affected_features: list[str] = Field(default_factory=list)
    affected_tasks: list[str] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)
    requires_approval: bool = True
    approved: bool = False
    status: Literal["proposed", "approved", "applied", "rejected"] = "proposed"
    created_at: str = Field(default_factory=utcnow)


class AgentCapabilities(BaseModel):
    installed: bool = False
    authenticated: bool | None = None
    interactive: bool = True
    structured_output: bool = True
    streaming: bool = True
    resume: bool = False
    interrupt: bool = True
    write_access: bool = True
    command: str = ""
    version: str | None = None
    notes: list[str] = Field(default_factory=list)


class AgentEvent(BaseModel):
    type: str
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=utcnow)


class AgentResult(BaseModel):
    success: bool
    text: str = ""
    events: list[AgentEvent] = Field(default_factory=list)
    session_id: str | None = None
    raw: Any = None
    exit_code: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class RepoContext(BaseModel):
    root: Path
    prd_text: str
    existing_summary: str = ""
