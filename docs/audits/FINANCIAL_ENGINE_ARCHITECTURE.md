# Financial engine architecture (Phase 4, 2026-11-17)

Review of whether a canonical engine exists per financial quantity, and where competing paths remain. **No new
calculation system was created.** Recommendations only; consolidation needs owner decisions listed below.

## One source of truth per quantity

| Domain | Canonical owner | Competing / derived paths | Status |
|---|---|---|---|
| Licence CIF (credit, BOE, allotment, billed, available) | `LicenseBalanceCalculator` (`balance_calculator.py`), two engines by design (customs / financial) | stored `LicenseBalance` (signals + `core/scripts/calculate_balance.py`), `license_balance_mv` (unread, non-netted), ledger builder + `canonical_ledger_service` (delegate), item pivot / plan enforcement (binary exclusion) | canonical exists; derived paths must stay equal (pinned by `test_balance_cif_single_source.py`, `test_item_pivot_balance_consistency.py`) |
| Allotment consumption | `_annotate_allotment_contribution` (`contributed` per row) | Allotments tab footer (**fixed**: now `outstanding_cif_fc` from the engine) | canonical; M2M-link rule open (owner) |
| BOE ↔ allotment reconciliation | `reconciliation/services/allocation_service.py` (`BOEAllotmentAllocation`) | M2M `BillOfEntryModel.allotment` (the only production path) | two mechanisms; allocation table has no production writer (doc 05 O6) |
| Invoice ↔ BOE matching | `boe_link_reconciler.py` + `InvoiceBOEAllocation` | `LicenseTrade.boes` M2M (reference only) | canonical; writes only via `backfill_boe_allocations --apply` |
| Trade line amount | `LicenseTradeLine.compute_amount` | frontend `TradeForm.tsx` (float, whole rupee), manual override accepted, copy/sync verbatim | **not authoritative** — see T1–T4 |
| Trade header totals | `LicenseTrade.recompute_totals` | PDFs (`round()` HALF_EVEN), sale documents (per-licence bill) | canonical; delete path **fixed**; PDFs/documents open (T6/T7) |
| Currency conversion | none server-side for trade lines; `ExchangeRateModel` (DGFT customs rates) for BOE/allotment | frontend `cif_fc × exc_rate`, 2dp back-derivation | missing canonical service |
| Unit conversion | none (kg only) | — | not needed today |
| Rounding | `q2`/`q4` ROUND_HALF_UP (`trade/models.py:23-28`), `quantize_2dp` (balance) | JS `Math.round`, Python `round()` in PDFs | inconsistent at edges |

## Principles check

| Principle | State |
|---|---|
| One source of truth | licence: yes (with derived caches); trade amount: **no** |
| Explicit decimal precision | backend yes; frontend float; `computed_amount` serialised as float |
| Deterministic | yes for engine; trade amounts depend on client |
| Idempotent operations | header recompute idempotent; ledger re-import can duplicate CREDIT rows (`core/scripts/ledger.py:308`) |
| Traceable inputs / auditable outputs | `ReconciliationLog`, `TradePairAudit`, `InvoiceDocumentAuditEvent`; no field history on lines/payments |
| No silent historical modification | header recompute on delete/save rewrites stored totals of that trade (documented) |
| Transaction-safe | allocation service atomic; BOE↔allotment M2M write not atomic (doc 05); nested sync errors swallowed for paired trades |
| Efficient queries | overview +1 constant query; ledger expand path 85-460 queries (doc 09) |

## Recommended boundaries (proposal)

- **Licence balance domain** (`apps/license/services/balance_*`): unchanged owner of CIF buckets. Retire or fix
  `license_balance_mv`; keep stored `LicenseBalance` as a cache pinned by parity tests.
- **Trade pricing domain** (new small service in `apps/trade/services/`, e.g. `line_pricing.py`): the single
  `compute_line_amount(mode, qty, rate, cif_inr, fob_inr, pct)` + `derive_cif_inr(cif_fc, exc_rate)` + rounding policy,
  used by model save, serializer validation and exposed to the frontend as string values. Requires T1–T4 decisions.
- **Document domain** (`invoice_document_service`, PDFs): consume header totals only; HALF_UP everywhere (T6/T7).
- Do **not** merge licence balance and trade pricing into one service.
