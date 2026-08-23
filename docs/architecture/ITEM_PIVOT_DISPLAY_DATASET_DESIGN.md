# Item Pivot Report — Display Dataset Migration Design (Phase 2B.2)

**Status:** Design only. No code changes made. Do not implement until this
document is explicitly approved.
**Prerequisite:** Export Consistency Fixes, Phase 2A, and Phase 2B.1
complete (see commit history `44381308`..`31813d26`) and the Display
Dataset Rule (`docs/02-architecture.md`, "Report & Export Architecture").
**Scope:** `backend/apps/license/views/item_pivot_report.py`,
`frontend/src/pages/reports/ItemPivotReport.tsx`, and the services each
imports. Confirmed via three independent read-only investigations of the
current codebase (not assumed from prior audits) — all line numbers below
were re-verified at the current HEAD.

---

## 0. Executive Summary

Item Pivot Report is not one violation of the Display Dataset Rule — it's
two different problems that look similar from the outside:

1. **Per-cell business values** (Balance CIF, Planned Qty/CIF, Unit Price,
   Restriction %, Available Qty) are each computed **exactly once**, on the
   backend, in `_build_license_row()`, and read verbatim everywhere else
   (JSON, Excel). **This part already complies with the rule.** There is no
   "three divergent formulas" problem at the cell level — a prior summary
   describing this report as having per-cell duplication was imprecise.

2. **Aggregate values built from those cells** (the Notification/Norm
   Summary panel, footer TOTAL rows, and the per-license "Planned CIF" row
   total) are where the real problem lives:
   - The **Notification/Norm Summary panel** — opening balance sum,
     restriction-pool aggregation, available/planned aggregation, and a
     blended unit-price ratio — exists **only in the frontend**
     (`calculateNotificationSummary`, `ItemPivotReport.tsx:507-621`). There
     is no backend field for it and no equivalent sheet in the Excel
     export. This is not "the frontend duplicates the backend" — **the
     backend has never computed this value at all.** Migrating it means
     writing new backend aggregation logic, not moving existing logic.
   - **Footer TOTAL rows** are computed independently in two places
     (`ItemPivotReport.tsx:1288-1346` in JS, `item_pivot_report.py:1518-1589`
     in the Excel exporter) by summing the *same* already-computed per-row
     cells. Today these produce identical numbers because both sum the same
     fields the same way — but nothing enforces that; a future edit to one
     without the other is a silent-divergence risk, not a live bug.
   - The **manual-plan-vs-norm-derived selection rule** for "which planned
     CIF figure to show" (`hasManual ? plan_cif : planned_cif`) is
     implemented **four separate times**: three copies inside
     `ItemPivotReport.tsx` (row level, notification-total, per-item-column
     total) and once in the Excel exporter (`_planned_cif_for`,
     `item_pivot_report.py:1579-1587`). This is the single most duplicated
     piece of logic in the report and the highest internal-consistency
     risk, independent of the frontend/backend question.

3. **Warnings**: grepped for "warning"/"over-alloc"/"violat"/"exceed"
   across the backend service layer — **zero matches**. The frontend
   investigation found no warnings-rendering code for this report either.
   **This is very likely a feature that does not exist for Item Pivot
   Report today**, not a hidden duplication. Flagged as an open question in
   §9 — do not build a "Warnings" field into the Display Dataset on the
   assumption it already exists somewhere; verify with the user first.

Net effect: this is not a "delete the frontend copy, keep the backend
copy" migration for most of what's listed. For the Notification Summary
specifically, it's "write the backend copy for the first time, then point
the frontend and Excel at it." That changes the risk profile and the
phase ordering from what a generic template would suggest.

---

## 1. Calculation Inventory

