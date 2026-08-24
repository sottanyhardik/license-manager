from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("license", "0049_replan_request_scope")]

    operations = [
        migrations.AddField(
            model_name="licensedetailsmodel",
            name="individual_item_cif_override",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
    ]
