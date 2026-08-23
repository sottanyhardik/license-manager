# BL-PLAN-01 — E126/E132 Auto-Plan: planned_cif_fc is computed from the
pre-floor quantity, not the persisted (floored) planned_quantity

## Files / functions
- `backend/apps/license/services/e126_auto_plan.py` — `compute_e126_auto_plan()`, lines ~242-272 (non-preserved branch) and ~219-241 (preserved branch inherits the same original error)
- `backend/apps/license/services/e132_auto_plan.py` — `compute_e132_auto_plan()`, identical pattern, lines ~239-269
- Root helpers (both files, byte-identical): `_floor_qty()`, `_r2()`
- Correct sibling pattern for comparison: `backend/apps/license/services/e5_plan.py::_fixed_rate_line()` (floors qty, then recomputes `planned_cif = planned_qty * rate` from the FLOORED quantity)

## Root cause
Both `compute_e126_auto_plan` and `compute_e132_auto_plan` take the engine's
raw per-line output (`sp['planned_quantity']`, `sp['unit_price']`,
`sp['planned_cif']` from `plan_e126_per_item_split` / `plan_e132_per_item_split`)
and do:

```python
fqty = _floor_qty(planned_qty)   # floors the quantity to a whole number
cif  = _r2(planned_cif)          # keeps the CIF value computed from the
                                  # UN-FLOORED planned_qty

item_lines.append({
    'planned_quantity': fqty,
    'unit_price':       _r2(unit_price),
    'planned_cif_fc':   cif,      # != fqty * unit_price whenever planned_qty
                                   # had a fractional part
    ...
})
```

`planned_cif_fc` is never recomputed as `fqty * unit_price`. Whenever the
engine's raw `planned_quantity` has a fractional part — which happens for
EVERY plain category whose available_quantity is not a whole number, and
(more importantly) for BOTH halves of E126's PKO/Olive-Oil 50/50 split and
E132's PKO/Cheese 40/60 split whenever the group's summed
`available_quantity` is not evenly divisible by 2 (E126) or 5 (E132) — the
saved `LicenseItemPlan` row's `planned_cif_fc` no longer equals
`planned_quantity * unit_price`.

`save_plan_lines_for_license` (`plan_enforcement.py`) then sets
`remaining_quantity = planned_quantity` and `remaining_cif_fc =
planned_cif_fc` verbatim for a fresh (non-preserved) line, so the
inconsistency is baked into the row for the lifetime of the plan line
(including every future "preserved once generated" re-emission — see the
`preserved` branch, which just re-emits whatever `remaining_cif_fc` was
originally saved).

The sibling E5 engine solves the IDENTICAL problem (floor Auto-Plan
quantities to whole numbers) correctly: `e5_plan.py::_fixed_rate_line()`
computes `planned_qty = floor(...)` and then `planned_cif = planned_qty *
rate` — i.e. it recomputes the value FROM the floored quantity. E126/E132's
auto-plan modules diverge from this established, correct pattern.

## Effect
For every affected plan line: `planned_quantity` (and therefore
`remaining_quantity`, and the physical goods quantity the plan says can be
imported) is under-recorded by up to just-under-1 unit, while
`planned_cif_fc` (and `remaining_cif_fc`) keeps the full, un-floored CIF
value. This:
  * permanently consumes real DFIA license Balance CIF (a legally-capped,
    scarce import entitlement) against NO recorded plannable quantity —
    the license's `remaining_cif` (`balance_cif - total_planned_cif`)
    understates what is actually still usable;
  * leaves the persisted `LicenseItemPlan` row internally inconsistent
    (`planned_cif_fc != planned_quantity * unit_price`), which several
    other parts of the codebase implicitly assume holds (e.g.
    `plan_grouping._effective_rate`/`_blended_pko_olive_rate` recompute a
    rate as `value / qty` for REPORTING elsewhere, which would show a
    different, WRONG effective rate than the fixed ceiling price stored on
    this row, were that recomputation ever applied to a persisted plan row
    instead of a live per-item result).

## Reproduction (exact commands run)
```
cd backend && source ../.venv/bin/activate
PYTHONPATH=<repo>/backend python3 <repo>/audit_evidence/pass1/BL-PLAN/01/repro.py
PYTHONPATH=<repo>/backend python3 <repo>/audit_evidence/pass1/BL-PLAN/01/db_context.py
```
Full output captured in `query_result.txt` (this directory). Scripts are in
`repro.py` / `db_context.py` (this directory) — both call the real,
unmodified production functions (`plan_e126_per_item_split`,
`classify_e132_record`, `detect_norm`); no source file was edited and no
row was written to the real `lmanagement` DB.

