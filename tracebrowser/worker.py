"""Optional async boundary. The local verified path stays synchronous and credential-free."""

import os

try:
    import dramatiq
    from dramatiq.brokers.redis import RedisBroker
except ImportError:  # pragma: no cover - optional deployment dependency
    dramatiq = None

from .db import session_factory
from .main import ARTIFACT_ROOT
from .runtime import BrowserExecutor

if dramatiq is not None:  # pragma: no cover - optional deployment path
    dramatiq.set_broker(RedisBroker(url=os.getenv("REDIS_URL", "redis://localhost:6379/0")))

    @dramatiq.actor
    def execute_run(run_id: str) -> None:
        BrowserExecutor(session_factory(), ARTIFACT_ROOT).execute(run_id)
else:

    def execute_run(run_id: str) -> None:
        BrowserExecutor(session_factory(), ARTIFACT_ROOT).execute(run_id)
