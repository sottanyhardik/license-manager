from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("trade", "0003_licensetrade_boe_to_boes_m2m")]

    operations = [
        migrations.CreateModel(
            name="TradeInvoiceDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version_hash", models.CharField(max_length=64)),
                ("file", models.FileField(upload_to="trade/generated_sale_invoices/")),
                ("signed", models.BooleanField(default=False)),
                ("sale_bill_inr", models.DecimalField(decimal_places=2, max_digits=20)),
                ("generated_on", models.DateTimeField(auto_now_add=True)),
                ("trade", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="generated_invoice_documents", to="trade.licensetrade")),
            ],
            options={"ordering": ["-generated_on", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="tradeinvoicedocument",
            constraint=models.UniqueConstraint(fields=("trade", "version_hash"), name="uniq_trade_invoice_document_version"),
        ),
    ]
