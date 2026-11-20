# SAT Phase 6 — Excel / PDF export audit (SAT-EXP)

Branch `feature/v5` (tree as-is, 178 uncommitted paths owned by other sessions) · local DB `lmanagement@localhost` read-only
(every export generated inside a rolled-back `transaction.atomic()`, `APIClient.force_authenticate(superuser)`; DRF throttling
disabled in the harness only, because the default burst throttle returned 429 after ~30 exports).
Evidence dir: `/tmp/sat/exp/` (`out/` generated files, `gen*.py`/`verify*.py`/`cmp_*.py` scripts, `gen*_results.json`, `verify1.json`).
Audit only: no application code changed.

## 1. Inventory

| ID | Export | Endpoint | Frontend caller | Format |
|---|---|---|---|---|
| X01 | Licence Balance PDF | `GET licenses/{id}/balance-pdf/` | LicenceCard, LicenseBalanceModal, LicenseOverviewPage | PDF |
| X02 | Licence Balance Excel (5 sheets) | `GET licenses/{id}/balance-excel/[?show_hidden]` | same | XLSX |
| X03 | Bulk balance Excel | `POST licenses/bulk-balance-excel/` | DownloadLicense | XLSX |
| X04 | Customs Ledger item-detail PDF | `GET license-ledger/{id}/custom-ledger-pdf/` | licenseLedgerExport.ts | PDF |
| X05 | Financial ledger PDF | `GET license-ledger/{id}/financial-ledger-pdf/` | (API only) | PDF |
| X06 | License Ledger export (xlsx/pdf) | `GET license-ledger/export/?file_format=` | LicenseLedger, LicenseLedgerDetail | XLSX/PDF |
| X07 | Ledger package PDF | `POST license-ledger/download-package-pdf/` | licenseLedgerExport.ts | PDF |
| X08 | Allotment letter PDF | `GET allotment-actions/{id}/generate-pdf/` | allotment cards/pages | PDF |
| X09 | Allotment Excel | `GET allotment-actions/{id}/export-excel/` | `allotmentApi.exportAllotmentExcel` (no caller) | none |
| X10 | Licence list export | `GET licenses/export/?_export=` | MasterList | XLSX/PDF |
| X11 | Allotment list export | `GET allotments/download/?_export=&type=` | MasterList | XLSX/PDF |
| X12 | BOE list export (grouped, port) | `GET bill-of-entries/export/?_export=pdf/xlsx/port_xlsx` | boeApi, MasterList | XLSX/PDF |
| X13 | Trades list export | `GET trades/export/` | MasterList | XLSX/PDF |
| X14 | Master exports (companies, ports, hs-codes, item-names, sion-classes, ...) | `GET masters/{e}/export/` | MasterList | XLSX/PDF |
| X15 | Active licences report | `reports/active-licenses/?format=excel` | ActiveLicenses | XLSX |
| X16 | Expiring licences report | `reports/expiring-licenses/?format=excel` | ExpiringLicenses | XLSX |
| X17 | Inventory balance report | `reports/inventory-balance/?format=excel` | (API) | XLSX |
| X18 | Item Pivot report | `reports/item-pivot/?format=excel` | ItemPivotReport | XLSX |
| X19 | Item Report | `reports/item-report/?_format=excel` | ItemReport | XLSX |
| X20 | Item Report products | `reports/item-report/products/?_format=excel` | ItemReport | XLSX |
| X21 | Planned report | `reports/planned-report/?_format=excel` | PlannedReport | XLSX |
| X22 | Licence purchase/profit | `reports/license-purchase-profit/?_format=excel|pdf` | LicensePurchaseProfitReport | XLSX/PDF |
| X23 | Entitlement planning | `entitlement-plan/?export=xlsx` | EntitlementPlanningReport | XLSX |
| X24 | Unknown sales classification | `trades/sales-classification-review/export/` | none found | CSV |
| X25 | Trade invoice / bill of supply PDFs | `trade/api/views_invoice_documents.py` | TradeForm, TradesListView | PDF |

Not generated: X25 and the trade-based parts of X06/X07/X13/X22 (see §5, ENV-1).

## 2. Sample (19 licences, chosen deliberately)

