from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:18]}"


def now_utc() -> datetime:
    return datetime.now(UTC)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("org"))
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("usr"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(40), default="operator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class BrowserTask(Base):
    __tablename__ = "browser_tasks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("task"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    latest_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class TaskVersion(Base):
    __tablename__ = "task_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ver"))
    task_id: Mapped[str] = mapped_column(ForeignKey("browser_tasks.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    immutable_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("task_id", "version", name="uq_task_version"),)


class BrowserRun(Base):
    __tablename__ = "browser_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("run"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("browser_tasks.id"), index=True)
    task_version_id: Mapped[str] = mapped_column(ForeignKey("task_versions.id"))
    idempotency_key: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", index=True)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    browser_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class BrowserStep(Base):
    __tablename__ = "browser_steps"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("step"))
    run_id: Mapped[str] = mapped_column(ForeignKey("browser_runs.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    step_id: Mapped[str] = mapped_column(String(120))
    action_type: Mapped[str] = mapped_column(String(50))
    target: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    screenshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dom_evidence: Mapped[str] = mapped_column(Text, default="")
    selector_used: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    failure_class: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("art"))
    run_id: Mapped[str] = mapped_column(ForeignKey("browser_runs.id"), index=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("browser_steps.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    path: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ckpt"))
    run_id: Mapped[str] = mapped_column(ForeignKey("browser_runs.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Assertion(Base):
    __tablename__ = "assertions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("asrt"))
    run_id: Mapped[str] = mapped_column(ForeignKey("browser_runs.id"), index=True)
    step_id: Mapped[str] = mapped_column(ForeignKey("browser_steps.id"))
    name: Mapped[str] = mapped_column(String(160))
    expected: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    actual: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Failure(Base):
    __tablename__ = "failures"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("fail"))
    run_id: Mapped[str] = mapped_column(ForeignKey("browser_runs.id"), index=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("browser_steps.id"), nullable=True)
    failure_class: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("audit"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("browser_runs.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
