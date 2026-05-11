"""
Data migration: convert empty-string email '' → NULL on all User rows.

The User.email field is unique=True. PostgreSQL treats '' as a real value,
so multiple users with email='' violate the constraint.  NULL is excluded
from unique checks, which is the correct behaviour for an optional email.
"""
from django.db import migrations


def fix_empty_emails(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(email='').update(email=None)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_add_account_access_group'),
    ]

    operations = [
        migrations.RunPython(fix_empty_emails, noop),
    ]
