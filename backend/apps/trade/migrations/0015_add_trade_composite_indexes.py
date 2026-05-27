"""
Migration: Add composite indexes to LicenseTrade for common filter patterns.

Indexes added:
- (invoice_date) — date-range filtering
- (direction, invoice_date) — ledger list: filter by direction + date range
- (direction, from_company) — ledger: purchases per supplier
- (direction, to_company) — ledger: sales per buyer
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trade', '0014_add_linked_trade'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='licensetrade',
            index=models.Index(fields=['invoice_date'], name='trade_invoice_date_idx'),
        ),
        migrations.AddIndex(
            model_name='licensetrade',
            index=models.Index(fields=['direction', 'invoice_date'], name='trade_dir_date_idx'),
        ),
        migrations.AddIndex(
            model_name='licensetrade',
            index=models.Index(fields=['direction', 'from_company'], name='trade_dir_from_co_idx'),
        ),
        migrations.AddIndex(
            model_name='licensetrade',
            index=models.Index(fields=['direction', 'to_company'], name='trade_dir_to_co_idx'),
        ),
    ]
