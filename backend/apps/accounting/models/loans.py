"""Loans given/taken. Principal and accrued interest each live in their own ledger account."""
from django.db import models

from apps.core.models import AuditModel, CompanyModel

from .banking import BankAccount
from .books import EntityBooks
from .coa import Account
from .vouchers import Voucher


class Loan(AuditModel):
    GIVEN, TAKEN = "GIVEN", "TAKEN"
    ACTIVE, CLOSED = "ACTIVE", "CLOSED"
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="loans")
    party = models.ForeignKey(CompanyModel, on_delete=models.PROTECT, related_name="+")
    direction = models.CharField(max_length=5, choices=[(GIVEN, "Loan given"), (TAKEN, "Loan taken")])
    loan_type = models.CharField(max_length=40, blank=True)
    principal = models.DecimalField(max_digits=20, decimal_places=2, help_text="Sanctioned principal")
    interest_rate = models.DecimalField(max_digits=7, decimal_places=4, help_text="Annual %")
    compound = models.BooleanField(default=False, help_text="Charge interest on unpaid accrued interest")
    accrual_frequency = models.CharField(
        max_length=8, choices=[("MONTHLY", "Monthly"), ("DAILY", "Daily (posted monthly)")], default="MONTHLY"
    )
    repayment_type = models.CharField(
        max_length=8, choices=[("EMI", "EMI"), ("BULLET", "Bullet"), ("FLEXIBLE", "Flexible")], default="FLEXIBLE"
    )
    tenure_months = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField()
    maturity_date = models.DateField(null=True, blank=True)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="+")
    principal_account = models.OneToOneField(Account, on_delete=models.PROTECT, related_name="loan_principal")
    interest_account = models.OneToOneField(Account, on_delete=models.PROTECT, related_name="loan_interest")
    status = models.CharField(max_length=6, choices=[(ACTIVE, "Active"), (CLOSED, "Closed")], default=ACTIVE)
    closed_on = models.DateField(null=True, blank=True)
    agreement = models.FileField(upload_to="accounting/loans/", null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(principal__gt=0), name="acct_loan_principal_positive"),
            models.CheckConstraint(condition=models.Q(interest_rate__gte=0), name="acct_loan_rate_non_negative"),
        ]

    def __str__(self) -> str:
        return f"Loan#{self.pk} {self.direction} {self.party_id}"


class LoanAccrual(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="accruals")
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    voucher = models.OneToOneField(Voucher, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["loan_id", "period_end"]
        constraints = [models.UniqueConstraint(fields=["loan", "period_end"], name="acct_accrual_unique_period")]
