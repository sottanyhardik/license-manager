# 19. Technical debt and code quality

**Agent:** F (documentation, technical debt and missing features audit)
**Evidence snapshot:** branch `version-v1`, working tree as of 2026-11-01 (uncommitted changes included).
**Method:** read-only static analysis: grep for markers and importers, line counts, Python `ast` scan of test bodies (no test was executed), `git ls-files` for tracked artefacts. No source file was modified and no package was installed. Pytest was not run, so pass and fail results are not claimed.
**Heuristic status:** the import-cycle result is a static grep of import lines, not a dependency-graph analysis. It is labelled as a heuristic in section 6.

---

## 1. Summary

- **Markers.** `backend/apps` has 95 matched lines: 93 `TODO`, 2 `XXX` (both false positives in a format string), 0 `FIXME`, 0 `HACK`. Of the real markers, 89 are in three `*_option_c.py` test files and 4 are in production code. `frontend/src` has 0 markers of any kind.
- **Dead code confirmed.** All eight frontend candidates in the inventory have no importers. Three more frontend items are new: `utils/canonicalLedgerAdapter.js` (no references), `components/ui/index.js` (no importers, likely), and the `recharts` dependency (no production import). Backend: `lmanagement/tasks.py` (orphaned and broken), `core/signals_materialized_views.py` plus `core/tasks_materialized_views.py` (orphaned chain), `core/cached_views.py` (module unused), `apps/accounting` (residue, bytecode only).
- **Correction to the inventory.** `apps/core/sync` is not dead. It is not in `INSTALLED_APPS` by design, but it is routed, imported and signal-wired.
- **Duplicate logic.** StatCard has two APIs. The two transfer-letter pages are near-clones (59 changed diff lines). The four SION report wrappers are thin shells. The two reconciliation screens overlap. The two `licenseBalanceHelpers.ts` files are a name collision, not duplicated logic.
- **Large files.** 14 production Python files and 10 frontend files exceed 1,000 lines (plus 5 test files). The four files named in the brief all combine several responsibilities; `ItemPivotReportView` alone is about 1,744 lines in one class.
- **Circular dependencies (heuristic).** No model-level import cycle was found. Five pairs of production apps import each other at module level through services, serializers, signals and views.
- **Test discovery.** Confirmed: the three `tests.py` files are never collected by pytest (`python_files = test_*.py`). The trade file is a 3-line placeholder and is shadowed by its `tests/` package.
- **New test-quality finding.** 74 test functions in three `*_option_c.py` files contain no assertion. 73 of them have only comments and `pass`, so they can only pass. This is the most important debt item in this file (ISS-073).
- **Naming.** Code uses `license` (6,897 occurrences in production Python). `licence` appears 885 times, mostly in comments, docstrings and business text. UI text mixes both spellings. No convention is enforced.

---

## 2. Marker counts

Pattern: `\b(TODO|FIXME|XXX|HACK)\b`, `--include='*.py'` for backend, all text files under `frontend/src` for frontend.

| App / area | TODO | FIXME | XXX | HACK | Production | Tests / other |
|---|---:|---:|---:|---:|---:|---:|
| accounts | 1 | 0 | 0 | 0 | 1 (`management/commands/migrate_auth.py:301`, "FIELD MAPPING (TODO for backend-engineer)") | 0 |
| license | 92 | 0 | 2 | 0 | 3 (`services/percentage_existing_usage.py:226`; `services/split_by_percentage_planner.py:286`, `:377`) | 89 in `tests/test_ledger_characterization_option_c.py` (50), `tests/test_cross_output_parity_option_c.py` (28), `tests/test_p0_defect_regression_option_c.py` (11). 2 XXX false positives in `tests/parity_utils.py:113,128` (`X,XX,XX,XXX` number format) |
| allotment, bill_of_entry, core, reconciliation, tasks, trade, accounting | 0 | 0 | 0 | 0 | 0 | 0 |
| **backend/apps total** | **93** | **0** | **2** | **0** | **4** | **89 real + 2 false positive** |
| backend outside apps (`lmanagement`, `shared`, `api_utils`, `tests`) | 0 | 0 | 0 | 0 | 0 | 0 |
| **frontend/src total** | **0** | **0** | **0** | **0** | 0 | 0 |

