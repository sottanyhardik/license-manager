# License Ledger Detail — Calculation Inventory (Phase 3A)

**Status:** Research output. No code changed.
**Companion to:** `LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md` (analysis),
`LEDGER_DETAIL_MIGRATION_PLAN.md` (sequencing),
`LEDGER_DETAIL_RISK_ANALYSIS.md` (risk ratings).
**Verification:** every line number below was read at current HEAD
(`b32b2f75`, branch `feature/V2`) during this session. Nothing here is
carried over from a prior audit or inferred from a docstring.

---

## 0. The four consumers

`ledger_detail` (`backend/apps/license/views/ledger.py:218-259`) has **four**
distinct consumers, not two. This matters for every row of the table below,
because "the frontend" is not one thing:

| # | Consumer | Entry point | Role |
|---|---|---|---|
| C1 | **Detail page** | `frontend/src/pages/LicenseLedgerDetail.tsx:136` | The feature's own screen |
| C2 | **Client-side PDF** | `frontend/src/utils/ledgerExport.js:402` (`generatePDF`) | Called by C1 (`LicenseLedgerDetail.tsx:212`) *and* by the list page (`LicenseLedger.tsx:6`) |
| C3 | **Client-side Excel** | `frontend/src/utils/ledgerExport.js:623` (`generateExcel`) | Same two callers (`LicenseLedgerDetail.tsx:215`) |
| C4 | **Licenses master table, Transactions tab** | `frontend/src/pages/masters/tables/LicensesTable.tsx:990` fetch, `:518-629` render | A *different* screen reading the *same* endpoint |

C4 is the reason several findings below are live user-visible defects
rather than latent divergence risks: it renders backend fields that C1
recomputes.

Column key for the tables that follow:

- **Backend** — computed in `backend/apps/license/services/exporters/ledger_pdf.py`
- **Page (C1)** — `LicenseLedgerDetail.tsx`
- **PDF (C2)** / **Excel (C3)** — `ledgerExport.js`
- **Other (C4)** — `LicensesTable.tsx`
- ✓ = computes it here · **read** = consumes the backend value verbatim ·
  — = absent

---

## 1. License-level values

| Business Value | Backend | Page (C1) | PDF (C2) | Excel (C3) | Other (C4) | Current Owner |
|---|---|---|---|---|---|---|
| **Available / current balance** | ✓ `float(license.balance_cif or 0)` — `ledger_pdf.py:1260`, returned as `available_balance` `:1270`. Incentive: `float(license.balance_value or 0)` `:1438,1448` | **read** `:193, :321` | **read** `:248, :276` | **read** `:642, :677` | **read** `:565` | **`LicenseBalanceCalculator`** via the materialised `LicenseBalance.balance_cif` field (`models/core.py:188` proxy → `:1790` field). Backend is a pass-through, not an owner. **Compliant.** |
| **`db_balance`** | ✓ identical value, second key — `:1271`, `:1449` | — | — | — | typed at `:146`, never rendered | **Nobody.** Zero readers repo-wide (grep). Redundant alias created by the fix documented at `:1249-1259`. |
| **Total Value** | ✓ `total_purchase_cif` — `:1269`. Accumulated at `:1128` over `PURCHASE` **and** `COMMISSION_PURCHASE`; **or** overwritten to `float(license.opening_balance)` at `:1073` when the license has zero trades. Incentive: `total_purchase_value` `:1447`, accumulated `:1330`, no zero-trade branch | **read** `:305` | **read** `:275` | **read** `:677` | **read** `:561` | Backend, single. **But two different business meanings under one key** — see §5 (B1). |
| **1st Purchase Date** | — | — | ✓ `getFirstPurchaseDate` `:134-140` — lexicographic `min` over `type === 'PURCHASE'` dates; excludes `OPENING`/`COMMISSION`/`SALE` | ✓ same function `:568` | — | **Frontend-only.** No backend equivalent. Not shown on screen at all — appears only in the two exports. |
| **SION norms (license-level union)** | per-transaction `sion_norms` only — `:1167` | ✓ `:287-294` — `Set` over `String(t.sion_norms).split(', ')` | ✓ `getLicenseSionNorms` `:147-155` — `Set` over `.split(',').map(trim)` | ✓ same function `:569` | — | **Duplicated 2×, and the two split on different delimiters.** The page splits on `', '`, the exports split on `','` then trim — equivalent for the backend's own `', '.join(...)` output, divergent for any hand-entered value containing a bare comma. |
| **Purchase warning** (`hasPurchases`, `isNegativeBalance`, `showPurchaseWarning`) | — | ✓ `:190-195` | — | — | — | **Frontend-only, page-only.** A business-rule validation ("this license has no purchase entries") rendered as an Action Required banner `:244-259`. Never appears in the PDF or Excel a user downloads. Direct analogue of Item Pivot's on-screen-only Notification Summary. |

