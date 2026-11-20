# Global ERP formatting standardisation — audit (2026-11-20, feature/v5)

Owner requirements: (1) Excel numeric business values are real numeric cells; totals/subtotals are live
`=SUM(range)` formulas; identifiers stay text. (2) DD-MM-YYYY is the universal user-facing date format.
No financial calculation was changed — only cell typing, number formats, formula generation and display.

## Owner decisions taken during the task
- **API dates stay DD-MM-YYYY** (`REST_FRAMEWORK.DATE_FORMAT='%d-%m-%Y'`, `DATETIME_FORMAT='%d-%m-%Y %H:%M'`).
  Switching to ISO 8601 would be a global API-contract change → deferred to a separate, planned migration.
  The frontend parser (`utils/dateFormatter.js`) already accepts both DD-MM-YYYY and ISO.
- **Native `<input type="date">` not replaced** (renders in the browser locale; listed below for a follow-up).
- **Canonical ledger totals are never SUM formulas** (CIF audit B1): the Financial Ledger workbook keeps the
  canonical DTO totals as numeric cells, because licence rows show whole-licence balances while company/SION
  totals sum each company's share, and canonical totals include an opening row that is not rendered.
  Summing visible rows would double count multi-company licences / drop the opening credit.

## Shared utilities (single source)
| Utility | Role |
|---|---|
| `backend/apps/core/exporters/excel/cell_formats.py` (new) | `write_number` / `write_date` / `write_text`, `to_number`, `parse_display_date` (day-first, never MM-DD), `sum_formula`, `write_sum`, `sum_cells_formula` (255-arg chunking, 8,000-char fallback), `sumif_label_formula` (grand totals over sub-total rows), `finalize_workbook` (DD-MM-YYYY on every date cell, tz-aware → local naive, `fullCalcOnLoad`) |
| `backend/apps/core/utils/date_utils.py` | `format_date` now converts aware datetimes with `localtime` (no UTC date shift); `format_date_display` default `%d/%m/%Y` → `%d-%m-%Y` (no production callers) |
| `backend/apps/core/exporters/excel/workbook_builder.py` / `base_excel.py` | `add_total_row(sum_columns=, first_data_row=)` optional live SUM (backward compatible); numeric strings → numbers; `save_workbook` finalizes |
| `frontend/src/utils/dateFormatter.js` (+ `.d.ts`) | single display formatter; ISO with `T`/`Z` shown in local time; date-only never shifts; fixed `00:xx` → `12:xx` bug |

## Excel exporters
| Exporter | Numeric cells | Dates | Totals | Notes |
|---|---|---|---|---|
| `license/api/views/active_licenses_report.py`, `expiring_licenses_report.py` | Balance CIF `"$12.34"` string → number; qty 3dp, CIF 2dp | real | per-licence `=SUM`, item-wise grand `=SUM`, Total Balance CIF `=SUM(cells)` (length-safe) | |
| `license/api/views/inventory_balance_report.py` | qty/CIF/count typed | — | `=SUM` E:J | item count stays value |
| `license/api/views/license_purchase_profit_report.py` (Excel) | amounts/qty numeric | real | **kept values** | service sums raw Decimals and rounds once |
| `license/api/views/planned_report.py` | qty/CIF/rate typed; HSN text | real | none | |
| `license/services/exporters/balance_excel_ledger_sheets.py` | `float()` removed (Decimal kept) | real (timeline datetime) | engine values kept | 0 credit/debit blank (was `-`) |
| `…/balance_excel_recon_sheets.py` | summary qty 3dp | real (label in number format) | Summary TOTAL CIF `=SUM` | reconciliation block = engine values |
| `…/license_balance_excel_bulk.py` | typed | real | Summary FC/INR, NORM TOTAL, Grand Total `=SUM`; item summary refs | |
| `…/license_balance_excel.py` | via shared sheets | — | — | finalize before save |
| `…/planning_split_rows.py` | metrics numeric; unit price numeric with `"@ $"…"/unit"` format | — | `=SUM(group cells)` (length-safe) | Remaining CIF (clamped) kept |
| `…/entitlement_plan_excel.py` | `float()` removed; split % `0.00"%"` | — | **kept values** | quantized raw sums |
| `…/financial_ledger_excel_renderer.py` | USD/INR numeric | DD-MM-YYYY (was `dd-mmm-yyyy`) | **canonical values** (see decision) | no formulas in this workbook (parity test guard kept) |
| `license/services/item_pivot_intelligence_export.py` | typed per column | expiry real | — | licence no./HSN forced text (leading zeros were lost) |
| `allotment/api/views_export.py` (xlsx) | qty raw Decimal 3dp (was `int()` truncation); USD/INR | real | item `=SUM`, grand `=SUMIF(C…,"Total Quantity",…)` | |
| `bill_of_entry/services/exporters/grouped_xlsx.py` | total qty raw Decimal 3dp (was `int()`) | real | product `=SUM`, grand `=SUMIF(C…,"Total",…)` | goldens regenerated |
| `bill_of_entry/services/exporters/port_xlsx.py` | — | real; BOE no. text | none | |
| `core/views/master_view.py` (xlsx) | Decimal/int/float numeric | real (tz → local) | — | integer fields now numbers |
| `accounting/services/banking.py` | — | — | — | import only, see below |
| `license/utils/condition_excel.py`, `license_balance_ledger_builder.py` | no cell output — unchanged | | | |

