from __future__ import annotations

import os

import pytest
from sqlalchemy import select

from tracebrowser.db import session_factory
from tracebrowser.models import AuditEvent, BrowserRun, BrowserStep
from tracebrowser.runtime import BrowserExecutor
from tracebrowser.schemas import ActionDefinition, LocatorSpec, TaskDefinition, TaskPolicy
from tracebrowser.service import serialize_run
from tracebrowser.showcases import broken_ui_task, crm_task, portal_task

from .conftest import create_test_run


def load_run(run_id: str):
    session = session_factory()()
    run = session.get(BrowserRun, run_id)
    payload = serialize_run(session, run)
    session.close()
    return payload


@pytest.mark.integration
def test_crm_pauses_and_resumes(executor: BrowserExecutor, demo_server: str):
    run_id = create_test_run(crm_task(demo_server), "runtime:crm")
    waiting = executor.execute(run_id)
    assert waiting.status == "WAITING_FOR_APPROVAL"
    assert waiting.current_step_index == 5
    assert waiting.output_data["approval_request"]["id"] == "submit-crm"
    finished = executor.execute(run_id, approve=True)
    assert finished.status == "SUCCESS"
    payload = load_run(run_id)
    assert payload["current_step_index"] == 8
    assert payload["output_data"]["assert-saved"]["matched"] == "Saved"


@pytest.mark.integration
def test_portal_extracts_table(executor: BrowserExecutor, demo_server: str):
    run_id = create_test_run(portal_task(demo_server), "runtime:portal")
    result = executor.execute(run_id)
    assert result.status == "SUCCESS"
    payload = load_run(run_id)
    assert payload["output_data"]["extract-orders"]["row_count"] == 4
    assert len(payload["steps"]) == 5


@pytest.mark.integration
def test_broken_ui_uses_explicit_fallback(executor: BrowserExecutor, demo_server: str):
    run_id = create_test_run(broken_ui_task(demo_server, version="v2"), "runtime:broken")
    result = executor.execute(run_id)
    payload = load_run(run_id)
    assert result.status == "SUCCESS"
    save_step = next(step for step in payload["steps"] if step["step_id"] == "save-with-fallback")
    assert save_step["selector_used"]["strategy"] == "role"


@pytest.mark.integration
def test_missing_selector_fails_with_trace_evidence(executor: BrowserExecutor, demo_server: str):
    definition = TaskDefinition(
        name="Missing selector",
        slug="missing-selector",
        start_url=f"{demo_server}/portal.html",
        actions=[
            ActionDefinition(id="open", type="navigate", value=f"{demo_server}/portal.html"),
            ActionDefinition(
                id="missing",
                type="click",
                target=LocatorSpec(value="#does-not-exist"),
                retries=1,
                timeout_ms=300,
            ),
        ],
    )
    run_id = create_test_run(definition, "runtime:missing")
    result = executor.execute(run_id)
    payload = load_run(run_id)
    assert result.status == "FAILED"
    assert payload["failures"][0]["failure_class"] == "SELECTOR_NOT_FOUND"
    failed_step = payload["steps"][-1]
    assert failed_step["retry_count"] == 1
    assert failed_step["screenshot_path"]


@pytest.mark.integration
def test_domain_policy_fails_before_navigation(executor: BrowserExecutor):
    definition = TaskDefinition(
        name="Blocked domain",
        slug="blocked-domain",
        start_url="https://example.com",
        actions=[ActionDefinition(id="open", type="navigate", value="https://example.com")],
    )
    run_id = create_test_run(definition, "runtime:blocked-domain")
    result = executor.execute(run_id)
    payload = load_run(run_id)
    assert result.status == "FAILED"
    assert payload["failures"][0]["failure_class"] == "BLOCKED_BY_POLICY"


@pytest.mark.integration
def test_action_limit_is_enforced(executor: BrowserExecutor, demo_server: str):
    definition = TaskDefinition(
        name="Action limit",
        slug="action-limit",
        start_url=f"{demo_server}/portal.html",
        policy=TaskPolicy(max_actions=1),
        actions=[
            ActionDefinition(id="open", type="navigate", value=f"{demo_server}/portal.html"),
            ActionDefinition(id="second", type="screenshot"),
        ],
    )
    run_id = create_test_run(definition, "runtime:action-limit")
    result = executor.execute(run_id)
    payload = load_run(run_id)
    assert result.status == "FAILED"
    assert payload["failures"][0]["failure_class"] == "BLOCKED_BY_POLICY"


@pytest.mark.integration
def test_page_limit_is_enforced(executor: BrowserExecutor, demo_server: str):
    definition = TaskDefinition(
        name="Page limit",
        slug="page-limit",
        start_url=f"{demo_server}/portal.html",
        policy=TaskPolicy(max_pages=1),
        actions=[
            ActionDefinition(id="open", type="navigate", value=f"{demo_server}/portal.html"),
            ActionDefinition(id="second", type="navigate", value=f"{demo_server}/crm.html"),
        ],
    )
    run_id = create_test_run(definition, "runtime:page-limit")
    result = executor.execute(run_id)
    payload = load_run(run_id)
    assert result.status == "FAILED"
    assert payload["failures"][0]["failure_class"] == "BLOCKED_BY_POLICY"


@pytest.mark.integration
def test_assertion_failure_is_not_success(executor: BrowserExecutor, demo_server: str):
    definition = TaskDefinition(
        name="Assertion failure",
        slug="assertion-failure",
        start_url=f"{demo_server}/portal.html",
        actions=[
            ActionDefinition(id="open", type="navigate", value=f"{demo_server}/portal.html"),
            ActionDefinition(
                id="wrong-assertion",
                type="assert_text",
                target=LocatorSpec(value="#row-count"),
                expected="99 rows",
                timeout_ms=500,
            ),
        ],
    )
    run_id = create_test_run(definition, "runtime:assertion")
    result = executor.execute(run_id)
    payload = load_run(run_id)
    assert result.status == "FAILED"
    assert payload["failures"][0]["failure_class"] == "ASSERTION_FAILED"


def test_browser_start_failure_is_recorded(executor, monkeypatch):
    monkeypatch.setenv(
        "PLAYWRIGHT_EXECUTABLE_PATH", os.path.join(os.getcwd(), "missing-browser.exe")
    )
    definition = TaskDefinition(
        name="Browser crash",
        slug="browser-crash",
        start_url="http://127.0.0.1:8765/portal.html",
        actions=[
            ActionDefinition(id="open", type="navigate", value="http://127.0.0.1:8765/portal.html")
        ],
    )
    run_id = create_test_run(definition, "runtime:browser-failure")
    result = executor.execute(run_id)
    payload = load_run(run_id)
    assert result.status == "FAILED"
    assert payload["failures"][0]["failure_class"] == "UNKNOWN"


def test_failure_records_are_immutable_trace_rows(executor, demo_server):
    definition = TaskDefinition(
        name="Failure row",
        slug="failure-row",
        start_url=f"{demo_server}/portal.html",
        actions=[ActionDefinition(id="open", type="navigate", value=f"{demo_server}/portal.html")],
    )
    run_id = create_test_run(definition, "runtime:immutable")
    executor.execute(run_id)
    session = session_factory()()
    assert session.scalar(select(BrowserStep).where(BrowserStep.run_id == run_id)) is not None
    assert session.scalar(select(AuditEvent).where(AuditEvent.run_id == run_id)) is not None
    session.close()
