from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import create_tables, session_factory
from .models import BrowserRun, BrowserTask, TaskVersion
from .runtime import BrowserExecutor
from .schemas import RunCreateRequest, TaskCreateRequest
from .service import create_run, create_task, ensure_organization, serialize_run

ARTIFACT_ROOT = Path(os.getenv("TRACEBROWSER_ARTIFACT_ROOT", "artifacts"))
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
app = FastAPI(
    title="TraceBrowser API",
    version="0.1.0",
    description="Reliable browser automation with replayable execution traces.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACT_ROOT)), name="artifacts")


def get_session():
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()


@app.on_event("startup")
def startup() -> None:
    create_tables()


@app.get("/health")
def health():
    return {"status": "ok", "service": "tracebrowser-api", "storage": "sqlalchemy"}


@app.post("/api/tasks")
def post_task(request: TaskCreateRequest, session: Session = Depends(get_session)):
    task, version = create_task(session, request.definition, request.organization_id)
    return {"task_id": task.id, "task_version_id": version.id, "version": version.version}


@app.get("/api/tasks")
def list_tasks(session: Session = Depends(get_session)):
    ensure_organization(session)
    tasks = session.scalars(select(BrowserTask).order_by(BrowserTask.created_at.desc())).all()
    return [
        {
            "id": task.id,
            "name": task.name,
            "slug": task.slug,
            "latest_version_id": task.latest_version_id,
        }
        for task in tasks
    ]


@app.post("/api/runs")
def post_run(request: RunCreateRequest, session: Session = Depends(get_session)):
    task = session.get(BrowserTask, request.task_id)
    if task is None:
        raise HTTPException(404, "task not found")
    version = session.get(TaskVersion, request.task_version_id or task.latest_version_id)
    if version is None:
        raise HTTPException(404, "task version not found")
    run = create_run(session, task, version, request.idempotency_key, request.input_data)
    if request.execute and run.status not in {"SUCCESS", "FAILED"}:
        BrowserExecutor(session_factory(), ARTIFACT_ROOT).execute(run.id)
        session.expire_all()
        run = session.get(BrowserRun, run.id)
    return serialize_run(session, run)


@app.get("/api/runs")
def list_runs(session: Session = Depends(get_session)):
    runs = session.scalars(
        select(BrowserRun).order_by(BrowserRun.created_at.desc()).limit(100)
    ).all()
    return [
        {
            "id": run.id,
            "task_id": run.task_id,
            "status": run.status,
            "current_step_index": run.current_step_index,
            "created_at": run.created_at.isoformat(),
        }
        for run in runs
    ]


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)):
    run = session.get(BrowserRun, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return serialize_run(session, run)


@app.post("/api/runs/{run_id}/approve")
def approve_run(run_id: str, session: Session = Depends(get_session)):
    run = session.get(BrowserRun, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    BrowserExecutor(session_factory(), ARTIFACT_ROOT).execute(run.id, approve=True)
    session.expire_all()
    return serialize_run(session, session.get(BrowserRun, run.id))


@app.post("/api/runs/{run_id}/replay")
def replay_run(run_id: str, session: Session = Depends(get_session)):
    run = session.get(BrowserRun, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    task = session.get(BrowserTask, run.task_id)
    version = session.get(TaskVersion, run.task_version_id)
    replay = create_run(
        session, task, version, f"replay:{run.id}:{run.created_at.timestamp()}", run.input_data
    )
    BrowserExecutor(session_factory(), ARTIFACT_ROOT).execute(replay.id, approve=run.approved)
    session.expire_all()
    return serialize_run(session, session.get(BrowserRun, replay.id))