Suppression comments (approximate, grep counts):

| Pattern | Frontend `src` (non-test) | Backend `apps` (non-test) |
|---|---:|---:|
| `eslint-disable` | 14 | n/a |
| `as any` | 16 | n/a |
| `: any` annotations | about 166 | n/a |
| `# noqa` | n/a | 14 |
| `# type: ignore` | n/a | 2 |
| `@ts-ignore` / `@ts-expect-error` | 0 | n/a |

---

## 3. Dead code table

Status key: **CONFIRMED_DEAD** (no importer and no route), **CONFIRMED_UNUSED** (only re-exported), **LIKELY_DEAD** (no path-based importer found; module-graph check not run), **BROKEN_ORPHAN** (unused and cannot run as written), **STALE_RESIDUE** (no source left), **LIVE** (candidate rejected), **AD_HOC** (not imported; outside the test suite).

| Path | Evidence | Status |
|---|---|---|
| `frontend/src/layout/Sidebar.tsx` | Only self-reference. Sole consumer of the `routes` export in `routes/config.js` (lines 1-59). That config names `LicensePage` (line 12) and `AllotmentPage` (line 19), which do not exist | CONFIRMED_DEAD |
| `frontend/src/components/GlobalErrorBoundary.tsx` | No importer | CONFIRMED_DEAD |
| `frontend/src/pages/errors/ServerError.tsx` | No importer; no route. `AppRoutes.tsx:11-12` imports only `Unauthorized` and `NotFound` | CONFIRMED_DEAD |
| `frontend/src/components/AllotmentFormModal.tsx` | Self-definition only (line 11). Still documented as the allotment entry point in `docs/03-features.md:120, 143` (DOC-05) | CONFIRMED_DEAD |
| `frontend/src/pages/masters/tables/BalanceTab.tsx` | No importer (matches only its own file) | CONFIRMED_DEAD |
| `frontend/src/pages/planning/ResidualPolicyEditor.tsx` | No importer (named export only) | CONFIRMED_DEAD |
| `frontend/src/services/api/masterApi.js`, `allotmentApi.js` | Re-exported as namespaces at `services/api/index.js:5-6` and default at `:12-13`. Namespace never consumed; only mock objects in `pages/masters/MasterList.smoke.test.tsx:42-44` | CONFIRMED_UNUSED |
| `frontend/src/utils/canonicalLedgerAdapter.js` (new) | Four exports (lines 22, 92, 109, 149). Zero references in `src` or `e2e`. Its comments say it is for "compatibility with existing PDF/Excel generation code" (lines 59, 103, 134) | CONFIRMED_DEAD |
| `frontend/src/components/ui/index.js` (new) | "Legacy UI primitives barrel" (lines 1, 20). No importer of `components/ui` by path or `@/` alias | LIKELY_DEAD |
| `recharts` in `frontend/package.json:50` (new) | Referenced only by `src/pages/Dashboard.test.tsx:14` (mock) and `vite.config.js:107` (chunk list). Not imported by production code | UNUSED_DEPENDENCY |
| `backend/apps/accounting/` | Directory contains only 33 `cpython-314` `.pyc` files under `__pycache__` (including `migrations/`, `tests/`, `management/`). No `.py` source, no tracked files (`git ls-files backend/apps/accounting` is empty), not in `INSTALLED_APPS`, no URL or import reference | STALE_RESIDUE |
| `backend/lmanagement/tasks.py` | No importer. Celery autodiscovery uses `INSTALLED_APPS` (`lmanagement/celery.py:40`), so it is never loaded. Functions import `ebrc` (not in the repo) at lines 21-25 and later. Contains `@shared_task delete_license_details_by_numbers` (lines 119-120); if the module were ever imported, that destructive task would register | BROKEN_ORPHAN |
| `backend/apps/core/signals_materialized_views.py` | No importer. `CoreConfig.ready()` (`apps/core/apps.py`) does not import it. Its only import target, `apps/core/tasks_materialized_views.py`, is imported only by this module | CONFIRMED_DEAD (chain of two modules) |
| `backend/apps/core/materialized_views.py` | Imported by migration `0003_create_materialized_views.py:18-19` | LIVE (only the signals and tasks chain above is dead) |
| `backend/apps/core/cached_views.py` (whole module) | No importer outside the file. `CachedModelViewSet` (line 107) and `CachedReadOnlyModelViewSet` (line 120) have no subclass in the repo. Mixins (lines 27, 64) used only within the file | CONFIRMED_DEAD (module) |
| `backend/apps/core/sync/` | Routed at `lmanagement/urls.py:52`; `core/models.py:20` imports `.sync.mixins`; `core/apps.py` connects sync signals; models use `app_label = "core"`. Not in `INSTALLED_APPS` as its own app, by design | LIVE (inventory candidate rejected) |
| Backend root ad hoc scripts (22): `deep_trace.py`, `final_debug.py`, `reconciliation_detailed.py`, `trace_canonical_lines.py`, `trace_persistence.py`, `trace_sql.py`, 9 × `verify_*.py`, 7 × `test_*.py` | No importer by name. The seven `test_*.py` files sit outside `pytest.ini` `testpaths` (`tests`, `apps`) | AD_HOC |
| `backend/apps/core/management/commands/sync_from_ge_server.py:224` | Live command whose `_sync_license_data` body has `_ = force  # Retained for CLI compatibility; external sync is not implemented here.` | LIVE (compatibility stub; see section 9) |

