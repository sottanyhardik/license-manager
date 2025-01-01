import decimal
import itertools

import django_tables2 as dt2
from django.contrib.humanize.templatetags.humanize import intcomma
from django.template.defaultfilters import floatformat
from django_tables2 import Column

from . import models


class ColumnTotal(dt2.Column):
    column_total = 0

    def render_footer(self, bound_column, table):
        return intcomma(round(self.column_total, 0))


class BalanceCIFColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_balance_cif
        self.column_total += bills
        return intcomma(round(bills, 2))


class TotalBalanceCIFColumn(ColumnTotal):

    def render(self, record):
        bills = record.opening_balance
        self.column_total += bills
        return intcomma(round(bills, 2))


class PERCIFColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_per_cif()
        self.column_total += bills
        return intcomma(round(bills, 0))


class WheatQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_wheat()
        self.column_total += bills
        return intcomma(round(bills, 0))


class SugarQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_sugar()
        self.column_total += bills
        return intcomma(round(bills, 0))


class BOPPQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_bopp()
        self.column_total += bills
        return intcomma(round(bills, 0))


class FruitsQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_fruit()
        self.column_total += bills
        return intcomma(round(bills, 0))


class PaperQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_paper()
        self.column_total += bills
        return intcomma(round(bills, 0))


class MNMQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_m_n_m()
        self.column_total += bills
        return intcomma(round(bills, 0))


class PPQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_pp()
        self.column_total += bills
        return intcomma(round(bills, 0))


class PaperBoardQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_pp()
        self.column_total += bills
        return intcomma(round(bills, 0))


class DFQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_dietary_fibre()
        self.column_total += bills
        return intcomma(round(bills, 0))


class ColourQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_food_colour()
        self.column_total += bills
        return intcomma(round(bills, 0))


class AntiOxidantQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_anti_oxidant()
        self.column_total += bills
        return intcomma(round(bills, 0))


class StarchQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_starch()
        self.column_total += bills
        return intcomma(round(bills, 0))


class StarchConfectioneryQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_starch_confectionery()
        self.column_total += bills
        return intcomma(round(bills, 0))


class EmulsifierQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_emulsifier()
        self.column_total += bills
        return intcomma(round(bills, 0))


class FFQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_food_flavour()
        self.column_total += bills
        return intcomma(round(bills, 0))


class LAQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_leavening_agent()
        self.column_total += bills
        return intcomma(round(bills, 0))


class RBDQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_rbd()
        self.column_total += bills
        return intcomma(round(bills, 0))


class LiquidGlucoseQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_liquid_glucose()
        self.column_total += bills
        return intcomma(round(bills, 0))


class TartaricAcidQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_tartaric_acid()
        self.column_total += bills
        return intcomma(round(bills, 0))


class OCIQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_other_confectionery()
        self.column_total += bills
        return intcomma(round(bills, 0))


class EssentialOilQuantityColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_essential_oil()
        self.column_total += bills
        return intcomma(round(bills, 0))


class LicenseDetailTable(dt2.Table):
    sr_no = dt2.Column(empty_values=(), orderable=False)
    edit = dt2.TemplateColumn('<a href="/license/{{ record.id }}/update"><i class="mdi mdi-grease-pencil"></i></a>',
                              orderable=False)
    view = dt2.TemplateColumn('<a href="/license/{{ record.license_number }}/"><i class="mdi mdi-share"></i></a>',
                              orderable=False)
    pdf = dt2.TemplateColumn('<a href="/license/{{ record.license_number }}.pdf"><i class="mdi mdi-file-pdf"></i></a>',
                             orderable=False)
    excel = dt2.TemplateColumn(
        '<a href="/license/{{ record.license_number }}.xlsx"><i class="mdi mdi-file-pdf"></i></a>',
        orderable=False)
    license_date = dt2.DateTimeColumn(format='d-m-Y')
    license_expiry_date = dt2.DateTimeColumn(format='d-m-Y')
    balance_cif = BalanceCIFColumn(verbose_name='Balance CIF', accessor='get_balance_cif', orderable=False)
    norm_class = dt2.Column(verbose_name='Norm Class', accessor='get_norm_class', orderable=False)

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 50
        fields = ['sr_no', 'notification_number', 'norm_class', 'port', 'is_au', 'license_number', 'license_date',
                  'license_expiry_date', 'file_number', 'exporter', 'balance_cif', 'is_audit', 'ledger_date']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_sr_no(self):
        self.row_sr_no = getattr(self, 'row_sr_no', itertools.count(start=1))
        return next(self.row_sr_no)


