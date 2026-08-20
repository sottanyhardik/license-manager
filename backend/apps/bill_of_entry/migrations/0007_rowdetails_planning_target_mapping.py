from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("bill_of_entry", "0006_alter_billofentrymodel_company_and_more"), ("core", "0011_split_milk_into_swp_dwp_wpc")]
    operations = [
        migrations.AddField(model_name="rowdetails", name="planning_target_item", field=models.ForeignKey(blank=True, db_index=True, help_text="Canonical planning target selected for this actual usage.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="boe_actual_usage", to="core.itemnamemodel")),
        migrations.AddField(model_name="rowdetails", name="planning_mapping_status", field=models.CharField(choices=[("MAPPED_EXPLICIT", "Mapped explicitly"), ("MAPPED_DETERMINISTIC", "Mapped from a unique target"), ("UNMAPPED_AMBIGUOUS", "Target is ambiguous")], db_index=True, default="UNMAPPED_AMBIGUOUS", max_length=32)),
        migrations.AddField(model_name="rowdetails", name="planning_mapping_source", field=models.CharField(blank=True, default="", max_length=32)),
    ]
