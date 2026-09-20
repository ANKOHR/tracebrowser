from __future__ import annotations

from typing import Any

from .schemas import LocatorSpec


def locator_for(page: Any, spec: LocatorSpec) -> Any:
    if spec.strategy == "role":
        return page.get_by_role(spec.value, name=spec.name)
    if spec.strategy == "text":
        return page.get_by_text(spec.value)
    if spec.strategy == "label":
        return page.get_by_label(spec.value)
    if spec.strategy == "testid":
        return page.get_by_test_id(spec.value)
    return page.locator(spec.value)


def selector_dict(spec: LocatorSpec | None) -> dict[str, Any] | None:
    return spec.model_dump() if spec else None
