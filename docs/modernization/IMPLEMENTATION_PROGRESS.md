# Implementation Progress

Statuses: ✅ done+verified · 🟡 in progress · ⛔ blocked (needs owner) · ⏭ deferred

| # | Batch | Status | Commit | Notes |
|---|---|---|---|---|
| 0 | Discovery, docs, verified backups (3 datasets) | ✅ | 85370c94 | backups in `~/lm_backups/` |
| 1 | Repo hygiene: 263 root reports → `docs/archive/root-reports/`, 35 ad-hoc scripts → `scripts/adhoc/` | ✅ | 85370c94 | `git mv`, no references found in code/CI |
| 2 | BUSINESS-RULE CHANGE (owner-approved): signed licence balances + `is_over_utilised`; caps clamped; exhausted `<= 0` | ✅ | 85370c94, 4f6ef131 | cif-balance-auditor: APPROVE WITH FIXES → planning export clamp fixed in 4f6ef131 |
| 3 | Baseline test repair (stale tests, missing fixtures, flake); no production code | ✅ | 5e8bdba9*, 0a55d205 | *frontend part by session license-manager-02 |
| 4 | Celery beat: 4 entries for nonexistent tasks disabled + test; `LicenseBalance` validator removed (migration 0057, no-op SQL) | ✅ | e22f1ad5 | 0057 **not applied** to local DB (see blocked) |
| 5 | core→domain imports made runtime-only (28→18 edges, 0 module-level) | ✅ | ca9dad8b | no shims needed |
| 6 | Frontend: single typed API layer `src/api` + central typed route roles (40 guards verified identical) | ✅ | 40198342 | shims at `services/api/*` |
| 7 | Performance: licence list 268→21 queries; BOE list 2116→1112 (byte-identical JSON, 18 combos) | ✅ | 81163117 | BOE per-row available-CIF batching needs CIF audit |
| 8 | Reports: PERFORMANCE_REPORT, SECURITY_REPORT | ✅ | 4f6ef131 | |
| 9 | Refresh stale `LicenseBalance` rows | ⛔ | | live DB replaced by syncs; also see beat finding below |
| W0 | Read-only integrity tooling `scripts/dev/db_integrity/` | ✅ | 5e8bdba9* | |

## Blocked / needs owner

- **CRITICAL (security):** `.env`, `backend/.env_dgft`, `frontend/.env`, `frontend/.env.production` are tracked in git. Fix = rotate secrets + `git rm --cached` + gitignore. Not done automatically: untracking deletes the files on every machine/server that next pulls (deploy outage risk), and rotation is owner-only.
- **Scheduled balance refresh never ran:** beat `update-balances-11am/8pm-ist` pointed to a nonexistent task (likely cause of stale `LicenseBalance` rows). Restoring it means writing a task, which counts as new behaviour, so it needs owner approval (`update_balance_cif` command exists and could be wrapped).
- Apply migration 0057 to the local DB (`manage.py migrate license`). No-op SQL; prompts by policy.

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
