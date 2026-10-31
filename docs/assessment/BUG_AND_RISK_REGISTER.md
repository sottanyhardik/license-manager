# Defect and risk register

| ID | Severity | Status/evidence | Impact and remedy |
|---|---|---|---|
| SEC-01 | P0 external SaaS; P1 otherwise | Confirmed static: global roles/no tenant membership and unscoped domain reads. | Cross-company leakage. Tenant membership, scoped query/mutation layer, negative tests. |
| DFR-01 | P1 | Confirmed static: percentage text key in condition pools. | Incorrect shared/independent cap consumption. Explicit versioned group/member model. |
| DFR-02 | P1 | Confirmed static: duplicated SION capacity and exception→zero paths. | Undercount/bypass/race risk. Canonical resolver and fail-safe errors/locks. |
| DFR-03 | P1 | Confirmed static: canonical and legacy planning paths coexist. | Divergent plans. Characterisation and staged migration. |
| SEC-03 | P1 | Confirmed static: reconciliation query calls lack user/company context. | Financial data exposure. Scoped services. |
| QA-01 | P2 | Executed fail: `AllocationStrategyEditor.test.tsx:70`. | Stale test/API contract mismatch; decide payload then update test in implementation phase. |
| QA-02 | P2 | Executed fail: lint finds 3 ESM `require` errors. | Release hygiene blocker; fix/replace script. |
| UX-01 | P2 | Static: reports/masters/admin largely command-palette-only. | Discoverability/workflow friction; contextual nav. |
| UX-02 | P2 | Static: `routes/config.js` says protected false versus actual router guards. | Metadata drift; one manifest. |
| OPS-01 | P2 | Runtime operations unavailable. | Unknown restore/task/deploy reliability; staging drills/observability. |

No item above is a claim of production reproduction unless explicitly marked “executed”.
