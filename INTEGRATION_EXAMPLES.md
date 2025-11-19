# Integration Examples

This document provides practical examples of how to integrate the new modular services into your existing code.

## Table of Contents

1. [Backend Integration](#backend-integration)
2. [Frontend Integration](#frontend-integration)
3. [Complete Examples](#complete-examples)
4. [Testing Examples](#testing-examples)

---

## Backend Integration

### Example 1: Updating Views to Use Services

#### Before (views_actions.py)

```python
@action(detail=True, methods=['post'])
def allocate_item(self, request, pk=None):
    allotment = get_object_or_404(AllotmentModel, pk=pk)
    item_id = request.data.get('item_id')
    qty = request.data.get('qty')
    cif_fc = request.data.get('cif_fc')
    
    # Inline validation and allocation
    import_item = LicenseImportItemsModel.objects.get(id=item_id)
    
    # Calculate available quantity manually
    total_qty = import_item.quantity
    debited = RowDetails.objects.filter(
        sr_number=import_item
    ).aggregate(Sum('qty'))['qty__sum'] or 0
    allotted = AllotmentItems.objects.filter(
        item=import_item
    ).aggregate(Sum('qty'))['qty__sum'] or 0
    available = total_qty - debited - allotted
    
    if qty > available:
        return Response({'error': 'Insufficient quantity'}, status=400)
    
    # Create allocation
    allocation = AllotmentItems.objects.create(
        allotment=allotment,
        item=import_item,
        qty=qty,
        cif_fc=cif_fc
    )
    
    return Response({'success': True})
```

#### After (using services)

```python
from allotment.services import AllocationService
from license.services.validation_service import LicenseValidationService

@action(detail=True, methods=['post'])
def allocate_item(self, request, pk=None):
    allotment = get_object_or_404(AllotmentModel, pk=pk)
    item_id = request.data.get('item_id')
    qty = request.data.get('qty')
    cif_fc = request.data.get('cif_fc')
    
    import_item = get_object_or_404(LicenseImportItemsModel, id=item_id)
    
    try:
        # Use service for allocation (includes all validation)
        allocation = AllocationService.allocate_item(
            allotment=allotment,
            import_item=import_item,
            quantity=qty,
            cif_fc=cif_fc,
            user=request.user
        )
        
        serializer = AllotmentItemSerializer(allocation)
        return Response(serializer.data, status=201)
        
    except ValidationError as e:
        return Response({'error': str(e)}, status=400)
```

### Example 2: Using Balance Calculator in Models

#### Integrating with Existing Models

```python
# license/models.py
from license.models_integration import LicenseBalanceMixin, LicenseItemBalanceMixin

class LicenseDetailsModel(AuditModel, LicenseBalanceMixin):
    # ... existing fields ...
    
    # The mixin provides these methods:
    # - get_balance_cif (property)
    # - get_restriction_balances()
    # - validate_active()
    # - update_status_flags()
    
    class Meta:
        ordering = ("license_expiry_date",)
    
    def __str__(self):
        return self.license_number


class LicenseImportItemsModel(AuditModel, LicenseItemBalanceMixin):
    # ... existing fields ...
    
    # The mixin provides these methods:
    # - get_balance_cif (property)
    # - available_quantity (property)
    # - balance_cif_fc (property)
    # - get_balance_components()
    # - calculate_max_allocation()
    
    class Meta:
        ordering = ("serial_number",)
```

### Example 3: Creating PDF Reports with Base Classes

#### Before (ledger_pdf.py)

```python
def generate_license_ledger_pdf(license_obj):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Manually create styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Manually build tables...
    # 200+ lines of table building code
```

#### After (using base classes)

```python
from core.exporters.pdf import BasePDFExporter, PDFConfig, PDFStyles
from core.exporters.pdf.table_builder import PDFTableBuilder, create_info_header_table

class LicenseLedgerPDF(BasePDFExporter):
    def __init__(self):
        config = PDFConfig(
            orientation='landscape',
            title='License Ledger'
        )
        super().__init__(config=config)
        self.styles = PDFStyles()
    
    def _add_content(self, license_obj):
        # Add title
        self.add_title(f"LICENSE LEDGER", self.styles.title)
        self.add_spacer(0.1)
        
        # Add license info using helper
        license_info = [
            ['License Number:', license_obj.license_number, 
             'License Date:', license_obj.license_date.strftime('%d-%b-%Y')],
            ['Exporter:', license_obj.exporter.name if license_obj.exporter else 'N/A',
             'Expiry Date:', license_obj.license_expiry_date.strftime('%d-%b-%Y')],
        ]
        info_table = create_info_header_table(license_info)
        self.add_table(info_table)
        self.add_spacer(0.3)
        
        # Add items table
        builder = PDFTableBuilder(styles=self.styles)
        builder.add_header_row(['Sr No', 'Description', 'Quantity', 'CIF FC', 'Balance'])
        
        for item in license_obj.import_license.all():
            builder.add_data_row([
                item.serial_number,
                item.description,
                f"{item.quantity:,.3f}",
                f"{item.cif_fc:,.2f}",
                f"{item.get_balance_cif:,.2f}"
            ], number_columns=[2, 3, 4])
        
        table = builder.build()
        self.add_table(table)


# Usage
def generate_license_ledger_pdf(license_obj):
    exporter = LicenseLedgerPDF()
    buffer = exporter.generate(license_obj)
    return buffer
```

### Example 4: Management Command Using Services

```python
# license/management/commands/check_licenses.py
from django.core.management.base import BaseCommand
from license.models import LicenseDetailsModel
from license.services.validation_service import LicenseValidationService

class Command(BaseCommand):
    help = 'Check and update license status flags'
    
    def handle(self, *args, **options):
        licenses = LicenseDetailsModel.objects.all()
        updated_count = 0
        
        for license in licenses:
            # Use service to update flags
            flags = LicenseValidationService.update_license_flags(license)
            
            # Apply flags to model
            for flag_name, flag_value in flags.items():
                setattr(license, flag_name, flag_value)
            
            license.save()
            updated_count += 1
            
            if not flags['is_active']:
                self.stdout.write(
                    self.style.WARNING(
                        f'License {license.license_number} is now inactive'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Updated {updated_count} licenses')
        )
```

---

## Frontend Integration

### Example 1: Refactoring AllotmentAction Component

#### Before (AllotmentAction.jsx - 803 lines)

```javascript
export default function AllotmentAction() {
    const {id} = useParams();
    
    // 9 useState hooks
    const [allotment, setAllotment] = useState(null);
    const [availableItems, setAvailableItems] = useState([]);
    const [allocationData, setAllocationData] = useState({});
    // ... 6 more useState hooks
    
    // 3 useEffect hooks for data fetching
    useEffect(() => { /* fetch notifications */ }, []);
    useEffect(() => { /* auto-set description */ }, [allotment]);
    useEffect(() => { /* debounced fetch */ }, [search, filters]);
    
    // Large inline functions
    const calculateMaxAllocation = (item) => {
        // 50+ lines of calculation logic
    };
    
    const handleQuantityChange = (itemId, qty) => {
        // 60+ lines of logic
    };
    
    // More inline functions...
    
    return (
        <div>
            {/* 400+ lines of JSX */}
        </div>
    );
}
```

#### After (using custom hook)

```javascript
import { useAllotmentAction } from '../hooks/allotment/useAllotmentAction';

export default function AllotmentAction() {
    const { id } = useParams();
    
    // Single hook encapsulates all logic
    const {
        allotment,
        availableItems,
        allocationData,
        initialLoading,
        tableLoading,
        search,
        filters,
        error,
        success,
        pagination,
        setSearch,
        updateFilter,
        handleQuantityChange,
        handleValueChange,
        handleAllocate,
        handleDelete,
        calculateMaxAllocation,
        isAllocating,
        isDeleting,
    } = useAllotmentAction(id);
    
    if (initialLoading) return <LoadingSpinner />;
    
    return (
        <div>
            <AllotmentHeader allotment={allotment} />
            
            <AllotmentFilters
                search={search}
                filters={filters}
                onSearchChange={setSearch}
                onFilterChange={updateFilter}
            />
            
            <AvailableLicensesTable
                items={availableItems}
                allocationData={allocationData}
                onQuantityChange={handleQuantityChange}
                onValueChange={handleValueChange}
                onAllocate={handleAllocate}
                onDelete={handleDelete}
                calculateMax={calculateMaxAllocation}
                isAllocating={isAllocating}
                isDeleting={isDeleting}
            />
            
            <Pagination {...pagination} />
        </div>
    );
}
```

### Example 2: Using Calculator Utilities

#### Before (inline calculations)

```javascript
const handleQuantityChange = (itemId, qty) => {
    const item = availableItems.find(i => i.id === itemId);
    const unitPrice = parseFloat(allotment.unit_value_per_unit);
    let inputQty = parseInt(qty) || 0;
    
    const balancedQty = parseInt(allotment.balanced_quantity || 0);
    const requiredValue = parseFloat(allotment.required_value || 0);
    const requiredValueWithBuffer = parseFloat(
        allotment.required_value_with_buffer || (requiredValue + 20)
    );
    const allottedValue = parseFloat(allotment.allotted_value || 0);
    const balancedValueWithBuffer = requiredValueWithBuffer - allottedValue;
    const availableCifFc = parseFloat(item.balance_cif_fc || 0);
    const availableQty = parseInt(item.available_quantity || 0);
    
    // Constrain to minimum
    if (inputQty > balancedQty) inputQty = balancedQty;
    if (inputQty > availableQty) inputQty = availableQty;
    
    let allocateCifFc = inputQty * unitPrice;
    
    if (allocateCifFc > balancedValueWithBuffer) {
        inputQty = Math.floor(balancedValueWithBuffer / unitPrice);
        allocateCifFc = inputQty * unitPrice;
    }
    
    if (allocateCifFc > availableCifFc) {
        inputQty = Math.floor(availableCifFc / unitPrice);
        allocateCifFc = inputQty * unitPrice;
    }
    
    // ... more logic
};
```

#### After (using calculator)

```javascript
import { allocationCalculator } from '../services/calculators';

const handleQuantityChange = (itemId, qty) => {
    const item = availableItems.find(i => i.id === itemId);
    
    // Calculate max with all constraints
    const max = allocationCalculator.calculateMaxAllocation(item, allotment);
    
    // Constrain input
    const constrainedQty = Math.min(parseInt(qty) || 0, max.qty);
    
    // Calculate value
    const value = allocationCalculator.calculateAllocationValue(
        constrainedQty,
        allotment.unit_value_per_unit
    );
    
    setAllocationData(prev => ({
        ...prev,
        [itemId]: { qty: constrainedQty, cif_fc: value }
    }));
};
```

### Example 3: Using API Services

#### Before (direct axios calls)

```javascript
const allocateItem = async (itemId) => {
    try {
        const response = await api.post(
            `/allotment-actions/${id}/allocate-item/`,
            {
                item_id: itemId,
                qty: allocationData[itemId].qty,
                cif_fc: allocationData[itemId].cif_fc
            }
        );
        
        if (response.status === 201) {
            setSuccess('Item allocated successfully');
            fetchData();
        }
    } catch (err) {
        setError(err.response?.data?.detail || 'Failed to allocate');
    }
};
```

#### After (using API service)

```javascript
import { allotmentApi } from '../services/api';

const allocateItem = async (itemId) => {
    try {
        await allotmentApi.allocateItem(
            id,
            itemId,
            allocationData[itemId]
        );
        
        setSuccess('Item allocated successfully');
        fetchData();
    } catch (err) {
        setError(err.response?.data?.detail || 'Failed to allocate');
    }
};
```

### Example 4: Using Master Form Hook

#### Before (MasterForm.jsx - 623 lines)

```javascript
function MasterForm({ endpoint, recordId }) {
    const [formData, setFormData] = useState({});
    const [metadata, setMetadata] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [errors, setErrors] = useState({});
    
    useEffect(() => {
        fetchMetadata();
        if (recordId) fetchRecord();
    }, []);
    
    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
        
        // Auto-calculate registration number
        if (field === 'license_number') {
            const regNumber = value.split('/')[0];
            setFormData(prev => ({ ...prev, registration_number: regNumber }));
        }
        
        // Auto-calculate dates
        if (field === 'license_date') {
            const expiryDate = new Date(value);
            expiryDate.setMonth(expiryDate.getMonth() + 12);
            setFormData(prev => ({ 
                ...prev, 
                license_expiry_date: expiryDate.toISOString().split('T')[0]
            }));
        }
        
        // ... more auto-calculation logic
    };
    
    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        // ... save logic
    };
    
    // ... 500+ more lines
}
```

#### After (using custom hook)

```javascript
import { useMasterForm } from '../hooks/masters/useMasterForm';

function MasterForm({ endpoint, recordId }) {
    const {
        formData,
        metadata,
        loading,
        saving,
        errors,
        isDirty,
        handleChange,
        handleSubmit,
        resetForm,
        getFieldError,
        isFieldRequired,
    } = useMasterForm(endpoint, recordId, {
        enableAutoCalculation: true,
        onSuccess: (data) => {
            navigate(`/${endpoint}${data.id}/`);
        }
    });
    
    if (loading) return <LoadingSpinner />;
    
    return (
        <form onSubmit={handleSubmit}>
            {Object.entries(metadata?.actions?.POST || {}).map(([fieldName, fieldMeta]) => (
                <FormField
                    key={fieldName}
                    name={fieldName}
                    value={formData[fieldName]}
                    metadata={fieldMeta}
                    error={getFieldError(fieldName)}
                    required={isFieldRequired(fieldName)}
                    onChange={(value) => handleChange(fieldName, value)}
                />
            ))}
            
            <button type="submit" disabled={saving || !isDirty}>
                {saving ? 'Saving...' : 'Save'}
            </button>
        </form>
    );
}
```

---

## Complete Examples

### Full Allotment Workflow

```javascript
// AllotmentActionPage.jsx
import React from 'react';
import { useParams } from 'react-router-dom';
import { useAllotmentAction } from '../hooks/allotment/useAllotmentAction';
import AllotmentHeader from '../components/allotment/AllotmentHeader';
import AllotmentFilters from '../components/allotment/AllotmentFilters';
import AvailableLicensesTable from '../components/allotment/AvailableLicensesTable';
import Pagination from '../components/common/Pagination';
import ErrorAlert from '../components/common/ErrorAlert';
import SuccessAlert from '../components/common/SuccessAlert';

export default function AllotmentActionPage() {
    const { id } = useParams();
    const {
        allotment,
        availableItems,
        allocationData,
        initialLoading,
        tableLoading,
        search,
        filters,
        error,
        success,
        pagination,
        setSearch,
        updateFilter,
        clearFilters,
        handleQuantityChange,
        handleValueChange,
        handleAllocate,
        handleDelete,
        calculateMaxAllocation,
        isAllocating,
        isDeleting,
    } = useAllotmentAction(id);

    if (initialLoading) {
        return <div className="loading">Loading allotment data...</div>;
    }

    return (
        <div className="allotment-action-page">
            {error && <ErrorAlert message={error} />}
            {success && <SuccessAlert message={success} />}
            
            <AllotmentHeader allotment={allotment} />
            
            <AllotmentFilters
                search={search}
                filters={filters}
                onSearchChange={setSearch}
                onFilterChange={updateFilter}
                onClearFilters={clearFilters}
            />
            
            {tableLoading ? (
                <div className="loading">Loading items...</div>
            ) : (
                <AvailableLicensesTable
                    items={availableItems}
                    allocationData={allocationData}
                    onQuantityChange={handleQuantityChange}
                    onValueChange={handleValueChange}
                    onAllocate={handleAllocate}
                    onDelete={handleDelete}
                    calculateMax={calculateMaxAllocation}
                    isAllocating={isAllocating}
                    isDeleting={isDeleting}
                />
            )}
            
            <Pagination
                currentPage={pagination.currentPage}
                totalPages={pagination.totalPages}
                onPageChange={pagination.goToPage}
                onNext={pagination.nextPage}
                onPrev={pagination.prevPage}
            />
        </div>
    );
}
```

---

## Testing Examples

### Backend Service Tests

```python
# tests/test_balance_calculator.py
import pytest
from decimal import Decimal
from license.services.balance_calculator import LicenseBalanceCalculator
from license.tests.factories import LicenseFactory, ExportItemFactory

@pytest.mark.django_db
class TestLicenseBalanceCalculator:
    
    def test_calculate_credit(self):
        license = LicenseFactory()
        ExportItemFactory(license=license, cif_fc=Decimal('1000.00'))
        ExportItemFactory(license=license, cif_fc=Decimal('2000.00'))
        
        credit = LicenseBalanceCalculator.calculate_credit(license)
        
        assert credit == Decimal('3000.00')
    
    def test_calculate_balance(self):
        license = LicenseFactory()
        ExportItemFactory(license=license, cif_fc=Decimal('5000.00'))
        
        # Add some debits (BOE entries)
        # ... create test data
        
        balance = LicenseBalanceCalculator.calculate_balance(license)
        
        assert balance >= Decimal('0')
```

### Frontend Hook Tests

```javascript
// hooks/__tests__/useAllotmentAction.test.js
import { renderHook, act } from '@testing-library/react-hooks';
import { useAllotmentAction } from '../allotment/useAllotmentAction';
import * as allotmentApi from '../../services/api/allotmentApi';

jest.mock('../../services/api/allotmentApi');

describe('useAllotmentAction', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });
    
    it('fetches allotment data on mount', async () => {
        const mockData = {
            allotment: { id: 1, item_name: 'Sugar' },
            available_items: [],
            count: 0
        };
        
        allotmentApi.fetchAvailableLicenses.mockResolvedValue(mockData);
        
        const { result, waitForNextUpdate } = renderHook(() => 
            useAllotmentAction(1)
        );
        
        await waitForNextUpdate();
        
        expect(result.current.allotment).toEqual(mockData.allotment);
        expect(result.current.initialLoading).toBe(false);
    });
    
    it('calculates max allocation correctly', () => {
        const { result } = renderHook(() => useAllotmentAction(1));
        
        act(() => {
            result.current.allotment = {
                unit_value_per_unit: 10,
                balanced_quantity: 100,
                required_value: 1000
            };
        });
        
        const item = {
            available_quantity: 50,
            balance_cif_fc: 500
        };
        
        const max = result.current.calculateMaxAllocation(item);
        
        expect(max.qty).toBe(50);
        expect(max.value).toBe(500);
    });
});
```

---

## Summary

The modular refactoring enables:

1. **Backend**: Clean separation of business logic into services
2. **Frontend**: Reusable hooks and utilities
3. **Testing**: Easier to test individual modules
4. **Maintenance**: Clear responsibility boundaries
5. **Scalability**: Easy to extend and modify

All examples maintain backward compatibility while providing cleaner, more maintainable code.