class DecimalColumnWithTotal(Column):
    def __init__(self, *args, **kwargs):
        self.total = decimal.Decimal(0)  # Make sure total is a Decimal
        super().__init__(*args, **kwargs)

    def render(self, record):
        value = decimal.Decimal(self.accessor.resolve(record))  # Make sure value is Decimal
        self.total += value
        return floatformat(value, 2)

    def render_footer(self):
        return floatformat(self.total, 2)


class PrefixMixin:
    @staticmethod
    def prefixed(field, **kwargs):
        return dt2.TemplateColumn('\'{{record.%s}}' % field, **kwargs)


class LicenseReportTable(dt2.Table):
    sr_no = dt2.Column(empty_values=(), orderable=False)
    license_number = PrefixMixin.prefixed('license_number', verbose_name='DFIA No', orderable=False)
    license_date = PrefixMixin.prefixed('license_date', verbose_name='DFIA Dt', orderable=False)
    license_expiry_date = PrefixMixin.prefixed('license_expiry_date', verbose_name='Expiry Dt', orderable=False)
    party = dt2.Column(verbose_name='Exporter', accessor='exporter__name', orderable=False)
    total_cif = DecimalColumnWithTotal(verbose_name='Total CIF', accessor='opening_balance', orderable=False)
    balance_cif = DecimalColumnWithTotal(verbose_name='Balance CIF', accessor='get_balance_cif', orderable=False)


