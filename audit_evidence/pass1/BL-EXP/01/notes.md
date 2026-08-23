BL-EXP-01: Expired licenses can still be allocated (no server-side expiry gate)

Files:
- backend/apps/allotment/views_actions.py (AllotmentActionViewSet.allocate_items,
  lines ~623-830) — the real production write path for
  POST /api/allotments/<id>/allocate-items/
- backend/apps/license/services/validation_service.py
  (LicenseValidationService.validate_license_active / validate_allocation)
- backend/apps/allotment/services/allocation_service.py (AllocationService.allocate_item)

Root cause:
`allocate_items` (the only write path that actually creates `AllotmentItems` rows in
production — confirmed by grepping every `AllotmentItems.objects.create(...)` call
site) validates only:
  1. `actual_available_qty >= qty` (stored `available_quantity` field)
  2. `available_value_calculated >= cif_fc` (live balance/pool calc)
  3. utilization-plan cap (`plan_status_for`)
  4. duplicate-item merge logic

At no point does it read `license_item.license.is_expired`,
`license_item.license.license_expiry_date`, or call
`LicenseValidationService.validate_license_active` / `validate_allocation`. Those
methods DO implement an expiry check (`if license_obj.is_expired: errors.append(...)`)
and are exercised by `apps/allotment/services/allocation_service.py::AllocationService
.allocate_item/update_allocation`, but `AllocationService` itself is never called
from any view — it is only re-exported from `apps/allotment/services/__init__.py`.
It is dead code disconnected from the real allocate-items endpoint.

The `available_licenses` / `_available_licenses_plan_mode` listing endpoints (which
populate the item picker on the frontend) only exclude expired licenses when the
caller explicitly passes `license_status=active` — there is no default exclusion,
and even if the frontend always sends that filter, it only affects what the browser
sees in the dropdown; it is not re-checked when the POST actually creates the
allocation. Any direct API call (or a picker that doesn't apply that filter) can
allocate against an expired license today.

Live-data proof (see sql.sql / query_result):
- Server clock: 2026-08-07 (current_date).
- License 0311046335 (id 2434) expired 2026-08-06 (yesterday) — `flags.is_expired`
  is correctly `true` — yet it has 13 import items with available_quantity between
  2 and 9625 and available_value 6.20, all of which would pass the two checks
  `allocate_items` performs and be accepted as a new allocation right now.
- License 0311046297 (id 2433) expired 2026-08-05, same situation.
- 41 distinct expired licenses in the current 228-license dataset currently have
  positive available_quantity/available_value on at least one import item, i.e.
  are "allocatable" through the live endpoint despite being expired.

Expected: the API should reject (400) an allocation attempt against a license
whose `license_expiry_date` has passed (mirroring `validate_license_active`'s
existing, but unwired, business rule), the same way it already rejects
insufficient-quantity/insufficient-CIF/plan-exceeded attempts.

Actual: `allocate_items` has no expiry check; the write succeeds for any expired
license that still carries a positive `available_quantity`/`available_value`
(which many do, since balance is a running CIF total unrelated to the expiry date).

Confidence: high — proven by (a) reading the only real write path and confirming
no expiry check exists, (b) confirming the one component that WOULD check expiry
is unreachable dead code, and (c) 41 real expired licenses in the local DB that
satisfy every other guard and would be accepted today.

Ambiguous: false — this is squarely a missing validation, not a business-rule
judgment call. (Whether the intended behavior is "hard block" vs. "warn and allow"
is a product decision I'm not making here; I'm reporting that no rule at all is
enforced today, even though the codebase clearly intends one via
`validate_license_active`.)
