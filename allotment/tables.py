import itertools

import django_tables2 as dt2

from license import models as license_model
from allotment import models as allotment_model


class AllotmentItemsTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    license_date = dt2.Column(verbose_name='License Date', accessor='license.license_date')
    license_expiry = dt2.Column(verbose_name='License Expiry Date', accessor='license.license_expiry_date')
    balance_quantity = dt2.TemplateColumn(
        '<spam id = "id_allotment_balance_{{ record.id }}" > {{ record.balance_quantity }} </spam>', orderable=False)
    balance_value = dt2.TemplateColumn(
        '<spam id = "id_allotment_balance_value_{{ record.id }}"> {{ record.balance_cif_fc }} </spam>', orderable=False)
    allotment_quantity = dt2.TemplateColumn(template_name='allotment/quantity_input.html', orderable=False)
    allotment_value = dt2.TemplateColumn(template_name='allotment/value_input.html', orderable=False)

    class Meta:
        model = license_model.LicenseImportItemsModel
        per_page = 50
        fields = ['counter', 'serial_number', 'license', 'license_date', 'license_expiry', 'hs_code', 'item',
                  'balance_quantity', 'balance_value', 'allotment_quantity', 'allotment_value', 'unit']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)


class AllotmentTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    update = dt2.TemplateColumn(
        '<a href="{% url "allotment-update" record.id %}"><i class="mdi mdi-grease-pencil"></i></a>',
        orderable=False)
    view = dt2.TemplateColumn('<a href="{{ record.get_absolute_url }}"><i class="mdi mdi-share"></i></a>',
                              orderable=False)
    delete = dt2.TemplateColumn('<a href="{% url "allotment-delete" record.id %}"><i class="mdi mdi-share"></i></a>',
                                orderable=False)

    class Meta:
        model = allotment_model.AllotmentModel
        per_page = 50
        fields = ['counter', 'type', 'company', 'required_quantity', 'unit_value_per_unit', 'item_name',
                  'contact_person', 'contact_number', ]
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)


def qty_footer(table):
    total = 0
    for data in table.data.data:
        total = total + data.qty
    return round(total, 2)


def cif_fc_footer(table):
    total = 0
    for data in table.data.data:
        total = total + data.cif_fc
    return round(total, 2)


class AllotedItemsTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    delete = dt2.TemplateColumn('<a href="{{ record.get_delete_url }}"><i class="mdi mdi-delete-forever"></i></a>',
                                orderable=False)
    qty = dt2.Column(footer=qty_footer)
    cif_fc = dt2.Column(footer=cif_fc_footer)

    class Meta:
        model = allotment_model.AllotmentItems
        per_page = 50
        fields = ['counter', 'serial_number', 'license_number', 'license_date','exporter','license_expiry','registration_number',
                  'registration_date', 'qty', 'cif_fc', 'notification_number']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)
