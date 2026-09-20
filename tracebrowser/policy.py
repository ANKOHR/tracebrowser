from __future__ import annotations

from urllib.parse import urlparse

from .schemas import ActionDefinition, TaskPolicy


class PolicyError(Exception):
    failure_class = "BLOCKED_BY_POLICY"


def domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def validate_navigation(url: str, policy: TaskPolicy) -> None:
    if not domain_allowed(url, policy.allowed_domains):
        raise PolicyError(f"navigation blocked by domain policy: {url}")


def validate_action(action: ActionDefinition, policy: TaskPolicy) -> None:
    if action.type == "download" and not policy.downloads_allowed:
        raise PolicyError("downloads are disabled by task policy")
    external = bool(action.values.get("external_submission"))
    if external and not policy.external_submission_allowed:
        raise PolicyError("external submission is disabled by task policy")
    if action.type in policy.approval_required_actions and not action.requires_approval:
        raise PolicyError(f"action type requires explicit approval: {action.type}")
