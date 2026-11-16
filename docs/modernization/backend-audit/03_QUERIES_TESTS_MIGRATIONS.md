# Backend audit 03 - queries, tests, migrations, lint

Read-only audit, 2026-11-16, branch feature/v5. Licence and BOE lists (commit 81163117) excluded; they are covered in PERFORMANCE_REPORT.md.
Measurements: DRF APIClient (force_authenticate superuser) against clone `lmanagement_restore_verify_live_20261116`
(settings NAME asserted before each run, `SET TRANSACTION READ ONLY`, rolled back). Script: /tmp/audit3/measure.py (not in repo).

## 1. Static N+1 scan and measurements

Measured (queries per request, `?page_size=10` / `?page_size=50`; rows actually returned in brackets):

| # | Endpoint | ps=10 | ps=50 | Cause (file:line) | Severity |
|---|----------|-------|-------|-------------------|----------|
| 1 | GET /api/license-item-plans/ | 293 (10 rows), 199 ms | 1848 (50 rows), 1246 ms | ~37 queries/row. `LicenseItemPlanViewSet` queryset `apps/license/views/item_plan.py:105-109` selects import_item/license/item_name only. `LicenseItemPlanSerializer` (`apps/license/serializers/incentive.py:77`) then hits per row: `obj.planning_rule` and `SionPlanningRule...exists()` in `get_needs_rebuild` (:380-388), `obj.modified_by` (:242), `obj.license.get_balance_cif` (:252, `license/models/core.py:330`), plus `reconcile_license_plans` (`planning_usage_reconciliation.py:221`) cached per licence only. Top query tables: trade_licensetradeline 480, bill_of_entry_billofentrymodel 240, correlated subselects 240, licenseexportitem 155 (at 50 rows). | HIGH (grows linearly, planning page) |
| 2 | GET /api/masters/sion-classes/ | 52 | 253 | `SionNormClassViewSet` (`apps/core/views/views.py:320`) uses `SionNormClassNestedSerializer` (`core/serializers/models.py:127`) with 5 nested lists per row (export/import/note/condition/...) and no prefetch: ~5 queries/row. | MEDIUM-HIGH (about 2000 norm rows; default is_active filter limits) |
| 3 | GET /api/masters/item-names/ | 29 | 120 | `ItemNameSerializer.get_norm_details` (`core/serializers/models.py:313`) uses `obj.norms.order_by(...).values_list` which bypasses any prefetch (1 query/row); `get_sion_norm_class_label` (:300-305) touches `obj.sion_norm_class` FK (core_sionnormclassmodel 118 at 50 rows). Fix: prefetch `norms` and sort in Python; select_related `sion_norm_class`. | MEDIUM |
| 4 | GET /api/sion-planning-rules/ | 29 (10) | 49 (17 rows exist) | ~2-3/row: queryset `views/sion_planning_rule.py:224-227` lacks prefetch of unit_value rows / percentage rows (unitvaluerow 17, percentagerow 17) and `import_item` (serializer `incentive.py:477-480`). | MEDIUM (small table, rule editor) |
| 5 | GET /api/auth/users/ | 5 | 5 | Not N+1: prefetch works (2 users). OK. | none |
| - | GET /api/license-items/ | 3 | 3 | OK. | none |
| - | GET /api/masters/companies/, hs-codes/, activity-logs/ | 1-2 | 1-2 | OK (activity-logs `select_related('user')`, `pagination_class=None` at `core/views/activity_log.py:27`: the comment says DRF default but None disables pagination, so the list is UNPAGINATED. MEDIUM - core_activitylog is large). | MEDIUM |

Not measured, static findings only (viewsets all defined with `get_queryset`/select_related except as noted):
- `apps/allotment/serializers.py:123` (`obj.item.utilization_plans.all()`), `:224` (`obj.allotment_details.count()` bypasses prefetch), `:263,277` (per-row `export_license.all()` and `LicenseItemPlan.objects.filter(...)`): detail/nested serializers; list path has `test_allotment_list_performance_contract.py` using `ListProjectionDecimalField` (:11).
- `apps/license/serializers/license.py:378,413` (`get_billed_no_boe*` aggregate per licence), `:1010` (`.exists()`), `:1026` (`replan_requests...first()`), `:1049,1057` (`license_documents.filter(...).exists()` x2): per-row queries in `LicenseDetailsSerializer`; the list path was optimised in 81163117, detail/other callers (reports, `views_actions.py`) may still pay it.
- `apps/trade/serializers.py:240,357-362` already prefetch-aware (guarded by `_prefetched_objects_cache`, `test_trade_list_query_budget.py`); `get_incentive_license` iterates `obj.lines.all()` + `line.sr_number.license` (FK deref per line unless prefetched).

