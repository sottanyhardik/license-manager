# Background processing

Celery/Redis support replan and ledger-package lifecycle work with retries, finalization, cleanup and recovery. V1 requires idempotency keys, durable status/provenance, bounded retry, observable failure and recovery drills before refactoring.
