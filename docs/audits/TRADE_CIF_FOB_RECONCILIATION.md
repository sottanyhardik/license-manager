# Trade line CIF/FOB reconciliation (Phase 2, 2026-11-17)

Read-only audit. Local dev DB (`localhost`/`lmanagement`), READ ONLY transaction rolled back, run 2026-11-17T02:22:55Z
(snapshot; the DB is re-synced periodically). Scripts outside the repo: `/tmp/erp_audit_trade/recon{,2}.py`, output
`/tmp/erp_audit_trade/out.json`. **No historical row was changed.**

## Verdict

**FAIL on financial integrity.** The backend accepts whatever line amount the client sends and never recomputes it;
`cif_inr` is never derived or checked server-side; issued sale documents on multi-licence invoices mostly carry one
licence's share as the document total. The commercial formula itself is simple and Decimal-based on the server; the
drift comes from frontend float/whole-rupee rounding, the "compute only if 0" rule and copy/sync paths.

## Actual formulas (from code — not invented)

| Mode | Server (`trade/models.py:558-565`, Decimal, ROUND_HALF_UP) | Frontend (`TradeForm.tsx:502-507`, JS float) |
|---|---|---|
| QTY | `amount = q2(q4(qty_kg) × q2(rate_inr_per_kg))` — **rate field is 3dp but truncated to 2dp** | `Math.round(qty × rate)` (whole rupee) |
| CIF_INR | `amount = q2(q2(cif_inr) × pct/100)` | `Math.round(cif_inr × pct/100)` |
| FOB_INR | `amount = q2(q2(fob_inr) × pct/100)` | `Math.round(fob_inr × pct/100)` |
| cif_inr | **never derived server-side** | `parseFloat((cif_fc × exc_rate).toFixed(2))`, CIF_INR mode only (`:455-456`) |
| exc_rate | stored 12,4 | back-derived `Math.round(cif_inr/cif_fc×100)/100` (**2dp**, `:460-464`) |
| Header | `subtotal = Σ amount_inr`; `total = subtotal` rounded HALF_UP to rupee; `roundoff = total − subtotal` (`:365-390`) | `TradeForm.tsx:519-521` TS sum |

- No freight, insurance or other CIF adjustment fields exist on trade lines (`models.py:535-549`); the CIF/FOB values are
  entered/prefilled, not built from FOB + freight + insurance. The master prompt's generic formula does not apply.
- Units: `qty_kg` only (PDF label "Kg"); no MT conversion anywhere.
- Currency: amounts and bills are INR; ledger "amount" uses `cif_fc`. One unquantised fallback `cif_inr/exc_rate` at
  `canonical_ledger_service.py:1302-1306`.
- `save()` computes `amount_inr` **only when it is 0/None** (`:567-571`); `compute_amount` result `computed_amount` is
  returned to the client as **float** (`api/serializers.py:178`).

## Drift causes (reproducible)

1. Whole-rupee frontend amount vs paise backend: CIF 100,001.00 × 7.9% → stored 7,900, server 7,900.08 (660/874 lines
   are whole-rupee).
2. Amount computed only when 0: any client value wins; sending `''` drops the field (`serializers.py:77-80`) so a stale
   amount survives a qty/rate change.
3. Mode switch (`TradeForm.tsx:1249`) keeps the old amount.
4. Reverse-calc pct at 3dp on large bases: FOB 118,865,410.36 at 1.764% → 2,096,785.84 vs stored 2,097,369.99 (line 254).
5. `q2(rate)` truncation: 124,970.15 kg × 1.745 = 218,072.91 vs server 218,697.76 vs stored 218,076 (lines 1043/1045).
6. `exc_rate` cut to 2dp on back-derivation (245 of 250 CIF mismatches have 2dp rates; cause inferred).
7. Counterpart sync errors swallowed (`serializers.py:565-568, 611-618`) — 0 of 7 pairs diverge today.
8. Line delete outside the update path did not recompute the header — trade 362 (KASL252648) has 0 lines, total
   1,931,139. **Fixed for future deletes** (see below); the historical row is reported, not repaired.
9. Copy/sync (`trade_service.py:268-275, 422-430`) copies amounts verbatim (stale/manual values propagate).
10. Purchase PDF uses Python `round()` (HALF_EVEN, `purchase_invoice_pdf.py:449,468`) vs stored HALF_UP total.
11. Sale document total = per-licence bill (`license_ledger_export.py:41-48` → `invoice_document_service.py:106-131`),
    and the Bill of Supply PDF uses one mode for the whole invoice (`bill_of_supply_pdf.py:244`).

