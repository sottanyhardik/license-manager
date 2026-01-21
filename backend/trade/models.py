# trade/models.py
import re
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum, Q, F
from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from bill_of_entry.models import BillOfEntryModel
from core.models import CompanyModel
from license.models import LicenseImportItemsModel

# ---- quantize helpers ----
TWOPL = Decimal("0.01")
FOURPL = Decimal("0.0001")


def q2(v, q=TWOPL) -> Decimal:
    """Quantize to 2 d.p. (bank-statement style)."""
    if v in (None, ""):
        v = 0
    d = v if isinstance(v, Decimal) else Decimal(str(v))
    return d.quantize(q, rounding=ROUND_HALF_UP)


def q4(v) -> Decimal:
    """Quantize to 4 d.p."""
    return q2(v, q=FOURPL)


def indian_fy_label(d):
    """Return Indian FY label like '2025-26' for a given date."""
    if d is None:
        d = timezone.now().date()
    y = d.year
    if d.month >= 4:
        start = y
        end = y + 1
    else:
        start = y - 1
        end = y
    return f"{start}-{str(end)[-2:]}"


def company_prefix(name: str) -> str:
    """
    Build a company prefix from company name.
    - If 1 word: first 3 letters (e.g., 'Purvaj' -> 'PUR')
    - If 2 words: first letter of each word (e.g., 'Labdhi Mercantile' -> 'LM')
    - If 3+ words: first letter of first N words (e.g., 'Labdhi Mercantile LLP' -> 'LML')
    """
    if not name:
        return "INV"

    # Remove special characters and split into words
    words = re.sub(r"[^A-Za-z\s]", "", name).upper().split()

    if not words:
        return "INV"

    if len(words) == 1:
        # Single word: take first 3 letters
        return words[0][:3] if len(words[0]) >= 3 else words[0]
    else:
        # Multiple words: first letter of each word (up to all words)
        return ''.join([word[0] for word in words if word])


def get_next_invoice_number(direction: str, company_name: str, invoice_date=None) -> str:
    """
    Generate the next invoice number in format:
    - PURCHASE: P-PREFIX/YYYY-YY/NNNN (e.g., P-LM/2025-26/0024)
    - SALE: PREFIX/YYYY-YY/NNNN (e.g., LM/2025-26/0001)
    - COMMISSION_PURCHASE: COM-P-PREFIX/YYYY-YY/NNNN (e.g., COM-P-LM/2025-26/0001)
    - COMMISSION_SALE: COM-PREFIX/YYYY-YY/NNNN (e.g., COM-LM/2025-26/0001)

    Logic:
    - Finds the highest invoice number in the same financial year
    - Increments by 1 (skips gaps, e.g., if 17, 19, 83 exist, next is 84, not 18)
    - Restarts from 0001 for each new financial year
    - PURCHASE invoices are prefixed with 'P-'
    - COMMISSION invoices are prefixed with 'COM-' (and 'COM-P-' for commission purchase)

    Args:
        direction: 'PURCHASE', 'SALE', 'COMMISSION_PURCHASE', or 'COMMISSION_SALE'
        company_name: Company name to generate prefix
        invoice_date: Date to determine financial year (defaults to today)

    Returns:
        Next invoice number string
    """
    from django.db.models import Max
    import re

    # Get prefix and FY
    base_prefix = company_prefix(company_name)
    fy = indian_fy_label(invoice_date)

    # Add prefixes based on direction
    if direction == 'PURCHASE':
        prefix = f"P-{base_prefix}"
    elif direction == 'COMMISSION_PURCHASE':
        prefix = f"COM-P-{base_prefix}"
    elif direction == 'COMMISSION_SALE':
        prefix = f"COM-{base_prefix}"
    else:  # SALE
        prefix = base_prefix

    # Build the pattern for this prefix + FY
    pattern_prefix = f"{prefix}/{fy}/"

    # Find all invoice numbers with this prefix + FY pattern
    existing_invoices = LicenseTrade.objects.filter(
        direction=direction,
        invoice_number__startswith=pattern_prefix
    ).values_list('invoice_number', flat=True)

    # Extract the numeric part from each invoice
    max_number = 0
    for inv in existing_invoices:
        match = re.search(r'/(\d+)$', inv)
        if match:
            num = int(match.group(1))
            max_number = max(max_number, num)

    # Next number is max + 1
    next_number = max_number + 1

    # Format: PREFIX/YYYY-YY/NNNN (4 digits padded)
    return f"{prefix}/{fy}/{next_number:04d}"


