# trade/models.py
import re
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum, Q, F
from django.db.models.signals import pre_delete
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
    Build a 3-letter alpha prefix from company name.
    Example: 'Labdhi Mercantile LLP' -> 'LAB'
    """
    if not name:
        return "INV"
    letters = re.sub(r"[^A-Za-z]", "", name).upper()
    return (letters[:3] or "INV")


# -----------------------------------------------------------------------------
# LicenseTrade (header)
# -----------------------------------------------------------------------------
class LicenseTrade(models.Model):
    """Trade header (Purchase / Sale). Invoice-level details & totals only."""
    DIR_PURCHASE = "PURCHASE"
    DIR_SALE = "SALE"
    DIR_CHOICES = ((DIR_PURCHASE, "Purchase"), (DIR_SALE, "Sale"))

    direction = models.CharField(max_length=10, choices=DIR_CHOICES, db_index=True)

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
        ordering = ["-created_on"]
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
        Recompute subtotal, roundoff, and total from lines and
        persist via queryset.update() to avoid triggering save() again.
        """
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
        self.amount_inr = self.compute_amount()
        super().save(*args, **kwargs)
        if self.trade_id:
            # Safe: recompute uses queryset.update(), so no recursion
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
