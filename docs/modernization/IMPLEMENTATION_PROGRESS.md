# Implementation Progress

Statuses: ✅ done+verified · 🟡 in progress · ⛔ blocked (needs owner) · ⏭ deferred

| # | Batch | Status | Commit | Notes |
|---|---|---|---|---|
| 0 | Discovery, docs, verified backups (3 datasets) | ✅ | 85370c94 | backups in `~/lm_backups/` |
| 1 | Repo hygiene: 263 root reports → `docs/archive/root-reports/`, 35 ad-hoc scripts → `scripts/adhoc/` | ✅ | 85370c94 | `git mv`, no references found in code/CI |
| 2 | BUSINESS-RULE CHANGE (owner-approved): signed licence balances + `is_over_utilised`; cap consumers clamped; exhausted `<= 0` | ✅ code / 🟡 CIF audit | 85370c94 | backend 131/131 pinned + 9 new tests; frontend badge + 5 tests |
| 3 | Baseline test repair (no production code changes) | 🟡 | | test-automation-engineer |
| 4 | Celery beat integrity + remove `MinValueValidator(0)` on `LicenseBalance.balance_cif` (state-only migration) | 🟡 | | backend-engineer |
| 5 | Break core→license import cycle (shims keep import paths) | 🟡 | | refactor-specialist |
| 6 | Frontend: single typed API layer + central route roles (shims) | 🟡 | | frontend-engineer |
| 7 | Performance measurement on clone DB → PERFORMANCE_REPORT | 🟡 | | report only |
| 8 | Security/config audit → SECURITY_REPORT | 🟡 | | report only |
| 9 | Refresh stale `LicenseBalance` rows | ⛔ | | live DB keeps being replaced by syncs; needs owner to confirm target DB |

## Blocked / needs owner

- Target DB for the stale-balance refresh (live `lmanagement` was replaced twice on 2026-11-16).
- Approval for each of these:
  - financial-history `on_delete` CASCADE→PROTECT. This changes delete workflows.
  - non-negativity CHECKs and allocation partial-unique constraints. Production data has not been audited.
  - dropping duplicate indexes.
  - `core_activitylog` retention.
  - `backend/DFIA_COPY` untracking.
  - JWT-in-query-param removal. This is an auth behaviour change.

## Baseline test failures (pre-existing, recorded before batch 3)

- Backend:
  - `test_parse_pdf_hs_autocreate.py` ImportError (collection).
  - `tests/test_ledger_parser.py` ×5 (missing CSVs).
  - 7 app-level failures:
    - `test_a3627_item_pivot_e2e` ×2
    - `test_e132_display_sequence`
    - `test_e1_classification_sequence`
    - `test_item_pivot_planned_import_item` ×2
    - `test_plan_utilization::test_falls_back_to_item_names_then_id_for_description`
- Frontend: `AllocationStrategyEditor.test.tsx` ×1; lint 3 errors in `frontend/route-browser-test.js`.
