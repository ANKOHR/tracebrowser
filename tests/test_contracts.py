from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from tracebrowser.policy import PolicyError, domain_allowed, validate_action, validate_navigation
from tracebrowser.schemas import ActionDefinition, LocatorSpec, TaskDefinition, TaskPolicy
from tracebrowser.screenshot_diff import compare_images
from tracebrowser.selectors import locator_for


@pytest.mark.parametrize(
    ("url", "allowed", "expected"),
    [
        ("https://example.test", ["example.test"], True),
        ("https://sub.example.test", ["example.test"], True),
        ("https://example.test.evil", ["example.test"], False),
        ("http://127.0.0.1:8000/a", ["127.0.0.1"], True),
        ("http://localhost/a", ["localhost"], True),
        ("file:///secret", ["localhost"], False),
        ("https://example.test", [], False),
        ("https://EXAMPLE.TEST", ["example.test"], True),
    ],
)
def test_domain_allowlist(url, allowed, expected):
    assert domain_allowed(url, allowed) is expected


@pytest.mark.parametrize(
    "strategy",
    ["css", "role", "text", "label", "testid"],
)
def test_locator_strategy_dispatch(strategy):
    class FakePage:
        def __getattr__(self, name):
            def call(*args, **kwargs):
                return name, args, kwargs

            return call

    spec = LocatorSpec(strategy=strategy, value="value", name="Name")
    result = locator_for(FakePage(), spec)
    assert result[0] in {"locator", "get_by_role", "get_by_text", "get_by_label", "get_by_test_id"}


@pytest.mark.parametrize(
    ("action", "message"),
    [
        (
            ActionDefinition(id="download", type="download", target=LocatorSpec(value="#download")),
            "downloads",
        ),
        (
            ActionDefinition(id="submit", type="click", values={"external_submission": True}),
            "external submission",
        ),
    ],
)
def test_policy_rejects_unsafe_actions(action, message):
    with pytest.raises(PolicyError, match=message):
        validate_action(action, TaskPolicy())


def test_policy_requires_explicit_approval_for_configured_action():
    action = ActionDefinition(id="submit", type="click")
    with pytest.raises(PolicyError, match="explicit approval"):
        validate_action(action, TaskPolicy(approval_required_actions=["click"]))


def test_policy_allows_approved_external_action():
    action = ActionDefinition(
        id="submit",
        type="click",
        values={"external_submission": True},
        requires_approval=True,
    )
    validate_action(action, TaskPolicy(external_submission_allowed=True))


def test_navigation_policy_rejects_external_domain():
    with pytest.raises(PolicyError, match="domain policy"):
        validate_navigation("https://example.com", TaskPolicy())


def test_task_definition_rejects_duplicate_action_ids():
    action = ActionDefinition(id="same", type="screenshot")
    with pytest.raises(ValidationError, match="unique"):
        TaskDefinition(
            name="Duplicate",
            slug="duplicate",
            start_url="http://localhost",
            actions=[action, action],
        )


def test_task_definition_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        LocatorSpec(value="#x", unexpected="blocked")


def test_task_policy_bounds_are_validated():
    with pytest.raises(ValidationError):
        TaskPolicy(max_actions=0)
    with pytest.raises(ValidationError):
        TaskPolicy(max_runtime_seconds=3601)


def test_task_slug_is_constrained():
    with pytest.raises(ValidationError):
        TaskDefinition(
            name="Bad slug",
            slug="Bad Slug",
            start_url="http://localhost",
            actions=[ActionDefinition(id="one", type="screenshot")],
        )


def test_screenshot_diff_identical_and_different(tmp_path: Path):
    from PIL import Image

    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    third = tmp_path / "third.png"
    Image.new("RGB", (30, 30), "white").save(first)
    Image.new("RGB", (30, 30), "white").save(second)
    Image.new("RGB", (30, 30), "black").save(third)
    assert compare_images(first, second)["score"] == 0
    assert compare_images(first, third)["score"] > 0.9


def test_screenshot_diff_reports_missing_file(tmp_path: Path):
    result = compare_images(tmp_path / "missing.png", tmp_path / "other.png")
    assert result["status"] == "unavailable"


def test_action_dump_is_json_safe():
    action = ActionDefinition(
        id="fill", type="fill", target=LocatorSpec(value="#name"), value="Acme"
    )
    assert action.model_dump(mode="json")["value"] == "Acme"
