from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("license", "0052_license_ledger_server_ready_states"), ("trade", "0009_sale_classification_decision_not_applicable")]

    operations = [
        migrations.AlterField(
            model_name="licenseledgerpackageitem", name="status",
            field=models.CharField(choices=[
                ("queued", "Queued"), ("generating", "Generating"),
                ("validating_sources", "Validating Sources"), ("merging", "Merging"),
                ("server_ready", "Server Ready"), ("failed", "Failed"),
                ("blocked_missing_purchase_document", "Blocked Missing Purchase Document"),
                ("blocked_unknown_sales_classification", "Blocked Unknown Sales Classification"),
                ("blocked_multiple_reasons", "Blocked Multiple Reasons"),
                ("blocked_missing_final_party_sales_invoice", "Blocked Missing Final Party Sales Invoice"),
            ], db_index=True, default="queued", max_length=48),
        ),
        migrations.CreateModel(
            name="LicenseLedgerRecoveryAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_storage_key", models.CharField(max_length=512)),
                ("source_checksum", models.CharField(max_length=64)),
                ("linked_document_key", models.CharField(blank=True, default="", max_length=512)),
                ("evidence", models.JSONField(default=dict)),
                ("matching_rule", models.CharField(max_length=128)),
                ("recovery_method", models.CharField(default="ORPHAN_LINK", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("trade", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_recovery_audits", to="trade.licensetrade")),
            ],
        ),
        migrations.AddIndex(model_name="licenseledgerrecoveryaudit", index=models.Index(fields=["trade", "created_at"], name="license_led_trade_i_0b20a4_idx")),
    ]