## Reconciliation results

Rows: 566 trades (323 SALE, 243 PURCHASE; no COMMISSION_* in data), 874 lines (669 CIF_INR, 149 QTY, 56 FOB_INR),
550 incentive lines, 461 `TradeInvoiceDocument` rows.

**Stored `amount_inr` vs `compute_amount()`**

| Class | Count | Abs diff (INR) |
|---|---:|---:|
| Consistent | 219 | — |
| B Rounding (≤ 1.00 INR) | 522 | 128.98 |
| C Calculation defect / manual override | 129 | 9,286.29 |
| F Historical / missing inputs | 4 | 429,800.00 |
| G Unexplained | 0 | — |

By direction: SALE 347 B / 44 C; PURCHASE 175 B / 85 C / 4 F. By mode: CIF 399 B / 120 C / 3 F; FOB 47 B / 6 C;
QTY 76 B / 3 C / 1 F. 501 of 651 mismatches equal the whole-rupee round of the computed value. Affected trades 372;
**159 of them have issued documents**. Largest: F lines 588, 587, 585 (132,500 each, manual amount on all-zero inputs),
471 (32,300); C lines 1043/1045 (621.76), 254 (584.15), 253 (426.91), 246 (328.92), 706 (300.63).

**`cif_fc × exc_rate` vs stored `cif_inr`**: 404 consistent · 229 B (48.02 INR) · **21 C (3,982,333.28 INR)** ·
207 partial data · 13 all zero · 106 trades affected. Worst: line 1257 (LGL/2026-27/0103) 88,800 × 95.90 = 8,515,920
vs stored 4,536,070 (D/E-type: currency or entry defect — needs manual review).

**Header vs lines**: 565 consistent · 1 C (trade 362, above).

**Issued documents vs trade total**: 128 equal (single licence) · **310 equal one licence's unrounded subtotal on a
multi-licence invoice** (PDF total and "Rounding Off" row wrong) · 2 single-licence unrounded · 21 unexplained (probably
older document versions) · 73 trades have several distinct `sale_bill_inr` values.

**Incentive lines**: 94 consistent · 453 B · 3 C · 121.87 INR total (max 4.08, line 430).

Discrepancy classes used: A display-only · B rounding · C calculation defect · D currency conversion · E unit conversion
(none: kg only) · F historical/missing · G unexplained.

Summary table (all lines, INR):

| Metric | Existing (stored) | Recalculated (server formula) | Difference |
|---|---:|---:|---:|
| Line amount Σ abs diff | — | — | 439,215.27 (B 128.98 + C 9,286.29 + F 429,800) |
| CIF INR (fc × rate) Σ abs diff | — | — | 3,982,381.30 (B 48.02 + C 3,982,333.28) |
| Freight / Insurance | n/a — fields do not exist | n/a | — |
| Quantity / FOB rate / CIF rate | stored inputs; not recalculated (no independent source) | — | — |

## Fix implemented

- `backend/apps/trade/models.py`: `post_delete` receiver recomputes `LicenseTrade` totals when a `LicenseTradeLine` or
  `IncentiveTradeLine` is deleted (generic `lines/` DELETE and queryset deletes). Restores the existing invariant
  `subtotal = Σ lines`; affects only future deletes. Tests:
  `backend/apps/trade/tests/test_trade_line_delete_recomputes_totals.py`.

## Proposed (owner decision required — NOT implemented)

| # | Proposal | Flags |
|---|---|---|
| T1 | Server authoritative `amount_inr = compute_amount()` unless an explicit `amount_override` (+reason) is set; only for new/changed lines | SCHEMA + API CONTRACT + BUSINESS-RULE |
| T2 | Stop truncating the 3dp rate to 2dp in `compute_amount` | BUSINESS-RULE (changes amounts) |
| T3 | Rounding policy: line amount to whole rupee (frontend today) or paise (backend today) | BUSINESS-RULE |
| T4 | Validate `|cif_inr − q2(cif_fc × exc_rate)| ≤ 1.00` on write (warn or reject) | API CONTRACT |
| T5 | Stop swallowing counterpart/nested sync errors (`serializers.py:565-568, 611-618`) | behaviour change |
| T6 | PDF rounding HALF_UP to match stored totals | document output change |
| T7 | Sale document total = invoice `total_amount`, not the per-licence bill | document/API contract |
| T8 | Frontend parity: recompute on mode switch, keep `exc_rate` at 4dp, use server `computed_amount` as string | UI behaviour |
| T9 | Historical drift: report only; any correction via a separate audited, approved management command | DATA |
