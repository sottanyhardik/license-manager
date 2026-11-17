"""Own bank accounts, imported statements, matches and suspense."""
from django.db import models

from apps.core.models import AuditModel, CompanyModel

from .books import EntityBooks
from .coa import Account
from .vouchers import Voucher


class BankAccount(AuditModel):
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="bank_accounts")
    account = models.OneToOneField(Account, on_delete=models.PROTECT, related_name="bank_account")
    bank_name = models.CharField(max_length=128, blank=True)
    account_number = models.CharField(max_length=40)
    ifsc = models.CharField(max_length=11, blank=True)
    is_cash = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["entity_id", "bank_name", "account_number"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "account_number"], name="acct_bank_unique_number"),
        ]

    def __str__(self) -> str:
        return f"{self.bank_name} {self.account_number}"


class StatementImport(AuditModel):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="imports")
    file_name = models.CharField(max_length=255)
    file_format = models.CharField(max_length=8)
    file_sha256 = models.CharField(max_length=64, blank=True)
    column_mapping = models.JSONField(default=dict, blank=True)
    rows_total = models.PositiveIntegerField(default=0)
    rows_new = models.PositiveIntegerField(default=0)
    rows_duplicate = models.PositiveIntegerField(default=0)
    rows_rejected = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-id"]


class LineStatus(models.TextChoices):
    UNMATCHED = "UNMATCHED", "Unmatched"
    PARTIAL = "PARTIAL", "Partially matched"
    MATCHED = "MATCHED", "Matched"
    SUSPENSE = "SUSPENSE", "In suspense"
    RESOLVED = "RESOLVED", "Suspense resolved"
    EXCEPTION = "EXCEPTION", "Exception"


class StatementLine(models.Model):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="statement_lines")
    statement_import = models.ForeignKey(StatementImport, on_delete=models.PROTECT, related_name="lines")
    txn_date = models.DateField()
    value_date = models.DateField(null=True, blank=True)
    narration = models.CharField(max_length=500, blank=True)
    reference = models.CharField(max_length=128, blank=True)
    debit = models.DecimalField(max_digits=20, decimal_places=2, default=0, help_text="Withdrawal")
    credit = models.DecimalField(max_digits=20, decimal_places=2, default=0, help_text="Deposit")
    balance = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=LineStatus.choices, default=LineStatus.UNMATCHED)
    matched_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["txn_date", "id"]
        constraints = [
            models.UniqueConstraint(fields=["bank_account", "fingerprint"], name="acct_stmt_unique_fingerprint"),
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0, credit=0) | models.Q(debit=0, credit__gt=0)), name="acct_stmt_one_side",
            ),
        ]
        indexes = [models.Index(fields=["bank_account", "status"]), models.Index(fields=["reference"])]

    @property
    def amount(self):
        return self.credit or self.debit


class BankMatch(AuditModel):
    AUTO_REFERENCE, AUTO_AMOUNT, MANUAL, SUSPENSE = "AUTO_REFERENCE", "AUTO_AMOUNT", "MANUAL", "SUSPENSE"
    PROPOSAL = "PROPOSAL"  # a confirmed invoice proposal: the receipt/payment was booked from this bank line
    SPLIT = "SPLIT"  # one bank line (e.g. a "BU :" bulk upload) split into several payments/receipts
    statement_line = models.ForeignKey(StatementLine, on_delete=models.PROTECT, related_name="matches")
    voucher = models.ForeignKey(Voucher, on_delete=models.PROTECT, related_name="bank_matches")
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    method = models.CharField(max_length=16)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="acct_match_positive")]
        indexes = [models.Index(fields=["voucher", "is_active"]), models.Index(fields=["statement_line", "is_active"])]


class SuspenseItem(AuditModel):
    OPEN, RESOLVED = "OPEN", "RESOLVED"
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="suspense_items")
    statement_line = models.OneToOneField(
        StatementLine, null=True, blank=True, on_delete=models.PROTECT, related_name="suspense_item"
    )
    voucher = models.OneToOneField(Voucher, on_delete=models.PROTECT, related_name="suspense_item")
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    is_receipt = models.BooleanField(help_text="True: money came in (Cr suspense). False: money went out.")
    reason = models.CharField(max_length=255)
    owner = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    follow_up_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=[(OPEN, "Open"), (RESOLVED, "Resolved")], default=OPEN)
    resolution_voucher = models.OneToOneField(
        Voucher, null=True, blank=True, on_delete=models.PROTECT, related_name="resolved_suspense"
    )
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    resolved_at = models.DateTimeField(null=True, blank=True)
    document = models.FileField(upload_to="accounting/suspense/%Y/%m/", null=True, blank=True)

    class Meta:
        ordering = ["status", "-id"]


class NarrationAlias(AuditModel):
    """Learned 'bank narration counterparty text -> party' for one entity's books (from confirmed proposals).

    ``key`` is the normalised counterparty text of a narration (see services.bank_proposals.counterparty_key).
    ``direction`` is RECEIPT (money in) or PAYMENT (money out): the same text can name a customer and a supplier.
    """
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="narration_aliases")
    key = models.CharField(max_length=200)
    direction = models.CharField(max_length=8)
    party = models.ForeignKey(CompanyModel, on_delete=models.PROTECT, related_name="+")
    hits = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["entity", "key", "direction"], name="acct_alias_unique_key")]
