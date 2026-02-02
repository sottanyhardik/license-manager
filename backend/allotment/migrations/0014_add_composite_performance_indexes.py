# Generated manually for performance optimization
# Adds composite indexes for allotment models

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('allotment', '0013_allotmentmodel_is_approved'),
        ('core', '0030_add_composite_performance_indexes'),
    ]

    operations = [
        # ===================================================================
        # AllotmentModel - Composite indexes for allotment queries
        # ===================================================================

        # Index for company + arrival date filtering (most common query)
        # Query: .filter(company=company, estimated_arrival_date__gte=date)
        migrations.AddIndex(
            model_name='allotmentmodel',
            index=models.Index(
                fields=['company_id', 'estimated_arrival_date'],
                name='allot_company_arrival_idx'
            ),
        ),

        # Index for port + arrival date filtering
        migrations.AddIndex(
            model_name='allotmentmodel',
            index=models.Index(
                fields=['port_id', 'estimated_arrival_date'],
                name='allot_port_arrival_idx'
            ),
        ),

        # Index for BOE status filtering (allotments linked to BOE)
        # Query: .filter(is_boe=True, is_allotted=True)
        migrations.AddIndex(
            model_name='allotmentmodel',
            index=models.Index(
                fields=['is_boe', 'is_allotted', 'estimated_arrival_date'],
                name='allot_boe_status_date_idx'
            ),
        ),

        # Index for allotment type + company (type-specific company queries)
        migrations.AddIndex(
            model_name='allotmentmodel',
            index=models.Index(
                fields=['type', 'company_id', 'estimated_arrival_date'],
                name='allot_type_company_idx'
            ),
        ),

        # Index for invoice tracking
        migrations.AddIndex(
            model_name='allotmentmodel',
            index=models.Index(
                fields=['invoice', 'company_id'],
                name='allot_invoice_company_idx'
            ),
        ),

        # Index for related company tracking (transfer allotments)
        migrations.AddIndex(
            model_name='allotmentmodel',
            index=models.Index(
                fields=['related_company_id', 'estimated_arrival_date'],
                name='allot_related_company_idx'
            ),
        ),

        # Index for approval status filtering
        migrations.AddIndex(
            model_name='allotmentmodel',
            index=models.Index(
                fields=['is_approved', 'company_id', 'estimated_arrival_date'],
                name='allot_approved_company_idx'
            ),
        ),

        # Comprehensive index for pending allotments (without BOE)
        # Query: .filter(is_boe=False, is_allotted=True, company=...)
        migrations.AddIndex(
            model_name='allotmentmodel',
            index=models.Index(
                fields=['is_boe', 'company_id', '-estimated_arrival_date'],
                name='allot_pending_company_idx'
            ),
        ),

        # ===================================================================
        # AllotmentItems - Composite indexes for allotment line items
        # ===================================================================

        # Critical index for balance calculations (license item + allotment)
        # Query: .filter(item__license=license, allotment__bill_of_entry__isnull=True)
        migrations.AddIndex(
            model_name='allotmentitems',
            index=models.Index(
                fields=['item_id', 'allotment_id'],
                name='allot_item_allotment_idx'
            ),
        ),

        # Index for allotment line item lookups
        migrations.AddIndex(
            model_name='allotmentitems',
            index=models.Index(
                fields=['allotment_id', 'item_id'],
                name='allot_detail_lookup_idx'
            ),
        ),

        # Index for quantity-based queries (large allotments)
        migrations.AddIndex(
            model_name='allotmentitems',
            index=models.Index(
                fields=['allotment_id', 'qty'],
                name='allot_item_qty_idx'
            ),
        ),
    ]
