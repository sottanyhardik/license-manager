# Purchase Status FK Migration - Completion Summary

## ✅ COMPLETED TASKS

### 1. Database Model Changes
- [x] Updated `PurchaseStatus` model in `core/models.py` with `is_active` and `display_order` fields
- [x] Updated `LicenseDetailsModel.purchase_status` in `license/models.py` from CharField to ForeignKey
- [x] Created migration `core/0028_add_fields_to_purchase_status.py`
- [x] Created data migration `core/0029_populate_purchase_status_data.py`
- [x] Created migration `license/0016_change_purchase_status_to_fk.py`

### 2. API Endpoint
- [x] Created `PurchaseStatusSerializer` in `core/serializers.py`
- [x] Created `PurchaseStatusViewSet` in `core/views/views.py`
- [x] Registered API endpoint `/api/masters/purchase-statuses/` in `core/urls.py`

### 3. Frontend Integration
- [x] Updated `license/views/license.py` line 77 - filter config to use FK endpoint
- [x] Updated `license/views/license.py` lines 139-144 - field_meta to use FK endpoint
- [x] Frontend MasterForm will automatically render AsyncSelectField for FK fields

## ⚠️ CRITICAL - REMAINING WORK

This is a **MAJOR BREAKING CHANGE**. The following must be completed before deployment:

### 1. Update ALL Filter Queries (25+ files)

**Pattern to find and fix:**
```python
# OLD - Will break after migration:
.filter(purchase_status='GE')
.filter(purchase_status__in=['GE', 'MI'])
if license.purchase_status == GE:

# NEW - Required pattern:
.filter(purchase_status__code='GE')
.filter(purchase_status__code__in=['GE', 'MI'])
if license.purchase_status and license.purchase_status.code == GE:
```

**Files that MUST be updated (identified via grep):**

1. **license/views/license.py** (Lines 312-328)
   - Update filter handling for purchase_status

2. **license/services/validation_service.py** (Lines 37, 306)
   - Change `license_obj.purchase_status != GE` to `license_obj.purchase_status.code != GE`

3. **license/services/report_service.py** (Lines 28, 105, 114, 202, 211, 221)
   - Update purchase_status parameter handling

4. **license/views/expiring_licenses_report.py** (Line 74)
   - Change `purchase_status__in=[GE, MI, IP, SM]` to `purchase_status__code__in=`

5. **license/views/item_pivot_report.py**
6. **license/utils/query_builder.py**
7. **license/views/item_report.py**
8. **license/item_report_refactored.py**
9. **license/item_report.py**
10. **license/views/license_report.py**
11. **license/views/active_licenses_report.py**
12. **license/ledger_pdf.py**
13. **allotment/serializers.py**
14. **allotment/views_actions.py**
15. **allotment/scripts/aro.py**
16. **bill_of_entry/serializers.py**
17. **bill_of_entry/views/transfer_views.py**
18. **bill_of_entry/scripts/generate_tl.py**
19. **core/utils/transfer_letter.py**
20. **core/management/commands/sync_from_ge_server.py**

### 2. Update Serializers

**license/serializers.py - LicenseDetailsSerializer:**
```python
# Add to serializer:
purchase_status = serializers.PrimaryKeyRelatedField(
    queryset=PurchaseStatus.objects.filter(is_active=True),
    required=False,
    allow_null=True
)
purchase_status_code = serializers.SerializerMethodField()
purchase_status_label = serializers.SerializerMethodField()

def get_purchase_status_code(self, obj):
    return obj.purchase_status.code if obj.purchase_status else None

def get_purchase_status_label(self, obj):
    return obj.purchase_status.label if obj.purchase_status else None
```

### 3. Update Default Filters

**license/views/license.py line 87:**
```python
# OLD:
"purchase_status": "GE,NP,SM,CO"

# NEW: Need to fetch IDs from PurchaseStatus table or change to code-based filtering
# Option 1: Use codes with modified filter logic
"purchase_status__code__in": "GE,NP,SM,CO"

# Option 2: Pre-fetch IDs (more efficient)
default_ps_ids = ','.join(str(ps.id) for ps in PurchaseStatus.objects.filter(code__in=['GE', 'NP', 'SM', 'CO']))
"purchase_status": default_ps_ids
```

### 4. Update Query Optimization

Add `select_related('purchase_status')` to list views for performance:
```python
queryset = LicenseDetailsModel.objects.select_related(
    'exporter',
    'port',
    'purchase_status',  # Add this
    'current_owner'
)
```

## 📋 DEPLOYMENT CHECKLIST

### Before Running Migrations:
- [ ] Backup production database
- [ ] Review all code changes
- [ ] Update all filter queries to use `purchase_status__code`
- [ ] Update all serializers
- [ ] Update default filters
- [ ] Add select_related optimizations

### Migration Steps:
1. [ ] Apply migrations in order:
   ```bash
   python manage.py migrate core 0028
   python manage.py migrate core 0029
   python manage.py migrate license 0016
   ```

2. [ ] Verify data migration:
   ```bash
   python manage.py shell
   >>> from core.models import PurchaseStatus
   >>> PurchaseStatus.objects.all()
   # Should show 9 records with correct is_active flags
   ```

3. [ ] Test API endpoint:
   ```bash
   curl http://localhost:8000/api/masters/purchase-statuses/?is_active=true
   ```

### Testing:
- [ ] Test license list with filters
- [ ] Test license create
- [ ] Test license edit
- [ ] Test all reports (item, pivot, expiring, active)
- [ ] Test allotment actions
- [ ] Test BOE transfers
- [ ] Test frontend dropdowns

### Rollback Plan:
If issues occur:
1. [ ] Revert code changes
2. [ ] Run migrations backward:
   ```bash
   python manage.py migrate license 0015
   python manage.py migrate core 0027
   ```
3. [ ] Restore from database backup if needed

## 🎯 CURRENT STATUS

**Progress: 40% Complete**

✅ Models updated
✅ Migrations created
✅ API endpoint created
✅ Frontend metadata updated

❌ Filter queries NOT updated (CRITICAL)
❌ Serializers NOT updated (CRITICAL)
❌ Default filters NOT updated
❌ Performance optimizations NOT added

**Next Steps:**
1. Systematically update all 25+ files with filter queries
2. Update serializers to handle FK properly
3. Test thoroughly in development
4. Only then deploy to production

**Estimated Time to Complete: 4-6 hours**

## ⚠️ WARNING

**DO NOT RUN MIGRATIONS IN PRODUCTION** until all filter queries and serializers are updated. Running migrations without updating the code will break:
- License filtering
- Report generation
- Allotment actions
- BOE processing
- Any feature that queries by purchase_status
