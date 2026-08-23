# Generated manually: additive paired-transaction integrity fields.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('trade', '0005_invoicedocumentaccesstoken_invoicedocumentauditevent_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='licensetrade', name='transaction_pair_uuid',
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='licensetrade', name='counterpart',
            field=models.OneToOneField(blank=True, editable=False, help_text='Reciprocal immutable Sale↔Purchase counterpart.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='counterpart_of', to='trade.licensetrade'),
        ),
        migrations.AddField(
            model_name='licensetrade', name='copied_from',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='copies_created', to='trade.licensetrade'),
        ),
        migrations.AddField(
            model_name='licensetrade', name='copied_from_type',
            field=models.CharField(blank=True, default='', editable=False, max_length=20),
        ),
        migrations.AddField(
            model_name='licensetrade', name='source_document_number',
            field=models.CharField(blank=True, default='', editable=False, max_length=128),
        ),
        migrations.AddField(
            model_name='licensetradeline', name='counterpart_line',
            field=models.OneToOneField(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='counterpart_of_line', to='trade.licensetradeline'),
        ),
        migrations.AddField(
            model_name='licensetradeline', name='transaction_pair_uuid',
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.CreateModel(
            name='TradePairAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pair_uuid', models.UUIDField(db_index=True)),
                ('action', models.CharField(max_length=32)),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
                ('counterpart', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pair_audit_as_counterpart', to='trade.licensetrade')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pair_audit_as_source', to='trade.licensetrade')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-occurred_at', '-id']},
        ),
    ]
