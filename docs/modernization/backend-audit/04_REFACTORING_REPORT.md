# Backend Refactoring Report — 2026-11-16

Scope: approved batches A, B, C, D, E, I, J from [00_AUDIT_SUMMARY_AND_PROPOSAL.md](00_AUDIT_SUMMARY_AND_PROPOSAL.md). Not pushed.
Rules: [ARCHITECTURE_RULES.md](../ARCHITECTURE_RULES.md) · ADR: [ADR-003](../../decisions/ADR-003-backend-modular-monolith.md) ·
Responsibility matrix and dependency map: [01 §2–3](01_STRUCTURE_AND_COUPLING.md).

**No business-rule change, no API contract change, no schema change.** `makemigrations --check` is clean after every batch, and the balance engine is untouched.

## Batches

| Batch | Commit | Problem → change | Proof |
|---|---|---|---|
| C guardrails | 9f02e071 | No enforced boundaries → ADR-003, 9 rules, AST tests (core→domain shrink-only baseline, 28-edge cross-app ratchet, no cross-app `views` imports, single balance engine) | 4 tests |
| E reconciliation | 93af0a14 | Flat module layout → `api/views.py`, `api/serializers.py`, `selectors.py`; shims at old paths | 30 routes identical, OpenAPI byte-identical, 75 tests |
| B atomic writes | (B commit) | BOE create/update, MasterViewSet CRUD/deletes (incl. TradeLine/Payment), `destroy_allotment` were non-atomic → `transaction.atomic`; success path unchanged | 13 rollback tests |
| E trade | (trade commit) | → `trade/api/{views,serializers,views_invoice_documents}.py` + `sys.modules` shims | 74 routes identical, OpenAPI byte-identical, 73 tests |
| A defects + CI | (A commit) | Ledger dispatch NameError fixed. CI/gate now run **all** app tests (about 280 were skipped). flake8 undefined-name gate added. 2 stale tests fixed. legacy `tests.py` collected | regression tests; full gate |
| D N+1 | (D commit) | sion-classes 253→6, item-names 120→4, item-plans 1848→1136 queries at ps50, exporter `.exists()` loops | 18 JSON combos byte-identical; xlsx/pdf identical |
| PDF fix | 396fbea3 | Financial-ledger PDF crashed (KeyError) for every licence with hidden BOEs | no-DB test + clone render |
| I dead code | (I commit) | 17 files / 4,957 LOC with zero references removed (`git rm`) | check, compileall, 3,054 tests |
| J1 splits | (J1 commit) | `item_pivot_report.py` 2400→262 facade + 4 modules; `license_balance_excel.py` 2015→421 facade + 3 modules | workbooks byte-identical |
| J2 splits | (J2 commit) | `license/models/core.py` 2624→101 facade + 6 model modules | `makemigrations --check` clean; `dir()` identical; 2,894 tests |

Note: commit `9f02e071` also captured 4 staged `git mv` renames from concurrent agents (shared index). It is not independently importable; `93af0a14` completes it. Later commits used path-limited `git commit -- <paths>`.

## Resulting structure (changed areas)

```
apps/reconciliation/  api/{views,serializers}.py  selectors.py  services/  (shims: views.py, serializers.py, services/queries.py)
apps/trade/           api/{views,serializers,views_invoice_documents}.py  services/  (shims at old paths)
apps/license/models/  header.py items.py planning.py documents.py incentive.py ledger_jobs.py invoice.py  core.py(facade)
apps/license/views/   item_pivot_report.py(facade) item_pivot_{helpers,generate,row,excel}.py
apps/license/services/exporters/  license_balance_excel.py(facade) balance_excel_{ledger,recon}_sheets.py license_balance_excel_bulk.py
backend/tests/architecture/  test_architecture.py
backend/.flake8
```

## Defects found and NOT fixed (pre-existing; need a decision or a separate batch)

1. `POST /trade/lines/` and `/trade/payments/` raise TypeError: `MasterViewSet.perform_create` injects `created_by`, but the line and payment models lack it.
2. The item pivot Excel raises `UnboundLocalError: sheet` when filters match zero groups. The default filters hit this on some datasets.
3. `destroy_allotment` and other financial edits write no entity audit row (Batch H).

## Remaining technical debt → recommended next phases

1. **Quick fixes (approve as a defect batch):** items 1–2 above.
2. **F — allocation consolidation:** about 500 LOC in `allotment/views_actions.py` → `AllocationService`. Needs characterization tests and cif-balance + BOE reconciliation audits.
3. **G — second sources of truth** (02 §4): billed-CIF via M2M, `condition_pool`, `planning_usage_reconciliation`, `canonical_ledger_service`, matviews, and the `LicenseBalance` cache refresh after reconciliation. Each is a BUSINESS-RULE decision.
4. **H — entity audit history** for financial edits and deletes.
5. **Restore the scheduled balance refresh** (the beat entries pointed to nonexistent tasks). Needs owner approval.
6. **Layering rollout** to bill_of_entry, allotment, license (`api/` + selectors), one app per batch, using the E pattern.
7. **Remaining large files:** `balance_calculator.py` (2,160; business review), `sion_planning_execution.py` (1,744), `canonical_planning_service.py` (1,449), `allotment/views_actions.py` (1,680; part of F).
8. **Lint ratchet:** extend flake8 beyond F82x (271 unused imports, about 180 redefinitions).
9. **Item-plans endpoint:** remaining per-licence `reconcile_license_plans` cost.
10. Security items in [SECURITY_REPORT.md](../SECURITY_REPORT.md): committed `.env` files (CRITICAL; rotate and untrack), public media, query-param JWT, npm vulnerabilities.

## Test results (final, committed tree)

`scripts/dev/quality-gate.sh backend` (now identical to CI and covering **all** apps):
`manage.py check` PASS · migrations check PASS · `pytest tests/` **241 passed** (incl. 4 architecture tests) ·
flake8 (undefined names) PASS · `pytest apps` **2,989 passed, 0 failed, 0 xfail**.
`scripts/dev/quality-gate.sh frontend`: lint, typecheck, unit tests, build all PASS.
Before this work, CI never ran about 280 of these tests, and 2 of them were failing (stale; fixed in batch A).