---

## 4. Duplicate-logic table

| Pair | Evidence | Assessment |
|---|---|---|
| `frontend/src/components/licenseBalanceHelpers.ts` (17 lines, 6 exports) vs `frontend/src/pages/license-balance/licenseBalanceHelpers.ts` (137 lines, 11 exports) | No shared export names. Callers: `components/LicenseBalanceModal.tsx:13` imports the first; `pages/license-overview/*` import the second via `@/pages/license-balance/...` | NAME_COLLISION, not duplicate logic. Two modules with one basename make authoritative source ambiguous |
| `frontend/src/components/StatCard.tsx` (157 lines; props `label`, `value`, `icon`, `tone`, `onClick`, `loading`, `secondaryValue`, `title`, `compact`) vs `frontend/src/pages/license-overview/StatCard.tsx` (118 lines; props `icon`, `title`, `value`, `helper`, `accent`, `highlighted`, `footer`) | Five importers of the first (`LicenseLedgerDetail.tsx:18`, `Dashboard.tsx:24`, `ReconciliationIssues.tsx:10`, `ReconciliationPanel.tsx:10`, `LicensePurchaseProfitReport.tsx:16`). One importer of the second (`license-overview/LicenseMetricsGrid.tsx:3`) | DUPLICATE_CONCEPT with two APIs and two visual systems (`app-stat-card` class in the first) |
| `frontend/src/pages/BOETransferLetter.tsx` (93 lines) vs `frontend/src/pages/TradeTransferLetter.tsx` (100 lines) | `diff` shows 59 changed lines. Both wrap `components/TransferLetterForm.tsx` (432 lines). Differences: fetch URL (`bill-of-entries/`, `trades/`), field mapping, prop names. BOE is routed (`AppRoutes.tsx:175-177`); trade is reached via `components/TransferLetterModal.tsx:6, 29` from `TradeForm.tsx:1635` | NEAR_CLONE wrappers. A fix to one must be checked against the other |
| `frontend/src/pages/reports/SionE1.tsx`, `SionE5.tsx`, `SionE126.tsx`, `SionE132.tsx` (10 lines each) over `SionNormReport.tsx` (443 lines) | Each returns `<SionNormReport sionNorm="E…" title="SION Norm E… - Parle Report" />`. Routed at `AppRoutes.tsx:28-31, 61-64` | THIN_WRAPPER, intentional. Low severity |
| `frontend/src/pages/ReconciliationPanel.tsx` (201 lines, route `/reconciliation`, `AppRoutes.tsx:198-201`, roles BOE_MANAGER, TRADE_MANAGER, ACCOUNT_ACCESS) vs `frontend/src/pages/ReconciliationIssues.tsx` (281 lines, route `/reconciliation-issues`, `AppRoutes.tsx:204-209`, roles add TRADE_VIEWER, BOE_VIEWER, TL_GENERATE) | Both use `StatCard`, `Tabs`, `Card` and the shared `reconciliation/reconciliationHelpers.ts`. `ReconciliationIssues` describes itself as a "read-only portfolio-wide discovery companion" (`AppRoutes.tsx:204-206`). Role gates differ between the two screens over overlapping data | OVERLAPPING_SCREENS. Intent is documented in code; the gate difference and the product question are recorded in files 20 and 19 (ISS-072) |

