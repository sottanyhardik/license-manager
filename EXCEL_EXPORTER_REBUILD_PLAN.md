# Excel Exporter Refactoring Plan: Separation of Concerns

**Status:** Planning Phase  
**Date:** 2026-08-14  
**Scope:** Refactor `ledger_excel.py` to separate business logic from rendering  
**Target Files:**
- `backend/apps/license/services/exporters/ledger_excel.py` (currently 705 lines)
- `backend/apps/license/views/ledger.py` (calls the exporter)
- `backend/apps/license/tests/test_ledger_golden.py` (validation)

---

## Current State Analysis

### ledger_excel.py (705 lines)
**Current Problems:**
1. **Mixed concerns**: 3 functions each contain business logic + rendering
2. **Multiple CanonicalLedgerService calls inside loops**: Lines 87-96, 144-157, 341-348, 600-609
   - `generate_ledger_summary_excel()`: Calls service in loop for **every** license twice (P/L check + data fetch)
   - `generate_ledger_detailed_excel()`: Calls service in loop for **every** license
   - `generate_ledger_company_excel()`: Calls service in loop for **every** license
3. **Business logic embedded in rendering**:
   - Debit/credit calculations (lines 402-415 in detailed)
   - Running P/L computation (line 421)
   - Purchase bill status derivation (line 428)
   - Currency-aware formatting (lines 179-181)
4. **No data holder**: Pre-calculated data not reused; recalculated per format

### ledger.py (Views)
**Current Integration:**
- `export_excel()` (line 589): Calls `generate_ledger_summary_excel()` or `generate_ledger_detailed_excel()`
- `company_ledger_export_excel()` (line 655): Calls `generate_ledger_company_excel()`
- Views pass raw `licenses_data` list + `query_params` to exporters
- **No intermediate service layer**: Views → Exporters (should be Views → Service → Exporters)

### test_ledger_golden.py (Validation)
**Current Tests:**
- Lines 209-226: Validates canonical ledger data (purchase transaction)
- Lines 267-284: Validates canonical ledger data (sale transaction)
- Lines 287+: Validates balance, P/L, API response, PDF/Excel consistency

---

## Proposed Architecture

### Phase 1: Data Layer (DTOs)

#### 1.1 Create `FinancialLedgerExportDTO`
**File:** `backend/apps/license/services/exporters/dto.py` (new, ~80 lines)

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

@dataclass
class TransactionRow:
    """Pre-calculated transaction for rendering (no business logic)."""
    date: date
    particulars: str
    type: str
    items: str
    debit_cif: float  # Sale amount
    credit_cif: float  # Purchase amount
    debit_bill: float  # Sale bill INR
    credit_bill: float  # Purchase bill INR
    running_balance: float
    running_pl: float
    purchase_bill_status: str
    sion_norms: str

@dataclass
class SummaryRow:
    """Pre-calculated license summary (no business logic)."""
    license_number: str
    type: str
    exporter_name: str
    license_date: date
    expiry_date: date
    purchase_usd: float
    sold_usd: float
    balance_usd: float
    purchase_amt_inr: float
    sale_amt_inr: float
    profit_loss: float
    status: str
    has_no_purchase: bool
    has_negative_balance: bool

@dataclass
class CompanyLedgerRow:
    """Pre-calculated company ledger row (no business logic)."""
    license_number: str
    type: str
    exporter_name: str
    license_date: date
    expiry_date: date
    total_value: float
    balance: float
    profit_loss: float
    currency: str

@dataclass
class FinancialLedgerExportDTO:
    """Pre-calculated data ready for rendering — zero business logic."""
    
    # Summary Export
    summary_rows: List[SummaryRow]
    summary_totals: dict  # {total_purchase_usd, total_sold_usd, ...}
    
    # Detailed Export (per-license sheets)
    detailed_sheets: dict  # license_id → {transactions: List[TransactionRow], title, ...}
    
    # Company Export
    company_rows: List[CompanyLedgerRow]
    company_totals: dict
    
    # Metadata
    export_type: str  # 'summary', 'detailed', 'company'
    filter_info: dict
    no_purchase_count: int
