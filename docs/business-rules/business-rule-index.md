# Business Rule Index

> **Complete index of every business rule implemented in the codebase.**  
> Last updated: 2026-07-15.

---

## License Module

| ID | Rule | Implemented in | File |
|---|---|---|---|
| LIC-001 | `license_number` is globally unique | DB constraint `unique=True` | `license_licensedetailsmodel` table |
| LIC-002 | `balance_cif = max(0, credit - debit - allotment - trade)` | `recompute_license_balance()` | `balance_service.py` |
| LIC-003 | `balance_cif >= 0` — never negative | `max(_DEC_0, raw_balance)` | `balance_service.py:144` |
| LIC-004 | `is_null = True` when `balance_cif < 500` | `is_null = balance < _NULL_THRESHOLD` | `balance_service.py:158` |
| LIC-005 | `is_expired = True` when `license_expiry_date < today` | Checked on every recompute | `balance_service.py:159-162` |
| LIC-006 | Credit = SUM of all export item `cif_fc` | `_compute_credit()` | `balance_service.py:36-44` |
| LIC-007 | Debit = SUM of BOE RowDetails `cif_fc` WHERE type='D' AND no trade | `_compute_debit()` | `balance_service.py:47-65` |
| LIC-008 | Allotment component = only pending allotments (no BOE linked) | `allotment.bill_of_entry__isnull=True` filter | `balance_service.py:68-84` |
| LIC-009 | Trade component = SALE direction only (not PURCHASE) | `trade.direction='SALE'` filter | `balance_service.py:87-102` |
| LIC-010 | Balance recompute is always async (Celery) | `recompute_license_balance_task.delay()` | `license/tasks.py` |
| LIC-011 | Item-level balance: `available_qty = max(0, total - debited - allotted)` | `_update_item_level_balances()` | `balance_service.py:109-193` |
| LIC-012 | Item-level update in same transaction as license-level | Called at end of `recompute_license_balance()` | `balance_service.py:289` |
| LIC-013 | `import_items` are unique per `(license, serial_number)` | `unique_together = (license, serial_number)` | `LicenseImportItemsModel.Meta` |
| LIC-014 | Balance recompute triggered by import item CRUD | `create/update/delete_import_item()` dispatches task | `license_service.py` |
| LIC-015 | Balance snapshot date = `timezone.now().date()` | Written to `LicenseBalance.ledger_date` | `balance_service.py:152-154` |

---

## Planning Module (LicenseItemPlan)

| ID | Rule | Implemented in | File |
|---|---|---|---|
| PLAN-001 | Planning is optional — if no plan row exists, allotment is unrestricted | `_validate_plan_availability` returns early if `plan is None` | `allotment_service.py:74-78` |
| PLAN-002 | Creating allotment decrements plan: `planned_qty -= allot_qty` | `_adjust_plan(qty_delta=-allot_qty)` | `allotment_service.py:174-180` |
| PLAN-003 | Deleting allotment restores plan: `planned_qty += allot_qty` | `_adjust_plan(qty_delta=+allot_qty)` | `allotment_service.py:224-232` |
| PLAN-004 | Cannot allot more than `planned_quantity` | `ValidationError` if `qty_requested > plan.planned_quantity` | `allotment_service.py:82-88` |
| PLAN-005 | Cannot allot more than `planned_cif_fc` | `ValidationError` if `cif_fc_requested > plan.planned_cif_fc` | `allotment_service.py:90-95` |
| PLAN-006 | Plan adjustment uses atomic F() expression (no read-modify-write race) | `plan_qs.update(F("planned_quantity") + delta)` | `allotment_service.py:103-112` |
| PLAN-007 | Plan validation uses `select_for_update()` (concurrent over-allotment prevention) | `LicenseItemPlan.objects.select_for_update()` | `allotment_service.py:71` |
| PLAN-008 | `update_allotment` does NOT adjust the plan (header-only update) | Plan adjustment only in create/delete | `allotment_service.py:133-151` |

---

## Allotment Module

| ID | Rule | Implemented in | File |
|---|---|---|---|
| ALLOT-001 | Allotment type: AT (Allotment) or TR (Transfer) | `ALLOTMENT_TYPE_CHOICES = [("AT",...), ("TR",...)]` | `allotment/models.py:30` |
| ALLOT-002 | Balance recompute dispatched AFTER commit (not during) | `transaction.on_commit(_dispatch(...))` | `allotment_service.py:91,124,147` |
| ALLOT-003 | Dispatch resolves license_id from import item_id | `LicenseImportItemsModel.objects.filter(pk__in=item_ids).values_list("license_id")` | `allotment_service.py:43-49` |
| ALLOT-004 | AllotmentItems cascade-deleted when AllotmentModel is deleted | Django FK `on_delete=CASCADE` | `allotment/models.py:172-178` |
| ALLOT-005 | `unique_together = (item, allotment)` — one line per item per allotment | `AllotmentItems.Meta` | `allotment/models.py:203` |
| ALLOT-006 | `alloted_quantity` property = SUM of all allotment_details.qty | `cached_property` on AllotmentModel | `allotment/models.py:122-127` |
| ALLOT-007 | `balanced_quantity` property = required_quantity - alloted_quantity (never negative) | `max(diff, Decimal("0"))` | `allotment/models.py:138-141` |