---

## 5. Large-file table

Counts are total lines (`wc -l`). Excludes migrations. Responsibility notes come from top-level definitions.

### 5.1 Backend (production, more than 1,000 lines)

| Path | Lines | Responsibilities (top-level) |
|---|---:|---|
| `backend/apps/license/models/core.py` | 2,625 | 31 model classes spanning licence, import and export items, balances, transfers, documents, SION planning rules, runs and profiles |
| `backend/apps/license/views/item_pivot_report.py` | 2,400 | `ItemPivotReportView` (lines 531-2274, about 1,744 lines in one class), `ItemPivotViewSet` (2275), about 25 helpers for Excel rendering, notification summary and planning split |
| `backend/apps/license/services/balance_calculator.py` | 2,149 | `LicenseBalanceCalculator` and a second class, 59 functions |
| `backend/apps/license/services/exporters/license_balance_excel.py` | 2,006 | Excel workbook rendering |
| `backend/apps/license/services/sion_planning_execution.py` | 1,741 | SION planning execution |
| `backend/apps/license/services/license_balance_ledger_builder.py` | 1,682 | Ledger row building, `LicenseBalanceLedgerBuilder` |
| `backend/apps/allotment/views_actions.py` | 1,680 | Four classes of allotment actions |
| `backend/apps/license/services/canonical_planning_service.py` | 1,449 | Canonical planning |
| `backend/apps/license/services/canonical_ledger_service.py` | 1,367 | Canonical ledger dataset |
| `backend/apps/license/services/exporters/license_balance_pdf.py` | 1,311 | PDF rendering |
| `backend/apps/license/views/license.py` | 1,209 | `LicenseDetailsViewSet` (lines 213-1209, about 1,000 lines in one class) plus `get_default_purchase_status_ids` |
| `backend/apps/license/utils/item_matcher.py` | 1,174 | Item matching |
| `backend/apps/license/serializers/license.py` | 1,134 | Licence serializers |
| `backend/apps/license/parsers/dfia_pdf.py` | 1,012 | DFIA PDF parsing |

Test files over 1,000 lines (5): `test_balance_ledger_views.py` (2,026), `test_balance_calculator.py` (1,556), `test_license_purchase_profit_report.py` (1,243), `test_ledger_summary_reconciliation.py` (1,113), `test_sion_planning_rules.py` (1,111).

### 5.2 Frontend (more than 1,000 lines)

| Path | Lines | Responsibilities (top-level) |
|---|---:|---|
| `frontend/src/pages/reports/ItemPivotReport.tsx` | 1,951 | 12 component definitions and one export |
| `frontend/src/pages/AllotmentAction.tsx` | 1,833 | 5 components, 2 exports |
| `frontend/src/pages/masters/MasterList.tsx` | 1,705 | Default `MasterList` component spanning lines 98-1,638 (about 1,540 lines), plus `groupLinkedTrades` and `MasterListActiveFiltersDisplay` |
| `frontend/src/pages/TradeForm.tsx` | 1,644 | Trade create and edit |
| `frontend/src/pages/masters/tables/LicensesTable.tsx` | 1,441 | Licence table with actions, merged-PDF handler (line 1028) |
| `frontend/src/components/planning/PlanningEditor.tsx` | 1,265 | Planning editor |
| `frontend/src/pages/masters/tables/LedgerTab.tsx` | 1,159 | Ledger tab |
| `frontend/src/pages/masters/MasterForm.tsx` | 1,137 | Master form |
| `frontend/src/pages/LicenseLedger.tsx` | 1,078 | Default `LicenseLedger` (lines 390-902, about 513 lines), plus `TransactionLedger` (57), `LicenseWiseLedger` (125), `SummaryItem` (373), `LicenseLedgerActiveFiltersDisplay` (903) |
| `frontend/src/components/LicenseBalanceModal.tsx` | 1,059 | Licence balance modal |

