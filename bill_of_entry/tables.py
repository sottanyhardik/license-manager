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
    delete = dt2.TemplateColumn('<a href="{% url "bill-of-entry-delete" record.id %}"><i class="mdi mdi-share"></i></a>',
                                orderable=False)

    class Meta:
        model = bill_of_entry_model.BillOfEntryModel
        per_page = 50
        fields = ['counter', 'company', 'bill_of_entry_number', 'bill_of_entry_date', 'port', 'exchange_rate', 'product_name','allotment', 'invoice_no' ]
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)
