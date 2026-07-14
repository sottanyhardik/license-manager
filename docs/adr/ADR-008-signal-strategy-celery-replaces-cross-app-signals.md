# ADR-008 — Signal Strategy: Celery Replaces Cross-App Signals

**Status:** Accepted
**Date:** 2026-07-14

## Context

The legacy app uses Django signals (`post_save`, `post_delete`) to trigger
cross-model side effects. A Phase 1 audit identified two categories of
problems with this approach:

1. **String-referenced senders** (`@receiver(post_save, sender='myapp.MyModel')`):
   If `MyModel` is renamed or moved to a different app, the signal silently
   stops firing. No error is raised at startup or at the point of the change.
   This has caused production bugs where balance recomputes stopped running
   after a model refactor.

2. **Synchronous execution on the request thread**: A signal handler that
   recomputes license balances after a BOE save adds that computation to the
   HTTP response time for the BOE create/update endpoint. Under load, this
   can cause timeouts.

## Decision

The new app enforces the following signal policy:

**Cross-app side effects are dispatched as Celery tasks, not Django signals.**

- When saving a BOE record triggers a balance recompute for the parent license,
  the service function calls `recompute_balance.delay(license_id=...)` — a
  Celery task — not a signal.
- Celery tasks for side effects must be **idempotent**: calling them multiple
  times with the same arguments produces the same result as calling them once.
  This enables safe retry on transient failure (e.g. DB connection blip).

**Within-app signals are allowed for audit logging only.**

- `post_save` and `post_delete` receivers that write to
  `django-simple-history` audit tables are acceptable within a single app.
- The sender must be referenced as the class object directly, never as a
  string: `@receiver(post_save, sender=License)`.

**String-referenced senders are banned.**

- The CI linter (Ruff custom rule or `grep` check in the pre-commit hook)
  must flag any `sender='...'` string argument to `@receiver`.

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Keep Django signals for cross-app effects | Silent failure on sender rename (confirmed production bug in Phase 1 audit); synchronous execution blocks the request thread; hard to test signal chains in isolation. |
| Synchronous service calls (no Celery) | Keeps code simpler but adds computation latency to the user-facing request. For heavy operations (balance recompute over hundreds of BOE rows), this produces timeout risk. |
| Celery with non-idempotent tasks | Celery's default retry behaviour will call the task again on failure; non-idempotent tasks (e.g. incrementing a counter) produce incorrect results on retry. |
| Django Channels / async signals | Adds WebSocket infrastructure; async Django is not the primary execution model for this app; Celery is already required for other background work. |

## Consequences

**Positive:**
- Cross-app side effects are explicit, named, and traceable via Celery task
  names and Flower monitoring. No hidden signal wiring.
- Task execution is asynchronous: the HTTP response returns immediately after
  the task is enqueued; balance recomputes happen out of band.
- Idempotent tasks can be safely retried by Celery's auto-retry mechanism
  without double-counting risk.
- Celery Beat can schedule periodic recomputes (e.g. nightly balance
  reconciliation) using the same task functions.

**Negative:**
- Cross-app consistency is eventually consistent, not immediately consistent.
  A BOE save completes (HTTP 201) before the balance recompute finishes.
  UI consumers must handle the brief window where the displayed balance is
  stale (TanStack Query's `invalidateQueries` after mutation is the standard
  handling).
- Celery requires Redis (broker) and at least one worker process in production.
  This adds operational overhead vs a pure-Django deployment.
- Idempotency must be deliberately designed into every task. Developers must
  document the idempotency invariant in a docstring for each Celery task.
- The ban on string-referenced senders must be enforced by tooling, not just
  convention; adding the CI check is a prerequisite for merging the first
  signal-bearing PR.

## Related ADRs

- ADR-003 — Backend Tech Stack
- ADR-007 — Service Layer: Views Never Touch ORM
