# trade/models.py
import re
from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction
from django.db.models import Sum, Q, F
from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.core.models.masters import AuditModel

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

    words = re.sub(r"[^A-Za-z\s]", "", name).upper().split()

    if not words:
        return "INV"

    if len(words) == 1:
        return words[0][:3] if len(words[0]) >= 3 else words[0]
    else:
        return "".join([word[0] for word in words if word])


def get_next_invoice_number(direction: str, company_name: str, invoice_date=None) -> str:
    """
    Generate the next invoice number in format:
    - PURCHASE: P-PREFIX/YYYY-YY/NNNN (e.g., P-LM/2025-26/0024)
    - SALE: PREFIX/YYYY-YY/NNNN (e.g., LM/2025-26/0001)
    - COMMISSION_PURCHASE: COM-P-PREFIX/YYYY-YY/NNNN
    - COMMISSION_SALE: COM-PREFIX/YYYY-YY/NNNN

    Wrapped in select_for_update() inside transaction.atomic() to prevent
    concurrent requests from computing the same next number (TOCTOU race).
    """
    base_prefix = company_prefix(company_name)
    fy = indian_fy_label(invoice_date)

    if direction == "PURCHASE":
        prefix = f"P-{base_prefix}"
    elif direction == "COMMISSION_PURCHASE":
        prefix = f"COM-P-{base_prefix}"
    elif direction == "COMMISSION_SALE":
        prefix = f"COM-{base_prefix}"
    else:  # SALE
        prefix = base_prefix

    pattern_prefix = f"{prefix}/{fy}/"

    with transaction.atomic():
        existing_invoices = (
            LicenseTrade.objects
            .select_for_update()
            .filter(
                direction=direction,
                invoice_number__startswith=pattern_prefix,
            )
            .values_list("invoice_number", flat=True)
        )

        max_number = 0
        for inv in existing_invoices:
            match = re.search(r"/(\d+)$", inv)
            if match:
                num = int(match.group(1))
                max_number = max(max_number, num)

        next_number = max_number + 1
        return f"{prefix}/{fy}/{next_number:04d}"


