# Serializer Field Fixes

**Date:** November 19, 2025
**Status:** ✅ FIXED

## Issues Fixed

### Issue 1: Incorrect Audit Field Names
**Error:** `ImproperlyConfigured: Field name 'created_at' is not valid`

**Location:** `backend/bill_of_entry/serializers.py`

**Problem:**
```python
# Wrong field names
fields = [..., 'created_at', 'updated_at']
```

**Fix:**
```python
# Correct field names (matching AuditModel)
fields = [..., 'created_on', 'modified_on', 'created_by', 'modified_by']
read_only_fields = ['created_on', 'modified_on', 'created_by', 'modified_by']
```

**Root Cause:**
`BillOfEntryModel` extends `AuditModel` which provides `created_on` and `modified_on` (not `created_at`/`updated_at`)

---

### Issue 2: Non-existent Allotment Fields
**Error:** `AttributeError: 'AllotmentModel' object has no attribute 'allotment_no'`

**Location:** `backend/bill_of_entry/serializers.py` - `to_representation()` method

**Problem:**
```python
# Wrong - these fields don't exist on AllotmentModel
representation['allotments'] = [
    {
        'id': allot.id,
        'allotment_no': allot.allotment_no,        # ❌ Doesn't exist
        'allotment_date': allot.allotment_date,    # ❌ Doesn't exist
    }
    for allot in allotments
]
```

**Fix:**
```python
# Correct - using actual AllotmentModel fields
representation['allotments'] = [
    {
        'id': allot.id,
        'item_name': allot.item_name,              # ✅ Exists
        'invoice': allot.invoice,                   # ✅ Exists
        'required_quantity': str(allot.required_quantity),  # ✅ Exists
        'estimated_arrival_date': allot.estimated_arrival_date,  # ✅ Exists
        'company': allot.company.name if allot.company else None,  # ✅ Exists
    }
    for allot in allotments
]
```

**Root Cause:**
`AllotmentModel` doesn't have `allotment_no` or `allotment_date` fields. It has:
- `item_name` - Name of the item
- `invoice` - Invoice number
- `required_quantity` - Required quantity
- `estimated_arrival_date` - Estimated arrival date
- `company` - Company FK

---

## AllotmentModel Actual Fields

For reference, here are the actual fields available on `AllotmentModel`:

### Data Fields:
- `id` - Primary key
- `company` - ForeignKey to CompanyModel
- `type` - CharField (row type)
- `required_quantity` - DecimalField
- `unit_value_per_unit` - DecimalField
- `cif_fc` - DecimalField (CIF foreign currency)
- `cif_inr` - DecimalField (CIF in INR)
- `exchange_rate` - DecimalField
- `item_name` - CharField ✅
- `contact_person` - CharField
- `contact_number` - CharField
- `invoice` - CharField ✅
- `estimated_arrival_date` - DateField ✅
- `bl_detail` - CharField (Bill of Lading details)
- `port` - ForeignKey to PortModel
- `related_company` - ForeignKey to CompanyModel
- `is_boe` - BooleanField
- `is_allotted` - BooleanField

### Audit Fields (from AuditModel):
- `created_on` - DateTimeField ✅
- `created_by` - ForeignKey to User
- `modified_on` - DateTimeField ✅
- `modified_by` - ForeignKey to User

### Computed Properties:
- `required_value` - Calculated from quantity × unit_value
- `dfia_list` - Comma-separated DFIA numbers
- `balanced_quantity` - Remaining quantity after allocation
- `alloted_quantity` - Total allocated quantity
- `allotted_value` - Total allocated value

---

## Verification

### Test Commands:

```bash
# Test serializer import
python manage.py shell -c "from bill_of_entry.serializers import BillOfEntrySerializer; print('✓ Import successful')"

# Test API endpoint
curl http://localhost:8000/api/bill-of-entries/?page=1&page_size=25

# Or with authentication
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/bill-of-entries/
```

### Validation Results:

```
✓ BillOfEntrySerializer instantiated successfully
✓ Total fields: 27
✓ Has created_on: True
✓ Has modified_on: True
✓ Can serialize empty queryset
✅ All serializer checks passed!
```

---

## Common Model Field Patterns

### AuditModel Fields (Inherited):
```python
class MyModel(AuditModel):
    # Your fields here
    pass

# Automatically includes:
# - created_on (DateTimeField)
# - created_by (ForeignKey)
# - modified_on (DateTimeField)
# - modified_by (ForeignKey)
```

### Common Allotment Patterns:
```python
# Getting allotment data
allotment = AllotmentModel.objects.get(id=1)

# Available fields
allotment.item_name           # Item name
allotment.invoice             # Invoice number
allotment.required_quantity   # Required quantity
allotment.estimated_arrival_date  # ETA
allotment.company.name        # Company name
allotment.is_boe              # Is BOE?
allotment.is_allotted         # Is allotted?

# Computed properties
allotment.required_value      # Calculated value
allotment.dfia_list           # DFIA list
allotment.balanced_quantity   # Remaining quantity
```

---

## Best Practices

### 1. Always Check Model Fields First
Before accessing fields in serializers, verify they exist:

```bash
python manage.py shell -c "
from myapp.models import MyModel
print([f.name for f in MyModel._meta.get_fields()])
"
```

### 2. Use Actual Field Names
Don't assume field names. Check the model definition:
- ✅ Use `item_name` (actual field)
- ❌ Don't use `allotment_no` (doesn't exist)

### 3. Handle Null Foreign Keys
Always check if FK is None before accessing related fields:

```python
# Good
'company': allot.company.name if allot.company else None

# Bad (will error if company is None)
'company': allot.company.name
```

### 4. Use Audit Field Standard Names
- ✅ `created_on`, `modified_on`, `created_by`, `modified_by`
- ❌ `created_at`, `updated_at`, `creator`, `updater`

---

## Related Documentation

- **AUDIT_FIELDS_REFERENCE.md** - Complete audit field guide
- **FIELD_VALIDATION_REPORT.md** - Field validation results
- **DATABASE_SYNC_COMPLETE.md** - Database synchronization status

---

## Status: ✅ ALL FIXED

Both issues have been resolved:
1. ✅ Audit field names corrected (`created_on`/`modified_on`)
2. ✅ Allotment field names corrected (using actual model fields)

The API endpoint `/api/bill-of-entries/` should now work without errors.
