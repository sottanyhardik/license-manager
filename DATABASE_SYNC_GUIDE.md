# Database Structure Synchronization Guide

This guide explains how to maintain database structure consistency and sync data from GE (Government E-commerce) server.

## Overview

The project now includes three management commands to manage database structure and data synchronization:

1. **check_db_structure** - Check database structure against Django models
2. **rebuild_migrations** - Clean up and rebuild migration files
3. **sync_from_ge_server** - Sync data from GE server

## Missing Tables Analysis

### Current Status

The following models exist in code but don't have database tables yet:

#### Core App Missing Tables:
- `core_invoiceentity` (InvoiceEntity model)
- `core_schemecode` (SchemeCode model)
- `core_notificationnumber` (NotificationNumber model)
- `core_purchasestatus` (PurchaseStatus model)

#### License App Missing Tables:
- `license_invoice` (Invoice model)
- `license_invoiceitem` (InvoiceItem model)
- `license_licensepurchase` (LicensePurchase model)

#### Trade App Missing Tables:
- `trade_licensetrade` (LicenseTrade model)
- `trade_licensetradeline` (LicenseTradeLine model)
- `trade_licensetradepayment` (LicenseTradePayment model)

### Why These Tables Are Missing

These tables were defined in models but migrations were never created or applied for them. This typically happens when:
- Models are added but `makemigrations` was not run
- Migrations exist but were never applied with `migrate`
- Database was created from a partial schema backup

## Step-by-Step Workflow

### Option 1: Quick Fix (Recommended for Development)

```bash
cd backend

# Activate virtual environment
source ../.venv/bin/activate

# Step 1: Check current database structure
python manage.py check_db_structure --verbose

# Step 2: Create migrations for missing tables
python manage.py makemigrations core license trade

# Step 3: Apply migrations
python manage.py migrate

# Step 4: Verify all tables exist
python manage.py check_db_structure
```

### Option 2: Full Rebuild (For Migration Conflicts)

If you have migration conflicts or want to start fresh:

```bash
cd backend
source ../.venv/bin/activate

# Step 1: Backup current migrations
python manage.py rebuild_migrations --backup

# Step 2: Remove conflicting ALTER migrations
python manage.py rebuild_migrations --remove-alters

# Step 3: Create fresh migrations
python manage.py rebuild_migrations --recreate --apps core,license,trade

# Step 4: Review migrations before applying
python manage.py showmigrations

# Step 5: Apply migrations
python manage.py migrate --plan  # Preview first
python manage.py migrate  # Apply

# Step 6: Verify database structure
python manage.py check_db_structure --show-columns
```

### Option 3: One-Command Full Rebuild

```bash
python manage.py rebuild_migrations --full
python manage.py migrate
```

## Syncing Data from GE Server

Once database structure is correct, sync license data from GE server:

```bash
# Full sync (structure + data)
python manage.py sync_from_ge_server --full

# Data only (skip structure check)
python manage.py sync_from_ge_server --data-only

# Sync specific license
python manage.py sync_from_ge_server --license 0310837893

# Dry run (see what would be synced)
python manage.py sync_from_ge_server --full --dry-run
```

## Understanding the Models

### InvoiceEntity (core app)
Used for invoice generation with company branding (logo, signature, stamp, bank details).

### SchemeCode, NotificationNumber, PurchaseStatus (core app)
Lookup tables for license metadata. These use choices defined in `core/constants.py`:
- **SchemeCode**: EPCG, Advance Authorization, etc.
- **NotificationNumber**: Various DGFT notification numbers
- **PurchaseStatus**: GE, CONVERSION, AMALGAMATION, REVALIDATION

### LicensePurchase (license app)
Tracks license purchase transactions with amount/quantity modes and markup calculations.

### Invoice & InvoiceItem (license app)
Billing system for license items with multiple billing modes (KG-based, CIF %, FOB %).

### LicenseTrade Models (trade app)
Complete trade management system:
- **LicenseTrade**: Header (invoice details, parties, totals)
- **LicenseTradeLine**: Line items with flexible billing modes
- **LicenseTradePayment**: Payment tracking

## Migration File Naming Convention

After rebuilding, your migration files should follow this pattern:

```
core/migrations/
  0001_initial.py               # Initial schema
  0002_add_invoice_models.py    # New models

license/migrations/
  0001_initial.py
  0002_add_trade_models.py

trade/migrations/
  0001_initial.py
```

## Troubleshooting

### Problem: "table already exists" error

**Solution**: The table exists but Django doesn't know about it.

```bash
# Fake the migration as already applied
python manage.py migrate --fake core 0002_add_invoice_models
```

### Problem: Migration conflicts

**Solution**: Rebuild migrations from scratch.

```bash
python manage.py rebuild_migrations --full --dry-run  # Preview first
python manage.py rebuild_migrations --full            # Execute
```

### Problem: Column type mismatch

**Solution**: Create ALTER migration manually or modify model field to match DB.

```bash
# Check exact mismatch
python manage.py check_db_structure --show-columns

# Create migration for the fix
python manage.py makemigrations --name fix_column_types
```

### Problem: Foreign key constraint errors

**Solution**: Ensure referenced tables exist first.

```bash
# Check migration order
python manage.py showmigrations

# If needed, specify dependencies in migration file:
# dependencies = [
#     ('core', '0001_initial'),
#     ('license', '0001_initial'),
# ]
```

## Best Practices

1. **Always backup before major changes**
   ```bash
   pg_dump -U lmanagement lmanagement > backup_$(date +%Y%m%d).sql
   ```

2. **Use dry-run first**
   ```bash
   python manage.py rebuild_migrations --full --dry-run
   python manage.py sync_from_ge_server --full --dry-run
   ```

3. **Review migrations before applying**
   ```bash
   python manage.py migrate --plan
   python manage.py sqlmigrate core 0002
   ```

4. **Keep migrations clean**
   - Remove ALTER migrations that conflict
   - Squash migrations periodically
   - Don't hand-edit migration files unless necessary

5. **Test on development first**
   - Always test migration workflow on dev database
   - Use --dry-run flags to preview changes
   - Keep production backups

## Production Deployment Checklist

Before running these commands in production:

- [ ] Full database backup created
- [ ] Tested on staging environment
- [ ] All migration files reviewed
- [ ] Downtime window scheduled (if needed)
- [ ] Rollback plan prepared
- [ ] Team notified

### Safe Production Migration

```bash
# 1. Backup database
pg_dump -U lmanagement lmanagement > prod_backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Dry run to verify
python manage.py check_db_structure
python manage.py migrate --plan

# 3. Apply migrations
python manage.py migrate

# 4. Verify structure
python manage.py check_db_structure --verbose

# 5. Sync data (if needed)
python manage.py sync_from_ge_server --data-only
```

## Additional Resources

- Django Migrations: https://docs.djangoproject.com/en/5.0/topics/migrations/
- PostgreSQL Backup: https://www.postgresql.org/docs/current/backup-dump.html
- Project-specific migration docs: See migration files in each app's `migrations/` folder

## Support

For issues or questions:
1. Check this guide first
2. Run `python manage.py <command> --help` for command-specific help
3. Review Django documentation
4. Contact development team
