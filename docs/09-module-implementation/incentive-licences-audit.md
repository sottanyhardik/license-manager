# Incentive Licences — Filter & List Audit (2026-11)

Scope of this pass: the backend list endpoint `/api/incentive-licenses/` and the
filter/sort contract the `/incentive-licenses` page depends on. This is **not**
the full 12-phase redesign programme; see *Not yet done* below.

## 1. Architecture (as found)

| Layer | File | Notes |
|---|---|---|
| Route | `frontend/src/utils/navigationUtils.js`, `hooks/usePageTitle.js` | `/incentive-licenses` |
| Page | `frontend/src/pages/masters/MasterList.tsx` | Generic master list; `entityName = 'incentive-licenses'` |
| Filter UI | `frontend/src/components/AdvancedFilter.tsx` | `*_from`/`*_to` → `__gte`/`__lte` (line ~51) |
| Row UI | `frontend/src/pages/masters/tables/IncentiveLicensesTable.tsx` | Card list, **not** a table; no column sorting |
| Config | `frontend/src/pages/masters/masterListConfig.ts` | Default filter `sold_status: ""` |
| Routing | `backend/apps/license/urls.py:49` | `router.register("incentive-licenses", ...)` |
| ViewSet | `backend/apps/license/views_incentive.py` | `create_viewset` on `MasterViewSet` |
| Generic engine | `backend/apps/core/views/master_view.py` | `apply_advanced_filters`, `CaseInsensitiveSearchFilter`, `OrderingFilter` |
| Serializer | `backend/apps/license/serializers/incentive.py` | Reads cached `sold_value` / `balance_value` |
| Model | `backend/apps/license/models/core.py:2091` | `Meta.ordering = ("-license_date", "license_number")` |

### Findings on the filter engine

- `MasterViewSet.filter_backends` is `[CaseInsensitiveSearchFilter, OrderingFilter]`.
  `DjangoFilterBackend` is **not** in the list, so `IncentiveLicenseFilter`
  (the `sold_status` FilterSet in `views_incentive.py`) is **never applied**.
  All real filtering runs through `apply_advanced_filters`, driven by the
  `filter` config. The FilterSet is dead code. *Not changed in this pass.*
- The comment on `apply_advanced_filters` says "OR logic", but the code combines
  everything with AND (`reduce(operator.and_, ...)`). Only multi-value lists
  inside one filter are OR. The code is correct; the comment is wrong. *Not changed.*

## 2. Defects found and fixed

### D-1 — Default list order ignored the declared order (fixed)

- **Symptom:** The list returned records in primary-key (creation) order, so the
  oldest-created licence appeared first.
- **Root cause:** `create_viewset` builds the base queryset as
  `model.objects.order_by("pk")` (`master_view.py:250`). The `ordering` key in
  the incentive config is never copied onto the generated viewset, so the
  declared default `['-license_date', 'license_number']` was never applied.
- **Fix:** `IncentiveLicenseViewSetClass.ordering = ['-license_date', 'license_number']`
  (`views_incentive.py`). `OrderingFilter` uses this as the default when no
  `?ordering=` is supplied.
- **Regression tests:** `test_default_ordering_is_newest_license_first`,
  `test_combined_filters_with_search_and_date_range`.

### D-2 — Sorting by most columns was silently ignored (fixed)

- **Symptom:** `?ordering=-license_date` (and any column other than
  `license_number`) was dropped without an error. The response came back in the
  default order, so the request looked like it had worked.
- **Root cause:** `ordering_fields` was taken from the config `ordering` key,
  which held only `['-license_date', 'license_number']`. DRF's `OrderingFilter`
  then only accepted `license_number`, and `license_date` was rejected because
  the stored name carried a leading `-`.
- **Fix:** Explicit `ordering_fields` list in the incentive config:
  `license_number, license_type, license_date, license_expiry_date,
  license_value, sold_value, balance_value, sold_status, is_active,
  exporter__name, port_code__name`.
- **Regression tests:** `test_list_ordering_by_license_date_descending_is_honoured`,
  `test_list_ordering_by_license_date_ascending_is_honoured`,
  `test_list_ordering_by_license_number_descending_is_honoured`.

## 3. Filter verification matrix

Test file: `backend/apps/license/tests/test_incentive_license_list_filters.py`
(21 collected tests, including 3 parametrised sold-status cases). Expected IDs come from a fixture of four licences (A–D) with
distinct exporter, port, type, active flag, sold status and date. They are not
computed from the code under test.

