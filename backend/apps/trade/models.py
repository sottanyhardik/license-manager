# trade/models.py
import re
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum, Q, F
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.bill_of_entry.models import BillOfEntryModel
from apps.core.models import AuditModel, CompanyModel
from apps.license.models import LicenseImportItemsModel

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
class LicenseTrade(AuditModel):
    """Trade header (Purchase / Sale). Invoice-level details & totals only.

    Inherits created_on / modified_on / created_by / modified_by from AuditModel.
    """
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

    # Optional: many BOEs can be referenced by many trades
    boes = models.ManyToManyField(
        BillOfEntryModel,
        blank=True,
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

    # Preserve the existing db_index on created_on (other AuditModel inheritors don't have it).
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)

    linked_trade = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='paired_trades',
        help_text="Links this trade to its paired counterpart (Sale↔Purchase)"
    )
    # `linked_trade` predates enforced paired-copy semantics and remains for
    # backwards-compatible manual links.  Counterpart pairs created by the
    # domain service use these fields exclusively.
    transaction_pair_uuid = models.UUIDField(null=True, blank=True, db_index=True, editable=False)
    counterpart = models.OneToOneField(
        'self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='counterpart_of', editable=False,
        help_text='Reciprocal immutable Sale↔Purchase counterpart.',
    )
    copied_from = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='copies_created', editable=False,
    )
    copied_from_type = models.CharField(max_length=20, blank=True, default='', editable=False)
    source_document_number = models.CharField(max_length=128, blank=True, default='', editable=False)

    class Meta:
        ordering = ["-invoice_date", "-invoice_number", "-created_on"]
        indexes = [
            models.Index(fields=["invoice_date"]),
            models.Index(fields=["direction", "invoice_date"]),
            models.Index(fields=["direction", "from_company"]),
            models.Index(fields=["direction", "to_company"]),
        ]
        constraints = [
            # A) from_company and to_company must differ (NULLs allowed)
            models.CheckConstraint(
                name="chk_from_to_companies_different",
                condition=Q(from_company__isnull=True) | Q(to_company__isnull=True) | ~Q(from_company=F("to_company")),
            ),
            # B) Prevent duplicate supplier + invoice_number + direction for PURCHASE (ignore blanks)
            models.UniqueConstraint(
                fields=["from_company", "invoice_number", "direction"],
                condition=Q(direction="PURCHASE") & ~Q(invoice_number=""),
                name="uniq_purchase_supplier_invoice",
            ),
            # C) Prevent duplicate buyer + invoice_number + direction for SALE (ignore blanks)
            models.UniqueConstraint(
                fields=["to_company", "invoice_number", "direction"],
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
    counterpart_line = models.OneToOneField(
        'self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='counterpart_of_line', editable=False,
    )
    transaction_pair_uuid = models.UUIDField(null=True, blank=True, db_index=True, editable=False)
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
            return q2(q2(self.cif_inr) * (Decimal(str(self.pct if self.pct is not None else 0)) / Decimal("100")))
        if self.mode == self.MODE_FOB_INR:
            return q2(q2(self.fob_inr) * (Decimal(str(self.pct if self.pct is not None else 0)) / Decimal("100")))
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
        return q2(q2(self.license_value) * (Decimal(str(self.rate_pct if self.rate_pct is not None else 0)) / Decimal("100")))

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


class TradePairAudit(models.Model):
    """Append-only audit record for paired commercial-document operations."""
    pair_uuid = models.UUIDField(db_index=True)
    source = models.ForeignKey(LicenseTrade, on_delete=models.PROTECT, related_name='pair_audit_as_source')
    counterpart = models.ForeignKey(LicenseTrade, on_delete=models.PROTECT, related_name='pair_audit_as_counterpart')
    action = models.CharField(max_length=32)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at', '-id']


class TradeInvoiceDocument(models.Model):
    """Immutable generated SALE-invoice version.

    Uploaded supplier invoices deliberately remain on
    ``LicenseTrade.purchase_invoice_copy``.  A sale invoice is a different
    business object: it is rendered from the sale bill and persisted here so
    opening it repeatedly never creates divergent documents.
    """

    trade = models.ForeignKey(
        LicenseTrade, on_delete=models.CASCADE, related_name="generated_invoice_documents"
    )
    version_hash = models.CharField(max_length=64)
    file = models.FileField(upload_to="trade/generated_sale_invoices/")
    signed = models.BooleanField(default=False)
    sale_bill_inr = models.DecimalField(max_digits=20, decimal_places=2)
    generated_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_on", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["trade", "version_hash"], name="uniq_trade_invoice_document_version"
            )
        ]

    def __str__(self):
        return f"SaleInvoiceDocument[{self.pk}] trade={self.trade_id} signed={self.signed}"


