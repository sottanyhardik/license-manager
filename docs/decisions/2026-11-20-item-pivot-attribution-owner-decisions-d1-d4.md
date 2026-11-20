# Item Pivot / Item Report — owner decisions D1–D4 (2026-11-20)

Resolves the OPEN items D1–D4 in `2026-11-20-item-pivot-attribution-open-decisions.md`. Recorded by session
license-manager-cb from the owner's answers in conversation; **not yet implemented**. These decisions apply to
**both** Item Pivot and the aligned Item Report (Item Report must reuse the pivot engine, so the two reconcile).

| # | Case | Owner decision | Change vs current |
|---|------|----------------|-------------------|
| D1 | Two STANDARD plans on the same source both fall back (no usage mapped to either target) | **Proportional**: split the unmapped BOE / allotment rows between the plans in proportion to their planned CIF (counted once in total). | BUSINESS-RULE CHANGE (was: first plan in plan order takes all). |
| D2 | Row mapped to Item Name X on a source where X has no plan; source plan has no usage mapped to its own target | **NOT ATTRIBUTED** (`target_not_planned`); never shown under an item it was not mapped to. | BUSINESS-RULE CHANGE (was: legacy fallback to the plan's cell). |
| D3 | Billed-without-BOE on a percentage-split source | **Apportion by split %**: deduct from each split target's balance by its split percentage; target balances sum to the source balance. | BUSINESS-RULE CHANGE (was: once in NOT ATTRIBUTED, not deducted). |
| D4 | Reconciliation compares canonical licence CIF with raw item rows | **Keep current** (definitions text explains differences). | None. |

Implementation constraints (from the Item Report alignment spec): licence-level canonical CIF unchanged; no double
counting of BOE CIF, outstanding allotment CIF or billed-without-BOE; apportionment must be Decimal-safe with an explicit
rounding remainder rule so the parts sum exactly to the source amount; zero vs missing preserved. Requires
`cif-balance-auditor` (Opus) review and tests before landing.

## Implementation note (2026-11-20, session d3)
- Rounding remainder rule (D1/D3): **largest remainder** — each share is the proportional amount rounded down to 3 dp
  (qty) / 2 dp (CIF); leftover units go one at a time to the largest discarded fraction (ties: larger weight, then lowest
  plan pk). Parts sum exactly and no share is ever negative (the first draft's "whole remainder to the largest weight"
  could go negative for tiny amounts over 3+ plans — Opus review B2). All weights 0 → equal split.
- Licence-row billed CIF is the canonical `LicenseBalanceCalculator.calculate_trade` figure (a shadowed variable had
  leaked the last plan's share — Opus review B1).
- D1 eligibility: a plan falls back only when NO row (any qty, incl. 0 qty with CIF) is mapped to its target (Opus N2).
- Owner decisions (2026-11-20, asked directly in session d3):
  - **N1:** on a source with both STANDARD and percentage-split plans, billed-without-BOE is ALWAYS apportioned to the
    split targets by their percentage (order-independent); the STANDARD plan takes none of it.
  - **N4:** D1 also apportions the shared source's entitlement (Total Qty and item CIF) by the same planned-CIF weights.
  - **N8:** RUTILE (id 90) and RUTILE 3.5 (id 280) are the SAME product — a data fix (audited Item Name consolidation or
    BOE re-mapping, applied by the owner via the UI); no code change; agents do not write to the DB.