| Calculation | Backend | Frontend | Excel | Source of truth today | Recommendation |
|---|---|---|---|---|---|
| Opening Balance (component of Balance CIF) | ✓ (embedded in `LicenseBalanceCalculator`, not a standalone field) | — | — | Backend, single | No change — not separately exposed anywhere, nothing to migrate |
| Balance CIF / Available CIF (license-wide) | ✓ `item_pivot_report.py:536`, batched `LicenseBalanceCalculator.calculate_financial_balance_for_licenses` | reads verbatim, sums for its own aggregates | reads verbatim, sums for totals row | **Backend, single** | No change to the value; only the *summing of it* is duplicated (see Grand Totals row) |
| Available Qty (per item) | ✓ `item_pivot_report.py:768`, summed from `LicenseImportItemsModel.available_quantity` | reads verbatim, sums for aggregates | reads verbatim, sums for totals row | **Backend, single** | No change to the value |
| Planned Qty / Planned CIF (per license×item cell) | ✓ `_build_license_row`, 3 mutually-exclusive paths (manual plan / E1-E5 waterfall / E132 classification), `item_pivot_report.py:883-1310` | reads verbatim, re-aggregates | reads verbatim, re-aggregates | **Backend, single** | No change to the per-cell value |
| Unit Price (per cell) | ✓ RUTILE special case, E1/E5 effective rate, or E132 fixed rate — `item_pivot_report.py:868-881, 1003, 1094, 1200-1203` | reads verbatim | reads verbatim (no unit-price arithmetic found in Excel) | **Backend, single** | No change |
| Restriction % / restriction_value (per cell) | ✓ `services/condition_pool.py`, pool math per condition_type | reads verbatim, dedupes/pools for its own summary | reads verbatim, sums for totals row | **Backend, single** | No change to the value |
| Manual-vs-norm "which planned CIF" selection rule | ✓ once, inline in `_build_license_row` (produces the cell value) + again as `_planned_cif_for` in the Excel exporter (`item_pivot_report.py:1579-1587`) | ✓ **3 separate copies** (`ItemPivotReport.tsx:1131-1135`, `:1297-1301`, `:1334-1338`) | ✓ `_planned_cif_for` | **Duplicated 4-5×, no single owner** | **Highest priority**: extract one backend helper, expose the selected value as a first-class per-row field, delete all 4-5 re-implementations |
| Notification-level Summary (opening balance sum, restriction pool, available/planned aggregation, blended unit price) | **✗ does not exist** | ✓ `calculateNotificationSummary`, `ItemPivotReport.tsx:507-621` | **✗ does not exist** (no Summary sheet in the export) | **Frontend only — no backend equivalent to converge onto** | Build new backend aggregation (this is new logic, not a move); until built, the on-screen summary and the downloaded Excel will keep disagreeing (Excel shows none at all) |
| Norms Total Summary (same as above, flattened across notifications) | ✗ | ✓ `ItemPivotReport.tsx:1538-1541` | ✗ | Frontend only | Same as above, one level up |
| Grand/footer TOTAL row (per-sheet: total/debited/alloted/balance CIF, per-item qty/restriction/plan totals) | ✗ (JSON has no totals object) | ✓ `ItemPivotReport.tsx:1288-1346` | ✓ `item_pivot_report.py:1518-1589` (per-sheet, not report-wide) | **Duplicated 2× (JS + Python), both summing the same backend cells** | Compute once server-side per notification group, include in Display Dataset, both consumers read it |
| Warnings (over-allocation, missing plan, restriction breach) | ✗ not found | ✗ not found | ✗ not found | **Feature does not appear to exist** | Do not build speculatively — confirm with user first (see §9) |

---

## 2. Dependency Graph

