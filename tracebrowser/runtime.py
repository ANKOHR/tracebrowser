from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .models import (
    Artifact,
    Assertion,
    AuditEvent,
    BrowserRun,
    BrowserStep,
    Checkpoint,
    Failure,
    TaskVersion,
)
from .policy import PolicyError, validate_action, validate_navigation
from .schemas import ActionDefinition, LocatorSpec, TaskDefinition
from .selectors import locator_for, selector_dict


class ExecutionFailure(Exception):
    def __init__(self, failure_class: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.failure_class = failure_class
        self.retryable = retryable


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


class BrowserExecutor:
    def __init__(self, session_factory, artifact_root: str | Path = "artifacts"):
        self.session_factory = session_factory
        self.artifact_root = Path(artifact_root)

    def execute(self, run_id: str, approve: bool = False) -> BrowserRun:
        session = self.session_factory()
        run = session.get(BrowserRun, run_id)
        if run is None:
            session.close()
            raise KeyError(run_id)
        version = session.get(TaskVersion, run.task_version_id)
        if version is None:
            session.close()
            raise KeyError(run.task_version_id)
        definition = TaskDefinition.model_validate(version.definition)
        if run.status == "SUCCESS" and not approve:
            session.close()
            return run
        if approve:
            run.approved = True
        run.status = "RUNNING"
        run.started_at = run.started_at or _utcnow()
        run.browser_metadata = {
            "engine": "Playwright",
            "headless": True,
            "executable": os.getenv("PLAYWRIGHT_EXECUTABLE_PATH", "system Chromium/Chrome"),
        }
        session.commit()
        browser = None
        context = None
        page = None
        request_log: list[dict[str, Any]] = []
        started = time.perf_counter()
        runtime_state: dict[str, Any] = {"visited_pages": set()}
        try:
            with sync_playwright() as playwright:
                launch_kwargs: dict[str, Any] = {"headless": True}
                executable = os.getenv("PLAYWRIGHT_EXECUTABLE_PATH")
                if executable:
                    launch_kwargs["executable_path"] = executable
                try:
                    browser = playwright.chromium.launch(**launch_kwargs)
                    context = browser.new_context(
                        accept_downloads=definition.policy.downloads_allowed
                    )
                    page = context.new_page()
                except Exception as exc:
                    raise ExecutionFailure(
                        "UNKNOWN", f"browser process failed to start: {exc}"
                    ) from exc

                page.on(
                    "request",
                    lambda request: (
                        request_log.append({"method": request.method, "url": request.url})
                        if len(request_log) < 100
                        else None
                    ),
                )
                if run.current_step_index > 0:
                    self._restore_checkpoint(
                        page,
                        context,
                        definition,
                        run,
                        session,
                        runtime_state,
                    )
                for index in range(run.current_step_index, len(definition.actions)):
                    action = definition.actions[index]
                    if time.perf_counter() - started > definition.policy.max_runtime_seconds:
                        raise ExecutionFailure(
                            "BLOCKED_BY_POLICY",
                            "maximum runtime exceeded",
                        )
                    if index >= definition.policy.max_actions:
                        raise ExecutionFailure("BLOCKED_BY_POLICY", "maximum action count exceeded")
                    if action.requires_approval and not run.approved:
                        run.status = "WAITING_FOR_APPROVAL"
                        run.current_step_index = index
                        run.output_data = {
                            **run.output_data,
                            "approval_request": action.model_dump(),
                            "request_log": request_log[-20:],
                        }
                        session.add(
                            AuditEvent(
                                organization_id=run.organization_id,
                                run_id=run.id,
                                event_type="approval.requested",
                                payload={"step_id": action.id},
                            )
                        )
                        session.commit()
                        return run
                    step = BrowserStep(
                        run_id=run.id,
                        step_index=index,
                        step_id=action.id,
                        action_type=action.type,
                        target=action.target.model_dump() if action.target else None,
                        inputs={
                            "value": action.value,
                            "values": action.values,
                            "expected": action.expected,
                        },
                        status="RUNNING",
                    )
                    session.add(step)
                    session.flush()
                    action_started = time.perf_counter()
                    try:
                        output, used_selector, retry_count = self._with_retries(
                            page, context, action, definition, run, session, runtime_state
                        )
                        step.output = _json_safe(output) or {}
                        step.selector_used = selector_dict(used_selector)
                        step.retry_count = retry_count
                        step.status = "SUCCESS"
                        step.dom_evidence = self._bounded_dom(page)
                        try:
                            step.screenshot_path = self._capture(
                                page, run.id, action.id, session, step.id
                            )
                        except Exception as exc:
                            raise ExecutionFailure(
                                "UNKNOWN", f"evidence capture failed: {exc}"
                            ) from exc
                        step.duration_ms = int((time.perf_counter() - action_started) * 1000)
                        if action.type.startswith("assert_"):
                            session.add(
                                Assertion(
                                    run_id=run.id,
                                    step_id=step.id,
                                    name=action.id,
                                    expected={"value": action.expected},
                                    actual=step.output,
                                    passed=True,
                                )
                            )
                        if action.checkpoint or action.type == "checkpoint":
                            session.add(
                                Checkpoint(
                                    run_id=run.id,
                                    step_index=index + 1,
                                    state={
                                        "url": page.url,
                                        "output": step.output,
                                        "request_log": request_log[-20:],
                                    },
                                )
                            )
                        run.current_step_index = index + 1
                        run.output_data = {
                            **run.output_data,
                            action.id: step.output,
                            "request_log": request_log[-20:],
                        }
                        session.add(
                            AuditEvent(
                                organization_id=run.organization_id,
                                run_id=run.id,
                                event_type="step.succeeded",
                                payload={
                                    "step_id": action.id,
                                    "action_type": action.type,
                                    "duration_ms": step.duration_ms,
                                },
                            )
                        )
                        session.commit()
                    except ExecutionFailure as exc:
                        step.status = "FAILED"
                        step.failure_class = exc.failure_class
                        step.error_message = str(exc)
                        step.retry_count = getattr(exc, "retry_count", 0)
                        step.duration_ms = int((time.perf_counter() - action_started) * 1000)
                        step.dom_evidence = self._bounded_dom(page)
                        step.screenshot_path = self._capture_safely(
                            page, run.id, f"{action.id}-failure", session, step.id
                        )
                        session.add(
                            Failure(
                                run_id=run.id,
                                step_id=step.id,
                                failure_class=exc.failure_class,
                                message=str(exc),
                                evidence={"url": page.url, "screenshot": step.screenshot_path},
                                retryable=exc.retryable,
                            )
                        )
                        run.status = "FAILED"
                        run.completed_at = _utcnow()
                        run.output_data = {**run.output_data, "request_log": request_log[-20:]}
                        session.add(
                            AuditEvent(
                                organization_id=run.organization_id,
                                run_id=run.id,
                                event_type="run.failed",
                                payload={"step_id": action.id, "failure_class": exc.failure_class},
                            )
                        )
                        session.commit()
                        return run
                run.status = "SUCCESS"
                run.completed_at = _utcnow()
                run.output_data = {
                    **run.output_data,
                    "runtime_ms": int((time.perf_counter() - started) * 1000),
                    "request_log": request_log[-20:],
                }
                session.add(
                    AuditEvent(
                        organization_id=run.organization_id,
                        run_id=run.id,
                        event_type="run.completed",
                        payload={"steps": len(definition.actions)},
                    )
                )
                session.commit()
                return run
        except ExecutionFailure as exc:
            run.status = "FAILED"
            run.completed_at = _utcnow()
            session.add(
                Failure(
                    run_id=run.id,
                    failure_class=exc.failure_class,
                    message=str(exc),
                    evidence={"request_log": request_log[-20:]},
                    retryable=exc.retryable,
                )
            )
            session.add(
                AuditEvent(
                    organization_id=run.organization_id,
                    run_id=run.id,
                    event_type="run.failed",
                    payload={"failure_class": exc.failure_class},
                )
            )
            session.commit()
            return run
        except Exception as exc:
            run.status = "FAILED"
            run.completed_at = _utcnow()
            session.add(
                Failure(
                    run_id=run.id,
                    failure_class="UNKNOWN",
                    message=f"unhandled runtime error: {exc}",
                    evidence={"request_log": request_log[-20:]},
                    retryable=False,
                )
            )
            session.add(
                AuditEvent(
                    organization_id=run.organization_id,
                    run_id=run.id,
                    event_type="run.failed",
                    payload={"failure_class": "UNKNOWN"},
                )
            )
            session.commit()
            return run
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            session.close()

    def _with_retries(
        self,
        page,
        context,
        action: ActionDefinition,
        definition: TaskDefinition,
        run,
        session,
        runtime_state,
    ):
        last: ExecutionFailure | None = None
        for attempt in range(action.retries + 1):
            try:
                output, used = self._perform(
                    page, context, action, definition, run, session, runtime_state
                )
                return output, used, attempt
            except ExecutionFailure as exc:
                last = exc
                if attempt >= action.retries or not exc.retryable:
                    exc.retry_count = attempt
                    raise
                time.sleep(min(0.2 * (2**attempt), 1.0))
        assert last is not None
        last.retry_count = action.retries
        raise last

    def _perform(self, page, context, action, definition, run, session, runtime_state):
        try:
            validate_action(action, definition.policy)
            timeout = action.timeout_ms
            used: LocatorSpec | None = None
            if action.type == "navigate":
                url = action.value or str(action.values.get("url") or definition.start_url)
                validate_navigation(url, definition.policy)
                if (
                    url not in runtime_state["visited_pages"]
                    and len(runtime_state["visited_pages"]) >= definition.policy.max_pages
                ):
                    raise ExecutionFailure("BLOCKED_BY_POLICY", "maximum page count exceeded")
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                validate_navigation(page.url, definition.policy)
                runtime_state["visited_pages"].add(page.url)
                gate = self._detect_page_gate(page)
                if gate is not None:
                    raise ExecutionFailure(gate[0], gate[1])
                return {"url": page.url, "title": page.title()}, None
            if action.type == "wait":
                if action.target:
                    locator, used = self._resolve(page, action, timeout)
                    locator.wait_for(state="visible", timeout=timeout)
                else:
                    page.wait_for_timeout(min(timeout, 2000))
                return {"waited_ms": min(timeout, 2000)}, used
            if action.type in {"screenshot", "checkpoint"}:
                return {"url": page.url, action.type: True}, None
            locator, used = self._resolve(page, action, timeout)
            if action.type == "click":
                locator.click(timeout=timeout)
                return {"clicked": True, "url": page.url}, used
            if action.type == "fill":
                locator.fill(action.value or str(action.values.get("value", "")), timeout=timeout)
                return {"filled": True}, used
            if action.type == "select":
                value = action.value or str(action.values.get("value", ""))
                locator.select_option(value=value, timeout=timeout)
                return {"selected": value}, used
            if action.type == "extract_text":
                return {"text": locator.inner_text(timeout=timeout)[:5000]}, used
            if action.type == "extract_table":
                rows = locator.locator("tr").all_inner_texts()
                normalized = [
                    [cell.strip() for cell in re.split(r"\s{2,}|\n", row) if cell.strip()]
                    for row in rows
                ]
                return {"rows": normalized, "row_count": len(normalized)}, used
            if action.type == "assert_text":
                actual = locator.inner_text(timeout=timeout)
                expected = str(action.expected or action.values.get("text", ""))
                if expected not in actual:
                    raise ExecutionFailure(
                        "ASSERTION_FAILED", f"expected text not found: {expected}"
                    )
                return {"text": actual, "matched": expected}, used
            if action.type == "assert_element":
                if locator.count() < 1:
                    raise ExecutionFailure("ASSERTION_FAILED", "expected element was not present")
                return {"present": True}, used
            if action.type == "assert_url":
                expected = str(action.expected or action.values.get("url", ""))
                if expected not in page.url:
                    raise ExecutionFailure(
                        "ASSERTION_FAILED", f"expected URL fragment not found: {expected}"
                    )
                return {"url": page.url, "matched": expected}, used
            if action.type == "download":
                with page.expect_download(timeout=timeout) as info:
                    locator.click(timeout=timeout)
                download = info.value
                destination = (
                    self.artifact_root / run.id / (download.suggested_filename or "download.bin")
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                download.save_as(str(destination))
                session.add(
                    Artifact(
                        run_id=run.id,
                        kind="download",
                        path=str(destination),
                        content_type="application/octet-stream",
                        metadata_json={"filename": download.suggested_filename},
                    )
                )
                return {"path": str(destination), "filename": download.suggested_filename}, used
            raise ExecutionFailure("UNKNOWN", f"unsupported action type: {action.type}")
        except PolicyError as exc:
            raise ExecutionFailure("BLOCKED_BY_POLICY", str(exc)) from exc
        except ExecutionFailure:
            raise
        except PlaywrightTimeoutError as exc:
            failure_class = "SELECTOR_NOT_FOUND" if action.target else "PAGE_TIMEOUT"
            raise ExecutionFailure(failure_class, str(exc), retryable=True) from exc
        except AssertionError as exc:
            raise ExecutionFailure("ASSERTION_FAILED", str(exc)) from exc
        except PlaywrightError as exc:
            message = str(exc)
            failure_class = (
                "DOWNLOAD_FAILED"
                if action.type == "download"
                else "NAVIGATION_ERROR"
                if action.type == "navigate"
                else "SELECTOR_NOT_FOUND"
            )
            raise ExecutionFailure(failure_class, message, retryable=True) from exc
        except Exception as exc:
            raise ExecutionFailure("UNKNOWN", str(exc)) from exc

    def _restore_checkpoint(self, page, context, definition, run, session, runtime_state) -> None:
        """Rebuild deterministic page state before resuming a paused run.

        Browser processes are intentionally disposable. A resume therefore replays
        the completed, non-approval prefix without creating new trace steps. This
        is safe for the showcase tasks because side effects are approval-gated.
        """
        resume_url = definition.start_url
        for value in run.output_data.values():
            if isinstance(value, dict) and isinstance(value.get("url"), str):
                resume_url = value["url"]
        bootstrap = ActionDefinition(
            id="__resume_navigate__",
            type="navigate",
            value=resume_url,
            timeout_ms=5000,
        )
        self._perform(page, context, bootstrap, definition, run, session, runtime_state)
        for action in definition.actions[: run.current_step_index]:
            if action.requires_approval:
                continue
            self._with_retries(page, context, action, definition, run, session, runtime_state)

    def _resolve(self, page, action, timeout):
        specs = ([action.target] if action.target else []) + list(action.fallbacks)
        if not specs:
            raise ExecutionFailure("SELECTOR_NOT_FOUND", f"action {action.id} has no target")
        last_error = None
        for spec in specs:
            try:
                locator = locator_for(page, spec)
                locator.wait_for(state="attached", timeout=min(timeout, 800))
                if locator.count() < 1:
                    raise ValueError("no matching element")
                return locator, spec
            except Exception as exc:
                last_error = exc
        raise ExecutionFailure(
            "SELECTOR_NOT_FOUND",
            f"no selector matched for {action.id}: {last_error}",
            retryable=True,
        )

    def _bounded_dom(self, page) -> str:
        try:
            return page.content()[:12000]
        except Exception:
            return "<dom unavailable>"

    def _detect_page_gate(self, page) -> tuple[str, str] | None:
        """Stop transparently when a controlled run encounters an access gate."""
        try:
            text = page.locator("body").inner_text(timeout=500).lower()
            url = page.url.lower()
        except Exception:
            return None
        if any(
            token in text or token in url for token in ("captcha", "robot check", "access denied")
        ):
            return "BLOCKED_BY_POLICY", "page presented an access or anti-automation block"
        if any(
            token in text or token in url for token in ("authentication required", "login required")
        ):
            return "AUTH_REQUIRED", "page requires authentication"
        return None

    def _capture_safely(self, page, run_id, name, session, step_id) -> str | None:
        try:
            return self._capture(page, run_id, name, session, step_id)
        except Exception:
            return None

    def _capture(self, page, run_id, name, session, step_id) -> str:
        destination = self.artifact_root / run_id / f"{name}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(destination), full_page=False)
        relative = str(destination).replace("\\", "/")
        session.add(
            Artifact(
                run_id=run_id,
                step_id=step_id,
                kind="screenshot",
                path=relative,
                content_type="image/png",
                metadata_json={"step": name},
            )
        )
        return relative
