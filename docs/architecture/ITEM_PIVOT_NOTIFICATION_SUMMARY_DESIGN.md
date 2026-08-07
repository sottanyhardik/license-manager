# Item Pivot Report — Notification Summary Migration Design (Phase 2B.2B)

**Status:** Design only. No code changes made. Do not implement until this
document is explicitly approved.
**Prerequisite:** Phase 2B.2A complete (`b32b2f75` — backend-owned
`notification_totals` and `effective_planned_cif`). This document picks up
exactly where §7 "Phase C" of
`docs/architecture/ITEM_PIVOT_DISPLAY_DATASET_DESIGN.md` left off, and
supersedes that section with a fully reverse-engineered spec — the original
Phase C section described *what* to build; this document specifies *exactly
how*, line-for-line against the current frontend implementation.
**Scope:** `backend/apps/license/views/item_pivot_report.py`,
`frontend/src/pages/reports/ItemPivotReport.tsx:507-621` (the summary
engine) and its two call sites (`:1386`, `:1531`).

---

## 0. Why this is the highest-risk phase

Per the parent design doc's Risk Report (§5), this is rated **Critical**,
distinct from Phases A/B which were pure "move existing logic" work: the
Notification/Norm Summary panel is **new backend business logic**, not a
relocation. There is no backend or Excel value to diff against today — the
only spec that exists is the frontend implementation itself
(`calculateNotificationSummary`, `ItemPivotReport.tsx:507-621`). Getting the
translation wrong produces a *plausible-looking* wrong number, which is
worse than a crash. This document exists to remove that risk by reading the
current implementation exactly, once, and writing down every branch —
including the quirks — before any backend line is written.

---

## 1. Reverse-engineered spec of `calculateNotificationSummary`

Verified against `ItemPivotReport.tsx:507-621` at current HEAD, both call
sites (`:1386` — per notification group; `:1531` — per norm, flattened
across notifications), and the render blocks that consume the return value
(`:1388-1512`, `:1538-1616`).

