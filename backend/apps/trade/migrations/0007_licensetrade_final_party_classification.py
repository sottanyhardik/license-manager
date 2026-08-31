# Generated manually: explicit, auditable final-party classification.
import django.db.models.deletion
from django.db import migrations, models


def classify_known_intermediate_sales(apps, schema_editor):
    """Backfill only facts represented explicitly by existing relations.

    Unpaired historical sales remain UNKNOWN; guessing that they are final
    would make a package exporter disclose the wrong system invoice.
    """
    LicenseTrade = apps.get_model("trade", "LicenseTrade")
    LicenseTrade.objects.filter(
        direction="SALE",
    ).exclude(
        linked_trade__isnull=True,
        counterpart__isnull=True,
        copied_from__isnull=True,
        transaction_pair_uuid__isnull=True,
    ).update(final_party_status="INTERMEDIATE")


class Migration(migrations.Migration):
    dependencies = [("trade", "0006_paired_trade_counterparts")]

    operations = [
        migrations.AddField(
            model_name="licensetrade",
            name="final_party_status",
            field=models.CharField(
                choices=[
                    ("UNKNOWN", "Final party not classified"),
                    ("FINAL", "Final purchasing party"),
                    ("INTERMEDIATE", "Intermediate party"),
                ],
                db_index=True, default="UNKNOWN", max_length=16,
                help_text="Explicit final-party classification for SALE invoice packaging.",
            ),
        ),
        migrations.AddField(
            model_name="licensetrade",
            name="final_party",
            field=models.ForeignKey(
                blank=True, help_text="Explicit final purchasing party for a FINAL sale.",
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="final_party_sale_trades", to="core.companymodel",
            ),
        ),
        migrations.AddField(
            model_name="licensetrade",
            name="final_party_resolution_note",
            field=models.TextField(blank=True, default='', help_text="Auditable business reference used to classify the sale branch."),
        ),
        migrations.RunPython(classify_known_intermediate_sales, migrations.RunPython.noop),
    ]
