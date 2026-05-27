"""
Migration: Fix nullable name fields on CompanyModel and PortModel.

Strategy:
1. Backfill NULL values with empty string (RunPython)
2. AlterField to remove null=True

atomic = False is required because PostgreSQL raises
  "cannot ALTER TABLE because it has pending trigger events"
when a DDL statement (AlterField) follows a DML statement (UPDATE in RunPython)
inside the same transaction.  With atomic=False each operation commits before
the next one begins, so the trigger queue is flushed before the ALTER TABLE runs.
"""
from django.db import migrations, models


def backfill_nulls(apps, schema_editor):
    CompanyModel = apps.get_model('core', 'CompanyModel')
    PortModel = apps.get_model('core', 'PortModel')
    CompanyModel.objects.filter(name__isnull=True).update(name='')
    CompanyModel.objects.filter(address_line_1__isnull=True).update(address_line_1='')
    CompanyModel.objects.filter(address_line_2__isnull=True).update(address_line_2='')
    PortModel.objects.filter(name__isnull=True).update(name='')


def reverse_backfill(apps, schema_editor):
    # Reversal: convert empty strings back to NULL (best-effort)
    CompanyModel = apps.get_model('core', 'CompanyModel')
    PortModel = apps.get_model('core', 'PortModel')
    CompanyModel.objects.filter(name='').update(name=None)
    CompanyModel.objects.filter(address_line_1='').update(address_line_1=None)
    CompanyModel.objects.filter(address_line_2='').update(address_line_2=None)
    PortModel.objects.filter(name='').update(name=None)


class Migration(migrations.Migration):

    # Required: RunPython (UPDATE) and AlterField (DDL) cannot share a transaction
    # on PostgreSQL when deferred trigger events are pending.
    atomic = False

    dependencies = [
        ('core', '0032_remove_companymodel_company_iec_name_idx_and_more'),
    ]

    operations = [
        # Step 1: Backfill NULLs before removing null constraint
        migrations.RunPython(backfill_nulls, reverse_backfill),

        # Step 2: CompanyModel.name → NOT NULL, default ''
        migrations.AlterField(
            model_name='companymodel',
            name='name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),

        # Step 3: CompanyModel.address_line_1 → NOT NULL, default ''
        migrations.AlterField(
            model_name='companymodel',
            name='address_line_1',
            field=models.TextField(blank=True, default=''),
        ),

        # Step 4: CompanyModel.address_line_2 → NOT NULL, default ''
        migrations.AlterField(
            model_name='companymodel',
            name='address_line_2',
            field=models.TextField(blank=True, default=''),
        ),

        # Step 5: PortModel.name → NOT NULL, default ''
        migrations.AlterField(
            model_name='portmodel',
            name='name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
