# Purchase Status FK Migration Guide

## Overview
Major change to convert `purchase_status` from CharField with choices to ForeignKey to `PurchaseStatus` model.

## Migrations Created

### 1. Core Migrations
- `0028_add_fields_to_purchase_status.py` - Adds `is_active` and `display_order` fields to PurchaseStatus
- `0029_populate_purchase_status_data.py` - Populates PurchaseStatus table with data from LICENCE_PURCHASE_CHOICES_FULL

### 2. License Migrations
- `0016_change_purchase_status_to_fk.py` - Converts purchase_status from CharField to ForeignKey

## Model Changes

### core/models.py
- ✅ Updated `PurchaseStatus` model with `is_active` and `display_order` fields

### license/models.py
- ✅ Updated `LicenseDetailsModel.purchase_status` from CharField to ForeignKey

## Changes Required

### 1. Serializers (CRITICAL)

All serializers that reference `purchase_status` need updates:

**Pattern Change:**
```python
# OLD:
purchase_status = serializers.CharField()

# NEW:
purchase_status = serializers.PrimaryKeyRelatedField(
    queryset=PurchaseStatus.objects.filter(is_active=True),
    required=False
)
purchase_status_display = serializers.SerializerMethodField()

def get_purchase_status_display(self, obj):
    return {
        'code': obj.purchase_status.code if obj.purchase_status else None,
        'label': obj.purchase_status.label if obj.purchase_status else None
    }
```

**Files to Update:**
- `license/serializers.py` - LicenseDetailsSerializer
- `allotment/serializers.py` - References to license.purchase_status
- `bill_of_entry/serializers.py` - References to license.purchase_status

### 2. Filters and Queries (CRITICAL)

All filter queries need to be updated:

**Pattern Changes:**
```python
# OLD:
queryset.filter(purchase_status='GE')
queryset.filter(purchase_status__in=['GE', 'MI', 'IP'])
queryset.exclude(purchase_status='LM')

# NEW:
queryset.filter(purchase_status__code='GE')
queryset.filter(purchase_status__code__in=['GE', 'MI', 'IP'])
queryset.exclude(purchase_status__code='LM')

# OLD comparison:
if license.purchase_status == GE:

# NEW comparison:
if license.purchase_status and license.purchase_status.code == GE:
```

**Files to Update (25 files identified):**

1. **license/views/license.py**
   - Line 312-328: Filter handling for purchase_status
   - Update to use `purchase_status__code`

2. **license/views/item_pivot_report.py**
   - Update filter queries

3. **license/utils/query_builder.py**
   - Update query builder logic

4. **license/views/item_report.py**
   - Update filter queries

5. **license/services/report_service.py**
   - Lines 28, 105, 114, 202, 211, 221: Update parameter handling
   - Change `purchase_status: str` to work with FK

6. **license/item_report_refactored.py**
   - Lines 30, 49, 128, 135: Update purchase_status parameters

7. **license/item_report.py**
   - Line 17: Update function signature

8. **license/services/validation_service.py**
   - Lines 37, 306: Change `license_obj.purchase_status != GE` to `license_obj.purchase_status.code != GE`

9. **license/views/expiring_licenses_report.py**
   - Line 74: Change `purchase_status__in=[GE, MI, IP, SM]` to `purchase_status__code__in=[GE, MI, IP, SM]`

10. **license/views/license_report.py**
    - Update filter queries

11. **license/views/active_licenses_report.py**
    - Update filter queries

12. **allotment/serializers.py**
    - Update references to license.purchase_status

13. **allotment/views_actions.py**
    - Update filter queries

14. **bill_of_entry/serializers.py**
    - Update references to license.purchase_status

15. **bill_of_entry/views/transfer_views.py**
    - Update filter queries

16. **bill_of_entry/scripts/generate_tl.py**
    - Update filter queries

17. **core/utils/transfer_letter.py**
    - Update filter queries

18. **core/management/commands/sync_from_ge_server.py**
    - Update filter queries

19. **allotment/scripts/aro.py**
    - Update filter queries

20. **license/ledger_pdf.py**
    - Update references

### 3. Views Metadata (Frontend Compatibility)

Update views that provide filter metadata:

**license/views/license.py** - Line 77:
```python
# OLD:
"purchase_status": {"type": "choice", "choices": list(LICENCE_PURCHASE_CHOICES_ACTIVE)},

# NEW:
"purchase_status": {
    "type": "foreign_key",
    "endpoint": "masters/purchase-statuses/",
    "label_field": "label",
    "value_field": "id",
    "filter_params": {"is_active": True}
},
```

### 4. Frontend Changes

**If using AsyncSelectField:**
- Update purchase_status to use AsyncSelectField pointing to `masters/purchase-statuses/`
- Filter by `is_active=true`

**If using regular select:**
- Fetch from API: `/api/masters/purchase-statuses/?is_active=true`
- Use `id` as value, `label` as display text

### 5. API Endpoints

Create new endpoint for PurchaseStatus:

**core/views.py** or **masters/views.py**:
```python
class PurchaseStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PurchaseStatus.objects.all()
    serializer_class = PurchaseStatusSerializer
    filterset_fields = ['is_active', 'code']
    ordering_fields = ['display_order', 'label']
    ordering = ['display_order']
```

**Register in urls.py**:
```python
router.register(r'purchase-statuses', PurchaseStatusViewSet, basename='purchase-status')
```

## Testing Checklist

### Backend Tests
- [ ] Test license creation with purchase_status FK
- [ ] Test license update with purchase_status FK
- [ ] Test all filter queries with `purchase_status__code`
- [ ] Test serializer read/write operations
- [ ] Test report generation with purchase_status filters
- [ ] Test allotment actions with purchase_status filters
- [ ] Test BOE with purchase_status filters

### Frontend Tests
- [ ] Test license list filtering by purchase status
- [ ] Test license create/edit form
- [ ] Test allotment action filtering
- [ ] Test reports with purchase status filters
- [ ] Test item pivot report
- [ ] Test item report

### Migration Tests
- [ ] Run migrations on test database
- [ ] Verify data migration completed successfully
- [ ] Verify all existing purchase_status values converted to FKs
- [ ] Test rollback if needed

## Rollback Plan

If migration fails or causes issues:

1. Revert model changes in `license/models.py` and `core/models.py`
2. Delete migration files:
   - `core/migrations/0028_*.py`
   - `core/migrations/0029_*.py`
   - `license/migrations/0016_*.py`
3. Run `python manage.py migrate` to rollback
4. Restore from database backup if needed

## Migration Order

1. Apply core migrations first:
   ```bash
   python manage.py migrate core 0028
   python manage.py migrate core 0029
   ```

2. Apply license migration:
   ```bash
   python manage.py migrate license 0016
   ```

3. Update code (serializers, filters, views)

4. Test thoroughly

5. Deploy to production

## Performance Considerations

- Added index on `purchase_status` FK in License model (already exists in Meta.indexes)
- Added ordering in PurchaseStatus model for efficient dropdown queries
- Consider select_related('purchase_status') in list queries
- Use prefetch_related for bulk operations

## Notes

- `PROTECT` on_delete ensures you cannot delete a PurchaseStatus if it's referenced by licenses
- Existing code using constants (GE, MI, etc.) will need to be updated to use `.code` attribute
- Default purchase_status is now `null=True`, ensure proper handling in forms
- Consider adding a default PurchaseStatus in model or through application logic
