# License Manager V1 specification

Status: audit baseline in progress. This is the authoritative V1 planning layer; it authorizes no production, schema, data, or behaviour change.

## Baseline and evidence posture

| Item | Value |
| --- | --- |
| Branch | `version-v1` |
| Starting commit | `d78c8b1d108368a9e48b26a05a50094dc930608d` |
| Starting branch | `codex/baseline-regression` |
| Git worktree | No tracked staged or unstaged changes at branch creation; ignored local databases, media, PDFs, credentials, logs, caches, virtual environments and generated indexes were preserved in place. |
| Static inventory | `.claude/index/` (the documented `.Codex/index/` path is absent). At baseline it reports 1,013 backend files / 8,046 symbols; global symbol index: 9,868 rows. |

Claims have an evidence label: **Verified by code**, **Verified by test**, **Observed in running application**, **Inferred from static inspection**, **Proposed for V1**, or **Requires owner approval**. Existing `docs/enterprise-rebuild/` and `docs/assessment/` are evidence inputs, not silently superseded.

## Reading order

1. [Audit status](00-executive-overview/v1-audit-status.md), [Executive overview](00-executive-overview/product-vision.md), [scope](00-executive-overview/scope-and-non-goals.md), and [decisions](00-executive-overview/decisions-required.md).
2. [Repository inventory](01-discovery/repository-inventory.md), [API inventory](01-discovery/api-inventory.md), and [quality baseline](01-discovery/test-and-quality-baseline.md).
3. [Domain rules](04-domain-and-business-rules/domain-model.md) and [financial rules](04-domain-and-business-rules/financial-rules.md).
4. [Target architecture](05-target-architecture/architecture-overview.md), [roadmap](08-implementation/implementation-roadmap.md), and [traceability](09-traceability/requirements-to-code.md).

Read [completion audit](09-traceability/completion-audit.md) before treating any inventory as complete; it distinguishes verified denominators from unresolved contract coverage.

[Workflow traceability register](09-traceability/workflow-register.md) connects those technical denominators to the current business-capability families and their V1 dispositions.

[Traceability coverage metrics](09-traceability/traceability-coverage.md) shows exactly which fields are evidenced and which remain to be reconciled.

The implementation-ready P0/P1 route/API acceptance matrix is [p0-p1-route-api-contract-register.md](09-traceability/p0-p1-route-api-contract-register.md); it is the next safe execution artefact after owner decisions, rather than a mandate to refactor current behavior.

[The contract-closure protocol](09-traceability/contract-closure-protocol.md) defines the proof required to promote an operation, route, or backend boundary from Partial to Verified and sequences the remaining audit work by financial/security risk.

The current deep evidence samples are [P0/P1 API contracts](09-traceability/p0-api-deep-contracts.md), [P0/P1 frontend action contracts](09-traceability/frontend-p0-action-contracts.md), and [security-critical paths](09-traceability/security-critical-paths.md). They strengthen the baseline but deliberately do not close any global coverage denominator.

Supporting deep slices cover [balance/allocation/replan functions](09-traceability/balance-allocation-function-contracts.md), [high-risk entity lifecycles](06-data-and-migrations/high-risk-entity-lifecycle-contracts.md), and [P0/P1 regression tests](09-traceability/p0-regression-test-contracts.md).

The next domain-function slices cover [SION/planning](09-traceability/sion-planning-function-contracts.md), [reconciliation](09-traceability/reconciliation-function-contracts.md), and [task/activity lifecycle](09-traceability/task-activity-function-contracts.md).

Shared CRUD, inherited serializer and filtering behavior is bounded in the [generic CRUD contract register](09-traceability/generic-crud-serializer-contracts.md).

The V1 quality/UX planning layer now includes [performance hotspot contracts](07-quality-and-operations/performance-hotspot-contracts.md), [operational configuration contracts](07-quality-and-operations/operational-configuration-contracts.md), and [frontend maintainability contracts](03-ui-ux/frontend-maintainability-contracts.md).

Data, rules and external boundaries are sequenced in the [entity-contract queue](06-data-and-migrations/entity-contract-closure-queue.md), [business-rule queue](04-domain-and-business-rules/business-rule-closure-queue.md), and [integration queue](09-traceability/integration-contract-closure-queue.md).

The [business-rule closure queue](04-domain-and-business-rules/business-rule-closure-queue.md) sequences dual balances, quantity/CIF, planning, reconciliation, trade and report provenance into synthetic golden-data and owner-decision gates.

File, parser and generated-document boundaries are traced in the [document pipeline contracts](09-traceability/document-pipeline-function-contracts.md).

Operational and remaining UI evidence is bounded in [maintenance-command contracts](09-traceability/maintenance-command-contracts.md), [peer sync/background contracts](09-traceability/sync-background-contracts.md), and [admin/report/upload frontend contracts](09-traceability/frontend-admin-report-action-contracts.md).

Additional API slices cover [BOE/trade](09-traceability/boe-trade-deep-contracts.md), [identity/admin/master](09-traceability/identity-masters-deep-contracts.md), and [reports/exports/downloads](09-traceability/reports-download-deep-contracts.md).

[The V1 deliverable evidence matrix](09-traceability/v1-deliverable-evidence-matrix.md) reconciles the original audit deliverables with current proof, closure evidence and limitations.

The remaining large-population work is sequenced in the [API](09-traceability/api-contract-closure-queue.md), [backend-symbol](09-traceability/backend-symbol-closure-queue.md), [test-symbol](09-traceability/test-symbol-closure-queue.md), and [route](09-traceability/route-contract-closure-queue.md) closure queues. The external gates are packaged in [owner decision packets](00-executive-overview/owner-decision-packets.md) and the [live schema/recovery evidence protocol](06-data-and-migrations/live-schema-and-recovery-evidence-protocol.md).

The measured local browser/axe result and its exact failure disposition are in [e2e-baseline.md](07-quality-and-operations/e2e-baseline.md).

The running execution record is [execution-log.md](execution-log.md); preservation and retirement recommendations are in [legacy-documentation-disposition.md](legacy-documentation-disposition.md).