---

## Bill of Entry (BOE) Module

| ID | Rule | Implemented in | File |
|---|---|---|---|
| BOE-001 | BOE RowDetails are uniquely identified by `(bill_of_entry, sr_number, transaction_type)` | `unique_together` on RowDetails.Meta | `boe/models.py:306` |
| BOE-002 | Frozen rows cannot be edited via the frontend | `RowDetails.save()` silently returns if `is_frozen=True` | `boe/models.py:310-321` |
| BOE-003 | Balance recomputed after RowDetails save (post_save signal) | `update_stock` signal → `_dispatch_balance_recompute(license_id)` | `boe/models.py:349-363` |
| BOE-004 | Balance recomputed after RowDetails delete (post_delete signal) | `delete_stock` signal → `_dispatch_balance_recompute(license_id)` | `boe/models.py:366-380` |
| BOE-005 | BOE exchange rate auto-recalculated after row changes | `recalc_exchange_rate_on_row_save` signal | `boe/models.py:417-431` |
| BOE-006 | Scenario B: allotment linked to BOE exits allotment component | `BillOfEntryModel.allotment.set(allotment)` sets M2M; `allotment__bill_of_entry__isnull=False` | `boe/serializers.py:163-181` |
| BOE-007 | Dispute rows (`is_dispute=True`) are flagged when missing from ledger upload | Set during ledger processing | `boe/views/ledger.py` |
| BOE-008 | Dispute resolution clears `is_dispute` flag | `resolve_dispute` / `resolve_dispute_row` | `boe_service.py:169-213` |
| BOE-009 | `resolve_dispute_row` scopes RowDetails to parent BOE (IDOR prevention) | `RowDetails.objects.get(pk=row_id, bill_of_entry_id=boe_id)` | `boe_service.py:202` |
| BOE-010 | `update_row_detail` / `delete_row_detail` also scope to parent BOE | Same `bill_of_entry_id=boe_id` scoping | `boe_service.py:348,370` |
| BOE-011 | BOE exchange rate = total_inr / total_fc (auto-computed) | `BillOfEntryModel.save()` | `boe/models.py:115-134` |
| BOE-012 | `ooc_date` MUST stay CharField(255) — NOT DateField | Raw ICEGATE text field | `boe/models.py:89` |
| BOE-013 | BOE unique: `(bill_of_entry_number, bill_of_entry_date)` | `unique_together` on BillOfEntryModel.Meta | `boe/models.py:98` |

---

## Trade Module

| ID | Rule | Implemented in | File |
|---|---|---|---|
| TRADE-001 | `pct`/`rate_pct` must use `Decimal(str(value))` BEFORE dividing by 100 | `compute_amount()` formulas | `trade/models.py:384-404, 467-480` |
| TRADE-002 | `amount_inr` is ALWAYS recomputed on save (no stale guard) | Unconditional `self.amount_inr = self.compute_amount()` | `trade/models.py:405, 478` |
| TRADE-003 | Invoice number format: `{prefix}/{fiscal_year}/{4-digit-seq}` | `get_next_invoice_number()` | `trade/models.py:66-112` |
| TRADE-004 | Invoice number generation is race-safe (select_for_update) | `LicenseTrade.objects.select_for_update()` inside `transaction.atomic()` | `trade/models.py:91-100` |
| TRADE-005 | Invoice unique: PURCHASE by `(from_company, invoice_number)`, SALE by `(to_company, invoice_number)` | Conditional `UniqueConstraint` | `trade/models.py:232-239` |
| TRADE-006 | Trade billing modes: CIF_INR, FOB_INR, QTY (different formulas for each) | `compute_amount()` if/elif chain | `trade/models.py:391-401` |
| TRADE-007 | `paid_or_received` = SUM of all payments | `cached_property` on LicenseTrade | `trade/models.py:248-252` |
| TRADE-008 | `due_amount` = total_amount - paid_or_received | `cached_property` | `trade/models.py:254-257` |
| TRADE-009 | `recompute_totals()` called on trade save to update total_amount_inr | `LicenseTrade.save()` | `trade/models.py:318-326` |
| TRADE-010 | Auto-linked trades (PURCHASE/SALE pair) via `link_trades()` | `PartnerTradeNotFound` if no match | `trade_service.py` |
| TRADE-011 | `PartnerTradeNotFound` class defined ABOVE `link_trades()` (fixes historical NameError) | Class at module level before use | `trade_service.py:122` |
| TRADE-012 | IncentiveTradeLine: `rate_pct` must be 3dp (same rule as LicenseTradeLine.pct) | `rate_pct = DecimalField(max_digits=9, decimal_places=3)` | `trade/models.py` |