### Key result (repro.py)
Input: one E126 PKO/Olive-Oil split-eligible import-item group,
`available_quantity = 101` (an ordinary odd whole-number weight),
`balance_cif = 343.40` (exactly the base 50/50 split's value, so the
wastage-rebalance pass — which is separate, correct, documented behavior —
has nothing to shift, isolating this bug).

| item_name | planned_quantity (saved) | unit_price (saved) | planned_cif_fc (saved) | qty × price | mismatch |
|---|---|---|---|---|---|
| PALM KERNEL OIL - E126 | 50.0 | 1.80 | **90.90** | 90.00 | **+0.90** |
| OLIVE OIL - E126 | 50.0 | 5.00 | **252.50** | 250.00 | **+2.50** |

Total `planned_cif_fc` recorded = 343.40 = 100% of `balance_cif`, while only
100 of the group's 101 available units are ever recorded as planned
(`50 + 50 = 100`, the 101st unit is silently dropped). `remaining_cif` is
therefore reported as `$0.00` even though 1 real unit's worth of Balance
CIF entitlement was never actually attributed to any plannable quantity.

### Real-DB context (db_context.py)
- The real local DB currently has 0 licenses classified `E126` and 2
  classified `E132` (license 2462 `0311041993`, license 2435 `0311046523`
  — `detect_norm()` distribution: `{'E5': 76, '': 124, 'E1': 25, 'A3627':
  1, 'E132': 2}`). Neither real E132 license currently has an import item
  that satisfies BOTH the PKO and Cheese signals on the same record (see
  full per-item classification in `query_result.txt`), and E132's only
  classified item (id 37537, available_quantity 4.00) is below
  `MIN_PLAN_QTY = 50` and would not be auto-planned anyway. **So this
  defect has not yet corrupted any real license's `LicenseItemPlan` rows
  in this specific 228-license snapshot.**
- However, fractional `available_quantity` values ARE already present
  elsewhere in this exact DB for other norms (22 of 2401 import items,
  e.g. import_item 37986 on license_id 2664 has `available_quantity =
  3066.09`) — confirming this is an entirely realistic DGFT-derived data
  shape, not a contrived edge case, and the bug will fire on the very next
  E126 license, or the next E132 PKO+Cheese-signal item, whose group's
  summed `available_quantity` isn't an exact multiple of 2 (E126) / 5
  (E132) — which is the common case, not the exception, given real DGFT
  weight figures are essentially never engineered to be exact multiples of
  5.

## Expected vs actual
- Expected: `planned_cif_fc == round(planned_quantity * unit_price, 2)`
  for every `LicenseItemPlan` row Auto-Plan writes (this invariant holds
  for E1/E5's own floor-then-price pattern, and is implicitly assumed by
  reporting code elsewhere in the planning stack).
- Actual: for E126/E132, `planned_cif_fc` is computed from the un-floored
  quantity and never reconciled with the floored `planned_quantity` that
  is actually saved, producing a silent, permanent CIF/quantity mismatch
  on the persisted plan row whenever the classified (or split) quantity is
  fractional.

## Suggested fix (not applied — read-only investigation pass)
In both `e126_auto_plan.py` and `e132_auto_plan.py`'s non-preserved branch,
recompute `cif = round(fqty * _r2(unit_price), 2)` from the FLOORED
quantity (mirroring `e5_plan.py::_fixed_rate_line`'s pattern), instead of
keeping `_r2(planned_cif)` computed from the pre-floor quantity. This is a
pure bugfix to internal arithmetic consistency; it does not change any
public API shape, so no `api_breaking_change_flagged` note is needed — but
it DOES change persisted `LicenseItemPlan.planned_cif_fc` values for
future Auto-Plan runs on affected licenses, so it should go through the
normal fix+regression-test path with an explicit before/after check on
`test_e126_auto_plan.py` / `test_e132_auto_plan.py` (which currently only
exercise even quantities and therefore never caught this).

## Confidence
High — proven by directly executing the actual, unmodified production
functions and by inspecting the source line-by-line; the exact numeric
mismatch is reproducible and deterministic. Marked `ambiguous: false` (this
is a straightforward arithmetic-consistency bug, not a business-rule
judgment call). The only caveat is that it has not yet manifested against
any of the 228 real licenses currently in the local DB — noted above as
context, not as doubt about the defect itself.
