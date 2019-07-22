import itertools

import django_tables2 as dt2

from . import models


class LicenseDetailTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    edit = dt2.TemplateColumn('<a href="/license/edit/{{ record.id }}"><i class="mdi mdi-grease-pencil"></i></a>', orderable=False)
    view = dt2.TemplateColumn('<a href="/license/{{ record.id }}"><i class="mdi mdi-share"></i></a>', orderable=False)
    pdf = dt2.TemplateColumn('<a href="/license/{{ record.id }}/pdf"><i class="mdi mdi-file-pdf"></i></a>', orderable=False)
    license_date = dt2.DateTimeColumn(format='d-m-Y')
    license_expiry_date = dt2.DateTimeColumn(format='d-m-Y')

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 50
        fields = ['counter', 'notification_number', 'port_of_registration','license_number', 'license_date',
                  'license_expiry_date', 'file_no', 'exporter', 'balance_cif', 'is_audit', 'ledger_date']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)