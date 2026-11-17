"""Vouchers, voucher lines, numbering and the append-only audit trail.

Posted vouchers are immutable: enforced in services AND by Postgres triggers
(migration 0002): balanced-on-commit, no edit/delete of posted rows except the
POSTED -> REVERSED status flip.
"""
from django.db import models

from apps.core.models import AuditModel

from .books import CostCentre, EntityBooks, FinancialYear
from .coa import Account


class VoucherType(models.TextChoices):
    PURCHASE = "PURCHASE", "Purchase"
    SALES = "SALES", "Sales"
    PAYMENT = "PAYMENT", "Payment"
    RECEIPT = "RECEIPT", "Receipt"
    CONTRA = "CONTRA", "Contra"
    JOURNAL = "JOURNAL", "Journal"
    DEBIT_NOTE = "DEBIT_NOTE", "Debit note"
    CREDIT_NOTE = "CREDIT_NOTE", "Credit note"
    EXPENSE = "EXPENSE", "Expense"
    COMMISSION = "COMMISSION", "Commission"
    LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT", "Loan disbursement"
    LOAN_REPAYMENT = "LOAN_REPAYMENT", "Loan repayment"
    INTEREST_ACCRUAL = "INTEREST_ACCRUAL", "Interest accrual"
    OPENING = "OPENING", "Opening balance"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"
    REVERSAL = "REVERSAL", "Reversal"


VOUCHER_PREFIX = {
    "PURCHASE": "PUR", "SALES": "SAL", "PAYMENT": "PAY", "RECEIPT": "RCT", "CONTRA": "CON", "JOURNAL": "JNL",
    "DEBIT_NOTE": "DN", "CREDIT_NOTE": "CN", "EXPENSE": "EXP", "COMMISSION": "COM", "LOAN_DISBURSEMENT": "LND",
    "LOAN_REPAYMENT": "LNR", "INTEREST_ACCRUAL": "INT", "OPENING": "OPN", "ADJUSTMENT": "ADJ", "REVERSAL": "REV",
}


class VoucherStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    POSTED = "POSTED", "Posted"
    REVERSED = "REVERSED", "Reversed"


#: Statuses whose lines count in the ledger (a reversed voucher stays; its reversal negates it).
LEDGER_STATUSES = (VoucherStatus.POSTED, VoucherStatus.REVERSED)


class VoucherSequence(models.Model):
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT)
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    voucher_type = models.CharField(max_length=20, choices=VoucherType.choices)
    next_number = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entity", "financial_year", "voucher_type"], name="acct_seq_unique"),
        ]


class Voucher(AuditModel):
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="vouchers")
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT, related_name="vouchers")
    voucher_type = models.CharField(max_length=20, choices=VoucherType.choices)
    number = models.CharField(max_length=40, null=True, blank=True)
    date = models.DateField()
    status = models.CharField(max_length=8, choices=VoucherStatus.choices, default=VoucherStatus.DRAFT)
    narration = models.TextField(blank=True)
    total = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    source_type = models.CharField(max_length=32, blank=True, help_text="INVOICE, PAYMENT, BANK_LINE, LOAN, MANUAL, ...")
    source_id = models.BigIntegerField(null=True, blank=True)
    source_event = models.CharField(max_length=40, blank=True)
    source_version = models.CharField(max_length=64, blank=True)
    idempotency_key = models.CharField(max_length=200, null=True, blank=True, unique=True)
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    posted_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    posted_at = models.DateTimeField(null=True, blank=True)
    attachment = models.FileField(upload_to="accounting/vouchers/%Y/%m/", null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "financial_year", "voucher_type", "number"],
                condition=models.Q(number__isnull=False), name="acct_voucher_unique_number",
            ),
        ]
        indexes = [
            models.Index(fields=["entity", "date"]),
            models.Index(fields=["source_type", "source_id"]),
            models.Index(fields=["entity", "status", "voucher_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.number or 'DRAFT'} {self.voucher_type} {self.date}"


class VoucherLine(models.Model):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField()
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="voucher_lines")
    debit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    narration = models.CharField(max_length=255, blank=True)
    trade = models.ForeignKey("trade.LicenseTrade", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    cost_centre = models.ForeignKey(CostCentre, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["voucher_id", "line_no"]
        constraints = [
            models.CheckConstraint(condition=models.Q(debit__gte=0) & models.Q(credit__gte=0), name="acct_line_non_negative"),
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0, credit=0) | models.Q(debit=0, credit__gt=0)), name="acct_line_one_side",
            ),
            models.UniqueConstraint(fields=["voucher", "line_no"], name="acct_line_unique_no"),
        ]
        indexes = [models.Index(fields=["account", "voucher"]), models.Index(fields=["trade"])]


class AccountingAuditEvent(models.Model):
    """Append-only audit of every sensitive accounting action (written in the same transaction)."""
    entity = models.ForeignKey(EntityBooks, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=40)
    object_type = models.CharField(max_length=40)
    object_id = models.BigIntegerField(null=True, blank=True)
    actor = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    occurred_at = models.DateTimeField(auto_now_add=True)
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["object_type", "object_id"]), models.Index(fields=["entity", "occurred_at"])]