# -----------------------------------------------------------------------------
# LicenseTrade (header)
# -----------------------------------------------------------------------------
class LicenseTrade(models.Model):
    """Trade header (Purchase / Sale). Invoice-level details & totals only."""
    DIR_PURCHASE = "PURCHASE"
    DIR_SALE = "SALE"
    DIR_COMMISSION_PURCHASE = "COMMISSION_PURCHASE"
    DIR_COMMISSION_SALE = "COMMISSION_SALE"
    DIR_CHOICES = (
        (DIR_PURCHASE, "Purchase"),
        (DIR_SALE, "Sale"),
        (DIR_COMMISSION_PURCHASE, "Commission Purchase"),
        (DIR_COMMISSION_SALE, "Commission Sale"),
    )

    LICENSE_TYPE_DFIA = "DFIA"
    LICENSE_TYPE_INCENTIVE = "INCENTIVE"
    LICENSE_TYPE_CHOICES = (
        (LICENSE_TYPE_DFIA, "DFIA License"),
        (LICENSE_TYPE_INCENTIVE, "Incentive License"),
    )

    direction = models.CharField(max_length=20, choices=DIR_CHOICES, db_index=True)

    # License type selection
    license_type = models.CharField(
        max_length=20,
        choices=LICENSE_TYPE_CHOICES,
        default=LICENSE_TYPE_DFIA,
        db_index=True,
        help_text="Type of license to use for this trade"
    )

    # Incentive License (if license_type is INCENTIVE)
    incentive_license = models.ForeignKey(
        "license.IncentiveLicense",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trades",
        help_text="Incentive License (RODTEP/ROSTL/MEIS) - used when license_type is INCENTIVE"
    )

    # Optional: one BOE can be referenced by many trades
    boe = models.ForeignKey(
        BillOfEntryModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="license_trades",
    )

    # Parties (Company side only)
    from_company = models.ForeignKey(
        CompanyModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trades_from_company",
    )
    to_company = models.ForeignKey(
        CompanyModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trades_to_company",
    )

    # Snapshots (frozen when the trade is created/edited)
    from_pan = models.CharField(max_length=32, null=True, blank=True)
    from_gst = models.CharField(max_length=32, null=True, blank=True)
    from_addr_line_1 = models.TextField(null=True, blank=True)
    from_addr_line_2 = models.TextField(null=True, blank=True)

    to_pan = models.CharField(max_length=32, null=True, blank=True)
    to_gst = models.CharField(max_length=32, null=True, blank=True)
    to_addr_line_1 = models.TextField(null=True, blank=True)
    to_addr_line_2 = models.TextField(null=True, blank=True)

    # Invoice header
    invoice_number = models.CharField(max_length=128, blank=True, default="", db_index=True)
    invoice_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)

    # Totals (lines roll-up + auto round-off)
    subtotal_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    roundoff = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    # Purchase-only: upload copy of supplier invoice (optional)
    purchase_invoice_copy = models.FileField(
        upload_to="trade/purchase_invoices/", null=True, blank=True
    )

    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_on = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trades_created'
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trades_modified'
    )

    class Meta:
        ordering = ["-invoice_date", "-invoice_number", "-created_on"]
        constraints = [
            # A) from_company and to_company must differ (NULLs allowed)
            models.CheckConstraint(
                name="chk_from_to_companies_different",
                check=Q(from_company__isnull=True) | Q(to_company__isnull=True) | ~Q(from_company=F("to_company")),
            ),
            # B) Prevent duplicate supplier + invoice_number for PURCHASE (ignore blanks)
            models.UniqueConstraint(
                fields=["from_company", "invoice_number"],
                condition=Q(direction="PURCHASE") & ~Q(invoice_number=""),
                name="uniq_purchase_supplier_invoice",
            ),
            # C) Prevent duplicate buyer + invoice_number for SALE (ignore blanks)
            models.UniqueConstraint(
                fields=["to_company", "invoice_number"],
                condition=Q(direction='SALE') & ~Q(invoice_number=""),
                name="uniq_sale_buyer_invoice_nonblank",
            ),
        ]

    def __str__(self) -> str:
        return f"Trade[{self.id}] {self.direction} Inv:{self.invoice_number or '-'}"

    # ------ computed fields / helpers ------
    @property
    def paid_or_received(self) -> Decimal:
        """Total settled amount (paid for purchase / received for sale)."""
        agg = self.payments.aggregate(s=Sum("amount"))
        return q2(agg["s"] or 0)

    @property
    def due_amount(self) -> Decimal:
        """
        Remaining amount after settlements.
          - PURCHASE: amount still to PAY (total - paid)
          - SALE    : amount still to RECEIVE (total - received)
        """
        return q2(self.total_amount) - q2(self.paid_or_received)

    def recompute_totals(self) -> None:
        """
        Recompute subtotal, roundoff, and total from lines (or incentive_lines) and
        persist via queryset.update() to avoid triggering save() again.
        """
        # Choose the correct lines based on license_type
        if self.license_type == self.LICENSE_TYPE_INCENTIVE:
            agg = self.incentive_lines.aggregate(total=Sum("amount_inr"))
        else:
            agg = self.lines.aggregate(total=Sum("amount_inr"))

        subtotal = q2(agg["total"] or 0)
        nearest_rupee = subtotal.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        roundoff = q2(nearest_rupee - subtotal)
        total = q2(subtotal + roundoff)

        self.subtotal_amount = subtotal
        self.roundoff = roundoff
        self.total_amount = total

        if self.pk:
            LicenseTrade.objects.filter(pk=self.pk).update(
                subtotal_amount=subtotal,
                roundoff=roundoff,
                total_amount=total,
                modified_on=timezone.now(),
            )

    def snapshot_parties(self) -> None:
        """Fill snapshot fields from linked companies where missing; persist via update()."""

        def snap(company, to_side=False):
            if not company:
                return
            if to_side:
                self.to_pan = self.to_pan or (getattr(company, "pan", None) or "").upper()
                self.to_gst = self.to_gst or (getattr(company, "gst_number", None) or "").upper()
                self.to_addr_line_1 = self.to_addr_line_1 or (getattr(company, "address_line_1", "") or "")
                self.to_addr_line_2 = self.to_addr_line_2 or (getattr(company, "address_line_2", "") or "")
            else:
                self.from_pan = self.from_pan or (getattr(company, "pan", None) or "").upper()
                self.from_gst = self.from_gst or (getattr(company, "gst_number", None) or "").upper()
                self.from_addr_line_1 = self.from_addr_line_1 or (getattr(company, "address_line_1", "") or "")
                self.from_addr_line_2 = self.from_addr_line_2 or (getattr(company, "address_line_2", "") or "")

        snap(self.from_company, to_side=False)
        snap(self.to_company, to_side=True)

        if self.pk:
            LicenseTrade.objects.filter(pk=self.pk).update(
                from_pan=self.from_pan,
                from_gst=self.from_gst,
                from_addr_line_1=self.from_addr_line_1,
                from_addr_line_2=self.from_addr_line_2,
                to_pan=self.to_pan,
                to_gst=self.to_gst,
                to_addr_line_1=self.to_addr_line_1,
                to_addr_line_2=self.to_addr_line_2,
                modified_on=timezone.now(),
            )

    @staticmethod
    def build_invoice_pattern(prefix: str, fy: str) -> str:
        return f"{prefix}/{fy}/"

    @classmethod
    def next_invoice_number(cls, *, seller_company: CompanyModel, invoice_date=None, prefix: str = None) -> str:
        """
        Compute next invoice number for SALE:
          <PREFIX>/<FY>/<NNNN>
        - PREFIX: first 3 letters of seller company (alpha only)
        - FY: Indian FY (Apr–Mar)
        - NNNN: zero-padded 4-digit sequence
        """
        if not seller_company:
            return ""
        if invoice_date is None:
            invoice_date = timezone.now().date()

        fy = indian_fy_label(invoice_date)
        px = (prefix or company_prefix(getattr(seller_company, "name", ""))).upper()
        base = cls.build_invoice_pattern(px, fy)

        with transaction.atomic():
            # lock rows for this series to prevent race conditions
            qs = (
                cls.objects.select_for_update()
                .filter(direction=cls.DIR_SALE, from_company=seller_company, invoice_number__startswith=base)
                .order_by("-invoice_number")
            )
            last = qs.first()
            seq = 0
            if last and last.invoice_number:
                # Expect forms like 'LAB/2025-26/0007'
                m = re.match(rf"^{re.escape(base)}(\d+)$", last.invoice_number)
                if m:
                    try:
                        seq = int(m.group(1))
                    except Exception:
                        seq = 0
            next_seq = seq + 1
            return f"{base}{str(next_seq).zfill(4)}"

    def save(self, *args, **kwargs) -> None:
        if self.invoice_date is None:
            self.invoice_date = timezone.now().date()
        super().save(*args, **kwargs)
        # keep totals consistent even if header saved first
        self.recompute_totals()


