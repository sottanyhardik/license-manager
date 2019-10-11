from django.db import models

# Create your models here.
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from allotment.models import AllotmentItems, Debit
from bill_of_entry.models import RowDetails

DFIA = "26"

SCHEME_CODE_CHOICES = (
    (DFIA, '26 - Duty Free Import Authorization'),
)

N2009 = '098/2009'
N2015 = '019/2015'

NOTIFICATION_NORM_CHOICES = (
    (N2015, '019/2015'),
    (N2009, '098/2009')
)


def license_path(instance, filename):
    return '{0}/{1}'.format(instance.license.license_number, "{0}.pdf".format(instance.type))


class LicenseDetailsModel(models.Model):
    scheme_code = models.CharField(choices=SCHEME_CODE_CHOICES, max_length=10, default=DFIA)
    notification_number = models.CharField(choices=NOTIFICATION_NORM_CHOICES, max_length=10, default=N2015)
    license_number = models.CharField(max_length=50, unique=True)
    license_date = models.DateField(null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    file_number = models.CharField(max_length=30, null=True, blank=True)
    exporter = models.ForeignKey('core.CompanyModel', on_delete=models.CASCADE, null=True, blank=True)
    port = models.ForeignKey('core.PortModel', on_delete=models.CASCADE, null=True, blank=True)
    registration_number = models.CharField(max_length=10, null=True, blank=True)
    registration_date = models.DateField(null=True, blank=True)
    user_comment = models.TextField(null=True, blank=True)
    user_restrictions = models.TextField(null=True, blank=True)
    ledger_date = models.DateField(null=True, blank=True)
    is_audit = models.BooleanField(default=False)
    is_null = models.BooleanField(default=False)
    is_self = models.BooleanField(default=True)

    def __str__(self):
        return self.license_number

    @property
    def is_expired(self):
        return self.license_expiry_date < timezone.now()

    @property
    def get_norm_class(self):
        return ','.join([export.norm_class.norm_class for export in self.export_license.all()])

    def get_absolute_url(self):
        return reverse('license-detail', kwargs={'pk': self.pk})

    @property
    def get_total_debit(self):
        return RowDetails.objects.filter(sr_number__license=self).filter(transaction_type=Debit).aggregate(Sum('cif_fc'))['cif_fc__sum']

    @property
    def get_total_allotment(self):
        return AllotmentItems.objects.filter(item__license=self,
                                                  allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum']

    def get_balance_cif(self):
        credit = LicenseExportItemModel.objects.filter(license=self).aggregate(Sum('cif_fc'))['cif_fc__sum']
        debit = \
            RowDetails.objects.filter(sr_number__license=self).filter(transaction_type=Debit).aggregate(Sum('cif_fc'))[
                'cif_fc__sum']
        allotment = AllotmentItems.objects.filter(item__license=self,
                                                  allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum']
        t_debit = 0
        if debit:
            t_debit = t_debit + debit
        if allotment:
            t_debit = t_debit + allotment
        return round(credit - t_debit, 2)


KG = 'kg'

UNIT_CHOICES = (
    (KG, 'kg'),
)

USD = 'usd'
EURO = 'euro'

CURRENCY_CHOICES = (
    (USD, 'usd'),
    (EURO, 'euro'),
)


class LicenseExportItemModel(models.Model):
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE,
                                related_name='export_license')
    item = models.ForeignKey('core.ItemNameModel', related_name='export_licenses', on_delete=models.CASCADE, null=True,
                             blank=True)
    norm_class = models.ForeignKey('core.SionNormClassModel', null=True, blank=True, on_delete=models.CASCADE,
                                   related_name='export_item')
    duty_type = models.CharField(max_length=255, default='Basic')
    net_quantity = models.FloatField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=KG)
    fob_fc = models.FloatField(default=0)
    fob_inr = models.FloatField(default=0)
    fob_exchange_rate = models.FloatField(default=0)
    currency = models.CharField(choices=CURRENCY_CHOICES, default=USD, max_length=5)
    value_addition = models.FloatField(default=15)
    cif_fc = models.FloatField(default=0)
    cif_inr = models.FloatField(default=0)

    def __str__(self):
        try:
            return str(self.item.name)
        except:
            return ''

    def balance_cif_fc(self):
        if not self.cif_fc or self.cif_fc == 0:
            credit = LicenseExportItemModel.objects.filter(license=self.license).aggregate(Sum('cif_fc'))['cif_fc__sum']
        else:
            credit = self.cif_fc
        debit = RowDetails.objects.filter(sr_number__license=self.license).filter(transaction_type=Debit).aggregate(
            Sum('cif_fc'))[
            'cif_fc__sum']
        allotment = AllotmentItems.objects.filter(item__license=self.license,
                                                  allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum']
        t_debit = 0
        if debit:
            t_debit = t_debit + debit
        if allotment:
            t_debit = t_debit + allotment
        if self.cif_fc:
            return int(credit - t_debit)
        else:
            "Error"


class LicenseImportItemsModel(models.Model):
    serial_number = models.IntegerField(default=0)
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE, related_name='import_license')
    hs_code = models.ForeignKey('core.HSCodeModel', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='import_item')
    item = models.ForeignKey('core.ItemNameModel', related_name='license_items', on_delete=models.CASCADE, null=True,
                             blank=True)
    duty_type = models.CharField(max_length=255, default='Basic')
    quantity = models.FloatField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=KG)
    cif_fc = models.FloatField(null=True, blank=True)
    cif_inr = models.FloatField(default=0)
    restricted_value_in_percentage = models.FloatField(default=0)
    restricted_value_per_unit = models.FloatField(default=0)
    blocked_value = models.FloatField(default=0.00)
    blocked_quantity = models.FloatField(default=0.00)
    available_quantity = models.FloatField(default=0.00)
    available_value = models.FloatField(default=0.00)
    admin_search_fields = ('license__license_number',)

    class Meta:
        ordering = ['serial_number']

    def __str__(self):
        return "{0}-{1}".format(str(self.license), str(self.serial_number))


    @property
    def debited_quantity(self):
        return self.item_details.filter(transaction_type='D').aggregate(Sum('qty'))['qty__sum']

    @property
    def alloted_quantity(self):
        return self.allotment_details.filter(allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(Sum('qty'))['qty__sum']


    @property
    def balance_quantity(self):
        credit = self.quantity
        debit = self.debited_quantity
        alloted = self.alloted_quantity
        if debit and alloted:
            return  round(credit - debit - alloted, 2)
        elif debit:
            return round(credit - debit,2)
        elif alloted:
            return round((credit - alloted),2)


    @property
    def debited_value(self):
        return self.item_details.filter(transaction_type='D').aggregate(Sum('cif_fc'))['cif_fc__sum']

    @property
    def alloted_value(self):
        return self.allotment_details.filter(allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(Sum('cif_fc'))['cif_fc__sum']


    @property
    def balance_cif_fc(self):
        if not self.cif_fc or self.cif_fc == 0:
            return None
        else:
            credit = self.cif_fc
            debit = RowDetails.objects.filter(sr_number=self).filter(transaction_type=Debit).aggregate(
                Sum('cif_fc'))['cif_fc__sum']
        alloted = AllotmentItems.objects.filter(item=self,
                                                allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(Sum('cif_fc'))['cif_fc__sum']
        if debit and alloted:
            return  round(credit - debit - alloted, 2)
        elif debit:
            return round(credit - debit,2)
        elif alloted:
            return round((credit - alloted),2)


    @property
    def license_expiry(self):
        return self.license.license_expiry_date

    @property
    def license_date(self):
        return self.license.license_date


class LicenseDocumentModel(models.Model):
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE,
                                related_name='license_documents')
    type = models.CharField(max_length=255)
    file = models.FileField(upload_to=license_path)