### 5.3 Notes on the four files named in the brief

- `backend/apps/license/views/item_pivot_report.py`: one class of about 1,744 lines carries report orchestration, format decisions and workbook layout. This is the largest single unit of responsibility in the backend.
- `backend/apps/license/views/license.py`: one viewset of about 1,000 lines combines CRUD, custom actions for PDFs, Excel, merged documents and balance operations.
- `frontend/src/pages/masters/MasterList.tsx`: one component of about 1,540 lines.
- `frontend/src/pages/LicenseLedger.tsx`: the default export is about 513 lines, and the file also holds two large inner components (`TransactionLedger`, `LicenseWiseLedger`). It is smaller than the other three but has the same mixing.

---

## 6. Circular-dependency heuristic

**Method (heuristic).** Grep of `^(from|import) apps.<name>` at module level (not indented, so not function-local). Excluded: `tests/`, `migrations/`, `management/`, `scripts/`. This shows import-time edges between apps and is not a full graph analysis. Counts are line counts, not distinct modules.

**Production app-level pairs with module-level imports in both directions**

| Pair | Forward edges (example) | Reverse edges (example) |
|---|---|---|
| `accounts` ↔ `core` | `accounts/views/auth.py:10-11` imports `core.middleware`, `core.throttling` | `core/serializers/models.py:3`, `core/views/views.py:4`, `core/views/media.py:31` import `accounts.permissions` |
| `core` ↔ `allotment` | `core/utils/transfer_letter.py:21` imports `allotment.scripts.aro` | `allotment/*` imports `core` (17 lines) |
| `license` ↔ `bill_of_entry` | `license/models/core.py:23` imports `bill_of_entry.models` | `bill_of_entry/serializers.py:7`, `views/parse_pdf.py:23` import `license` |
| `license` ↔ `allotment` | `license/models/core.py:22` imports `allotment.models`; `license/signals.py:12` | `allotment/views_actions.py:28-30` imports `license` |
| `license` ↔ `trade` | `license/signals.py:17` imports `trade.models`; `license/services/*` (8 lines) | `trade/models.py:16` imports `license.models`; `trade/serializers.py:11` imports `license.services` |

Pairs seen only through `management/`, `scripts/` or tests (not counted): `core` ↔ `license` (`core/scripts/ledger.py:12`, management commands), `core` ↔ `bill_of_entry` (`core/scripts/ledger.py:8`), `allotment` ↔ `bill_of_entry` (`allotment/management/commands/update_is_boe.py:7`).

**Model-level check (the stronger test).** The model modules import in one direction only:

- `license.models` imports `allotment.models`, `bill_of_entry.models`, `core.models`. None of those imports `license.models`.
- `trade.models` imports `license.models`, `bill_of_entry.models`, `core.models`. No reverse edge.
- `allotment.models` and `bill_of_entry.models` import only `core`.
- `core.models` imports `.constants` and `.sync.mixins` only.

**Result.** No import-time (model-level) cycle was found. The five production pairs above are cycles only at the service, serializer, signal and view layer. They are resolved at runtime by function-local imports in some places and do not block Django startup, but they increase blast radius. `license` has 92 module-level production edges into `core` and 21 into `accounts`, so changes in `core` affect most of the system.

---

## 7. Naming convention note

Counts exclude migrations and tests (backend) and cover all `src` text (frontend).