Loops issuing queries (static AST-ish scan, 41 hits, key ones):
- Exporters, `.exists()` on a prefetched/`all()` relation inside per-item loop (defeats prefetch, 1 query per import item): `license/services/exporters/license_balance_excel.py:164,837,1331,1435`; `license_balance_pdf.py:784,1056`. Severity MEDIUM-HIGH (bulk ledger/balance exports scale with licences x items). Fix: use `bool(item.items.all())` after prefetch.
- `license/services/license_balance_ledger_builder.py:1041` (`InvoiceBOEAllocation.objects.filter` per trade line) and `:1184` (`BOEAllotmentAllocation.objects.filter` per row): HIGH for ledger builds with many rows; batch with `__in` + dict.
- `license/views/inventory_balance_viewset.py:53` (`LicenseImportItemsModel.objects.filter(...)` per norm): MEDIUM; one aggregate with `values('norm').annotate(Count)`.
- `bill_of_entry/serializers.py:366` (`AllotmentModel.objects.get(id=...)` in loop over removed ids), `license/views_actions.py:251` (`LicenseDetailsModel.objects.get(license_number=...)` per payload item in bulk action): MEDIUM; use `in_bulk`.
- `license/serializers/incentive.py:563,598` (`import_item.norms.filter(pk=...).exists()` per row in write validation): LOW-MEDIUM.
- `license/services/condition_pool.py:99` (RowDetails query per condition), `planning_actual_target_mapping.py:57`, `planning_operational_snapshot.py:40`, `canonical_planning_service.py:599`, `sion_planning_execution.py:1603`, `item_pivot_report.py:1041` (comment says prefetch cache used, verify), `bill_of_entry/models.py:346-351` (`sr_items.exists()` inside item_details loop): MEDIUM, planning/reporting paths.
- `license/tasks.py:145,324,363,589`, `signals.py:257,372,382,478`, `core/sync/*`: per-id `.update()` in Celery/sync loops; LOW (background, bounded).
- Real bug found by pyflakes while scanning: `apps/license/views/ledger.py:154,156` use `LicenseLedgerPackageJob` without importing it in `_enqueue_download_request` (the import at :44 is local to another method). NameError after successful `.delay()`; the `except Exception` handler at :156 raises the same NameError uncaught inside `transaction.on_commit`, so `root_task_id` is never saved and `dispatch_failed` is never recorded. HIGH (correctness; needs import fix; not changed here).

## 2. Other query inefficiencies

- `len(queryset)` anti-pattern: none found by regex (len() hits are on lists).
- `if queryset:` / truthiness on `.filter()`: none matched by regex.
- Python sum over DB rows where `aggregate(Sum)` fits: `license/views/license.py:438` and `license/services/planning_usage_reconciliation.py:383` (`sum(Decimal(v) for v in LicenseExportItemModel...values_list('cif_fc'))`: fetches every export item; replace with `aggregate(Sum('cif_fc'))`; LOW volume per licence, MEDIUM per call count); `allotment/scripts/allotment_pdf.py:119-120` (two passes of `allotment_details.all()` summing `qty`/`cif_fc`; `float()` on money too, flag for cif-balance-auditor); `license/views/ledger.py:180` sums over a list (fine).
- `.count()` sites: 39 outside tests/commands (not individually audited); `allotment/serializers.py:224` `obj.allotment_details.count()` per row.
- `.only()/.defer()`: only 10 uses repo-wide; none in the Excel/PDF exporters or `core` master exports (`license_balance_excel.py` loads full `LicenseImportItemsModel` and `LicenseDetailsModel` rows). `.iterator()` used 27 times. Opportunity: LOW-MEDIUM.
- Repeated identical queries per request: `get_balance_cif` (`license/models/core.py:330`; `cached_property` starts ~:362) is read per row in `LicenseItemPlanSerializer.get_actual_license_balance_cif` (:252); `SionPlanningRule.objects.filter(is_active=True)...` runs once per plan row in `get_needs_rebuild` with identical predicate for plans of the same rule (cache per `(stable_key|sion,name,priority,strategy)` in serializer context); per-licence `reconcile_license_plans` is correctly cached in context (`incentive.py:254-261`).

## 3. Test architecture

