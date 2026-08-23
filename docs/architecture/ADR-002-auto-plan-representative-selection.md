# ADR-002: Auto-Plan Group Representative Selection — Lowest Serial Number, No Migration

**Status:** Accepted
**Date:** 2026-08-04
**Deciders:** (human owner), informed by multi-turn code research + independent code-review pass
**Owner-agents referenced:** `backend-engineer`, `qa-test-engineer`, `code-reviewer`

---

## 1. Context

`plan_grouping.merge_items_for_classification()` groups a license's import items into one row per physical product (same HSN + normalized description, via `plan_group_key`). Every Auto-Plan engine (E1, E5, E126, E132) and the Item Pivot Report call it; the group's plan is persisted on one member's row — its **representative**.

Two different representative-selection conventions existed side by side before this fix:

- `auto_plan_shared.group_by_desc()` (now removed — superseded by `plan_group_key`) picked the member with the **lowest `serial_number`**.
- `plan_grouping.merge_items_for_classification()` picked the member with the **lowest database id** — inconsistent with this module's own top-of-file docstring ("a group's plan is stored on its representative import item, lowest serial number") and with the convention the Plan Tab / `PlanningEditor.tsx` / manual `bulk_upsert` already assumed.

DGFT re-syncs can assign new database ids in an order that does not match `serial_number` (a re-serialized license's newer rows can get lower or higher ids than their serial position implies), so "lowest id" and "lowest serial" genuinely diverge on real data. A read-only dev-DB check confirmed this: **31 of 75 real multi-member groups, across 5 licenses**, pick a different representative under the two rules — this was a live bug, not a hypothetical.

## 2. Decision

Standardize representative selection on **lowest `serial_number`** everywhere (`plan_grouping.merge_items_for_classification`), matching the module's own docstring and the Plan Tab's existing convention. **Ship without a backfill migration** of already-persisted `LicenseItemPlan.import_item` rows.

## 3. Why this is safe without a migration

Every business-critical consumer of `LicenseItemPlan.import_item` aggregates over the **current group's full member-id list** (via `plan_group_key`/`group_ids_of`), never by assuming a specific representative:

- `plan_enforcement.py`: `plan_status_for`, `plan_status_for_ids`, `plan_status_for_items`, `planned_totals_for`, `existing_split_balances_for_groups`
- `plan_utilization.py`: `plan_utilization_rows`
- `apps/allotment/views_actions.py::allocate_items`'s plan-cap check (`plan_status_for(license_item)`)

Because group *membership* is defined purely by `plan_group_key` — independent of which member is chosen as representative — an old plan row anchored to the pre-fix representative is still found and correctly aggregated by every one of these, as long as that member remains part of the same group (which it always does).

Separately, `allocate_items`'s plan-line balance decrement keys off `LicenseItemPlan.id` (`plan_line_id`), never `import_item_id` — completely unaffected by which member anchors a row.

Net effect: existing plans remain **functionally correct** immediately, with zero data migration, zero downtime, and no large-table rewrite.

## 4. What intentionally does not change immediately

A small number of representative-only display paths continue to show data keyed to whichever member currently holds the row:

- `LicenseImportItemSerializer.get_planned_quantity` (`apps/license/serializers/license.py`)
- `norm_plan.py::effective_plan_for_license`'s "manual" branch — a non-representative sibling falls through to a **live norm recompute** instead of the group's persisted plan share
- The Allotment "Plan mode" grid (`apps/allotment/views_actions.py::_available_licenses_plan_mode`)
- The Planned Report (`apps/license/views/planned_report.py`)

This is a pre-existing characteristic of the "one `LicenseItemPlan` row per group" model — it held under the old (lowest-id) rule exactly as much as under the new (lowest-serial) rule. This change only shifts *which* serial exhibits it, and only once a license's plan is next regenerated (auto-plan's full delete+recreate, or a manual bulk-upsert) — nothing rewrites existing rows in place.

## 5. Rejected alternative: backfill migration

Considered and rejected for this release. A backfill would touch every existing `LicenseItemPlan` row, need to account for in-flight `plan_line_id` references from allotment allocations, and require rollback/failure-mode testing under production load — real complexity for a benefit that is cosmetic/consistency-only, not correctness.

Revisit if any of the following becomes true:
- an external integration comes to depend on `import_item_id` matching the lowest-serial member;
- a report/export is contractually expected to show the new representative immediately post-deploy;
- support staff frequently investigate plans by representative serial number, and a mixed old/new convention causes operational confusion.

If that happens, the recommended tool is an explicit, non-automatic management command — e.g. `reanchor_license_plan_representatives` — idempotent, dry-run capable, run per-license, audit-logged. Not a bare data migration baked into deploy.

## 6. Verification performed

- Read in full: `plan_grouping.py`, `auto_plan_shared.py`, `e1_auto_plan.py`, `e5_auto_plan.py`, `e126_auto_plan.py`, `e132_auto_plan.py`, `plan_enforcement.py`, `plan_utilization.py`.
- Traced all 6 production call sites of `merge_items_for_classification`/`representative_id` (E1, E5, E126, E132 auto-plan; Item Pivot Report's E1 and E5 branches) and classified each as persisted / row-PK-referenced / in-memory-only.
- Live, read-only dev-DB query: 31/75 real multi-member groups (5 licenses) mismatch between old and new representative choice.
- Full affected test suite: **335 tests passing** — `plan_grouping`, E1/E5/E126/E132 engine + auto-plan tests, `plan_enforcement`, `plan_utilization`, and 3 allotment cap-enforcement integration test files.
- Independent `code-reviewer` pass on the full diff: no logic defects in the representative-selection algorithm; confirmed `LicenseImportItemsModel.serial_number` is a non-nullable `IntegerField` unique-together with `license`, so the "missing serial" fallback path is defensive-only and unreachable on real persisted data.

## 7. Known open item before commit

`e126_plan.py`'s PKO/Olive-Oil split-ratio change (40/60 → 50/50) is a **separate, unrelated business-rule fix** present in the same working tree. `test_e126_auto_plan.py`'s updated fixtures depend on the new ratio — `e126_plan.py` and `test_e126_plan.py` must land in the same commit/PR as this representative-selection fix (or an earlier commit on the same branch); committing the representative-selection files alone would leave `test_e126_auto_plan.py` failing against `e126_plan.py`'s old 40/60 ratio.

Minor, non-blocking nit: `plan_grouping.py`'s `serial_by_id.get(mid, mid)` fallback (in the `representative_id = min(...)` call) is dead code in practice — every `mid` is already a key in `serial_by_id` by that point, so the actual "missing serial" fallback happens earlier, at the per-item `getattr(item, 'serial_number', item.id)` call. Cosmetic only; no behavior change needed.

## 8. Release note

- Newly generated or regenerated plans (E1/E5/E126/E132 auto-plan, and manual bulk-upsert) now anchor each physical-product group's `LicenseItemPlan` row on its lowest-serial-number member, matching the Plan Tab/`PlanningEditor.tsx` convention used everywhere else.
- Existing plans keep their historical anchor until next regenerated — intentional (§4), and does not affect planning correctness or allotment-cap enforcement, both computed at the group level.
- No database migration or data backfill accompanies this change.