| Filter / case | Request param(s) | Test | Result |
|---|---|---|---|
| Exporter | `exporter=<pk>` | `test_filter_by_exporter` | pass |
| Port code | `port_code=<pk>` | `test_filter_by_port_code` | pass |
| License type | `license_type=RODTEP` | `test_filter_by_license_type` | pass |
| Active only | `is_active=true` | `test_filter_active_only` | pass |
| Inactive only | `is_active=false` | `test_filter_inactive_only` | pass |
| Sold: NO / YES / PARTIAL | `sold_status=…` (parametrised) | `test_filter_by_sold_status` | pass |
| Sold: All (empty) | `sold_status=` | `test_sold_status_empty_string_means_all` | pass |
| Date range (UI form) | `license_date__gte` + `__lte` | `test_license_date_range_uses_django_lookup_params_sent_by_ui` | pass |
| Date range (named) | `license_date_from` + `_to` | `test_license_date_range_from_and_to` | pass |
| Date from only | `license_date_from` | `test_license_date_range_from_only` | pass |
| Date to only | `license_date_to` | `test_license_date_range_to_only` | pass |
| Search licence no. (case-insensitive) | `search=lic-c` | `test_search_matches_license_number_case_insensitively` | pass |
| Search exporter name | `search=beta` | `test_search_matches_exporter_name` | pass |
| Exporter + type + sold | combined | `test_combined_exporter_license_type_and_sold_status` | pass |
| Search + date + active | combined | `test_combined_filters_with_search_and_date_range` | pass |
| Ordering default | — | `test_default_ordering_is_newest_license_first` | **fixed (D-1)** |
| Ordering `-license_date` | `ordering=-license_date` | `test_list_ordering_by_license_date_descending_is_honoured` | **fixed (D-2)** |
| Ordering `license_date` | `ordering=license_date` | `test_list_ordering_by_license_date_ascending_is_honoured` | pass |
| Ordering `-license_number` | `ordering=-license_number` | `test_list_ordering_by_license_number_descending_is_honoured` | pass |

Before the fix, 3 tests failed (default order, `-license_date`, and the combined
test that depends on default order). The full set of 21 passes after the fix.

## 4. Test results

Run with `TEST_DB_NAME=test_lmanagement_incentive_audit` (a dedicated test
database, so the shared test DB is not touched), `--no-cov`:

- `apps/license/tests/test_incentive_license_list_filters.py` + `test_incentive_serializers.py` → **24 passed**
- Related: `test_ledger_summary_reconciliation.py`, `test_masterdata_delete_protection.py`,
  `test_protected_media_view.py`, `test_canonical_ledger_service.py` → **62 passed**

Frontend typecheck, lint, unit tests and build were **not** run, because no
frontend source was changed in this pass.

## 5. Files changed in this pass

- `backend/apps/license/views_incentive.py` — default ordering and explicit `ordering_fields` (+19 lines)
- `backend/apps/license/tests/test_incentive_license_list_filters.py` — new (21 tests)
- `docs/09-module-implementation/incentive-licences-audit.md` — this report

No migrations. No database changes. Pre-existing uncommitted changes elsewhere
in the working tree were left as they were. Nothing has been committed or pushed.

## 6. Not yet done (remaining programme)

These parts of the original brief were **not** completed in this pass:

1. **Frontend table redesign.** The page is a card list with no column sorting.
   The brief's table requirements (sortable columns, sticky header, skeleton/empty/error states, responsive layout) are open.
2. **Filter UI redesign** (searchable exporter/port/type dropdowns, filter chips, active-filter count). Not started.
3. **URL state, back/forward and refresh behaviour** in the browser. Not tested in a browser.
4. **E2E tests and screenshots** at desktop/tablet/mobile. Not run.
5. **Financial audit.** `sold_value` and `balance_value` are cached columns and have not been reconciled against allotments and BOEs. Negative-balance handling has not been checked.
6. **Export (Excel/PDF) audit.** Not reviewed.
7. **Performance.** Query counts and N+1 checks on the list were not measured. The list uses `select_related('exporter', 'port_code')`, but the serializer's cached-value reads have not been profiled.
8. **Security review** of the export and write paths.
9. **Independent code review** of the diff.

## 7. Environment notes

- **ECC is not active in this environment.** The ECC marketplace is cloned at
  `~/.claude/plugins/marketplaces/ecc`, but `~/.claude/plugins/installed_plugins.json`
  is empty. Its agents and skills are not invocable from this session. The
  specialist agents in `.claude/agents/` were used as the available alternative.
- The project memory defines "ECC" as a design reference for the
  licence-balances module (`frontend/src/pages/licence-balances/`), not as
  Everything Claude Code. The brief's "ECC" meaning is therefore unresolved. This
  affects which screen is the visual reference for the redesign.