# -----------------------------------------------------------------------------
# LicenseTradeLine (detail lines)
# -----------------------------------------------------------------------------
class LicenseTradeLine(models.Model):
    """
    One billed line. Amount is computed by the chosen mode:

      - QTY     : amount = qty_kg × rate_inr_per_kg
      - CIF_INR : amount = cif_inr × pct / 100
      - FOB_INR : amount = fob_inr × pct / 100
    """

    MODE_QTY = "QTY"
    MODE_CIF_INR = "CIF_INR"
    MODE_FOB_INR = "FOB_INR"
    MODE_CHOICES = (
        (MODE_QTY, "Quantity (Kg × Rate)"),
        (MODE_CIF_INR, "CIF (INR × %)"),
        (MODE_FOB_INR, "FOB (INR × %)"),
    )

    trade = models.ForeignKey(
        LicenseTrade, on_delete=models.CASCADE, related_name="lines", db_index=True
    )
    # Billed SR (carries the license context)
    sr_number = models.ForeignKey(
        LicenseImportItemsModel,
        on_delete=models.PROTECT,  # protect billed SRs
        related_name="trade_lines",
    )

    description = models.TextField(blank=True, default="")
    hsn_code = models.CharField(max_length=10, default="49070000", blank=True)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_QTY, db_index=True)

    # QTY mode fields
    qty_kg = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    rate_inr_per_kg = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))

    # Amount modes (base amounts)
    cif_fc = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    exc_rate = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0.0000"))
    cif_inr = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    fob_inr = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    pct = models.DecimalField(max_digits=9, decimal_places=3, default=Decimal("0"))

    # Result
    amount_inr = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))

    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"TradeLine[{self.id}] {self.mode} → ₹{self.amount_inr}"

    def compute_amount(self) -> Decimal:
        if self.mode == self.MODE_QTY:
            return q2(q4(self.qty_kg) * q2(self.rate_inr_per_kg))
        if self.mode == self.MODE_CIF_INR:
            return q2(q2(self.cif_inr) * (q2(self.pct) / Decimal("100")))
        if self.mode == self.MODE_FOB_INR:
            return q2(q2(self.fob_inr) * (q2(self.pct) / Decimal("100")))
        return Decimal("0.00")

    def save(self, *args, **kwargs) -> None:
        # Don't auto-calculate amount_inr - allow manual entry from frontend
        # If amount_inr is not set (0 or None), calculate it
        if not self.amount_inr or self.amount_inr == 0:
            self.amount_inr = self.compute_amount()
        super().save(*args, **kwargs)
        if self.trade_id:
            # Safe: recompute uses queryset.update(), so no recursion
            self.trade.recompute_totals()


