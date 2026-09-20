from __future__ import annotations

import os
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tracebrowser.db import configure_database, create_tables, session_factory
from tracebrowser.runtime import BrowserExecutor
from tracebrowser.service import create_run, create_task

ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "demo_sites"


@pytest.fixture(autouse=True)
def isolated_database(tmp_path):
    configure_database(f"sqlite:///{tmp_path / 'tracebrowser-test.db'}")
    create_tables()
    yield


@pytest.fixture
def artifact_root(tmp_path):
    return tmp_path / "artifacts"


@pytest.fixture
def demo_server():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    handler = partial(SimpleHTTPRequestHandler, directory=str(DEMO_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.fixture
def browser_executable(monkeypatch):
    configured = os.getenv("PLAYWRIGHT_EXECUTABLE_PATH")
    candidates = [
        configured,
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    executable = next(
        (candidate for candidate in candidates if candidate and Path(candidate).exists()), None
    )
    if executable:
        monkeypatch.setenv("PLAYWRIGHT_EXECUTABLE_PATH", executable)
    return executable


@pytest.fixture
def executor(artifact_root, browser_executable):
    return BrowserExecutor(session_factory(), artifact_root)


def create_test_run(definition, key: str):
    session = session_factory()()
    task, version = create_task(session, definition)
    run = create_run(session, task, version, key)
    session.close()
    return run.id
