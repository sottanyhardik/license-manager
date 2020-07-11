from django.db import models

# Create your models here.
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from allotment.models import AllotmentItems, Debit, ALLOTMENT
from bill_of_entry.models import RowDetails, ARO

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
    is_au = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    balance_cif = models.FloatField(default=0.0)
    is_incomplete = models.BooleanField(default=False)
    is_expired = models.BooleanField(default=False)
    is_individual = models.BooleanField(default=False)
    admin_search_fields = ('license_number',)

    def __str__(self):
        return self.license_number

    @property
    def get_norm_class(self):
        return ','.join([export.norm_class.norm_class for export in self.export_license.all() if export.norm_class])

    def get_absolute_url(self):
        return reverse('license-detail', kwargs={'license': self.license_number})

    @property
    def get_total_debit(self):
        alloted = AllotmentItems.objects.filter(item__license=self, allotment__type=ARO,
                                                allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum']
        debited = \
            RowDetails.objects.filter(sr_number__license=self).filter(transaction_type=Debit).aggregate(Sum('cif_fc'))[
                'cif_fc__sum']
        if debited and alloted:
            total = debited + alloted
        elif alloted:
            total = alloted
        elif debited:
            total = debited
        else:
            total = 0
        return round(total, 0)

    @property
    def get_total_allotment(self):
        return AllotmentItems.objects.filter(item__license=self, allotment__type=ALLOTMENT,
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
        if credit and t_debit:
            return round(credit - t_debit, 0)
        elif credit:
            return round(credit, 0)
        else:
            return 0

    @property
    def opening_balance(self):
        return self.export_license.all().aggregate(sum=Sum('cif_fc'))['sum']

    def get_wheat(self):
        return self.import_license.filter(item__head__name__icontains='wheat').first().balance_quantity

    def wheat(self):
        return self.import_license.filter(item__head__name__icontains='wheat').first()

    def get_sugar(self):
        return self.import_license.filter(item__head__name__icontains='sugar').first().balance_quantity

    def sugar(self):
        return self.import_license.filter(item__head__name__icontains='sugar').first()

    def get_rbd(self):
        return self.import_license.filter(item__head__name__icontains='rbd').first().balance_quantity

    def rbd(self):
        return self.import_license.filter(item__head__name__icontains='rbd').first()

    def food_flavour(self):
        return self.import_license.filter(item__head__name__icontains='food flavour').first()

    def dietary_fibre(self):
        return self.import_license.filter(item__head__name__icontains='dietary fibre').first()

    def get_leavening_agent(self):
        return self.import_license.filter(item__head__name__icontains='Leavening Agent').first().balance_quantity

    def leavening_agent(self):
        return self.import_license.filter(item__head__name__icontains='Leavening Agent').first()

    def get_emulsifier(self):
        return self.import_license.filter(item__head__name__icontains='emulsifier').first().balance_quantity

    def get_food_flavour(self):
        return self.import_license.filter(item__head__name__icontains='food flavour').first().balance_quantity

    def get_starch(self):
        return self.import_license.filter(item__head__name__icontains='starch').first().balance_quantity

    def get_food_colour(self):
        return self.import_license.filter(item__head__name__icontains='food colour').first().balance_quantity

    def get_anti_oxidant(self):
        return self.import_license.filter(item__head__name__icontains='anti oxidant').first().balance_quantity

    def get_fruit(self):
        return self.import_license.filter(item__head__name__icontains='fruit').first().balance_quantity

    def fruit(self):
        return self.import_license.filter(item__head__name__icontains='fruit').first()

    def get_dietary_fibre(self):
        return self.import_license.filter(item__head__name__icontains='dietary fibre').first().balance_quantity

    def get_m_n_m(self):
        return self.import_license.filter(item__head__name__icontains='milk').first().balance_quantity

    def m_n_m(self):
        return self.import_license.filter(item__head__name__icontains='milk').first()

    def get_pp(self):
        return self.import_license.filter(item__head__name__icontains='pp').first().balance_quantity

    def pp(self):
        return self.import_license.filter(item__head__name__icontains='pp').first()

    def get_bopp(self):
        return self.import_license.filter(item__head__name__icontains='bopp').first().balance_quantity

    def get_paper(self):
        return self.import_license.filter(item__head__name__icontains='paper').first().balance_quantity

    def get_liquid_glucose(self):
        return self.import_license.filter(item__head__name__icontains='liquid glucose').first().balance_quantity

    def get_tartaric_acid(self):
        return self.import_license.filter(item__head__name__icontains='acid').first().balance_quantity

    def get_essential_oil(self):
        return self.import_license.filter(item__head__name__icontains='essential oil').first().balance_quantity

    def get_other_confectionery(self):
        return self.import_license.filter(item__head__name__icontains='other confectionery').first().balance_quantity

    def get_starch_confectionery(self):
        from django.db.models import Q
        return self.import_license.filter(Q(item__head__name__icontains='starch') | Q(
            item__head__name__icontains='emulsifier')).first().balance_quantity

    def get_party_name(self):
        return str(self.exporter)[:8]

    def get_required_sugar_value(self):
        return round(self.get_sugar() * 0.330, 0)

    def get_required_rbd_value(self):
        return round(self.get_rbd() * 0.800, 0)

    def get_required_mnm_value(self):
        return round(self.get_m_n_m() * 5, 0)

    def get_balance_value(self):
        if self.get_norm_class == 'E5':
            return round(
                self.get_balance_cif() - self.get_required_sugar_value() - self.get_required_rbd_value() - self.get_required_mnm_value(),
                0)
        else:
            return round(self.get_balance_cif() - self.get_required_sugar_value(), 0)


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
    old_quantity = models.FloatField(default=0)
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
    old_quantity = models.FloatField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=KG)
    cif_fc = models.FloatField(null=True, blank=True)
    cif_inr = models.FloatField(default=0)
    restricted_value_in_percentage = models.FloatField(default=0)
    restricted_value_per_unit = models.FloatField(default=0)
    blocked_value = models.FloatField(default=0.00)
    blocked_quantity = models.FloatField(default=0.00)
    available_quantity = models.FloatField(default=0.00)
    available_value = models.FloatField(default=0.00)
    is_restrict = models.BooleanField(default=False)
    comment = models.TextField(null=True, blank=True)
    admin_search_fields = ('license__license_number',)

    class Meta:
        ordering = ['serial_number']

    def __str__(self):
        return "{0}-{1}".format(str(self.license), str(self.serial_number))

    @property
    def debited_quantity(self):
        debited = self.item_details.filter(transaction_type='D').aggregate(Sum('qty'))['qty__sum']
        alloted = self.allotment_details.filter(allotment__type=ARO).aggregate(Sum('qty'))['qty__sum']
        if debited and alloted:
            total = debited + alloted
        elif alloted:
            total = alloted
        elif debited:
            total = debited
        else:
            total = 0
        return round(total, 0)

    @property
    def alloted_quantity(self):
        alloted = self.allotment_details.filter(allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                                                allotment__type=ALLOTMENT).aggregate(
            Sum('qty'))['qty__sum']
        if alloted:
            return alloted
        else:
            return 0

    @property
    def required_cif(self):
        if self.balance_quantity > 100:
            required = round(self.balance_quantity * self.item.head.unit_rate, 0) + 10
            return required
        else:
            return 0

    @property
    def balance_quantity(self):
        if self.item and self.item.head and self.item.head.is_restricted and self.old_quantity:
            credit = self.old_quantity
        elif self.item and self.item.head and self.item.head.is_restricted and self.license.notification_number == N2015:
            credit = self.quantity
        else:
            credit = self.quantity
        debit = self.debited_quantity
        alloted = self.alloted_quantity
        if debit and alloted:
            return round(credit - debit - alloted, 0)
        elif debit:
            return round(credit - debit, 0)
        elif alloted:
            return round((credit - alloted), 0)
        else:
            return round(credit, 0)

    @property
    def debited_value(self):
        debited = self.item_details.filter(transaction_type='D').aggregate(Sum('cif_fc'))['cif_fc__sum']
        alloted = self.allotment_details.filter(allotment__type=ARO).aggregate(Sum('cif_fc'))['cif_fc__sum']
        if debited and alloted:
            total = debited + alloted
        elif alloted:
            total = alloted
        elif debited:
            total = debited
        else:
            total = 0
        return round(total, 0)

    @property
    def alloted_value(self):
        return self.allotment_details.filter(allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                                             allotment__type=ALLOTMENT).aggregate(
            Sum('cif_fc'))['cif_fc__sum']

    @property
    def balance_cif_fc(self):
        if not self.cif_fc or int(self.cif_fc) == 0 or self.cif_fc == 0.1:
            credit = LicenseExportItemModel.objects.filter(license=self.license).aggregate(Sum('cif_fc'))['cif_fc__sum']
        else:
            credit = self.cif_fc
        if not self.cif_fc or self.cif_fc == 0.01:
            debit = RowDetails.objects.filter(sr_number__license=self.license).filter(transaction_type=Debit).aggregate(
                Sum('cif_fc'))[
                'cif_fc__sum']
            allotment = AllotmentItems.objects.filter(item__license=self.license,
                                                      allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
                Sum('cif_fc'))['cif_fc__sum']
        else:
            debit = RowDetails.objects.filter(sr_number=self).filter(transaction_type=Debit).aggregate(
                Sum('cif_fc'))[
                'cif_fc__sum']
            allotment = AllotmentItems.objects.filter(item=self,
                                                      allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
                Sum('cif_fc'))['cif_fc__sum']
        t_debit = 0
        if debit:
            t_debit = t_debit + debit
        if allotment:
            t_debit = t_debit + allotment
        return int(credit - t_debit)

    @property
    def license_expiry(self):
        return self.license.license_expiry_date

    @property
    def license_date(self):
        return self.license.license_date

    @property
    def sorted_item_list(self):
        dict_list = []
        dict_return = {}
        data = self.item_details.order_by('transaction_type', 'bill_of_entry__company',
                                          'bill_of_entry__bill_of_entry_date')
        company_data = list(set([c['bill_of_entry__company__name'] for c in
                                 self.item_details.order_by('transaction_type', 'bill_of_entry__company',
                                                            'bill_of_entry__bill_of_entry_date').values(
                                     'bill_of_entry__company__name')]))
        for company in company_data:
            if company:
                if not company in list(dict_return.keys()):
                    dict_return[company] = {}
                dict_return[company]['company'] = company
                dict_return[company]['data_list'] = data.filter(bill_of_entry__company__name=company)
                dict_return[company]['sum_total_qty'] = data.filter(bill_of_entry__company__name=company).aggregate(
                    Sum('qty')).get('qty__sum', 0.00)
                dict_return[company]['sum_total_cif_fc'] = data.filter(bill_of_entry__company__name=company).aggregate(
                    Sum('cif_fc')).get('cif_fc__sum', 0.00)
                dict_return[company]['sum_total_cif_inr'] = data.filter(bill_of_entry__company__name=company).aggregate(
                    Sum('cif_inr')).get('cif_inr__sum', 0.00)
        for company in company_data:
            if company:
                dict_list.append(dict_return[company])
        dict_return['item_details'] = dict_list
        return dict_return

    @property
    def total_debited_qty(self):
        return self.item_details.filter(transaction_type='D').aggregate(Sum('qty')).get('qty__sum', 0.00)

    @property
    def total_debited_cif_fc(self):
        debited = self.item_details.filter(transaction_type='D').aggregate(Sum('cif_fc')).get('cif_fc__sum', 0.00)
        alloted = self.allotment_details.filter(allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                                                allotment__type=ARO).aggregate(Sum('cif_fc'))['cif_fc__sum']
        if debited and alloted:
            total = debited + alloted
        elif alloted:
            total = alloted
        elif debited:
            total = debited
        else:
            total = 0
        return round(total, 0)

    @property
    def total_debited_cif_inr(self):
        return self.item_details.filter(transaction_type='D').aggregate(Sum('cif_inr')).get('cif_inr__sum', 0.00)

    @property
    def opening_balance(self):
        return self.item_details.filter(transaction_type='C').aggregate(Sum('qty')).get('qty__sum', 0.00)

    @property
    def usable(self):
        if self.license.notification_number == N2015 and self.item.head.is_restricted:
            return self.old_quantity
        value = self.item_details.filter(transaction_type='C').aggregate(Sum('qty')).get('qty__sum', 0.00)
        if value:
            return round(value, 0)
        else:
            return 0


class LicenseDocumentModel(models.Model):
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE,
                                related_name='license_documents')
    type = models.CharField(max_length=255)
    file = models.FileField(upload_to=license_path)


class StatusModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class OfficeModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class AlongWithModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class DateModel(models.Model):
    date = models.DateField()

    def __str__(self):
        return str(self.date)


class LicenseInwardOutwardModel(models.Model):
    date = models.ForeignKey('license.DateModel', on_delete=models.CASCADE,
                             related_name='license_status')
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE,
                                related_name='license_status', null=True, blank=True)
    status = models.ForeignKey('license.StatusModel', on_delete=models.CASCADE,
                               related_name='license_status')
    office = models.ForeignKey('license.OfficeModel', on_delete=models.CASCADE,
                               related_name='license_status')
    description = models.TextField(null=True, blank=True)
    amd_sheets_number = models.CharField(max_length=100, null=True, blank=True)
    copy = models.BooleanField(default=False)
    annexure = models.BooleanField(default=False)
    along_with = models.ForeignKey('license.AlongWithModel', on_delete=models.CASCADE,
                                   related_name='license_status', null=True, blank=True)

    def __str__(self):
        text = ''
        if self.license:
            text = text + str(self.license) + ' '
        if self.copy:
            text = text + 'copy '
        if self.amd_sheets_number:
            text = text + 'amendment sheet:- ' + str(self.amd_sheets_number) + ' '
        if self.annexure:
            text = text + '& annexure '
        if self.status:
            text = text + 'has been {0} '.format(self.status.name)
        if self.office:
            text = text + 'send to '.format(self.office.name)
        if self.description:
            text = text + 'for ' + str(self.description) + ' '
        if self.along_with:
            text = text + 'along with ' + str(self.along_with.name)
        return text
