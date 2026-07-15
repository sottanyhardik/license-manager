# Improvement Register

> **All known issues, technical debt, and improvement opportunities.**  
> Ranked: CRITICAL / HIGH / MEDIUM / LOW  
> Last updated: 2026-07-15.

---

## CRITICAL

| ID | Module | Issue | Details | Fix |
|---|---|---|---|---|
| C-001 | Reports | Balance report diverges from live balance formula | `balance_report.py` re-implements aggregation without the trade component. Reports show incorrect available CIF for licenses with trade sales. | Refactor to call `balance_service._compute_*` functions or `recompute_license_balance()` |

---

## HIGH

| ID | Module | Issue | Details | Fix |
|---|---|---|---|---|
| H-001 | Trade | PDF generation blocks gunicorn workers | `generate_purchase_invoice_pdf` and `generate_bill_of_supply_pdf` are synchronous in the view. `generate_trade_pdf_task` Celery stub exists but is not wired. Under load, all workers can stall on PDF rendering. | Connect `generate_trade_pdf_task` to the PDF endpoints; return `task_id` + poll pattern |
| H-002 | License | Single plan per import item not DB-enforced | `LicenseItemPlan` allows multiple rows per `import_item`. The API serializer reads only `.first()`. Business logic assumes one plan. | Add `unique_together = (import_item,)` constraint or at minimum a `unique` kwarg |
| H-003 | Reports | All 4 report services independently timestamp output | `datetime.now(tz=timezone.utc).isoformat()` copied into each report dict. If format changes, 4 files need updating. | Extract to a `report_envelope(data)` utility in `reports/utils.py` |
| H-004 | Reports | item_report and pivot_report share ~18 lines of identical queryset-building | Copy-paste will diverge when one is updated. | Extract to `_build_item_queryset(filters)` in `reports/utils.py` |

---

## MEDIUM

| ID | Module | Issue | Details | Fix |
|---|---|---|---|---|
| M-001 | License | `ImportItemSerializer` N+1 for planning fields | `get_planned_quantity` and `get_planned_cif_fc` each issue one `LicenseItemPlan` query per import item during serialization. For a license with 20 items: 40 extra queries. | Use `prefetch_related("utilization_plans")` on the import item queryset; access via `item.utilization_plans.first()` from prefetch cache |
| M-002 | License | `LicenseBalanceSerializer` N+1 for breakdown fields | `get_total_authorised`, `get_total_debited`, `get_total_allotted` each call a separate aggregation query. 3 extra queries per license detail request. | Store these values in `LicenseBalance` table (requires migration/legacy table change), OR compute in one pass inside `recompute_license_balance` and cache |
| M-003 | Allotment | `update_allotment` does not handle AllotmentItems changes | AllotmentItems qty/cif changes require delete+recreate allotment. No dedicated "edit item" flow. | Add `update_allotment_item(item_id, data, user)` service function with delta plan adjustment |
| M-004 | BOE | Allotment M2M not explicitly re-dispatched when changed without RowDetails changes | If only `boe.allotment.set()` changes (no RowDetails CRUD), balance is not recomputed. | Add explicit `recompute_license_balance_task.delay()` in `BillOfEntrySerializer.update()` when allotment M2M changes |
| M-005 | Frontend | No focus trap in mobile sidebar drawer | WCAG 2.1 Dialog pattern requires keyboard users cannot Tab outside an open modal/drawer. | Add `focus-trap-react` package; wrap Sidebar content when `mobileOpen=true` |
| M-006 | Frontend | Missing error boundaries around async page components | Any unhandled throw in a page component crashes the full SPA. | Add `<ErrorBoundary>` around `<Outlet />` in AdminLayout |
| M-007 | Tests | `_update_item_level_balances` not tested end-to-end with mocked ORM | The function's full ORM path (bulk aggregation queries, bulk_update) is tested only via formula assertions, not the actual query logic. | Add dedicated tests mocking `RowDetails.objects`, `AllotmentItems.objects`, and `LicenseImportItemsModel.objects.bulk_update` |
| M-008 | Tests | `update_allotment` dispatch path has no test | `_dispatch(item_ids)` is tested for create and delete paths, not update. | Add `test_update_allotment_dispatches_recompute` in `test_allotment.py` |
| M-009 | Backend | `ReportDispatchPermission.has_permission` still has the old is_active/superuser order | Unlike other permission classes that were fixed (is_active first), `ReportDispatchPermission` still checks `is_superuser` before `is_active`. | Apply the same is_active-first pattern |

---

## LOW

| ID | Module | Issue | Details | Fix |
|---|---|---|---|---|
| L-001 | Dashboard | `_boe_model()` helper is dead code since bill_of_entry is always installed | The function exists to degrade gracefully when bill_of_entry is absent. bill_of_entry is always installed. | Remove `_boe_model()` and inline the import directly (same refactor as was done for balance_service) |
| L-002 | License | `shared.models.AuditModel` is orphaned | No concrete class inherits from it. `apps.core.models.masters.AuditModel` is the one actually used. | Remove `shared/models.py` or document clearly that it is unused |
| L-003 | Frontend | Settings feature directory missing | `pages/settings/Settings.tsx` exists but `features/settings/` directory doesn't. | Create `features/settings/` with queries.ts, mutations.ts, types.ts |
| L-004 | Frontend | Tablet stat card labels still truncate at very narrow widths | `line-clamp-2` helps but at 768px (md) the 2-column grid may still be too narrow for "Expired Licenses" | Add `text-xs` override at `sm:` breakpoint for all stat card labels |
| L-005 | Frontend | `useDeleteLicense` should use `removeQueries` for detail cache | Currently may use `invalidateQueries` which re-fetches a deleted resource (404) | Change to `queryClient.removeQueries({ queryKey: ['licenses', id] })` |
| L-006 | nginx | `/admin/` endpoint has no IP allowlist comment | Admin panel is publicly accessible. A comment template for IP restriction was added but not the actual IP. | Operators should configure `allow <office-IP>; deny all;` |
| L-007 | Frontend | `useGenerateLicensePDF` should be verified for window.open usage | Similar to the trade PDF fix, license PDF endpoints should use `apiClient.get({responseType: 'blob'})` | Verify `features/licenses/mutations.ts` |
| L-008 | Allotment | `LicenseItemPlan` created via API but not auto-created from import items | Users must manually create plans. There's no "auto-plan" from existing import items. | Consider a "Initialize Plans" action on the license that creates LicenseItemPlan rows for all import items |
| L-009 | Auth | No "Forgot Password" functionality | Password reset flow not implemented backend or frontend | Add `/api/v1/auth/password-reset/` endpoint with email-based flow |
| L-010 | Infra | `generate_license_pdf_task` is a stub | The task logs a request but doesn't actually generate a PDF. | Implement actual PDF generation using the existing `purchase_invoice_pdf.py` / `bill_of_supply_pdf.py` infrastructure |
| L-011 | Tests | Dashboard tests use naive datetime fixtures | `DateTimeField received a naive datetime` warnings in `test_dashboard.py` | Wrap fixture datetimes with `django.utils.timezone.make_aware()` |