Negative balance: 0310827509 (-3,447,851.40, original CIF 0), 0310833304, 0910043222 (-0.07), 3411007247 (-18,401.98) ·
transferred/hidden BOEs: 0311052122, 0511002494, 0311050784 · zero balance: 0310733729, 2311014688 · many BOEs: 0310705160 (237), 0310776854 (191) ·
allotments outstanding: 0311020653, 3411008150 · mixed unit case `kg`/`KG`: 3411007247, 5211019110, 5211018767 ·
no import items: 0510244075 · plain: 0310815822, 0311008530, 5211020103. Multi-unit (different unit strings) exists only as kg/KG (no MT).
Per licence: X01, X02 (default and `show_hidden=true`), X04, X05, X06 xlsx+pdf; X03 for all 19; X08 for 12 allotments of 5 licences.
List and report exports: default scope plus one filter where the endpoint supports it.

## 3. Per-export results

Status: PASS / PASS-EXC (pass with exceptions) / FAIL / BLOCKED. Exit codes are from the generation runs (`gen1.log`, `gen3.log`, `gen4.log`: EXIT=0 unless noted).

| ID | Status | Result | Evidence |
|---|---|---|---|
| X01 | FAIL | BOE rows and CIF match DB on 19/19 (hidden BOEs omitted by default as designed). Financial section says MATCHED (balance = engine) while X02 for the same licence says FAILED (D01). Export item name prints literal `None` (D07). Import Items table numbers lack thousands separators (D12). 65 pages for 237 BOEs. | `out/balpdf_*.pdf`, `verify1.json` |
| X02 | FAIL | Customs Ledger BOE rows equal DB (multiset of number/qty/CIF) on 19/19, both modes; `show_hidden=true` restores hidden rows (22/22, 3/3, 13/13). All cells numeric/date; `=SUM` ranges cover all rows (0 gaps); negatives kept. Financial Ledger sheet "Current Balance" is wrong and flagged FAILED on 15/16 licences with BOEs (D01). Timeline "date" is created_on, not the BOE date (D08). Qty format 2dp on ledger sheets vs 3dp on Reconciliation (D12). No autofilter. | `out/balxls_*.xlsx`, `scan1.py` output |
| X03 | PASS-EXC | 200; one sheet per licence, `=SUM(Fn:Fn)` totals, negatives preserved (-1,977,787.36, -3,447,851.40, -18,401.98, -0.07 present). Sheet-level values not individually diffed against DB (limitation). | `out/bulkbal.xlsx` |
| X04 | PASS-EXC | Header, licence date, BOE numbers, CIF and qty present for all non-hidden BOEs; Actual balance = engine on 19/19. Known N1/N2/N4/RC13/RC14 still present (see §4). Layout: BOE date wraps mid-value (`18-10-20`/`17`), header `BOE debite/d qty`, Port wraps (D09). | `out/custpdf_*.pdf`, `img/custpdf_0310815822.pdf.png`, `verify2.py` |
| X05, X06-pdf | FAIL | Statement is trade/invoice based: no BOE rows; closing balance = canonical ledger balance (opening only), e.g. 978,259.87 vs licence balance 223.72 (0310815822). Balance not found in text on 15/16 licences with BOEs (D01). | `out/finpdf_*`, `out/ledgerpdf_*` |
| X06-xlsx | FAIL | Single-licence export: "License Summary" has no licence row and GRAND TOTAL balance 0 while "Financial Trade Ledger" LICENSE TOTAL balance = 978,259.87 (0310815822) (D10). Default list scope (no `license_id`) returns 404 "No License Ledger data available" (ENV-1). | `out/ledgerxlsx_*`, `out/ledger_auto_*` |
| X07 | BLOCKED | `license_ids:[3 ids]` rejected 400 "Select exactly one licence" (by design). Not re-run with one id (package job path is async, see ENV-2). | `gen4.log` |
| X08 | PASS-EXC | 12/12: licence number, qty and CIF of each allotment line present; totals row = Σ lines. Subject line shows `required_quantity` (2,500,000 Kgs) while table total is 2,082,810 Kgs; partial allocation is not signalled (D06). Quantities use `int()` truncation (latent, no fractional allotment qty in DB today). | `out/allot_pdf_*.pdf`, `verify_allot.py` |
| X09 | FAIL | Endpoint does not exist (404). Frontend client has no caller. | `out/allot_excel_dead.json` |
| X10 | PASS-EXC | Default export 329 rows (default list filter; DB has 2,185). License Date / Expiry / Ledger Date are text `DD-MM-YYYY`, not date cells (D03). PDF 9 pages. | `out/list_lic_*` |
| X11 | PASS-EXC | xlsx 14,059 rows (item-level) for 6,518 allotments / 11,610 items; one invoice value `34/04/2025` (data quality, DQ-1). 32.6 s for the default export. | `out/list_allot_*` |
| X12 | PASS-EXC | Date-filtered (>= 2026-01-01): DB 1,650 BOEs / 2,730 debit rows; xlsx 387 rows, port 75 rows (grouped; row-level diff not run, limitation). Company filter OK. | `out/list_boe_*` |
| X13 | PASS-EXC | 200 for empty set (0 trades); empty workbook/PDF. Content untestable (ENV-1). | `out/list_trades_*` |
| X14 | PASS | Row counts equal DB for companies 1,023, ports 865, hs-codes 13,701, item-names 110, sion-classes 2,086. | `out/master_*` |
| X15 | PASS | 174 JSON licences = 174 licence blocks; numeric/date cells correct. | `out/rep_active_*` |
| X16 | PASS | 3 = 3. | `out/rep_expiring_*` |
| X17 | PASS | 28 JSON items = 28 rows; `=SUM(E4:E31)` covers all rows. | `out/rep_inv_*` |
| X18 | FAIL | 80 (E1) and 69 (E5) licences equal JSON with 0 value diffs, but every numeric and date cell on the per-licence sheets is text (D02). `TOTAL_Summary` is numeric. | `out/rep_pivot*`, `cmp_pivot.py` |
| X19 | PASS-EXC | 232 licences; per-licence Available Balance and Balance CIF = JSON (0 diffs); Σ available qty = JSON (216,847,151.901). Dates are ISO text (known RC15). Items sharing HSN+item name are merged (2,198 rows vs 3,233 JSON items) and the merge is unlabelled (D11). 65 MB JSON for the same screen (performance note). | `cmp_itemrep.py` |
| X20 | PASS | 68 products (+ totals row). | `out/rep_itemprod_*` |
| X21 | PASS-EXC | 523 = 523. Available qty is floored to a whole number (27,219.0 vs quantity 27,219.19), same as RC13. | `out/rep_planned_*` |
| X22 | BLOCKED | No trades locally: valid workbook/PDF with 0 licences. Requires from/to dates (400 otherwise). | `out/rep_profit_*` |
| X23 | PASS | 0311040024/E1 opens with totals consistent with JSON. | `out/rep_entitle_*` |
| X24 | PASS-EXC | Header-only CSV (no data). | `out/list_salesclass_csv.bin` |
| X25 | BLOCKED | No trade/invoice rows locally (ENV-1). | n/a |

