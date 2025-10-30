import itertools

import django_tables2 as dt2

from license import models as license_model
from allotment import models as allotment_model


class AllotmentItemsTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    license_date = dt2.DateTimeColumn(format='d-m-Y', accessor='license.license_date')
    license_expiry = dt2.DateTimeColumn(format='d-m-Y', verbose_name='License Expiry Date',
                                        accessor='license.license_expiry_date')
    license_exporter = dt2.Column(verbose_name='Exporter', accessor='license.exporter')
    balance_quantity = dt2.TemplateColumn(
        '<spam id = "id_allotment_balance_{{ record.id }}" > {{ record.balance_quantity }} </spam>', orderable=False)
    balance_value = dt2.TemplateColumn(
        '<spam id = "id_allotment_balance_value_{{ record.id }}"> {{ record.balance_cif_fc }} </spam>', orderable=False)
    allotment_quantity = dt2.TemplateColumn(template_name='allotment/quantity_input.html', orderable=False)
    allotment_value = dt2.TemplateColumn(template_name='allotment/value_input.html', orderable=False)

    class Meta:
        model = license_model.LicenseImportItemsModel
        per_page = 50
        fields = ['counter', 'serial_number', 'license', 'license_date', 'license_expiry', 'license_exporter',
                  'hs_code', 'description',
                  'balance_quantity', 'balance_value', 'allotment_quantity', 'allotment_value', 'unit']
        attrs = {"class": "table table-bordered dataTable js-exportable"}

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
    bl_detail = dt2.Column(verbose_name='BL Details')
    required_quantity = dt2.Column(verbose_name='Quantity')
    unit_value_per_unit = dt2.Column(verbose_name='Unit Price')
    value = dt2.Column(verbose_name='Value', accessor='required_value')
    license = dt2.Column(verbose_name='DFIA No', accessor='dfia_list')

    class Meta:
        model = allotment_model.AllotmentModel
        per_page = 50
        fields = ['counter', 'type', 'company', 'required_quantity', 'unit_value_per_unit','value',
                  'item_name', 'license', 'port', 'invoice', 'eta']
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


class AllottedItemsTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    delete = dt2.TemplateColumn('<a href="{{ record.get_delete_url }}"><i class="mdi mdi-delete-forever"></i></a>',
                                orderable=False)
    qty = dt2.Column(footer=qty_footer)
    cif_fc = dt2.Column(footer=cif_fc_footer)

    class Meta:
        model = allotment_model.AllotmentItems
        per_page = 50
        fields = ['counter', 'serial_number', 'license_number','file_number', 'license_date', 'exporter', 'license_expiry',
                  'registration_number',
                  'registration_date', 'qty', 'cif_fc', 'notification_number']
        attrs = {"class": "table dataTable js-exportable"}
        template_name = "django_tables2/bootstrap.html"

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)
