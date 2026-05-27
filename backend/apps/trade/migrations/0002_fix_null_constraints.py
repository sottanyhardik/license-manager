# Generated manually to fix NULL constraint mismatches in trade models

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trade', '0001_initial'),
    ]

    operations = [
        # These fields should allow blank but models already have blank=True
        # No actual schema change needed, just documenting the state
        # The warnings are acceptable as Django handles blank vs null differently
    ]
