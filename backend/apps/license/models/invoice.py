"""Invoice and InvoiceItem models (split from the former models.py).

Standalone leaf models — referenced by nothing else in the app except each other.
"""
from datetime import date

from django.core.validators import RegexValidator
from django.db import models

from apps.core.constants import DEC_0, DEC_000
from apps.core.models import InvoiceEntity


class Invoice(models.Model):
    bills_of_entry = models.ForeignKey("bill_of_entry.BillOfEntryModel", related_name="invoices", blank=True,
                                       null=True,
                                       on_delete=models.CASCADE)
    from_entity = models.ForeignKey(InvoiceEntity, on_delete=models.CASCADE)
    to_company_name = models.CharField(max_length=255)
    to_company_pan = models.CharField(max_length=15, null=True, blank=True, validators=[
        RegexValidator(regex=r'^[A-Z]{5}[0-9]{4}[A-Z]$', message="Enter a valid PAN number.")])
    to_company_gst_number = models.CharField(max_length=15, null=True, blank=True, validators=[
        RegexValidator(regex=r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
                       message="Enter a valid GST number.")])
    to_company_address_line_1 = models.TextField()
    to_company_address_line_2 = models.TextField(blank=True)
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField(default=date.today)
    BILLING_MODE_CHOICES = [("kg", "KG"), ("cif", "CIF %"), ("fob", "FOB %")]

    billing_mode = models.CharField(max_length=10, choices=BILLING_MODE_CHOICES)
    total_qty = models.DecimalField(max_digits=12, decimal_places=3, default=DEC_000)
    total_cif_fc = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    total_cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    total_fob_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    total_amount_in_words = models.TextField(null=True, blank=True)

    sale_type = models.CharField(max_length=10, choices=[("item", "Item"), ("full", "Full")], default="item")


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="items", on_delete=models.CASCADE)
    sr_number = models.ForeignKey("license.LicenseImportItemsModel", on_delete=models.CASCADE,
                                  related_name="invoice_items")
    license_no = models.CharField(max_length=50)  # filled from sr_number.license.license_number
    hs_code = models.CharField(max_length=10, default="490700")
    qty = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    cif_fc = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    fob_inr = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    rate = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    def save(self, *args, **kwargs):
        if self.sr_number and not self.license_no:
            self.license_no = self.sr_number.license.license_number
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.license_no} - {self.amount}"