---

## 2. Per-transaction values (produced by the backend, DFIA)

All produced inside the single loop at `ledger_pdf.py:1090-1247`.

| Business Value | Backend definition (file:line) | Page (C1) | PDF (C2) | Excel (C3) | Other (C4) |
|---|---|---|---|---|---|
| `cif_usd` / `debit_cif` / `credit_cif` | `:1101-1109` per line: `cif_inr / exc_rate` when both present and `exc_rate > 0`, else `cif_fc`; summed to `total_cif_usd` `:1109`. Assigned to debit on `PURCHASE`/`COMMISSION_*` (`:1148,1171,1199`), to credit on `SALE` (`:1237`) | **read** `:434,437` | **read** `:198` | **read** `:746` | **read** `:610,613` |
| `amount` / `debit_amount` / `credit_amount` | `:1110` `sum(line.amount_inr)`; debit/credit split same rule | **read** `:454,457` | **read** `:212-213` | **read** `:750-751` | — |
| `qty` | `:1112` `sum(line.qty_kg)` for lines with an `sr_number` | — | — | — | — (no reader anywhere) |
| `rate` | `:1121-1124` `total_amount / total_cif_usd`, `round(...,2)` — a blended INR-per-CIF-$ rate | **read** `:451` | **read** `:211` | **read** `:749` | — |
| `items` | `:1166` `', '.join(set(items_desc))[:100]` | **read** `:428` | **read** `:198` | **read** `:746` | **read** `:604` |
| `sion_norms` | `:1167` `', '.join(sion_norms)` (insertion-ordered dedupe `:1118-1119`) | consumed by the union at `:291` | consumed at `:152` | same | — |
| **`balance` (running)** | `:1086,1154,1176,1205,1242` — `round(running_balance, 2)`. `running_balance` starts at 0 `:1056`; `+=` on `PURCHASE`/`COMMISSION_PURCHASE` `:1127`; **`+=` on `COMMISSION_SALE`** `:1188`; `-=` on `SALE` `:1212`. Ordered by `:1067` — purchases-first, then `invoice_date` | **✗ never read** — recomputed, see §3 | **✗ never read** — recomputed | **✗ never read** — recomputed | **read** `:616` — the **only reader in the app** |
| `profit_loss` | `:1216-1225`, `SALE` only. `total_amount − total_cif_usd × avg_rate`, where `avg_rate` = the **seller company's own** `purchase_amount / purchase_cif` when > 0 (`:1218-1220`), else the **license-wide** `total_purchase_amount / total_purchase_cif` (`:1221-1223`), else the raw `total_amount` (`:1225`). Zero on every non-`SALE` row | **read** `:404`, rendered `Math.abs` `:470` | **read** `:206`, rendered `(P)`/`(L)` `:207` | **read** `:753`, rendered `Math.abs` | **read** `:619-622`, rendered **signed** |
| `company_id` / `company_name` | `:1156-1157,1178-1179,1207-1208,1244-1245` — `to_company` on purchases, `from_company` on sales, i.e. **our** side of the trade, not the counterparty named in `particular` | grouping key `:107` | grouping key `:109` | same | — |
| `type` | `OPENING` / `PURCHASE` / `SALE` / `COMMISSION` — `:1077,1137,1144,1192,1229` | ✓ | ✓ | ✓ | ✓ |

