# V1 audit status report

## Outcome at this checkpoint

**Audit documentation is substantially advanced, but V1 audit completion is not yet proven.** This report separates measured discovery and bounded workflow evidence from the individual contracts, live-environment checks, and owner policy decisions still required before implementation begins.

## Preservation and baseline

| Item | Evidence | Status |
| --- | --- | --- |
| V1 branch | `version-v1`, created from `d78c8b1d108368a9e48b26a05a50094dc930608d` (original branch `codex/baseline-regression`) | Verified |
| Worktree preservation | Branch creation had no tracked staged/unstaged changes; ignored databases, media, PDFs, credentials, logs, caches, virtual environments and generated indexes were preserved | Verified at baseline |
| Source behavior | V1 work contains documentation only; no application source, schema, data, legacy documentation or production state was changed | Verified |
| Legacy documentation | 645 exact tracked Markdown paths are registered; every path is `Retain`, with no deletion or archival action executed | Verified for preservation |

## Traceability evidence

| Population | Current measured coverage | Meaning / remaining closure |
| --- | --- | --- |
| API operations | 354/354 resolve from OpenAPI to runtime callbacks; 354/354 source-family mapped; 354/354 have individual source-contract rows | Registration and source ownership/schema evidence are complete. Individual request/response fixtures, action authorization, data effect, consumer and test contracts remain Partial. |
| Frontend routes | 57/57 static page/gate/API-disposition rows; 49 P0/P1 route IDs have implementation acceptance gates; 2 read-only running-screen observations | Static discovery is complete. Browser state matrices and server contracts remain Partial. |
| Backend symbols | 8,046/8,046 have stable IDs/status; 3,136 carry file-import blast-radius evidence | Import edges are not caller/effect/auth/test mapping; individual symbols remain Partial. |
| Critical workflow boundaries | 12/12 source/data/authorization/recovery/named-test maps; 16/16 functional workflows have named existing test evidence | Named evidence is not full positive/negative/error contract coverage. |
| Data entities | Declared ownership, relationships, high-consequence constraints and lifecycle mechanics documented | Live schema, data-quality and restore reconciliation remain Partial. |

Detailed artefacts: [coverage metrics](../09-traceability/traceability-coverage.md), [API action map](../09-traceability/api-action-workflow-map.md), [P0/P1 route contract register](../09-traceability/p0-p1-route-api-contract-register.md), [backend workflow map](../09-traceability/backend-critical-workflow-map.md), and [workflow test map](../09-traceability/critical-workflow-test-map.md).

## Verification baseline

| Command / check | Result | Evidence class |
| --- | --- | --- |
| Frontend tests | 544 tests in 78 files passed | Verified by test |
| Frontend lint, typecheck, build | Passed | Verified by test |
| Django check / migration drift check | Passed / no changes detected | Verified by test |
| Canonical backend suite | 237 passed in 67.01s; 20% aggregate coverage reported | Verified by test |
| Licence/core app suite | 2,708 passed in 440.51s | Verified by test |
| OpenAPI validation | 246 paths, 354 operations, 0 errors, 22 warnings in six warning classes | Verified by test |
| MDS migration/test suite | Migration check passed; 25 passed in 0.80s against disposable PostgreSQL 16 CI-equivalent container | Verified by test |
| MDS-client suite | 32 passed in 0.015s against its in-memory Django test database | Verified by test |
| Local browser/axe suite | 68 passed, 54 failed, 8 skipped in 3.6m; two serious contrast failures plus harness/fixture defects | Measured failing baseline |
| Browser observation | Login and BOE list rendered in existing deployed tabs; no mutation/export/download occurred | Observed in running application |

## P0/P1 conditions before implementation changes

1. Obtain owner decisions D1–D6, especially company/object policy (D1), named dual balance semantics (D2), and SION/restriction policy (D3).
2. Convert the P0/P1 route/API acceptance register into direct positive, wrong-role/object-scope and error/recovery tests.
3. Freeze balance/allocation/report golden data cases and verify results across hidden/corrected/reversed/restored records.
4. Reconcile physical schema/migration graph and complete an isolated backup/restore exercise before schema work.
5. Run a controlled multi-peer MDS integration/recovery drill.
6. Repair the local Playwright harness/fixtures and serious contrast defect, then run authenticated critical-path browser/axe tests and deployment/worker/restore drills; add the agreed gate to CI.

## Architecture direction

The evidence supports an incremental Django/React modular-monolith V1: retain existing platform choices, establish explicit service/API/transaction contracts at domain boundaries, preserve dual balance engines pending policy approval, use additive/compatible data migrations, and introduce a typed feature/route registry with shared state/accessibility patterns. It does **not** support a microservice rewrite, universal tenant isolation, a double-entry ledger, or bank reconciliation without owner requirements.

## Completion gate

The authoritative gate is [completion-audit.md](../09-traceability/completion-audit.md). No V1 audit may be called complete solely because inventories or generated registers exist. Every current `Partial` must be directly verified or have a precise owner-approved external limitation.
