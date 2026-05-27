"""
Data migration: add the TL_GENERATE role Group.

Users with TL_GENERATE can generate and view transfer letters for
BOE, Allotment, and Trade records without needing full manager/viewer access.
"""
from django.db import migrations


def add_tl_generate_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='TL_GENERATE')


def noop(apps, schema_editor):
    pass  # Do not delete on reverse — may have assigned users


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_create_role_groups'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(add_tl_generate_group, noop),
    ]