```
LicenseBalanceCalculator.calculate_financial_balance_for_licenses  (balance_calculator.py)
        │  (batched, called once per report)
        ▼
generate_report()  (item_pivot_report.py:159-673)
        │
        ├─▶ services/condition_pool.py  (compute_condition_pools_bulk)   → restriction %, restriction_value
        ├─▶ services/plan_grouping.py   (merge_planned_import_items, merge_items_for_classification)
        ├─▶ services/e1_plan.py / e5_plan.py   (plan_e1_items / plan_e5_items)   → Planned Qty/CIF, Unit Price (E1/E5)
        ├─▶ services/e132_plan.py       (plan_e132_per_item)                     → Planned Qty/CIF, Unit Price (E132)
        │
        ▼
_build_license_row()  (item_pivot_report.py:675-1338)
        │  produces the per-license, per-item CELL values — single source
        ▼
   ┌────┴─────────────────────────────┐
   ▼                                  ▼
JSON response                  export_to_excel_streaming()
(licenses_by_norm_notification)  (item_pivot_report.py:1340-1641)
   │                                  │
   │  (no aggregation here)           │  re-derives its OWN per-sheet
   │                                  │  totals row from the same cells
   ▼                                  ▼
ItemPivotReport.tsx (frontend)   Excel workbook (per-sheet TOTAL row,
   │                              Planning Splits sheet)
   ├─ calculateNotificationSummary()  ◀── NEW LOGIC, no backend source
   ├─ footer TOTAL row (re-sum)       ◀── duplicates Excel's totals row
   └─ 3× manual-vs-norm CIF selection ◀── duplicates Excel's _planned_cif_for
```

The cell-value layer (top half) is a clean single-producer graph — this is
the part of the report that already matches the pattern
`LicenseBalanceLedgerBuilder` and `build_purchase_profit_report` set. The
aggregation layer (bottom half) is where JSON, frontend, and Excel each go
their own way after receiving the same cells.

---

## 3. Duplication Map

| Logic | Copies | Locations |
|---|---|---|
| Manual-vs-norm planned-CIF selection | **4** (5 if you count the per-item-column total as distinct from the row-level copy) | `ItemPivotReport.tsx:1131-1135`, `:1297-1301`, `:1334-1338`; `item_pivot_report.py:1579-1587` (`_planned_cif_for`) |
| Per-sheet/per-notification totals (CIF + qty columns) | **2** | `ItemPivotReport.tsx:1288-1346`; `item_pivot_report.py:1518-1589` |
| Notification/Norm Summary (opening balance, restriction pool, blended unit price) | **1** (no backend/Excel counterpart to be "duplicate" against — this is a gap, not a duplication) | `ItemPivotReport.tsx:507-621`, reused at `:1541` for norm scope |

Only the first two rows are genuine "the same number computed more than
once" duplication. The third is a coverage gap, not duplication — worth
keeping that distinction sharp because it changes what "fixing" it means
(delete vs. build).

---

## 4. Data Flow — Current vs. Target

**Current:**
```
Backend cells ─┬─▶ JSON ─▶ React (recomputes notification summary,
               │            re-sums totals, re-derives planned-CIF 3×)
               │
               └─▶ Excel exporter (re-sums its own totals, re-derives
                                    planned-CIF independently)
```

**Target:**
```
Backend cells ─▶ generate_report() also builds:
                   - per-notification `summary` object (opening balance,
                     restriction pool, available/planned aggregates,
                     blended unit price)
                   - per-notification `totals` object (the same sums the
                     footer/Excel totals row need)
                   - the manual-vs-norm planned-CIF selection exposed as
                     its own named field per cell (e.g. `effective_planned_cif`),
                     computed once
                 ─▶ Display Dataset (one dict per notification group)
                       ├─▶ JSON response (unchanged shape otherwise)
                       ├─▶ React (renders `summary`/`totals` verbatim,
                       │          zero arithmetic beyond display formatting)
                       └─▶ Excel exporter (writes `summary`/`totals` into
                                            a Summary sheet + existing
                                            per-sheet totals row, zero
                                            arithmetic)
```

---

## 5. Risk Report

