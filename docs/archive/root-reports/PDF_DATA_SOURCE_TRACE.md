# PDF DATA SOURCE AND ROUTING ANALYSIS

**CRITICAL FINDING:** Two separate PDF exporters exist, using DIFFERENT data sources.

---

## SUMMARY

There are **TWO completely separate PDF export systems** in the application:

1. **Single-License Balance PDF** (`balance-pdf`)
   - User-facing: Downloads from license detail modal/table
   - Data source: `LicenseBalanceCalculator` (balance engine)
   - File: `backend/apps/license/services/exporters/license_balance_pdf.py`

2. **Bulk Ledger PDF** (`export/all`, `company-ledger/export`)
   - User-facing: Bulk export from ledger view
   - Data source: `CanonicalLedgerService` (transaction ledger)
   - File: `backend/apps/license/services/exporters/ledger_pdf.py`

These two systems may produce **different financial totals** for the same license.

---

## PDF #1: SINGLE-LICENSE BALANCE PDF (Most Common)

### Frontend Entry Point
- **File:** `frontend/src/pages/masters/tables/LicensesTable.tsx`
- **Line:** 1085
- **Code:**
  ```typescript
  const r = await api.get(`licenses/${item.id}/balance-pdf/`, { responseType: "blob" });
  openPdfPreview(r.data as Blob, `${item.license_number || item.id}-balance.pdf`);
  ```
- **Trigger:** User clicks "Download PDF" button in license row expansion panel

### Backend Endpoint
- **Route:** `GET /api/licenses/{id}/balance-pdf/`
- **View:** `LicenseDetailsViewSet.balance_pdf()` in `/backend/apps/license/views/license.py` (line 692)
- **Handler Code:**
  ```python
  @action(detail=True, methods=['get'], url_path='balance-pdf')
  def balance_pdf(self, request, pk=None):
      """Generate PDF report for license balance details with all BOEs and Allotments."""
      from apps.license.services.exporters.license_balance_pdf import build_balance_pdf_response
      license_obj = self.get_object()
      show_hidden = request.query_params.get('show_hidden', '').lower() in ('1', 'true', 'yes')
      return build_balance_pdf_response(license_obj, request, show_hidden=show_hidden)
  ```

### PDF Generation Service
- **File:** `/backend/apps/license/services/exporters/license_balance_pdf.py`
- **Entry Point:** `build_balance_pdf_response(license_obj, request, show_hidden=False)` at line 648
- **Renders:** Three separate ledgers:
  1. **Financial Ledger** — bank-statement style CIF reconciliation
  2. **Customs Ledger** — BOE debit, allotment, trade details
  3. **Final Reconciliation Summary** — totals and variance check

### Data Sources for Balance PDF

#### 1. Financial Ledger (Lines 83-155)
- **Source:** `LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj, alloc_map, ext_map)` (line 105)
- **Location:** `/backend/apps/license/services/license_balance_ledger_builder.py` at line 194
- **Data Path:**
  - Opening balance: `license_obj.opening_balance`
  - Purchase credit: `LicenseBalanceCalculator.get_purchase_trade_rows(license_obj)`
  - BOE debits: `LicenseBalanceCalculator.get_debit_rows(license_obj)`
  - Allotment debits: `LicenseBalanceCalculator.get_allotment_rows(license_obj)`
  - Sale debits: `LicenseBalanceCalculator.get_trade_rows(license_obj)`
  - **Final balance:** `LicenseBalanceCalculator.calculate_financial_balance(license_obj)` (line 663)

#### 2. Customs Ledger (Lines 707-800)
- **Source:** `LicenseBalanceLedgerBuilder.build_customs_ledger()` at line 836 (in license_balance_ledger_builder.py)
- **Data Path:**
  - BOE rows: Direct query with invoice allocations
  - Allotment rows: Direct query
  - Running balance: Same calculator as financial

#### 3. Final Reconciliation Summary (Lines 701-800)
- **Source:** `build_reconciliation_summary()` (line 1220 in license_balance_ledger_builder.py)
- **Key Values Extracted:**
  - `engine_balance = LicenseBalanceCalculator.calculate_financial_balance(license_obj)` (line 663)
  - Used for: PDF summary totals at lines 705, 736, 800, 1179, 1251, 1285

### Critical Field Sources in Balance PDF

| PDF Field | Source | Line | Field |
|-----------|--------|------|-------|
| Current Balance | `LicenseBalanceCalculator.calculate_financial_balance(license_obj)` | 705 | engine_balance |
| Opening Balance | `license_obj.opening_balance` | 335 | direct model field |
| Total Purchase CIF | `LicenseBalanceCalculator.calculate_purchase_credit()` | 305 | accumulated credit |
| Total BOE Debit | `LicenseBalanceCalculator.get_debit_rows()` | queryset sum | debit total |
| Total Allotment Debit | `LicenseBalanceCalculator.get_allotment_rows()` | queryset sum | allotment total |

