from __future__ import annotations

import json
import os
import shutil
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tracebrowser.db import configure_database, create_tables, session_factory
from tracebrowser.models import BrowserRun
from tracebrowser.runtime import BrowserExecutor
from tracebrowser.service import create_run, create_task, serialize_run
from tracebrowser.showcases import broken_ui_task, crm_task, portal_task

ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "demo_sites"
ARTIFACT_ROOT = ROOT / "apps" / "web" / "public" / "artifacts"


def serve_demo_site() -> ThreadingHTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(DEMO_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 8765), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def run_task(executor, definition, key: str, approval: bool = False):
    session = session_factory()()
    task, version = create_task(session, definition)
    run = create_run(session, task, version, key)
    session.close()
    first = executor.execute(run.id)
    approved = None
    approval_waited = first.status == "WAITING_FOR_APPROVAL"
    if approval and first.status == "WAITING_FOR_APPROVAL":
        approved = executor.execute(run.id, approve=True)
    final = approved or first
    read_session = session_factory()()
    payload = serialize_run(read_session, read_session.get(BrowserRun, final.id))
    read_session.close()
    payload["approval_waited"] = approval_waited
    return payload


def copy_named_screenshot(run: dict, name: str) -> None:
    screenshots = [step["screenshot_path"] for step in run["steps"] if step.get("screenshot_path")]
    if not screenshots:
        return
    source = ROOT / screenshots[-1]
    destination = ARTIFACT_ROOT / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    os.environ.setdefault(
        "PLAYWRIGHT_EXECUTABLE_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    )
    database = ROOT / "reports" / "showcase.db"
    database.parent.mkdir(parents=True, exist_ok=True)
    if database.exists():
        database.unlink()
    configure_database(f"sqlite:///{database}")
    create_tables()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    server = serve_demo_site()
    executor = BrowserExecutor(session_factory(), Path("apps/web/public/artifacts"))
    try:
        crm = run_task(executor, crm_task(), "showcase:crm:v1", approval=True)
        portal = run_task(executor, portal_task(), "showcase:portal:v1")
        broken = run_task(executor, broken_ui_task(version="v2"), "showcase:broken:v2")
        copy_named_screenshot(crm, "crm-success.png")
        copy_named_screenshot(portal, "portal-extraction.png")
        copy_named_screenshot(broken, "broken-ui-recovered.png")
        output = {
            "crm": crm,
            "portal": portal,
            "broken_ui": broken,
            "verified_fixture": "local synthetic demo sites only",
        }
        (ROOT / "reports" / "showcase-results.json").write_text(
            json.dumps(output, indent=2), encoding="utf-8"
        )
        (ARTIFACT_ROOT / "showcase-results.json").write_text(
            json.dumps(output, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {key: value["status"] for key, value in output.items() if isinstance(value, dict)},
                indent=2,
            )
        )
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
