from django.db import models

# Create your models here.
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse

from core.scripts.calculate_balance import calculate_available_quantity

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


class AllotmentModel(models.Model):
    company = models.ForeignKey('core.CompanyModel', related_name='company_allotments', on_delete=models.CASCADE)
    type = models.CharField(max_length=2, choices=ROW_TYPE, default=ALLOTMENT)
    required_quantity = models.FloatField(default=0)
    unit_value_per_unit = models.FloatField(default=0)
    item_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    contact_number = models.CharField(max_length=255, null=True, blank=True)
    invoice = models.CharField(max_length=255, null=True, blank=True)
    estimated_arrival_date = models.DateField(null=True, blank=True)
    bl_detail = models.CharField(max_length=255, null=True, blank=True)
    port = models.ForeignKey('core.PortModel', on_delete=models.CASCADE, null=True, blank=True,
                             related_name="allotments")
    related_company = models.ForeignKey('core.CompanyModel', related_name='related_company', on_delete=models.CASCADE,
                                        null=True, blank=True)
    created_on = models.DateField(auto_created=True, null=True, blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='allotment_created')
    modified_on = models.DateField(auto_now=True)
    modified_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='allotment_updated')

    class Meta:
        ordering = ['estimated_arrival_date', ]

    def __str__(self):
        if self.invoice:
            return "{0} {1} {2} {3} {4}".format(self.item_name, self.company.name, str(self.invoice),
                                                str(self.required_quantity), self.estimated_arrival_date)
        else:
            return "{0} {1} {2}".format(self.item_name, self.company.name,
                                        str(self.required_quantity))

    @property
    def required_value(self):
        return round(self.required_quantity * self.unit_value_per_unit, 0)

    @property
    def dfia_list(self):
        dfia = [i.item.license.license_number for i in self.allotment_details.all()]
        return ', '.join(dfia)

    @property
    def balanced_quantity(self):
        qty = self.allotment_details.aggregate(Sum('qty'))['qty__sum']
        if qty:
            return int(self.required_quantity - qty)
        else:
            return int(self.required_quantity)

    @property
    def alloted_quantity(self):
        qty = self.allotment_details.aggregate(Sum('qty'))['qty__sum']
        if qty:
            return int(qty)
        else:
            return 0

    @property
    def alloted_value(self):
        value = self.allotment_details.aggregate(Sum('cif_fc'))['cif_fc__sum']
        if value:
            return int(value)
        else:
            return 0


class AllotmentItems(models.Model):
    item = models.ForeignKey('license.LicenseImportItemsModel', on_delete=models.CASCADE,
                             related_name='allotment_details', null=True, blank=True)
    allotment = models.ForeignKey('allotment.AllotmentModel', on_delete=models.CASCADE,
                                  related_name='allotment_details', null=True, blank=True)
    cif_inr = models.FloatField(default=0.0)
    cif_fc = models.FloatField(default=0.0)
    qty = models.FloatField(default=0.0)
    is_boe = models.BooleanField(default=False)
    admin_search_fields = ('item__license__license_number',)

    class Meta:
        ordering = ['qty', ]

    def __str__(self):
        return self.item.description

    @property
    def serial_number(self):
        return self.item.serial_number

    @property
    def product_description(self):
        return self.item.description

    @property
    def license_number(self):
        return self.item.license.license_number

    @property
    def license_date(self):
        return self.item.license.license_date

    @property
    def exporter(self):
        return self.item.license.exporter

    @property
    def license_expiry(self):
        return self.item.license.license_expiry_date

    @property
    def registration_number(self):
        return self.item.license.registration_number

    @property
    def registration_date(self):
        return self.item.license.registration_date

    @property
    def notification_number(self):
        return self.item.license.notification_number

    @property
    def file_number(self):
        return self.item.license.file_number

    @property
    def port_code(self):
        return self.item.license.port

    @property
    def get_delete_url(self):
        return reverse('allotment-item-delete', kwargs={'pk': self.pk}) + '?allotment_id=' + str(self.allotment_id)


@receiver(post_save, sender=AllotmentItems, dispatch_uid="update_stock")
def update_stock(sender, instance, **kwargs):
    instance.item.available_quantity = calculate_available_quantity(instance.item)
    instance.item.save()


@receiver(post_delete, sender=AllotmentItems)
def delete_stock(sender, instance, *args, **kwargs):
    instance.item.available_quantity = calculate_available_quantity(instance.item)
    instance.item.save()
