# ERP data-integrity final report (2026-11-17)

**Status: BLOCKED for Trade-to-Finance feature work** — Gates B and C fail pending owner decisions. Gate A passes
for the defect found, with one escalated rule-vs-code conflict. Nothing committed, pushed or merged. No production or
historical data modified. Branch `feature/v5`, HEAD `01223ea7` (peer commits `9fec5b48`, `01223ea7` landed during the
work; none by this audit).

## Executive summary

1. **Licence "Total Allotted" double count — root cause found, fixed (display path).** The engine and the summary card
   were already correct. The Allotments tab footer summed gross `cif_fc` including BOE-linked allotments (whose CIF is
   already in BOE CIF): +4,144,946.34 FC across 45 of 102 live licences on the local snapshot. The tab now shows the
   engine's outstanding allotment as its headline and gross separately.
2. **Trade CIF/FOB drift — root causes found; one safe fix; the rest need owner decisions.** The server accepts any
   client-sent line amount (computes only when 0), never derives/validates `cif_inr`, truncates 3dp rates, and the
   frontend uses float/whole-rupee rounding. 651 of 870 computable lines differ (522 rounding, 129 defect/manual,
   4 missing inputs); 21 lines have CIF-INR defects totalling 3,982,333.28 INR; 310 issued sale documents carry a
   per-licence subtotal instead of the invoice total. Fixed: header totals now recompute on line delete.
3. **No finance/accounting module exists** (no journal, client/payment ledger, bank reconciliation or P&L engine), so
   Gate C's "finance posting / client ledger" items are not applicable yet; the master prompt's Phase 11 list of
   features to "preserve" does not match the code (see `docs/modernization/backend-audit/10_TRADE_TO_FINANCE_GAP_MATRIX.md`).

## Files changed (uncommitted)

| File | Change |
|---|---|
| `backend/apps/license/services/license_overview_allotments.py` | additive `outstanding_cif_fc` per row from engine `get_allotment_rows` (`contributed`), +1 constant query |
| `backend/apps/license/tests/test_license_overview_allotments_view.py` | shape + query count 5→6; scenario tests A, B, C, C′, D |
| `frontend/src/pages/license-overview/AllotmentsTab.tsx` | footer headline "Outstanding Allotted" = Σ outstanding; "Gross allotted (incl. BOE-linked)" and "Gross qty" labelled |
| `frontend/src/pages/license-overview/AllotmentsTab.test.tsx`, `types.ts` | test + type for the new field |
| `backend/apps/trade/models.py` | `post_delete` receiver recomputes trade header on line/incentive-line delete (skips trade cascade) |
| `backend/apps/trade/tests/test_trade_line_delete_recomputes_totals.py` | 5 tests |
| `docs/audits/*.md` (7 files) | audit deliverables |

Flags: **API CONTRACT (additive)** for `overview-allotments`. **DISPLAY BUSINESS-FIGURE CHANGE** for the Allotments tab
footer (no CIF rule change; engine untouched — per `cif-balance-auditor`). **FINANCIAL DATA-INTEGRITY BEHAVIOUR CHANGE**
for the trade receiver: stored header totals of a trade (and of its counterpart, via `counterpart_line` cascade) are
recomputed when a line is deleted; historical stale headers (e.g. trade 362) are not repaired. Invoice-auditor
sign-off recommended before commit.

## Migrations proposed

None created. T1 (amount override flag) would need a schema migration; not drafted until approved.

## Before / after evidence

Licence (live licences, FC, local snapshot 2026-11-17T02:22:51): Allotments-tab total **4,999,764.29 → 854,817.95**
(= engine ALLOTMENT CIF; difference 4,144,946.34 = Σ BOE-linked allotments). Original, BOE, billed, utilised and
available CIF unchanged (engine untouched) — full table in `LICENCE_OVERVIEW_DOUBLE_COUNTING_AUDIT.md`. The "after"
figure is the engine total by construction; the endpoint was not re-queried against the DB after the change.

Trade: reconciliation is report-only (no recalculation applied) — tables in `TRADE_CIF_FOB_RECONCILIATION.md`.

