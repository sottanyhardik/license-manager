# License Manager - Refactoring Guide

## Overview

This document describes the modular refactoring completed for the license-manager application. The refactoring separates
business logic into small, focused, reusable modules for both backend and frontend.

## What Was Refactored

### Phase 1 & 2: Foundation and Services (Completed)

#### Backend Modules Created

##### 1. Core Utilities (`backend/core/utils/`)

**Purpose**: Reusable utility functions for common operations

- **`decimal_utils.py`**: Safe decimal operations, conversions, formatting
    - `to_decimal()`: Safe decimal conversion
    - `round_decimal_down()`: Round down to decimal places
    - `decimal_division()`: Safe division with zero handling
    - `sum_decimals()`: Sum multiple decimal values
    - `DecimalEncoder`: JSON encoder for Decimal types

- **`date_utils.py`**: Date parsing, formatting, and validation
    - `parse_date_safe()`: Parse dates from multiple formats
    - `is_date_expired()`: Check if date has passed
    - `date_range_overlaps()`: Check date range overlaps
    - `add_months()`: Add months to a date

- **`validation.py`**: Common validation functions
    - `validate_positive_decimal()`: Ensure positive numbers
    - `validate_date_range()`: Validate start/end dates
    - `validate_required_fields()`: Check required fields
    - `validate_balance_sufficient()`: Check balance sufficiency

##### 2. Core Exporters (`backend/core/exporters/`)

**Purpose**: Base classes for PDF and Excel generation

- **`base.py`**: Base exporter class and enums
    - `BaseExporter`: Abstract base for all exporters
    - `ExportFormat`: Enum for supported formats

- **`pdf/base_pdf.py`**: PDF generation base class
    - `BasePDFExporter`: ReportLab-based PDF generator
    - `PDFConfig`: Configuration dataclass
    - Helper methods for adding titles, tables, spacers

- **`pdf/styles.py`**: Predefined PDF styles
    - `PDFStyles`: Collection of paragraph and table styles
    - `create_table_style_basic()`: Standard table styling
    - `create_table_style_striped()`: Alternating row colors
    - `highlight_total_row()`: Emphasize summary rows

- **`pdf/table_builder.py`**: PDF table building utilities
    - `PDFTableBuilder`: Fluent interface for building tables
    - `create_simple_table()`: Quick table creation
    - `create_key_value_table()`: Info header tables
    - `format_currency_cell()`: Currency formatting

- **`excel/base_excel.py`**: Excel generation base class
    - `BaseExcelExporter`: openpyxl-based Excel generator
    - `ExcelConfig`: Configuration dataclass
    - Methods for writing cells, rows, worksheets

- **`excel/workbook_builder.py`**: Excel workbook utilities
    - `ExcelWorkbookBuilder`: Fluent interface for Excel
    - Methods for headers, data rows, totals
    - Auto-sizing and styling helpers

##### 3. License Services (`backend/license/services/`)

**Purpose**: Business logic for license operations

- **`balance_calculator.py`**: Balance calculations
    - `LicenseBalanceCalculator`: License-level balances
        - `calculate_credit()`: Total export CIF
        - `calculate_debit()`: Total BOE debits
        - `calculate_allotment()`: Total allotments
        - `calculate_balance()`: Final balance
    - `ItemBalanceCalculator`: Item-level balances
        - `calculate_item_balance()`: Import item balance
        - `calculate_available_quantity()`: Available qty
        - `calculate_available_value_for_allocation()`: Max allocation

- **`restriction_calculator.py`**: Restriction balance logic
    - `RestrictionCalculator`: Percentage-based restrictions
        - `calculate_restriction_balance()`: Balance for restriction %
        - `calculate_all_restriction_balances()`: All restrictions
        - `get_item_restriction_percentage()`: Item's restriction

- **`validation_service.py`**: License validation
    - `LicenseValidationService`: Business rule validation
        - `validate_license_active()`: Check if usable
        - `validate_sufficient_balance()`: Check balance
        - `validate_allocation()`: Comprehensive allocation check
        - `update_license_flags()`: Update all status flags

##### 4. Allotment Services (`backend/allotment/services/`)

**Purpose**: Business logic for allotment operations