**Inputs:** `licenses` (an array of license row objects for the scope —
either one notification group, or every license under a norm flattened
across notifications), plus the module-level `reportData.items` (the
report's ordered item catalogue, shared across all scopes).

**Pass 1 — opening balance:**
```
openingBalance = Σ toFiniteNumber(license.balance_cif) over licenses
```
`toFiniteNumber` (`:112-115`) is `parseFloat` guarded against
`NaN`/non-finite → falls back to `0`. This is the same shape as
`notification_totals[...]['balance_cif']` from Phase 2B.2A, but computed
independently here — see §9 quirk (c).

**Pass 2 — restriction pool dedup (shared value, once per license×percentage):**
```
processedRestrictions = ∅   // Set of "license_number_percentage" keys
for license in licenses:
    for item in reportData.items:
        itemData = license.items[item.name]
        if itemData exists and itemData.restriction is not null/undefined:
            pct = toFiniteNumber(itemData.restriction)
            key = f"{license.license_number}_{pct}"
            if key not in processedRestrictions:
                processedRestrictions.add(key)
                restrictedItemsByPercentage[pct].sharedRestrictionValue
                    += toFiniteNumber(itemData.restriction_value)
```
The dedup key is **license × percentage**, not license × item. This encodes
a real business rule: `restriction_value` on a license is a *shared quota*
against that license's restriction percentage, not a per-item value — if
two items on the same license both carry a 5% restriction, the license's
restricted CIF pool is counted **once**, not twice. This is the single
piece of logic in this migration most likely to be subtly wrong if
re-derived from first principles instead of copied verbatim. See §3 for a
worked example.

**Pass 3 — per-item aggregation across licenses, in `reportData.items` order:**
```
for item in reportData.items:
    itemAvailable = 0; itemPlanned = 0; itemPlannedQty = 0
    hasRestriction = false; restrictionPercentage = 0
    for license in licenses:
        itemData = license.items[item.name]
        if itemData exists:
            itemAvailable += toFiniteNumber(itemData.available_quantity)
            itemHasManual = toFiniteNumber(itemData.plan_cif) > 0
                          or toFiniteNumber(itemData.plan_quantity) > 0
            itemPlanned    += itemHasManual ? plan_cif      : planned_cif
            itemPlannedQty += itemHasManual ? plan_quantity : available_quantity
            if itemData.restriction is not null/undefined:
                hasRestriction = true
                restrictionPercentage = toFiniteNumber(itemData.restriction)
                // last license wins if licenses disagree on pct — see §9(a)

    if itemAvailable > 0 or itemPlanned > 0:
        itemSummary = {
            available:   itemAvailable > 0 ? itemAvailable : itemPlannedQty,
            planned_cif: itemPlanned,
            planned_qty: itemPlannedQty,
            unit_price:  itemPlannedQty > 0 ? itemPlanned / itemPlannedQty : 0,
        }
        (route into regularItems[item.name] or
         restrictedItemsByPercentage[pct].items[item.name])

        totalAvailable   += itemAvailable        // NOT itemSummary.available — see §9(b)
        totalPlanned      += itemPlanned
        totalPlannedQty   += itemPlannedQty
```

**Grand total ("blended") row**, rendered separately, not stored on the
summary object under its own key — computed inline at render time
(`:1499-1502`, `:1602-1604`):
```
blendedUnitPrice = totalPlannedQty > 0 ? totalPlanned / totalPlannedQty : 0
```

**Two call sites, same function, different scope:**
- `:1386` — one call per notification group, `licenses` = that group's
  license list. Rendered as the per-notification "Summary" card.
- `:1531` — one call per active norm tab, `licenses` = every license
  across every notification under that norm, flattened with
  `Object.values(...).flat()`. Rendered as the "Norms Total Summary" card.
  This card *also* independently recomputes opening balance via its own
  `reduce()` over the flattened licenses (`:1528-1530`) instead of reading
  `ns.openingBalance` — a second, redundant copy of Pass 1 that happens to
  agree with the first. Not a behavior difference, just duplicate work to
  not bother replicating server-side.

---

## 2. Notification Summary DTO

Naming follows the sibling convention Phase 2B.2A already established
(`notification_totals[norm_class][notification_key]`) rather than the
generic `summary` key sketched in the parent design doc's §6 — this keeps
the two backend-owned aggregate objects visually paired in the JSON and in
code.

```jsonc
{
  // Existing, unchanged (Phase 2B.2A):
  "notification_totals": { "<norm_class>": { "<notification_key>": { ... } } },

  // NEW:
  "notification_summary": {
    "<norm_class>": {
      "<notification_key>": {
        "opening_balance": 0.0,
        "total_available": 0.0,
        "total_planned_cif": 0.0,
        "total_planned_qty": 0.0,
        "blended_unit_price": 0.0,        // total_planned_cif / total_planned_qty, 0 if qty is 0
        "regular_items": {
          "<item_name>": {
            "available": 0.0, "planned_cif": 0.0,
            "planned_qty": 0.0, "unit_price": 0.0
          }
        },
        "restricted_items_by_percentage": {
          "5.0": {                         // string key — percentage as encountered
            "shared_restriction_value": 0.0,
            "items": {
              "<item_name>": {
                "available": 0.0, "planned_cif": 0.0,
                "planned_qty": 0.0, "unit_price": 0.0
              }
            }
          }
        }
      }
    }
  },

  // NEW: same shape, one level up — flattened across every notification
  // under the norm. Replaces the `:1531` call site.
  "norm_summary": {
    "<norm_class>": {
      "opening_balance": 0.0,
      "total_available": 0.0,
      "total_planned_cif": 0.0,
      "total_planned_qty": 0.0,
      "blended_unit_price": 0.0,
      "regular_items": { "...": "..." },
      "restricted_items_by_percentage": { "...": "..." }
    }
  }
}
```

`notification_summary` and `norm_summary` are both produced by a single
shared builder function (see §6), called once per notification group and
once per norm (flattened), mirroring exactly how the frontend calls
`calculateNotificationSummary` twice today. No new per-cell fields are
required for this DTO beyond §5's `effective_planned_quantity`.

---

## 3. Restriction Pool algorithm — worked example

Two licenses under one notification group, both carrying item **X**, one
also carrying item **Y**:

| License | Item | restriction (%) | restriction_value |
|---|---|---|---|
| LIC-A | X | 5 | 1000 |
| LIC-A | Y | 5 | 1000 |
| LIC-B | X | 5 | 800 |

**Naive (wrong) approach** — sum `restriction_value` over every
`(license, item)` row with a restriction: `1000 + 1000 + 800 = 2800`. This
overcounts LIC-A's restricted pool because the 5% restriction is a
per-license quota shared by X and Y, not two independent 1000-value pools.

**Correct (dedup) approach**, per §1 Pass 2:
- `(LIC-A, X)` → key `LIC-A_5` not seen → add, `sharedRestrictionValue[5] = 1000`
- `(LIC-A, Y)` → key `LIC-A_5` **already seen** → skip
- `(LIC-B, X)` → key `LIC-B_5` not seen → add, `sharedRestrictionValue[5] = 1000 + 800 = 1800`

Result: `restricted_items_by_percentage["5"].shared_restriction_value = 1800`,
and both X and Y appear under that group's `items`, each with their own
`available`/`planned_cif`/`planned_qty`/`unit_price` (those *are* per-item,
only the restricted-value pool is shared).

---

## 4. Blended Unit Price — formal definition

```
blended_unit_price(scope) = Σ effective_planned_cif(item, scope)
                             ────────────────────────────────────
                             Σ effective_planned_qty(item, scope)
```
where the sums run over every item in `reportData.items` that appears in
scope (a notification group or a flattened norm), and each per-item
numerator/denominator is itself first summed across every license in that
scope using the manual-vs-norm selection rule (§5). This is **not** an
average of each item's `unit_price` column — it is total CIF over total
quantity, computed once at the bottom of the aggregation, which is why two
items with very different unit prices but similar quantities pull the
blended figure toward the item with more planned CIF, not toward a simple
average. Division by zero (`total_planned_qty == 0`) yields `0`, matching
the existing frontend ternary — never `NaN`/`Infinity`.

**Rounding:** the frontend stores the unrounded float in state and only
applies `.toFixed(2)` at render time (`:1429`, `:1467`, `:1500`, `:1603`).
Existing backend `unit_price` fields elsewhere in this file round to 2
decimal places at computation time (e.g. `item_pivot_report.py:1083`,
`round(item_plan / uq, 2)`). **Recommendation:** round `unit_price` and
`blended_unit_price` to 2 decimals server-side, for consistency with every
other unit-price field already in the Display Dataset. This is a
deliberate, minor behavior change (backend-rounds vs. frontend's
full-float-then-format) — call it out explicitly in the parity check (§7
step 3) as an *expected* rounding-only diff, not a bug.

**Test cases to encode in the backend unit test (§7 step 1):**

| total_planned_cif | total_planned_qty | expected unit_price | note |
|---|---|---|---|
| 1000.00 | 50 | 20.00 | normal case |
| 0 | 0 | 0.00 | no plan at all — must not be `NaN` |
| 500.00 | 0 | 0.00 | qty-zero guard fires even when CIF is nonzero (matches current ternary; flagged as a quirk, not "fixed") |
| 333.33 | 3 | 111.11 | rounding boundary (111.11̄ → verify banker's vs. round-half-up matches Python's `round()`) |

---

## 5. `effective_planned_quantity` — new per-cell field

Phase 2B.2A added `effective_planned_cif` (`_effective_planned_cif`,
`item_pivot_report.py:41-52`) but no quantity counterpart, because nothing
consumed one yet. This migration is the first consumer: Pass 3's
`itemPlannedQty` needs the identical manual-vs-norm branch applied to
*quantity*, and today there is no single backend field encoding it — the
frontend re-derives `itemHasManual` itself (§1 Pass 3), which is a **sixth**
copy of the selection rule the parent design doc's §1 inventory didn't
count (it only tracked the CIF-selection copies).

Add, mirroring `_effective_planned_cif` exactly:
```python
def _effective_planned_quantity(plan_quantity, plan_cif, planned_quantity, available_quantity):
    """Quantity counterpart to _effective_planned_cif — same manual-vs-norm
    branch, applied to quantity instead of CIF. The norm-derived branch uses
    available_quantity because the E1/E5/E132 waterfall always plans against
    the full available balance; there is no separate norm-planned-quantity
    field."""
    pq = plan_quantity or 0
    pc = plan_cif or 0
    return pq if (pq or pc) else (available_quantity or 0)
```
Note the branch selects `pq` (not recomputing from `pc`) when manual —
consistent with `itemData.plan_quantity` being the authored quantity
alongside `plan_cif`. Exposed per cell as `effective_planned_quantity`,
additive next to `effective_planned_cif`, same call site
(`_build_license_row`, `item_pivot_report.py:1371` area).

**Selection-condition fidelity note:** `_effective_planned_cif` uses
Python truthy (`pq or pc` — fires on any nonzero, including a
hypothetical negative), while the frontend's `itemHasManual` uses
`plan_cif > 0 || plan_quantity > 0` (strictly positive only). These agree
for every value these fields can actually take in this domain (planned
quantities/CIF are never negative), so no behavior difference is expected
— noted here so nobody "fixes" one to match the other under the mistaken
belief they currently disagree.

---

## 6. Backend builder — shape

One function, called twice (once per notification group, once per
flattened norm), exactly mirroring the frontend's two call sites:

```python
def _build_notification_summary(licenses, items):
    """Translates ItemPivotReport.tsx:507-621 (calculateNotificationSummary)
    verbatim, including its quirks (see design doc §9) — do not
    'improve' the logic here without a corresponding product decision."""
    ...
```
Called as:
```python
notification_summary[norm][notification_key] = _build_notification_summary(
    licenses_list, items
)
...
norm_summary[norm] = _build_notification_summary(
    [lic for notifications in licenses_by_norm[norm].values() for lic in notifications],
    items
)
```
Placed alongside the existing `notification_totals` construction
(`item_pivot_report.py:654-750`) so both backend-owned aggregates are built
in the same pass over the same license lists — no second full iteration
needed.

---

## 7. Parity strategy (expands parent design doc §7 Phase C, steps 1-5)

1. Implement `_build_notification_summary` and `_effective_planned_quantity`
   as pure functions; unit-test against hand-computed fixtures covering:
   the restriction-pool dedup worked example (§3), the blended-unit-price
   test table (§4), an item with `available_quantity > 0` but no plan
   (regular item, unit_price 0), and a manually-split item with
   `available_quantity == 0` (e.g. a "DWP - E1" split line) to confirm the
   `available: itemAvailable > 0 ? itemAvailable : itemPlannedQty` fallback
   is preserved.
2. Add `notification_summary` and `norm_summary` to the JSON response
   additively. Frontend keeps calling `calculateNotificationSummary` for
   both cards — zero UI change yet.
3. Add a temporary, dev-only parity check (not a permanent test) that
   fetches a sample of real filter combinations and diffs the new backend
   objects against the frontend's own computed values for the same data,
   after rounding both sides to 2 decimals on `unit_price`/
   `blended_unit_price` (§4's rounding note is an *expected* diff at full
   float precision — the check must tolerate it, not flag it). Any other
   diff is a translation bug and blocks step 4. Promote the fixtures used
   here into a permanent backend regression test (`test_item_pivot_
   notification_summary_parity.py` or similar) rather than discarding them
   once parity is confirmed — they are the proof that Category C items
   (§9(b), §9(c)) were preserved on purpose, not missed.
4. **Business review gate — do not skip.** Before touching any UI code,
   walk the parity results and §9's Category B/C items past whoever owns
   the restriction/condition-pool business rules:
   - Category B (§9(a), and the dedup rule itself, §3/§10 Q2) needs an
     explicit answer: is the current frontend behavior correct, or does it
     need to change? If it needs to change, that's a separate,
     explicitly-scoped follow-up — not folded into this migration.
   - Category C (§9(b), §9(c)) needs an explicit "preserve as-is, file a
     follow-up issue" or "fix now" decision — do not let either get fixed
     silently as a side effect of the rewrite.
   Record the decision inline in this document (or a dated addendum)
   before proceeding to step 5.
5. Only after the business review gate closes, switch both
   `ItemPivotReport.tsx` call sites (`:1386`, `:1531`) to read
   `notification_summary`/`norm_summary` from `reportData`, and delete
   `calculateNotificationSummary` (`:507-621`) entirely — there are exactly
   two call sites, both replaced in the same commit.
6. Add the Excel Summary sheet (§8), reading the same backend objects —
   no new backend logic, pure formatting.

**Rollback:** steps 2-3 are additive and never reach the UI — trivially
revertible with no user impact. Step 5 is the only user-visible change;
revert that single commit if a discrepancy surfaces post-ship, independent
of whether the backend objects themselves are kept for the Excel sheet.

---

## 8. Excel Summary Sheet

Decision: **reuse `notification_summary`/`norm_summary` verbatim** — do not
build a fourth independent implementation. The sheet is a direct
transcription of the same object already used by JSON and React:
- One "Summary" sheet (or a section per norm tab, matching the per-norm
  sheet structure the exporter already uses for the main pivot data —
  confirm against current sheet-per-norm layout before implementing) with:
  Opening Balance row → regular items rows → restricted-items-by-percentage
  groups with their shared-value subtotal row → grand total row with
  `blended_unit_price`.
- No arithmetic in the exporter beyond number formatting — every value is
  read directly off `notification_summary[norm][notification_key]` /
  `norm_summary[norm]`, the same objects React renders.

This is purely Phase 7 step 5 above; called out as its own checklist item
only because it was requested as a separate deliverable, not because it
needs separate backend work.

---

## 9. Quirks found during reverse-engineering — preserve, don't silently fix

These are genuine ambiguities in the current implementation. The
translation should replicate them exactly (since that's what "no
behavior change" means), but they're flagged here so the user can decide
if any should be corrected as part of this migration rather than carried
forward unexamined.

**(a) [Category B — business validation required] Restriction percentage
is "last license wins" per item.** In Pass 3,
`restrictionPercentage` is overwritten on every license iteration that has
a restriction for that item — if two licenses in the same scope disagree
on the percentage for the same item (data inconsistency, but not
impossible), the summary silently uses whichever license was iterated
last, with no error or warning. Not something to fix without a product
decision; flagging so it isn't "fixed" as an unreviewed side effect of the
backend rewrite.

**(b) [Category C — likely implementation defect, preserve for parity]
`totalAvailable` sums raw `itemAvailable`, not the displayed
`available` value.** The row's own `available` field falls back to
`itemPlannedQty` when `itemAvailable` is 0 (for split-planned items with no
import counterpart), but the grand-total row sums the pre-fallback
`itemAvailable` — so a split item can show a nonzero "Available" in its
own row while contributing 0 to the total's Available column. This is a
real (if minor) footer-doesn't-foot-the-rows-above-it inconsistency that
exists today; replicate it as-is unless the user wants it fixed here.

**(c) [Category C — likely implementation defect, preserve for parity]
Opening balance is computed independently at both call sites'
scopes**, and separately from Phase 2B.2A's `notification_totals[...]
['balance_cif']`, which sums the exact same `license.balance_cif` values.
Three call sites computing the same sum today (Pass 1 here ×2, plus
2B.2A's totals). The backend builder in §6 does not need to recompute this
a third way — `notification_summary[...]['opening_balance']` can simply
equal `notification_totals[...]['balance_cif']` where scopes match
one-for-one (they do, for the per-notification case); for `norm_summary`
there is currently no norm-level `notification_totals` equivalent to reuse,
so that one sum is computed once in the builder. Worth a one-line
comment at implementation time noting the two fields are intentionally
kept in sync, not coincidentally equal.

---

## 10. Open questions — classified

Carried forward from the parent design doc's §9, still unresolved as of
this document — do not schedule implementation until answered. Each is
classified so the migration goal for that item is unambiguous going in:

| # | Question | Category | Migration goal until resolved |
|---|---|---|---|
| 1 | Is the on-screen-only Notification/Norm Summary (never in today's Excel download) a known, accepted gap, or news to the user? | — (scoping, not a behavior question) | Confirm priority to close it now, ahead of Phase 2B.2D cleanup |
| 2 | Restriction-pool dedup rule fidelity (§3) — is `license_number × percentage` dedup itself business-correct, or does it need a domain-owner walkthrough first? | **B — business validation required** | `Backend == Current Frontend` first. Reproduce the existing rule exactly; do not change the algorithm before parity is proven, and only change it afterward with explicit business sign-off |
| 3 | §9(a) last-license-wins restriction % — carry forward, or fix? | **B — business validation required** | Same as above: preserve for parity now, revisit only after domain-owner confirms intended behavior |
| 4 | §9(b) footer-vs-row `totalAvailable` inconsistency — carry forward, or fix? | **C — likely implementation defect** | Preserve as-is in this migration; add a regression test that pins the *current* (quirky) value so any future change is deliberate; file a separate follow-up issue if the business wants it corrected |
| 5 | §9(c) triple opening-balance computation — carry forward, or consolidate? | **C — likely implementation defect** | Preserve the *value* for parity (§9(c) already notes the backend builder can share the sum with `notification_totals` without changing behavior); no separate follow-up needed since consolidating the computation, unlike (4), doesn't change any displayed number |
| 6 | "Warnings" — still no evidence found anywhere in the codebase (parent doc §9.1) | — (scoping) | Not in scope for this phase; do not add speculatively |

**Rule of thumb applied above:** Category A (plain "preserve for parity,
no ambiguity") doesn't appear in this table because every quirk found
during reverse-engineering turned out to touch either a business rule
(B) or a visible-but-questionable number (C) — there were no "obviously
preserve, obviously fine" quirks worth a separate row.

---

## 11. Phase 2B.2B implementation gate

Do not begin §7 step 1 (backend code) until every box below is checked.
This gate exists because this phase is rated Critical risk (§0) — the cost
of pausing here is a review meeting; the cost of getting the restriction
pool math wrong in a financial report is much higher.

- [x] Design document committed (this document — `3b4fc0a8`).
- [x] DTO (§2) finalized — no further shape changes expected.
- [x] Restriction pooling rule (§3, §10 Q2/Q3) explicitly marked
      "preserve current behavior" by the business owner — see §12.
- [x] Blended unit-price formula (§4) approved, including the
      backend-rounds-to-2dp decision — see §12.
- [x] `effective_planned_quantity` (§5) accepted as a required new
      backend field — see §12.
- [ ] Parity test fixtures (§7 step 1) drafted and reviewed.
- [x] §10 Q4/Q5 (Category C items) have an explicit "preserve, file
      follow-up" decision recorded — see §12.

Six of seven boxes are checked as of §12's decision. The remaining box —
parity fixtures — is the next concrete step, not a review gate: it is
produced *during* §7 step 1 (the hand-computed fixtures in §3/§4 are the
starting point) and should be reviewed for correctness before the
backend implementation is trusted, but no further business sign-off is
required to write it.

---

## 12. Business decision — approved 2026-08-07

**Decision: Option A — Preserve current behavior exactly.** The objective
of Phase 2B.2B is architectural consolidation (single backend owner), not
a change to business behavior. Recorded rules, verbatim intent:

- The backend becomes the single authoritative owner of the Restriction
  Pool calculation (§3) and the Notification/Norm Summary (§2) as a whole.
- The backend implementation must match the current frontend output
  exactly — including quirks §9(a) (last-license-wins restriction %),
  §9(b) (footer `totalAvailable` vs. fallback-adjusted row value), and
  §9(c) (redundant opening-balance computation). None of the three are to
  be corrected as part of this migration.
- §10 Q2/Q3 (Category B — restriction-pool dedup rule, last-license-wins)
  resolved as: reproduce exactly; any change to the algorithm itself is a
  separate, future, explicitly-approved phase (design update + regression
  analysis + its own implementation), not part of 2B.2B.
- §10 Q4/Q5 (Category C — footer inconsistency, redundant opening-balance
  sum) resolved as: preserve for parity. §9(b) may get a separate
  follow-up issue if the business later wants it corrected; §9(c) needs
  no follow-up since consolidating *how* the sum is computed doesn't
  change the displayed value (per §9(c)'s own note — `notification_summary`
  can share `notification_totals['balance_cif']` for the per-notification
  scope with zero behavior difference).
- The frontend (`ItemPivotReport.tsx`) stays unchanged until backend/
  frontend parity is demonstrated on the approved regression fixtures —
  do not delete `calculateNotificationSummary` in the same change that
  adds the backend fields.
- Excel must consume `notification_summary`/`norm_summary` verbatim (§8)
  with no independent arithmetic, once added — no fourth implementation.
- The §4 backend-rounds-to-2dp decision is compatible with "match current
  frontend output exactly" because the frontend already displays
  `unit_price`/`blended_unit_price` via `.toFixed(2)` at render — rounding
  one step earlier, server-side, does not change what a user sees. Noted
  here explicitly since it is a stored-precision change even though it is
  not a displayed-value change.

**Explicitly deferred (not part of 2B.2B):** changing the restriction-pool
algorithm; correcting §9(a)/(b)/(c); altering any report value; any new
business calculation beyond relocating existing logic to the backend;
any user-visible change to Notification Summary numbers.

This decision clears gate items 1, 2, 3, 4, 5, and 7 in §11. Item 6
(parity fixtures) remains open and is the next step (§7 step 1).

---

**No code has been changed as part of this document.** §7 step 1
(backend implementation, additive to JSON only — no frontend or Excel
changes) may now begin.
