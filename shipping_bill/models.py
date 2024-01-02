from django.db import models


# Create your models here.
class FileUploadDetails(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, db_index=True, related_name='uploaded_files_shipping_bill')
    iec_code = models.CharField(max_length=255, null=True, blank=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)
    upload_time = models.CharField(max_length=255, null=True, blank=True)


class ShippingDetailsOther(models.Model):
    file_id = models.IntegerField(null=True, blank=True)
    sr_no = models.IntegerField(null=True, blank=True)
    shipping_port = models.CharField(max_length=255, null=True, blank=True)
    shipping_bill = models.CharField(max_length=255, null=True, blank=True)
    shipping_date = models.CharField(max_length=255, null=True, blank=True)
    iec = models.CharField(max_length=255, null=True, blank=True)
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
    failed = models.IntegerField(default=0)
    file_number = models.CharField(max_length=255, null=True, blank=True)
    custom_file_number = models.CharField(max_length=255, null=True, blank=True)
    time_of_upload = models.CharField(max_length=255, null=True, blank=True)
    fetch_status = models.BooleanField(default=False)

    def __str__(self):
        return "{0} {1}".format(self.shipping_bill, self.fetch_status)


class ShippingBillDetailsModels(models.Model):
    file_id = models.IntegerField(null=True, blank=True)
    sr_no = models.IntegerField(null=True, blank=True)
    shipping_port = models.CharField(max_length=255, null=True, blank=True)
    shipping_bill = models.CharField(max_length=255, null=True, blank=True)
    shipping_date = models.CharField(max_length=255, null=True, blank=True)
    cha_number = models.CharField(max_length=255, null=True, blank=True)
    gross_weight = models.CharField(max_length=255, null=True, blank=True)
    fob_inr = models.CharField(max_length=255, null=True, blank=True)
    drawback = models.CharField(max_length=255, null=True, blank=True)
    str = models.CharField(max_length=255, null=True, blank=True)
    total = models.CharField(max_length=255, null=True, blank=True)
    current_status = models.CharField(max_length=255, null=True, blank=True)
    DBK_scroll_no = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return "{0}".format(self.shipping_bill)