- **`allocation_service.py`**: Allocation operations
    - `AllocationService`: Allocation business logic
        - `calculate_max_allocation()`: Max qty/value to allocate
        - `allocate_item()`: Create allocation
        - `deallocate_item()`: Remove allocation
        - `update_allocation()`: Modify allocation
        - `get_allocation_summary()`: Stats summary

- **`validation_service.py`**: Allotment validation
    - `AllotmentValidationService`: Validation rules
        - `validate_allotment_complete()`: Check required fields
        - `validate_can_allocate()`: Check if allocatable
        - `validate_allocation_within_limits()`: Check limits
        - `get_remaining_allocation_capacity()`: Remaining space

- **`filter_service.py`**: License filtering for allocation
    - `LicenseFilterService`: Filter available licenses
        - `filter_available_items()`: Apply all filters
        - `apply_search_filter()`: General search
        - `apply_quantity_filters()`: Qty range filters
        - `apply_value_filters()`: Value range filters

#### Frontend Modules Created

##### 1. Custom Hooks (`frontend/src/hooks/`)

**Purpose**: Reusable React hooks for common patterns

- **`usePagination.js`**: Pagination state management
    - `currentPage`, `pageSize`, `totalPages`
    - `goToPage()`, `nextPage()`, `prevPage()`
    - `getPageNumbers()`: For pagination UI

- **`useDebounce.js`**: Debouncing values and callbacks
    - `useDebounce(value, delay)`: Debounced value
    - `useDebouncedCallback()`: Debounced function

- **`useApiCall.js`**: API call state management
    - `execute()`: Run API call with error handling
    - `loading`, `error`, `data`, `success` states
    - `useMultipleApiCalls()`: Track multiple operations

##### 2. API Services (`frontend/src/services/api/`)

**Purpose**: Centralized API calls

- **`allotmentApi.js`**: Allotment operations
    - `fetchAvailableLicenses()`: Get allocatable licenses
    - `allocateItem()`: Allocate license to allotment
    - `updateAllocation()`: Update allocation
    - `deleteAllocation()`: Remove allocation
    - `exportAllotmentPDF()`: Export to PDF

- **`masterApi.js`**: Master CRUD operations
    - `fetchMasterList()`: List with pagination
    - `fetchMasterMetadata()`: Field definitions
    - `createMasterRecord()`: Create record
    - `updateMasterRecord()`: Update record
    - `deleteMasterRecord()`: Delete record
    - `exportMasterPDF()`, `exportMasterExcel()`: Exports

- **`licenseApi.js`**: License operations
    - `fetchLicenseList()`: List licenses
    - `fetchLicense()`: Get single license
    - `fetchLicenseBalance()`: Get balance info
    - `exportLicenseLedgerPDF()`: Export ledger
    - `fetchLicenseTransactions()`: BOE entries

##### 3. Calculator Utilities (`frontend/src/services/calculators/`)

**Purpose**: Business logic calculations

- **`allocationCalculator.js`**: Allocation calculations
    - `calculateMaxAllocation()`: Max qty/value
    - `calculateAllocationValue()`: Qty × price
    - `validateAllocation()`: Check constraints
    - `calculateRemainingCapacity()`: Remaining space
    - `isFullyAllocated()`: Check completion
    - `calculateAllocationPercentage()`: Progress %

- **`formCalculator.js`**: Form field calculations
    - `calculateRegistrationNumber()`: From license #
    - `calculateRelatedDates()`: Auto-fill dates
    - `calculateCIF()`: Qty × unit price
    - `autoCalculateFields()`: Auto-fill logic
    - `validateNumericField()`: Number validation
    - `formatNumber()`: Display formatting

## How to Use the New Modules

### Backend Usage Examples

#### Using Core Utilities

```python
from core.utils.decimal_utils import to_decimal, decimal_division
from core.utils.date_utils import is_date_expired
from core.utils.validation import validate_positive_decimal

# Safe decimal operations
value = to_decimal(user_input, default=Decimal('0'))
unit_price = decimal_division(100, 3, decimals=2)  # 33.33

# Date validation
if is_date_expired(license.expiry_date):
    print("License expired")

# Validation
validate_positive_decimal(amount, "invoice_amount", allow_zero=False)
```

#### Using License Services

