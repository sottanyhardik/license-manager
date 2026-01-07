# Fix: Add Ordering to Models to Prevent Pagination Warnings

## Problem
Django shows warnings: `UnorderedObjectListWarning: Pagination may yield inconsistent results with an unordered object_list`

## Solution
Add `ordering` in `Meta` class for all models without explicit ordering.

## Models to Fix

### ✅ FIXED
1. **core.TransferLetterModel** - Added `ordering = ['name', 'id']`

### Needs Fixing

#### core/models.py (10 models)
2. **ItemHeadModel** (line 162) - Add: `ordering = ['name', 'id']`
3. **HeadSIONNormsModel** (line 266) - Add: `ordering = ['head', 'sion_norm', 'id']`
4. **SionNormClassModel** (line 273) - Add: `ordering = ['norm_class', 'id']`
5. **SIONExportModel** (line 286) - Add: `ordering = ['id']`
6. **ProductDescriptionModel** (line 353) - Add: `ordering = ['hs_code', 'id']`
7. **UnitPriceModel** (line 372) - Add: `ordering = ['name', 'id']`
8. **InvoiceEntity** (line 392) - Add: `ordering = ['name', 'id']`
9. **SchemeCode** (line 422) - Add: `ordering = ['id']`
10. **NotificationNumber** (line 430) - Add: `ordering = ['id']`
11. **PurchaseStatus** (line 438) - Add: `ordering = ['id']`

#### license/models.py (10 models)
12. **AlongWithModel** - Add: `ordering = ['id']`
13. **DateModel** - Add: `ordering = ['date', 'id']`
14. **Invoice** - Add: `ordering = ['-invoice_date', 'invoice_number', 'id']`
15. **InvoiceItem** - Add: `ordering = ['invoice', 'id']`
16. **LicenseDocumentModel** - Add: `ordering = ['license', 'type', 'id']`
17. **LicenseExportItemModel** - Add: `ordering = ['license', 'serial_number', 'id']`
18. **LicenseInwardOutwardModel** - Add: `ordering = ['license', '-date', 'id']`
19. **LicenseTransferModel** - Add: `ordering = ['license', '-created_on', 'id']`
20. **OfficeModel** - Add: `ordering = ['name', 'id']`
21. **StatusModel** - Add: `ordering = ['name', 'id']`

#### accounts/models.py (1 model)
22. **User** - Add: `ordering = ['username', 'id']`

## Implementation

Add a `Meta` class (or update existing) with `ordering` attribute:

```python
class Meta:
    ordering = ['field1', 'field2', 'id']  # Always include 'id' as last resort
```

## Notes
- Always include `'id'` as the last field to ensure consistent ordering
- Use descending order with `-` prefix where appropriate (e.g., `-created_on` for newest first)
- Choose fields that make semantic sense for the model
