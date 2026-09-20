# Reliability model

TraceBrowser treats a browser run as a bounded state machine, not as an unobserved script.

## Controls

- Domain allowlist checked before navigation and after redirects.
- Maximum actions, pages and runtime per task policy.
- Per-action timeout and bounded retry count.
- Explicit assertion actions that produce `ASSERTION_FAILED` rather than a false success.
- Screenshot and bounded DOM capture on successful and failed steps where the browser is still available.
- Idempotency key on run submission.
- Immutable task-version hash attached to each run.
- Checkpoint rows and deterministic prefix replay when a disposable browser resumes.
- `WAITING_FOR_APPROVAL` before configured external submission actions.
- Explicit failure taxonomy: `SELECTOR_NOT_FOUND`, `PAGE_TIMEOUT`, `ASSERTION_FAILED`, `AUTH_REQUIRED`, `NAVIGATION_ERROR`, `DOWNLOAD_FAILED`, `RATE_LIMITED`, `BLOCKED_BY_POLICY` and `UNKNOWN`.

## Recovery semantics

Browser processes are disposable. When a run resumes after approval, the runtime rebuilds the completed deterministic prefix in a fresh page and then continues at the stored step index. Replay creates a new run with the same immutable task version and a new idempotency key.

The controlled broken-UI fixture demonstrates the boundary: a stale test ID fails, then an explicitly authored role fallback succeeds. TraceBrowser does not claim arbitrary selector repair.

## Measurement

`tracebrowser benchmark` runs 50 synthetic task definitions through a contract-level harness. It reports completion, assertion pass rate, retry rate, mean/p95 latency, recovery success and false-success count. The benchmark is not a measurement of third-party websites or production traffic.