Counts (`grep 'def test_'`): 
| Location | Test functions | In CI? |
|---|---|---|
| backend/tests/ (14 files) | 235 | yes (`ci.yml:108`, `quality-gate.sh:51`) |
| backend/apps/license/tests/ (181 files) | 1669 | yes (`ci.yml:111`) |
| backend/apps/core/tests/ (23 files) | 583 | yes (`ci.yml:111`) |
| backend/apps/allotment/tests/ (12 files) | 109 | NO |
| backend/apps/reconciliation/tests/ (6) | 75 | NO |
| backend/apps/trade/tests/ (8) + trade/tests.py (0) | 60 | NO |
| backend/apps/bill_of_entry/tests/ (2) | 12 | NO |
| backend/apps/accounts/tests/ (2) + accounts/tests.py | 9 + 9 | NO |
| backend/apps/tasks/tests.py | 2 | NO |
| repo-root tests/e2e (selenium/QA scripts, 189 `def test_`; mostly `qa_phase*.py` that pytest does not match, only `test_api_smoke.py`, `test_pages_selenium.py` match) | 189 | NO (needs live stack) |
| repo-root tests/deployment | shell script | NO |

Collection facts: `backend/pytest.ini` has `testpaths = tests apps` (comment claims both trees are collected) and `addopts` includes `--cov=. --cov-report=html` (slows every run). But CI (`.github/workflows/ci.yml:108,111`) and `scripts/dev/quality-gate.sh:51-52` run only `tests/`, `apps/license/tests`, `apps/core/tests`. Net: about 280 backend tests (allotment, trade, reconciliation, BOE, accounts, tasks) are never run in CI, including `test_trade_list_query_budget.py`, `test_boe_list_query_count.py`, `test_allotment_list_performance_contract.py`, `test_trades_contract_parity.py`, `test_allocation_service.py` (reconciliation) - the very contracts added to protect the 81163117 perf work. Also `--import-mode=importlib` is used for the second command only. HIGH process gap; fix is adding `pytest apps` (or the missing dirs) to ci.yml and quality-gate.sh.

Coverage map by area (by test filenames; counts approximate):
- Balance engine: strong (test_balance_calculator, test_balance_cif_single_source, test_ledger_*, test_canonical_ledger_service, test_negative_balance, test_dashboard_balance_cif, test_license_list_balance_consistency, test_inr_reconciliation_golden_case, golden/dual-run/characterisation tests).
- Planning/SION: very strong (about 90 files: e1/e5/e126/e132/a3627/c969, sion_*, split_*, shortage_*, plan_*, replan).
- BOE: thin and outside CI: `bill_of_entry/tests` 2 files (hide service, list query count) plus `tests/test_api_boe.py`, `test_boe_script_helpers.py`, `license/tests/test_boe_invoice_representation.py`, overview_boes view. No tests for `bill_of_entry/views/boe.py` write paths (create/update/allotment unlink at `serializers.py:366`) or `parse_pdf.py` beyond hs autocreate.
- Allotment: 12 files (cif validation, expiry, group plan cap, plan-line balance) but none in CI; `allotment/services/{allocation_service,filter_service,validation_service,allocation_availability}.py` have no direct imports in tests (covered only indirectly through API).
- Trade/invoice: 8 files outside CI; `trade/views.py` (719 lines), `bill_of_supply_pdf.py` (793), `purchase_invoice_pdf.py` (741), `final_party_classification.py`, `sale_classification_review.py` have no direct tests.
- Reconciliation: 6 files outside CI; `reconciliation/views.py` (316) and `services/warning_service.py` untested directly.
- Ledger: strong (license_ledger_*, ledger_security, package jobs). Note `ledger.py:154` NameError above is not caught by any test (probably mocked).
- API contract: `tests/test_api_*.py` (license, boe, trade, allotment, core, integration), `test_url_routing`, `core/tests/test_openapi_schema.py`, trade contract parity.
- Permissions: `tests/test_authorization_permissions.py`, `license/tests/test_idor_fixes_p0_p1.py`, `test_planning_security.py`, `test_ledger_security.py`, `test_license_ledger_export_security.py`; accounts views (`auth.py`, `password.py`, `user_management.py`) have no direct tests beyond 18 trivial accounts tests and no throttle tests besides `core/views/throttle_status.py` (260 lines, untested).
- Services/modules with no direct import in any test (heuristic): `license/services/{license_overview_*(4), item_usage, item_pivot_aggregation, report_service, plan_lifecycle, plan_reporting, norm_plan, planning_allocation, planning_actual_target_mapping, planning_operational_snapshot, scoped_sion_planning, custom_ledger_pdf}`, `license/serializers/_license_write.py` (895 lines, central write path), `core/utils/transfer_letter.py` (836), `core/utils/pdf_helpers.py`, `pdf_utils.py`, `core/serializers/{fields,mixins}.py`, `tasks/services/task_service.py`. Some are covered via view tests (overview views have tests), so treat as a lead, not proof.
- Performance contracts exist for: license list, BOE list, trade list, allotment list. Missing for: license-item-plans, masters (item-names, sion-classes), sion-planning-rules, exports.

