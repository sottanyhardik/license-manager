"""
Data migration: add the ACCOUNT_ACCESS role Group.

Users with ACCOUNT_ACCESS can view the BOE list and update the
invoice_no field inline — they cannot create, fully edit, or delete BOEs.
"""
from django.db import migrations


def add_account_access_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='ACCOUNT_ACCESS')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_add_ledger_manager_group'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(add_account_access_group, noop),
    ]
