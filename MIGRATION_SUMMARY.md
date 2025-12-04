# ItemHeadModel to ItemGroupModel Migration Summary

## Overview

This migration replaces `ItemHeadModel` with a simpler `ItemGroupModel` and removes unnecessary fields from
`ItemNameModel`. The restriction logic has been moved from ItemHeadModel to ItemNameModel level using `sion_norm_class`
and `restriction_percentage`.

## Changes Made

### 1. Backend Models (core/models.py)

#### Created ItemGroupModel

```python
class ItemGroupModel(AuditModel):
    """Group model for categorizing items"""
    name = models.CharField(max_length=255, unique=True)
```

#### Updated ItemNameModel

**Removed Fields:**

- `unit_price` - No longer needed
- `head` - Replaced with `group`

**Changed Fields:**

- `head` → `group` (now ForeignKey to ItemGroupModel)
- `ordering` changed from `['head__name', 'name']` to `['group__name', 'name']`

**Kept Fields:**

- `name`
- `is_active`
- `sion_norm_class`
- `restriction_percentage`

#### ItemHeadModel

- Marked as deprecated
- Still exists for backward compatibility
- Will be removed in future version

### 2. Database Migration (core/migrations/0020_create_group_model_and_migrate_items.py)

The migration automatically:

1. Creates ItemGroupModel table
2. Copies all ItemHeadModel names to ItemGroupModel
3. Migrates ItemNameModel.head to ItemNameModel.group
4. Removes unit_price field
5. Removes head field
6. Includes reverse migration support

### 3. Backend Serializers (core/serializers.py)

**Added:**

- `GroupSerializer` - New serializer for ItemGroupModel

**Updated:**

- `ItemNameSerializer`:
    - Changed `head_name` to `group_name`
    - Updated to use `group.name` instead of `head.name`

**Deprecated:**

- `ItemHeadSerializer` - Marked as deprecated

### 4. Backend ViewSets (core/views/views.py)

**Added:**

- `GroupViewSet` - New viewset for ItemGroupModel
    - Endpoint: `/api/masters/groups/`
    - Simple CRUD operations

**Updated:**

- `ItemNameViewSet`:
    - Search: `head__name` → `group__name`
    - Filter: `head` → `group` with endpoint `/masters/groups/`
    - List display: `head__name` → `group__name`, removed `unit_price`
    - Form fields: `head` → `group`, removed `unit_price`
    - Ordering: `head__name` → `group__name`

### 5. Backend URLs (core/urls.py)

**Added:**

- `router.register("groups", GroupViewSet)` - New endpoint

**Updated:**

- `item-heads` endpoint marked as deprecated

### 6. Backend License Models (license/models.py)

**Updated Methods:**

- `import_license_head_grouped()` → `import_license_group_grouped()`
    - Changed `items__head__name` to `items__group__name`
    - Removed `items__unit_price` from values
    - Old method kept as deprecated alias

- `get_item_head_data()` → `get_item_group_data()`
    - Changed to use `items__group__name`
    - Old method kept as deprecated alias

- `_sum_for_head()` → `_sum_for_group()`
    - Changed `items__head__name` to `items__group__name`
    - Old method kept as deprecated alias

**Updated Restriction Logic:**

- Moved from `item_name.head.is_restricted` to `item_name.sion_norm_class` and `item_name.restriction_percentage`
- Changed from checking `items__head` to `items__sion_norm_class` and `items__restriction_percentage`
- Now groups by `(sion_norm_class, restriction_percentage)` tuple instead of just `head`

### 7. Frontend Routes (frontend/src/routes/config.js)

**Added:**

```javascript
{
    path: "/masters/groups",
    label: "Groups",
    entity: "groups",
    icon: "folder",
}
```

**Updated:**

- Moved "Item Heads" after "Item Names"
- Marked as deprecated
- Added `deprecated: true` flag

### 8. Management Commands

**Updated:**

- `populate_license_items.py` - Now auto-creates items and clears existing associations
    - Creates norm-specific items (e.g., "EMULSIFIER - E1", "EMULSIFIER - E5")
    - Separates items by SION norm class for different restrictions

## Migration Steps

1. **Backup your database** before running migrations

2. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

3. **Populate new item names:**
   ```bash
   # Dry run to see what will happen
   python manage.py populate_license_items --dry-run

   # Actually run the population
   python manage.py populate_license_items
   ```

4. **Verify the migration:**
    - Check that all groups are created: `/api/masters/groups/`
    - Check that item names have correct groups: `/api/masters/item-names/`
    - Verify restriction calculations still work correctly

## Breaking Changes

### API Endpoints

- ItemName now returns `group` and `group_name` instead of `head` and `head_name`
- ItemName no longer includes `unit_price` field
- ItemHeadModel endpoints still work but are deprecated

### Database Schema

- `core_itemnamemodel.head_id` removed
- `core_itemnamemodel.unit_price` removed
- `core_itemnamemodel.group_id` added
- `core_ItemGroupModel` table added

### Restriction Logic

- Restrictions now calculated using `sion_norm_class` + `restriction_percentage` on ItemNameModel
- No longer relies on ItemHeadModel restrictions
- Groups items by `(norm_class, restriction_percentage)` tuple

## Backward Compatibility

### Deprecated but Still Working

- ItemHeadModel still exists in database
- `/api/masters/item-heads/` endpoint still works
- `import_license_head_grouped` property still works (calls new method internally)
- `get_item_head_data()` method still works (calls new method internally)
- `_sum_for_head()` function still works (calls new function internally)

### To Be Removed in Future

- ItemHeadModel (after confirming no dependencies)
- item-heads API endpoint
- All deprecated methods and properties

## Testing Checklist

- [ ] Groups CRUD operations work
- [ ] Item Names can be created/updated with groups
- [ ] Item Names show correct group in list view
- [ ] Restriction calculations work correctly
- [ ] License import grouping works correctly
- [ ] Item pivot report works correctly
- [ ] Populate license items command works
- [ ] Frontend displays groups correctly
- [ ] Frontend forms work with new group field

## Rollback Plan

If issues occur, the migration can be reversed:

```bash
python manage.py migrate core 0019_replace_restriction_group_with_sion_norm
```

This will:

1. Restore the `head` field on ItemNameModel
2. Remove the `group` field
3. Restore the `unit_price` field
4. Remove the ItemGroupModel table

## Next Steps

1. Monitor for any issues in production
2. Update any custom reports or scripts that reference `head` or `unit_price`
3. Once confirmed stable, plan removal of ItemHeadModel in future release
4. Update documentation to reflect new structure
