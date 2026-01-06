# allotment/models.py
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_UP
from typing import Optional

from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property

from core.constants import (
    ROW_TYPE_CHOICES,
    DEC_0,
    DEC_000,
)

# Note: TYPE_CHOICES imported in case you want to use it in forms/serializers here

# Decimal helper
_D = Decimal


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
# Allotment models
# -----------------------------
from core.models import AuditModel


class AllotmentModel(AuditModel):
    company = models.ForeignKey(
        "core.CompanyModel",
        related_name="company_allotments",
        on_delete=models.CASCADE,
    )
    type = models.CharField(max_length=2, choices=ROW_TYPE_CHOICES, default=ROW_TYPE_CHOICES[1][0])
    required_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    unit_value_per_unit = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    cif_fc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        null=True,
        blank=True,
    )
    cif_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        null=True,
        blank=True,
    )
    exchange_rate = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        null=True,
        blank=True,
    )
    item_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    contact_number = models.CharField(max_length=255, null=True, blank=True)
    invoice = models.CharField(max_length=255, null=True, blank=True)
    estimated_arrival_date = models.DateField(null=True, blank=True)
    bl_detail = models.CharField(max_length=255, null=True, blank=True)
    port = models.ForeignKey(
        "core.PortModel",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="allotments",
    )
    related_company = models.ForeignKey(
        "core.CompanyModel",
        related_name="related_company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    is_boe = models.BooleanField(default=False)
    is_allotted = models.BooleanField(default=False, help_text="True if DFIA licenses are allotted")
    is_approved = models.BooleanField(default=False, help_text="Indicates if the allotment has been approved")

    class Meta:
        ordering = ["estimated_arrival_date"]
        indexes = [
            models.Index(fields=['company', 'estimated_arrival_date']),
            models.Index(fields=['port', 'estimated_arrival_date']),
            models.Index(fields=['related_company']),
            models.Index(fields=['estimated_arrival_date']),
            models.Index(fields=['is_boe', 'is_allotted']),
            models.Index(fields=['type']),
            models.Index(fields=['invoice']),
        ]

    def __str__(self):
        return (
            f"{self.item_name} {self.company.name} "
            f"{self.invoice or ''} {self.required_quantity} "
            f"{self.estimated_arrival_date or ''}".strip()
        )

    def save(self, *args, **kwargs):
        """
        Auto-calculate fields before saving:
        1. If unit_value_per_unit and required_quantity provided, calculate cif_fc = unit_value_per_unit * required_quantity
        2. If cif_fc and required_quantity provided, calculate unit_value_per_unit = cif_fc / required_quantity
        3. If cif_fc and exchange_rate provided, calculate cif_inr = cif_fc * exchange_rate
        """
        unit_value = _to_decimal(self.unit_value_per_unit, DEC_0)
        required_qty = _to_decimal(self.required_quantity, DEC_0)
        cif_fc_val = _to_decimal(self.cif_fc, DEC_0)
        exchange_rate_val = _to_decimal(self.exchange_rate, DEC_0)

        # Priority 1: Calculate cif_fc from unit_value_per_unit and required_quantity
        if unit_value > DEC_0 and required_qty > DEC_0:
            self.cif_fc = (unit_value * required_qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            cif_fc_val = self.cif_fc  # Update for next calculations
        # Priority 2: If cif_fc provided but unit_value not, calculate unit_value
        elif cif_fc_val > DEC_0 and required_qty > DEC_0 and unit_value == DEC_0:
            self.unit_value_per_unit = (cif_fc_val / required_qty).quantize(Decimal("0.001"), rounding=ROUND_UP)

        # Calculate cif_inr from cif_fc and exchange_rate (always recalculate if both present)
        cif_fc_val = _to_decimal(self.cif_fc, DEC_0)
        if cif_fc_val > DEC_0 and exchange_rate_val > DEC_0:
            self.cif_inr = (cif_fc_val * exchange_rate_val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        super().save(*args, **kwargs)

    @cached_property
    def required_value(self) -> Decimal:
        """Required value = required_quantity * unit_value_per_unit (with 2 decimal places)."""
        val = _to_decimal(self.required_quantity) * _to_decimal(self.unit_value_per_unit)
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @cached_property
    def dfia_list(self) -> str:
        """Comma-separated DFIA numbers for items linked to this allotment."""
        dfia_numbers = self.allotment_details.values_list("item__license__license_number", flat=True)
        return ", ".join(filter(None, dfia_numbers))

    @cached_property
    def balanced_quantity(self) -> Decimal:
        """
        Remaining required quantity = required_quantity - SUM(allotment_details.qty)
        Returns Decimal (never negative).
        """
        total_allocated = _to_decimal(
            self.allotment_details.aggregate(
                total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField())
            )["total"],
            DEC_000,
        )
        remaining = _to_decimal(self.required_quantity, DEC_000) - total_allocated
        return remaining if remaining >= DEC_000 else DEC_000

    @cached_property
    def alloted_quantity(self) -> Decimal:
        """Total quantity allocated to this allotment (Decimal)."""
        total = _to_decimal(
            self.allotment_details.aggregate(
                total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField())
            )["total"],
            DEC_000,
        )
        return total

    @cached_property
    def allotted_value(self) -> Decimal:
        """Total CIF (fc) value allocated to this allotment (Decimal)."""
        total = _to_decimal(
            self.allotment_details.aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )
        return total


class AllotmentItems(AuditModel):
    item = models.ForeignKey(
        "license.LicenseImportItemsModel",
        on_delete=models.CASCADE,
        related_name="allotment_details",
        null=True,
        blank=True,
    )
    allotment = models.ForeignKey(
        "allotment.AllotmentModel",
        on_delete=models.CASCADE,
        related_name="allotment_details",
        null=True,
        blank=True,
    )
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
        decimal_places=0,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    is_boe = models.BooleanField(default=False)

    class Meta:
        ordering = ["qty"]
        unique_together = ("item", "allotment")

    def __str__(self):
        return getattr(self.item, "description", "Unknown Item")

    @cached_property
    def serial_number(self) -> Optional[str]:
        return getattr(self.item, "serial_number", None)

    @cached_property
    def ledger(self):
        return getattr(self.item.license, "ledger_date", None)

    @cached_property
    def product_description(self) -> str:
        return getattr(self.item, "description", "")

    @cached_property
    def license_number(self) -> Optional[str]:
        return getattr(self.item.license, "license_number", None)

    @cached_property
    def license_date(self):
        return getattr(self.item.license, "license_date", None)

    @cached_property
    def exporter(self):
        return getattr(self.item.license, "exporter", None)

    @cached_property
    def license_expiry(self):
        return getattr(self.item.license, "license_expiry_date", None)

    @cached_property
    def registration_number(self) -> Optional[str]:
        return getattr(self.item.license, "registration_number", None)

    @cached_property
    def registration_date(self):
        return getattr(self.item.license, "registration_date", None)

    @cached_property
    def notification_number(self) -> Optional[str]:
        return getattr(self.item.license, "notification_number", None)

    @cached_property
    def file_number(self) -> Optional[str]:
        return getattr(self.item.license, "file_number", None)

    @cached_property
    def port_code(self):
        return getattr(self.item.license, "port", None)

    @cached_property
    def get_delete_url(self) -> str:
        return f"{reverse('allotment-item-delete', kwargs={'pk': self.pk})}?allotment_id={self.allotment_id}"


# -----------------------------
# Signals — Stock Update
# -----------------------------
def _update_balance_sync(item_id: int) -> None:
    """Update balance values synchronously (faster than Celery task)."""
    try:
        from license.models import LicenseImportItemsModel
        from core.scripts.calculate_balance import update_balance_values

        item = LicenseImportItemsModel.objects.get(id=item_id)
        update_balance_values(item)
    except Exception:
        # swallow exceptions to avoid failing DB writes
        pass


@receiver(post_save, sender=AllotmentItems, dispatch_uid="update_stock")
def update_stock(sender, instance, **kwargs):
    """Update stock balance synchronously after save."""
    item = instance.item
    if not item:
        return

    # Update immediately instead of scheduling a task
    def _job():
        _update_balance_sync(item.id)

    try:
        transaction.on_commit(_job)
    except Exception:
        # fallback immediate invocation in environments without on_commit
        _job()


@receiver(post_delete, sender=AllotmentItems)
def delete_stock(sender, instance, **kwargs):
    """Update stock balance synchronously after delete."""
    item = instance.item
    if not item:
        return

    # Update immediately instead of scheduling a task
    def _job():
        _update_balance_sync(item.id)

    try:
        transaction.on_commit(_job)
    except Exception:
        # fallback immediate invocation in environments without on_commit
        _job()