| Scope | `license` / `License` | `licence` / `Licence` | Notes |
|---|---|---|---|
| Backend production Python | 6,897 / 2,547 | 885 / 88 | `licence` in 93 files versus `license` in 217 files. `licence` mostly in comments, docstrings and business text (e.g. `apps/reconciliation/models.py:6, 197, 246`) |
| Frontend `src` text | 3,052 / 1,391 | 217 / 85 | Mixed UI text: "License ledger" (`LicenseDownloadRequests.tsx:14`) versus "Licence-level CIF" (`IndividualItemCifSwitch.tsx:69`), "Recalculate Licence Balance" (`ReconciliationPanel.smoke.test.tsx:98`) |
| Identifiers | `license` used throughout (models, URLs, modules, files) | Only one file name: `backend/apps/license/tests/test_licence_save_import_items.py` | Identifiers follow `license` almost everywhere |
| Docs | `docs/01`, `docs/03` use `license` (57 times) and `licence` 0 times | `docs/v1` and `CLAUDE.md` amendment use "licence-balance" | No single rule |

**Convention in use.** Code identifiers use `license`. Business text and comments often use `licence`. User-visible text is mixed. The brief asks that no convention be forced; this note records the state only.

---

## 8. Test-discovery gap

**Configuration.** `backend/pytest.ini`: `python_files = test_*.py`; `testpaths = tests apps`.

**Evidence (static).** pytest matches `python_files` against the basename, so `tests.py` is never collected.

| File | Lines | Test definitions | Collected? | Notes |
|---|---:|---:|---|---|
| `backend/apps/accounts/tests.py` | 185 | 9 | No | `apps/accounts/tests/` exists with two `test_*.py` files and no `__init__.py`. Those two are collected |
| `backend/apps/tasks/tests.py` | 29 | 2 | No | No `tests/` directory |
| `backend/apps/trade/tests.py` | 3 | 0 | No | Placeholder. `apps/trade/tests/` is a package (`__init__.py` present), which takes import precedence over the module, so `tests.py` is also unimportable |

Confirms BE-INV-08 (`docs/v1/system-audit/inventories/backend-app-inventory.md:55`). The total of collected test files is 247 (`test_*.py` under `apps/` and `tests/`).

Seven `test_*.py` scripts at `backend/` root are outside `testpaths`. Their collection depends on running pytest with explicit paths.

---

## 9. Legacy and compatibility shims

