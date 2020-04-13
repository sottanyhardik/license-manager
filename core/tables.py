import django_tables2 as dt2
from . import models
import itertools


class CompanyClassTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    edit = dt2.TemplateColumn('<a href="/company/{{ record.id }}/update/"><i class="mdi mdi-grease-pencil"></i></a>',
                              orderable=False)

    class Meta:
        model = models.CompanyModel
        per_page = 100
        fields = ('counter', 'iec', 'name', 'address', 'phone_number', 'email', 'edit')
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)


class SionNormClassTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    edit = dt2.TemplateColumn('<a href="/sion/{{ record.id }}/update/"><i class="mdi mdi-grease-pencil"></i></a>')
    view = dt2.TemplateColumn('<a href="/sion/{{ record.id }}/"><i class="mdi mdi-share"></i></a>')
    norm_class = dt2.Column(order_by=('id'))

    class Meta:
        model = models.SionNormClassModel
        per_page = 50
        fields = ('counter', 'head_norm', 'norm_class', 'norm_name', 'edit', 'view', 'company_name')
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)


class HSCodeTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    edit = dt2.TemplateColumn('<a href="/hs_code/{{ record.id }}/update/"><i class="mdi mdi-grease-pencil"></i></a>')

    class Meta:
        model = models.HSCodeModel
        per_page = 50
        fields = ('counter', 'hs_code', 'product_description', 'basic_duty')
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)


class ItemNameTable(dt2.Table):
    counter = dt2.Column(empty_values=(), orderable=False)
    edit = dt2.TemplateColumn('<a href="/item/{{ record.id }}/update/"><i class="mdi mdi-grease-pencil"></i></a>')

    class Meta:
        model = models.ItemNameModel
        per_page = 50
        fields = ('counter', 'name','head', 'edit')
        attrs = {"class": "table table-bordered table-striped table-hover dataTable js-exportable dark-bg"}

    def render_counter(self):
        self.row_counter = getattr(self, 'row_counter', itertools.count(start=1))
        return next(self.row_counter)