### Backend accumulators that never leave the function

| Variable | Written | Read | Verdict |
|---|---|---|---|
| `total_purchase_amount` | `:1058,1129,1189` | `:1222` only (avg-rate fallback) | Internal — but it is exactly the number C2/C3 recompute as `totalDebit` |
| `total_sales_amount` | `:1059,1213` (Incentive `:1313,1405`) | **nowhere** | **Dead code.** Written on every sale, never read, never returned. It is exactly the number C2/C3 recompute as `totalCredit`. |
| `company_purchase_cif` / `company_purchase_amount` | `:1060-1061,1133-1134` | `:1216-1217` only | Internal — the per-company purchase rollup the exports recompute independently |

---

## 3. Per-company aggregates (the duplication core)

Every value in this section is computed **three times** in three files, and
**zero times** in the backend response.

| Business Value | Backend | Page (C1) | PDF (C2) | Excel (C3) | Current Owner |
|---|---|---|---|---|---|
| **Per-company running balance** | ✗ (backend's `balance` is license-wide, §2) | ✓ `:339-348` `companyBalMap` | ✓ `:185-191` `running` | ✓ `:730-740` `running` | **Triplicated, no owner.** All three are byte-identical in logic: `+=` debit on `PURCHASE`/`OPENING`, `-=` credit on `SALE`, **`COMMISSION` contributes nothing**, iterated in `TXN_ORDER` sequence (`tsx:331`, `js:118`), not date order. |
| **Company total debit (₹)** | `total_purchase_amount`, not returned | ✓ `:350` `reduce` over **all** txns | ✓ `:222` | ✓ `:771` | **Triplicated, no owner.** |
| **Company total credit (₹)** | `total_sales_amount`, dead + not returned | ✓ `:351` | ✓ `:223` | ✓ `:772` | **Triplicated, no owner.** |
| **Company P/L (ledger view)** | ✗ | ✓ `:352` `totalCredit − totalDebit` | ✓ `:227` | ✓ `:774` | **Triplicated, no owner.** Includes `COMMISSION` debits. |
| **Company closing balance (total row)** | ✗ | ✓ `:489` renders `companyRunning` after the loop | ✓ `:238` renders `running` | ✓ `:775` `lastBal = running` | Same three copies as the running balance. |

---

## 4. Summary-page / Summary-sheet aggregates

Present only in the two exports. **A different formula from §3 for the same
conceptual number.**

| Business Value | Backend | Page (C1) | PDF (C2) | Excel (C3) | Current Owner |
|---|---|---|---|---|---|
| Per-company-per-license **Purchase (₹)** | ✗ | ✗ | ✓ `:312` — `debit_amount` summed over `PURCHASE` **and** `OPENING` only | ✓ `:508-509` identical | **Duplicated 2×, frontend-only.** |
| Per-company-per-license **Sale (₹)** | ✗ | ✗ | ✓ `:313` — `credit_amount` over `SALE` only | ✓ `:510-511` identical | **Duplicated 2×, frontend-only.** |
| Per-company-per-license **P/L (₹)** | ✗ | ✗ | ✓ `:319` `_tSale − _tPurchase` | ✓ `:513` identical | **Duplicated 2×, frontend-only.** Excludes `COMMISSION` — see §5 (C1). |
| Company rollup Purchase/Sale/P-L | ✗ | ✗ | ✓ `:341,357` | ✓ `:558,597-599` | **Duplicated 2×, frontend-only.** |

> Note: `ledger_service.get_company_wise_trades` (`:616-711`) already
> computes a server-side `purchase_total` / `sale_total` / `profit_loss`
> per company for the **list page** — but over `trade.total_amount` (whole
> trade, all licenses on it), not per-license line amounts. It is a
> *third* definition of the same words, not a reusable owner for this
> feature. Recorded here so nobody mistakes it for one.

---

## 5. Divergences — the same number, two answers

Each is classified per the Item Pivot convention (A = preserve, no
ambiguity; B = business-rule validation required; C = likely
implementation defect, preserve for parity and flag).

### **[B1] "Total Value" has two meanings**
`total_value` is the sum of purchased CIF when the license has trades
(`:1128`), but the license's **total export CIF** — `license.opening_balance`,
which `models/core.py:280` documents as *"Total export CIF (credit)"* — when
it has none (`:1073`). Same field, same label ("Total Value",
`LicenseLedgerDetail.tsx:303`), two incompatible definitions depending on
data state. Incentive has no such branch at all (`:1311-1330`), so DFIA and
Incentive licenses answer "Total Value" differently too.

### **[B2] Backend `balance` and the on-screen Balance column are different numbers**
The backend computes a license-wide running balance in purchase-first,
then-`invoice_date` order (`:1067`), treating `COMMISSION_SALE` as a debit
(`:1188`). C1/C2/C3 compute a **per-company** running balance, restarting at
zero for each company group, in `OPENING → PURCHASE → SALE` type order with
no date component (`tsx:331-337`, `js:118-119`), treating `COMMISSION` as
contributing nothing (`tsx:342-346`, `js:187-191`, `js:736-740`).

For any license with more than one company, or any `COMMISSION` row, the two
disagree by construction. **C4 (`LicensesTable.tsx:616`) renders the backend
value.** So the same license's Balance column shows different figures in the
Licenses master table and on the License Ledger Detail page today. This is
a live defect, not a latent risk.

### **[B3] Three unreconciled definitions of P/L**
1. Backend per-`SALE` `profit_loss` — weighted-average-cost margin (`:1216-1225`).
2. Company total-row P/L — `totalCredit − totalDebit`, **all** rows including `COMMISSION` (`tsx:352`, `js:227`, `js:774`).
3. Summary P/L — `SALE credit − (PURCHASE|OPENING) debit`, **excluding** `COMMISSION` (`js:319`, `js:513`).

(1) is never totalled anywhere. (2) and (3) appear in the *same PDF* for the
same company and can differ by exactly the commission amount.

### **[C1] Commission rows are included in the ledger total but excluded from the summary total**
Direct consequence of B3(2) vs B3(3). Within one downloaded PDF, page 1's
"Purchase (Rs)" for a company and page 2's "Total — <company>" debit will
disagree whenever a commission exists.

### **[C2] `total_sales_amount` is dead code**
`ledger_pdf.py:1059,1213` (DFIA), `:1313,1405` (Incentive), and `:103,194`
(the out-of-scope `get_license_transactions`). Written on every sale, read
nowhere. The number it holds is precisely what C2/C3 recompute client-side.

### **[C3] `db_balance` has zero readers**
`:1271`, `:1449`. Byte-identical to `available_balance`.

### **[C4] P/L is rendered four different ways from one field**
`Math.abs` + colour (`tsx:470`); `(P)`/`(L)` prefix (`js:207`); `Math.abs`,
no per-row colour (`js:753`); signed with `+` (`LicensesTable.tsx:621`).
The screen actively hides the sign of a loss.

### **[C5] Zero renders as `0.00` on screen but `-` in both exports**
`fmtNum` (`js:122`) returns `'-'` for any value equal to zero;
`tsx:463` calls `formatIndianNumber` unconditionally. A genuinely
zero balance therefore looks like missing data in the download. This is
almost certainly the folk memory behind the *"fixes the '–' bug"* comment —
see [A1].

### **[C6] The PDF labels Incentive money in dollars**
`js:276` hardcodes `` `$${...}` `` for the Balance field regardless of type;
`js:423` gives Incentive sheets `'Value Dr ($)'`, `'Value Cr ($)'`,
`'Balance ($)'`; the summary column is `'Balance ($)'` at `js:331` and `js:531`
with a `$` value at `js:352` and `js:570`. The Excel *detail* sheet gets this
right (`js:677` uses `fmtCur(..., isDFIA ? 'USD' : 'INR')`), so PDF and Excel
disagree on currency for the same Incentive license.

### **[C7] `rate` means two different things under one column header**
DFIA `rate` is a blended INR-per-CIF-$ ratio rounded to 2dp (`:1122,1150`).
Incentive `rate` is `license_line.rate_pct` — a **percentage** — rounded to
3dp (`:1347`). Both render under a column headed "Rate"
(`tsx:390`, `js:422-423`, `js:649`).

### **[C8] The zero-trade OPENING row is grouped under a company named "N/A"**
The synthetic row at `:1074-1088` omits `company_id`, `company_name`, and
`trade_id`. `groupTransactionsByCompany` (`tsx:107`) keys it `unknown-0` and
`normalizeText` (`tsx:109`) yields `'N/A'`. So the only ledger row a
never-traded license has appears under a company header reading "N/A".

### **[C9] `items` ordering is non-deterministic**
`:1166` `', '.join(set(items_desc))[:100]` — Python `set` iteration order is
not stable across processes. Two identical requests can return different
`items` strings, and the `[:100]` truncation can therefore cut a different
item mid-name each time.

### **[A1] The "fixes the '–' bug" comment is *not* evidence of a backend correctness problem**
Read in full (`js:164-168` and `js:722-729`), the comment describes a removed
helper, `computeBalanceMap`, that keyed a `Map` by **transaction object
reference**. `groupByCompany` (`js:103-116`) re-runs `normalizeTransaction`
internally, producing fresh objects, so every lookup missed and every Balance
cell rendered `fmtNum(0)` → `'-'`. It was a client-side object-identity bug,
fixed by inlining the loop. `computeBalanceMap` no longer exists anywhere in
`frontend/src` (grep: only these two comments). Regression test:
`ledgerExport.test.ts:122-176`.

This **downgrades** the working hypothesis that the inline loop exists
because the backend's `balance` was wrong. It does not, however, explain
away B2 — the inline loop computes a genuinely *different, per-company*
quantity, whatever its origin.

> Note the same object-identity pattern survives at
> `LicenseLedgerDetail.tsx:340` (`Map<LedgerTransaction, number>`). It is
> **correct there** — `groupTransactionsByCompany` (`tsx:111`) pushes the
> original references rather than re-normalising — but it is untested and
> one refactor away from reproducing the bug.

---

## 6. Test coverage of everything above

| Target | Coverage |
|---|---|
| `build_dfia_ledger_detail` (~250 lines) | **None.** No test file in the repo references it. |
| `build_incentive_ledger_detail` (~175 lines) | **None.** |
| The `ledger_detail` action | **None.** `backend/tests/test_api_trade.py:91` `test_license_ledger_detail` reverses `license:license-ledger-detail`, which is DRF's router-generated **`retrieve`** route, not the action's `license-ledger-ledger-detail`. It asserts only `200` and `isinstance(response.data, dict)` (`:96-98`). A name collision that reads as coverage and is not. |
| Golden master | `backend/scripts/golden_master_ledger_pdf.py` covers `export/all` (×2) and `company-ledger/export` only (`:4-6, 82-86`) — the in-scope builders are deliberately excluded. |
| C1 running balance / totals (`tsx:339-352`) | **None.** `LicenseLedgerDetail.test.tsx` has 5 blocks, all formatting/plumbing; the render test (`:101`) mocks `ledgerExport` entirely (`:26-29`) and asserts no numbers. |
| C2 PDF (`buildPdfBody`) | **None.** `generatePDF` is never invoked by any test. |
| C3 Excel running balance | **One test** — `ledgerExport.test.ts:122-176`, asserts `500.00 → 400.00`, total `400.00` against a real workbook buffer. The only genuine calculation test in the feature. |
| C3 summary sheet | `ledgerExport.test.ts:178-225` — asserts 1st-purchase-date and SION dedupe (non-numeric aggregation). No Purchase/Sale/P-L assertions. |
| C4 (`LicensesTable` Transactions tab) | **None** found. |

Runner notes (relevant to Phase 3D): backend pytest collects cleanly (210
under `tests/`, 868 under `apps/license/tests/`), but `pytest.ini:6` sets
`testpaths = tests`, so a bare `pytest` **skips all 868** license tests.
Frontend runs on Vitest (`frontend/vitest.config.ts`); `frontend/jest.config.js`
is orphaned (jest not installed).