---

## PDF #2: BULK LEDGER PDF (Less Common)

### Frontend Entry Point
- **File:** `frontend/src/services/api/licenseApi.js`
- **Line:** 76
- **Code:**
  ```javascript
  export const exportLicenseLedgerPDF = async (licenseId) => {
      const response = await api.get(`licenses/${licenseId}/ledger-pdf/`, {
          responseType: 'blob'
      });
      return response.data;
  };
  ```
- **Note:** This function is defined but NOT USED in the codebase

### Backend Endpoints
- **Route 1:** `GET /api/license-ledger/export/all`
- **Route 2:** `GET /api/license-ledger/company-ledger/export`
- **View:** `LicenseLedgerViewSet.export_all()` and `company_ledger_export()` in `/backend/apps/license/views/ledger.py`
- **Handler Code (export_all at line 514):**
  ```python
  @action(detail=False, methods=['get'], url_path='export/all')
  def export_all(self, request):
      """Export all licenses (or filtered licenses) to a single PDF file."""
      # ... filtering logic ...
      pdf_content = self._generate_detailed_licenses_pdf(data, request.query_params)
      # or
      pdf_content = self._generate_all_licenses_pdf(data, request.query_params)
      return HttpResponse(pdf_content, content_type='application/pdf')
  ```

### PDF Generation Service
- **File:** `/backend/apps/license/services/exporters/ledger_pdf.py`
- **Entry Points:**
  1. `generate_detailed_licenses_pdf(licenses_data, query_params)` (line 308)
  2. `generate_all_licenses_pdf(licenses_data, query_params)` (line 670)
  3. `generate_company_ledger_pdf(licenses_data, company_name, query_params)` (line 1087)

### Data Sources for Ledger PDF

#### Canonical Ledger Dataset (Lines 44-295)
- **Source Function:** `CanonicalLedgerService.build_canonical_ledger_dataset()` (line 78)
- **File:** `/backend/apps/license/services/canonical_ledger_service.py`
- **Data Extracted (lines 88-94):**
  ```python
  canonical_total_purchase_bill_inr = float(canonical_summary.get('total_purchase_bill_inr', 0) or 0)
  canonical_total_sale_bill_inr = float(canonical_summary.get('total_sale_bill_inr', 0) or 0)
  canonical_total_profit_loss = float(canonical_summary.get('total_profit_loss', 0) or 0)
  ```
- **Per-Transaction Data (lines 96-104):**
  - Running balance: `canonical_balances[txn_id] = float(txn.get('license_running_balance', 0) or 0)`
  - Bill amount: `canonical_bill_amounts[txn_id] = float(txn.get('bill_amount', 0) or 0)`
  - SION norms: `canonical_sion_norms[txn_id] = txn.get('sion_norms', '')`

#### Transaction Data (Lines 120-288)
- **Source:** `LicenseTrade` model queries with direction-aware filtering
- **Lines:** 122-133
- **CIF Values:** Computed from `line.cif_inr` / `line.exc_rate` (lines 201-210)
- **Bill Amounts:** Pulled from canonical dataset (line 227)
  ```python
  total_amount = canonical_bill_amounts.get(trans_obj.id, 0)
  ```
- **Canonical Balance:** (line 264)
  ```python
  canonical_balance = canonical_balances.get(trans_obj.id, 0)
  ```

### Critical Field Sources in Ledger PDF

| PDF Field | Source | Line | Field |
|-----------|--------|------|-------|
| Running Balance | `CanonicalLedgerService.build_canonical_ledger_dataset()` | 78 | transactions[].license_running_balance |
| Bill Amount (INR) | `canonical_data['transactions'][idx]['bill_amount']` | 101 | extracted to canonical_bill_amounts |
| Total Purchase Bill INR | `canonical_summary['total_purchase_bill_inr']` | 92 | canonical_total_purchase_bill_inr |
| Total Sale Bill INR | `canonical_summary['total_sale_bill_inr']` | 93 | canonical_total_sale_bill_inr |
| Profit/Loss | `canonical_summary['total_profit_loss']` | 94 | canonical_total_profit_loss |
| SION Norms | `canonical_data['transactions'][idx]['sion_norms']` | 104 | canonical_sion_norms |

---

## CRITICAL DIFFERENCE: DATA SOURCES

