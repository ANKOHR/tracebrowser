from __future__ import annotations

from sqlalchemy import select

from tracebrowser.db import session_factory
from tracebrowser.models import AuditEvent, BrowserRun, TaskVersion
from tracebrowser.schemas import ActionDefinition, TaskDefinition
from tracebrowser.service import create_run, create_task, definition_hash, serialize_run


def make_definition(name="Service test"):
    return TaskDefinition(
        name=name,
        slug=name.lower().replace(" ", "-"),
        start_url="http://127.0.0.1:8765/portal.html",
        actions=[ActionDefinition(id="screenshot", type="screenshot")],
    )


def test_definition_hash_is_stable():
    definition = make_definition()
    assert definition_hash(definition) == definition_hash(make_definition())


def test_task_version_is_immutable_by_hash():
    session = session_factory()()
    _, version = create_task(session, make_definition())
    stored = session.get(TaskVersion, version.id)
    assert stored.immutable_hash == definition_hash(make_definition())
    assert stored.version == 1
    session.close()


def test_run_submission_is_idempotent():
    session = session_factory()()
    task, version = create_task(session, make_definition("Idempotent"))
    first = create_run(session, task, version, "same-key")
    second = create_run(session, task, version, "same-key")
    assert first.id == second.id
    assert (
        session.scalar(select(BrowserRun).where(BrowserRun.idempotency_key == "same-key")).id
        == first.id
    )
    session.close()


def test_created_run_has_audit_event():
    session = session_factory()()
    task, version = create_task(session, make_definition("Audited"))
    run = create_run(session, task, version, "audit-key")
    event = session.scalar(select(AuditEvent).where(AuditEvent.run_id == run.id))
    assert event.event_type == "run.created"
    session.close()


def test_serialized_run_exposes_immutable_version_and_status():
    session = session_factory()()
    task, version = create_task(session, make_definition("Serialized"))
    run = create_run(session, task, version, "serialize-key")
    payload = serialize_run(session, run)
    assert payload["task_version_id"] == version.id
    assert payload["status"] == "PENDING"
    assert payload["steps"] == []
    session.close()
