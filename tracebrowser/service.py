from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    AuditEvent,
    BrowserRun,
    BrowserStep,
    BrowserTask,
    Failure,
    Organization,
    TaskVersion,
    User,
)
from .schemas import TaskDefinition


def definition_hash(definition: TaskDefinition) -> str:
    encoded = json.dumps(definition.model_dump(mode="json"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def ensure_organization(session: Session, organization_id: str = "org_demo") -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None:
        organization = Organization(id=organization_id, name="TraceBrowser Demo Organization")
        session.add(organization)
        session.flush()
        session.add(
            User(organization_id=organization.id, email="operator@example.test", role="operator")
        )
    return organization


def create_task(
    session: Session, definition: TaskDefinition, organization_id: str = "org_demo"
) -> tuple[BrowserTask, TaskVersion]:
    ensure_organization(session, organization_id)
    task = BrowserTask(
        organization_id=organization_id,
        name=definition.name,
        slug=definition.slug,
        description=definition.description,
    )
    session.add(task)
    session.flush()
    version = TaskVersion(
        task_id=task.id,
        version=1,
        definition=definition.model_dump(mode="json"),
        immutable_hash=definition_hash(definition),
    )
    session.add(version)
    session.flush()
    task.latest_version_id = version.id
    session.commit()
    return task, version


def create_run(
    session: Session,
    task: BrowserTask,
    version: TaskVersion,
    idempotency_key: str,
    input_data: dict[str, Any] | None = None,
) -> BrowserRun:
    existing = session.scalar(
        select(BrowserRun).where(BrowserRun.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing
    run = BrowserRun(
        organization_id=task.organization_id,
        task_id=task.id,
        task_version_id=version.id,
        idempotency_key=idempotency_key,
        input_data=input_data or {},
    )
    session.add(run)
    session.flush()
    session.add(
        AuditEvent(
            organization_id=task.organization_id,
            run_id=run.id,
            event_type="run.created",
            payload={"idempotency_key": idempotency_key},
        )
    )
    session.commit()
    return run


def serialize_run(session: Session, run: BrowserRun) -> dict[str, Any]:
    steps = session.scalars(
        select(BrowserStep).where(BrowserStep.run_id == run.id).order_by(BrowserStep.step_index)
    ).all()
    failures = session.scalars(
        select(Failure).where(Failure.run_id == run.id).order_by(Failure.created_at)
    ).all()
    return {
        "id": run.id,
        "status": run.status,
        "task_id": run.task_id,
        "task_version_id": run.task_version_id,
        "idempotency_key": run.idempotency_key,
        "current_step_index": run.current_step_index,
        "approved": run.approved,
        "input_data": run.input_data,
        "output_data": run.output_data,
        "browser_metadata": run.browser_metadata,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "steps": [
            {
                "id": step.id,
                "step_id": step.step_id,
                "action_type": step.action_type,
                "target": step.target,
                "inputs": step.inputs,
                "output": step.output,
                "status": step.status,
                "duration_ms": step.duration_ms,
                "retry_count": step.retry_count,
                "screenshot_path": step.screenshot_path,
                "dom_evidence": step.dom_evidence,
                "selector_used": step.selector_used,
                "failure_class": step.failure_class,
                "error_message": step.error_message,
            }
            for step in steps
        ],
        "failures": [
            {
                "failure_class": failure.failure_class,
                "message": failure.message,
                "evidence": failure.evidence,
                "retryable": failure.retryable,
            }
            for failure in failures
        ],
    }
