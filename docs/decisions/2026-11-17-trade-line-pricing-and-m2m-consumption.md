# Decision 2026-11-17 — M2M allotment consumption and trade line pricing (T1–T4)

Status: **APPROVED by the product owner, 2026-11-17** (conversation authorisation; options chosen via explicit
questions where the proposal left a choice). Sources: `docs/audits/LICENCE_OVERVIEW_DOUBLE_COUNTING_AUDIT.md`
(escalation 1), `docs/audits/TRADE_CIF_FOB_RECONCILIATION.md` §Proposed T1–T4.

## 1. Partly-used allotment rule — M2M link = FULL CONSUMPTION

- An allotment linked to a BOE through `BillOfEntryModel.allotment` (M2M) contributes **0** to ALLOTMENT CIF,
  whatever the linked BOE's CIF (no remainder is derived). This is the existing engine behaviour
  (`LicenseBalanceCalculator._annotate_allotment_contribution`); the decision confirms it — engine unchanged.
- Independently consumed allotments (formal `BOEAllotmentAllocation`, no M2M link) keep partial netting
  (`cif_fc − min(cif_fc, allocated)`). The distinction is preserved.
- BOE debit CIF is counted once in BOE CIF regardless of how many allotments a BOE is linked to.
- Canonical CIF rule unchanged (`.claude/rules/business-rules.md`). Pinned by
  `backend/apps/license/tests/test_m2m_full_consumption.py` (engine, item, summary card, Allotments tab).

## 2. Trade line pricing

| Id | Approved scope | Choice |
|---|---|---|
| T1 | Server is authoritative for `LicenseTradeLine.amount_inr` on API writes (trade create, nested update, `lines/` endpoint): `amount_inr = compute_amount()` for new lines and lines whose pricing inputs changed, unless `amount_override` is true; a reason is required with the override. Unchanged lines keep their stored amount (no historical recompute). | API + minimal TradeForm toggle ("Manual amount" + reason) |
| T2 | `compute_amount` QTY mode uses the stored 3-dp `rate_inr_per_kg` (removes 2-dp truncation) | — |
| T3 | Line amounts rounded to **paise (2 dp, ROUND_HALF_UP)**; header keeps rupee rounding with explicit `roundoff`. Frontend preview rounds to 2 dp. | Paise |
| T4 | `|cif_inr − q2(cif_fc × exc_rate)| > 1.00 INR` (all three non-zero) → **accept and warn**: additive `warnings` list on line representations; form shows them. | Accept and warn |

Behaviour notes (from independent review, accepted as within the approved definitions):

- Typing an amount with "Manual amount" off derives a 3-dp rate/pct in the form; the server then recomputes from that
  rate/pct, so the saved amount can differ from the typed value (paise; more on very large CIF/FOB bases). Use the
  manual-amount toggle to keep a typed amount.
- Changing the trade's billing mode changes every line's `mode`, so every non-override line is re-priced.
- Legacy model fallback is unchanged: a stored line with `amount_inr == 0` (no override) is filled from the formula
  whenever it is saved, now with the T2 rate.
- Pair mirrors (`_copy_to_counterpart`, `sync_to_counterpart`) copy `amount_inr` and override flags verbatim; they do
  not re-price.
- Override is not attributed to a user (no `overridden_by/at`); adding that is a separate schema change (not approved).

Out of scope (unapproved): T5–T9, `IncentiveTradeLine` pricing (no drift beyond rounding found), frontend parity
beyond T1/T3/T4 (T8), historical correction (T9). Implementation: `backend/apps/trade/services/line_pricing.py`.

Flags: SCHEMA (`trade/0012_licensetradeline_amount_override`, additive, defaults) · API CONTRACT (additive
`amount_override`, `amount_override_reason`, `warnings`; new 400 when override has no reason) · BUSINESS-RULE (T1–T3
change how new/changed line amounts are computed).