```python
from license.services.balance_calculator import LicenseBalanceCalculator
from license.services.validation_service import LicenseValidationService

# Calculate license balance
balance = LicenseBalanceCalculator.calculate_balance(license)

# Get all balance components
components = LicenseBalanceCalculator.calculate_all_components(license)
print(f"Credit: {components['credit']}, Balance: {components['balance']}")

# Validate allocation
is_valid, errors = LicenseValidationService.validate_allocation(
    license, import_item, quantity, value
)
```

#### Using Allotment Services

```python
from allotment.services.allocation_service import AllocationService
from allotment.services.filter_service import LicenseFilterService

# Calculate max allocation
max_alloc = AllocationService.calculate_max_allocation(allotment, import_item)
print(f"Max: {max_alloc['max_quantity']} qty, {max_alloc['max_value']} value")

# Allocate item
allocation = AllocationService.allocate_item(
    allotment, import_item, quantity=100, cif_fc=1000, user=request.user
)

# Filter available licenses
available = LicenseFilterService.filter_available_items(
    description="sugar",
    min_quantity="50",
    notification_number="76/2015"
)
```

#### Using PDF/Excel Exporters

```python
from core.exporters.pdf import BasePDFExporter, PDFConfig, PDFStyles
from core.exporters.pdf.table_builder import PDFTableBuilder

class MyReportPDF(BasePDFExporter):
    def _add_content(self, data):
        styles = PDFStyles()
        
        # Add title
        self.add_title("My Report", styles.title)
        self.add_spacer(0.2)
        
        # Build table
        builder = PDFTableBuilder(styles=styles)
        builder.add_header_row(['Column 1', 'Column 2', 'Column 3'])
        builder.add_data_rows(data, number_columns=[2])
        table = builder.build()
        
        self.add_table(table)

# Use exporter
config = PDFConfig(orientation='landscape')
exporter = MyReportPDF(config=config)
buffer = exporter.generate(my_data)
```

### Frontend Usage Examples

#### Using Custom Hooks

```javascript
import { usePagination, useDebounce, useApiCall } from '../hooks';

function MyListComponent() {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 500);
  
  const {
    currentPage,
    pageSize,
    totalPages,
    goToPage,
    nextPage,
    prevPage,
    setTotalItems
  } = usePagination({ initialPageSize: 20 });
  
  const { execute, loading, error, data } = useApiCall();
  
  useEffect(() => {
    execute(() => fetchData(debouncedSearch, currentPage, pageSize));
  }, [debouncedSearch, currentPage]);
  
  // Use in JSX...
}
```

#### Using API Services

```javascript
import { allotmentApi, licenseApi, masterApi } from '../services/api';

// Fetch available licenses
const { data } = await allotmentApi.fetchAvailableLicenses(allotmentId, {
  description: 'sugar',
  min_quantity: '50'
});

// Allocate item
await allotmentApi.allocateItem(allotmentId, itemId, {
  qty: 100,
  cif_fc: 1000
});

// Fetch license balance
const balance = await licenseApi.fetchLicenseBalance(licenseId);

// Export to PDF
const pdfBlob = await licenseApi.exportLicenseLedgerPDF(licenseId);
```

#### Using Calculator Utilities

```javascript
import { allocationCalculator, formCalculator } from '../services/calculators';

// Calculate max allocation
const max = allocationCalculator.calculateMaxAllocation(item, allotment);
console.log(`Max qty: ${max.qty}, Max value: ${max.value}`);

// Validate allocation
const validation = allocationCalculator.validateAllocation(
  qty, value, item, allotment
);
if (!validation.isValid) {
  console.error(validation.errors);
}

// Auto-calculate form fields
const updates = formCalculator.autoCalculateFields(
  formData, 
  'quantity', 
  newQuantity
);
setFormData({ ...formData, ...updates });

// Format number
const formatted = formCalculator.formatNumber(1234567.89); // "1,234,567.89"
```

## Migration Guide

### Migrating Existing Code

#### Example: Migrating Views to Use Services

**Before:**

```python
# In views.py
def my_view(request, license_id):
    license = License.objects.get(id=license_id)
    
    # Calculate balance inline
    credit = ExportItems.objects.filter(license=license).aggregate(Sum('cif_fc'))
    debit = BOE.objects.filter(license=license).aggregate(Sum('cif_fc'))
    balance = credit - debit
```