**Deferred — other sessions' uncommitted WIP (not touched):** `license/api/views/item_pivot_excel.py`,
`item_pivot_helpers.py`, `item_report.py` need the same treatment (write_number/write_date, SUM totals,
`finalize_workbook`). `item_pivot_intelligence.py` only calls the already-typed `workbook_response`.

## Excel import
`accounting/services/banking.py` + `accounting/domain/statement.py`: numeric cells → `Decimal` via `repr`
(no float math); commas/₹/brackets/CR-DR/negatives handled; date cells accepted; string dates parsed
day-first. No change needed. Gap (not fixed): a bare Excel serial number in a date column is rejected.

## PDF / backend display dates
Changed to `%d-%m-%Y` (time ` %H:%M` kept where shown): `allotment/scripts/allotment_pdf.py`,
`allotment/api/views_export.py` (PDF), `bill_of_entry/…/grouped_pdf.py`, `core/utils/pdf_utils.py`,
`core/serializers/fields.py` defaults, `license/services/custom_ledger_pdf.py`,
`…/financial_ledger_pdf_renderer.py`, `trade/purchase_invoice_pdf.py`, `trade/bill_of_supply_pdf.py`.
Kept intentionally: `license_purchase_profit_report.py` PDF timestamp `%d-%b-%Y %I:%M %p`; portal/server
payloads (`resync_local_to_server.py`, `update_license_ownership.py` `%d/%m/%Y`); parsers of external
formats; filename timestamps; dashboard `%b %Y` month buckets.

## Frontend
Ad-hoc `toLocaleString`/`toLocaleDateString`/local helpers → `formatDate`/`formatDateTime`:
`HistoryTab.tsx`, `TaskDrawer.tsx`, `OwnershipDetailsModal.tsx`, `PlanningEditor.tsx` (last updated),
`LicenseDownloadRequests.tsx`, `LicenseDownloadRequestDetail.tsx`, `MappingChanges.tsx`, `ActivityLog.tsx`,
`normConfig.ts`, `Settings.tsx`, `MdsStatusCard.tsx`, `licenseBalanceHelpers.ts`. react-datepicker (3) already
`dd-MM-yyyy`. No DD-MM-YYYY string sorts found. Dashboard greeting ("Friday, 20 November 2026") kept as a label.

Native date inputs (follow-up): `components/DateRangeFilter.tsx:97,103`, `AllotmentFormModal.tsx:465`,
`TaskDrawer.tsx:517,709`, `filters/FilterBar.tsx:179,182`, `form/fields.tsx:83`,
`shared/DateRangePicker.tsx:38,42`, `pages/accounting/{Vouchers:215,Payments:159,Banking:233,Loans:37,78,79,
Setup:37,142,AccountingWorkspace:58,63,Invoices:165}.tsx`, `license-overview/TransactionsTab.tsx:288,290`,
`reports/LicensePurchaseProfitReport.tsx:282,287`.
Peer-WIP frontend files not checked for date columns: `ActiveLicenses.tsx`, `ExpiringLicenses.tsx`,
`DownloadLicense.tsx`, `SionNormReport.tsx`, `ItemsTab.tsx`, `ApprovedMappings.tsx`.

## Known presentation effects
- Formula totals have no cached value (openpyxl limitation); `fullCalcOnLoad` makes Excel/LibreOffice
  compute on open. Readers that do not recalculate (pandas, `openpyxl data_only=True`) see empty totals.
- SUM over 2dp-rounded row cells can differ by a paisa/cent from the old `round(sum(raw))`.
- Allotment/BOE quantities now show the true fractional value (3dp) instead of a truncated integer.
- Missing dates in allotment xlsx: blank date cell instead of `--`. Aware datetimes shown in app local time.

## Tests
New: `core/tests/test_excel_cell_formats.py`, `allotment/tests/test_allotment_export_xlsx_formulas.py`,
`license/tests/test_excel_cell_types.py` (+ `xlsx_eval.py` formula evaluator for tests),
`frontend/src/utils/dateFormatter.test.ts`. Pins updated for intended typing only (BOE goldens, planning
split rows, item report unit price, inventory total, bulk balance summary, ledger PDF date text).
