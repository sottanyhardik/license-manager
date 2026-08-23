# Calculation Ownership Registry

**Purpose:** a canonical inventory of business calculations and their
single authoritative owner, so that any future code computing one of
these values somewhere else is an obvious, visible architecture
violation rather than a silent third implementation.

**Scope note — read before trusting this as exhaustive:** this document
is seeded from the Item Pivot Report Display-Dataset migration
(Phases 2A–2B.2B, `docs/architecture/ITEM_PIVOT_DISPLAY_DATASET_DESIGN.md`
and `ITEM_PIVOT_NOTIFICATION_SUMMARY_DESIGN.md`), where every row below
was verified against current code as of 2026-08-07. The three
cross-report rows (Balance CIF, Trade Balance, Ledger Running Balance)
are included because they came up during that work and their owning
class/module was confirmed to exist — they are **not** the product of a
full audit of those reports the way the Item Pivot rows are. Add to this
registry incrementally, the same way: verify against current code before
writing a row down, the same discipline the migration itself followed.

---

## Item Pivot Report (`backend/apps/license/views/item_pivot_report.py`)

| Business Calculation | Authoritative Owner | Notes |
|---|---|---|
| Balance CIF / Available CIF (per license) | `LicenseBalanceCalculator.calculate_financial_balance_for_licenses` (`services/balance_calculator.py`), read verbatim into `_build_license_row` | Item Pivot doesn't own this one — it consumes it, same as every other report |
| Available Qty (per item) | `_build_license_row`, summed from `LicenseImportItemsModel.available_quantity` | |
| Planned Qty / Planned CIF (per license×item cell, norm-derived) | `_build_license_row`'s E1/E5/E132 waterfall (`services/e1_plan.py`, `e5_plan.py`, `e132_plan.py`) | |
| Restriction % / restriction_value (per cell) | `services/condition_pool.py` | |
| Effective Planned CIF (manual-vs-norm selection, per cell) | `_effective_planned_cif` (`item_pivot_report.py:41`) | Phase 2B.2A. Every consumer (JSON, React, Excel) reads the `effective_planned_cif` field it produces — do not re-derive the manual-vs-norm branch elsewhere |
| Effective Planned Quantity (manual-vs-norm selection, per cell) | `_effective_planned_quantity` (`item_pivot_report.py:55`) | Phase 2B.2B. Consumed by `_build_notification_summary` (fixed 2026-08-07 — see "Resolved findings" below) |
| Notification Totals (per-sheet CIF/qty grand totals) | `generate_report()`, inline construction (`item_pivot_report.py:~897-975`) | Phase 2B.2A. Read by both the frontend footer row and the Excel `TOTAL` row |
| Notification/Norm Summary (opening balance, restriction pool, blended unit price) | `_build_notification_summary` (`item_pivot_report.py:75`) | Phase 2B.2B. Read verbatim by React (`notification_summary`/`norm_summary` in `reportData`) and by the Excel exporter's `_write_notification_summary_block` — neither recomputes it |
| Restriction Pool dedup (license × percentage) | `_build_notification_summary`'s Pass 2 | Business rule preserved-for-parity per §12 of the design doc, not yet independently business-validated — see that doc's §10 |
| Blended Unit Price | `_build_notification_summary` (`total_planned_cif / total_planned_qty`, rounded 2dp) | |

---

## Other reports (confirmed to exist, not independently audited)

| Business Calculation | Authoritative Owner |
|---|---|
| Balance CIF (license-wide, all reports) | `LicenseBalanceCalculator` (`backend/apps/license/services/balance_calculator.py`) |
| Trade Balance | `backend/apps/license/views/license_purchase_profit_report.py` |
| License Ledger running balance | `LicenseBalanceLedgerBuilder` (`backend/apps/license/services/license_balance_ledger_builder.py`), also consumed by `services/exporters/license_balance_pdf.py` / `license_balance_excel.py` / `ledger_pdf.py` |

---

## Resolved findings from the Item Pivot audit (2026-08-07)

- **Fixed: `effective_planned_quantity`/`effective_planned_cif` now
  consumed by `_build_notification_summary`.** Originally found unused:
  `effective_planned_quantity` was computed and serialized on every item
  cell but had zero readers — `_build_notification_summary`'s Pass 3
  re-derived the identical manual-vs-norm branch inline
  (`item_has_manual = plan_cif > 0 or plan_quantity > 0`) instead of
  reading the field Phase 2B.2B added specifically to give that branch
  one canonical home, meaning the selection rule had two live
  implementations in the same file. Classified as a pure cleanup (same
  rule, same values — see the design doc's §5 note that the function's
  truthy check and the inline `> 0` check are equivalent for this
  domain's always-non-negative inputs), not a business-logic change, so
  fixed directly rather than left open: Pass 3 now reads
  `item_data.get('effective_planned_cif')`/`item_data.get('effective_planned_quantity')`
  directly. Regression test added
  (`test_notification_summary_reads_effective_fields_not_raw_inputs`,
  `test_item_pivot_notification_summary.py`) that sets the raw
  `plan_cif`/`plan_quantity`/`planned_cif`/`available_quantity` fields to
  values that would produce a *different*, wrong result if the branch
  were ever recomputed inline again — so reintroducing the duplicate
  copy fails loudly, not silently. Verified via the full existing test
  suite (63/63 pass, including the Excel export tests that exercise the
  real `generate_report()` → `_build_license_row` →
  `_build_notification_summary` pipeline against the test DB) that this
  was behavior-preserving end-to-end.
