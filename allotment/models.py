from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property

# -----------------------------
# Constants
# -----------------------------
CREDIT = 'C'
DEBIT = 'D'

TYPE_CHOICES = (
    (CREDIT, 'Credit'),
    (DEBIT, 'Debit'),
)

ARO = 'AR'
ALLOTMENT = 'AT'

ROW_TYPE = (
    (ARO, 'ARO'),
    (ALLOTMENT, 'Allotment'),
)


# -----------------------------
# Allotment Models
# -----------------------------
class AllotmentModel(models.Model):
    company = models.ForeignKey(
        'core.CompanyModel',
        related_name='company_allotments',
        on_delete=models.CASCADE
    )
    type = models.CharField(max_length=2, choices=ROW_TYPE, default=ALLOTMENT)
    required_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    unit_value_per_unit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    item_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    contact_number = models.CharField(max_length=255, null=True, blank=True)
    invoice = models.CharField(max_length=255, null=True, blank=True)
    estimated_arrival_date = models.DateField(null=True, blank=True)
    bl_detail = models.CharField(max_length=255, null=True, blank=True)
    port = models.ForeignKey(
        'core.PortModel',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="allotments"
    )
    related_company = models.ForeignKey(
        'core.CompanyModel',
        related_name='related_company',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    modified_on = models.DateField(auto_now=True)

    class Meta:
        ordering = ['estimated_arrival_date']

    def __str__(self):
        return (
            f"{self.item_name} {self.company.name} "
            f"{self.invoice or ''} {self.required_quantity} "
            f"{self.estimated_arrival_date or ''}".strip()
        )

    @cached_property
    def required_value(self):
        return round(self.required_quantity * self.unit_value_per_unit, 0)

    @cached_property
    def dfia_list(self):
        # safer join for large querysets
        dfia_numbers = self.allotment_details.values_list(
            'item__license__license_number', flat=True
        )
        return ', '.join(filter(None, dfia_numbers))

    @cached_property
    def balanced_quantity(self):
        qty = self.allotment_details.aggregate(total=Sum('qty'))['total'] or 0
        return int(self.required_quantity - qty)

    @cached_property
    def alloted_quantity(self):
        qty = self.allotment_details.aggregate(total=Sum('qty'))['total'] or 0
        return int(qty)

    @cached_property
    def allotted_value(self):
        value = self.allotment_details.aggregate(total=Sum('cif_fc'))['total'] or 0
        return int(value)


class AllotmentItems(models.Model):
    item = models.ForeignKey(
        'license.LicenseImportItemsModel',
        on_delete=models.CASCADE,
        related_name='allotment_details',
        null=True,
        blank=True
    )
    allotment = models.ForeignKey(
        'allotment.AllotmentModel',
        on_delete=models.CASCADE,
        related_name='allotment_details',
        null=True,
        blank=True
    )
    cif_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    cif_fc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    is_boe = models.BooleanField(default=False)

    class Meta:
        ordering = ['qty']
        unique_together = ('item', 'allotment')

    def __str__(self):
        return getattr(self.item, 'description', 'Unknown Item')

    @cached_property
    def serial_number(self):
        return getattr(self.item, 'serial_number', '')

    @cached_property
    def ledger(self):
        return getattr(self.item.license, 'ledger_date', None)

    @cached_property
    def product_description(self):
        return getattr(self.item, 'description', '')

    @cached_property
    def license_number(self):
        return getattr(self.item.license, 'license_number', '')

    @cached_property
    def license_date(self):
        return getattr(self.item.license, 'license_date', None)

    @cached_property
    def exporter(self):
        return getattr(self.item.license, 'exporter', '')

    @cached_property
    def license_expiry(self):
        return getattr(self.item.license, 'license_expiry_date', None)

    @cached_property
    def registration_number(self):
        return getattr(self.item.license, 'registration_number', '')

    @cached_property
    def registration_date(self):
        return getattr(self.item.license, 'registration_date', None)

    @cached_property
    def notification_number(self):
        return getattr(self.item.license, 'notification_number', '')

    @cached_property
    def file_number(self):
        return getattr(self.item.license, 'file_number', '')

    @cached_property
    def port_code(self):
        return getattr(self.item.license, 'port', None)

    @cached_property
    def get_delete_url(self):
        return f"{reverse('allotment-item-delete', kwargs={'pk': self.pk})}?allotment_id={self.allotment_id}"


# -----------------------------
# Signals — Stock Update
# -----------------------------
@receiver(post_save, sender=AllotmentItems, dispatch_uid="update_stock")
def update_stock(sender, instance, **kwargs):
    """Trigger background balance update after save."""
    item = instance.item
    if not item:
        return
    from bill_of_entry.tasks import update_balance_values_task
    try:
        update_balance_values_task.delay(item.id)
    except Exception:
        update_balance_values_task(item.id)


@receiver(post_delete, sender=AllotmentItems)
def delete_stock(sender, instance, **kwargs):
    """Trigger background balance update after delete."""
    item = instance.item
    if not item:
        return
    from bill_of_entry.tasks import update_balance_values_task
    try:
        update_balance_values_task.delay(item.id)
    except Exception:
        update_balance_values_task(item.id)
