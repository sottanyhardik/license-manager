"""TDS configuration. No statutory rates are seeded: rates/thresholds are entered and dated by the accountant."""
from django.db import models

from apps.core.models import AuditModel, CompanyModel


class TdsSection(AuditModel):
    FULL, EXCESS = "FULL", "EXCESS"
    code = models.CharField(max_length=16, help_text="e.g. 194Q, 194H, 194J, 194A")
    description = models.CharField(max_length=200)
    rate_individual = models.DecimalField(max_digits=6, decimal_places=3, help_text="% for PAN category P/H")
    rate_other = models.DecimalField(max_digits=6, decimal_places=3, help_text="% for companies, firms, LLPs, others")
    rate_no_pan = models.DecimalField(max_digits=6, decimal_places=3)
    threshold_single = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    threshold_aggregate = models.DecimalField(max_digits=20, decimal_places=2, default=0, help_text="Per party per FY")
    threshold_mode = models.CharField(
        max_length=6, choices=[(FULL, "Whole amount once crossed"), (EXCESS, "Only amount above threshold")], default=FULL,
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["code", "-effective_from"]
        constraints = [models.UniqueConstraint(fields=["code", "effective_from"], name="acct_tds_unique_version")]

    def __str__(self) -> str:
        return f"{self.code} from {self.effective_from}"


class LowerDeductionCertificate(AuditModel):
    party = models.ForeignKey(CompanyModel, on_delete=models.PROTECT, related_name="+")
    section_code = models.CharField(max_length=16)
    certificate_no = models.CharField(max_length=64)
    rate = models.DecimalField(max_digits=6, decimal_places=3)
    valid_from = models.DateField()
    valid_to = models.DateField()
    amount_limit = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-valid_from"]