# -----------------------------------------------------------------------------
# IncentiveTradeLine (for RODTEP/ROSTL/MEIS licenses)
# -----------------------------------------------------------------------------
class IncentiveTradeLine(models.Model):
    """
    Trade line for Incentive Licenses (RODTEP/ROSTL/MEIS).
    Simplified structure: license + value + rate% = amount
    """
    trade = models.ForeignKey(
        LicenseTrade,
        on_delete=models.CASCADE,
        related_name="incentive_lines",
        db_index=True
    )

    incentive_license = models.ForeignKey(
        "license.IncentiveLicense",
        on_delete=models.PROTECT,
        related_name="trade_lines",
        help_text="The incentive license being traded"
    )

    # License value in INR (auto-filled from license, can be edited)
    license_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="License value in INR"
    )

    # Billing rate as percentage
    rate_pct = models.DecimalField(
        max_digits=9,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="Billing rate as percentage"
    )

    # Result amount
    amount_inr = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculated amount = license_value × rate_pct / 100"
    )

    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"IncentiveLine[{self.id}] {self.incentive_license} → ₹{self.amount_inr}"

    def compute_amount(self) -> Decimal:
        """Calculate amount from license_value and rate_pct"""
        return q2(q2(self.license_value) * (q2(self.rate_pct) / Decimal("100")))

    def save(self, *args, **kwargs) -> None:
        # Auto-calculate amount_inr if not manually set
        if not self.amount_inr or self.amount_inr == 0:
            self.amount_inr = self.compute_amount()
        super().save(*args, **kwargs)
        if self.trade_id:
            # Recompute trade totals
            self.trade.recompute_totals()


