from django.db import migrations, models
import django.db.models.deletion
from django.db.models import F


def backfill_trade_ids(apps, schema_editor):
    TradePairAudit = apps.get_model('trade', 'TradePairAudit')
    TradePairAudit.objects.filter(source_trade_id__isnull=True).update(source_trade_id=F('source_id'))
    TradePairAudit.objects.filter(counterpart_trade_id__isnull=True).update(counterpart_trade_id=F('counterpart_id'))


class Migration(migrations.Migration):

    dependencies = [
        ('trade', '0010_alter_licensetrade_final_party_status_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tradepairaudit',
            name='source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pair_audit_as_source', to='trade.licensetrade'),
        ),
        migrations.AlterField(
            model_name='tradepairaudit',
            name='counterpart',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pair_audit_as_counterpart', to='trade.licensetrade'),
        ),
        migrations.AddField(
            model_name='tradepairaudit',
            name='source_trade_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tradepairaudit',
            name='counterpart_trade_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tradepairaudit',
            name='detail',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(backfill_trade_ids, migrations.RunPython.noop),
    ]
