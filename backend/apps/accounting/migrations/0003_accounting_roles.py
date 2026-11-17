"""Create the accounting role groups (additive). Reverse is a no-op so members are never dropped."""
from django.db import migrations

ROLES = ("ACCOUNTS_VIEWER", "ACCOUNTS_MANAGER", "ACCOUNTS_APPROVER")


def create_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLES:
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("accounting", "0002_ledger_integrity_triggers"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(create_roles, migrations.RunPython.noop)]
