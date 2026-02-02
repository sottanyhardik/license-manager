# Generated manually for performance optimization
# Adds composite indexes for core master data models

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0029_populate_purchase_status_data'),
    ]

    operations = [
        # ===================================================================
        # ItemNameModel - Composite indexes for item lookups
        # ===================================================================

        # Index for active items by group (item selection queries)
        # Query: .filter(is_active=True, group=group)
        migrations.AddIndex(
            model_name='itemnamemodel',
            index=models.Index(
                fields=['is_active', 'group_id', 'display_order'],
                name='item_active_group_order_idx'
            ),
        ),

        # Index for SION norm class filtering (restriction-based queries)
        # Query: .filter(sion_norm_class=norm, is_active=True)
        migrations.AddIndex(
            model_name='itemnamemodel',
            index=models.Index(
                fields=['sion_norm_class_id', 'is_active'],
                name='item_sion_active_idx'
            ),
        ),

        # Index for restriction percentage filtering
        migrations.AddIndex(
            model_name='itemnamemodel',
            index=models.Index(
                fields=['restriction_percentage', 'is_active'],
                name='item_restriction_active_idx'
            ),
        ),

        # Index for display ordering (report generation)
        migrations.AddIndex(
            model_name='itemnamemodel',
            index=models.Index(
                fields=['display_order', 'group_id'],
                name='item_order_group_idx'
            ),
        ),

        # ===================================================================
        # HSCodeModel - Composite indexes for HS code lookups
        # ===================================================================

        # Index for HS code + unit price (pricing queries)
        migrations.AddIndex(
            model_name='hscodemodel',
            index=models.Index(
                fields=['hs_code', 'unit_price'],
                name='hscode_code_price_idx'
            ),
        ),

        # Index for unit-based filtering
        migrations.AddIndex(
            model_name='hscodemodel',
            index=models.Index(
                fields=['unit', 'hs_code'],
                name='hscode_unit_code_idx'
            ),
        ),

        # ===================================================================
        # SionNormClassModel - Composite indexes for norm class lookups
        # ===================================================================

        # Index for active norm classes by head (norm selection queries)
        # Query: .filter(is_active=True, head_norm=head)
        migrations.AddIndex(
            model_name='sionnormclassmodel',
            index=models.Index(
                fields=['is_active', 'head_norm_id'],
                name='sion_active_head_idx'
            ),
        ),

        # Index for norm class + active status (frequently used in filters)
        migrations.AddIndex(
            model_name='sionnormclassmodel',
            index=models.Index(
                fields=['norm_class', 'is_active'],
                name='sion_class_active_idx'
            ),
        ),

        # ===================================================================
        # CompanyModel - Composite indexes for company lookups
        # ===================================================================

        # Index for IEC + name (company search queries)
        migrations.AddIndex(
            model_name='companymodel',
            index=models.Index(
                fields=['iec', 'name'],
                name='company_iec_name_idx'
            ),
        ),

        # Index for PAN-based lookups
        migrations.AddIndex(
            model_name='companymodel',
            index=models.Index(
                fields=['pan', 'iec'],
                name='company_pan_iec_idx'
            ),
        ),

        # Index for GST-based lookups
        migrations.AddIndex(
            model_name='companymodel',
            index=models.Index(
                fields=['gst_number', 'iec'],
                name='company_gst_iec_idx'
            ),
        ),

        # ===================================================================
        # PurchaseStatus - Composite indexes for status lookups
        # ===================================================================

        # Index for active status filtering
        migrations.AddIndex(
            model_name='purchasestatus',
            index=models.Index(
                fields=['is_active', 'code'],
                name='status_active_code_idx'
            ),
        ),

        # ===================================================================
        # InvoiceEntity - Composite indexes for invoice tracking
        # ===================================================================

        # Index for company + invoice lookups
        migrations.AddIndex(
            model_name='invoiceentity',
            index=models.Index(
                fields=['company_id', 'invoice_no'],
                name='invoice_company_no_idx'
            ),
        ),

        # Index for invoice date range queries
        migrations.AddIndex(
            model_name='invoiceentity',
            index=models.Index(
                fields=['company_id', '-invoice_date'],
                name='invoice_company_date_idx'
            ),
        ),
    ]