**After:**

```python
# In views.py
from license.services.balance_calculator import LicenseBalanceCalculator

def my_view(request, license_id):
    license = License.objects.get(id=license_id)
    
    # Use service
    balance = LicenseBalanceCalculator.calculate_balance(license)
```

#### Example: Migrating Components to Use Hooks

**Before:**

```javascript
function MyComponent() {
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalItems, setTotalItems] = useState(0);
  
  const totalPages = Math.ceil(totalItems / pageSize);
  
  const goToPage = (page) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
  };
  
  // More pagination logic...
}
```

**After:**

```javascript
import { usePagination } from '../hooks';

function MyComponent() {
  const { 
    currentPage, 
    pageSize, 
    totalPages, 
    goToPage, 
    setTotalItems 
  } = usePagination({ initialPageSize: 20 });
  
  // Much cleaner!
}
```

## Benefits of Refactoring

### Backend Benefits

1. **Reusability**: Services can be used in views, management commands, signals, etc.
2. **Testability**: Pure functions easy to unit test
3. **Maintainability**: Business logic centralized in one place
4. **Consistency**: Same calculations everywhere
5. **DRY**: No more duplicate balance calculation code

### Frontend Benefits

1. **Code Reuse**: Hooks and utilities used across components
2. **Separation of Concerns**: Business logic separate from UI
3. **Easier Testing**: Pure functions testable independently
4. **Better Performance**: Logic outside components reduces re-renders
5. **Developer Experience**: Clear API, easy to understand

## Next Steps (Future Phases)

### Phase 3: Component Refactoring

- Split large components (AllotmentAction.jsx, MasterForm.jsx)
- Extract nested components
- Create specialized filter components

### Phase 4: Report Consolidation

- Consolidate PDF generators using base classes
- Consolidate Excel generators
- Extract report-specific logic

## File Structure Overview

```
backend/
├── core/
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── decimal_utils.py
│   │   ├── date_utils.py
│   │   └── validation.py
│   └── exporters/
│       ├── __init__.py
│       ├── base.py
│       ├── pdf/
│       │   ├── __init__.py
│       │   ├── base_pdf.py
│       │   ├── styles.py
│       │   └── table_builder.py
│       └── excel/
│           ├── __init__.py
│           ├── base_excel.py
│           └── workbook_builder.py
├── license/
│   └── services/
│       ├── __init__.py
│       ├── balance_calculator.py
│       ├── restriction_calculator.py
│       └── validation_service.py
└── allotment/
    └── services/
        ├── __init__.py
        ├── allocation_service.py
        ├── validation_service.py
        └── filter_service.py

frontend/
├── src/
│   ├── hooks/
│   │   ├── index.js
│   │   ├── usePagination.js
│   │   ├── useDebounce.js
│   │   └── useApiCall.js
│   ├── services/
│   │   ├── api/
│   │   │   ├── index.js
│   │   │   ├── allotmentApi.js
│   │   │   ├── masterApi.js
│   │   │   └── licenseApi.js
│   │   └── calculators/
│   │       ├── index.js
│   │       ├── allocationCalculator.js
│   │       └── formCalculator.js
│   └── utils/
```

## Testing the New Modules

### Backend Tests

```python
from decimal import Decimal
from license.services.balance_calculator import LicenseBalanceCalculator

def test_calculate_balance():
    # Create test license with known values
    license = create_test_license()
    
    balance = LicenseBalanceCalculator.calculate_balance(license)
    
    assert balance == Decimal('5000.00')
```

### Frontend Tests

```javascript
import { calculateMaxAllocation } from '../services/calculators/allocationCalculator';

test('calculateMaxAllocation', () => {
  const item = { available_quantity: 100, balance_cif_fc: 1000 };
  const allotment = { 
    unit_value_per_unit: 10, 
    balanced_quantity: 50,
    required_value: 500
  };
  
  const result = calculateMaxAllocation(item, allotment);
  
  expect(result.qty).toBe(50);
  expect(result.value).toBe(500);
});
```

## Conclusion

The refactoring creates a solid foundation for maintainable, testable code. All business logic is now centralized in
service modules, making the codebase easier to understand, modify, and extend.
