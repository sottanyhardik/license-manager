# Backend architecture rules (ADR-003)

Tests live in `backend/tests/architecture/test_architecture.py`:
`cd backend && .venv/bin/python -m pytest tests/architecture -q --no-cov -p no:cacheprovider`

| # | Rule | How enforced |
|---|---|---|
| 1 | Views handle HTTP only: validate via serializer, call a service/selector, respond. | Review checklist |
| 2 | Serializers validate and represent; they never write other models or compute balances. | Review checklist |
| 3 | Every financial write (BOE rows, allotment items, import-item values, trades/lines/payments, allocations, LicenseBalance, ledger/recon rows) goes through a service with `transaction.atomic`, `select_for_update` where concurrent, and an audit record. | Review checklist + `cif-balance-auditor` / `boe-reconciliation-auditor` |
| 4 | Balances come only from `LicenseBalanceCalculator`; re-deriving balance math elsewhere is a defect. | Automated: `test_single_balance_engine` (no `calculate_balance`-style function outside `apps/license/services/`); equivalence otherwise by review/auditor |
| 5 | `core` imports no domain app at module level; cross-app access uses the target's services/selectors/models, never its views. | Automated: `test_core_has_no_new_module_level_domain_imports` (baseline = management commands only, may only shrink), `test_cross_app_import_edges_ratchet` (no new app-to-app edges), `test_no_cross_app_views_imports` (`core.views` MasterViewSet kernel exempt) |
| 6 | Read endpoints have query-count regression tests; N+1 is a defect. | Review checklist + per-endpoint `assertNumQueries` tests |
| 7 | API contracts are frozen; changes are additive only. | Review checklist + API contract tests (`tests/test_api_*.py`) |
| 8 | Schema changes are expand-and-contract, rehearsed on a clone, never destructive without approval. | Review checklist (`migration-safety` skill) |
| 9 | CI runs every app's tests; Python lint (F821/F822/F823 at minimum) gates merges. | CI (`.github/workflows/ci.yml`, `scripts/dev/quality-gate.sh`) |

Ratchet policy: when you remove an edge/import, delete it from the baseline in the test. Never add to it without an ADR note.
