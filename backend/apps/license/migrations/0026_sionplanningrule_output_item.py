from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("license", "0025_licenseitemplan_allocation_provenance")]

    operations = [
        migrations.AddField(
            model_name="sionplanningrule",
            name="output_item",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sion_planning_rules",
                to="core.itemnamemodel",
                help_text="Where matched items are allocated to",
            ),
        ),
    ]