# -----------------------------------------------------------------------------
# LicenseTradePayment (settlements)
# -----------------------------------------------------------------------------
class LicenseTradePayment(models.Model):
    """
    Positive 'amount' means money settled against the trade:
      - PURCHASE: amount PAID to supplier
      - SALE    : amount RECEIVED from customer
    """
    trade = models.ForeignKey(LicenseTrade, on_delete=models.CASCADE, related_name="payments")
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        return f"Payment[{self.id}] Trade#{self.trade_id} ₹{q2(self.amount)} on {self.date}"


# -----------------------------------------------------------------------------
# Signals
# -----------------------------------------------------------------------------
@receiver(pre_delete, sender=LicenseTrade)
def clear_boe_invoice_on_trade_delete(sender, instance, **kwargs):
    """
    When a trade is deleted, clear the invoice_no from the associated BOE.
    This allows the BOE to be reused for other trades.
    """
    if instance.boe and instance.invoice_number:
        # Only clear if the BOE's invoice_no matches this trade's invoice_number
        if instance.boe.invoice_no == instance.invoice_number:
            instance.boe.invoice_no = None
            instance.boe.invoice_date = None
            instance.boe.save(update_fields=['invoice_no', 'invoice_date'])


@receiver(post_save, sender=IncentiveTradeLine)
def update_incentive_license_on_trade_line_save(sender, instance, **kwargs):
    """
    When an IncentiveTradeLine is saved, update the related IncentiveLicense sold status.
    Only update if this is a SALE trade.
    """
    if instance.incentive_license and instance.trade.direction == 'SALE':
        instance.incentive_license.update_sold_status()


@receiver(pre_delete, sender=IncentiveTradeLine)
def update_incentive_license_on_trade_line_delete(sender, instance, **kwargs):
    """
    When an IncentiveTradeLine is deleted, update the related IncentiveLicense sold status.
    Only update if this is a SALE trade.
    """
    if instance.incentive_license and instance.trade.direction == 'SALE':
        instance.incentive_license.update_sold_status()


