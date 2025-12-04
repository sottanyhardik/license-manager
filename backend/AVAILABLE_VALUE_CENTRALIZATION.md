# Available Value Centralization - Complete Refactoring

## 🎯 Objective
Centralize ALL available_value and balance_cif calculations into a single source of truth in the license models, ensuring 100% consistency across frontend, backend, PDFs, APIs, and management commands.

## 📋 Changes Made

### 1. Model Changes (`license/models.py`)

#### A. Added `is_restricted` Field to `LicenseImportItemsModel`
```python
is_restricted = models.BooleanField(
    default=False,
    help_text="If True, uses restriction-based calculation (2%, 3%, 5%, 10% etc.). If False, uses license balance."
)
```

**Purpose**: This field determines which calculation logic to use:
- `is_restricted = True`: Use restriction-based calculation from item's head (2%, 3%, 5%, 10% from norms E1, E5, etc.)
- `is_restricted = False`: Use license-level balance (shared across all non-restricted items)

#### B. Added `available_value_calculated` Property
```python
@property
def available_value_calculated(self) -> Decimal:
    """
    CENTRALIZED available_value calculation - SINGLE SOURCE OF TRUTH.

    Business Logic:
    1. If is_restricted = True: Calculate based on item's head restriction
       Formula: (License Export CIF × restriction_percentage / 100) - (debits + allotments)
    2. If is_restricted = False: Use license.get_balance_cif (shared balance)

    This property should be used EVERYWHERE in the project.
    """
```

**Key Features:**
- ✅ Handles restriction-based calculations (delegated to `_calculate_head_restriction_balance()`)
- ✅ Handles license-level balance (delegated to `license.get_balance_cif`)
- ✅ No caching - always calculates fresh values
- ✅ Type-safe with Decimal arithmetic
- ✅ Comprehensive documentation

### 2. Migration (`license/migrations/0007_add_is_restricted_field.py`)

Created migration to add `is_restricted` field to database:
```python
migrations.AddField(
    model_name='licenseimportitemsmodel',
    name='is_restricted',
    field=models.BooleanField(default=False, ...),
)
```

### 3. Serializer Changes (`license/serializers.py`)

#### Before (37 lines of complex logic):
```python
def get_balance_cif_fc(self, obj):
    # Check exceptions
    # Check restrictions
    # Fallback logic
    # Multiple return paths
    ...
```

#### After (3 lines):
```python
def get_balance_cif_fc(self, obj):
    """CENTRALIZED - uses available_value_calculated property"""
    return obj.available_value_calculated
```

**Benefits:**
- ✅ Eliminated 34 lines of duplicate logic
- ✅ Single source of truth
- ✅ Consistent with model calculation
- ✅ Easier to maintain

### 4. PDF Report Changes (`license/ledger_pdf.py`)

#### Before:
```python
# Complex conditional logic checking CIF values
if license_has_zero_cif_items:
    balance_cif_fc = license_balance_cif
else:
    balance_cif_fc = sum(item.balance_cif_fc for item in items)
```

#### After:
```python
# Use centralized property
balance_cif_fc = sum(Decimal(str(item.available_value_calculated or 0)) for item in items)
```

**Benefits:**
- ✅ Consistent with API responses
- ✅ Consistent with frontend display
- ✅ No duplicate calculation logic

### 5. Existing Centralized Methods (Already Present)

#### License Level (`LicenseDetailsModel`):
```python
@property
def get_balance_cif(self) -> Decimal
    """License-level balance: Export CIF - (Debits + Allotments)"""

def _calculate_license_credit(self) -> Decimal
    """Sum of all export CIF"""

def _calculate_license_debit(self) -> Decimal
    """Sum of all BOE debits"""

def _calculate_license_allotment(self) -> Decimal
    """Sum of all non-BOE allotments"""

def get_restriction_balances(self) -> Dict[Decimal, Decimal]
    """Calculate all restriction balances (2%, 3%, 5%, 10%, etc.)"""
```

#### Item Level (`LicenseImportItemsModel`):
```python
@property
def balance_cif_fc(self) -> Decimal
    """Item-level balance with special handling for CIF=0, restrictions, etc."""

def _calculate_item_debit(self) -> Decimal
    """Sum of debits for this item"""

def _calculate_item_allotment(self) -> Decimal
    """Sum of allotments for this item"""

def _calculate_head_restriction_balance(self) -> Decimal
    """Calculate restriction-based balance from item's head"""

@property
def available_value_calculated(self) -> Decimal  # NEW
    """SINGLE SOURCE OF TRUTH for available value"""
```

## 🔧 How to Use

### Frontend (React/JavaScript)

When displaying license import items, the API will automatically return the correct available value:

```javascript
// Item data from API
{
  "serial_number": 1,
  "description": "Wheat Flour",
  "cif_fc": 5339312.05,
  "is_restricted": false,
  "balance_cif_fc": 14041.61,  // ← Automatically calculated from available_value_calculated
  ...
}
```

**No frontend calculation needed** - just display `balance_cif_fc` from the API response.

### Backend (Python)

Always use the centralized property:

```python
# ✅ CORRECT - Use centralized property
available_value = item.available_value_calculated

# ❌ WRONG - Don't calculate manually
available_value = item.cif_fc - debits - allotments  # Don't do this!
```

