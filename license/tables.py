import itertools

import django_tables2 as dt2
from django.contrib.humanize.templatetags.humanize import intcomma

from . import models


class ColumnTotal(dt2.Column):
    column_total = 0

    def render_footer(self, bound_column, table):
        return intcomma(round(self.column_total, 0))


class BalanceCIFColumn(ColumnTotal):

    def render(self, record):
        bills = record.get_balance_cif()
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
    counter = dt2.Column(empty_values=(), orderable=False)
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
        fields = ['counter', 'notification_number', 'norm_class', 'port', 'license_number', 'license_date',
                  'license_expiry_date', 'file_number', 'exporter', 'balance_cif', 'is_audit', 'ledger_date']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)


class LicenseBiscuitReportTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    license = dt2.TemplateColumn('<a href="/license/{{ record.license_number }}/">{{ record.license_number }}</a>',
                                 orderable=False)
    license_expiry_date = dt2.DateTimeColumn(format='d-m-Y', verbose_name='Expiry')
    balance_cif = BalanceCIFColumn(verbose_name='Balance CIF', accessor='get_balance_cif', orderable=False)
    wheat_flour = WheatQuantityColumn(verbose_name='Wheat Flour', accessor='get_wheat', orderable=False)
    sugar = SugarQuantityColumn(verbose_name='Sugar', orderable=False, accessor='get_sugar')
    rbd = RBDQuantityColumn(verbose_name='RBD Palmolein', orderable=False, accessor='get_rbd')
    leavening_agent = LAQuantityColumn(verbose_name='Leavening Agent', orderable=False, accessor='get_leavening_agent')
    emulsifier = EmulsifierQuantityColumn(verbose_name='Emulsifier', orderable=False, accessor='get_emulsifier')
    food_flavour = FFQuantityColumn(verbose_name='Food Flavour', orderable=False, accessor='get_food_flavour')
    starch = StarchQuantityColumn(verbose_name='Starch', orderable=False, accessor='get_starch')
    food_colour = ColourQuantityColumn(verbose_name='Food Colour', orderable=False, accessor='get_food_colour')
    anti_oxidant = AntiOxidantQuantityColumn(verbose_name='Anti Oxidant', orderable=False, accessor='get_anti_oxidant')
    fruit = FruitsQuantityColumn(verbose_name='Fruit', orderable=False, accessor='get_fruit')
    dietary_fibre = DFQuantityColumn(verbose_name='Dietary Fibre', orderable=False, accessor='get_dietary_fibre')
    m_n_m = MNMQuantityColumn(verbose_name='M & M', orderable=False, accessor='get_m_n_m')
    pp = PPQuantityColumn(verbose_name='PP', orderable=False, accessor='get_pp')
    bopp = BOPPQuantityColumn(verbose_name='BOPP', orderable=False, accessor='get_bopp')
    paper = PaperQuantityColumn(verbose_name='Paper', orderable=False, accessor='get_paper')

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 50
        fields = ['counter', 'license', 'license_expiry_date',
                  'exporter', 'balance_cif']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)


class LicenseConfectineryReportTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    license = dt2.TemplateColumn('<a href="/license/{{ record.license_number }}/">{{ record.license_number }}</a>',
                                 orderable=False)
    license_expiry_date = dt2.DateTimeColumn(format='d-m-Y', verbose_name='Expiry')
    balance_cif = BalanceCIFColumn(verbose_name='Balance CIF', accessor='get_balance_cif', orderable=False)
    sugar = SugarQuantityColumn(verbose_name='Sugar', orderable=False, accessor='get_sugar')
    liquid_glucose = LiquidGlucoseQuantityColumn(verbose_name='Liquid Glucose', orderable=False,
                                                 accessor='get_liquid_glucose')
    fruit_juice = FruitsQuantityColumn(verbose_name='Fruit Juice', orderable=False, accessor='get_fruit')
    tartaric_acid = TartaricAcidQuantityColumn(verbose_name='Tartaric Acid', orderable=False,
                                               accessor='get_tartaric_acid')
    essential_oil = EssentialOilQuantityColumn(verbose_name='Essential Oil', orderable=False,
                                               accessor='get_essential_oil')
    food_colour = ColourQuantityColumn(verbose_name='Food Colour', orderable=False, accessor='get_food_colour')
    food_flavour = FFQuantityColumn(verbose_name='Food Flavour', orderable=False, accessor='get_food_flavour')
    starch = StarchConfectioneryQuantityColumn(verbose_name='Starch', orderable=False,
                                               accessor='get_starch_confectionery')
    other_confectionery = OCIQuantityColumn(verbose_name='Other Confectionery Ingredients', orderable=False,
                                            accessor='get_other_confectionery')
    pp = PPQuantityColumn(verbose_name='PP', orderable=False, accessor='get_pp')
    bopp = BOPPQuantityColumn(verbose_name='BOPP', orderable=False, accessor='get_bopp')
    paper = PaperQuantityColumn(verbose_name='Paper', orderable=False, accessor='get_paper')

    class Meta:
        model = models.LicenseDetailsModel
        per_page = 50
        fields = ['counter', 'license', 'license_expiry_date',
                  'exporter', 'balance_cif']
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)