class LicenseBiscuitReportTable(LicenseReportTable):
    veg_oil_hsn = PrefixMixin.prefixed('oil_queryset.hs_code__hs_code', verbose_name='Vegetable Oil HSN Code',
                                       orderable=False)
    veg_oil_pd = dt2.Column(verbose_name='Vegetable Oil PD', accessor='oil_queryset.description', orderable=False)
    total_veg_qty = DecimalColumnWithTotal(verbose_name='Total Veg QTY', accessor='oil_queryset.available_quantity_sum',
                                           orderable=False)
    rbd_qty = DecimalColumnWithTotal(verbose_name='RBD QTY',
                                     accessor='cif_value_balance_biscuits.veg_oil.get_rbd.quantity', orderable=False)
    rbd_cif = DecimalColumnWithTotal(verbose_name='RBD CIF',
                                     accessor='cif_value_balance_biscuits.veg_oil.get_rbd.value', orderable=False)
    pko_qty = DecimalColumnWithTotal(verbose_name='PKO QTY', accessor='cif_value_balance_biscuits.veg_oil.pko.quantity',
                                     orderable=False)
    pko_cif = DecimalColumnWithTotal(verbose_name='PKO CIF', accessor='cif_value_balance_biscuits.veg_oil.pko.value',
                                     orderable=False)
    veg_qty = DecimalColumnWithTotal(verbose_name='VEG QTY',
                                     accessor='cif_value_balance_biscuits.veg_oil.veg_oil.quantity', orderable=False)
    veg_cif = DecimalColumnWithTotal(verbose_name='VEG CIF',
                                     accessor='cif_value_balance_biscuits.veg_oil.veg_oil.value', orderable=False)
    ten_restriction = DecimalColumnWithTotal(verbose_name='10% Value Bal',
                                             accessor='cif_value_balance_biscuits.cif_juice', orderable=False)
    juice_hsn = PrefixMixin.prefixed('get_biscuit_juice.hs_code__hs_code', verbose_name='JUICE HSN Code',
                                       orderable=False)
    juice_pd = dt2.Column(verbose_name='Juice PD', accessor='get_biscuit_juice.description', orderable=False)
    juice_qty = DecimalColumnWithTotal(verbose_name='Juice Qty', accessor='get_biscuit_juice.available_quantity_sum',
                                       orderable=False)
    juice_cif = DecimalColumnWithTotal(verbose_name='JUICE CIF',
                                       accessor='cif_value_balance_biscuits.cif_juice', orderable=False)
    ff_hsn = PrefixMixin.prefixed('get_food_flavour.hs_code__hs_code', verbose_name='FF HSN Code',
                                     orderable=False)
    ff_pd = dt2.Column(verbose_name='FF PD', accessor='get_food_flavour.description', orderable=False)
    ff_qty = DecimalColumnWithTotal(verbose_name='FF QTY', accessor='get_food_flavour.available_quantity_sum',
                                    orderable=False)
    df_qty = DecimalColumnWithTotal(verbose_name='DF Qty', accessor='get_dietary_fibre.available_quantity_sum',
                                    orderable=False)
    f_f_qty = DecimalColumnWithTotal(verbose_name='Fruit/Cocoa', accessor='get_fruit.available_quantity_sum',
                                     orderable=False)
    f_f_cif = DecimalColumnWithTotal(verbose_name='Fruit/Cocoa CIF',
                                     accessor='cif_value_balance_biscuits.f_f_cif', orderable=False)
    la_qty = DecimalColumnWithTotal(verbose_name='Leavening Agent Qty',
                                    accessor='get_leavening_agent.available_quantity_sum',
                                    orderable=False)
    starch_1108 = DecimalColumnWithTotal(verbose_name='Starch 1108', accessor='get_wheat_starch.available_quantity_sum',
                                         orderable=False)
    starch__1108_cif = DecimalColumnWithTotal(verbose_name='Starch 1108 CIF',
                                              accessor='cif_value_balance_biscuits.wheat_starch_cif', orderable=False)
    starch_3505 = DecimalColumnWithTotal(verbose_name='Starch 3505',
                                         accessor='get_modified_starch.available_quantity_sum', orderable=False)
    mnm_pd = dt2.Column(verbose_name='Milk & Milk PD', accessor='get_mnm_pd.description', orderable=False)
    mnm_qty = DecimalColumnWithTotal(verbose_name='Milk & Milk Qty', accessor='get_mnm_pd.available_quantity_sum',
                                     orderable=False)
    cheese_qty = DecimalColumnWithTotal(verbose_name='Cheese Qty', accessor='get_cheese.available_quantity_sum',
                                        orderable=False)
    cheese_cif = DecimalColumnWithTotal(verbose_name='Cheese CIF', accessor='cif_value_balance_biscuits.cif_cheese',
                                        orderable=False)
    swp_qty = DecimalColumnWithTotal(verbose_name='SWP QTY', accessor='get_swp.available_quantity_sum', orderable=False)
    swp_cif = DecimalColumnWithTotal(verbose_name='SWP CIF', accessor='cif_value_balance_biscuits.cif_swp',
                                     orderable=False)
    wpc_qty = DecimalColumnWithTotal(verbose_name='WPC QTY', accessor='get_wpc.available_quantity_sum', orderable=False)
    pp_hsn = PrefixMixin.prefixed('get_pp.hs_code__hs_code', verbose_name='PP HSN', orderable=False)
    pp_pd = dt2.Column(verbose_name='PP PD', accessor='get_pp.description', orderable=False)
    pp_qty = DecimalColumnWithTotal(verbose_name='PP QTY', accessor='get_pp.available_quantity_sum', orderable=False)
    get_aluminium = DecimalColumnWithTotal(verbose_name='Aluminium Foil QTY',
                                           accessor='get_aluminium.available_quantity_sum', orderable=False)
    balance_cif_value = DecimalColumnWithTotal(verbose_name='Wastage CIF',
                                               accessor='cif_value_balance_biscuits.available_value', orderable=False)

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 100
        fields = []
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_sr_no(self):
        self.row_sr_no = getattr(self, 'row_sr_no', itertools.count(start=1))
        return next(self.row_sr_no)


