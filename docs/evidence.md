# Evidence ledger

Updated: 2026-09-20

## Verified locally

| Capability | Evidence |
| --- | --- |
| Playwright execution | `scripts/run_showcase.py` completed CRM, portal and broken-UI scenarios against `demo_sites/`. |
| Human approval pause/resume | CRM run entered `WAITING_FOR_APPROVAL` before the synthetic submit action and completed only after approval. |
| Per-step trace | Showcase JSON contains step IDs, action types, inputs, outputs, durations, selector used, bounded DOM evidence and screenshots. |
| Explicit fallback | Broken UI v2 succeeds through the authored role fallback after the v1 test ID is absent. |
| Portal extraction | Synthetic table was extracted and its three-data-row assertion passed. |
| Failure evidence | Tests verify missing-selector, assertion, domain, page-budget, action-budget and browser-start failures are not represented as success. |
| Persistence controls | 40 pytest cases pass, including idempotent submission, task-version hashing and audit linkage. |
| Screenshot comparison | Pixel-difference helper returns comparable/unavailable results for controlled artifacts. |
| Benchmark | `reports/tracebrowser-benchmark.json`: 50 synthetic contract cases, 100% completion/assertion pass, 0 false successes. |

## Not verified or not claimed

- No live third-party site or customer workflow was run.
- No credentials, CAPTCHA, anti-bot bypass or access-control circumvention exists.
- No arbitrary selector healing is claimed; fallbacks must be authored in the task.
- PostgreSQL, Redis and a separate Dramatiq worker are topology boundaries, not externally verified deployment evidence.
- Docker/Compose files are provided as a deployment topology, but Docker was not available in the local verification environment.
- Production authentication, tenant isolation enforcement and hosted browser fleet operations are not claimed.
- The benchmark uses deterministic synthetic definitions and must not be presented as production reliability or customer accuracy.