### Balance PDF (`balance-pdf`)
Uses the **Balance Calculator Engine** — focuses on **CIF reconciliation**:
- Opening balance from `License.opening_balance` (fixed point in time)
- BOE debits from `LicenseBOEMapping` queryset
- Allotment debits from `AllotmentModel` queryset
- Trade debits/credits from `LicenseTrade` queryset
- **Final balance:** Computed by `LicenseBalanceCalculator.calculate_financial_balance()`

### Ledger PDF (`ledger_pdf`)
Uses the **Canonical Ledger Service** — focuses on **transaction history**:
- Opening balance from `canonical_data['opening_balance']`
- All transactions from `canonical_data['transactions']` array
- Bill amounts from `canonical_data['transactions'][idx]['bill_amount']`
- Running balances from `canonical_data['transactions'][idx]['license_running_balance']`
- **Final balance:** Comes from canonical ledger's running balance

---

## POTENTIAL BUG: FIELD MISMATCH

### If PDF shows "1,92,806.27 (USD)" 

**Investigate:**
1. Is this value in the Balance PDF or the Ledger PDF?
2. Is the field showing `balance_cif` from `License` model (denormalized)?
3. Or is it pulling from `canonical_summary['total_purchase_bill_inr']`?
4. Does the value match what `LicenseBalanceCalculator.calculate_financial_balance()` returns?
5. Does it match what `CanonicalLedgerService.build_canonical_ledger_dataset()` returns?

### Current Wrong Source (if confirmed):
- If PDF uses `License.balance_cif` (denormalized field), that's WRONG
- Should use **either:**
  - `LicenseBalanceCalculator.calculate_financial_balance()` (for Balance PDF)
  - `CanonicalLedgerService` final balance (for Ledger PDF)

---

## URLS ROUTING

### LicenseDetailsViewSet (single license operations)
- Base: `GET /api/licenses/`
- Actions:
  - `balance-pdf`: `GET /api/licenses/{id}/balance-pdf/`
  - `balance-excel`: `GET /api/licenses/{id}/balance-excel/`
  - `balance-excel-unused`: `GET /api/licenses/{id}/balance-excel-unused/`
  - `merged-documents`: `GET /api/licenses/{id}/merged-documents/`

### LicenseLedgerViewSet (ledger bulk operations)
- Base: `GET /api/license-ledger/`
- Actions:
  - `export/all`: `GET /api/license-ledger/export/all` — exports all/filtered licenses
  - `export/excel`: `GET /api/license-ledger/export/excel` — Excel export
  - `company-ledger/export`: `GET /api/license-ledger/company-ledger/export` — company-specific PDF
  - `company-ledger/export/excel`: `GET /api/license-ledger/company-ledger/export/excel` — company-specific Excel

---

## SERVICES INVOLVED

### Balance Calculator
- **File:** `/backend/apps/license/services/balance_calculator.py`
- **Methods:**
  - `calculate_financial_balance(license_obj)` — returns Decimal
  - `calculate_customs_balance(license_obj)` — returns Decimal
  - `get_purchase_trade_rows(license_obj)` — returns queryset
  - `get_debit_rows(license_obj)` — returns annotated queryset
  - `get_allotment_rows(license_obj)` — returns queryset
  - `get_trade_rows(license_obj)` — returns queryset

### License Balance Ledger Builder
- **File:** `/backend/apps/license/services/license_balance_ledger_builder.py`
- **Methods:**
  - `build_financial_ledger(license_obj, alloc_map, ext_map)` — returns (rows, summary)
  - `build_customs_ledger(license_obj, show_hidden)` — returns (rows, summary)
  - `build_reconciliation_summary(license_obj, financial_summary, customs_summary)` — returns summary dict

### Canonical Ledger Service
- **File:** `/backend/apps/license/services/canonical_ledger_service.py`
- **Methods:**
  - `build_canonical_ledger_dataset(license_id, license_type)` — returns dict with transactions and summary

---

## RECOMMENDATIONS

1. **Audit both services independently:**
   - Run Balance PDF on 5 test licenses
   - Run Ledger PDF on the same 5 licenses
   - Compare: `opening_balance`, `total_purchase`, `total_sale`, `final_balance`
   
2. **Check which is AUTHORITATIVE:**
   - Is `LicenseBalanceCalculator` tested against real trade data?
   - Is `CanonicalLedgerService` tested against real trade data?
   - Which one matches the human-auditable transaction history?

3. **Identify the bug:**
   - If value is `License.balance_cif` (denormalized field), that's the wrong source
   - Both PDFs should use live-calculated values from their respective services
   - Never use stale denormalized fields in exports

4. **Fix strategy:**
   - Align both to use the same authoritative source (or document why they differ)
   - Remove any use of `License.balance_cif` from PDF exports
   - Add tests to verify both PDFs show the same totals for the same license

