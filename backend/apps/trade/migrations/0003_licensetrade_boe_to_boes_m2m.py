# Generated for License Manager: convert LicenseTrade.boe (FK) to
# LicenseTrade.boes (ManyToMany), preserving existing links via a data
# migration before the old column is dropped.

from django.db import migrations, models


def copy_boe_fk_to_boes_m2m(apps, schema_editor):
    """Copy each trade's existing single boe_id into the new boes M2M."""
    LicenseTrade = apps.get_model('trade', 'LicenseTrade')
    trades_with_boe = LicenseTrade.objects.filter(boe_id__isnull=False)
    for trade in trades_with_boe.iterator():
        trade.boes.add(trade.boe_id)


def copy_boes_m2m_to_boe_fk(apps, schema_editor):
    """Reverse: copy the first linked BOE (if any) back onto the boe FK."""
    LicenseTrade = apps.get_model('trade', 'LicenseTrade')
    for trade in LicenseTrade.objects.prefetch_related('boes').iterator():
        first_boe = trade.boes.first()
        if first_boe is not None:
            trade.boe_id = first_boe.id
            trade.save(update_fields=['boe_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('bill_of_entry', '0003_alter_billofentrymodel_unique_together'),
        ('trade', '0002_alter_licensetrade_created_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensetrade',
            name='boes',
            field=models.ManyToManyField(blank=True, related_name='license_trades', to='bill_of_entry.billofentrymodel'),
        ),
        migrations.RunPython(copy_boe_fk_to_boes_m2m, copy_boes_m2m_to_boe_fk),
        migrations.RemoveField(
            model_name='licensetrade',
            name='boe',
        ),
    ]
