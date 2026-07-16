"""Invoice and InvoiceItem models.

These are standalone leaf models kept importable from ``apps.license.models``.
"""
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from apps.core.constants import DEC_0, DEC_000
from apps.core.models import InvoiceEntity
from apps.core.utils.validation import validate_pan_number


BILLING_MODE_KG = "kg"
BILLING_MODE_CIF = "cif"
BILLING_MODE_FOB = "fob"
BILLING_MODE_CHOICES = (
    (BILLING_MODE_KG, "KG"),
    (BILLING_MODE_CIF, "CIF %"),
    (BILLING_MODE_FOB, "FOB %"),
)

SALE_TYPE_ITEM = "item"
SALE_TYPE_FULL = "full"
SALE_TYPE_CHOICES = (
    (SALE_TYPE_ITEM, "Item"),
    (SALE_TYPE_FULL, "Full"),
)

GST_VALIDATOR = RegexValidator(
    regex=r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
    message="Enter a valid GST number.",
)


def _clean_required(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_optional(value: object | None, *, uppercase: bool = False) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if uppercase:
        cleaned = cleaned.upper()
    return cleaned or None


class Invoice(models.Model):
    bills_of_entry = models.ForeignKey(
        "bill_of_entry.BillOfEntryModel",
        related_name="invoices",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    from_entity = models.ForeignKey(InvoiceEntity, on_delete=models.CASCADE)
    to_company_name = models.CharField(max_length=255)
    to_company_pan = models.CharField(max_length=15, null=True, blank=True)
    to_company_gst_number = models.CharField(max_length=15, null=True, blank=True)
    to_company_address_line_1 = models.TextField()
    to_company_address_line_2 = models.TextField(blank=True)
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField(default=date.today)

    billing_mode = models.CharField(max_length=10, choices=BILLING_MODE_CHOICES)
    total_qty = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=DEC_000,
        validators=[MinValueValidator(DEC_000)],
    )
    total_cif_fc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    total_cif_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    total_fob_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    total_amount_in_words = models.TextField(null=True, blank=True)

    sale_type = models.CharField(max_length=10, choices=SALE_TYPE_CHOICES, default=SALE_TYPE_ITEM)

    def _normalize_fields(self):
        self.to_company_name = _clean_required(self.to_company_name)
        self.to_company_address_line_1 = _clean_required(self.to_company_address_line_1)
        self.to_company_address_line_2 = _clean_required(self.to_company_address_line_2)
        self.invoice_number = _clean_required(self.invoice_number)
        self.to_company_pan = _clean_optional(self.to_company_pan, uppercase=True)
        self.to_company_gst_number = _clean_optional(
            self.to_company_gst_number,
            uppercase=True,
        )

    def clean_fields(self, exclude=None):
        self._normalize_fields()
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        self._normalize_fields()

        errors = {}
        if not self.to_company_name:
            errors["to_company_name"] = "Recipient company name is required."
        if not self.to_company_address_line_1:
            errors["to_company_address_line_1"] = "Recipient address line 1 is required."
        if not self.invoice_number:
            errors["invoice_number"] = "Invoice number is required."
        if self.to_company_pan:
            try:
                self.to_company_pan = validate_pan_number(self.to_company_pan)
            except ValidationError as exc:
                errors["to_company_pan"] = exc.messages
        if self.to_company_gst_number:
            try:
                GST_VALIDATOR(self.to_company_gst_number)
            except ValidationError as exc:
                errors["to_company_gst_number"] = exc.messages
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if kwargs.get("update_fields") is not None and not kwargs["update_fields"]:
            return super().save(*args, **kwargs)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(total_qty__gte=DEC_000)
                    & models.Q(total_cif_fc__gte=DEC_0)
                    & models.Q(total_cif_inr__gte=DEC_0)
                    & models.Q(total_fob_inr__gte=DEC_0)
                    & models.Q(total_amount__gte=DEC_0)
                ),
                name="license_invoice_non_negative_totals",
            ),
        ]


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="items", on_delete=models.CASCADE)
    sr_number = models.ForeignKey(
        "license.LicenseImportItemsModel",
        on_delete=models.CASCADE,
        related_name="invoice_items",
    )
    license_no = models.CharField(max_length=50)  # filled from sr_number.license.license_number
    hs_code = models.CharField(max_length=10, default="490700")
    qty = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(DEC_000)],
    )
    cif_fc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(DEC_0)],
    )
    cif_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(DEC_0)],
    )
    fob_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(DEC_0)],
    )

    rate = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(DEC_0)])
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(DEC_0)])

    def _normalize_fields(self):
        if self.sr_number_id and not self.license_no:
            self.license_no = self.sr_number.license.license_number
        self.license_no = _clean_required(self.license_no)
        self.hs_code = _clean_required(self.hs_code)

    def clean_fields(self, exclude=None):
        self._normalize_fields()
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        self._normalize_fields()

        errors = {}
        if not self.license_no:
            errors["license_no"] = "License number is required."
        if not self.hs_code:
            errors["hs_code"] = "HS code is required."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if kwargs.get("update_fields") is not None and not kwargs["update_fields"]:
            return super().save(*args, **kwargs)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.license_no} - {self.amount}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(qty__gte=DEC_000) | models.Q(qty__isnull=True))
                    & (models.Q(cif_fc__gte=DEC_0) | models.Q(cif_fc__isnull=True))
                    & (models.Q(cif_inr__gte=DEC_0) | models.Q(cif_inr__isnull=True))
                    & (models.Q(fob_inr__gte=DEC_0) | models.Q(fob_inr__isnull=True))
                    & models.Q(rate__gte=DEC_0)
                    & models.Q(amount__gte=DEC_0)
                ),
                name="license_invoiceitem_non_negative_values",
            ),
        ]