## Test, type-check, lint, performance results

Backend gate EXIT 0 (check, migrations, flake8, ruff, `tests/` 246 passed, app-level 3041 passed / 1 xfailed).
Frontend gate EXIT 0 (lint, typecheck, 726 passed, build). After the final label-only footer edit: licence-overview
vitest 34 passed, `tsc` and eslint clean (full frontend build not re-run for that edit). Performance: +1 constant query on
`overview-allotments`; no other query changes. Details: `FINANCIAL_REGRESSION_TEST_REPORT.md`.

## Release gates

| Gate | Status | Why |
|---|---|---|
| A Licence integrity | **PASS with escalation** | tab double count removed; footer = engine; negative balances unchanged/signed. Partial-BOE via M2M zeroes the remainder (scenarios C/D, 57 pairs, 422,766.62) — rule-vs-code conflict, owner decides. Cancellation/reversal (F) not representable. |
| B Trade financial integrity | **FAIL** | formulas documented; Decimal on server, float on client; no server derivation/validation of `cif_inr` or amount; decisions T1–T4, T8 pending; historical inconsistencies identified (report only) |
| C Cross-module | **FAIL** | 310 sale documents ≠ invoice total (T7); PDF rounding mismatch (T6); no finance posting exists; reports use engine (licence) but trade profit sums uncomputed/manual amounts |
| D Technical quality | **PASS** | all gates green; no migrations; query count +1 constant |
| E Governance | **PASS with note** | OD-BA-a/b/c and `@tanstack/react-table` left PENDING; register not edited by this audit. Note: `@tanstack/react-table` is already in committed code (`1d37f29c`) and the uncommitted register text marks it APPROVED — owner to resolve. |

## Unresolved decisions (owner)

1. M2M BOE link = full allotment consumption? (Licence audit escalation 1–2.)
2. T1–T9 trade proposals (server-authoritative amount, rate precision, rounding policy, CIF tolerance, error swallowing,
   PDF rounding, document total, frontend parity, historical correction process).
3. `license_balance_mv`: retire or fix. 4. Allotment cancellation model. 5. OD-QTY (quantity semantics; tab quantity is
   still gross).
6. Ownership of the untracked `license_overview_transactions*` files (a peer attributes them to this session's earlier,
   pre-resume history; not authored in this conversation; untouched).

## Production risks

- Issued sale documents (310) show per-licence totals on multi-licence invoices — customer-facing.
- 4 lines carry manual amounts on all-zero inputs (429,800 INR); line 1257 CIF INR off by ~3.98M INR.
- Header recompute on delete will overwrite any legacy, deliberately different header total of the affected trade.

## Recommended next steps

1. Owner decisions on items 1–2 above. 2. Invoice-auditor sign-off, then commit the two fixes as separate commits.
3. Implement T1–T4 behind tests (new `apps/trade/services/line_pricing.py`), then T6–T8. 4. Draft an audited,
   approval-gated management command for historical trade drift (dry-run report first). 5. Re-run the reconciliation
   scripts and close Gates B/C before resuming Trade-to-Finance.

## Update 2026-11-17 — owner-authorised implementation

Owner approved M2M link = full consumption and T1–T4 (T3 paise, T4 accept-and-warn, T1 API + form toggle);
T5–T9 remain unapproved. Recorded in `docs/decisions/2026-11-17-trade-line-pricing-and-m2m-consumption.md`.

- M2M: engine behaviour confirmed, no engine change; cross-layer regression tests `test_m2m_full_consumption.py` (8).
- T1–T4: `apps/trade/services/line_pricing.py`, migration `trade/0012` (additive, **not applied**), serializer hooks on
  all API write paths, `compute_amount` 3-dp rate, TradeForm manual-amount toggle + warnings; tests
  `test_line_pricing.py` (11), frontend `TradeLineAmountOverride.test.tsx`, `tradeFormHelpers.test.ts`.
- Gate B moves from FAIL to **PASS for new/changed lines** (historical drift still report-only, T9). Gate C still FAIL
  (T6/T7 unapproved).
