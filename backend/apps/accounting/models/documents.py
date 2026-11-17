"""Accounting documents: invoices (trade-linked or standalone), payments/receipts, bill-wise settlements."""
from django.db import models

from apps.core.models import AuditModel, CompanyModel

from .books import CostCentre, EntityBooks
from .coa import Account
from .guards import protect_if_posted
from .tax import TdsSection
from .vouchers import Voucher


class InvoiceKind(models.TextChoices):
    PURCHASE = "PURCHASE", "Purchase invoice"
    SALES = "SALES", "Sales invoice"
    EXPENSE = "EXPENSE", "Expense bill"
    COMMISSION_PAYABLE = "COMMISSION_PAYABLE", "Commission payable"
    COMMISSION_RECEIVABLE = "COMMISSION_RECEIVABLE", "Commission receivable"
    DEBIT_NOTE = "DEBIT_NOTE", "Debit note (to supplier)"
    CREDIT_NOTE = "CREDIT_NOTE", "Credit note (to customer)"


#: Kinds that create a payable to the party (we owe them).
PAYABLE_KINDS = (InvoiceKind.PURCHASE, InvoiceKind.EXPENSE, InvoiceKind.COMMISSION_PAYABLE)
#: Kinds that create a receivable from the party.
RECEIVABLE_KINDS = (InvoiceKind.SALES, InvoiceKind.COMMISSION_RECEIVABLE)
NOTE_KINDS = (InvoiceKind.DEBIT_NOTE, InvoiceKind.CREDIT_NOTE)


class DocStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"
    POSTED = "POSTED", "Posted"
    CANCELLED = "CANCELLED", "Cancelled"
    REVERSED = "REVERSED", "Reversed"


class Invoice(AuditModel):
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="invoices")
    kind = models.CharField(max_length=24, choices=InvoiceKind.choices)
    party = models.ForeignKey(CompanyModel, on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=128, help_text="Our document number (trade invoice number when linked).")
    party_reference = models.CharField(max_length=128, blank=True, help_text="Supplier's own bill number.")
    date = models.DateField()
    credit_days = models.PositiveIntegerField(default=0)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="INR")
    fx_rate = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    taxable_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    roundoff = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    gross_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    tds_section = models.ForeignKey(TdsSection, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    tds_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    tds_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    net_amount = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, help_text="Gross - TDS: the amount the bill settles at."
    )
    status = models.CharField(max_length=10, choices=DocStatus.choices, default=DocStatus.DRAFT)
    trade = models.OneToOneField(
        "trade.LicenseTrade", null=True, blank=True, on_delete=protect_if_posted, related_name="accounting_invoice"
    )
    source_version = models.CharField(max_length=64, blank=True, help_text="Hash of the trade fields last synced.")
    against_invoice = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="notes",
        help_text="For debit/credit notes: the bill being adjusted.",
    )
    voucher = models.OneToOneField(Voucher, null=True, blank=True, on_delete=models.PROTECT, related_name="invoice")
    narration = models.TextField(blank=True)
    attachment = models.FileField(upload_to="accounting/invoices/%Y/%m/", null=True, blank=True)
    confirmed_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "kind", "party", "number"], name="acct_invoice_unique_number",
            ),
            models.CheckConstraint(condition=models.Q(net_amount__gte=0), name="acct_invoice_net_non_negative"),
        ]
        indexes = [models.Index(fields=["entity", "kind", "date"]), models.Index(fields=["entity", "party", "status"])]

    def __str__(self) -> str:
        return f"{self.kind} {self.number}"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField()
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    amount = models.DecimalField(max_digits=20, decimal_places=2, help_text="Taxable value")
    gst_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    cgst = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    trade = models.ForeignKey("trade.LicenseTrade", null=True, blank=True, on_delete=protect_if_posted,
                              related_name="+")
    cost_centre = models.ForeignKey(CostCentre, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["invoice_id", "line_no"]
        constraints = [models.UniqueConstraint(fields=["invoice", "line_no"], name="acct_invline_unique_no")]


class PaymentDirection(models.TextChoices):
    PAYMENT = "PAYMENT", "Payment (money out)"
    RECEIPT = "RECEIPT", "Receipt (money in)"


class Payment(AuditModel):
    MODES = [(m, m) for m in ("NEFT", "RTGS", "IMPS", "UPI", "CHEQUE", "CASH", "OTHER")]
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="payments")
    direction = models.CharField(max_length=8, choices=PaymentDirection.choices)
    party = models.ForeignKey(CompanyModel, on_delete=models.PROTECT, related_name="+")
    bank_account = models.ForeignKey("accounting.BankAccount", on_delete=models.PROTECT, related_name="payments")
    date = models.DateField()
    amount = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount through the bank")
    tds_amount = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, help_text="Receipts: TDS deducted by the customer"
    )
    mode = models.CharField(max_length=8, choices=MODES, default="NEFT")
    reference = models.CharField(max_length=128, blank=True, help_text="UTR / cheque number")
    status = models.CharField(max_length=10, choices=DocStatus.choices, default=DocStatus.DRAFT)
    voucher = models.OneToOneField(Voucher, null=True, blank=True, on_delete=models.PROTECT, related_name="payment")
    trade_payment = models.OneToOneField(
        "trade.LicenseTradePayment", null=True, blank=True, on_delete=models.PROTECT, related_name="accounting_payment",
        help_text="Existing trade payment this document accounts for (linked, never recreated).",
    )
    narration = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="acct_payment_positive"),
            models.CheckConstraint(condition=models.Q(tds_amount__gte=0), name="acct_payment_tds_non_negative"),
        ]
        indexes = [models.Index(fields=["entity", "party", "status"]), models.Index(fields=["reference"])]

    @property
    def party_amount(self):
        """Amount credited/debited to the party (bank amount + TDS deducted at source)."""
        return self.amount + self.tds_amount


class Settlement(AuditModel):
    """Bill-wise allocation of a settling voucher (payment, receipt, note, suspense resolution) to a bill."""
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="+")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="settlements")
    voucher = models.ForeignKey(Voucher, on_delete=models.PROTECT, related_name="settlements")
    payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.PROTECT, related_name="settlements")
    note = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.PROTECT, related_name="note_settlements")
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    is_active = models.BooleanField(default=True, help_text="False once the settling voucher is reversed.")

    class Meta:
        ordering = ["id"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="acct_settlement_positive")]
        indexes = [models.Index(fields=["invoice", "is_active"]), models.Index(fields=["voucher", "is_active"])]
