# Backend architecture rules (ADR-003)

Tests live in `backend/tests/architecture/test_architecture.py`:
`cd backend && .venv/bin/python -m pytest tests/architecture -q --no-cov -p no:cacheprovider`

| # | Rule | How enforced |
|---|---|---|
| 1 | Views handle HTTP only: validate via serializer, call a service/selector, respond. | Automated (heuristic ratchet): `test_views_orm_writes_do_not_grow` (ORM write calls per view module may only fall) + review |
| 2 | Serializers validate and represent; they never write other models or compute balances. | Review checklist |
| 3 | Every financial write (BOE rows, allotment items, import-item values, trades/lines/payments, allocations, LicenseBalance, ledger/recon rows) goes through a service with `transaction.atomic`, `select_for_update` where concurrent, and an audit record. | Automated (ratchet): `test_financial_writes_outside_services_do_not_grow` (direct `FinancialModel.objects.<write>` outside `services/`) + `cif-balance-auditor` / `boe-reconciliation-auditor` |
| 4 | Balances come only from `LicenseBalanceCalculator`; re-deriving balance math elsewhere is a defect. | Automated: `test_single_balance_engine` (no `calculate_balance`-style function outside `apps/license/services/`); equivalence otherwise by review/auditor |
| 5 | `core` imports no domain app at module level; cross-app access uses the target's services/selectors/models, never its views. | Automated: `test_core_has_no_new_module_level_domain_imports` (baseline = management commands only, may only shrink), `test_cross_app_import_edges_ratchet` (no new app-to-app edges), `test_no_cross_app_views_imports` (`core.views` MasterViewSet kernel exempt), `test_no_new_app_dependency_cycles` (no new app-level cycle/SCC; prints cycle path), `test_no_new_cross_app_private_imports` (no `_name` imports across apps), `test_domain_packages_are_pure` (`*/domain/**` imports no django.db/DRF/requests/celery/redis) |
| 6 | Read endpoints have query-count regression tests; N+1 is a defect. | Review checklist + per-endpoint `assertNumQueries` tests |
| 7 | API contracts are frozen; changes are additive only. | Review checklist + API contract tests (`tests/test_api_*.py`) |
| 8 | Schema changes are expand-and-contract, rehearsed on a clone, never destructive without approval. | Review checklist (`migration-safety` skill) |
| 9 | CI runs every app's tests; Python lint (F821/F822/F823 at minimum) gates merges. | CI (`.github/workflows/ci.yml`, `scripts/dev/quality-gate.sh`) |

Ratchet policy: when you remove an edge/import, delete it from the baseline in the test. Never add to it without an ADR note.