class LicenseConfectioneryReportTable(LicenseReportTable):
    get_sugar = DecimalColumnWithTotal(verbose_name='Sugar Qty', accessor='sugar_quantity.available_quantity_sum',
                                       orderable=False)
    get_juice_hsn = PrefixMixin.prefixed('get_juice.hs_code__hs_code', verbose_name='Juice HSN', orderable=False)
    get_juice_pd = dt2.Column(verbose_name='Juice PD', accessor='get_juice.description',
                              orderable=False)

    get_juice = DecimalColumnWithTotal(verbose_name='Juice Qty', accessor='get_juice.available_quantity_sum',
                                       orderable=False)
    get_tartaric_acid = DecimalColumnWithTotal(verbose_name='Tartaric Acid Qty',
                                               accessor='get_tartaric_acid.available_quantity_sum', orderable=False)
    get_food_flavour_confectionery_hsn = PrefixMixin.prefixed('get_food_flavour_confectionery.hs_code__hs_code',
                                                              verbose_name='Food Flavour HSN', orderable=False)
    get_food_flavour_confectionery_pd = dt2.Column(verbose_name='Food Flavour PD',
                                                   accessor='get_food_flavour_confectionery.description',
                                                   orderable=False)
    get_food_flavour_confectionery_qty = DecimalColumnWithTotal(verbose_name='Food Flavour QTY',
                                                                accessor='get_food_flavour_confectionery.available_quantity_sum',
                                                                orderable=False)
    get_essential_oil_hsn = PrefixMixin.prefixed('get_essential_oil.hs_code__hs_code', verbose_name='Essential Oil HSN',
                                                 orderable=False)
    get_essential_oil_pd = dt2.Column(verbose_name='Essential Oil PD', accessor='get_essential_oil.description',
                                      orderable=False)
    get_essential_oil_qty = DecimalColumnWithTotal(verbose_name='Essential Oil QTY',
                                                   accessor='get_essential_oil.available_quantity_sum', orderable=False)
    fiveRestriction = DecimalColumnWithTotal(verbose_name='5% Balance',
                                             accessor='get_per_cif.fiveRestriction',
                                             orderable=False)
    get_starch_confectionery_hsn = PrefixMixin.prefixed('get_starch_confectionery.hs_code__hs_code',
                                                        verbose_name='Emulsifier HSN', orderable=False)
    get_starch_confectionery_pd = dt2.Column(verbose_name='Emulsifier PD',
                                             accessor='get_starch_confectionery.description', orderable=False)
    get_starch_confectionery_qty = DecimalColumnWithTotal(verbose_name='Emulsifier QTY',
                                                          accessor='get_starch_confectionery.available_quantity_sum',
                                                          orderable=False)
    threeRestriction = DecimalColumnWithTotal(verbose_name='3% Balance',
                                              accessor='get_per_cif.threeRestriction',
                                              orderable=False)
    get_other_confectionery_hsn = PrefixMixin.prefixed('get_other_confectionery.hs_code__hs_code',
                                                       verbose_name='OCI HSN', orderable=False)
    get_other_confectionery_pd = dt2.Column(verbose_name='OCI PD', accessor='get_other_confectionery.description',
                                            orderable=False)
    get_other_confectionery_qty = DecimalColumnWithTotal(verbose_name='OCI QTY',
                                                         accessor='get_other_confectionery.available_quantity_sum',
                                                         orderable=False)
    twoRestriction = DecimalColumnWithTotal(verbose_name='2% Balance',
                                            accessor='get_per_cif.twoRestriction',
                                            orderable=False)
    pp_qty = DecimalColumnWithTotal(verbose_name='PP QTY', accessor='get_pp.available_quantity_sum', orderable=False)
    get_aluminium = DecimalColumnWithTotal(verbose_name='Aluminium Foil QTY',
                                           accessor='get_aluminium.available_quantity_sum', orderable=False)
    pnp_qty = DecimalColumnWithTotal(verbose_name='Paper & Paper QTY',
                                     accessor='get_paper_and_paper.available_quantity_sum', orderable=False)

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 50
        fields = []
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_sr_no(self):
        self.row_sr_no = getattr(self, 'row_sr_no', itertools.count(start=1))
        return next(self.row_sr_no)


