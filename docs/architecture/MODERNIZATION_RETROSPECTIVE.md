# Item Pivot Report Modernization — Retrospective

**Scope of this retrospective:** the full Display Dataset Rule migration
for Item Pivot Report — Export Consistency Fixes through Phase 2B.2B and
its cleanup, 2026-08-06 to 2026-08-07. Written as a reusable playbook for
the next migration of this shape (Phase 3, License Ledger Detail, is the
next candidate), not as a general engineering manifesto — every claim
below is grounded in what actually happened in this migration, not
generic advice.

---

## Goal

Enforce the Display Dataset Rule (`docs/02-architecture.md`, "Report &
Export Architecture") for Item Pivot Report: the backend computes every
business value exactly once; JSON, React, and Excel each read that same
value verbatim. No consumer re-derives a number another consumer already
computed.

## Architecture before

```
LicenseBalanceCalculator ─▶ generate_report() ─▶ per-cell values
                                    │             (Balance CIF, Planned
                                    │              Qty/CIF, Unit Price,
                                    │              Restriction %)
                                    │  (already single-sourced — this
                                    │   part was never the problem)
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
              JSON response                 export_to_excel_streaming()
                    │                               │
                    ▼                               ▼
         ItemPivotReport.tsx              re-derives its OWN per-sheet
    ├─ calculateNotificationSummary()      totals from the same cells
    │  (opening balance, restriction
    │  pool, blended unit price —
    │  NEW LOGIC, no backend source
    │  at all)
    ├─ footer TOTAL row (re-sum)
    └─ 3× manual-vs-norm CIF
       selection (re-derived)
```

Two distinct problems, not one: per-cell values were already correctly
single-sourced; the *aggregation* layer (grand totals, the manual-vs-norm
selection rule, and — the largest gap — the Notification/Norm Summary
panel, which existed **only** in the frontend with no backend or Excel
equivalent at all) was where JSON, React, and Excel each went their own
way.

## Architecture after

```
generate_report() also builds, once, server-side:
  - effective_planned_cif / effective_planned_quantity (per cell —
    the manual-vs-norm selection rule, one implementation)
  - notification_totals (per notification group — grand totals)
  - notification_summary / norm_summary (opening balance, restriction
    pool, blended unit price — genuinely new backend logic, not a move)
        │
        ▼
   Display Dataset (one dict per notification group / per norm)
        ├─▶ JSON response
        ├─▶ React — renders verbatim, zero arithmetic beyond formatting
        └─▶ Excel — writes the same objects, zero arithmetic
```

## Migration strategy that worked

Phased, each phase independently shippable and independently testable:

1. **Export Consistency Fixes / Phase 2A** — shared conventions (Display
   Dataset envelope, export filename standardization) before touching
   any single report's business logic.
2. **Phase 2B.1** — thread an existing, already-correct dataset through
   multiple exporters. Low risk: no new logic, just plumbing.
3. **Phase 2B.2A** — consolidate logic that existed in *multiple places*
   into one backend place (grand totals, the manual-vs-norm selection
   rule). Medium risk: mechanical, but wide blast radius (4-5 call
   sites).
4. **Phase 2B.2B** — migrate logic that existed in *only one place* (the
   frontend) with no backend equivalent to build against. This is a
   different kind of work — new backend business logic, not a
   relocation — and needed a different, heavier process (below).

**The single most important process decision:** treating phase 4's kind
of work differently from phases 2-3. A generic "move calculation from
frontend to backend, then delete the frontend copy" template is fine for
phases 2-3. It is dangerous for phase 4, because there is no existing
backend implementation to diff against — a plausible-looking wrong
translation is worse than an obvious crash, and nothing catches it
except independently reproducing the *real* ground truth (the actual
running frontend code, on real data) and diffing against it.

## The sequencing that made phase-4-style work safe

For any new-logic (not relocated-logic) migration:

```
1. Design doc — reverse-engineer the existing implementation
   line-by-line, including its quirks, before writing any backend code.
   Classify every ambiguity as:
     A — preserve for parity, no ambiguity (rare)
     B — business-rule validation required (don't change without
         explicit domain-owner sign-off; migration goal is
         `Backend == Current Frontend` until that sign-off happens)
     C — likely implementation defect (preserve for parity, add a
         regression test pinning the current value, file a separate
         follow-up if the business wants it corrected — don't fix
         inline)
   Commit the design doc on its own, before any code.

2. Business decision — get an explicit answer on every Category B item,
   recorded as a dated addendum to the design doc, its own commit. Do
   not proceed past this point on "probably fine."

3. Backend implementation — additive only. New fields, new response
   keys, nothing renamed or removed yet. Hand-built fixture unit tests
   covering every worked example the design doc identified. Its own
   commit.

4. Real-data parity check — NOT just unit fixtures. Pull real scopes
   from the live database, run the actual (unmodified) frontend logic
   independently (we ported the literal JS into a standalone Node
   script for this), diff field-by-field against the backend's new
   output. Record results in the design doc. This step is a canary:
   write it, run it, record the numbers, delete the script — don't
   accumulate one-off verification scripts as permanent repo tooling.

5. Frontend cutover — only after step 4 passes clean. One commit,
   deleting the old calculation entirely (not leaving it dead in place).
   UI must be pixel- and numerically-identical; if the two
   implementations differ in any *representation* detail (see "DTO key
   format" lesson below), fix it at the display layer, not by changing
   the backend DTO to match old frontend conventions.

6. Other-consumer cutover (Excel, PDF, etc.) — same backend objects,
   zero new arithmetic in the consumer. Its own commit.

7. Cleanup audit — a genuine audit, not an assumption that additive
   work left nothing to clean up (see lesson below). Update the
   calculation-ownership registry.
```

## Lessons learned

1. **"New logic" and "relocated logic" are different risk classes and
   need different processes.** The gate-and-parity-check machinery in
   steps 1-4 above was overkill for Phase 2B.2A (relocated logic, low
   translation risk) and load-bearing for Phase 2B.2B (new logic, real
   translation risk). Match the process to the risk, don't apply either
   extreme uniformly.

2. **An additive-only migration can still reintroduce the exact
   duplication it exists to eliminate — check for this explicitly at
   the end, don't assume additive means clean.** Phase 2B.2B added
   `effective_planned_quantity` specifically so the new
   `_build_notification_summary` could read it — and then that function
   was written to re-derive the same selection rule inline instead,
   because it was built as a "verbatim translation of the frontend,"
   and the frontend never had that field to read. Nobody was wrong to
   write it that way in the moment; the bug was in not checking
   afterward whether the new field actually got consumed. The fix: a
   dedicated cleanup-audit step, after the migration otherwise looks
   done, that greps for every new field/function and confirms every one
   has a real reader — and a regression test that fails loudly (not
   silently) if the duplicate implementation ever comes back.

3. **Cross-language DTO ports need an explicit check for
   representation mismatches, not just value mismatches.** Porting a
   JS object with numeric keys (`{5: {...}}`, which JS stringifies via
   plain `Number.toString()` → `"5"`) to a Python dict with the same
   numeric keys (`str(5.0)` → `"5.0"`) produces identical *values* under
   identical *different* key strings. This is not a parity bug — the
   parity check should compare by numeric value, not string key — but
   it does need a display-layer fix wherever the raw key reaches the
   UI, and it's easy to miss because the underlying data is genuinely
   correct.

4. **Treat one-time verification scripts as canaries, not
   infrastructure.** Writing a throwaway Node port of the frontend logic
   to diff against real backend output was the single highest-value
   step in this migration — it's what turned "the unit tests pass" into
   "we've verified this against production-shaped data." But it doesn't
   belong in the permanent test suite or the scripts directory once
   it's served its purpose; keep the *result* (recorded in the design
   doc) and the regression tests it justified, not the script itself.