```

---

### Phase 2: Business Logic Service

#### 2.1 Create `LedgerExportService`
**File:** `backend/apps/license/services/exporters/export_service.py` (new, ~200 lines)

**Responsibilities:**
- Call `CanonicalLedgerService.build_canonical_ledger_dataset()` **once per license**
- Pre-calculate all debit/credit, P/L, running totals
- Populate DTO with ready-to-render data
- Handle currency, formatting decisions

**Key Methods:**

```python
class LedgerExportService:
    
    @staticmethod
    def prepare_summary_export(licenses_data: List[dict], query_params: dict) -> FinancialLedgerExportDTO:
        """
        Pre-calculate all licenses for summary export.
        - Fetch canonical ledger for each license once
        - Derive all displayed fields (P/L, purchase amt, etc.)
        - Return DTO ready for rendering
        """
        summary_rows = []
        totals = {
            'total_purchase_usd': 0.0,
            'total_sold_usd': 0.0,
            'total_balance_usd': 0.0,
            'total_purchase_amt': 0.0,
            'total_sale_amt': 0.0,
            'total_pl': 0.0,
        }
        no_purchase_count = 0
        
        for lic in licenses_data:
            canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
                license_id=lic.get('id'),
                license_type=lic.get('license_type')
            )
            summary = canonical.get('summary', {})
            
            # Extract and pre-calculate
            purchase_amt = float(summary.get('total_purchase_bill_inr', 0) or 0)
            sale_amt = float(summary.get('total_sale_bill_inr', 0) or 0)
            profit_loss = float(summary.get('total_profit_loss', 0) or 0)
            
            # Check purchase status
            has_no_purchase = purchase_amt == 0
            if has_no_purchase:
                no_purchase_count += 1
            
            # Create row
            row = SummaryRow(
                license_number=lic.get('license_number', '-'),
                type=lic.get('license_type', '-'),
                exporter_name=lic.get('exporter_name', '-') or '-',
                license_date=lic.get('license_date'),
                expiry_date=lic.get('license_expiry_date'),
                purchase_usd=float(lic.get('total_value', 0) or 0),
                sold_usd=float(lic.get('sold_value', 0) or 0),
                balance_usd=float(lic.get('balance_value', 0) or 0),
                purchase_amt_inr=purchase_amt,
                sale_amt_inr=sale_amt,
                profit_loss=profit_loss,
                status='Active' if lic.get('is_active') else 'Expired',
                has_no_purchase=has_no_purchase,
                has_negative_balance=float(lic.get('balance_value', 0) or 0) < 0,
            )
            summary_rows.append(row)
            
            # Accumulate totals
            totals['total_purchase_usd'] += row.purchase_usd
            totals['total_sold_usd'] += row.sold_usd
            totals['total_balance_usd'] += row.balance_usd
            totals['total_purchase_amt'] += row.purchase_amt_inr
            totals['total_sale_amt'] += row.sale_amt_inr
            totals['total_pl'] += row.profit_loss
        
        return FinancialLedgerExportDTO(
            export_type='summary',
            summary_rows=summary_rows,
            summary_totals=totals,
            detailed_sheets={},
            company_rows=[],
            company_totals={},
            filter_info=_extract_filter_info(query_params),
            no_purchase_count=no_purchase_count,
        )
    
    @staticmethod
    def prepare_detailed_export(licenses_data: List[dict], query_params: dict) -> FinancialLedgerExportDTO:
        """
        Pre-calculate all transactions for detailed export.
        - One sheet per license
        - Transactions from canonical ledger
        - Running balance/P/L pre-calculated
        """
        detailed_sheets = {}
        
        for lic in licenses_data:
            canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
                license_id=lic.get('id'),
                license_type=lic.get('license_type')
            )
            
            transactions = canonical.get('display_transactions', [])
            rows = []
            cumulative_sale_bill = 0.0
            cumulative_purchase_bill = 0.0
            has_purchase_bill = canonical.get('has_purchase_bill', False)
            
            for txn in transactions:
                # Extract and calculate
                debit_cif = 0.0
                credit_cif = 0.0
                debit_amount = 0.0
                credit_amount = 0.0
                
                if 'SALE' in txn.get('type', ''):
                    debit_cif = float(txn.get('amount') or 0)
                    debit_amount = float(txn.get('bill_amount') or 0)
                    cumulative_sale_bill += debit_amount
                elif 'PURCHASE' in txn.get('type', '') or txn.get('type') == 'OPENING':
                    credit_cif = float(txn.get('amount') or 0)
                    credit_amount = float(txn.get('bill_amount') or 0)
                    cumulative_purchase_bill += credit_amount
                
                running_pl = cumulative_sale_bill - cumulative_purchase_bill
                
                row = TransactionRow(
                    date=txn.get('date'),
                    particulars=_format_particulars(txn),
                    type=txn.get('type', 'UNKNOWN').replace('_', ' ').title(),
                    items=_format_items(txn.get('item_names', [])),
                    debit_cif=debit_cif,
                    credit_cif=credit_cif,
                    debit_bill=debit_amount,
                    credit_bill=credit_amount,
                    running_balance=float(txn.get('license_running_balance', 0) or 0),
                    running_pl=running_pl,
                    purchase_bill_status='WITH_PURCHASE_BILL' if has_purchase_bill else 'NO_PURCHASE_BILL',
                    sion_norms=txn.get('sion_norms', '') or 'N/A',
                )
                rows.append(row)
            
            detailed_sheets[lic.get('id')] = {
                'title': f"LICENSE {lic.get('license_number')}",
                'exporter': lic.get('exporter_name'),
                'type': lic.get('license_type'),
                'license_date': lic.get('license_date'),
                'expiry_date': lic.get('license_expiry_date'),
                'transactions': rows,
            }
        
        return FinancialLedgerExportDTO(
            export_type='detailed',
            summary_rows=[],
            summary_totals={},
            detailed_sheets=detailed_sheets,
            company_rows=[],
            company_totals={},
            filter_info=_extract_filter_info(query_params),
            no_purchase_count=0,
        )
    
    @staticmethod
    def prepare_company_export(licenses_data: List[dict], company_name: str, query_params: dict) -> FinancialLedgerExportDTO:
        """
        Pre-calculate all licenses for company export.
        - One row per license for the company
        - P/L from canonical ledger
        """
        company_rows = []
        total_pl = 0.0
        
        for lic in licenses_data:
            canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
                license_id=lic.get('id'),
                license_type=lic.get('license_type')
            )
            summary = canonical.get('summary', {})
            profit_loss = float(summary.get('total_profit_loss', 0) or 0)
            
            currency = 'USD' if lic.get('license_type') == 'DFIA' else 'INR'
            
            row = CompanyLedgerRow(
                license_number=lic.get('license_number', '-'),
                type=lic.get('license_type', '-'),
                exporter_name=lic.get('exporter_name', '-') or '-',
                license_date=lic.get('license_date'),
                expiry_date=lic.get('license_expiry_date'),
                total_value=float(lic.get('total_value', 0) or 0),
                balance=float(lic.get('balance_value', 0) or 0),
                profit_loss=profit_loss,
                currency=currency,
            )
            company_rows.append(row)
            total_pl += profit_loss
        
        return FinancialLedgerExportDTO(
            export_type='company',
            summary_rows=[],
            summary_totals={},
            detailed_sheets={},
            company_rows=company_rows,
            company_totals={'total_pl': total_pl},
            filter_info=_extract_filter_info(query_params),
            no_purchase_count=0,
        )