class LicenseNamkeenReportTable(LicenseReportTable):
    get_chickpeas_hsn = PrefixMixin.prefixed('get_chickpeas.hs_code__hs_code', verbose_name='Chickpeas HSN',
                                             orderable=False)
    get_chickpeas_pd = dt2.Column(verbose_name='Chickpeas PD', accessor='get_chickpeas.description',
                                  orderable=False)
    get_chickpeas_qty = DecimalColumnWithTotal(verbose_name='Chickpeas QTY',
                                               accessor='get_chickpeas.available_quantity_sum', orderable=False)
    oil_queryset_hsn = PrefixMixin.prefixed('oil_queryset.hs_code__hs_code', verbose_name='Vegetable Oil HSN',
                                            orderable=False)
    oil_queryset_pd = dt2.Column(verbose_name='Vegetable Oil PD', accessor='oil_queryset.description',
                                 orderable=False)
    get_rbd = DecimalColumnWithTotal(verbose_name='RBD Oil QTY',
                                     accessor='get_rbd.available_quantity_sum', orderable=False)
    get_pko = DecimalColumnWithTotal(verbose_name='PKO Oil QTY',
                                     accessor='get_pko.available_quantity_sum', orderable=False)
    get_cmc_pd = dt2.Column(verbose_name='CMC PD', accessor='get_cmc.description',
                            orderable=False)
    get_cmc_qty = DecimalColumnWithTotal(verbose_name='CMC QTY',
                                         accessor='get_cmc.available_quantity_sum', orderable=False)
    get_cmc_value = DecimalColumnWithTotal(verbose_name='5% Restriction',
                                           accessor='get_per_cif.fiveRestriction', orderable=False)

    get_food_flavour_namkeen_hsn = PrefixMixin.prefixed('get_food_flavour_namkeen.hs_code__hs_code',
                                                        verbose_name='Food Flavour PD', orderable=False)
    get_food_flavour_namkeen_pd = dt2.Column(verbose_name='Food Flavour PD',
                                             accessor='get_food_flavour_namkeen.description',
                                             orderable=False)
    get_food_flavour_namkeen_qty = DecimalColumnWithTotal(verbose_name='Food Flavour QTY',
                                                          accessor='get_food_flavour_namkeen.available_quantity_sum',
                                                          orderable=False)
    threeRestriction = DecimalColumnWithTotal(verbose_name='3% Restriction',
                                              accessor='get_per_cif.threeRestriction', orderable=False)
    pp_qty = DecimalColumnWithTotal(verbose_name='PP QTY', accessor='get_pp.available_quantity_sum', orderable=False)
    get_aluminium = DecimalColumnWithTotal(verbose_name='Aluminium Foil QTY',
                                           accessor='get_aluminium.available_quantity_sum', orderable=False)

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 50
        fields = []
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_sr_no(self):
        self.row_sr_no = getattr(self, 'row_sr_no', itertools.count(start=1))
        return next(self.row_sr_no)