| Calculation | Risk | Why |
|---|---|---|
| Balance CIF, Available Qty, per-cell Planned Qty/CIF, Unit Price, Restriction % | **Low** | Already single-sourced on the backend; no migration needed, just confirm during testing that nothing downstream re-derives them (confirmed: nothing does) |
| Footer/per-sheet TOTAL rows (CIF + qty sums) | **Medium** | Two independent implementations that happen to agree today; consolidating is mechanical (both are pure sums of already-correct cells) but touches a lot of line-for-line frontend rendering code and the Excel totals-row code — moderate blast radius, low logic risk |
| Manual-vs-norm planned-CIF selection rule | **Medium-High** | Not computationally complex, but duplicated 4-5× — the risk isn't getting the formula right, it's making sure every one of the 4-5 call sites is found and replaced, and that no fifth undiscovered copy exists elsewhere (e.g. a print view, a PDF that doesn't exist yet, a different report that imports this component) |
| Notification/Norm Summary (opening balance sum, restriction pool dedup, blended unit price) | **Critical** | This is **new backend business logic**, not a migration of existing logic. The restriction-pool dedup logic in particular (`Set`-based dedup by `license_number + restriction%`, `ItemPivotReport.tsx:521-546`) encodes a real business rule about shared restriction pools that must be reverse-engineered precisely and re-implemented server-side without behavioral drift — this is exactly the kind of "moving calculations from frontend to backend" work Phase 2B.1's low-risk plumbing was explicitly not. Needs its own careful line-by-line translation and a wide regression-test net before any UI change ships. |
| Warnings | **Unclassified — verify existence first** | Cannot risk-rate a calculation that doesn't appear to exist. Do not build speculatively. |

---

## 6. Display Dataset Specification

Extending `generate_report()`'s existing return shape
(`licenses_by_norm_notification`, `items`, `norm_notes_conditions`,
`report_date`) — not replacing it. New keys are added; nothing existing
is renamed (per the Display Dataset convention's rule against renaming
API fields the frontend already depends on).

```jsonc
{
  // Existing, unchanged:
  "report_date": "...",
  "norm_notes_conditions": {...},
  "licenses_by_norm_notification": {
    "<norm_class>": {
      "<notification_key>": {
        // NEW: one summary object per notification group, replacing
        // ItemPivotReport.tsx's calculateNotificationSummary output.
        "summary": {
          "opening_balance": 0.0,          // sum of balance_cif across group
          "total_available": 0.0,
          "total_planned": 0.0,
          "total_planned_qty": 0.0,
          "unit_price": 0.0,               // total_planned / total_planned_qty
          "restriction_pools": [           // replaces the Set-based dedup
            {"percentage": 5.0, "shared_value": 1234.56}
          ]
        },
        // NEW: replaces the footer TOTAL row's re-derived sums.
        "totals": {
          "total_cif": 0.0,
          "debited_cif": 0.0,
          "alloted_cif": 0.0,
          "balance_cif": 0.0,
          "items": {
            "<item_name>": {
              "quantity": 0.0, "allotted_quantity": 0.0,
              "debited_quantity": 0.0, "available_quantity": 0.0,
              "restriction_value": 0.0,
              "planned_quantity": 0.0, "planned_cif": 0.0
            }
          }
        },
        "licenses": [
          {
            // existing per-license fields unchanged, PLUS:
            "items": {
              "<item_name>": {
                // existing fields unchanged (plan_quantity, plan_cif,
                // planned_cif, unit_price, restriction, restriction_value,
                // quantity, allotted_quantity, debited_quantity,
                // available_quantity), PLUS:
                "effective_planned_cif": 0.0   // NEW — the already-selected
                                                // manual-vs-norm value, so
                                                // no consumer branches again
              }
            }
          }
        ]
      }
    }
  },
  "meta": {                                // Phase 2A envelope convention
    "generated_at": "...",
    "filters_applied": {...}
  }
}
```

`effective_planned_cif` is deliberately additive, not a replacement for
`plan_cif`/`planned_cif`/`plan_quantity` — those stay for backward
compatibility with anything else reading this response, and because the
raw manual vs. norm-derived figures are legitimately useful to show
separately in some views. Consumers that today re-derive "which one to
display" switch to reading `effective_planned_cif` directly.

Warnings key intentionally omitted pending §9.

---

## 7. Migration Plan

Each phase is independently shippable and independently testable, per the
existing per-report-phase discipline this initiative has followed
(Phase 2A: 5 commits; Phase 2B.1: 1 commit — this report's `summary`
migration is closer in shape to Phase 2A's multi-step work than to
2B.1's single-commit plumbing, because part of it is new logic).

### Phase A — Grand Totals consolidation (Medium risk, do first)
Move the footer/per-sheet TOTAL row computation into `generate_report()`
as the `totals` object (§6). Frontend reads `totals` instead of its own
`reduce()` calls (`ItemPivotReport.tsx:1288-1346`); Excel exporter reads
`totals` instead of its own sums (`item_pivot_report.py:1518-1589`).
**Files:** `item_pivot_report.py` (add `totals` to `generate_report`),
`ItemPivotReport.tsx` (delete 3 reduce blocks, read `totals`),
`item_pivot_report.py` export method (delete the 4 sum() blocks at
1529-1589, read `report_data[...]['totals']`).
**Tests:** extend `test_item_pivot_balance_consistency.py` and
`test_item_pivot_excel_export.py` to assert `totals` in JSON matches both
the Excel totals row AND the (still-present during transition) frontend
render.
**Rollback:** revert the one commit; `totals` is additive to the JSON
shape, so nothing else breaks if reverted.

### Phase B — Manual-vs-norm planned-CIF unification (Medium-High risk)
Add `effective_planned_cif` per cell in `_build_license_row` (the same
branching logic already in `_planned_cif_for`, moved to be the canonical
implementation). Frontend's 3 copies and the Excel exporter's
`_planned_cif_for` all switch to reading `effective_planned_cif` instead
of re-deriving it.
**Files:** `item_pivot_report.py` (`_build_license_row`, `export_to_excel_streaming`),
`ItemPivotReport.tsx` (3 call sites).
**Tests:** a new backend test asserting `effective_planned_cif` matches
the pre-existing manual/norm branching for both cases; frontend test
(if any exist for this component — verify) asserting rendered value
matches the new field, not a local computation.
**Rollback:** additive field, safe to revert independently of Phase A.

### Phase C — Notification Summary migration (Critical risk, largest phase)
Build the backend `summary` object (§6) replicating
`calculateNotificationSummary`'s exact current behavior — opening balance
sum, the restriction-pool dedup rule, available/planned aggregation, and
the blended unit-price ratio. This is new backend code translating
existing frontend business logic, not a deletion-first move.
**Sequencing within this phase (do not skip steps):**
  1. Implement the backend `summary` builder, unit-test it in isolation
     against hand-computed fixtures that exercise the restriction-pool
     dedup rule specifically (this is the part most likely to have a
     subtle bug when translated).
  2. Add it to the JSON response ADDITIVELY — frontend keeps using its own
     `calculateNotificationSummary` for now.
  3. Add a temporary parity test/dev-only check comparing the new backend
     `summary` against the frontend's existing computed values for a
     sample of real filter combinations (a canary, not a permanent test) —
     confirms translation fidelity before touching any UI code.
  4. Only after parity is confirmed, switch `ItemPivotReport.tsx` to read
     `report_data[...]['summary']` and delete `calculateNotificationSummary`
     and its norm-scope reuse at line 1541.
  5. Add the Summary sheet to the Excel export, reading the same object.
**Files:** `item_pivot_report.py` (new summary builder + `export_to_excel_streaming`
new sheet), `ItemPivotReport.tsx` (delete `calculateNotificationSummary`
and its 2 call sites).
**Tests:** extensive — JSON summary vs. hand-computed fixture, JSON
summary vs. Excel Summary sheet, frontend rendering vs. JSON summary.
**Rollback:** steps 2-3 are additive/non-shipped-to-UI, trivially
revertible. Step 4 (UI switch) is the only user-visible change — revert
that single commit if a discrepancy surfaces post-ship, independent of
whether the backend `summary` object itself is kept.

### Phase D — Excel Summary sheet (Low-Medium risk, depends on Phase C)
Already covered as Phase C step 5 above — separated here only because it's
explicitly requested in the deliverables. No new backend logic; purely
formatting the Phase C `summary` object into a new sheet.

### Phase E — Delete duplicate frontend logic (cleanup, do last)
Confirm zero remaining call sites of `calculateNotificationSummary`, the 3
manual-vs-norm copies, and the footer reduce blocks. Delete dead code.
**This phase is a no-op if Phases A-C already deleted their own dead code
as they went** (recommended) rather than batching all deletions to the
end — batching increases the diff size of the riskiest phase (C) for no
benefit.

### Phase F — Warnings (blocked on §9)
Do not schedule until the open question is resolved.

---

## 8. Implementation Checklist

| Phase | Blast radius | Est. files | Can ship independently? |
|---|---|---|---|
| A — Grand Totals | Medium (frontend render + Excel totals rewritten, but pure mechanical resum) | 2 | Yes |
| B — planned-CIF unification | Medium (4-5 call sites across 2 files, simple logic) | 2 | Yes, independent of A |
| C — Notification Summary | **Large** (new backend logic + backend tests + frontend deletion + Excel new sheet) | 2-3 | Split into its own sub-commits per the 5-step sequencing above; do not ship as one commit |
| D — Excel Summary sheet | Small (depends on C) | 1 | Only after C's backend piece lands |
| E — Dead code cleanup | Small, ideally zero (done incrementally) | 2 | N/A |
| F — Warnings | Unscoped | Unscoped | Blocked on §9 |

Recommended order: **A → B → C (5 sub-steps) → D → E**, matching the
user's requested phase lettering with C absorbing D's content until the
backend piece is proven, then D split out as its own commit for the
Excel-specific formatting work.

---

## 9. Open Questions — resolve before implementation

1. **Does "Warnings" exist for this report anywhere?** Grepped
   exhaustively on both frontend and backend — no evidence found. Before
   scoping Phase F, confirm whether this was: (a) carried over from the
   generic phase-template language and doesn't apply to Item Pivot
   specifically, (b) a planned-but-unbuilt feature, or (c) actually exists
   somewhere not yet searched (e.g. a toast/alert triggered by a different
   component, or business-rule validation surfaced elsewhere in the app
   that happens to reference Item Pivot data). Recommend dropping Phase F
   from this migration unless evidence surfaces.
2. **Is the on-screen-only Notification Summary (never in the Excel
   download) a known, accepted gap, or news to the user?** Worth surfacing
   explicitly — today, a user viewing Item Pivot Report on screen sees
   figures (opening balance, blended unit price, restriction pools) that
   do not appear anywhere in the file they download. That's arguably a
   more user-visible inconsistency than anything else found in this
   report, and Phase C exists to close exactly this gap — flagging it here
   in case the user wants to prioritize Phase C above Phases A/B.
3. **Restriction-pool dedup rule fidelity** — the `Set`-based
   dedup-by-`license_number + restriction%` in `calculateNotificationSummary`
   (`ItemPivotReport.tsx:521-546`) is the most business-logic-dense piece
   of client-side code found in this report. Recommend a short walkthrough
   with whoever owns the restriction/condition-pool business rules before
   Phase C begins, to confirm the frontend's interpretation is itself
   correct and worth preserving exactly — not just faithfully translating
   a rule that might itself be subtly wrong.

---

**No code has been changed as part of this document.** Awaiting explicit
approval before starting Phase A.
