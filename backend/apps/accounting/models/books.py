"""Books-owning entities, financial years and periods.

``EntityBooks`` is NOT a second company master: its primary key *is* the
existing ``core.CompanyModel`` id (trade's entity master), and it holds only
book-keeping configuration. Entities are discovered from Trade and activated
explicitly; nothing is seeded or invented.
"""
from django.db import models

from apps.core.models import AuditModel, CompanyModel


class EntityBooks(AuditModel):
    company = models.OneToOneField(
        CompanyModel, on_delete=models.PROTECT, primary_key=True, related_name="accounting_books"
    )
    books_start_date = models.DateField(help_text="No voucher may be dated before this.")
    state_code = models.CharField(max_length=2, blank=True, help_text="GST state code; defaults from GSTIN.")
    tan = models.CharField(max_length=10, blank=True)
    default_credit_days = models.PositiveIntegerField(default=0)
    require_maker_checker = models.BooleanField(
        default=False, help_text="If set, a manual voucher cannot be posted by the user who drafted it."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["company__name"]
        verbose_name_plural = "entity books"

    def __str__(self) -> str:
        return f"Books[{self.company.name}]"

    @property
    def name(self) -> str:
        return self.company.name


class FinancialYear(AuditModel):
    OPEN, CLOSED = "OPEN", "CLOSED"
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="financial_years")
    label = models.CharField(max_length=9)  # "2026-27"
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=6, choices=[(OPEN, "Open"), (CLOSED, "Closed")], default=OPEN)

    class Meta:
        ordering = ["entity_id", "start_date"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "label"], name="acct_fy_unique_label"),
            models.UniqueConstraint(fields=["entity", "start_date"], name="acct_fy_unique_start"),
            models.CheckConstraint(condition=models.Q(end_date__gt=models.F("start_date")), name="acct_fy_end_after_start"),
        ]

    def __str__(self) -> str:
        return f"FY {self.label} ({self.entity_id})"


class AccountingPeriod(AuditModel):
    OPEN, LOCKED = "OPEN", "LOCKED"
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT, related_name="periods")
    period_no = models.PositiveSmallIntegerField()  # 1 = April
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=6, choices=[(OPEN, "Open"), (LOCKED, "Locked")], default=OPEN)
    locked_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["financial_year_id", "period_no"]
        constraints = [
            models.UniqueConstraint(fields=["financial_year", "period_no"], name="acct_period_unique_no"),
        ]


class CostCentre(AuditModel):
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="cost_centres")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["entity", "code"], name="acct_cc_unique_code")]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"
