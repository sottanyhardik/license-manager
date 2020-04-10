# Create your views here.
from django.views.generic import TemplateView, CreateView, UpdateView, DetailView
from extra_views import UpdateWithInlinesView, InlineFormSetFactory

from core.scripts.sion import fetch_sion_data
from core.utils import PagedFilteredTableView
from . import models, tables, filters, forms


class DashboardView(TemplateView):
    template_name = 'dashboard.html'


class CreateCompanyView(CreateView):
    model = models.CompanyModel
    template_name = 'core/add.html'
    fields = "__all__"


class UpdateCompanyView(UpdateView):
    model = models.CompanyModel
    template_name = 'core/add.html'
    fields = "__all__"


class ListCompanyView(PagedFilteredTableView):
    template_name = 'core/../bill_of_entry/templates/bill_of_entry/list.html'
    model = models.CompanyModel
    table_class = tables.CompanyClassTable
    filter_class = filters.CompanyFilter


class SIONExportInline(InlineFormSetFactory):
    model = models.SIONExportModel
    form_class = forms.SIONExportForm
    factory_kwargs = {
        'extra': 0,
        'max_num': 1
    }


class SIONImportInline(InlineFormSetFactory):
    model = models.SIONImportModel
    form_class = forms.SIONImportForm
    factory_kwargs = {
        'extra': 0,
    }


class ListSionView(PagedFilteredTableView):
    template_name = 'core/../bill_of_entry/templates/bill_of_entry/list.html'
    model = models.SionNormClassModel
    table_class = tables.SionNormClassTable
    filter_class = filters.SionNormClassFilter


class SionDetailView(DetailView):
    model = models.SionNormClassModel
    template_name = 'sion/detail.html'
    context_object_name = 'sion_norm'

    def get_object(self, queryset=None):
        return self.model.objects.get(id=self.kwargs.get('pk'))


class UpdateSionView(UpdateWithInlinesView):
    template_name = 'core/add.html'
    model = models.SionNormClassModel
    form_class = forms.SionNormClassForm
    inlines = [SIONExportInline, SIONImportInline]

    def get_object(self, queryset=None):
        object = self.model.objects.get(id=self.kwargs.get('pk'))
        fetch_sion_data(object)
        return object

    def form_valid(self, form):
        import datetime
        if not form.instance.created_by:
            form.instance.created_by = self.request.user
            form.instance.created_on = datetime.datetime.now()
        form.instance.modified_by = self.request.user
        form.instance.modified_on = datetime.datetime.now()
        return super().form_valid(form)


class CreateHSNCodeView(CreateView):
    model = models.HSCodeModel
    template_name = 'core/add.html'
    fields = "__all__"


class ListHSNView(PagedFilteredTableView):
    template_name = 'core/../bill_of_entry/templates/bill_of_entry/list.html'
    model = models.HSCodeModel
    table_class = tables.HSCodeTable
    filter_class = filters.HSNCodeFilter


class CreateItemView(CreateView):
    model = models.ItemNameModel
    template_name = 'core/add.html'
    fields = "__all__"


class ListItemView(PagedFilteredTableView):
    template_name = 'core/../bill_of_entry/templates/bill_of_entry/list.html'
    model = models.ItemNameModel
    table_class = tables.ItemNameTable
    filter_class = filters.ItemFilter


class UpdateItemView(UpdateView):
    model = models.ItemNameModel
    template_name = 'core/add.html'
    fields = "__all__"


class UpdateHSNCodeView(UpdateView):
    model = models.HSCodeModel
    template_name = 'core/add.html'
    fields = "__all__"


class UploadLedger(TemplateView):
    template_name = 'core/ledger.html'

    def get_context_data(self, **kwargs):
        context = super(UploadLedger, self).get_context_data(**kwargs)
        return context

    def post(self, request, **kwargs):
        # workbook = xlrd.open_workbook(files.temporary_file_path())
        # worksheet = workbook.sheet_by_index(0)
        # rows = []
        # for column in range(worksheet.nrows):
        #     for row in range(worksheet.nrows):
        #         print(worksheet.cell(row, column).value)

        files = request.FILES.getlist('ledger')
        license = None
        for raw_file in files:
            file = raw_file.read()
            full = file.decode('utf-8')
            full = full.replace(',','\t')
            for data in full.split('Page No:-1\t'):
                try:
                    from bill_of_entry.scripts.ledger import parse_file
                    license = parse_file(data)
                except Exception as e:
                    print(data)
                    print(e)
                    license = None
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        if license:
            return HttpResponseRedirect(reverse('license_ledger_pdf', kwargs={'license': license}))
        else:
            return HttpResponseRedirect(reverse('ledger-upload'))
