# Backend app and model inventory

Source: read-only inventory by an Explore agent (2026-11-01), with spot-checks by the lead. Labels: VERIFIED = the lead checked the file or ran a grep; SUSPECTED = indirect or heuristic.

## Apps (INSTALLED_APPS, `backend/lmanagement/settings.py:122-150`)

| App | Models | Views (top-level / factory) | Serializers | Migrations | Test files | Purpose |
|---|---|---|---|---|---|---|
| accounts | 2 | 7 / 0 | 3 | 6 | 3 | Custom User, JWT auth, password reset, user and role management |
| allotment | 5 | 1 / 1 | 2 | 16 | 12 | Licence-quantity allotments, allocation versions, shortfalls, audit events |
| bill_of_entry | 2 | 2 / 1 | 2 | 14 | 1 | Bill of Entry records, PDF parsing, export |
| core (incl. core/sync) | 30 | 20 / 17 | 41 | 19 | 23 | Master data, activity log, throttling, health, master sync framework, materialized views |
| license | 33 | 26 / 2 | 30 | 56 | 182 | Licence register, ledger upload, SION planning engine, reports, incentive licences, package jobs |
| reconciliation | 6 | 1 / 0 | 0 | 5 | 6 | Invoice, BOE and allotment reconciliation |
| tasks | 2 | 1 / 0 | 2 | 1 | 1 | User task tracker |
| trade | 9 | 2 / 3 | 5 | 10 | 8 | Trades, trade lines, payments, tokenised invoice-document links |
| accounting | 0 | 0 | 0 | 0 | 0 | **Not an app.** Only `__pycache__` directories remain. Not in INSTALLED_APPS. |

Total concrete models: 89. Abstract bases excluded: `AuditModel`, `SyncTimestampModel`, `SyntheticUidMixin`, `MasterSyncMixin`.

## Model locations

Full list with file:line is in the agent output; the main files are:

- accounts: `apps/accounts/models.py` (`User`, `RevokedAccessToken`)
- core: `apps/core/models.py` (23 models: companies, ports, HS codes, SION norms, items, exchange rates, `ActivityLog`, `CeleryTaskTracker`, etc.) and `apps/core/sync/models.py` (7 sync models)
- allotment: `apps/allotment/models/core.py` (`AllotmentModel`, `AllotmentItems`), `allocation_version.py`, `shortfall.py`, `audit_event.py`
- bill_of_entry: `apps/bill_of_entry/models.py` (`BillOfEntryModel`, `RowDetails`)
- license: `apps/license/models/core.py` (31 models: `LicenseDetailsModel`, `LicenseExportItemModel`, `LicenseImportItemsModel`, SION planning models, `LicenseBalance`, `LicenseFlags`, `LicenseOwnership`, package job models, `IncentiveLicense`), `apps/license/models/invoice.py` (`Invoice`, `InvoiceItem`)
- reconciliation: `apps/reconciliation/models.py` (6 models)
- tasks: `apps/tasks/models.py` (`Task`, `TaskRemark`)
- trade: `apps/trade/models.py` (9 models: `LicenseTrade`, `LicenseTradeLine`, `LicenseTradePayment`, `TradeInvoiceDocument`, `InvoiceDocumentAccessToken`, audit models)

## Routes

- Root (`backend/lmanagement/urls.py`): `api/auth/`, `api/` (license, allotment, bill_of_entry, trade, reconciliation, tasks), `api/masters/` (core), `api/sync/`, `api/health/`, `api/mds/status/`, `api/schema/`, `api/docs/`, protected media at `api/media/`, SPA catch-all.
- Each app's `urls.py` registers its routers (license has 13 routers and 13 report paths).

## Celery (VERIFIED spot-checks)

- 25 real task definitions across `apps/license/tasks.py`, `apps/core/tasks.py`, `apps/core/sync/tasks.py`, `apps/core/tasks_materialized_views.py`.
- **VERIFIED:** three beat-schedule entries name tasks with no definition anywhere in the repository: `license.tasks.sync_all_licenses`, `identify_licenses_needing_update`, `cleanup_old_task_records` (`lmanagement/celery.py:47,59,67,83`). The grep for each name returned zero definitions.

## Verified observations

| ID | Label | Observation | Evidence |
|---|---|---|---|
| BE-INV-01 | VERIFIED | `apps/accounting` is a stale directory with no app configuration; not an app. | `settings.py:122-150` |
| BE-INV-02 | VERIFIED | `apps/core/signals_materialized_views.py` has no Python importer. The materialized-view refresh tasks it wires are therefore not connected by any code path. Runtime effect SUSPECTED. | grep returned 0 importers |
| BE-INV-03 | VERIFIED | `apps/core/sync/tasks.py` has no importer, and `apps.core.sync` is not in INSTALLED_APPS, so Celery autodiscovery does not register its `sync.*` tasks. SYNC beat entries are gated by `SYNC_ENABLED`. | `apps/core/sync/tasks.py`; `lmanagement/celery.py` |
| BE-INV-04 | VERIFIED | `apps/core/management/commands/rqworker.py` imports `rq`; neither `rq` nor `django-rq` is in `requirements.txt`. The command presumably fails when run (CommandError behaviour SUSPECTED). | `rqworker.py:68-94`; `requirements.txt` |
| BE-INV-05 | VERIFIED | `AppConfig.ready()` in `apps/core/apps.py:14-20` swallows `ImportError` around signal wiring, so broken imports fail silently. | `apps/core/apps.py` |
| BE-INV-06 | VERIFIED | Three core viewsets (`SIONExportViewSet`, `SIONImportViewSet`, `ItemHeadViewSet`) are built but not routed. | `apps/core/views/views.py:349,363,414`; `apps/core/urls.py` |
| BE-INV-07 | VERIFIED | `lmanagement/tasks.py` is orphaned (not autodiscovered, not imported) and imports modules that do not exist (`ebrc.models`, `shipping_bill.models`). | `lmanagement/tasks.py:20,43` |
| BE-INV-08 | VERIFIED | `apps/trade/tests.py` is a placeholder. `apps/accounts/tests.py` and `apps/tasks/tests.py` are never collected by pytest (`python_files = test_*.py`). | `pytest.ini`; the files |
| BE-INV-09 | VERIFIED | Tracked in git: `backend/.env_dgft` (contents not read), `backend/DFIA_COPY/*.pdf` (licence PDFs). Review whether these belong in version control. | `git ls-files` |
| BE-INV-10 | SUSPECTED | Duplicated background-job tracking (`Task`, `CeleryTaskTracker`) and seven separate audit or log tables. | model docstrings |
| BE-INV-11 | SUSPECTED | Several models have no reference outside their defining file (`CeleryTaskTracker`, `SionPlanningRun`, `LicensePackageArtifact`, `StatusModel`, `OfficeModel`, `AlongWithModel`). String or reverse references were not checked. | grep |
| BE-INV-12 | SUSPECTED | Six `DefaultRouter` instances share the `api/` prefix; only the first root view is reachable. | `lmanagement/urls.py` |

## Modules with no tests (SUSPECTED, basename heuristic)

Listed in the agent output. Largest groups: `apps/license` (around 20 modules, including `services/custom_ledger_pdf.py`, `services/planning_allocation.py`, `services/report_service.py`, `views/ledger_upload.py`), `apps/core` (exporters and PDF helpers), `apps/trade` (purchase and bill-of-supply PDFs, final-party classification). A module may still be covered indirectly through endpoint tests.

## Limits

No Django process, Celery worker or database was started. Counts are grep-based. Serializer counts may include nested definitions.