# -----------------------------------------------------------------------------
# LicenseTrade (header)
# -----------------------------------------------------------------------------
class LicenseTrade(AuditModel):
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

    license_type = models.CharField(
        max_length=20,
        choices=LICENSE_TYPE_CHOICES,
        default=LICENSE_TYPE_DFIA,
        db_index=True,
        help_text="Type of license to use for this trade",
    )

    incentive_license = models.ForeignKey(
        "license.IncentiveLicense",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trades",
        help_text="Incentive License (RODTEP/ROSTL/MEIS) - used when license_type is INCENTIVE",
    )

    boe = models.ForeignKey(
        "bill_of_entry.BillOfEntryModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="license_trades",
    )

    from_company = models.ForeignKey(
        "core.CompanyModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trades_from_company",
    )
    to_company = models.ForeignKey(
        "core.CompanyModel",
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

    purchase_invoice_copy = models.FileField(
        upload_to="trade/purchase_invoices/", null=True, blank=True
    )

    # Override AuditModel.created_on to add db_index=True
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)

    linked_trade = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="paired_trades",
        help_text="Links this trade to its paired counterpart (Sale<->Purchase)",
    )

    class Meta:
        managed = False
        db_table = "trade_licensetrade"
        ordering = ["-invoice_date", "-invoice_number", "-created_on"]
        indexes = [
            models.Index(fields=["invoice_date"]),
            models.Index(fields=["direction", "invoice_date"]),
            models.Index(fields=["direction", "from_company"]),
            models.Index(fields=["direction", "to_company"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="chk_from_to_companies_different",
                condition=Q(from_company__isnull=True) | Q(to_company__isnull=True) | ~Q(from_company=F("to_company")),
            ),
            models.UniqueConstraint(
                fields=["from_company", "invoice_number", "direction"],
                condition=Q(direction="PURCHASE") & ~Q(invoice_number=""),
                name="uniq_purchase_supplier_invoice",
            ),
            models.UniqueConstraint(
                fields=["to_company", "invoice_number", "direction"],
                condition=Q(direction="SALE") & ~Q(invoice_number=""),
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
        """Remaining amount after settlements."""
        return q2(self.total_amount) - q2(self.paid_or_received)

    def recompute_totals(self) -> None:
        """
        Recompute subtotal, roundoff, and total from lines (or incentive_lines) and
        persist via queryset.update() to avoid triggering save() again.
        """
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

    def save(self, *args, **kwargs) -> None:
        if self.invoice_date is None:
            self.invoice_date = timezone.now().date()
        super().save(*args, **kwargs)
        self.recompute_totals()


# -----------------------------------------------------------------------------
# LicenseTradeLine (detail lines)
# -----------------------------------------------------------------------------
class LicenseTradeLine(models.Model):
    """
    One billed line. Amount is computed by the chosen mode:
      - QTY     : amount = qty_kg x rate_inr_per_kg
      - CIF_INR : amount = cif_inr x pct / 100
      - FOB_INR : amount = fob_inr x pct / 100
    """

    MODE_QTY = "QTY"
    MODE_CIF_INR = "CIF_INR"
    MODE_FOB_INR = "FOB_INR"
    MODE_CHOICES = (
        (MODE_QTY, "Quantity (Kg x Rate)"),
        (MODE_CIF_INR, "CIF (INR x %)"),
        (MODE_FOB_INR, "FOB (INR x %)"),
    )

    trade = models.ForeignKey(
        LicenseTrade, on_delete=models.CASCADE, related_name="lines", db_index=True
    )
    sr_number = models.ForeignKey(
        "license.LicenseImportItemsModel",
        on_delete=models.PROTECT,
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
    # CRITICAL: pct must be 3 decimal places — never round to 2dp before dividing by 100
    pct = models.DecimalField(max_digits=9, decimal_places=3, default=Decimal("0"))

    # Result
    amount_inr = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))

    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "trade_licensetradeline"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"TradeLine[{self.id}] {self.mode} -> {self.amount_inr}"

    def compute_amount(self) -> Decimal:
        """
        Compute line amount.

        PRECISION CRITICAL: pct/rate_pct are 3dp fields. We must NOT pass them
        through q2() before dividing by 100 — that would round 7.925 -> 7.93,
        causing a 5-rupee error on a 100,000 INR base.

        Correct: Decimal(str(self.pct)) / Decimal("100") preserves 3dp.
        """
        if self.mode == self.MODE_QTY:
            return q2(q4(self.qty_kg) * q2(self.rate_inr_per_kg))
        if self.mode == self.MODE_CIF_INR:
            pct_val = Decimal(str(self.pct if self.pct is not None else 0))
            return q2(q2(self.cif_inr) * (pct_val / Decimal("100")))
        if self.mode == self.MODE_FOB_INR:
            pct_val = Decimal(str(self.pct if self.pct is not None else 0))
            return q2(q2(self.fob_inr) * (pct_val / Decimal("100")))
        return Decimal("0.00")

    def save(self, *args, **kwargs) -> None:
        self.amount_inr = self.compute_amount()
        super().save(*args, **kwargs)
        if self.trade_id:
            self.trade.recompute_totals()


# -----------------------------------------------------------------------------
# IncentiveTradeLine (for RODTEP/ROSTL/MEIS licenses)
# -----------------------------------------------------------------------------
class IncentiveTradeLine(models.Model):
    """
    Trade line for Incentive Licenses (RODTEP/ROSTL/MEIS).
    Simplified: license + value + rate% = amount.
    """

    trade = models.ForeignKey(
        LicenseTrade,
        on_delete=models.CASCADE,
        related_name="incentive_lines",
        db_index=True,
    )

    incentive_license = models.ForeignKey(
        "license.IncentiveLicense",
        on_delete=models.PROTECT,
        related_name="trade_lines",
        help_text="The incentive license being traded",
    )

    license_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="License value in INR",
    )

    # CRITICAL: rate_pct must be 3 decimal places — never round to 2dp before dividing by 100
    rate_pct = models.DecimalField(
        max_digits=9,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="Billing rate as percentage",
    )

    amount_inr = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculated amount = license_value x rate_pct / 100",
    )

    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "trade_incentivetradeline"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"IncentiveLine[{self.id}] {self.incentive_license} -> {self.amount_inr}"

    def compute_amount(self) -> Decimal:
        """
        Compute amount from license_value and rate_pct.

        PRECISION CRITICAL: rate_pct is a 3dp field. Must NOT pass through q2()
        before dividing by 100.
        """
        rate_val = Decimal(str(self.rate_pct if self.rate_pct is not None else 0))
        return q2(q2(self.license_value) * (rate_val / Decimal("100")))

    def save(self, *args, **kwargs) -> None:
        self.amount_inr = self.compute_amount()
        super().save(*args, **kwargs)
        if self.trade_id:
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
        managed = False
        db_table = "trade_licensetradepayment"
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        return f"Payment[{self.id}] Trade#{self.trade_id} {q2(self.amount)} on {self.date}"


# -----------------------------------------------------------------------------
# Signals
# -----------------------------------------------------------------------------
@receiver(pre_delete, sender=LicenseTrade)
def clear_boe_invoice_on_trade_delete(sender, instance, **kwargs):
    """When a trade is deleted, clear the invoice_no from the associated BOE."""
    if instance.boe and instance.invoice_number:
        if instance.boe.invoice_no == instance.invoice_number:
            instance.boe.invoice_no = None
            instance.boe.invoice_date = None
            instance.boe.save(update_fields=["invoice_no", "invoice_date"])


@receiver(post_save, sender=IncentiveTradeLine)
def update_incentive_license_on_trade_line_save(sender, instance, **kwargs):
    """When an IncentiveTradeLine is saved, update the related IncentiveLicense sold status."""
    if instance.incentive_license and instance.trade.direction == "SALE":
        instance.incentive_license.update_sold_status()


@receiver(pre_delete, sender=IncentiveTradeLine)
def update_incentive_license_on_trade_line_delete(sender, instance, **kwargs):
    """When an IncentiveTradeLine is deleted, update the related IncentiveLicense sold status."""
    if instance.incentive_license and instance.trade.direction == "SALE":
        instance.incentive_license.update_sold_status()
