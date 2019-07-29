import itertools

import django_tables2 as dt2

from . import models


class LicenseDetailTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    edit = dt2.TemplateColumn('<a href="/license/{{ record.id }}/update"><i class="mdi mdi-grease-pencil"></i></a>', orderable=False)
    view = dt2.TemplateColumn('<a href="/license/{{ record.id }}"><i class="mdi mdi-share"></i></a>', orderable=False)
    pdf = dt2.TemplateColumn('<a href="/license/{{ record.license_number }}.pdf"><i class="mdi mdi-file-pdf"></i></a>', orderable=False)
    excel = dt2.TemplateColumn('<a href="/license/{{ record.license_number }}.xlsx"><i class="mdi mdi-file-pdf"></i></a>',
                             orderable=False)
    license_date = dt2.DateTimeColumn(format='d-m-Y')
    license_expiry_date = dt2.DateTimeColumn(format='d-m-Y')
    balance_cif = dt2.Column(verbose_name='Balance CIF', accessor='get_balance_cif', orderable=False)
    norm_class = dt2.Column(verbose_name='Norm Class', accessor='get_norm_class', orderable=False)

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 50
        fields = ['counter', 'notification_number', 'norm_class','port','license_number', 'license_date',
                  'license_expiry_date', 'file_number', 'exporter', 'balance_cif', 'is_audit', 'ledger_date']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)