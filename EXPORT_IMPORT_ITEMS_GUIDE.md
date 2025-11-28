# Export and Import Items Guide

## Overview
This guide explains how to export all LicenseImportItemsModel data, define item names in Excel/Google Sheets, and import them back to update the database.

## Workflow

```
1. Export → 2. Edit in Excel → 3. Import → 4. Verify
```

---

## Step 1: Export Data

### Export All Items (Full Detail)

Export every import item with full details:

```bash
python manage.py export_import_items
```

This creates: `import_items_export_YYYYMMDD_HHMMSS.csv`

**Columns:**
- `import_item_id` - Import item ID
- `license_number` - License number
- `exporter` - Exporter name
- `description` - Product description
- `hs_code` - HSN code
- `norms` - SION norms (comma-separated)
- `quantity` - Quantity
- `cif_value` - CIF value
- `current_item_names` - Already assigned items
- `suggested_item_name` - **Empty for you to fill**

### Export Unique Combinations (Recommended)

Export only unique combinations of description + HSN + norms:

```bash
python manage.py export_import_items --unique
```

**Benefits:**
- Smaller file (easier to work with)
- Each unique combination appears once
- Less repetitive work

### Export with Statistics

Include occurrence counts and totals:

```bash
python manage.py export_import_items --unique --with-count
```

**Additional columns:**
- `occurrence_count` - How many times this combination appears
- `total_quantity` - Sum of all quantities
- `total_cif_value` - Sum of all CIF values
- `sample_licenses` - Sample license numbers (first 5)

### Custom Output File

Specify custom output filename:

```bash
python manage.py export_import_items --unique --with-count --output my_items.csv
```

---

## Step 2: Edit in Excel/Google Sheets

1. **Open the CSV file** in Excel or Google Sheets

2. **Review the data:**
   - Check `description` column
   - Check `hs_code` column
   - Check `norms` column
   - Check `current_item_names` (if any)

3. **Fill in `suggested_item_name` column:**

   Use the pattern: `ITEM_NAME` or `ITEM_NAME - NORM` for norm-specific items

   **Examples:**

   | description | hs_code | norms | suggested_item_name |
   |------------|---------|-------|-------------------|
   | Cocoa Powder | 18050000 | E1 | FRUIT/COCOA - E1 |
   | Cocoa Powder | 18050000 | E5 | FRUIT/COCOA - E5 |
   | Emulsifier | 21069020 | E1 | EMULSIFIER - E1 |
   | Emulsifier | 21069020 | E5 | EMULSIFIER - E5 |
   | Sugar | 17019100 | E1, E5 | SUGAR |
   | Wheat Flour | 11010000 | | WHEAT FLOUR |
   | Water Pump | 84137000 | | WATER PUMP |

4. **Tips:**
   - Use consistent naming
   - Add norm suffix for norm-specific items (e.g., `- E1`, `- E5`)
   - Use ALL CAPS for consistency
   - Group similar items with same base name
   - Leave blank if you don't want to assign an item

5. **Save the file** (keep as CSV format)

---

## Step 3: Import Item Names

### Preview Import (Dry Run)

Preview what will happen without making changes:

```bash
python manage.py import_item_names my_items.csv --dry-run
```

This shows:
- How many items will be created
- How many import items will be updated
- Any errors or warnings

### Import with Auto-Create

Import and automatically create missing ItemNameModel entries:

```bash
python manage.py import_item_names my_items.csv --create-items
```

This will:
1. Create ItemNameModel entries for new item names
2. Link items to import items based on matching criteria
3. Show statistics

### Import Without Auto-Create

Only link to existing ItemNameModel entries:

```bash
python manage.py import_item_names my_items.csv
```

Use this if you want to create items manually first.

---

## Step 4: Verify Results

### Check Statistics

The import command shows:
```
Statistics:
  Total mappings processed: 150
  Items found: 80
  Items created: 70
  Items not found: 0
  Import items matched: 5432
  Import items updated: 5432
```

### Verify in Database

```bash
python manage.py shell
```

```python
from core.models import ItemNameModel
from license.models import LicenseImportItemsModel

# Check total items
ItemNameModel.objects.count()

# Check items with E1 norm
ItemNameModel.objects.filter(name__contains='E1').count()

# Check import items with assigned items
LicenseImportItemsModel.objects.filter(items__isnull=False).count()

# Check specific item assignment
item = ItemNameModel.objects.get(name='EMULSIFIER - E1')
import_items = LicenseImportItemsModel.objects.filter(items=item)
print(f"Import items with EMULSIFIER - E1: {import_items.count()}")
```

### Verify in Admin/API

1. **Admin:** Go to `/admin/core/itemnamemodel/`
2. **API:** Visit `/api/masters/item-names/`
3. Check that items were created correctly

---

## Matching Logic

The import command matches import items based on:

### 1. Description (Case-insensitive contains)
```python
description__icontains="Cocoa Powder"
```

### 2. HSN Code (First 6 digits)
```python
hs_code__hs_code__startswith="180500"
```

### 3. SION Norms (Exact match)
```python
license__export_license__norm_class__norm_class="E1"
```

**All conditions must match** (AND logic)

---

## Complete Example

### 1. Export
```bash
python manage.py export_import_items --unique --with-count --output items.csv
```

