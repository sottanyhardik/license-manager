# Performance baseline

Measured frontend build chunk baseline is recorded in [test baseline](../01-discovery/test-and-quality-baseline.md). Static dependency centrality identifies change-risk, not measured slowness:

| Module | Indexed dependents | V1 implication |
| --- | ---: | --- |
| `backend/apps/license/models/__init__.py` | 293 | Treat model/interface changes as migration-contract work. |
| `backend/apps/core/models.py` | 233 | Validate cross-domain data ownership and query impact. |
| `frontend/src/api/axios.js` | 110 | API-client changes require consumer/refresh/upload regression tests. |
| `backend/apps/core/constants.py` | 91 | Classify configuration semantics before edits. |
| `backend/apps/trade/models.py` | 80 | Preserve trade/report/reconciliation contracts. |
| `backend/apps/bill_of_entry/models.py` | 70 | Preserve import/BOE traceability and exports. |
| `backend/apps/allotment/models/__init__.py` | 68 | Protect allocation/reversal behavior. |
| `backend/apps/license/services/balance_calculator.py` | 57 | Golden balance comparisons before changes. |
| `backend/apps/accounts/permissions.py` | 35 | Role/object-scope matrix before changes. |
| `backend/apps/license/services/canonical_ledger_service.py` | 34 | Ledger/download compatibility testing. |

Verify query counts, report/export workloads and live navigation before setting performance budgets. No static-dependent count is presented as a runtime performance metric.

The bounded query/test and static-risk evidence is catalogued in
[performance hotspot contracts](performance-hotspot-contracts.md). It
separates existing fixture query guards from proposed production-like budgets.