Fixtures/factories: factory_boy and model_bakery are NOT in requirements; no factory usage. Pattern is ad-hoc: `backend/conftest.py` fixtures (`test_company`, `test_license` with 3 import items, `test_bill_of_entry`, `test_trade`, `api_client`, `authenticated_client`, `admin_user`), `apps/core/tests/sync_factories.py`, `report_assertions.py`, `license/tests/planning_contract_support.py` and `parity_utils.py`, plus per-file `Model.objects.create` builders. Many tests use `force_authenticate`-style clients.

## 4. Migrations (additions only; see MIGRATION_REGISTER.md for the rest)

`makemigrations --check --dry-run` against the clone: "No changes detected" (CI runs the same at `ci.yml:105`).

Latest per app: accounts 0006_repoint_legacy_user_fks; allotment 0015_plan_identity_to_business_dimensions; bill_of_entry 0013_repair_boe_number_date_unique_constraint_columns; core 0019_increase_natural_key_length_to_2000; license 0057_licensebalance_balance_cif_signed; reconciliation 0005_alter_reconciliationlog_action; tasks 0001_initial; trade 0011_tradepairaudit_survive_trade_delete. Counts: 6/16/14/19/57/5/1/11. The register's license row says 56 / latest 0056; 0057 is missing from the table (AlterField `licensebalance.balance_cif`, max_digits=15, decimal_places=2, default 0.00; only the narrative in IMPLEMENTATION_PROGRESS mentions it).

RunPython without `reverse_code`: none. Every one passes a reverse (real or `noop`). Noop-reversal on data-deleting/mutating steps is already classified in the register. New: `0052_license_ledger_server_ready_states` and no others use RunSQL (both with reverse SQL).

Operations unsafe on large tables (no `AddIndexConcurrently`, no `atomic = False` except allotment 0015, license 0002/0005, trade 0008 which use non-atomic or heavy data steps, justified in docstrings):
- `bill_of_entry/0007_rowdetails_planning_target_mapping.py:8-10`: AddField on RowDetails (core BOE table): FK with `db_index=True`, PROTECT; plus `planning_mapping_status` CharField `default="UNMAPPED_AMBIGUOUS"` `db_index=True` (index build, non-concurrent, ACCESS EXCLUSIVE/SHARE lock during build). Followed by RunPython `0009` `promote_detail_targets` over RowDetails. Applied already; relevant for any re-deploy to a fresh large copy.
- `bill_of_entry/0004_...py:47`: non-concurrent AddIndex on rowdetails.is_hidden (boolean, low selectivity; plus 3 AddFields).
- `core_activitylog`: only in `core/0001_initial`; no later index/AddField migrations, so no lock risk from migrations (the table is read unpaginated by the API, see section 1).
- `license/0056` (3 nullable DecimalFields, metadata-only on PG11+; safe), `license/0057` AlterField (same type, default only; no table rewrite; the Django default is Python-side, safe), `license/0054` AddField unique UUID then AlterField to unique+default (unique index build on package-job table, small).
- `trade/0011`: 3 AddFields + RunPython backfill (noop reverse) on trade pair audit table; moderate.
Squash candidates: license (57 files, many seed/backfill RunPython 0014-0049, 0036-0042 mappings) and core (19, seeds 0007-0011) are candidates, but cross-app cycles (core<->license, license<->boe, license<->trade) and noop reverses make squashing risky; no `replaces` exist. Recommend squashing only after all environments are at head, using `squashmigrations` with `--no-optimize` review; no action advised now.

## 5. Lint / typecheck

- No ruff, mypy, black, isort, pyproject.toml, setup.cfg, .flake8, or pre-commit config exists (repo root or backend). `flake8==7.1.1` is pinned in `backend/requirements-test.txt:20` but unconfigured and not run in CI. CI Python steps (`ci.yml`) are: makemigrations --check, pytest tests/, pytest apps/license/tests apps/core/tests; MDS job similar. CI lint exists only for the frontend (`npm run lint`, `ci.yml:33`). `quality-gate.sh` has no Python lint either.
- pyflakes (`.venv/bin/python -m pyflakes apps`): 543 messages. Categories: F401 unused imports 271; F811 redefinition of unused name about 180 (lines 29/34/35/16 pattern: duplicated `from` imports/test helper redefinitions); F841 unused local 57; F541 f-string without placeholders 30; F821 undefined name 3 (`ledger.py:154,156` real NameError; `sion_planning_execution.py:1215` is a string annotation, benign); plus star-import notice `license/models/__init__.py:7`.
- flake8 (F,E7,W6, max-line 200): F401 246, F811 180, E701 59, E702 59 (one-line compound statements, concentrated in `license/views/ledger.py`), F841 57, F541 30, E731 6, E704 4, F821 3, E741 2.
- Suggested minimal gate (not applied): CI step `flake8 apps --select=F821,F811,E9` (zero-noise after fixing 3 F821/ledger bug) and widen pytest to `apps`.