## 4. Known findings carried forward (re-verified in the current tree, not new)

- N1 PDF item Balance CIF = RC4a value: code unchanged (`custom_ledger_pdf.py:90`); not re-diffed per item.
- N2 PDF Total CIF = `opening_balance` (`custom_ledger_pdf.py:93`): code present; equals credit on all 19 sampled licences, so no visible difference in the sample.
- N4 unit totals split by raw text: **reproduced** on 3411007247, 5211019110, 5211018767 (`kg` and `KG` rows).
- RC13 whole-unit floor: reproduced (0.78 kg of `KG` item dropped, item Available 194,441.00 vs 194,441.78).
- RC14 tautological "CIF reconciliation PASS": reproduced, including PASS on over-utilised licences (0310827509: -3,447,851.40; 3411007247). "Actual debited" absorbs allotments (e.g. 0311020653: 3,036,544.43 vs BOE 460,384.43).
- RC15 Item Report dates as ISO text: reproduced (232 rows).

## 5. Environment limitations / data quality

- ENV-1: `trade_licensetrade` has 0 rows locally. Trade/invoice/purchase-profit/ledger-list exports cannot be content-verified; default `license-ledger/export` returns 404.
- ENV-2: no PDF rasteriser except macOS `qlmanage` (used for one visual check); text extraction via `pypdf`. Table layout checked by text only.
- ENV-3: DRF burst throttle returns 429 for ~30 rapid exports from one user (harness bypassed it).
- DQ-1: allotment invoice `34/04/2025` (X11 I9873). DQ-2: licence 0310827509 has original CIF 0 with 30 BOEs (negative balance is data, correctly preserved). DQ-3: many licences have unnamed items / empty exporter (`—`).

