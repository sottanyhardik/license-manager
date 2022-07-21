import django_tables2 as tables
from django_tables2 import Column
import itertools

from .models import ShippingDetails


class ShippingTable(tables.Table):
    brc_amount = Column(orderable=False)
    brc_date = Column(orderable=False)
    brc_no = Column(orderable=False)
    interest_date = Column(orderable=False)
    days = Column(orderable=False)
    interest_rate = Column(orderable=False)
    interest_amount = Column(orderable=False)
    interest_total = Column(orderable=False)
    counter = tables.Column(empty_values=(), orderable=False)
    shipping_date = tables.DateColumn(format="d M Y")

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count())
        return next(self.row_counter)

    class Meta:
        model = ShippingDetails
        export_formats = ['csv', ]
        empty_text = ''
        template_name = 'django_tables2/bootstrap.html'
        fields = ['counter', 'brc_no', 'brc_date', 'brc_amount', 'shipping_port', 'shipping_bill', 'shipping_date',
                  'gross_weight', 'fob','currency', 'drawback', 'str', 'total', 'dbk_scroll_no', 'scroll_date',
                  'interest_date', 'days', 'interest_rate', 'interest_amount', 'interest_total'
                  ]
