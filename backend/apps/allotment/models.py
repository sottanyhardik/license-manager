# allotment/models.py
"""
Allotment models — managed=False (tables owned by legacy DB).

AllotmentModel: header record for a pre-auth reservation (AT) or transfer (TR).
AllotmentItems: line items linking a LicenseImportItemsModel to an AllotmentModel.

The FK to "license.LicenseImportItemsModel" is a string reference; Django
resolves it lazily so the app can load before apps.license exists.
"""
from decimal import ROUND_HALF_UP, Decimal
from functools import cached_property

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce

from apps.core.models.masters import AuditModel


class AllotmentModel(AuditModel):
    """
    Allotment header.

    Mirrors legacy allotment_allotmentmodel. managed=False — the legacy
    database owns DDL; this class is a read/write proxy only.
    """

    ALLOTMENT_TYPE_CHOICES = [
        ("AT", "Allotment"),
        ("TR", "Transfer"),
    ]

    company = models.ForeignKey(
        "core.CompanyModel",
        on_delete=models.CASCADE,
        related_name="company_allotments",
    )
    type = models.CharField(
        max_length=2,
        choices=ALLOTMENT_TYPE_CHOICES,
        default="AT",
    )
    required_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    unit_value_per_unit = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(0)],
    )
    cif_fc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
    )
    cif_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
    )
    exchange_rate = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=0,
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
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="related_company_allotments",
    )
    is_boe = models.BooleanField(default=False)
    is_allotted = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "allotment_allotmentmodel"
        ordering = ["estimated_arrival_date"]

    def __str__(self):
        return f"{self.item_name} | {self.company}"

    # ------------------------------------------------------------------
    # Computed properties (no save() logic — service layer handles math)
    # ------------------------------------------------------------------

    @property
    def required_value(self) -> Decimal:
        """required_quantity * unit_value_per_unit, rounded to 2 dp."""
        qty = self.required_quantity or Decimal("0")
        uvpu = self.unit_value_per_unit or Decimal("0")
        return (qty * uvpu).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def alloted_quantity(self) -> Decimal:
        """Sum of qty across allotment_details (Coalesce → 0 if none)."""
        result = self.allotment_details.aggregate(
            total=Coalesce(Sum("qty"), Decimal("0"))
        )
        return result["total"]

    @property
    def allotted_value(self) -> Decimal:
        """Sum of cif_fc across allotment_details (Coalesce → 0 if none)."""
        result = self.allotment_details.aggregate(
            total=Coalesce(Sum("cif_fc"), Decimal("0"))
        )
        return result["total"]

    @property
    def balanced_quantity(self) -> Decimal:
        """required_quantity minus alloted_quantity; never negative."""
        diff = (self.required_quantity or Decimal("0")) - self.alloted_quantity
        return max(diff, Decimal("0"))

    @property
    def dfia_list(self) -> str:
        """Comma-joined license_numbers from allotment_details."""
        numbers = (
            self.allotment_details
            .select_related("item__license")
            .values_list("item__license__license_number", flat=True)
        )
        return ", ".join(n for n in numbers if n)


class AllotmentItems(AuditModel):
    """
    Allotment line item.

    Links a LicenseImportItemsModel entry to an AllotmentModel header.
    The FK to "license.LicenseImportItemsModel" is a lazy string reference —
    the license app need not exist at import time.

    managed=False — legacy DB owns the table.
    """

    item = models.ForeignKey(
        "license.LicenseImportItemsModel",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="allotment_details",
    )
    allotment = models.ForeignKey(
        "allotment.AllotmentModel",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="allotment_details",
    )
    cif_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    cif_fc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    qty = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(0)],
    )
    is_boe = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "allotment_allotmentitems"
        ordering = ["qty"]
        unique_together = [("item", "allotment")]

    def __str__(self):
        return f"AllotmentItem #{self.pk}"

    # ------------------------------------------------------------------
    # cached_property helpers — walk self.item.license safely
    # ------------------------------------------------------------------

    def _get_license(self):
        """Return the license object, or None if any FK is missing."""
        item = self.item
        if item is None:
            return None
        return getattr(item, "license", None)

    @cached_property
    def serial_number(self):
        item = self.item
        if item is None:
            return None
        return getattr(item, "serial_number", None)

    @cached_property
    def product_description(self):
        item = self.item
        if item is None:
            return None
        return getattr(item, "description", None)

    @cached_property
    def license_number(self):
        lic = self._get_license()
        if lic is None:
            return None
        return getattr(lic, "license_number", None)

    @cached_property
    def license_date(self):
        lic = self._get_license()
        if lic is None:
            return None
        return getattr(lic, "license_date", None)

    @cached_property
    def license_expiry(self):
        lic = self._get_license()
        if lic is None:
            return None
        return getattr(lic, "license_expiry_date", None)

    @cached_property
    def hs_code(self):
        item = self.item
        if item is None:
            return None
        return getattr(item, "hs_code", None)

    @cached_property
    def exporter(self):
        lic = self._get_license()
        if lic is None:
            return None
        return getattr(lic, "exporter", None)

    @cached_property
    def registration_number(self):
        lic = self._get_license()
        if lic is None:
            return None
        return getattr(lic, "registration_number", None)

    @cached_property
    def notification_number(self):
        lic = self._get_license()
        if lic is None:
            return None
        return getattr(lic, "notification_number", None)

    @cached_property
    def file_number(self):
        lic = self._get_license()
        if lic is None:
            return None
        return getattr(lic, "file_number", None)

    @cached_property
    def port_code(self):
        lic = self._get_license()
        if lic is None:
            return None
        return getattr(lic, "port", None)
