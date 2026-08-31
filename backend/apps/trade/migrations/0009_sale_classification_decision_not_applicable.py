from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("trade", "0008_final_party_vocabulary_provenance_constraints")]
    operations = [
        migrations.RemoveConstraint(model_name="licensetrade", name="chk_final_party_classification_valid"),
        migrations.AlterField(model_name="licensetrade", name="final_party_status", field=models.CharField(max_length=16, db_index=True, default="UNKNOWN", choices=[("UNKNOWN", "Final party not classified"), ("FINAL_PARTY", "Final purchasing party"), ("INTERLINKED", "Interlinked or intermediate party"), ("NOT_APPLICABLE", "No qualifying final-party sale")])),
        migrations.AddConstraint(model_name="licensetrade", constraint=models.CheckConstraint(name="chk_final_party_classification_valid", condition=Q(Q(("direction", "SALE"), ("final_party__isnull", False), ("final_party_classification_provenance__gt", ""), ("final_party_status", "FINAL_PARTY")), Q(("direction", "SALE"), ("final_party__isnull", True), ("final_party_status__in", ["UNKNOWN", "INTERLINKED", "NOT_APPLICABLE"])), Q(Q(("direction", "SALE"), _negated=True), ("final_party__isnull", True), ("final_party_status", "UNKNOWN")), _connector="OR"))),
        migrations.CreateModel(name="SaleClassificationDecision", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("decision", models.CharField(max_length=16, choices=[("FINAL_PARTY", "Final party"), ("INTERLINKED", "Interlinked"), ("NOT_APPLICABLE", "Not applicable")])),
            ("reason", models.TextField()), ("provenance", models.CharField(max_length=255)),
            ("licence_ids", models.JSONField(default=list, blank=True)), ("decided_at", models.DateTimeField(auto_now_add=True)),
            ("decided_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sale_classification_decisions", to=settings.AUTH_USER_MODEL)),
            ("trade", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="classification_decisions", to="trade.licensetrade")),
        ], options={"ordering": ("-decided_at", "-pk")}),
    ]
