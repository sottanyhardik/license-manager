from django.db import models
from django.db.models import Sum
from django.urls import reverse


class BillOfEntryModel(models.Model):
    company = models.ForeignKey('core.CompanyModel', db_index=True, related_name="bill_of_entry", on_delete=models.CASCADE, null=True,
                                blank=True)
    bill_of_entry_number = models.CharField(max_length=25)
    bill_of_entry_date = models.DateField(null=True, blank=True)
    port = models.ForeignKey('core.PortModel', on_delete=models.CASCADE, db_index=True, related_name='boe_port', null=True, blank=True)
    exchange_rate = models.FloatField(default=0)
    product_name = models.CharField(max_length=255, default='')
    allotment = models.ManyToManyField('allotment.AllotmentModel', db_index=True, related_name="bill_of_entry", blank=True)
    invoice_no = models.CharField(max_length=255, null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    is_fetch = models.BooleanField(default=False)
    failed = models.IntegerField(default=0)
    appraisement = models.CharField(max_length=255, null=True, blank=True)
    ooc_date = models.CharField(max_length=255, null=True, blank=True)
    cha = models.CharField(max_length=255, null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    admin_search_fields = ['bill_of_entry_number', ]

    class Meta:
        unique_together = ('company','bill_of_entry_number', 'bill_of_entry_date',)
        ordering = ('-bill_of_entry_date',)

    def __str__(self):
        return self.bill_of_entry_number

    @property
    def get_absolute_url(self):
        return reverse('bill-of-entry-detail', kwargs={'boe': self.bill_of_entry_number})

    @property
    def get_total_inr(self):
        total = self.item_details.all().aggregate(Sum('cif_inr'))['cif_inr__sum']
        if total:
            return round(total, 2)
        else:
            return 0

    @property
    def get_total_fc(self):
        total = self.item_details.all().aggregate(Sum('cif_fc'))['cif_fc__sum']
        if total:
            return round(total, 2)
        else:
            return 0

    @property
    def get_total_quantity(self):
        total = self.item_details.all().aggregate(Sum('qty'))['qty__sum']
        if total:
            return round(total, 2)
        else:
            return 0

    @property
    def get_licenses(self):
        return ", ".join([item.sr_number.license.license_number for item in self.item_details.all()])

    @property
    def get_unit_price(self):
        if self.get_total_quantity and self.get_total_quantity != 0:
            return round(self.get_total_fc / self.get_total_quantity, 3)
        return 0

    @property
    def get_exchange_rate(self):
        if self.get_total_quantity and self.get_total_quantity != 0:
            return round(self.get_total_inr / self.get_total_fc, 3)
        return 0


Credit = 'C'
Debit = 'D'

TYPE_CHOICES = (
    (Credit, 'Credit'),
    (Debit, 'Debit')
)

ARO = 'AR'
ALLOTMENT = 'AT'

ROW_TYPE = (
    (ARO, 'ARO'),
    (ALLOTMENT, 'Allotment')
)


class RowDetails(models.Model):
    bill_of_entry = models.ForeignKey('bill_of_entry.BillOfEntryModel', on_delete=models.CASCADE,
                                      related_name='item_details', null=True, blank=True)
    row_type = models.CharField(max_length=2, choices=ROW_TYPE, default=ALLOTMENT)
    sr_number = models.ForeignKey('license.LicenseImportItemsModel', on_delete=models.CASCADE,
                                  related_name='item_details')
    transaction_type = models.CharField(max_length=2, choices=TYPE_CHOICES, default='D')
    cif_inr = models.FloatField(default=0.0)
    cif_fc = models.FloatField(default=0.0)
    qty = models.FloatField(default=0.0)
    admin_search_fields = ('sr_number__license__license_number', 'bill_of_entry__bill_of_entry_number')

    class Meta:
        ordering = ['transaction_type', 'bill_of_entry__bill_of_entry_date']
