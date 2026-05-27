# Generated manually to cleanup orphaned columns and fix field constraints

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0007_add_is_restricted_field'),
    ]

    operations = [
        # Remove orphaned is_restrict column (replaced by is_restricted)
        migrations.RunSQL(
            sql='ALTER TABLE license_licenseimportitemsmodel DROP COLUMN IF EXISTS is_restrict;',
            reverse_sql='ALTER TABLE license_licenseimportitemsmodel ADD COLUMN is_restrict BOOLEAN NOT NULL DEFAULT FALSE;',
        ),
    ]
