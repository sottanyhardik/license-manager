# Observability

## Current evidence

**Verified by code.** `GET /api/health/` is public and intentionally returns only `{"status":"ok"}` when Django can query the database and set/read cache, otherwise `{"status":"degraded"}` with HTTP 503 (`apps/core/views/health.py`). This is a useful liveness/readiness signal; it does not establish worker, broker, storage, materialized-view freshness, external service, or business-calculation health.

Materialized-view refresh tasks log start/success/failure and can refresh all views or the licence/item/dashboard views individually (`apps/core/tasks_materialized_views.py`). A health task logs view statistics and returns a basic healthy/unhealthy payload, but its schedule, alert routing, execution history and response to stale data were not verified in a deployed environment.

Activity history and aggregate-specific audit tables exist, but activity middleware writes asynchronously. The source therefore proves instrumentation exists, not durable delivery, immutable retention, or a compliance-grade audit trail.

## V1 telemetry contract

| Signal | Current evidence | V1 requirement / acceptance criterion |
| --- | --- | --- |
| HTTP health | DB/cache probe and 200/503 status | Monitor availability, latency and response class without exposing configuration, identifiers or secrets. Exercise DB/cache outage behavior in staging. |
| Request correlation | Not evidenced as an end-to-end contract | Generate/redact correlation IDs across API, Celery, document/export and UI error reports; an operator can connect one failed user action to one request/job trace. |
| Background job lifecycle | Named Celery/package/replan/sync task states and tests exist | Capture queued/running/success/failure/retry age, owner/context and terminal error category; alert on stuck/failed critical jobs without logging sensitive payloads. |
| Financial provenance | Dual balance engines and reports are source-inspected | Every consequential displayed/exported value names calculation engine/version/as-of time and traceable inputs; mismatches become an auditable event. |
| Materialized views | Refresh/health task source exists | Record last successful refresh, duration, error, staleness threshold and fallback behavior; never silently serve stale derived balances as current. |
| Security/audit | Role checks, protected media and activity records exist | Log access-denied, export/download, destructive action and configuration mutation events with approved retention/access policy (D6). |
| Client failure | Global error boundary is source-inspected; console-only reporting noted | Provide retry/support-safe error UI and send redacted telemetry only after security policy is approved. |

## Explicit limitations

No metrics backend, alert channel, production dashboard, log-retention configuration, trace sampling, worker heartbeat, or incident runbook execution was observed. These are P1 operational implementation and validation work, not existing verified capabilities.