class LicenseSteelReportTable(LicenseReportTable):
    get_hot_rolled_hsn = PrefixMixin.prefixed('get_hot_rolled.hs_code__hs_code', verbose_name='HOT ROLLED STEEL HSN',
                                              orderable=False)
    get_hot_rolled_pd = dt2.Column(verbose_name='HOT ROLLED STEEL PD', accessor='get_hot_rolled.description',
                                   orderable=False)
    get_hot_rolled_qty = DecimalColumnWithTotal(verbose_name='HOT ROLLED STEEL QTY',
                                                accessor='get_hot_rolled.available_quantity_sum', orderable=False)

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 50
        fields = []
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_sr_no(self):
        self.row_sr_no = getattr(self, 'row_sr_no', itertools.count(start=1))
        return next(self.row_sr_no)


class LicenseTractorReportTable(LicenseReportTable):
    get_battery_hsn = PrefixMixin.prefixed('get_battery.hs_code__hs_code', verbose_name='Battery HSN',
                                           orderable=False)
    get_battery_pd = dt2.Column(verbose_name='Battery PD', accessor='get_battery.description',
                                orderable=False)
    get_battery_total_qty = DecimalColumnWithTotal(verbose_name='Battery TOTAL QTY',
                                                   accessor='get_battery.quantity_sum', orderable=False)
    get_battery_qty = DecimalColumnWithTotal(verbose_name='Battery QTY',
                                             accessor='get_battery.available_quantity_sum', orderable=False)
    get_alloy_steel_hsn = PrefixMixin.prefixed('get_alloy_steel_total.hs_code__hs_code', verbose_name='ALLOY STEEL HSN',
                                               orderable=False)
    get_alloy_steel_pd = dt2.Column(verbose_name='ALLOY STEEL PD', accessor='get_alloy_steel_total.description',
                                    orderable=False)
    get_alloy_steel_total_qty = DecimalColumnWithTotal(verbose_name='ALLOY STEEL TOTAL QTY',
                                                       accessor='get_alloy_steel_total.quantity_sum', orderable=False)
    get_alloy_steel_qty = DecimalColumnWithTotal(verbose_name='ALLOY STEEL QTY',
                                                 accessor='get_alloy_steel_total.available_quantity_sum',
                                                 orderable=False)
    get_hot_rolled_hsn = PrefixMixin.prefixed('get_hot_rolled.hs_code__hs_code', verbose_name='HOT ROLLED STEEL HSN',
                                              orderable=False)
    get_hot_rolled_pd = dt2.Column(verbose_name='HOT ROLLED STEEL PD', accessor='get_hot_rolled.description',
                                   orderable=False)
    get_hot_rolled_total_qty = DecimalColumnWithTotal(verbose_name='HOT ROLLED STEEL TOTAL QTY',
                                                      accessor='get_hot_rolled.quantity_sum', orderable=False)
    get_hot_rolled_qty = DecimalColumnWithTotal(verbose_name='HOT ROLLED STEEL QTY',
                                                accessor='get_hot_rolled.available_quantity_sum', orderable=False)
    get_bearing_hsn = PrefixMixin.prefixed('get_bearing.hs_code__hs_code', verbose_name='BEARING HSN', orderable=False)
    get_bearing_pd = dt2.Column(verbose_name='BEARING PD', accessor='get_bearing.description',
                                orderable=False)
    get_bearing_total_qty = DecimalColumnWithTotal(verbose_name='BEARING TOTAL QTY',
                                                   accessor='get_bearing.quantity_sum', orderable=False)
    get_bearing_qty = DecimalColumnWithTotal(verbose_name='BEARING QTY',
                                             accessor='get_bearing.available_quantity_sum', orderable=False)

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 50
        fields = []
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_sr_no(self):
        self.row_sr_no = getattr(self, 'row_sr_no', itertools.count(start=1))
        return next(self.row_sr_no)


