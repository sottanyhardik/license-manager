"""
Data migration: add the LEDGER_MANAGER role Group.

Users with LEDGER_MANAGER can view the license ledger, upload ledger files,
and download ledger PDFs — without needing full LICENSE_MANAGER access.
"""
from django.db import migrations


def add_ledger_manager_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='LEDGER_MANAGER')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_add_tl_generate_group'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(add_ledger_manager_group, noop),
    ]