## 6. Difference register (export vs API vs DB)

| Licence | Field | Export value | API/screen value | DB/engine value | Diff | Root cause |
|---|---|---|---|---|---|---|
| 0310815822 | Financial Ledger Current Balance (X02) | 978,259.87 | 978,259.87 (`balance-ledger` summary `computed_balance`, `matched:false`) | 223.72 | 978,036.15 | D01 |
| 0310815822 | Financial Ledger Current Balance (X01 PDF) | 223.72 | 978,259.87 | 223.72 | 978,036.15 (PDF vs Excel) | D01 |
| 0310833304 | same (X02) | 6,824,661.89 | same | -1,977,787.36 | 8,802,449.25 | D01 |
| 0310827509 | same (X02) | 0.00 | same | -3,447,851.40 | 3,447,851.40 (negative lost) | D01 |
| 0310776854 | same (X02) | 16,368,720.50 | same | 4,193.82 | 16,364,526.68 | D01 |
| all 15 licences with BOEs | same | = original CIF/opening | `matched:false` | engine | see `scan1.py` output | D01 |
| 0310815822 | X06 License Summary balance | 0 (no row) | 978,259.87 | 223.72 | n/a | D10 |
| E1/E5 pivot, 149 licences | Total/Debited/Allotted/Planned/Balance CIF | text | JSON strings | n/a | 0 numeric diff | D02 (type only) |
| Item Report, 232 licences | balance and qty | = JSON | = JSON | n/a | 0 | none |

Tolerances: CIF 0.01, qty 0.001. BOE rows/CIF/qty in X01, X02, X04: 0 diffs on 19 licences.

## 7. Defect register

