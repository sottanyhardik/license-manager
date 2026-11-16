"""Incentive licences and licence purchases.

Split verbatim from core.py; behaviour unchanged.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.constants import DEC_0, DEC_000
from apps.core.models import AuditModel
from apps.core.utils.decimal_utils import to_decimal as _to_decimal


# -----------------------------
# Incentive License (RODTEP/ROSTL/MEIS)
# -----------------------------
class IncentiveLicense(AuditModel):
    """
    Model for incentive-based licenses: RODTEP, ROSTL, MEIS
    These licenses have a standard 2-year validity from license date.
    """
    LICENSE_TYPE_CHOICES = (
        ('RODTEP', 'RODTEP'),
        ('ROSTL', 'ROSTL'),
        ('MEIS', 'MEIS'),
    )

    SOLD_STATUS_CHOICES = (
        ('NO', 'Not Sold'),
        ('PARTIAL', 'Partially Sold'),
        ('YES', 'Fully Sold'),
    )

    license_type = models.CharField(max_length=10, choices=LICENSE_TYPE_CHOICES, db_index=True)
    license_number = models.CharField(max_length=50, unique=True, db_index=True)
    license_date = models.DateField()
    license_expiry_date = models.DateField(help_text="Auto-calculated as 2 years from license date")

    exporter = models.ForeignKey("core.CompanyModel", on_delete=models.CASCADE, related_name="incentive_licenses")
    port_code = models.ForeignKey("core.PortModel", on_delete=models.CASCADE, related_name="incentive_licenses")

    license_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        help_text="Total license value in INR"
    )

    sold_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        help_text="Total sold value in INR (auto-calculated)"
    )

    balance_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        help_text="Remaining balance in INR (auto-calculated)"
    )

    sold_status = models.CharField(
        max_length=10,
        choices=SOLD_STATUS_CHOICES,
        default='NO',
        db_index=True,
        help_text="Sold status (auto-calculated)"
    )

    # Additional fields for tracking
    is_active = models.BooleanField(default=True)
    notes = models.TextField(null=True, blank=True)

    admin_search_fields = ("license_number", "exporter__name")

    class Meta:
        ordering = ("-license_date", "license_number")
        indexes = [
            models.Index(fields=['license_number']),
            models.Index(fields=['license_type']),
            models.Index(fields=['exporter', 'license_date']),
            models.Index(fields=['license_date']),
            models.Index(fields=['license_expiry_date']),
            models.Index(fields=['is_active']),
            models.Index(fields=['sold_status']),
        ]
        verbose_name = "Incentive License"
        verbose_name_plural = "Incentive Licenses"

    def __str__(self) -> str:
        return f"{self.license_type} - {self.license_number}"

    def save(self, *args, **kwargs):
        """Auto-calculate expiry date as 2 years from license date"""
        if self.license_date and not self.license_expiry_date:
            from dateutil.relativedelta import relativedelta
            self.license_expiry_date = self.license_date + relativedelta(years=2)

        # Calculate balance if license_value changed
        if self.license_value is not None:
            self.balance_value = self.license_value - self.sold_value

        super().save(*args, **kwargs)

    def update_sold_status(self):
        """
        Update sold_value, balance_value, and sold_status based on related trades.
        Call this method after trade changes.
        """
        from django.db.models import Sum
        from decimal import Decimal

        # Calculate sold value from SALE trades
        sold = self.trade_lines.filter(
            trade__direction='SALE'
        ).aggregate(
            total=Sum('license_value')
        )['total'] or Decimal('0.00')

        self.sold_value = sold
        self.balance_value = self.license_value - self.sold_value

        # Determine sold status
        if self.sold_value == Decimal('0.00'):
            self.sold_status = 'NO'
        elif self.balance_value <= Decimal('0.00'):
            self.sold_status = 'YES'
        else:
            self.sold_status = 'PARTIAL'

        # Use update() to avoid triggering signals
        IncentiveLicense.objects.filter(pk=self.pk).update(
            sold_value=self.sold_value,
            balance_value=self.balance_value,
            sold_status=self.sold_status
        )

    def get_sold_value(self):
        """Get cached sold value (deprecated - use sold_value field directly)"""
        return self.sold_value

    def get_balance_value(self):
        """Get cached balance value (deprecated - use balance_value field directly)"""
        return self.balance_value


# -----------------------------
# License Purchase (unchanged but Decimal-safe)
# -----------------------------
class LicensePurchase(AuditModel):
    MODE_AMOUNT = "AMOUNT"
    MODE_QTY = "QTY"
    MODE_CHOICES = (
        (MODE_AMOUNT, "Amount-based"),
        (MODE_QTY, "Quantity-based"),
    )

    SRC_FOB_INR = "FOB_INR"
    SRC_CIF_INR = "CIF_INR"
    SRC_CIF_USD = "CIF_USD"
    AMOUNT_SOURCE_CHOICES = (
        (SRC_FOB_INR, "FOB (INR)"),
        (SRC_CIF_INR, "CIF (INR)"),
        (SRC_CIF_USD, "CIF (USD)"),
    )

    # relations
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="purchases")
    purchasing_entity = models.ForeignKey("core.CompanyModel", null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name="entity_purchases")
    supplier = models.ForeignKey("core.CompanyModel", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="supplier_purchases")

    supplier_pan = models.CharField(max_length=32, null=True, blank=True)
    supplier_gst = models.CharField(max_length=32, null=True, blank=True)

    invoice_number = models.CharField(max_length=128, null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    invoice_copy = models.FileField(upload_to="license_purchases/invoices/", null=True, blank=True)

    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_AMOUNT)

    amount_source = models.CharField(max_length=10, choices=AMOUNT_SOURCE_CHOICES, default=SRC_FOB_INR)
    fob_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0, validators=[MinValueValidator(DEC_0)])
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0, validators=[MinValueValidator(DEC_0)])
    cif_usd = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0, validators=[MinValueValidator(DEC_0)])
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=6, default=DEC_0,
                                        validators=[MinValueValidator(DEC_0)])
    markup_pct = models.DecimalField(max_digits=15, decimal_places=6, default=DEC_0,
                                     validators=[MinValueValidator(DEC_0)])

    product_name = models.CharField(max_length=255, null=True, blank=True)
    quantity_kg = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_000,
                                      validators=[MinValueValidator(DEC_000)])
    rate_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0,
                                   validators=[MinValueValidator(DEC_0)])

    amount_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0,
                                     validators=[MinValueValidator(DEC_0)])

    class Meta:
        ordering = ["-created_on"]

    def __str__(self):
        base = f"{self.amount_source}" if self.mode == self.MODE_AMOUNT else f"{self.product_name or 'QTY'}"
        return f"Purchase[{self.id}] L#{self.license_id} {base} ₹{self.amount_inr:.2f}"

    def _source_amount(self) -> Decimal:
        if self.amount_source == self.SRC_FOB_INR:
            return _to_decimal(self.fob_inr, DEC_0)
        if self.amount_source == self.SRC_CIF_INR:
            return _to_decimal(self.cif_inr, DEC_0)
        if self.amount_source == self.SRC_CIF_USD:
            return _to_decimal(self.cif_usd, DEC_0)
        return DEC_0

    def _amount_base_inr(self) -> Decimal:
        return self._source_amount()

    def compute_amount_inr(self) -> Decimal:
        if self.mode == self.MODE_AMOUNT:
            source = self._source_amount()
            pct = _to_decimal(self.markup_pct, DEC_0)
            bill = source * (pct / _to_decimal("100"))
            return bill.quantize(DEC_0, rounding=ROUND_HALF_UP)
        q = _to_decimal(self.quantity_kg, DEC_000)
        r = _to_decimal(self.rate_inr, DEC_0)
        amt = q * r
        return amt.quantize(DEC_0, rounding=ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        if self.supplier and not self.supplier_pan:
            try:
                self.supplier_pan = getattr(self.supplier, "pan", self.supplier_pan)
            except Exception:
                pass
        if self.supplier and not self.supplier_gst:
            try:
                self.supplier_gst = getattr(self.supplier, "gst_number", self.supplier_gst)
            except Exception:
                pass

        er = _to_decimal(self.exchange_rate, DEC_0)
        usd = _to_decimal(self.cif_usd, DEC_0)
        inr = _to_decimal(self.cif_inr, DEC_0)

        if er <= DEC_0 and usd > DEC_0 and inr > DEC_0:
            self.exchange_rate = (inr / usd).quantize(_to_decimal("0.001"))

        try:
            if self.markup_pct not in (None, ""):
                self.markup_pct = _to_decimal(self.markup_pct, DEC_0).quantize(_to_decimal("0.000001"))
        except Exception:
            self.markup_pct = DEC_0

        self.amount_inr = self.compute_amount_inr()
        super().save(*args, **kwargs)
