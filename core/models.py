# Create your models here.

# Create your models here.
from django.urls import reverse

"""Declare models for YOUR_APP app."""

from django.contrib.auth.models import AbstractUser

from django.contrib.auth.models import AbstractUser  ## A new class is imported. ##
from django.core.validators import RegexValidator
from django.db import models

alpha = RegexValidator(r'^[a-zA-Z ]*$', 'Only alpha characters are allowed.')


class CompanyModel(models.Model):
    iec = models.CharField(max_length=10, unique=True)
    pan = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    address_line_1 = models.TextField(null=True, blank=True)
    address_line_2 = models.TextField(null=True, blank=True)
    director_1 = models.TextField(null=True, blank=True)
    director_2 = models.TextField(null=True, blank=True)
    is_fetch = models.BooleanField(default=False)
    failed = models.IntegerField(default=0)
    is_self = models.BooleanField(default=True)

    def __str__(self):
        if self.name:
            return self.name
        else:
            return self.iec

    def get_absolute_url(self):
        return reverse('company-list')

    class Meta:
        ordering = ['name']


class PortModel(models.Model):
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ('code', 'name')
        unique_together = ('name', 'code')

    def __str__(self):
        return "{0}".format(self.code)


class ItemHeadModel(models.Model):
    name = models.CharField(max_length=255, unique=True)
    hs_code = models.CharField(max_length=255)
    unit_rate = models.FloatField(default=0)
    biscuit_priority = models.FloatField(default=0)
    confectionery_priority = models.FloatField(default=0)
    is_restricted = models.BooleanField(default=True)
    is_amend = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class ItemNameModel(models.Model):
    head = models.ForeignKey('core.ItemHeadModel', on_delete=models.CASCADE, related_name='items', null=True,
                             blank=True)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('item-list')


class HSCodeModel(models.Model):
    hs_code = models.CharField(max_length=8, unique=True)
    product_description = models.TextField(null=True, blank=True)
    unit_price = models.FloatField(default=0)
    basic_duty = models.CharField(max_length=225, null=True, blank=True)
    unit = models.CharField(max_length=255, null=True, blank=True)
    policy = models.CharField(max_length=255, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    search_fields = ('hs_code', 'product_description')

    def __str__(self):
        return "{}".format(self.hs_code, self.product_description)

    class Meta:
        ordering = ('hs_code',)


class HeadSIONNormsModel(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField(null=True, blank=True)
    is_fetch = models.BooleanField(default=False)
    tpages = models.IntegerField(default=1)
    tcurrent = models.IntegerField(default=1)

    def __str__(self):
        return self.name


class SionNormClassModel(models.Model):
    head_norm = models.ForeignKey('core.HeadSIONNormsModel', on_delete=models.CASCADE, related_name='sion_head')
    item = models.ForeignKey('core.ItemNameModel', related_name='norm_class', on_delete=models.CASCADE, null=True,
                             blank=True)
    norm_class = models.CharField(max_length=10)
    url = models.URLField(null=True, blank=True, help_text="Please Enter Exim Guru URL")
    is_fetch = models.BooleanField(default=False)
    created_on = models.DateField(auto_created=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='sion_created')
    modified_on = models.DateField(auto_now=True)
    modified_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='sion_updated')

    def __str__(self):
        if self.item:
            return "{0} | {1}".format(self.norm_class, self.item.name)
        else:
            return "{0}".format(self.norm_class)

    def get_absolute_url(self):
        return reverse('sion-detail', kwargs={'pk': self.pk})


class SIONExportModel(models.Model):
    norm_class = models.OneToOneField('core.SionNormClassModel', on_delete=models.CASCADE, related_name='export_norm')
    item = models.ForeignKey('core.ItemNameModel', related_name='sion_export', on_delete=models.CASCADE, null=True,
                             blank=True)
    quantity = models.FloatField(default=0.0)
    unit = models.CharField(max_length=255, null=True, blank=True)
    hs_code = models.ManyToManyField('core.HSCodeModel', blank=True, related_name='export_norms')

    def __str__(self):
        if self.item:
            return "{0} | {1}".format(self.norm_class, self.item.name)
        else:
            return "{0}".format(self.norm_class)


class SIONImportModel(models.Model):
    sr_no = models.IntegerField(default=0)
    norm_class = models.ForeignKey('core.SionNormClassModel', on_delete=models.CASCADE, related_name='import_norm')
    item = models.ForeignKey('core.ItemNameModel', related_name='sion_import', on_delete=models.CASCADE, null=True,
                             blank=True)
    quantity = models.FloatField(default=0.0)
    unit = models.CharField(max_length=255, null=True, blank=True)
    condition = models.CharField(max_length=255, null=True, blank=True)
    hs_code = models.ManyToManyField('core.HSCodeModel', blank=True, related_name='import_norms')

    class Meta:
        ordering = ['sr_no']

    def __str__(self):
        if self.item:
            return "{0} | {1}".format(self.norm_class, self.item.name)
        else:
            return "{0}".format(self.norm_class)


class HSCodeDutyModel(models.Model):
    hs_code = models.CharField(max_length=8, unique=True)
    basic_custom_duty = models.FloatField(default=0)
    additional_duty_of_customs = models.FloatField(default=0)
    custom_health_CESS = models.FloatField(default=0)
    social_welfare_surcharge = models.FloatField(default=0)
    additional_CVD = models.FloatField(default=0)
    IGST_levy = models.FloatField(default=0)
    compensation_cess = models.FloatField(default=0)
    total_duty = models.FloatField(default=0)
    sample_on_lakh = models.FloatField(default=0)
    is_fetch = models.BooleanField(default=False)
    is_fetch_xls = models.BooleanField(default=False)
    list_filter = ('is_fetch', 'is_fetch_xls')
    admin_search_fields = ('hs_code',)

    def __str__(self):
        return self.hs_code

    @property
    def product_description(self):
        return '\n'.join([product_description['product_description'] for product_description in
                          self.product_descriptions.all().values('product_description')])


class ProductDescriptionModel(models.Model):
    hs_code = models.ForeignKey('core.HSCodeDutyModel', on_delete=models.PROTECT, related_name='product_descriptions')
    product_description = models.TextField()

    def __str__(self):
        return self.product_description


class TransferLetterModel(models.Model):
    name = models.CharField(max_length=255)
    tl = models.FileField(upload_to='tl')

    def __str__(self):
        return self.name


class MEISMODEL(models.Model):
    exporter = models.CharField(max_length=255)
    importer = models.CharField(max_length=255)
    cif_inr = models.CharField(max_length=255)
    dfia_date = models.CharField(max_length=255)
    dfia_no = models.CharField(max_length=255)
    file_no = models.CharField(null=True, blank=True, max_length=255)

    def __str__(self):
        return self.dfia_no


class UnitPriceModel(models.Model):
    name = models.CharField(max_length=255)
    unit_price = models.FloatField(default=0)
    label = models.CharField(max_length=255, default='')

    def __str__(self):
        return self.name
