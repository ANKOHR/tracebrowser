# Architecture

TraceBrowser separates task definitions, execution state and evidence so a run can be inspected without reconstructing browser history from logs.

```text
Next.js dashboard
        │
     FastAPI
        │
 SQLAlchemy models ─── SQLite fallback / PostgreSQL-ready URL
        │
 BrowserExecutor ─── Playwright ─── controlled or explicitly allowed site
        │
  screenshots · DOM evidence · request log · assertions · audit events
        │
 optional Dramatiq boundary (not required for local verification)
```

`BrowserTask` points to an immutable `TaskVersion`. A `BrowserRun` references the exact version used for execution. Each action produces a `BrowserStep`; screenshots and downloads are separate `Artifact` rows. `Checkpoint`, `Assertion`, `Failure` and `AuditEvent` rows make recovery and review explicit.

The task definition is Pydantic-validated before it enters the runtime. A selector can use CSS, role, text, label or test ID. Fallbacks are authored in the task definition, so a successful fallback is visible in the trace rather than attributed to invisible selector healing.

The current dashboard is static-first and reads committed showcase artifacts. The API is separately runnable and exposes task/run submission, approval, replay and artifact routes.
