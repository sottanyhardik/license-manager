# Audit Fields Reference

**Date:** November 19, 2025
**Purpose:** Standard field naming convention for audit fields across the project

## Standard Audit Fields

All models extending `AuditModel` automatically include these fields:

### Field Names (Use These):
- ✅ `created_on` - DateTimeField (auto_now_add=True)
- ✅ `modified_on` - DateTimeField (auto_now=True)
- ✅ `created_by` - ForeignKey to AUTH_USER_MODEL (nullable)
- ✅ `modified_by` - ForeignKey to AUTH_USER_MODEL (nullable)

### DO NOT Use These Names:
- ❌ `created_at` - Wrong naming convention
- ❌ `updated_at` - Wrong naming convention
- ❌ `created_date` - Wrong naming convention
- ❌ `modified_date` - Wrong naming convention

## AuditModel Definition

Located in: `backend/core/models.py`

```python
class AuditModel(models.Model):
    """
    Abstract base with automatic created/modified auditing.
    """
    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created",
    )
    modified_on = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True
```

## Models Using AuditModel

All these models inherit audit fields:

### Core App:
- ✅ CompanyModel
- ✅ HSCodeModel
- ✅ ItemHeadModel
- ✅ ItemNameModel
- ✅ PortModel
- ✅ ProductDescriptionModel
- ✅ SIONNormClassModel
- ✅ TransferLetterModel
- ✅ UnitPriceModel
- ✅ MEISModel (legacy)
- ✅ HSCodeDutyModel (legacy)

### Bill of Entry App:
- ✅ BillOfEntryModel
- ✅ RowDetails

### Allotment App:
- ✅ AllotmentModel
- ✅ AllotmentItems

## Serializer Usage

### Correct Way:

```python
class MyModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyModel
        fields = [
            'id',
            # ... other fields ...
            'created_on',      # ✅ Correct
            'modified_on',     # ✅ Correct
            'created_by',      # ✅ Correct
            'modified_by',     # ✅ Correct
        ]
        read_only_fields = ['created_on', 'modified_on', 'created_by', 'modified_by']
```

### Wrong Way:

```python
class MyModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyModel
        fields = [
            'id',
            # ... other fields ...
            'created_at',      # ❌ Wrong - will cause error
            'updated_at',      # ❌ Wrong - will cause error
        ]
```

## Database Column Names

In PostgreSQL, these fields appear as:

| Field in Django | Column in Database | Type |
|----------------|-------------------|------|
| created_on | created_on | timestamp with time zone |
| modified_on | modified_on | timestamp with time zone |
| created_by | created_by_id | integer/bigint |
| modified_by | modified_by_id | integer/bigint |

## API Response Format

When serialized, audit fields appear in JSON responses:

```json
{
    "id": 1,
    "created_on": "2025-11-19T10:30:00Z",
    "modified_on": "2025-11-19T14:24:34Z",
    "created_by": 1,
    "modified_by": 2
}
```

## Common Issues and Fixes

### Issue 1: ImproperlyConfigured Error
**Error:** `Field name 'created_at' is not valid for model`

**Cause:** Using wrong field name in serializer

**Fix:** Change `created_at` → `created_on` and `updated_at` → `modified_on`

```python
# Before (Wrong)
fields = [..., 'created_at', 'updated_at']

# After (Correct)
fields = [..., 'created_on', 'modified_on']
```

### Issue 2: Missing Audit Fields in Serializer
**Symptom:** Audit fields not returned in API

**Fix:** Add to serializer fields list

```python
fields = [
    'id',
    # ... your fields ...
    'created_on',
    'modified_on',
    'created_by',
    'modified_by',
]
```

### Issue 3: Trying to Set Read-Only Fields
**Error:** Validation error when creating/updating

**Fix:** Mark as read-only

```python
read_only_fields = ['created_on', 'modified_on', 'created_by', 'modified_by']
```

## Automatic User Tracking

The `created_by` and `modified_by` fields are automatically set when:

1. User is authenticated
2. Middleware/signal captures current user
3. Model's save() method is called

```python
# Automatic tracking happens via:
def save(self, *args, **kwargs):
    user = get_current_user()
    if not self.pk and user:
        self.created_by = user
    if user:
        self.modified_by = user
    super().save(*args, **kwargs)
```

## Validation

Use the validation command to check all audit fields:

```bash
python manage.py validate_db_fields

# Check specific model
python manage.py validate_db_fields --table bill_of_entry_billofentrymodel

# Detailed output
python manage.py validate_db_fields --detailed
```

## Testing Audit Fields

```python
# In Django shell
from bill_of_entry.models import BillOfEntryModel

# Check field existence
print(hasattr(BillOfEntryModel, 'created_on'))      # True
print(hasattr(BillOfEntryModel, 'modified_on'))     # True
print(hasattr(BillOfEntryModel, 'created_by'))      # True
print(hasattr(BillOfEntryModel, 'modified_by'))     # True

# Check field types
from django.db import models
boe = BillOfEntryModel._meta.get_field('created_on')
print(isinstance(boe, models.DateTimeField))        # True
```

## Migration Considerations

When creating new models:

1. Extend `AuditModel` instead of `models.Model`
2. Audit fields are inherited automatically
3. No need to define them manually

```python
# Correct
class MyNewModel(AuditModel):
    # Your fields here
    name = models.CharField(max_length=100)
    # created_on, modified_on, created_by, modified_by inherited automatically

# Wrong
class MyNewModel(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)  # Don't do this
```

## Summary

| Aspect | Use This | Not This |
|--------|----------|----------|
| Timestamp (creation) | `created_on` | ~~created_at~~ |
| Timestamp (modification) | `modified_on` | ~~updated_at~~ |
| User (creation) | `created_by` | ~~created_by_user~~ |
| User (modification) | `modified_by` | ~~updated_by~~ |
| Base model | `AuditModel` | ~~BaseModel~~ |
| Field type | `DateTimeField` | ~~DateField~~ |

---

**Remember:** Always use `created_on` and `modified_on` (with "on"), not `created_at` or `updated_at` (with "at")!
