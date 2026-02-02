# Generated manually for performance optimization
# Adds composite indexes for common query patterns

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('license', '0022_remove_licensedetailsmodel_license_lic_purchas_97c381_idx'),
        ('core', '0030_add_composite_performance_indexes'),  # Ensure core indexes are added first
    ]

    operations = [
        # ===================================================================
        # LicenseDetailsModel - Composite indexes for frequent filter combos
        # ===================================================================

        # Index for active licenses with balance filtering (item reports, dashboard)
        # Query: .filter(is_active=True, balance_cif__gte=200)
        migrations.AddIndex(
            model_name='licensedetailsmodel',
            index=models.Index(
                fields=['is_active', 'balance_cif'],
                name='license_active_balance_idx'
            ),
        ),

        # Index for active licenses with expiry filtering (most common filter)
        # Query: .filter(is_active=True, license_expiry_date__gt=today)
        migrations.AddIndex(
            model_name='licensedetailsmodel',
            index=models.Index(
                fields=['is_active', 'license_expiry_date'],
                name='license_active_expiry_idx'
            ),
        ),

        # Index for purchase status + expiry filtering (reports with status)
        # Query: .filter(purchase_status__in=[...], license_expiry_date__gt=...)
        migrations.AddIndex(
            model_name='licensedetailsmodel',
            index=models.Index(
                fields=['purchase_status_id', 'license_expiry_date'],
                name='license_status_expiry_idx'
            ),
        ),

        # Index for purchase status + active + balance (item report filters)
        # Query: .filter(purchase_status__in=[...], is_active=True, balance_cif__gte=...)
        migrations.AddIndex(
            model_name='licensedetailsmodel',
            index=models.Index(
                fields=['purchase_status_id', 'is_active', 'balance_cif'],
                name='license_status_active_bal_idx'
            ),
        ),

        # Index for exporter + active status (company-specific active licenses)
        # Query: .filter(exporter=company, is_active=True)
        migrations.AddIndex(
            model_name='licensedetailsmodel',
            index=models.Index(
                fields=['exporter_id', 'is_active', 'license_expiry_date'],
                name='license_exporter_active_idx'
            ),
        ),

        # Index for port + active status (port-specific reports)
        # Query: .filter(port=port, is_active=True, license_expiry_date__gt=...)
        migrations.AddIndex(
            model_name='licensedetailsmodel',
            index=models.Index(
                fields=['port_id', 'is_active', 'license_expiry_date'],
                name='license_port_active_idx'
            ),
        ),

        # Index for null/expired licenses (cleanup queries)
        # Query: .filter(is_null=False, is_expired=False)
        migrations.AddIndex(
            model_name='licensedetailsmodel',
            index=models.Index(
                fields=['is_null', 'is_expired', 'license_expiry_date'],
                name='license_null_expired_idx'
            ),
        ),

        # ===================================================================
        # LicenseImportItemsModel - Composite indexes for item reports
        # ===================================================================

        # Index for license + item filtering (item report queries)
        # Query: .filter(license__is_active=True, items__in=[...])
        migrations.AddIndex(
            model_name='licenseimportitemsmodel',
            index=models.Index(
                fields=['license_id', 'is_restricted'],
                name='import_item_license_restr_idx'
            ),
        ),

        # Index for serial number lookup (frequently used in joins)
        migrations.AddIndex(
            model_name='licenseimportitemsmodel',
            index=models.Index(
                fields=['license_id', 'serial_number'],
                name='import_item_serial_idx'
            ),
        ),

        # Index for HS code filtering
        migrations.AddIndex(
            model_name='licenseimportitemsmodel',
            index=models.Index(
                fields=['hs_code_id', 'license_id'],
                name='import_item_hscode_idx'
            ),
        ),

        # ===================================================================
        # LicenseExportItemModel - Composite indexes for export queries
        # ===================================================================

        # Index for license + norm class (export item filtering)
        migrations.AddIndex(
            model_name='licenseexportitemmodel',
            index=models.Index(
                fields=['license_id', 'norm_class_id'],
                name='export_item_norm_idx'
            ),
        ),

        # Index for license + item lookup
        migrations.AddIndex(
            model_name='licenseexportitemmodel',
            index=models.Index(
                fields=['license_id', 'item_id'],
                name='export_item_license_idx'
            ),
        ),

        # ===================================================================
        # LicenseTransferModel - Composite indexes for transfer tracking
        # ===================================================================

        # Index for license transfers ordered by date (transfer history)
        migrations.AddIndex(
            model_name='licensetransfermodel',
            index=models.Index(
                fields=['license_id', '-transfer_date'],
                name='transfer_license_date_idx'
            ),
        ),

        # Index for company transfer lookups
        migrations.AddIndex(
            model_name='licensetransfermodel',
            index=models.Index(
                fields=['to_company_id', 'transfer_date'],
                name='transfer_to_company_idx'
            ),
        ),

        migrations.AddIndex(
            model_name='licensetransfermodel',
            index=models.Index(
                fields=['from_company_id', 'transfer_date'],
                name='transfer_from_company_idx'
            ),
        ),
    ]