5. **A calculation-ownership registry is more useful scoped honestly
   than claimed complete.** `docs/architecture/CALCULATION_OWNERSHIP.md`
   distinguishes "fully verified this session," "owner confirmed to
   exist but not independently audited," and "not yet audited" — that
   distinction is what makes the document trustworthy enough to actually
   consult later, rather than a one-time snapshot nobody double-checks.

6. **This environment has genuine concurrent-session risk — verify
   `git status`/`git diff --stat` scope before and after every
   agent-delegated commit**, not just at the start. Two unrelated
   commits (a config value change, and an in-progress A3627 auto-plan
   feature) landed in this same working tree from what was evidently a
   different concurrent session, mid-migration. Nothing was lost, but
   only because every commit in this migration was scoped by explicit
   file path (`git add <specific files>`), never a broad `git add -A`/`.`.

## Reusable checklist for the next Display Dataset migration

- [ ] Calculation inventory: for every value the report displays, is it
      computed once (backend) or independently in more than one place?
- [ ] For each duplicate found, classify: relocate existing logic
      (lower risk, mechanical) vs. new logic with no backend equivalent
      (higher risk, needs the full parity-check sequencing above).
- [ ] Design doc committed before any code, including a line-by-line
      reverse-engineering of whatever the "ground truth" implementation
      currently is.
- [ ] Every business-rule ambiguity found gets an explicit decision
      recorded in writing before implementation — not assumed.
- [ ] Backend implementation is additive-only until parity is proven.
- [ ] Parity is checked against real data, not just hand-built fixtures.
- [ ] UI cutover happens in its own commit, only after parity, and
      preserves exact display output (watch for cross-language
      representation mismatches, not just value mismatches).
- [ ] Every other consumer (Excel, PDF, ...) gets its own cutover
      commit reading the same backend object, zero new arithmetic.
- [ ] Cleanup audit at the end explicitly checks that every new
      field/function added during the migration has a real reader —
      don't assume "additive" means "nothing to clean up."
- [ ] Calculation-ownership registry updated, scoped honestly (verified
      vs. owner-confirmed vs. not-yet-audited).
