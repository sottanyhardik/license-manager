# Create your views here.
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView, CreateView, UpdateView, DetailView
from extra_views import UpdateWithInlinesView, InlineFormSetFactory
from tablib import Dataset

from core.scripts.sion import fetch_sion_data
from core.utils import PagedFilteredTableView
from . import models, tables, filters, forms
from .models import MEISMODEL


class DashboardView(TemplateView):
    template_name = 'blank.html'

    def get_context_data(self, **kwargs):
        context = super(DashboardView, self).get_context_data(**kwargs)
        context['page_title'] = "Dashboard"
        return context


class CreateCompanyView(CreateView):
    model = models.CompanyModel
    template_name = 'core/add.html'
    fields = "__all__"


class UpdateCompanyView(UpdateView):
    model = models.CompanyModel
    template_name = 'core/add.html'
    fields = "__all__"


class ListCompanyView(PagedFilteredTableView):
    template_name = 'core/list.html'
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
    template_name = 'core/list.html'
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
    template_name = 'core/list.html'
    model = models.HSCodeModel
    table_class = tables.HSCodeTable
    filter_class = filters.HSNCodeFilter


class CreateItemView(CreateView):
    model = models.ItemNameModel
    template_name = 'core/add.html'
    fields = "__all__"


class ListItemView(PagedFilteredTableView):
    template_name = 'core/list.html'
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

    def get_success_url(self):
        from django.urls import reverse
        return reverse('hs-code-update', kwargs={'pk': self.object.pk})


class LedgerSuccess(TemplateView):
    template_name = 'core/message.html'


class UploadLedger(TemplateView):
    template_name = 'core/ledger.html'

    def get_context_data(self, **kwargs):
        context = super(UploadLedger, self).get_context_data(**kwargs)
        return context

    def post(self, request, **kwargs):
        files = request.FILES.getlist('ledger')
        license = None
        for raw_file in files:
            file = raw_file.read()
            full = file.decode('latin-1').encode("utf-8")
            full = full.decode()
            full = full.replace(',', '\t')
            full = full.replace('Â', '')
            full = full.replace('\xa0', ' ')
            full = full.replace('No:-10', 'No:-T')
            full = full.replace('No:-11', 'No:-T')
            full = full.replace('No:-12', 'No:-T')
            full = full.replace('No:-13', 'No:-T')
            full = full.replace('No:-14', 'No:-T')
            full = full.replace('No:-15', 'No:-T')
            split_list = full.split('Page No:-1')
            for data in split_list:
                try:
                    from bill_of_entry.scripts.ledger import parse_file
                    license = parse_file(data)
                    messages.success(request, str(license))
                except Exception as e:
                    messages.error(request, str(e))
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(reverse('ledger-complete'))



class TemplateListView(TemplateView):
    template_name = 'base.html'


class MEISTLVIEW(TemplateView):
    template_name = 'core/list.html'
    model = models.MEISMODEL


class UploadMEISView(TemplateView):
    template_name = 'upload.html'

    def post(self, request, *args, **kwargs):
        dataset = Dataset()
        new_orders = self.request.FILES['myfile']
        imported_data = dataset.load(new_orders.read())
        models.MEISMODEL.objects.all().delete()
        for data in imported_data.dict:
            meis = models.MEISMODEL()
            meis.importer = data['Importer']
            meis.exporter = data['Exporter']
            dfia = str(data['DFIA']).split('.')[0]
            if len(dfia) == 9:
                meis.dfia_no = '0' + dfia
            else:
                meis.dfia_no = dfia
            meis.dfia_date = data['DFIA_DT']
            meis.cif_inr = data['CIF_INR']
            meis.file_number = data['FILE_NUMBER']
            meis.save()
        return redirect("meis-upload")

    def get_context_data(self, **kwargs):
        context = super(UploadMEISView, self).get_context_data(**kwargs)
        context['page_title'] = 'Upload Order List'
        context['object_list'] = MEISMODEL.objects.all()
        return context


class GenerateTransferLetterMEISView(View):

    def get(self, request, *args, **kwargs):
        from shutil import make_archive
        from datetime import datetime
        meis_list = models.MEISMODEL.objects.all()
        data = [{
            'id': item.id,
            'company': item.importer,
            'today': str(datetime.now().date()),
            'license': item.dfia_no,
            'license_date': item.dfia_date,
            'file_number': item.file_no,
            'v_allotment_inr': item.cif_inr,
            'exporter_name': item.exporter} for item in
            meis_list]
        from core.models import TransferLetterModel
        value = self.request.GET.get('type')
        if value == 'empty':
            transfer_letter = TransferLetterModel.objects.get(name='GE EMPTY MEIS')
        else:
            transfer_letter = TransferLetterModel.objects.get(name='GE FILLED MEIS')
        tl_path = transfer_letter.tl.path
        file_path = 'media/TL_' + 'meis' + '_' + transfer_letter.name.replace(' ', '_') + '/'
        transfer_letter_name = transfer_letter.name.replace(' ', '_')
        from allotment.scripts.aro import generate_tl_software
        generate_tl_software(data=data, tl_path=tl_path, path=file_path, transfer_letter_name=transfer_letter_name)
        file_name = 'TL_' + 'meis' + '_' + 'GE' + '.zip'
        path_to_zip = make_archive(file_path, "zip", file_path)
        zip_file = open(path_to_zip, 'rb')
        response = HttpResponse(zip_file, content_type='application/force-download')
        response['Content-Disposition'] = 'attachment; filename="%s"' % file_name
        return response
