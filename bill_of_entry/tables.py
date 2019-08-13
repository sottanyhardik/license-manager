import itertools

import django_tables2 as dt2

from bill_of_entry import models as bill_of_entry_model
from allotment import models as allotment_model


class BillOfEntryTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    update = dt2.TemplateColumn(
        '<a href="{% url "bill-of-entry-update" record.id %}"><i class="mdi mdi-grease-pencil"></i></a>',
        orderable=False)
    view = dt2.TemplateColumn('<a href="{{ record.get_absolute_url }}"><i class="mdi mdi-share"></i></a>',
                              orderable=False)
    delete = dt2.TemplateColumn(
        '<a href="{% url "bill-of-entry-delete" record.id %}"><i class="mdi mdi-share"></i></a>',
        orderable=False)
    amount_inr = dt2.Column(verbose_name='BE Amount INR', accessor='get_total_inr')
    amount_fc = dt2.Column(verbose_name='BE Amount FC', accessor='get_total_fc')
    quantity = dt2.Column(verbose_name='BE Quantity', accessor='get_total_quantity')
    licenses = dt2.Column(verbose_name='License No', accessor='get_licenses')

    bill_of_entry_date = dt2.DateTimeColumn(format='d-m-Y')

    class Meta:
        model = bill_of_entry_model.BillOfEntryModel
        per_page = 50

        fields = ['counter', 'company', 'bill_of_entry_number', 'bill_of_entry_date','amount_inr', 'amount_fc','quantity','port', 'exchange_rate',
                  'product_name', 'allotment', 'invoice_no', 'licenses']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)