| Path | Shim | Status |
|---|---|---|
| `backend/apps/core/pagination.py:242-243` | `StandardResultsSetPagination = StandardPagination` ("Backward compatibility alias") | LIVE_ALIAS |
| `backend/apps/core/models.py:307-308, 341-342`; `backend/apps/core/serializers/models.py:271-273` | `ItemHeadModel` marked "Deprecated: Use ItemGroupModel instead". Still a `MasterSyncMixin` model, exported by `mds_payload.py:61` and `export_masters_mds.py:96`, and matched by `audit_masters`, `check_master_quality` and `merge_masters` | DEPRECATED_BUT_LIVE |
| `backend/apps/core/filtersets.py:101` | "Legacy company filters (mapped to exporter for backwards compatibility)" | LIVE_SHIM |
| `backend/apps/core/management/commands/sync_from_ge_server.py:224` | `_ = force  # Retained for CLI compatibility; external sync is not implemented here.` The command recalculates locally and does not sync | STUB_SHIM |
| `backend/apps/core/sync/service.py:44, 608`; `sync/tasks.py:45`; `sync/push.py:227`; `sync/serializers.py:19`; `sync/models.py:89` | Transition paths for legacy peers (deterministic replay key, "one-release compatibility path", "transition-only compatibility feed", retained `last_synced_at`) | LIVE_SHIM. No sunset date found |
| `backend/apps/bill_of_entry/serializers.py:55, 93, 100` | `legacy_available` lambda; "legacy licences retain..." opt-in guard | LIVE_SHIM |
| `backend/apps/core/utils/transfer_letter.py:381` | Fallback to "flat fields + global template_id for backward compatibility" | LIVE_SHIM |
| `backend/apps/reconciliation/views.py:286` | Parameter "compatibility but currently ignored" (always recalculates) | IGNORED_PARAM |
| `backend/apps/reconciliation/services/boe_link_reconciler.py:3, 50, 178` | Reconciles the legacy `LicenseTrade.boes` M2M into allocations | LIVE_LEGACY |
| `backend/apps/reconciliation/management/commands/backfill_boe_allocations.py` | One-time backfill of legacy `trade.boes` links | ONE_TIME_LEGACY |
| `frontend/src/utils/ledgerDisplayRows.ts:73, 106, 133` | "COMPATIBILITY SHIM" functions; used by `LicenseLedgerDetail.tsx:17` and `masters/tables/LicensesTable.tsx:51` | LIVE_SHIM |
| `frontend/src/utils/dateRangePresets.ts:20` | Re-export kept "for backward compatibility" from `LicenseLedger.tsx` | LIVE_SHIM |
| `frontend/src/utils/canonicalLedgerAdapter.js:59, 103, 134` | "compatibility with existing code" | DEAD_SHIM (ISS-070) |
| `frontend/src/components/ui/index.js:1, 20` | "Legacy UI primitives barrel ... Kept working during the ..." | DEAD_SHIM (ISS-070) |
| `frontend/src/components/Icon.tsx:14, 89` | Maps legacy Bootstrap icon names to lucide | LIVE_SHIM |
| `frontend/src/styles/tailwind.css:243, 392`; `frontend/src/App.css:12, 215` | Bootstrap-compatible button fallback and "legacy" wrapper classes | LIVE_CSS_SHIM |
| `frontend/src/components/TopNav.tsx:244, 361` | `masterEntities.filter(!m.deprecated)` (filter present; no entity flagged `deprecated` was verified) | UNVERIFIED |
| `frontend/src/types/canonicalLedger.ts:289` | "Deprecated fields (Phase 4C backward compatibility only)" | LIVE_TYPE_SHIM |
| `frontend/src/components/PageHeader.tsx:14` | "API-compatible with the legacy PageHeader" | LIVE_SHIM |

Repository artefact (not a shim, recorded in ISS-071): `backend/DFIA_COPY/` is tracked with 210 PDF files totalling about 217 MB.

---

## 10. Findings ISS-070 to ISS-074

### ISS-070: Frontend dead modules, unused dependency and misleading references (Medium)
- **Evidence.** Dead or unused, all confirmed in section 3: `layout/Sidebar.tsx`, `components/GlobalErrorBoundary.tsx`, `pages/errors/ServerError.tsx`, `components/AllotmentFormModal.tsx`, `pages/masters/tables/BalanceTab.tsx`, `pages/planning/ResidualPolicyEditor.tsx`, `services/api/masterApi.js` and `allotmentApi.js` (re-export only), `utils/canonicalLedgerAdapter.js` (new), `components/ui/index.js` (new, likely), `recharts` in `package.json` (new). `routes/config.js` `routes` export is consumed only by the dead Sidebar and names components that do not exist.
- **Effect.** The docs point readers at `AllotmentFormModal` (DOC-05). `ServerError` is defined but not routed, and the app's route table has no server-error screen. Whether a 5xx screen exists elsewhere was not checked.
- **Direction.** Record-only. Remove or route each module, and correct the docs. Remove the unused `recharts` dependency if the dashboard charts are not in scope (file 20).

### ISS-071: Backend orphaned and broken code, residue and tracked data (Medium)
- **Evidence.** `backend/lmanagement/tasks.py` (orphaned, depends on the missing `ebrc` app, contains a shared destructive task). `apps/core/signals_materialized_views.py` and `apps/core/tasks_materialized_views.py` (orphaned chain; materialized views themselves are live via migration 0003). `apps/core/cached_views.py` (module unused). `apps/accounting/` (only `.pyc` remains). 22 ad hoc scripts at `backend/` root, some named `verify_*` and `test_*`, not imported and outside pytest `testpaths`. `backend/DFIA_COPY/` is tracked with 210 PDFs (about 217 MB) in git.
- **Effect.** Future readers may treat orphaned code as live. A future import of `lmanagement/tasks.py` would register a destructive task that depends on an absent app. Tracked data files inflate the repository and may contain customer documents; the content was not reviewed.
- **Direction.** Record-only. Decide per module whether to delete, quarantine or document; decide whether `DFIA_COPY` belongs in version control.

