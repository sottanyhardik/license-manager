# bill_of_entry/models.py
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, DivisionByZero

from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property

from core.constants import (
    TYPE_CHOICES,
    ROW_TYPE_CHOICES,
    DEC_0,
    DEC_000,
)
from core.models import AuditModel, CompanyModel

# Locally-used decimal for 4 dp exchange rates
DEC_EX_0 = Decimal("0.0000")


def _to_decimal(value, default: Decimal = DEC_0) -> Decimal:
    """Safely coerce value to Decimal."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


# -----------------------------
# Bill of Entry Model
# -----------------------------
class BillOfEntryModel(AuditModel):
    company = models.ForeignKey(
        CompanyModel,
        related_name="bill_of_entry",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    bill_of_entry_number = models.CharField(max_length=25)
    bill_of_entry_date = models.DateField(null=True, blank=True)
    port = models.ForeignKey(
        "core.PortModel",
        on_delete=models.CASCADE,
        related_name="boe_port",
        null=True,
        blank=True,
    )
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=DEC_EX_0,
        validators=[MinValueValidator(DEC_EX_0)],
    )
    product_name = models.CharField(max_length=255, default="")
    allotment = models.ManyToManyField(
        "allotment.AllotmentModel",
        related_name="bill_of_entry",
        blank=True,
    )
    invoice_no = models.CharField(max_length=255, null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    is_fetch = models.BooleanField(default=False)
    failed = models.IntegerField(default=0)
    appraisement = models.CharField(max_length=255, null=True, blank=True)
    ooc_date = models.CharField(max_length=255, null=True, blank=True)
    cha = models.CharField(max_length=255, null=True, blank=True)
    comments = models.TextField(null=True, blank=True)

    admin_search_fields = ["bill_of_entry_number"]

    class Meta:
        unique_together = ("bill_of_entry_number", "bill_of_entry_date", "port")
        ordering = ("-bill_of_entry_date",)
        verbose_name = "Bill of Entry"
        verbose_name_plural = "Bills of Entry"
        indexes = [
            models.Index(fields=['bill_of_entry_number']),
            models.Index(fields=['company', 'bill_of_entry_date']),
            models.Index(fields=['port', 'bill_of_entry_date']),
            models.Index(fields=['bill_of_entry_date']),
            models.Index(fields=['invoice_no', 'invoice_date']),
            models.Index(fields=['is_fetch']),
            models.Index(fields=['product_name']),
        ]

    def __str__(self):
        return self.bill_of_entry_number

    def save(self, *args, **kwargs):
        """Auto-calculate exchange rate if not explicitly set (Decimal-safe)."""
        if not self.exchange_rate or _to_decimal(self.exchange_rate, DEC_EX_0) == DEC_EX_0:
            try:
                total_fc = self.get_total_fc
                total_inr = self.get_total_inr
                if total_fc > DEC_0:
                    # compute precise division, quantize to 4 dp
                    ex = (total_inr / total_fc).quantize(DEC_EX_0)
                    self.exchange_rate = ex
            except (DivisionByZero, ZeroDivisionError, TypeError, InvalidOperation):
                self.exchange_rate = DEC_EX_0
        super().save(*args, **kwargs)

    @cached_property
    def get_absolute_url(self) -> str:
        return reverse("bill-of-entry-detail", kwargs={"pk": self.pk})

    # --- Computed properties ---
    @cached_property
    def item_details_cached(self):
        return self.item_details.all()

    @cached_property
    def get_total_inr(self) -> Decimal:
        total = self.item_details_cached.aggregate(
            total=Coalesce(Sum("cif_inr"), Value(DEC_0), output_field=DecimalField())
        )["total"]
        return _to_decimal(total, DEC_0).quantize(DEC_0)

    @cached_property
    def get_total_fc(self) -> Decimal:
        total = self.item_details_cached.aggregate(
            total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
        )["total"]
        return _to_decimal(total, DEC_0).quantize(DEC_0)

    @cached_property
    def get_total_quantity(self) -> Decimal:
        total = self.item_details_cached.aggregate(
            total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField())
        )["total"]
        return _to_decimal(total, DEC_000).quantize(DEC_000)

    @cached_property
    def get_licenses(self) -> str:
        return ", ".join(
            item.sr_number.license.license_number
            for item in self.item_details_cached
            if getattr(item.sr_number, "license", None)
        )

    @cached_property
    def get_unit_price(self) -> Decimal:
        total_qty = self.get_total_quantity
        if total_qty > DEC_000:
            try:
                up = (self.get_total_fc / total_qty).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
                return _to_decimal(up, DEC_000)
            except (DivisionByZero, ZeroDivisionError, InvalidOperation):
                return DEC_000
        return DEC_000

    @cached_property
    def get_exchange_rate(self) -> Decimal:
        total_fc = self.get_total_fc
        if total_fc > DEC_0:
            try:
                ex = (self.get_total_inr / total_fc).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
                return _to_decimal(ex, DEC_0)
            except (DivisionByZero, ZeroDivisionError, InvalidOperation):
                return DEC_0
        return DEC_0


# -----------------------------
# Row Details
# -----------------------------
class RowDetails(AuditModel):
    bill_of_entry = models.ForeignKey(
        BillOfEntryModel,
        on_delete=models.CASCADE,
        related_name="item_details",
        null=True,
        blank=True,
    )
    row_type = models.CharField(max_length=2, choices=ROW_TYPE_CHOICES, default=ROW_TYPE_CHOICES[1][0])
    sr_number = models.ForeignKey(
        "license.LicenseImportItemsModel",
        on_delete=models.CASCADE,
        related_name="item_details",
    )
    transaction_type = models.CharField(max_length=2, choices=TYPE_CHOICES, default=TYPE_CHOICES[1][0])
    cif_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    cif_fc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    qty = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=DEC_000,
        validators=[MinValueValidator(DEC_000)],
    )

    admin_search_fields = (
        "sr_number__license__license_number",
        "bill_of_entry__bill_of_entry_number",
    )

    class Meta:
        ordering = ["transaction_type", "bill_of_entry__bill_of_entry_date"]
        unique_together = ("bill_of_entry", "sr_number", "transaction_type")
        verbose_name = "Item Detail"
        verbose_name_plural = "Item Details"

    def __str__(self):
        return str(self.sr_number)


# -----------------------------
# Signals for stock updates
# -----------------------------
def _schedule_update_balance(item_id: int) -> None:
    """Schedule update_balance_values_task after transaction commit (safe for tests)."""

    def _job():
        try:
            from bill_of_entry.tasks import update_balance_values_task

            try:
                update_balance_values_task.delay(item_id)
            except Exception:
                update_balance_values_task(item_id)
        except Exception:
            # swallow exceptions to avoid failing DB writes
            pass

    try:
        transaction.on_commit(_job)
    except Exception:
        # fallback immediate invocation in environments without on_commit
        _job()


@receiver(post_save, sender=RowDetails, dispatch_uid="update_stock_on_save")
def update_stock(sender, instance, **kwargs):
    """Trigger stock update task after save."""
    item = instance.sr_number
    if not item:
        return
    _schedule_update_balance(item.id)


@receiver(post_delete, sender=RowDetails)
def delete_stock(sender, instance, **kwargs):
    """Trigger stock update task after delete."""
    item = instance.sr_number
    if not item:
        return
    _schedule_update_balance(item.id)
