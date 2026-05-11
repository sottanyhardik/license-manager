"""
Data migration: create the 12 predefined role Groups.

Groups are used as roles throughout the permission system.  Each Group name
is a role code that matches the string constants in accounts/permissions.py.

This migration is idempotent (uses get_or_create) so it is safe to run more
than once.  The reverse is intentionally a no-op: groups are shared
infrastructure and deleting them would strip roles from all existing users.
"""
from django.db import migrations

ROLE_CODES = [
    'USER_MANAGER',
    'LICENSE_MANAGER',
    'LICENSE_VIEWER',
    'ALLOTMENT_MANAGER',
    'ALLOTMENT_VIEWER',
    'BOE_MANAGER',
    'BOE_VIEWER',
    'TRADE_MANAGER',
    'TRADE_VIEWER',
    'INCENTIVE_LICENSE_MANAGER',
    'INCENTIVE_LICENSE_VIEWER',
    'REPORT_VIEWER',
]


def create_role_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for code in ROLE_CODES:
        Group.objects.get_or_create(name=code)


def noop(apps, schema_editor):
    pass  # Do not delete groups on reverse — they may have users assigned.


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_add_avatar_to_user'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_role_groups, noop),
    ]
