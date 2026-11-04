# Additive, nullable batch identity for planning bulk actions.  No data is
# rewritten; existing replan ledger rows keep batch_id="" and no initiator.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("license", "0056_add_cif_restriction_percentage"),
    ]

    operations = [
        migrations.AddField(
            model_name="licensereplanrequest",
            name="batch_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=36),
        ),
        migrations.AddField(
            model_name="licensereplanrequest",
            name="initiated_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
