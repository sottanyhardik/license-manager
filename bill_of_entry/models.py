from decimal import Decimal, DivisionByZero
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property

from core.models import AuditModel, InvoiceEntity, CompanyModel


# -----------------------------
# Constants
# -----------------------------
Credit = 'C'
Debit = 'D'
TYPE_CHOICES = (
    (Credit, 'Credit'),
    (Debit, 'Debit'),
)

ARO = 'AR'
ALLOTMENT = 'AT'
ROW_TYPE = (
    (ARO, 'ARO'),
    (ALLOTMENT, 'Allotment'),
)


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
        'core.PortModel',
        on_delete=models.CASCADE,
        related_name='boe_port',
        null=True,
        blank=True,
    )
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('0.0000'),
        validators=[MinValueValidator(Decimal('0.0000'))],
    )
    product_name = models.CharField(max_length=255, default='')
    allotment = models.ManyToManyField(
        'allotment.AllotmentModel',
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

    admin_search_fields = ['bill_of_entry_number']

    class Meta:
        unique_together = ('bill_of_entry_number', 'bill_of_entry_date', 'port')
        ordering = ('-bill_of_entry_date',)
        verbose_name = "Bill of Entry"
        verbose_name_plural = "Bills of Entry"

    def __str__(self):
        return self.bill_of_entry_number

    def save(self, *args, **kwargs):
        """Auto-calculate exchange rate if not explicitly set."""
        if not self.exchange_rate or self.exchange_rate == Decimal('0.0000'):
            try:
                total_fc = self.get_total_fc
                total_inr = self.get_total_inr
                if total_fc > 0:
                    self.exchange_rate = round(total_inr / total_fc, 4)
            except (ZeroDivisionError, DivisionByZero, TypeError):
                self.exchange_rate = Decimal('0.0000')
        super().save(*args, **kwargs)

    @cached_property
    def get_absolute_url(self):
        return reverse('bill-of-entry-detail', kwargs={'pk': self.pk})

    # --- Computed properties ---
    @cached_property
    def item_details_cached(self):
        return self.item_details.all()

    @cached_property
    def get_total_inr(self):
        total = self.item_details_cached.aggregate(Sum('cif_inr'))['cif_inr__sum']
        return round(total or 0, 2)

    @cached_property
    def get_total_fc(self):
        total = self.item_details_cached.aggregate(Sum('cif_fc'))['cif_fc__sum']
        return round(total or 0, 2)

    @cached_property
    def get_total_quantity(self):
        total = self.item_details_cached.aggregate(Sum('qty'))['qty__sum']
        return round(total or 0, 3)

    @cached_property
    def get_licenses(self):
        return ", ".join([
            item.sr_number.license.license_number
            for item in self.item_details_cached
            if getattr(item.sr_number, 'license', None)
        ])

    @cached_property
    def get_unit_price(self):
        total_qty = self.get_total_quantity
        return round(self.get_total_fc / total_qty, 3) if total_qty > 0 else 0

    @cached_property
    def get_exchange_rate(self):
        total_fc = self.get_total_fc
        return round(self.get_total_inr / total_fc, 3) if total_fc > 0 else 0


# -----------------------------
# Row Details
# -----------------------------
class RowDetails(AuditModel):
    bill_of_entry = models.ForeignKey(
        BillOfEntryModel,
        on_delete=models.CASCADE,
        related_name='item_details',
        null=True,
        blank=True,
    )
    row_type = models.CharField(max_length=2, choices=ROW_TYPE, default=ALLOTMENT)
    sr_number = models.ForeignKey(
        'license.LicenseImportItemsModel',
        on_delete=models.CASCADE,
        related_name='item_details',
    )
    transaction_type = models.CharField(max_length=2, choices=TYPE_CHOICES, default=Debit)
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
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))],
    )

    admin_search_fields = (
        'sr_number__license__license_number',
        'bill_of_entry__bill_of_entry_number',
    )

    class Meta:
        ordering = ['transaction_type', 'bill_of_entry__bill_of_entry_date']
        unique_together = ('bill_of_entry', 'sr_number', 'transaction_type')
        verbose_name = "Item Detail"
        verbose_name_plural = "Item Details"

    def __str__(self):
        return str(self.sr_number)


# -----------------------------
# Signals for stock updates
# -----------------------------
@receiver(post_save, sender=RowDetails, dispatch_uid="update_stock_on_save")
def update_stock(sender, instance, **kwargs):
    """Trigger stock update task after save."""
    item = instance.sr_number
    from bill_of_entry.tasks import update_balance_values_task
    try:
        update_balance_values_task.delay(item.id)
    except Exception:
        update_balance_values_task(item.id)


@receiver(post_delete, sender=RowDetails)
def delete_stock(sender, instance, **kwargs):
    """Trigger stock update task after delete."""
    item = instance.sr_number
    from bill_of_entry.tasks import update_balance_values_task
    try:
        update_balance_values_task.delay(item.id)
    except Exception:
        update_balance_values_task(item.id)