class LicenseGlassReportTable(LicenseReportTable):
    average_unit_price = dt2.Column(verbose_name='Average', accessor='average_unit_price',
                                    orderable=False)
    get_glass_formers_pd = dt2.Column(verbose_name='Glass Former PD', accessor='get_glass_formers.description',
                                      orderable=False)
    get_glass_formers_total_qty = DecimalColumnWithTotal(verbose_name='Glass Former Total Qty',
                                                         accessor='get_glass_formers.total',
                                                         orderable=False)
    borax_qty = DecimalColumnWithTotal(verbose_name='Borax QTY',
                                       accessor='get_glass_formers.borax', orderable=False)
    borax_value = DecimalColumnWithTotal(verbose_name='Borax Value',
                                         accessor='cif_value_balance_glass.borax', orderable=False)
    rutile_qty = DecimalColumnWithTotal(verbose_name='Rutile QTY',
                                        accessor='get_glass_formers.rutile', orderable=False)
    unit_price = dt2.Column(verbose_name='Unit Price', accessor='average_unit_price',
                            orderable=False)
    rutile_value = DecimalColumnWithTotal(verbose_name='Rutile Value',
                                          accessor='cif_value_balance_glass.rutile', orderable=False)
    get_intermediates_namely_pd = dt2.Column(verbose_name='Intermediates Namely PD',
                                             accessor='get_intermediates_namely.description',
                                             orderable=False)
    get_intermediates_namely_qty = DecimalColumnWithTotal(verbose_name='Intermediates Namely Qty',
                                                          accessor='get_intermediates_namely.available_quantity_sum',
                                                          orderable=False)
    get_modifiers_namely_pd = dt2.Column(verbose_name='Modifiers Namely PD',
                                         accessor='get_modifiers_namely.description',
                                         orderable=False)
    get_modifiers_namely_qty = DecimalColumnWithTotal(verbose_name='Modifiers Namely Qty',
                                                      accessor='get_modifiers_namely.available_quantity_sum',
                                                      orderable=False)
    get_modifiers_namely_cif = DecimalColumnWithTotal(verbose_name='Modifiers Namely Value',
                                                      accessor='cif_value_balance_glass.soda_ash',
                                                      orderable=False)
    get_other_special_additives_pd = dt2.Column(verbose_name='OTHER SPECIAL ADDITIVES PD',
                                                accessor='get_other_special_additives.description',
                                                orderable=False)
    get_other_special_additives_qty = DecimalColumnWithTotal(verbose_name='OTHER SPECIAL ADDITIVES Qty',
                                                             accessor='get_other_special_additives.available_quantity_sum',
                                                             orderable=False)
    get_other_special_additives_cif = DecimalColumnWithTotal(verbose_name='OTHER SPECIAL ADDITIVES Value',
                                                             accessor='cif_value_balance_glass.titanium',
                                                             orderable=False)
    pp_qty = DecimalColumnWithTotal(verbose_name='PP QTY', accessor='get_pp.available_quantity_sum', orderable=False)
    get_aluminium = DecimalColumnWithTotal(verbose_name='Aluminium Foil QTY',
                                           accessor='get_aluminium.available_quantity_sum', orderable=False)
    balance_cif_value = DecimalColumnWithTotal(verbose_name='Wastage CIF',
                                               accessor='cif_value_balance_glass.balance_cif', orderable=False)

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 100
        fields = []
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_sr_no(self):
        self.row_sr_no = getattr(self, 'row_sr_no', itertools.count(start=1))
        return next(self.row_sr_no)