---

## Tasks Module

| ID | Rule | Implemented in | File |
|---|---|---|---|
| TASK-001 | Task states: PENDING → COMPLETED, PENDING → REJECTED, REJECTED → PENDING (reopen) | `mark_completed()`, `mark_rejected()`, `reopen()` methods | `tasks/models.py:79-92` |
| TASK-002 | Rejection requires a reason text | `mark_rejected(reason=reason)` stored on task | `tasks/models.py:84-92` |
| TASK-003 | TaskRemark is append-only (no edit/delete) | No update/delete serializer fields | `tasks/serializers.py` |
| TASK-004 | Remarks created via `task_service.add_remark()` — not directly | `tasks/views.py` delegates to service | `task_service.py:72-78` |

---

## Reports Module

| ID | Rule | Implemented in | File |
|---|---|---|---|
| RPT-001 | CeleryTaskTracker row created BEFORE apply_async (prevents tracker race) | `uuid.uuid4()` pre-generated; tracker INSERT before dispatch | `reports/views.py:204-219` |
| RPT-002 | All 4 report tasks: `acks_late=True, reject_on_worker_lost=True` | Decorator on all `@shared_task` | `reports/tasks.py:86,111,136,161` |
| RPT-003 | Report filter params are fully typed (no DictField injection) | `ItemReportRequestSerializer`, `PivotReportRequestSerializer` | `reports/views.py:79-149` |
| RPT-004 | Ledger report uses direct lazy imports (not _safe_get_model) | `from apps.bill_of_entry.models import RowDetails` | `reports/services/ledger_report.py` |
| RPT-005 | **WARNING**: Balance report service re-implements aggregations instead of calling `balance_service._compute_*` | Divergence potential | `reports/services/balance_report.py:53-78` |

---

## Authentication / Permissions

| ID | Rule | Implemented in | File |
|---|---|---|---|
| AUTH-001 | `is_active` checked BEFORE `is_superuser` (deactivated superusers blocked) | `if not is_active: return False; if is_superuser: return True` | `accounts/permissions.py:31-38` |
| AUTH-002 | Login throttled by `LoginRateThrottle` (AnonRateThrottle subclass) | Applied to `LoginView` | `accounts/views.py:29-35` |
| AUTH-003 | Logout invalidates refresh token (blacklisted via `rest_framework_simplejwt.token_blacklist`) | `RefreshToken(refresh).blacklist()` | `accounts/views.py:83-100` |
| AUTH-004 | JWT HS256 shared `SECRET_KEY` between legacy and new backend (ADR-006) | `SIMPLE_JWT.ALGORITHM = "HS256"` | `config/settings/base.py` |
| AUTH-005 | `is_superuser` exposed in `UserSerializer` (required for frontend RBAC) | `is_superuser = BooleanField(read_only=True)` | `accounts/serializers.py` |
| AUTH-006 | RBAC via Django Groups (group name = role code) | `user.has_any_role(role_codes)` = `groups.filter(name__in=...).exists()` | `accounts/models.py:124-126` |
| AUTH-007 | 30-minute idle timeout (frontend enforced) | `IDLE_TIMEOUT_MS = 30 * 60 * 1000` | `AuthContext.tsx:46` |
| AUTH-008 | Proactive token refresh 5 minutes before expiry | `TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000` | `AuthContext.tsx:48` |

---

## Infrastructure / Cross-Cutting

| ID | Rule | Implemented in | File |
|---|---|---|---|
| INFRA-001 | Redis DB isolation: cache=/1, broker=/2, results=/3 | Three separate DB numbers | `config/settings/base.py:118-123` |
| INFRA-002 | Celery serialization: JSON only (no pickle — security) | `CELERY_ACCEPT_CONTENT = ["json"]` | `config/settings/base.py` |
| INFRA-003 | `SECURE_PROXY_SSL_HEADER` required in prod (nginx SSL termination) | `("HTTP_X_FORWARDED_PROTO", "https")` | `config/settings/prod.py` |
| INFRA-004 | `/api/v1/` routes BEFORE `/api/` in nginx (more specific prefix first) | Order in nginx location blocks | `nginx-*.conf` |
| INFRA-005 | `client_header_timeout 30s` (not 300s — Slow Loris protection) | nginx configs | `nginx-*.conf` |
| INFRA-006 | `/protected-media/` uses nginx `internal` directive | Only Django can serve (X-Accel-Redirect) | `nginx-*.conf` |
