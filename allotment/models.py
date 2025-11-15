# allotment/models.py — cleaned Decimal-safe version

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property

# Decimal helpers
_D = Decimal
DEC_0 = _D("0.00")
DEC_000 = _D("0.000")


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
# Constants
# -----------------------------
CREDIT = "C"
DEBIT = "D"

TYPE_CHOICES = ((CREDIT, "Credit"), (DEBIT, "Debit"))

ARO = "AR"
ALLOTMENT = "AT"

ROW_TYPE = ((ARO, "ARO"), (ALLOTMENT, "Allotment"))


# -----------------------------
# Allotment Models
# -----------------------------
class AllotmentModel(models.Model):
    company = models.ForeignKey(
        "core.CompanyModel",
        related_name="company_allotments",
        on_delete=models.CASCADE,
    )
    type = models.CharField(max_length=2, choices=ROW_TYPE, default=ALLOTMENT)
    required_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    unit_value_per_unit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
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
    modified_on = models.DateField(auto_now=True)

    class Meta:
        ordering = ["estimated_arrival_date"]

    def __str__(self):
        return (
            f"{self.item_name} {self.company.name} "
            f"{self.invoice or ''} {self.required_quantity} "
            f"{self.estimated_arrival_date or ''}".strip()
        )

    @cached_property
    def required_value(self) -> Decimal:
        """Required value = required_quantity * unit_value_per_unit (rounded to 0 d.p.)."""
        val = _to_decimal(self.required_quantity) * _to_decimal(self.unit_value_per_unit)
        return val.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

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
            self.allotment_details.aggregate(total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))[
                "total"],
            DEC_000,
        )
        remaining = _to_decimal(self.required_quantity, DEC_000) - total_allocated
        return remaining if remaining >= DEC_000 else DEC_000

    @cached_property
    def alloted_quantity(self) -> Decimal:
        """Total quantity allocated to this allotment (Decimal)."""
        total = _to_decimal(
            self.allotment_details.aggregate(total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))[
                "total"],
            DEC_000,
        )
        return total

    @cached_property
    def allotted_value(self) -> Decimal:
        """Total CIF (fc) value allocated to this allotment (Decimal)."""
        total = _to_decimal(
            self.allotment_details.aggregate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))[
                "total"],
            DEC_0,
        )
        return total


class AllotmentItems(models.Model):
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
        decimal_places=2,
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
@receiver(post_save, sender=AllotmentItems, dispatch_uid="update_stock")
def update_stock(sender, instance, **kwargs):
    """Schedule background balance update after save (runs after DB commit)."""
    item = instance.item
    if not item:
        return

    def _job():
        try:
            from bill_of_entry.tasks import update_balance_values_task
            # prefer Celery async delay if available
            try:
                update_balance_values_task.delay(item.id)
            except Exception:
                update_balance_values_task(item.id)
        except Exception:
            # swallow so saving isn't blocked by task issues
            pass

    try:
        transaction.on_commit(_job)
    except Exception:
        # fallback immediate call if on_commit unavailable
        _job()


@receiver(post_delete, sender=AllotmentItems)
def delete_stock(sender, instance, **kwargs):
    """Schedule background balance update after delete (runs after DB commit)."""
    item = instance.item
    if not item:
        return

    def _job():
        try:
            from bill_of_entry.tasks import update_balance_values_task
            try:
                update_balance_values_task.delay(item.id)
            except Exception:
                update_balance_values_task(item.id)
        except Exception:
            pass

    try:
        transaction.on_commit(_job)
    except Exception:
        _job()