class LicensePickleReportTable(LicenseReportTable):
    get_veg_oil_hsn = PrefixMixin.prefixed('get_veg_oil.hs_code__hs_code', verbose_name='Relevant Fats and Oils HSN',
                                           orderable=False)
    get_veg_oil_pd = dt2.Column(verbose_name='Relevant Fats and Oils PD', accessor='get_veg_oil.description',
                                orderable=False)
    get_veg_oil_qty = DecimalColumnWithTotal(verbose_name='Relevant Fats and Oils QTY',
                                             accessor='get_veg_oil.available_quantity_sum', orderable=False)

    get_rfa_hsn = PrefixMixin.prefixed('get_rfa.hs_code__hs_code', verbose_name='Relevant Food Additives HSN',
                                       orderable=False)
    get_rfa_pd = dt2.Column(verbose_name='Relevant Food Additives PD', accessor='get_rfa.description',
                            orderable=False)
    get_rfa_qty = DecimalColumnWithTotal(verbose_name='Relevant Food Additives QTY',
                                         accessor='get_rfa.available_quantity_sum', orderable=False)
    threeRestriction = DecimalColumnWithTotal(verbose_name='3% Restriction',
                                              accessor='get_per_cif.threeRestriction', orderable=False)
    pp_qty = DecimalColumnWithTotal(verbose_name='PP QTY', accessor='get_pp.available_quantity_sum', orderable=False)
    get_aluminium = DecimalColumnWithTotal(verbose_name='Aluminium Foil QTY',
                                           accessor='get_aluminium.available_quantity_sum', orderable=False)

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 100
        fields = []
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_sr_no(self):
        self.row_sr_no = getattr(self, 'row_sr_no', itertools.count(start=1))
        return next(self.row_sr_no)


class TruncatedTextColumn(dt2.Column):
    '''A Column to limit to 100 characters and add an ellipsis'''

    def render(self, value):
        if len(value) > 10:
            return value[0:10] + '...'
        return str(value)


class TruncatedBigTextColumn(dt2.Column):
    '''A Column to limit to 100 characters and add an ellipsis'''

    def render(self, value):
        if len(value) > 32:
            return value[0:30] + '...'
        return str(value)


class ColumnWithThousandsSeparator(dt2.Column):
    column_total = 0

    def render(self, value):
        return intcomma(round(value, 2))

    def render_footer(self, bound_column, table):
        return intcomma(round(self.column_total, 0))


class LicenseItemReportTable(dt2.Table):
    sr_no = dt2.Column(empty_values=(), orderable=False)
    license_date = dt2.DateTimeColumn(format='d-m-Y', accessor='license.license_date')
    license_expiry = dt2.DateTimeColumn(format='d-m-Y', verbose_name='License Expiry Date',
                                        accessor='license.license_expiry_date')
    license_exporter = TruncatedTextColumn(verbose_name='Exporter', accessor='license.exporter.name')
    item = dt2.Column(verbose_name='Item Description', accessor='description')
    available_quantity = DecimalColumnWithTotal(verbose_name='Available Qty', accessor='available_quantity',
                                                orderable=False)
    available_value = DecimalColumnWithTotal(verbose_name='Available CIF', accessor='available_value', orderable=False)

    class Meta:
        model = models.LicenseImportItemsModel
        per_page = 500
        fields = ['sr_no', 'serial_number', 'license', 'license_date', 'license_expiry', 'license_exporter',
                  'hs_code', 'item', 'available_quantity', 'available_value', 'comment']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_sr_no(self):
        self.row_sr_no = getattr(self, 'row_sr_no', itertools.count(start=1))
        return next(self.row_sr_no)


class RutileLicenseItemReportTable(LicenseItemReportTable):
    rutile_quantity = dt2.Column()
    borax_quantity = dt2.Column()

    class Meta:
        fields = ['sr_no', 'serial_number', 'license', 'license_date', 'license_expiry', 'license_exporter',
                  'hs_code', 'item', 'rutile_quantity', 'borax_quantity', 'available_quantity', 'available_value',
                  'comment']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}


class LicenseInwardOutwardTable(dt2.Table):
    sr_no = dt2.Column(empty_values=(), orderable=False)
    ge_file_number = dt2.Column(orderable=False)

    class Meta:
        model = models.LicenseInwardOutwardModel
        per_page = 50
        fields = (
            'sr_no', 'date', 'ge_file_number', 'license', 'status', 'office', 'description',
            'amd_sheets_number', 'copy', 'annexure', 'tl', 'aro', 'along_with')
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_sr_no(self):
        self.row_sr_no = getattr(self, 'row_sr_no', itertools.count(start=1))
        return next(self.row_sr_no)