### 2. Edit `items.csv`

| description | hs_code | norms | occurrence_count | suggested_item_name |
|------------|---------|-------|-----------------|-------------------|
| Cocoa Powder | 18050000 | E1 | 45 | FRUIT/COCOA - E1 |
| Cocoa Powder | 18050000 | E5 | 23 | FRUIT/COCOA - E5 |
| Food Flavour | 33029010 | E1 | 67 | FOOD FLAVOUR - E1 |
| Food Flavour | 33029010 | E5 | 89 | FOOD FLAVOUR - E5 |
| Sugar | 17019100 | E1, E5 | 120 | SUGAR |

### 3. Preview Import
```bash
python manage.py import_item_names items.csv --dry-run --create-items
```

Output:
```
Processing mappings...
  + Would create: FRUIT/COCOA - E1
  + Would create: FRUIT/COCOA - E5
  + Would create: FOOD FLAVOUR - E1
  + Would create: FOOD FLAVOUR - E5
  + Would create: SUGAR

Statistics:
  Total mappings processed: 5
  Items created: 5
  Import items matched: 344
  Import items updated: 344

DRY RUN - No changes were made
```

### 4. Actual Import
```bash
python manage.py import_item_names items.csv --create-items
```

### 5. Verify
```bash
python manage.py shell

>>> from core.models import ItemNameModel
>>> ItemNameModel.objects.count()
5
>>> ItemNameModel.objects.filter(name__contains='E1').values_list('name', flat=True)
['FRUIT/COCOA - E1', 'FOOD FLAVOUR - E1']
```

---

## Advanced Usage

### Export Specific Licenses

Export only specific norms:

```bash
python manage.py shell

>>> from license.models import LicenseImportItemsModel
>>> items = LicenseImportItemsModel.objects.filter(
...     license__export_license__norm_class__norm_class='E1'
... )
>>> # Save to CSV manually or modify export command
```

### Bulk Update Existing Items

If items already exist but need to be re-linked:

```bash
# First clear existing assignments
python manage.py shell

>>> from license.models import LicenseImportItemsModel
>>> for item in LicenseImportItemsModel.objects.all():
...     item.items.clear()

# Then import
python manage.py import_item_names items.csv
```

### Update Item Properties

After importing, update SION norms and restrictions:

```bash
python manage.py shell

>>> from core.models import ItemNameModel, SionNormClassModel
>>> e1_norm = SionNormClassModel.objects.get(norm_class='E1')
>>>
>>> # Update all E1 items
>>> for item in ItemNameModel.objects.filter(name__contains='- E1'):
...     item.sion_norm_class = e1_norm
...     item.restriction_percentage = 2.00  # 2%
...     item.is_active = True
...     item.save()
```

---

## Troubleshooting

### No matches found

**Problem:** Import items not getting linked

**Solution:**
- Check that description matches (case-insensitive)
- Check that HSN code matches (first 6 digits)
- Check that norms match exactly
- Try with just description first (remove HSN/norms from CSV)

### Items not created

**Problem:** "Item not found" errors

**Solution:**
- Use `--create-items` flag
- Or create items manually first in admin

### Too many matches

**Problem:** One mapping matches too many import items

**Solution:**
- Be more specific with description
- Include HSN code for better filtering
- Include norms for better filtering
- Split into multiple mappings

### Duplicate items created

**Problem:** Same item created multiple times

**Solution:**
- Check for duplicate rows in CSV
- Item names are unique - duplicates will error
- Use unique export to avoid duplicates

---

## Best Practices

1. **Always start with --dry-run**
   ```bash
   python manage.py import_item_names items.csv --dry-run --create-items
   ```

2. **Use unique export for cleaner workflow**
   ```bash
   python manage.py export_import_items --unique --with-count
   ```

3. **Sort by occurrence_count**
   - Handle high-frequency items first
   - These have the most impact

4. **Use consistent naming**
   - ALL CAPS for item names
   - Add norm suffix: `- E1`, `- E5`, `- E126`, `- E132`
   - Use same format throughout

5. **Backup before importing**
   ```bash
   pg_dump your_database > backup_before_import.sql
   ```

6. **Verify after importing**
   - Check counts match expectations
   - Spot-check some assignments
   - Test in reports

---

## Next Steps After Import

1. **Set Groups:**
   ```python
   from core.models import ItemNameModel, GroupModel

   food_group = GroupModel.objects.get_or_create(name='Food Additives')[0]
   ItemNameModel.objects.filter(name__contains='EMULSIFIER').update(group=food_group)
   ```

2. **Set SION Norms:**
   ```python
   from core.models import SionNormClassModel

   e1 = SionNormClassModel.objects.get(norm_class='E1')
   ItemNameModel.objects.filter(name__endswith='- E1').update(sion_norm_class=e1)
   ```

3. **Set Restrictions:**
   ```python
   # 2% restriction for E1 items
   ItemNameModel.objects.filter(
       name__endswith='- E1'
   ).update(restriction_percentage=2.00)
   ```

4. **Activate Items:**
   ```python
   ItemNameModel.objects.all().update(is_active=True)
   ```

5. **Generate Reports:**
   - Test Item Pivot Report
   - Verify restriction calculations
   - Check balance calculations
