from django.db import models


# Create your models here.


class FileUploadDetails(models.Model):
    iec = models.CharField(max_length=255, null=True, blank=True)
    ifsc = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, db_index=True, related_name='uploaded_files')
    file_name = models.CharField(max_length=255, null=True, blank=True)
    upload_time = models.CharField(max_length=255, null=True, blank=True)


class ShippingDetails(models.Model):
    shipping_port = models.CharField(max_length=255, null=True, blank=True)
    shipping_bill = models.CharField(max_length=255)
    shipping_date = models.DateField(null=True, blank=True)
    cha_number = models.CharField(max_length=255, null=True, blank=True)
    job_no = models.CharField(max_length=255, null=True, blank=True)
    job_date = models.CharField(max_length=255, null=True, blank=True)
    total_package = models.CharField(max_length=255, null=True, blank=True)
    port_of_discharge = models.CharField(max_length=255, null=True, blank=True)
    gross_weight = models.CharField(max_length=255, null=True, blank=True)
    fob = models.CharField(max_length=255, null=True, blank=True)
    total_cess = models.CharField(max_length=255, null=True, blank=True)
    drawback = models.CharField(max_length=255, null=True, blank=True)
    str = models.CharField(max_length=255, null=True, blank=True)
    total = models.CharField(max_length=255, null=True, blank=True)
    leo_date = models.CharField(max_length=255, null=True, blank=True)
    scroll_date = models.CharField(max_length=255, null=True, blank=True)
    dbk_scroll_no = models.CharField(max_length=255, null=True, blank=True)
    file_number = models.CharField(max_length=255, null=True, blank=True)
    custom_file_number = models.CharField(max_length=255, null=True, blank=True)
    time_of_upload = models.CharField(max_length=255, null=True, blank=True)
    file = models.ForeignKey('ebrc.FileUploadDetails', db_index=True, related_name='shipping_bills', blank=True, null=True, on_delete=models.CASCADE)
    failed = models.IntegerField(default=0)
    ebrc = models.BooleanField(default=False)
    scroll_details = models.BooleanField(default=False)

    def __str__(self):
        return self.shipping_bill

    @property
    def brc_date(self):
        return self.ebrc_list.first().brc_date

    @property
    def brc_status(self):
        return self.ebrc_list.first().brc_status

    @property
    def brc_amount(self):
        from django.db.models import Sum
        return self.ebrc_list.all().aggregate(Sum('realised_value'))['realised_value__sum']

    @property
    def currency(self):
        return self.ebrc_list.first().currency

    @property
    def date_of_realisation(self):
        return self.ebrc_list.first().date_of_realisation

    @property
    def brc_utilisation_status(self):
        return self.ebrc_list.first().brc_utilisation_status

    @property
    def brc_no(self):
        return ", ".join([ebrc.ebrcNumb for ebrc in self.ebrc_list.all()])


class EbrcDetails(models.Model):
    shipping_bill = models.ForeignKey('ebrc.ShippingDetails', on_delete=models.CASCADE, db_index=True, related_name='ebrc_list')
    brc_date = models.CharField(max_length=255, null=True, blank=True)
    brc_status = models.CharField(max_length=255, null=True, blank=True)
    realised_value = models.FloatField(default=0)
    currency = models.CharField(max_length=255, null=True, blank=True)
    date_of_realisation = models.CharField(max_length=255, null=True, blank=True)
    brc_utilisation_status = models.CharField(max_length=255, null=True, blank=True)
    ebrcNumb = models.CharField(max_length=255, null=True, blank=True)
    recid = models.CharField(max_length=255, null=True, blank=True)
    iec = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.shipping_bill.shipping_bill


class ExchangeRateModel(models.Model):
    date = models.DateField()
    usd_import = models.FloatField(default=0)
    gbp_import = models.FloatField(default=0)
    euro_import = models.FloatField(default=0)
    usd_export = models.FloatField(default=0)
    gbp_export = models.FloatField(default=0)
    euro_export = models.FloatField(default=0)
    notification_no = models.CharField(max_length=255)

    def __str__(self):
        return str(self.date)
