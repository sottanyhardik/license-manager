# Security and SaaS readiness

## Evidence-backed assessment

JWT/role configuration, production security validation and protected-media checks are present (`settings.py:80,270,328,503,562`; `core/views/media.py:1`). Activity logging/audit fields exist (`core/middleware.py:138`; `core/models.py:73`). These are strengths, not a SaaS certification.

| ID | Priority | Risk | Required control |
|---|---|---|---|
| SEC-01 | P0 external SaaS | Global roles/no demonstrated tenant membership or request scoping. | Tenant + Membership, mandatory scoped repositories, object checks, negative isolation tests/backfill. |
| SEC-02 | P1 | Authenticated master reads and potentially sensitive company/counterparty data. | Data-classification and global-vs-tenant master policy. |
| SEC-03 | P1 | Reconciliation query service has no user/company context (`reconciliation/views.py:64`). | Pass/validate scoped company set in every query/mutation. |
| SEC-06 | P2 | HTTP activity log is not immutable financial event history. | Transactional domain audit events with before/after/reason/actor. |
| SEC-08 | P2 | Query-string token download exception (`middleware.py:7`). | Short-lived signed URLs and log/referrer redaction. |
| SEC-09 | P2 | Deployment, backups, restore, monitoring and live headers not inspected. | Staging evidence, restore drill, alert/runbook/release gate. |

External SaaS remains blocked pending these controls and runtime validation. Application-level scoping is a practical first step; evaluate DB RLS as defence in depth after consistent tenant IDs.