class InvoiceDocumentAccessToken(models.Model):
    """Opaque, short-lived capability for viewing one invoice document."""

    TYPE_PURCHASE_UPLOADED = "PURCHASE_UPLOADED"
    TYPE_SALE_GENERATED = "SALE_GENERATED"
    DOCUMENT_TYPE_CHOICES = (
        (TYPE_PURCHASE_UPLOADED, "Purchase uploaded invoice"),
        (TYPE_SALE_GENERATED, "Generated sale invoice"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    trade = models.ForeignKey(LicenseTrade, on_delete=models.CASCADE, related_name="invoice_access_tokens")
    document_type = models.CharField(max_length=32, choices=DOCUMENT_TYPE_CHOICES)
    storage_name = models.CharField(max_length=500)
    document_version = models.CharField(max_length=128, blank=True, default="")
    signed = models.BooleanField(default=False)
    issued_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoice_document_tokens")
    authorized_company = models.ForeignKey(CompanyModel, null=True, blank=True, on_delete=models.CASCADE, related_name="invoice_document_tokens")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    max_views = models.PositiveSmallIntegerField(default=2)
    view_count = models.PositiveSmallIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["expires_at", "view_count"])]


class InvoiceDocumentAuditEvent(models.Model):
    """Security audit trail; metadata must never contain raw bearer tokens."""

    EVENT_PURCHASE_VIEWED = "PURCHASE_DOCUMENT_VIEWED"
    EVENT_SALE_GENERATED = "SALE_INVOICE_GENERATED"
    EVENT_SALE_VIEWED = "SALE_INVOICE_VIEWED"
    EVENT_EXPIRED = "DOCUMENT_VIEW_EXPIRED"
    EVENT_FORBIDDEN = "DOCUMENT_VIEW_FORBIDDEN"
    EVENT_CHOICES = (
        (EVENT_PURCHASE_VIEWED, "Purchase document viewed"),
        (EVENT_SALE_GENERATED, "Sale invoice generated"),
        (EVENT_SALE_VIEWED, "Sale invoice viewed"),
        (EVENT_EXPIRED, "Document view expired"),
        (EVENT_FORBIDDEN, "Document view forbidden"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.CharField(max_length=40, choices=EVENT_CHOICES, db_index=True)
    trade = models.ForeignKey(LicenseTrade, on_delete=models.CASCADE, related_name="invoice_document_events")
    access_token = models.ForeignKey(InvoiceDocumentAccessToken, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoice_document_events")
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)


# -----------------------------------------------------------------------------
# Signals
# -----------------------------------------------------------------------------
@receiver(pre_delete, sender=LicenseTrade)
def clear_boe_invoice_on_trade_delete(sender, instance, **kwargs):
    """
    When a trade is deleted, clear the invoice_no from the associated BOE.
    This allows the BOE to be reused for other trades.
    """
    if instance.invoice_number:
        for boe in instance.boes.all():
            # Only clear if the BOE's invoice_no matches this trade's invoice_number
            if boe.invoice_no == instance.invoice_number:
                boe.invoice_no = None
                boe.invoice_date = None
                boe.save(update_fields=['invoice_no', 'invoice_date'])


@receiver(pre_delete, sender=LicenseTrade)
def prevent_single_counterpart_delete(sender, instance, **kwargs):
    """A paired transfer is an audited unit; it cannot be deleted one-sided."""
    if instance.counterpart_id:
        raise ValidationError('This trade has a linked counterpart. Use the audited pair-deletion workflow.')


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