# =============================================================================
# LEDGER MODULE - Double Entry Accounting System
# =============================================================================

class ChartOfAccounts(models.Model):
    """
    Chart of Accounts for double-entry bookkeeping.
    Standard accounting categories with hierarchical structure.
    """
    ASSET = 'ASSET'
    LIABILITY = 'LIABILITY'
    EQUITY = 'EQUITY'
    REVENUE = 'REVENUE'
    EXPENSE = 'EXPENSE'

    ACCOUNT_TYPE_CHOICES = [
        (ASSET, 'Asset'),
        (LIABILITY, 'Liability'),
        (EQUITY, 'Equity'),
        (REVENUE, 'Revenue'),
        (EXPENSE, 'Expense'),
    ]

    code = models.CharField(max_length=20, unique=True, db_index=True, help_text="Account code (e.g., 1000, 2000)")
    name = models.CharField(max_length=255, help_text="Account name (e.g., Cash, Accounts Receivable)")
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='sub_accounts')

    # For party accounts (sundry debtors/creditors)
    linked_company = models.ForeignKey(
        CompanyModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ledger_accounts',
        help_text="Link to company for party ledgers"
    )

    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code', 'name']
        verbose_name = 'Chart of Account'
        verbose_name_plural = 'Chart of Accounts'

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def balance(self):
        """Calculate current balance from journal entries."""
        from django.db.models import Sum

        # Get all journal entry lines for this account
        lines = self.journal_entry_lines.all()

        debits = lines.aggregate(
            total=Sum('debit_amount')
        )['total'] or Decimal('0.00')

        credits = lines.aggregate(
            total=Sum('credit_amount')
        )['total'] or Decimal('0.00')

        # Assets and Expenses have debit balance (debit - credit)
        if self.account_type in [self.ASSET, self.EXPENSE]:
            return q2(debits - credits)
        # Liabilities, Equity, and Revenue have credit balance (credit - debit)
        else:
            return q2(credits - debits)


class BankAccount(models.Model):
    """
    Bank accounts for cash/bank reconciliation.
    """
    account_name = models.CharField(max_length=255, help_text="Account name/label")
    bank_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=100)
    ifsc_code = models.CharField(max_length=20, blank=True)
    branch = models.CharField(max_length=255, blank=True)

    # Link to Chart of Accounts
    ledger_account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
        help_text="Link to bank account in chart of accounts"
    )

    opening_balance = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Opening balance"
    )
    opening_balance_date = models.DateField(default=timezone.now)

    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['bank_name', 'account_name']

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"

    @property
    def current_balance(self):
        """Calculate current balance including opening balance and transactions."""
        return q2(self.opening_balance + self.ledger_account.balance)


