from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ActionType = Literal[
    "navigate",
    "click",
    "fill",
    "select",
    "wait",
    "extract_text",
    "extract_table",
    "download",
    "assert_text",
    "assert_url",
    "assert_element",
    "screenshot",
    "checkpoint",
]


class LocatorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: Literal["css", "role", "text", "label", "testid"] = "css"
    value: str
    name: str | None = None


class TaskPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_domains: list[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost"])
    max_pages: int = Field(default=10, ge=1, le=100)
    max_runtime_seconds: int = Field(default=300, ge=1, le=3600)
    max_actions: int = Field(default=50, ge=1, le=500)
    downloads_allowed: bool = False
    external_submission_allowed: bool = False
    approval_required_actions: list[str] = Field(default_factory=list)


class ActionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=120)
    type: ActionType
    target: LocatorSpec | None = None
    fallbacks: list[LocatorSpec] = Field(default_factory=list)
    value: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    expected: Any | None = None
    timeout_ms: int = Field(default=5000, ge=100, le=60000)
    retries: int = Field(default=0, ge=0, le=3)
    requires_approval: bool = False
    checkpoint: bool = False


class TaskDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    description: str = ""
    start_url: str
    actions: list[ActionDefinition] = Field(min_length=1, max_length=500)
    policy: TaskPolicy = Field(default_factory=TaskPolicy)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("actions")
    @classmethod
    def unique_action_ids(cls, value: list[ActionDefinition]) -> list[ActionDefinition]:
        ids = [action.id for action in value]
        if len(ids) != len(set(ids)):
            raise ValueError("action IDs must be unique")
        return value


class TaskCreateRequest(BaseModel):
    organization_id: str = "org_demo"
    definition: TaskDefinition


class RunCreateRequest(BaseModel):
    task_id: str
    task_version_id: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=220)
    input_data: dict[str, Any] = Field(default_factory=dict)
    execute: bool = True


class RunResponse(BaseModel):
    id: str
    status: str
    task_id: str
    task_version_id: str
    current_step_index: int
    output_data: dict[str, Any]
