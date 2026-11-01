# Deployment readiness

## Verified delivery controls

**Verified by code/static inspection.** GitHub CI has four required job families: frontend lint/typecheck/Vitest/build; backend migration check plus canonical and licence/core tests against PostgreSQL 16 and Redis 7; MDS migration/test against its own PostgreSQL 16 service; and mds-client unit tests. The workflow does not run Playwright/axe, a restore drill, deployment preflight, performance tests, or an enforced coverage threshold.

`/api/health/` checks database/cache reachability only. Deployment scripts exist under `scripts/deployment/`, and `verify-deployment.sh` delegates to `auto-deploy.sh --preflight-only --execute`, so the preflight implementation is shared with deployment entry logic. Neither script has been executed against production or staging in this audit.

## Release evidence gate

| Gate | Evidence needed before release | Current status |
| --- | --- | --- |
| Immutable release input | Branch/commit/artifact identity, dependency lock verification and approved configuration diff | Partial: V1 branch baseline is recorded; release artifact process not observed. |
| Database safety | Pinned migration graph, schema diff, duplicate/orphan scan, verified backup and isolated restore | Not verified. |
| Application availability | Django health plus worker/beat/broker/storage/external-integration health and failure drill | Partial code evidence only. |
| Security posture | Deployed TLS/HSTS/cookie/CORS/CSP/header evidence, secret-rotation record, protected-file/direct-download checks | Settings tests exist; deployed configuration not verified. |
| Functional regression | CI job results, P0/P1 API negative/transaction tests, authenticated browser/axe smoke and export/upload checks | Backend/frontend/MDS/MDS-client unit baselines measured; local E2E executed but failed (harness, fixture and two serious axe contrast failures); contracts incomplete. |
| Background recovery | Replan/ledger/sync retry, duplicate, worker restart and poison-input drill | Source/test evidence exists; production-like exercise not verified. |
| Data correctness | Dual-balance/allocation/report golden reconciliation and migration backfill checksums | Partial source/test evidence; owner decisions D2/D3 outstanding. |
| Operability | Correlated logs, alerts, dashboards, runbooks and on-call/rollback owner | Not verified. |

## MDS isolated verification

The initial default-local-host MDS attempt collected 25 tests but errored at database setup because that PostgreSQL service lacked the `master_data` role. It was not modified. The test was subsequently reproduced against a disposable PostgreSQL 16 container bound to `127.0.0.1:55432`, using the CI service user/database values: migration drift check passed and **25/25 tests passed in 0.80s**. The container was removed after the run. The mds-client unit runner also passed **32/32 in 0.015s** against its in-memory database. This closes the local MDS/MDS-client unit-environment gaps, but not deployment, peer-lifecycle or production-service verification.

Production deployment, live schema and restore capabilities remain **not verified**. Configuration-code tests and script existence are not substitutes for deployment evidence.

The bounded tracked-configuration analysis and safe validation/rollback sequence are in [operational configuration contracts](operational-configuration-contracts.md). It records no live-system inspection or deployment action.
