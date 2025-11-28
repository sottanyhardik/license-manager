# Clean ItemNameModel Guide

## Overview
This guide explains how to clean (delete) all ItemNameModel records from the database and repopulate them with the new norm-specific structure.

## Steps to Clean and Repopulate

### Step 1: Preview What Will Be Deleted

Run without `--confirm` to see what will be deleted:

```bash
python manage.py clean_item_names
```

This will show:
- Total number of records
- Preview of first 10 items
- No actual deletion happens

### Step 2: Clean All Item Names

**⚠️ WARNING: This will delete ALL ItemNameModel records!**

```bash
python manage.py clean_item_names --confirm
```

This will:
- Delete all ItemNameModel records
- Show deletion details
- Clear all item associations from LicenseImportItemsModel

### Step 3: Repopulate with New Items

After cleaning, populate with the new norm-specific items:

```bash
# Preview what will be created
python manage.py populate_license_items --dry-run

# Actually create and populate items
python manage.py populate_license_items
```

This will:
1. Clear any existing item associations
2. Create new norm-specific items:
   - E1 items: EMULSIFIER - E1, FOOD FLAVOUR - E1, FRUIT/COCOA - E1, etc.
   - E5 items: EMULSIFIER - E5, FOOD FLAVOUR - E5, FRUIT/COCOA - E5, etc.
   - E126 items: FOOD FLAVOUR - E126, FOOD ADDITIVES - E126, etc.
   - E132 items: FOOD FLAVOUR - E132, FOOD ADDITIVES - E132, etc.
3. Link items to LicenseImportItemsModel based on description filters

## Complete Workflow

```bash
# 1. Backup database first!
pg_dump your_database > backup_before_clean.sql  # PostgreSQL
# or
mysqldump your_database > backup_before_clean.sql  # MySQL

# 2. Preview deletion
python manage.py clean_item_names

# 3. Clean all items
python manage.py clean_item_names --confirm

# 4. Preview population
python manage.py populate_license_items --dry-run

# 5. Populate with new items
python manage.py populate_license_items

# 6. Verify results
python manage.py shell
>>> from core.models import ItemNameModel
>>> ItemNameModel.objects.count()
>>> ItemNameModel.objects.filter(name__contains='E1').count()
>>> ItemNameModel.objects.filter(name__contains='E5').count()
```

## What Gets Created

### E1 Confectionery Items
- STABILIZING AGENT - E1
- WPC - E1
- EMULSIFIER - E1
- FRUIT/COCOA - E1
- FRUIT JUICE - E1
- FOOD FLAVOUR - E1
- CITRIC ACID / TARTARIC ACID - E1
- OTHER CONFECTIONERY INGREDIENTS - E1

### E5 Biscuits Items
- BISCUITS ADDITIVES & INGREDIENTS - E5
- EMULSIFIER - E5
- FOOD FLAVOUR - E5
- FRUIT/COCOA - E5
- JUICE - E5

### E126 Pickle Items
- FOOD FLAVOUR - E126
- FOOD ADDITIVES - E126
- SANITATION AND CLEANING CHEMICALS - E126

### E132 Namkeen Items
- FOOD FLAVOUR - E132
- FOOD ADDITIVES - E132
- FOOD ADDITIVES TBHQ - E132
- EDIBLE VEGETABLE OIL - E132

### Common Items (No Norm Restriction)
- SUGAR
- WHEAT GLUTEN
- WHEAT FLOUR
- CHEESE
- ANTI OXIDANT
- FOOD COLOUR
- STARCH 1108
- STARCH 3505
- LEAVENING AGENT
- VEGETABLE SHORTENING
- RBD PALMOLEIN OIL
- PALM KERNEL OIL
- LIQUID GLUCOSE
- ESSENTIAL OIL
- CEREALS FLAKES
- And all automotive/engineering items
- And all packaging materials

## Setting Restrictions

After populating, you need to set the `sion_norm_class` and `restriction_percentage` for each item in the Django admin or through the API:

1. Go to `/admin/core/itemnamemodel/` or `/masters/item-names`
2. For each item, set:
   - **Group**: Optional categorization (e.g., "Food", "Automotive", "Packaging")
   - **SION Norm Class**: Select the norm (e.g., E1, E5, E126, E132)
   - **Restriction Percentage**: Set the percentage (e.g., 2.00 for 2%, 10.00 for 10%)
   - **Is Active**: Set to True to make it available

Example:
```
Name: EMULSIFIER - E1
Group: Food Additives
SION Norm Class: E1
Restriction Percentage: 2.00
Is Active: True
```

## Verification Queries

### Check Total Items
```sql
SELECT COUNT(*) FROM core_itemnamemodel;
```

### Check Items by Norm
```sql
SELECT name, sion_norm_class_id, restriction_percentage
FROM core_itemnamemodel
WHERE name LIKE '%E1%'
ORDER BY name;
```

### Check Items Without Group
```sql
SELECT name FROM core_itemnamemodel WHERE group_id IS NULL;
```

### Check Items Without SION Norm
```sql
SELECT name FROM core_itemnamemodel WHERE sion_norm_class_id IS NULL;
```

## Rollback

If something goes wrong:

```bash
# Restore from backup
psql your_database < backup_before_clean.sql  # PostgreSQL
# or
mysql your_database < backup_before_clean.sql  # MySQL
```

## Notes

- The clean command will also clear all ManyToMany relationships in `LicenseImportItemsModel.items`
- After cleaning and repopulating, you may need to manually set the `group`, `sion_norm_class`, and `restriction_percentage` for each item
- The populate command matches items to import items based on description filters
- Items are matched case-insensitively