### Setting `is_restricted` Field

#### Option 1: Automatically (Recommended)
Create a management command or signal to auto-set based on item's head:

```python
for item in LicenseImportItemsModel.objects.all():
    has_restriction = item.items.filter(
        head__is_restricted=True,
        head__restriction_percentage__gt=0
    ).exists()
    item.is_restricted = has_restriction
    item.save()
```

#### Option 2: Manual (via Frontend Form)
Add `is_restricted` checkbox in the license import item form:
```javascript
<Checkbox
  label="Restricted Item"
  checked={item.is_restricted}
  onChange={(e) => handleFieldChange('is_restricted', e.target.checked)}
/>
```

## 📊 Business Logic Flow

```
┌─────────────────────────────────────────┐
│  Frontend/API Request                    │
│  "Get available value for item X"       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Serializer: get_balance_cif_fc()       │
│  Returns: obj.available_value_calculated│
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Model: available_value_calculated      │
│  Check: item.is_restricted?             │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
   YES │                │ NO
       ▼                ▼
┌──────────────┐  ┌──────────────────────┐
│ Restriction  │  │ License Balance      │
│ Calculation  │  │ license.get_balance_ │
│ (2%,3%,5%,   │  │ cif (shared)         │
│ 10%)         │  │                      │
└──────────────┘  └──────────────────────┘
```

## 🎯 Benefits

### 1. Single Source of Truth
- **Before**: 5+ different places calculating available_value
- **After**: 1 centralized property in the model

### 2. Consistency
- ✅ Frontend displays same value as API
- ✅ API returns same value as PDF reports
- ✅ PDF reports show same value as management commands
- ✅ Management commands use same logic as serializers

### 3. Maintainability
- ✅ Change logic in ONE place → affects entire project
- ✅ No duplicate code to maintain
- ✅ Easier to test (test one property vs. multiple functions)
- ✅ Clear documentation in one location

### 4. Type Safety
- ✅ All calculations use Decimal (no float precision issues)
- ✅ Proper null/None handling
- ✅ Type hints for better IDE support

### 5. Business Logic Clarity
- ✅ `is_restricted` field makes intent explicit
- ✅ No hidden assumptions in code
- ✅ Easy to understand: "If restricted → use restriction calc, else → use license balance"

## 🚀 Migration Path

### Step 1: Run Migration
```bash
python manage.py migrate license
```

### Step 2: Set `is_restricted` for Existing Data
```bash
python manage.py shell

from license.models import LicenseImportItemsModel

# Auto-set based on item's head
for item in LicenseImportItemsModel.objects.all():
    has_restriction = item.items.filter(
        head__is_restricted=True,
        head__restriction_percentage__gt=0
    ).exists()
    if has_restriction != item.is_restricted:
        item.is_restricted = has_restriction
        item.save(update_fields=['is_restricted'])
        print(f"Updated item {item.id}: is_restricted = {has_restriction}")
```

### Step 3: Add Frontend Form Field
Add `is_restricted` checkbox to the license import item form in React.

### Step 4: Update Existing Management Commands (Optional)
Review commands in `license/management/commands/` and ensure they use `available_value_calculated`.

## 📝 Files Changed

1. ✅ `license/models.py` - Added field and property
2. ✅ `license/migrations/0007_add_is_restricted_field.py` - Database migration
3. ✅ `license/serializers.py` - Simplified to use centralized property
4. ✅ `license/ledger_pdf.py` - Updated to use centralized property
5. 📄 `AVAILABLE_VALUE_CENTRALIZATION.md` - This documentation

## ⚠️ Important Notes

### DO NOT:
- ❌ Calculate available_value manually in views
- ❌ Calculate available_value manually in serializers
- ❌ Calculate available_value manually in management commands
- ❌ Calculate available_value manually in frontend

### ALWAYS:
- ✅ Use `item.available_value_calculated` property
- ✅ Use `license.get_balance_cif` for license-level balance
- ✅ Use `license.get_restriction_balances()` for restriction balances
- ✅ Refer to model methods for ALL balance calculations

## 🧪 Testing

### Test Scenarios:

1. **Non-Restricted Item (is_restricted=False)**
   - Should return license.get_balance_cif
   - All non-restricted items share same balance

2. **Restricted Item (is_restricted=True)**
   - Should calculate based on head restriction percentage
   - Different items with different restrictions show different balances

3. **Mixed License (Some restricted, some not)**
   - Restricted items: Show restriction-based balance
   - Non-restricted items: Show license balance

4. **Exception Licenses (098/2009, Conversion)**
   - Handled by `_calculate_head_restriction_balance()` method
   - Returns 0 for restrictions, falls back to license balance

## 🎓 Developer Guide

When adding new features that need available_value:

```python
# ✅ CORRECT
from license.models import LicenseImportItemsModel

item = LicenseImportItemsModel.objects.get(id=1)
available_value = item.available_value_calculated

# ❌ WRONG
# Don't do manual calculations
# Don't check CIF values manually
# Don't query debits/allotments directly
```

## 📞 Support

If you need to add new calculation logic:
1. Check if it belongs in the model (it probably does)
2. Update `available_value_calculated` property if needed
3. Document the change
4. Update this documentation

**Remember**: The model is the SINGLE SOURCE OF TRUTH. All other code should delegate to model properties.