class JournalEntry(models.Model):
    """
    Journal Entry Header for double-entry bookkeeping.
    Each entry must have balanced debits and credits.
    """
    GENERAL = 'GENERAL'
    SALES = 'SALES'
    PURCHASE = 'PURCHASE'
    PAYMENT = 'PAYMENT'
    RECEIPT = 'RECEIPT'
    JOURNAL = 'JOURNAL'

    ENTRY_TYPE_CHOICES = [
        (GENERAL, 'General Entry'),
        (SALES, 'Sales Entry'),
        (PURCHASE, 'Purchase Entry'),
        (PAYMENT, 'Payment Entry'),
        (RECEIPT, 'Receipt Entry'),
        (JOURNAL, 'Journal Entry'),
    ]

    entry_number = models.CharField(max_length=100, unique=True, db_index=True)
    entry_date = models.DateField(default=timezone.now, db_index=True)
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, default=GENERAL)

    # Link to trade if auto-generated from trade
    linked_trade = models.ForeignKey(
        LicenseTrade,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='journal_entries'
    )

    # Link to payment if auto-generated from payment
    linked_payment = models.ForeignKey(
        LicenseTradePayment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='journal_entries'
    )

    narration = models.TextField(help_text="Description of the transaction")
    reference_number = models.CharField(max_length=100, blank=True, help_text="External reference (invoice, receipt no.)")

    is_posted = models.BooleanField(default=False, help_text="Posted entries cannot be modified")
    is_auto_generated = models.BooleanField(default=False, help_text="Auto-generated from trades/payments")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_entries_created'
    )
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-entry_date', '-entry_number']
        verbose_name = 'Journal Entry'
        verbose_name_plural = 'Journal Entries'

    def __str__(self):
        return f"JE#{self.entry_number} - {self.entry_date} - {self.narration[:50]}"

    @property
    def total_debit(self):
        """Sum of all debit amounts in this entry."""
        agg = self.lines.aggregate(total=Sum('debit_amount'))
        return q2(agg['total'] or 0)

    @property
    def total_credit(self):
        """Sum of all credit amounts in this entry."""
        agg = self.lines.aggregate(total=Sum('credit_amount'))
        return q2(agg['total'] or 0)

    @property
    def is_balanced(self):
        """Check if debits equal credits."""
        return self.total_debit == self.total_credit

    def validate_balance(self):
        """Raise error if entry is not balanced."""
        if not self.is_balanced:
            raise ValueError(
                f"Journal entry not balanced: Debit={self.total_debit}, Credit={self.total_credit}"
            )

    def post(self):
        """Post the journal entry (make it immutable)."""
        self.validate_balance()
        self.is_posted = True
        self.save(update_fields=['is_posted', 'modified_on'])

    def unpost(self):
        """Unpost the journal entry (allow modifications)."""
        if self.is_auto_generated:
            raise ValueError("Cannot unpost auto-generated entries")
        self.is_posted = False
        self.save(update_fields=['is_posted', 'modified_on'])


class JournalEntryLine(models.Model):
    """
    Journal Entry Lines - individual debit/credit entries.
    Each line has either debit OR credit (not both).
    """
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name='lines'
    )

    account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.PROTECT,
        related_name='journal_entry_lines'
    )

    debit_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Debit amount (0 if credit entry)"
    )
    credit_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Credit amount (0 if debit entry)"
    )

    description = models.TextField(blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        if self.debit_amount > 0:
            return f"Dr. {self.account.name}: ₹{q2(self.debit_amount)}"
        else:
            return f"Cr. {self.account.name}: ₹{q2(self.credit_amount)}"

    def clean(self):
        """Validate that only one of debit or credit is non-zero."""
        from django.core.exceptions import ValidationError

        if self.debit_amount > 0 and self.credit_amount > 0:
            raise ValidationError("Line cannot have both debit and credit amounts")

        if self.debit_amount == 0 and self.credit_amount == 0:
            raise ValidationError("Line must have either debit or credit amount")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


# =============================================================================
# COMMISSION MODULE
# =============================================================================

class CommissionAgent(models.Model):
    """
    Commission agents/brokers who earn commission on trades
    """
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True, help_text="Agent code/ID")

    # Contact details
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    # Banking details
    pan = models.CharField(max_length=20, blank=True, help_text="PAN number")
    bank_name = models.CharField(max_length=255, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)

    # Default commission rates (can be overridden per trade)
    default_purchase_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Default commission % for purchases"
    )
    default_sale_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Default commission % for sales"
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Commission Agent'
        verbose_name_plural = 'Commission Agents'

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def total_commission_earned(self):
        """Total commission earned by this agent"""
        agg = self.commissions.aggregate(total=Sum('commission_amount'))
        return q2(agg['total'] or 0)

    @property
    def total_commission_paid(self):
        """Total commission paid to this agent"""
        agg = self.commissions.filter(is_paid=True).aggregate(total=Sum('commission_amount'))
        return q2(agg['total'] or 0)

    @property
    def outstanding_commission(self):
        """Outstanding commission to be paid"""
        return q2(self.total_commission_earned - self.total_commission_paid)


