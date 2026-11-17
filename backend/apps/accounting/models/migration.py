"""Historical-data migration runs (dry runs and executions) with per-record outcomes."""
from django.db import models

from apps.core.models import AuditModel

from .books import EntityBooks


class MigrationRun(AuditModel):
    DRY_RUN, EXECUTE = "DRY_RUN", "EXECUTE"
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="migration_runs")
    mode = models.CharField(max_length=8, choices=[(DRY_RUN, "Dry run"), (EXECUTE, "Execute")])
    parameters = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-id"]


class MigrationItem(models.Model):
    run = models.ForeignKey(MigrationRun, on_delete=models.CASCADE, related_name="items")
    source_type = models.CharField(max_length=24)  # TRADE | TRADE_PAYMENT
    source_id = models.BigIntegerField()
    classification = models.CharField(max_length=20)
    outcome = models.CharField(max_length=20, blank=True)
    reasons = models.JSONField(default=list, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    financial_year = models.CharField(max_length=9, blank=True)

    class Meta:
        ordering = ["run_id", "id"]
        indexes = [models.Index(fields=["source_type", "source_id"])]
