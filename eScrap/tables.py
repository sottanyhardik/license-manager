import django_tables2 as dt2
from . import models
import itertools


class CompanyClassTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    license_date = dt2.DateTimeColumn(format='d/M/Y')
    dgft_transmission_date = dt2.DateTimeColumn(format='d/M/Y')
    date_of_integration = dt2.DateTimeColumn(format='d/M/Y')

    class Meta:
        model = models.CompanyLicenseModel
        per_page = 100
        fields = ('counter', 'company', 'status',  'scheme', 'license_no','license_date', 'port','dgft_transmission_date', 'date_of_integration', 'error_code', 'file_number')
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)