```

---

### Phase 3: Pure Renderers

#### 3.1 Refactor `ledger_excel.py` (~150-250 lines)

**New Structure:**
```python
def generate_ledger_summary_excel(dto: FinancialLedgerExportDTO) -> tuple[bytes, str]:
    """
    PURE RENDERER: Takes pre-calculated DTO, returns Excel bytes.
    Zero business logic.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "License Summary"
    
    # Apply styles (unchanged)
    HEADER_FILL = ...
    HEADER_FONT = ...
    
    current_row = 1
    
    # Title
    ws.merge_cells(f'A{current_row}:L{current_row}')
    title_cell = ws[f'A{current_row}']
    title_cell.value = "LICENSE LEDGER - SUMMARY"
    # ... styling ...
    current_row += 1
    
    # Filter info (from DTO)
    ws.merge_cells(f'A{current_row}:L{current_row}')
    filter_cell = ws[f'A{current_row}']
    filter_cell.value = f"Filter: {_format_filter_info(dto.filter_info)}"
    # ... styling ...
    current_row += 1
    
    # Warning if no-purchase licenses
    if dto.no_purchase_count > 0:
        ws.merge_cells(f'A{current_row}:L{current_row}')
        warn_cell = ws[f'A{current_row}']
        warn_cell.value = f"⚠ WARNING: {dto.no_purchase_count} license(s) with no purchase transactions"
        # ... styling ...
        current_row += 2
    
    # Headers (unchanged)
    headers = [...]
    header_row = current_row
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col_num, value=header)
        # ... styling ...
    current_row += 1
    
    # DATA ROWS — iterate DTO.summary_rows (already calculated)
    for row_dto in dto.summary_rows:
        values = [
            row_dto.license_number,
            row_dto.type,
            row_dto.exporter_name,
            row_dto.license_date.strftime('%d-%b-%y') if row_dto.license_date else '-',
            row_dto.expiry_date.strftime('%d-%b-%y') if row_dto.expiry_date else '-',
            f"${format_indian_number(row_dto.purchase_usd, 2)}",
            f"${format_indian_number(row_dto.sold_usd, 2)}",
            f"${format_indian_number(row_dto.balance_usd, 2)}",
            format_indian_number(row_dto.purchase_amt_inr, 2),
            format_indian_number(row_dto.sale_amt_inr, 2),
            format_indian_number(row_dto.profit_loss, 2),
            row_dto.status,
        ]
        
        for col_num, value in enumerate(values, 1):
            cell = ws.cell(row=current_row, column=col_num, value=value)
            cell.border = THIN_BORDER
            
            # Apply styling based on DTO flags
            if row_dto.has_no_purchase:
                cell.fill = NO_PURCHASE_FILL
            
            if col_num == 8 and row_dto.has_negative_balance:
                cell.fill = NEGATIVE_BALANCE_FILL
                cell.font = NEGATIVE_BALANCE_FONT
            
            if col_num == 11:  # P/L column
                cell.font = PROFIT_FONT if row_dto.profit_loss >= 0 else LOSS_FONT
        
        current_row += 1
    
    # TOTALS ROW — from DTO.summary_totals (already calculated)
    totals_data = [
        'TOTAL', '', '', '', '',
        f"${format_indian_number(dto.summary_totals['total_purchase_usd'], 2)}",
        # ... rest from DTO ...
    ]
    # ... render totals ...
    
    # Column widths (unchanged)
    ws.column_dimensions['A'].width = 15
    # ...
    
    ws.freeze_panes = f'A{header_row + 1}'
    
    # Save & return
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"ledger_summary_{timestamp}.xlsx"
    
    return excel_file.read(), filename

def generate_ledger_detailed_excel(dto: FinancialLedgerExportDTO) -> tuple[bytes, str]:
    """
    PURE RENDERER: Takes pre-calculated DTO, returns Excel bytes.
    Zero business logic. One sheet per license from DTO.detailed_sheets.
    """
    # Similar structure, iterate dto.detailed_sheets
    # Each sheet has pre-calculated TransactionRow objects
    # Just render them with no calculations
    
def generate_ledger_company_excel(dto: FinancialLedgerExportDTO, company_name: str) -> tuple[bytes, str]:
    """
    PURE RENDERER: Takes pre-calculated DTO, returns Excel bytes.
    Zero business logic. Iterates dto.company_rows.
    """
    # Similar structure for company export
```

---

### Phase 4: View Integration

#### 4.1 Update `ledger.py`

**Before:**
```python
@action(detail=False, methods=['get'], url_path='export/excel')
def export_excel(self, request):
    data = self.get_queryset()
    # ... filtering ...
    excel_content, filename = generate_ledger_detailed_excel(data, request.query_params)
    # Direct call to exporter with no intermediate processing
```

**After:**
```python
@action(detail=False, methods=['get'], url_path='export/excel')
def export_excel(self, request):
    from apps.license.services.exporters.export_service import LedgerExportService
    
    data = self.get_queryset()
    # ... filtering ...
    
    detailed = request.query_params.get('detailed', 'false').lower() == 'true'
    
    if detailed:
        # PHASE 2: Pre-calculate with service
        dto = LedgerExportService.prepare_detailed_export(data, request.query_params)
        # PHASE 3: Render with pure renderer
        excel_content, filename = generate_ledger_detailed_excel(dto)
    else:
        dto = LedgerExportService.prepare_summary_export(data, request.query_params)
        excel_content, filename = generate_ledger_summary_excel(dto)
    
    # ... return response ...

@action(detail=False, methods=['get'], url_path='company-ledger/export/excel')
def company_ledger_export_excel(self, request):
    from apps.license.services.exporters.export_service import LedgerExportService
    
    company_id = request.query_params.get('company')
    # ... validation ...
    
    data = self.get_queryset()
    
    # PHASE 2: Pre-calculate
    dto = LedgerExportService.prepare_company_export(data, company_name, request.query_params)
    # PHASE 3: Render
    excel_content, filename = generate_ledger_company_excel(dto, company_name)
    
    # ... return response ...
```

---

## Implementation Phases

### Phase 1: Create DTO (Week 1, Day 1)
- Create `dto.py` with 5 dataclasses
- 80 lines, no dependencies on other modules
- **Validation**: Manual inspection for dataclass correctness

### Phase 2: Create Service (Week 1, Days 2-3)
- Create `export_service.py` with business logic
- Pre-calculate all data from canonical ledger
- 200 lines of logic
- **Validation**: Unit tests mock CanonicalLedgerService, verify DTO structure

### Phase 3: Refactor Exporter (Week 1, Day 4)
- Refactor 3 functions in `ledger_excel.py`
- Remove all CanonicalLedgerService calls
- Replace with DTO field access
- Lines: 705 → ~200 (67% reduction)
- **Validation**: Manual code inspection, no functionality change yet

### Phase 4: Update Views (Week 2, Day 1)
- Update 3 endpoints in `ledger.py`
- Add service calls before exporter calls
- 3 small changes, low risk
- **Validation**: Integration tests verify Excel export still works

### Phase 5: Golden Test Validation (Week 2, Day 2)
- Run `test_ledger_golden.py`
- Verify numbers match (purchase, sale, balance, P/L)
- Verify no regressions
- **Success Criteria**: All golden tests pass with same numbers

---

## File Structure After Refactoring

```
backend/apps/license/services/exporters/
├── __init__.py
├── dto.py                      (NEW, 80 lines)
├── export_service.py           (NEW, 200 lines)
├── ledger_excel.py             (REFACTORED, 705 → ~200 lines)
├── ledger_pdf.py               (UNCHANGED)
└── ...

backend/apps/license/views/
├── ledger.py                   (UPDATED, 3 small integration points)
└── ...
```

---

## Risk Assessment

### Low Risk
- **DTO creation**: No dependencies, pure data holders
- **Service creation**: Only reads from CanonicalLedgerService, no writes
- **View integration**: Only changes call signature, logic stays same

### Medium Risk
- **Exporter refactoring**: Large file, many formatting details
  - **Mitigation**: Render each section independently, test per-sheet
  - **Validation**: Byte-by-byte comparison with old export (visual test)

### Golden Test Dependency
- Tests assume specific column layouts in Excel
- If column widths change, tests may fail visually (not numerically)
- **Mitigation**: Keep styles/widths identical, test numbers only

---

## Success Criteria

1. ✅ `dto.py` created with correct types
2. ✅ `export_service.py` created with logic moved from `ledger_excel.py`
3. ✅ `ledger_excel.py` reduced to ~200 lines (rendering only)
4. ✅ View integration updated
5. ✅ Golden test suite passes (test_ledger_golden.py)
6. ✅ Excel numbers match PDF/API output (no regression)
7. ✅ No CanonicalLedgerService calls inside export functions

---

## Example: Before/After

### Before (Mixed Concerns)
```python
def generate_ledger_summary_excel(licenses_data, query_params):
    wb = openpyxl.Workbook()
    # ... 100 lines of styling setup ...
    
    for lic in licenses_data:
        # BUSINESS LOGIC: Fetch canonical data
        canonical_data = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=lic.get('id'),
            license_type=lic.get('license_type')
        )
        summary = canonical_data.get('summary', {})
        
        # BUSINESS LOGIC: Calculate values
        purchase_amt = float(summary.get('total_purchase_bill_inr', 0) or 0)
        sale_amt = float(summary.get('total_sale_bill_inr', 0) or 0)
        profit_loss = float(summary.get('total_profit_loss', 0) or 0)
        
        # RENDERING: Format and place in Excel
        cell.value = format_indian_number(purchase_amt, 2)
        cell.font = PROFIT_FONT if profit_loss >= 0 else LOSS_FONT
    
    # ... 600 more lines ...
    return excel_file.read(), filename
```

### After (Separated Concerns)
```python
# Service layer (business logic)
def prepare_summary_export(licenses_data, query_params):
    rows = []
    for lic in licenses_data:
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(...)
        summary = canonical.get('summary', {})
        
        row = SummaryRow(
            purchase_amt_inr=float(summary.get('total_purchase_bill_inr', 0) or 0),
            sale_amt_inr=float(summary.get('total_sale_bill_inr', 0) or 0),
            profit_loss=float(summary.get('total_profit_loss', 0) or 0),
            # ... all fields pre-calculated ...
        )
        rows.append(row)
    
    return FinancialLedgerExportDTO(summary_rows=rows, ...)

# Renderer (rendering only)
def generate_ledger_summary_excel(dto):
    wb = openpyxl.Workbook()
    # ... styling ...
    
    for row_dto in dto.summary_rows:
        cell.value = format_indian_number(row_dto.purchase_amt_inr, 2)
        cell.font = PROFIT_FONT if row_dto.profit_loss >= 0 else LOSS_FONT
    
    return excel_file.read(), filename
```

---

## Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| ledger_excel.py size | 705 lines | ~200 lines | -67% |
| CanonicalLedgerService calls in loop | Yes (3 functions) | No (service only) | 100% |
| Code separation | Mixed | Clean (2 modules) | N/A |
| Testability | Medium | High | N/A |
| Maintainability | Low | High | N/A |

---

## Dependencies
- `openpyxl`: Excel generation (unchanged)
- `CanonicalLedgerService`: Service dependency (unchanged usage)
- `shared.pdf.builders.format_indian_number`: Number formatting (unchanged)

---

## Open Questions
1. Should DTOs use Pydantic or dataclasses? → **Decision: dataclasses** (simpler, no validation needed)
2. Should service cache canonical results? → **Decision: No** (CanonicalLedgerService handles caching)
3. Should renderers be in separate file? → **Decision: Keep in ledger_excel.py** (low churn, related functions)

---

## Next Steps
1. **Approval**: Review plan, confirm scope
2. **Sprint 1**: Implement Phases 1-2 (DTO + Service)
3. **Sprint 2**: Implement Phases 3-4 (Renderer refactor + view updates)
4. **Validation**: Run golden test suite, verify no regressions
5. **Merge**: PR with before/after metrics