- **SAT-EXP-D01** — High · Confirmed defect (cross-surface inconsistency) · license (balance ledger) · Repro: `GET licenses/2531/balance-excel/` (0310815822), sheet "Financial Ledger" · Expected: "Current Balance" = last running balance = licence balance 223.72, status MATCHED · Actual: Current Balance 978,259.87 (= canonical invoice-only ledger, which ignores BOEs "Pending Invoice"), row 4 running balance 223.72, "MISMATCH vs Balance Engine", "FINANCIAL RECONCILIATION FAILED"; the Balance PDF for the same licence shows 223.72 MATCHED; `balance-ledger` API (the screen) shows `matched:false`, integrity score 0. 15 of 16 licences with BOEs; negative licence 0310827509 shows 0.00 instead of -3,447,851.40 · Evidence: `out/balxls_*`, `out/api_ledger_0310815822.json`, `scan1.py` · Root cause: `build_balance_excel` passes `canonical_data` to `build_financial_ledger`, which overrides `computed_balance` with `license_running_balance` (`license_balance_ledger_builder.py:664-671`); the canonical dataset has only OPENING when no invoices exist · Scope: Balance Excel, balance-ledger screen, license-ledger statements (X05/X06) · Remediation: owner decision on whether pending-invoice BOEs belong in the financial ledger balance; then align builder or drop the override; make PDF and Excel use the same source · Business approval: **Y** (financial/CIF rule).
- **SAT-EXP-D02** — High · Confirmed defect · license (Item Pivot Excel) · Repro: `reports/item-pivot/?format=excel&sion_norm=E5&license_status=active` · Expected: numeric cells and date cells · Actual: all numeric (Total/Debited/Allotted/Planned/Balance CIF, quantities) and expiry-date cells on the per-licence sheets are inline strings (`3609764.80`, `2027-02-28`); `SUM`, sort and filter in Excel do not work; also 3dp-float cells in General format · Evidence: `out/rep_pivotE5_xlsx.xlsx` sheet XML `t="inlineStr"`, `cmp_pivot.py` · Root cause: `item_pivot_excel.py:283-360` writes the report's string-serialised Decimals straight into the row without conversion · Scope: X18 (all norms) · Remediation: convert to `Decimal`/`float` and `date` at write time, apply number formats · Business approval: N (presentation; values already match screen).
- **SAT-EXP-D03** — Medium · Confirmed defect · core (master export) · Licence list export: License Date, Expiry, Ledger Date are `DD-MM-YYYY` text (335/286/326 cells) · Expected: date cells · Root cause: master `_export_xlsx` serialises dates through the serializer's string output · Evidence: `out/list_lic_xlsx.xlsx` · Remediation: write real dates · Approval: N.
- **SAT-EXP-D04** — (withdrawn, merged into D10; ID kept to avoid renumbering).
- **SAT-EXP-D05** — Low · Confirmed (known N4/RC13/RC14) · Customs Ledger PDF · re-verified, see §4 · Approval: Y for RC14 wording/real check, N for N4 (normalise unit case).
- **SAT-EXP-D06** — Low · Suspected defect · allotment · Allotment PDF subject quantity is `required_quantity` while table total is the allocated quantity (2,500,000 vs 2,082,810 Kgs; 1,488 vs 1,260 Kgs for allotment 3166); `int()` truncation of quantities and CIF header 0.00 where items hold CIF · Evidence: `out/allot_pdf_9827.pdf`, `allot_pdf_3166.pdf` · Remediation: show allocated total or flag shortfall; use Decimal rounding · Approval: Y (letter content).
- **SAT-EXP-D07** — Low · Confirmed defect · license (Balance PDF) · Export Items table prints the literal `None` as item name (0310815822, page 2) · Remediation: render "-" · Approval: N.
- **SAT-EXP-D08** — Low · Confirmed defect · license (Balance Excel Timeline) · "BOE Filed" date column shows the record creation timestamp (2026-07-31 07:12) instead of the BOE date (2017-10-18) · Approval: N.
- **SAT-EXP-D09** — Low · Confirmed defect · Customs Ledger PDF layout · BOE date wraps (`18-10-20`/`17`), header `BOE debite/d qty`, Port wraps, wide empty "BOE item" column · Evidence: `img/custpdf_0310815822.pdf.png` · Approval: N.
- **SAT-EXP-D10** — Medium · Confirmed defect · license-ledger export · Single-licence xlsx (`license_id=2531`) has License Summary with no licence row and GRAND TOTAL 0 while Financial Trade Ledger LICENSE TOTAL balance = 978,259.87; default scope returns 404 · Evidence: `out/ledgerxlsx_0310815822.xlsx`, `out/ledger_auto_xlsx.json` · Root cause: summary lists only licences with trade rows · Approval: Y (what the ledger should show for BOE-only licences).
- **SAT-EXP-D11** — Low · Business-rule ambiguity · Item Report Excel merges items sharing HSN + item name (2,198 rows vs 3,233 screen items) without a label · Approval: Y.
- **SAT-EXP-D12** — Low · Confirmed defect (formatting) · Qty shown 2dp on Balance Excel ledger sheets and PDF (3dp on Reconciliation sheet); 6,283 BOE rows in DB carry a non-zero third decimal (no hidden value in the sampled licences) – conflicts with owner decision D-F (qty 3dp). Also no autofilter on balance workbooks; Import Items PDF table has no thousand separators · Approval: N.
- **SAT-EXP-D13** — Low · Confirmed defect (dead code) · `exportAllotmentExcel` calls `allotment-actions/{id}/export-excel/`, which does not exist (404); no UI caller · Remediation: remove client or add endpoint · Approval: N.
- **SAT-EXP-D14** — Low · Performance note · `reports/item-report/` JSON is 65 MB; default allotment xlsx export takes ~33 s · Approval: N.

## 8. Test run (export-related files, own DB)

`cd backend && TEST_DB_NAME=test_lmanagement_sat_exp .venv/bin/python -m pytest <20 files> --import-mode=importlib -p no:cacheprovider -q -o addopts=""`
Files: `/tmp/sat/exp/testfiles.txt` (BOE export golden, cell formats/types, allotment xlsx formulas, item pivot excel x2, balance pdf/excel x3, ledger export security/parity/golden/pdf x6, custom ledger pdf, financial ledger pdf/DTO, trade export, date utils).
Result: **192 passed, exit 0** (27.05 s), log `/tmp/sat/exp/pytest_export.log`. The passing suite does not detect D01, D02, D03.

## 9. Limitations

Sample is 19 licences (of 2,185); no trade/invoice data; BOE grouped/port list exports not diffed row by row; bulk Excel per-sheet values and list PDFs checked structurally (page counts, row counts), not value-by-value; PDF layout judged from one rendered page plus text extraction.
