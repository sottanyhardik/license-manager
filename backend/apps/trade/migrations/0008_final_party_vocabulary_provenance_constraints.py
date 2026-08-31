from django.db import migrations, models
from django.db.models import Q


def migrate_vocabulary(apps, schema_editor):
    Trade = apps.get_model("trade", "LicenseTrade")
    Trade.objects.filter(final_party_status="FINAL").update(final_party_status="FINAL_PARTY")
    Trade.objects.filter(final_party_status="INTERMEDIATE").update(final_party_status="INTERLINKED")
    Trade.objects.filter(final_party_status="INTERLINKED").update(
        final_party_classification_provenance="CANONICAL_TRANSACTION_GRAPH_INTERLINK",
        final_party_resolution_note="Deterministic canonical transaction-graph backfill. CANONICAL_TRANSACTION_GRAPH_INTERLINK",
    )


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("trade", "0007_licensetrade_final_party_classification")]
    operations = [
        migrations.AlterField(model_name="licensetrade", name="final_party_status", field=models.CharField(max_length=16, db_index=True, default="UNKNOWN", help_text="Explicit final-party classification for SALE invoice packaging.", choices=[("UNKNOWN", "Final party not classified"), ("FINAL_PARTY", "Final purchasing party"), ("INTERLINKED", "Interlinked or intermediate party")])),
        migrations.AddField(model_name="licensetrade", name="final_party_classification_provenance", field=models.CharField(max_length=64, blank=True, default='', help_text="Stable canonical-graph or authorised-resolution provenance for this classification.")),
        migrations.RunPython(migrate_vocabulary, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="licensetrade", constraint=models.CheckConstraint(name="chk_final_party_classification_valid", condition=models.Q(models.Q(("direction", "SALE"), ("final_party__isnull", False), ("final_party_classification_provenance__gt", ""), ("final_party_status", "FINAL_PARTY")), models.Q(("direction", "SALE"), ("final_party__isnull", True), ("final_party_status__in", ["UNKNOWN", "INTERLINKED"])), models.Q(models.Q(("direction", "SALE"), _negated=True), ("final_party__isnull", True), ("final_party_status", "UNKNOWN")), _connector="OR"))),
    ]