class Commission(models.Model):
    """
    Commission record for each trade
    """
    trade = models.ForeignKey(
        LicenseTrade,
        on_delete=models.CASCADE,
        related_name='commissions'
    )

    agent = models.ForeignKey(
        CommissionAgent,
        on_delete=models.PROTECT,
        related_name='commissions'
    )

    # Commission calculation
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Commission rate in %"
    )

    base_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Amount on which commission is calculated"
    )

    commission_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Calculated commission amount"
    )

    # Payment tracking
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=255, blank=True)
    payment_note = models.TextField(blank=True)

    # Link to journal entry if payment is recorded in ledger
    payment_journal_entry = models.ForeignKey(
        'JournalEntry',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='commission_payments'
    )

    notes = models.TextField(blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commissions_created'
    )

    class Meta:
        ordering = ['-trade__invoice_date', '-created_on']
        verbose_name = 'Commission'
        verbose_name_plural = 'Commissions'

    def __str__(self):
        return f"Commission for {self.trade.invoice_number} - {self.agent.name}"

    def calculate_commission(self):
        """Calculate commission based on rate and base amount"""
        self.commission_amount = q2(self.base_amount * self.commission_rate / Decimal('100'))

    def mark_paid(self, payment_date=None, reference='', note=''):
        """Mark commission as paid"""
        self.is_paid = True
        self.payment_date = payment_date or timezone.now().date()
        self.payment_reference = reference
        self.payment_note = note
        self.save(update_fields=['is_paid', 'payment_date', 'payment_reference', 'payment_note', 'modified_on'])

    def save(self, *args, **kwargs):
        # Auto-calculate commission if not set
        if not self.commission_amount or self.commission_amount == 0:
            self.calculate_commission()
        super().save(*args, **kwargs)


class CommissionSlab(models.Model):
    """
    Commission slab structure for tiered/progressive commission rates
    """
    agent = models.ForeignKey(
        CommissionAgent,
        on_delete=models.CASCADE,
        related_name='commission_slabs'
    )

    DIRECTION_CHOICES = [
        ('PURCHASE', 'Purchase'),
        ('SALE', 'Sale'),
        ('COMMISSION_PURCHASE', 'Commission Purchase'),
        ('COMMISSION_SALE', 'Commission Sale'),
        ('BOTH', 'Both'),
    ]

    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default='BOTH')

    # Slab range
    min_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Minimum transaction amount for this slab"
    )

    max_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum transaction amount (null = no upper limit)"
    )

    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Commission rate % for this slab"
    )

    is_active = models.BooleanField(default=True)

    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['agent', 'direction', 'min_amount']
        verbose_name = 'Commission Slab'
        verbose_name_plural = 'Commission Slabs'
        constraints = [
            models.CheckConstraint(
                name='chk_min_less_than_max',
                check=Q(max_amount__isnull=True) | Q(max_amount__gt=F('min_amount')),
            )
        ]

    def __str__(self):
        max_str = f"{self.max_amount:,.2f}" if self.max_amount else "∞"
        return f"{self.agent.name} - {self.direction} - ₹{self.min_amount:,.2f} to ₹{max_str} @ {self.commission_rate}%"

    @staticmethod
    def get_applicable_rate(agent, direction, amount):
        """
        Get applicable commission rate for given agent, direction and amount
        """
        slabs = CommissionSlab.objects.filter(
            agent=agent,
            is_active=True,
            min_amount__lte=amount
        ).filter(
            Q(direction=direction) | Q(direction='BOTH')
        ).filter(
            Q(max_amount__isnull=True) | Q(max_amount__gte=amount)
        ).order_by('-commission_rate')  # Get highest rate if multiple match

        slab = slabs.first()
        if slab:
            return slab.commission_rate

        # Fallback to agent's default rate
        if direction in ('PURCHASE', 'COMMISSION_PURCHASE'):
            return agent.default_purchase_rate
        else:
            return agent.default_sale_rate