### ISS-072: Duplicate and parallel implementations (Medium)
- **Evidence.** Section 4. StatCard exists in two incompatible APIs with two styles (five and one importers). The two transfer-letter pages are near-clones (59 changed lines) that both wrap `TransferLetterForm`. The two reconciliation screens overlap on the same domain and helpers, with different role gates (`AppRoutes.tsx:198-209`). Four SION wrappers are thin and intentional. `licenseBalanceHelpers.ts` exists twice under one basename with disjoint exports.
- **Effect.** A change in one copy does not reach the other. Imports of `licenseBalanceHelpers` can pick the wrong module. Visual drift between the two StatCards.
- **Direction.** Record-only. Name the authoritative copy of each pair; the SION wrappers are low priority.

### ISS-073: Test-suite integrity: vacuous tests, uncollected tests and placeholders (High)
- **Evidence.**
  - 74 test functions contain no `assert` and no `pytest.raises`: `backend/apps/license/tests/test_ledger_characterization_option_c.py` (49), `test_cross_output_parity_option_c.py` (15), `test_p0_defect_regression_option_c.py` (10). 73 of them have only comments and `pass` as their body. Example: `test_ledger_characterization_option_c.py` (the method `test_commission_excluded_from_license_balance`) states the expected balances in its docstring and comments and then passes.
  - The test-symbol register lists 12 of these classes as "Partial" with no assertion evidence (`docs/v1/09-traceability/test-symbol-register.tsv`, rows for `TestCrossOutputParityOptionC`, `TestBalanceFormulaOption_C`, `TestCompanyIsolationOption_C`).
  - 89 TODO markers sit inside those files, many in test bodies ("Once ledger builder is stable").
  - Three `tests.py` files are never collected (section 8). `apps/trade/tests.py` is an empty placeholder shadowed by its package.
  - Seven `test_*.py` scripts at backend root sit outside `testpaths`.
  - Not verified: the pytest.ini comment claims the suite has about 1,855 tests. Pytest was not run, so this count is unconfirmed.
- **Effect.** These tests inflate pass counts and give false assurance for the commission and cross-output parity behaviours they name. The v1 test evidence should not count them until they assert something.
- **Direction.** Record-only. Each of the 74 tests needs an assertion or an explicit skip with a reason; the three `tests.py` files need either a rename to `test_*.py` or an explicit decision to retire them.

### ISS-074: Oversized modules, mixed responsibilities and service-level cycles (Medium)
- **Evidence.** Section 5: 14 production Python files and 10 frontend files exceed 1,000 lines. The four named files each concentrate several responsibilities: `ItemPivotReportView` (about 1,744 lines in one class), `LicenseDetailsViewSet` (about 1,000 lines), `MasterList` (about 1,540 lines), and the `LicenseLedger` file. Section 6: five production app pairs import each other at module level (`accounts`↔`core`, `core`↔`allotment`, `license`↔`bill_of_entry`, `license`↔`allotment`, `license`↔`trade`); no model-level cycle.
- **Effect.** High blast radius for changes to `license` and `core` (92 and 21 module-level edges from `license`). Hard to review and test in isolation.
- **Direction.** Record-only. Structure changes belong to a separate refactor plan; no change is recommended in this audit.

---

## 11. Limits

- Static analysis only: grep, `wc`, `git ls-files`, `ast` parsing of test bodies. No tests were run. Pass or fail status is not claimed for any test.
- Dead-code status is based on name and path search. Dynamic imports built from strings were not searched beyond the module names. The module-graph check for `components/ui/index.js` was not run.
- Import-cycle result is a heuristic (section 6).
- Duplicate-logic judgments rest on structural comparison and a `diff` of the transfer-letter pages; behavioural equivalence was not tested.
- The contents of `backend/DFIA_COPY/` were not reviewed.
- Line numbers refer to the working tree on 2026-11-01, including uncommitted changes. Other agents are writing files in `docs/v1/` concurrently.
