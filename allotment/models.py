from django.db import models

# Create your models here.
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property

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

    @cached_property
    def required_value(self):
        return round(self.required_quantity * self.unit_value_per_unit, 0)

    @cached_property
    def dfia_list(self):
        dfia = [i.item.license.license_number for i in self.allotment_details.all()]
        return ', '.join(dfia)

    @cached_property
    def balanced_quantity(self):
        qty = self.allotment_details.aggregate(Sum('qty'))['qty__sum']
        if qty:
            return int(self.required_quantity - qty)
        else:
            return int(self.required_quantity)

    @cached_property
    def alloted_quantity(self):
        qty = self.allotment_details.aggregate(Sum('qty'))['qty__sum']
        if qty:
            return int(qty)
        else:
            return 0

    @cached_property
    def allotted_value(self):
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
        unique_together = ('item', 'allotment')

    def __str__(self):
        return self.item.description

    @cached_property
    def serial_number(self):
        return self.item.serial_number

    @cached_property
    def ledger(self):
        return self.item.license.ledger_date


    @cached_property
    def product_description(self):
        return self.item.description

    @cached_property
    def license_number(self):
        return self.item.license.license_number

    @cached_property
    def license_date(self):
        return self.item.license.license_date

    @cached_property
    def exporter(self):
        return self.item.license.exporter

    @cached_property
    def license_expiry(self):
        return self.item.license.license_expiry_date

    @cached_property
    def registration_number(self):
        return self.item.license.registration_number

    @cached_property
    def registration_date(self):
        return self.item.license.registration_date

    @cached_property
    def notification_number(self):
        return self.item.license.notification_number

    @cached_property
    def file_number(self):
        return self.item.license.file_number

    @cached_property
    def port_code(self):
        return self.item.license.port

    @cached_property
    def get_delete_url(self):
        return reverse('allotment-item-delete', kwargs={'pk': self.pk}) + '?allotment_id=' + str(self.allotment_id)


@receiver(post_save, sender=AllotmentItems, dispatch_uid="update_stock")
def update_stock(sender, instance, **kwargs):
    item = instance.item
    from bill_of_entry.tasks import update_balance_values_task
    update_balance_values_task(item.id)


@receiver(post_delete, sender=AllotmentItems)
def delete_stock(sender, instance, *args, **kwargs):
    item = instance.item
    from bill_of_entry.tasks import update_balance_values_task
    update_balance_values_task.delay(item.id)
