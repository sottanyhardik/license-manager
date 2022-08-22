from django.db import models


# Create your models here.
class CompanyListModel(models.Model):
    company_name = models.CharField(max_length=255,null=True, blank=True)
    iec_number = models.CharField(max_length=10, unique=True)
    amount = models.FloatField(default=0)
    address = models.TextField(null=True, blank=True)
    phone_number = models.CharField(max_length=255, null=True, blank=True)
    is_fetch = models.BooleanField(default=False)
    port = models.ManyToManyField('core.PortModel', null=True, blank=True)

    def __str__(self):
        if self.company_name:
            return self.company_name
        else:
            return self.iec_number


class CompanyLicenseModel(models.Model):
    company = models.ForeignKey('eScrap.CompanyListModel', on_delete=models.CASCADE)
    status = models.CharField(max_length=255, null=True, blank=True)
    license_no = models.CharField(max_length=255, null=True, blank=True)
    scheme = models.CharField(max_length=255, null=True, blank=True)
    license_date = models.DateField(null=True, blank=True)
    port = models.CharField(max_length=10, null=True, blank=True)
    dgft_transmission_date = models.DateField(null=True, blank=True)
    date_of_integration = models.DateField(null=True, blank=True)
    error_code = models.CharField(max_length=255, null=True, blank=True)
    file_number = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.license_no