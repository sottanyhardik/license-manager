# Services

> Living document. One row per service function as implemented in `backend/`.
> Rule: Views call services. Services call the ORM. Services never call other views.

## Service Inventory

Last updated: Phase 1-9 build on feature/V1 (2026-07-14).

### license — apps/license/services/balance_service.py

| Function | Signature | Purpose | Status |
|---|---|---|---|
| recompute_license_balance | `recompute_license_balance(license_id: int) -> None` | Recomputes LicenseBalance for a license: sums credit, debit, allotment, trade sub-totals. Writes back to LicenseBalance. | done |
| _compute_credit | `_compute_credit(license_id: int) -> Decimal` | Sums credit entries from the license ledger | done |
| _compute_debit | `_compute_debit(license_id: int) -> Decimal` | Sums debit entries from the license ledger | done |
| _compute_allotment | `_compute_allotment(license_id: int) -> Decimal` | Sums allotment amounts via _safe_get_model (avoids circular import) | done |
| _compute_trade | `_compute_trade(license_id: int) -> Decimal` | Sums trade usage via _safe_get_model — returns 0 while trade app is absent | pending (trade not built) |
| _safe_get_model | `_safe_get_model(app_label: str, model_name: str)` | Dynamic Django model lookup; returns None gracefully if app/model not installed | done |

### license — apps/license/services/license_service.py

| Function | Signature | Purpose | Status |
|---|---|---|---|
| create_license | `create_license(data: dict, user) -> LicenseDetailsModel` | Create license in transaction.atomic | done |
| update_license | `update_license(license_id: int, data: dict, user) -> LicenseDetailsModel` | Update license fields in transaction.atomic | done |
| delete_license | `delete_license(license_id: int, user) -> None` | Soft/hard delete with permission check | done |
| create_import_item | `create_import_item(license_id: int, data: dict, user) -> LicenseImportItemsModel` | Add import item to license; triggers balance recompute | done |
| update_import_item | `update_import_item(item_id: int, data: dict, user) -> LicenseImportItemsModel` | Update import item; triggers balance recompute | done |
| delete_import_item | `delete_import_item(item_id: int, user) -> None` | Remove import item; triggers balance recompute | done |

### allotment — apps/allotment/services/allotment_service.py

| Function | Signature | Purpose | Status |
|---|---|---|---|
| create_allotment | `create_allotment(data: dict, user) -> AllotmentModel` | Create allotment + items in transaction.atomic; dispatches Celery balance recompute | done |
| update_allotment | `update_allotment(allotment_id: int, data: dict, user) -> AllotmentModel` | Update allotment; dispatches Celery balance recompute | done |
| delete_allotment | `delete_allotment(allotment_id: int, user) -> None` | Delete allotment; dispatches Celery balance recompute | done |
| _dispatch | `_dispatch(item_ids)` | Calls recompute_license_balance_task.delay(iid) for each affected license item after commit | done |

### bill_of_entry — apps/bill_of_entry/services/boe_service.py

| Function | Signature | Purpose | Status |
|---|---|---|---|
| create_boe | `create_boe(data: dict, user) -> Any` | Create BOE header in transaction.atomic | done |
| update_row_detail | `update_row_detail(row_id: int, data: dict, user) -> Any` | Update a frozen BOE row detail | done |
| delete_row_detail | `delete_row_detail(row_id: int, user) -> None` | Delete a BOE row detail | done |
| resolve_dispute | `resolve_dispute(boe) -> dict[str, Any]` | Resolve all disputed rows for a BOE in bulk | done |
| resolve_dispute_row | `resolve_dispute_row(row_id: int, license_item_id: int, user) -> Any` | Resolve a single disputed row, linking it to a license item | done |
| merge_boe | `merge_boe(target_boe, source_boe_id: int) -> dict[str, Any]` | Merge rows from source BOE into target BOE | done |
| update_invoice_no | `update_invoice_no(boe, invoice_no: str) -> dict[str, Any]` | Update the invoice number on a BOE | done |
| fetch_allotment_item_details | `fetch_allotment_item_details(allotment_id: int, boe_id: int \| None = None) -> dict[str, Any]` | Fetch allotment item details for BOE row matching | done |
| update_product_name_for_boe | `update_product_name_for_boe(boe) -> dict[str, Any]` | Derive and update product name for a single BOE | done |
| bulk_update_product_names | `bulk_update_product_names() -> dict[str, Any]` | Bulk update product names across all BOEs | done |

### tasks — apps/tasks/services/task_service.py

| Function | Signature | Purpose | Status |
|---|---|---|---|
| create_task | `create_task(data: dict, user) -> Task` | Create a new workflow task | done |
| complete_task | `complete_task(task: Task) -> Task` | Transition task to completed state | done |
| reject_task | `reject_task(task: Task, by_user, reason: str = "") -> tuple` | Transition task to rejected state; records reason | done |
| reopen_task | `reopen_task(task: Task) -> Task` | Reopen a completed or rejected task | done |
| add_remark | `add_remark(task_id: int, text: str, user) -> TaskRemark` | Append a remark to a task | done |

### dashboard — apps/dashboard/services/dashboard_service.py

| Function | Signature | Purpose | Status |
|---|---|---|---|
| get_dashboard_stats | `get_dashboard_stats(user: Any) -> dict` | Aggregate KPI stats (license count, BOE count, allotment totals, etc.) | done |
| get_license_utilisation_chart | `get_license_utilisation_chart(user: Any) -> list[dict]` | Per-license utilisation percentages for Recharts bar chart | done |
| get_monthly_activity | `get_monthly_activity(user: Any) -> list[dict]` | Month-by-month activity counts for Recharts line chart | done |
| get_expiring_licenses | `get_expiring_licenses(user: Any) -> list[dict]` | Licenses expiring within the alert window | done |
| _boe_model | `_boe_model()` | _safe_get_model wrapper for BillOfEntry (avoids circular import) | done |

### reports — apps/reports/services/

| Function | File | Signature | Purpose | Status |
|---|---|---|---|---|
| generate_balance_report | balance_report.py | `generate_balance_report(license_ids: list, output_format: str) -> dict` | Generate balance report for selected licenses in given format | done |
| generate_item_report | item_report.py | `generate_item_report(license_ids, output_format, ...) -> dict` | Generate per-item usage report | done |
| generate_ledger_report | ledger_report.py | `generate_ledger_report(license_id: int) -> dict` | Generate ledger (debit/credit history) for one license | done |
| generate_pivot_report | pivot_report.py | `generate_pivot_report(...) -> dict` | Generate pivot/cross-tab report across licenses | done |

### trade — apps/trade/services/ (pending)

| Function | File | Purpose | Status |
|---|---|---|---|
| create_trade | trade_service.py | Create trade + lines + payments atomically | pending (app not built) |

## Service Rules

1. All database writes inside `transaction.atomic()`
2. Services return domain objects, never HTTP responses
3. Services raise `ValidationError` or `PermissionDenied` — views catch and format
4. Balance recompute dispatched via Celery task (not called inline from signals)
5. No circular imports between services
