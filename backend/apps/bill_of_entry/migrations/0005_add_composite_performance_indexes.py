# Generated manually for performance optimization
# Adds composite indexes for bill_of_entry and rowdetails models

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('bill_of_entry', '0004_add_performance_indexes'),
        ('core', '0030_add_composite_performance_indexes'),
    ]

    operations = [
        # ===================================================================
        # BillOfEntryModel - Composite indexes for BOE queries
        # ===================================================================

        # Index for company + date filtering (company-specific BOE reports)
        # Query: .filter(company=company, bill_of_entry_date__gte=start_date)
        migrations.AddIndex(
            model_name='billofentrymodel',
            index=models.Index(
                fields=['company_id', '-bill_of_entry_date'],
                name='boe_company_date_desc_idx'
            ),
        ),

        # Index for port + date filtering (port-specific BOE reports)
        migrations.AddIndex(
            model_name='billofentrymodel',
            index=models.Index(
                fields=['port_id', '-bill_of_entry_date'],
                name='boe_port_date_desc_idx'
            ),
        ),

        # Index for invoice tracking (invoice-based queries)
        # Query: .filter(invoice_no=..., invoice_date=...)
        migrations.AddIndex(
            model_name='billofentrymodel',
            index=models.Index(
                fields=['invoice_no', 'invoice_date', 'company_id'],
                name='boe_invoice_company_idx'
            ),
        ),

        # Index for fetch status filtering (pending import queries)
        # Query: .filter(is_fetch=False, bill_of_entry_date__gte=...)
        migrations.AddIndex(
            model_name='billofentrymodel',
            index=models.Index(
                fields=['is_fetch', '-bill_of_entry_date'],
                name='boe_fetch_date_idx'
            ),
        ),

        # Index for product-based searches
        migrations.AddIndex(
            model_name='billofentrymodel',
            index=models.Index(
                fields=['product_name', 'company_id'],
                name='boe_product_company_idx'
            ),
        ),

        # Index for company + port + date (comprehensive filtering)
        migrations.AddIndex(
            model_name='billofentrymodel',
            index=models.Index(
                fields=['company_id', 'port_id', '-bill_of_entry_date'],
                name='boe_company_port_date_idx'
            ),
        ),

        # ===================================================================
        # RowDetails - Composite indexes for line item queries
        # ===================================================================

        # Index for license item lookups (most critical for balance calculations)
        # Query: .filter(sr_number__license=license, transaction_type='DEBIT')
        migrations.AddIndex(
            model_name='rowdetails',
            index=models.Index(
                fields=['sr_number_id', 'transaction_type'],
                name='row_sr_transaction_idx'
            ),
        ),

        # Index for BOE line items (BOE detail views)
        # Query: .filter(bill_of_entry=boe).order_by('sr_number')
        migrations.AddIndex(
            model_name='rowdetails',
            index=models.Index(
                fields=['bill_of_entry_id', 'sr_number_id'],
                name='row_boe_sr_idx'
            ),
        ),

        # Index for transaction type filtering (debit/credit reports)
        migrations.AddIndex(
            model_name='rowdetails',
            index=models.Index(
                fields=['transaction_type', 'bill_of_entry_id'],
                name='row_transaction_boe_idx'
            ),
        ),

        # Index for row type filtering
        migrations.AddIndex(
            model_name='rowdetails',
            index=models.Index(
                fields=['row_type', 'bill_of_entry_id'],
                name='row_type_boe_idx'
            ),
        ),

        # Critical composite index for balance calculations
        # Covers: license item + transaction type + CIF aggregations
        migrations.AddIndex(
            model_name='rowdetails',
            index=models.Index(
                fields=['sr_number_id', 'transaction_type', 'bill_of_entry_id'],
                name='row_balance_calc_idx'
            ),
        ),
    ]
