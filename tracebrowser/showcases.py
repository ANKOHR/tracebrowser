from __future__ import annotations

from .schemas import ActionDefinition, LocatorSpec, TaskDefinition, TaskPolicy


def css(value: str) -> LocatorSpec:
    return LocatorSpec(strategy="css", value=value)


def crm_task(base_url: str = "http://127.0.0.1:8765") -> TaskDefinition:
    return TaskDefinition(
        name="CRM data entry",
        slug="crm-data-entry",
        description="Find a synthetic customer, update a status and pause before submission.",
        start_url=f"{base_url}/crm.html",
        policy=TaskPolicy(
            allowed_domains=["127.0.0.1", "localhost"], external_submission_allowed=True
        ),
        actions=[
            ActionDefinition(id="open-crm", type="navigate", value=f"{base_url}/crm.html"),
            ActionDefinition(
                id="search-customer", type="fill", target=css("#customer-search"), value="Acme Ltd"
            ),
            ActionDefinition(
                id="run-search", type="click", target=css("[data-testid='search-customer']")
            ),
            ActionDefinition(
                id="assert-customer",
                type="assert_text",
                target=css("#customer-card"),
                expected="Acme Ltd",
            ),
            ActionDefinition(
                id="fill-status",
                type="select",
                target=css("#status"),
                value="qualified",
                checkpoint=True,
            ),
            ActionDefinition(
                id="submit-crm",
                type="click",
                target=css("[data-testid='submit-crm']"),
                values={"external_submission": True},
                requires_approval=True,
            ),
            ActionDefinition(
                id="assert-saved", type="assert_text", target=css("#success"), expected="Saved"
            ),
            ActionDefinition(id="complete-screenshot", type="screenshot"),
        ],
    )


def portal_task(base_url: str = "http://127.0.0.1:8765") -> TaskDefinition:
    return TaskDefinition(
        name="Portal table extraction",
        slug="portal-table-extraction",
        description="Navigate a synthetic portal, extract a table and verify its row count.",
        start_url=f"{base_url}/portal.html",
        actions=[
            ActionDefinition(id="open-portal", type="navigate", value=f"{base_url}/portal.html"),
            ActionDefinition(id="wait-for-table", type="wait", target=css("#orders")),
            ActionDefinition(
                id="extract-orders", type="extract_table", target=css("#orders"), checkpoint=True
            ),
            ActionDefinition(
                id="assert-row-count",
                type="assert_text",
                target=css("#row-count"),
                expected="3 rows",
            ),
            ActionDefinition(id="portal-screenshot", type="screenshot"),
        ],
    )


def broken_ui_task(base_url: str = "http://127.0.0.1:8765", version: str = "v2") -> TaskDefinition:
    return TaskDefinition(
        name="Broken UI recovery",
        slug=f"broken-ui-{version}",
        description="Use an explicit fallback when a known demo selector changes.",
        start_url=f"{base_url}/broken-{version}.html",
        actions=[
            ActionDefinition(
                id="open-broken-ui", type="navigate", value=f"{base_url}/broken-{version}.html"
            ),
            ActionDefinition(
                id="save-with-fallback",
                type="click",
                target=LocatorSpec(strategy="testid", value="submit-v1"),
                fallbacks=[LocatorSpec(strategy="role", value="button", name="Save changes")],
            ),
            ActionDefinition(
                id="assert-recovered", type="assert_text", target=css("#result"), expected="Saved"
            ),
            ActionDefinition(id="broken-screenshot", type="screenshot"),
        ],
    )
