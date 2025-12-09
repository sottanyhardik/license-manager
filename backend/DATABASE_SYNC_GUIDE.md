# Database Schema Synchronization Guide

This guide explains how to check and sync your database schema with Django models.

## Tools Available

### 1. `sync_database_schema` - Management Command
Comprehensive Python-based schema checker and fixer.

#### Basic Usage:
```bash
# Check schema only
python manage.py sync_database_schema

# Check specific app
python manage.py sync_database_schema --app license

# Show SQL that would be executed
python manage.py sync_database_schema --show-sql

# Fix issues automatically
python manage.py sync_database_schema --fix
```

### 2. `check_db_structure` - Management Command
Quick database structure checker.

#### Basic Usage:
```bash
# Basic check
python manage.py check_db_structure

# Detailed check with columns
python manage.py check_db_structure --show-columns

# Check specific app
python manage.py check_db_structure --app license

# Verbose output
python manage.py check_db_structure --verbose

# Attempt to fix missing tables
python manage.py check_db_structure --fix
```

### 3. `check_and_fix_schema.sh` - Interactive Bash Script
User-friendly interactive script for checking and fixing schema.

#### Basic Usage:
```bash
# Run interactive script
./check_and_fix_schema.sh
```

The script will:
1. Check database structure
2. Check for schema inconsistencies
3. Check for missing migrations
4. Offer options to generate and/or apply migrations

## Common Issues and Solutions

### Issue 1: Missing Tables
**Symptom:** Model exists but no corresponding database table

**Solution:**
```bash
python manage.py makemigrations
python manage.py migrate
```

### Issue 2: Missing Columns
**Symptom:** Model field exists but column not in database

**Solution:**
```bash
# Generate migration for the missing column
python manage.py makemigrations

# Review the migration
python manage.py sqlmigrate <app> <migration_number>

# Apply the migration
python manage.py migrate
```

### Issue 3: Type Mismatches
**Symptom:** Database column type doesn't match model field type

**Solution:**
```bash
# This requires manual migration
python manage.py makemigrations --empty <app>

# Edit the migration file to add:
operations = [
    migrations.AlterField(
        model_name='modelname',
        name='fieldname',
        field=models.DecimalField(max_digits=10, decimal_places=2),
    ),
]

# Apply the migration
python manage.py migrate
```

### Issue 4: Extra Columns in Database
**Symptom:** Database has columns that don't exist in models

**Options:**
1. **Keep them** - If they're used by other systems
2. **Remove them** - If they're legacy/unused:
```sql
-- Manually drop the column (after backup!)
ALTER TABLE table_name DROP COLUMN column_name;
```

## Step-by-Step: Full Database Sync

### For Development/Testing Environment:

```bash
# 1. Check what's out of sync
python manage.py sync_database_schema

# 2. Generate migrations
python manage.py makemigrations

# 3. Review migrations
ls -la */migrations/

# 4. Apply migrations
python manage.py migrate

# 5. Verify
python manage.py sync_database_schema
```

### For Production Environment:

```bash
# 1. BACKUP DATABASE FIRST!
pg_dump -h localhost -U dbuser -d dbname > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Check schema on production
python manage.py sync_database_schema

# 3. Test migrations on staging first
# ... test on staging ...

# 4. Apply to production (with backup)
python manage.py migrate --verbosity 2

# 5. Verify
python manage.py sync_database_schema
```

## Common Field Type Mappings

| Django Field Type | PostgreSQL Type |
|------------------|-----------------|
| AutoField | integer (with sequence) |
| BigAutoField | bigint (with sequence) |
| BooleanField | boolean |
| CharField | character varying(max_length) |
| DateField | date |
| DateTimeField | timestamp with time zone |
| DecimalField | numeric(max_digits, decimal_places) |
| FloatField | double precision |
| IntegerField | integer |
| TextField | text |
| ForeignKey | integer (references other table) |

## Troubleshooting

### Error: "no such table"
**Cause:** Migrations haven't been applied
**Fix:**
```bash
python manage.py migrate
```

### Error: "column does not exist"
**Cause:** Model has new field but migration not applied
**Fix:**
```bash
python manage.py makemigrations
python manage.py migrate
```

### Error: "duplicate column name"
**Cause:** Trying to add a column that already exists
**Fix:**
```bash
# Remove the migration file and regenerate
rm app/migrations/XXXX_migration.py
python manage.py makemigrations
```

### Error: "cannot cast type"
**Cause:** Type change requires explicit casting
**Fix:**
```python
# In migration file, use RunSQL to cast:
operations = [
    migrations.RunSQL(
        "ALTER TABLE table_name ALTER COLUMN column_name TYPE new_type USING column_name::new_type"
    ),
]
```

## Best Practices

1. **Always backup before schema changes**
2. **Test migrations on staging first**
3. **Review generated migrations before applying**
4. **Use `--dry-run` to preview changes**
5. **Document custom migrations**
6. **Keep migrations in version control**

## Specific Fix: Float to Decimal Conversion

If you're experiencing `unsupported operand type(s) for *: 'float' and 'decimal.Decimal'` errors:

### Diagnosis:

```bash
# 1. Check the current database column type for restriction_percentage
python manage.py dbshell
```

```sql
SELECT table_name, column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE column_name = 'restriction_percentage'
AND table_schema = 'public';
```

**Expected output:**
- data_type: `numeric`
- numeric_precision: `5`
- numeric_scale: `2`

**If you see:**
- data_type: `double precision`

This means the database column is still a float type, causing the error.

### Solution:

```bash
# 1. The model is already defined as DecimalField in core/models.py:
# restriction_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

# 2. Apply migration 0028 to convert database column from float to Decimal:
cd backend
python manage.py migrate core 0028

# 3. Verify the change:
python manage.py dbshell
```

```sql
SELECT table_name, column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE column_name = 'restriction_percentage'
AND table_schema = 'public';
```

**After migration, you should see:**
- data_type: `numeric`
- numeric_precision: `5`
- numeric_scale: `2`

### Migration Details:

Migration `0028_alter_restriction_percentage_to_decimal.py` contains:

```python
operations = [
    migrations.AlterField(
        model_name='itemnamemodel',
        name='restriction_percentage',
        field=models.DecimalField(
            decimal_places=2,
            default=Decimal('0'),
            max_digits=5,
            validators=[MinValueValidator(Decimal('0'))],
        ),
    ),
]
```

This will execute SQL similar to:
```sql
ALTER TABLE core_itemnamemodel
ALTER COLUMN restriction_percentage TYPE numeric(5, 2)
USING restriction_percentage::numeric(5, 2);
```

### Testing After Fix:

```bash
# Test Item Pivot Report endpoint
curl -X POST 'http://localhost:8000/api/reports/item-pivot/generate-report/' \
  -H 'Content-Type: application/json' \
  -d '{
    "filters": {
      "item_names": ["1"],
      "companies": ["1"]
    }
  }'

# Should return JSON report data without float * Decimal error
```

## Getting Help

If you encounter issues:

1. Check the migration history:
   ```bash
   python manage.py showmigrations
   ```

2. Check for unapplied migrations:
   ```bash
   python manage.py showmigrations | grep '\[ \]'
   ```

3. Fake migrations if needed (advanced):
   ```bash
   python manage.py migrate --fake <app> <migration>
   ```

4. Rebuild migrations (last resort):
   ```bash
   python manage.py rebuild_migrations --full
   ```

## Additional Resources

- Django Migrations Documentation: https://docs.djangoproject.com/en/stable/topics/migrations/
- PostgreSQL ALTER TABLE: https://www.postgresql.org/docs/current/sql-altertable.html
