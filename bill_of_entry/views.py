# Create your views here.
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, DeleteView, UpdateView, CreateView
from django_filters.views import FilterView
from django_tables2 import SingleTableView
from django_tables2.export import ExportMixin
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import UpdateWithInlinesView, InlineFormSetFactory

from allotment.forms import TlForm
from bill_of_entry.models import RowDetails
from lmanagement.tasks import fetch_data_to_model
from . import forms, tables, filters
from . import models as bill_of_entry


class BillOfEntryView(FilterView, ExportMixin, SingleTableView):
    template_name = 'bill_of_entry/list.html'
    model = bill_of_entry.BillOfEntryModel
    table_class = tables.BillOfEntryTable
    filterset_class = filters.BillOfEntryFilter
    paginate_by = 50
    ordering = '-bill_of_entry_date'


class BillOfEntryAjaxListView(FilterView):
    template_name = 'bill_of_entry/ajax_list.html'
    model = bill_of_entry.BillOfEntryModel
    table_class = tables.BillOfEntryTable
    filterset_class = filters.BillOfEntryFilter
    paginate_by = 50
    ordering = '-bill_of_entry_date'


class BillOfEntryCreateView(CreateView):
    template_name = 'bill_of_entry/add.html'
    model = bill_of_entry.BillOfEntryModel
    form_class = forms.BillOfEntryForm

    def get_context_data(self, **kwargs):
        context = super(BillOfEntryCreateView, self).get_context_data(**kwargs)
        context['inline'] = True
        return context


class BillOfEntryDetailView(DetailView):
    template_name = 'bill_of_entry/card.html'
    model = bill_of_entry.BillOfEntryModel

    def get_object(self, queryset=None):
        object = self.model.objects.get(bill_of_entry_number=self.kwargs.get('boe'))
        return object

    def get_context_data(self, **kwargs):
        context = super(BillOfEntryDetailView, self).get_context_data(**kwargs)
        context['important'] = 'show active'
        return context


class BillOfEntryLicenseImportItemInline(InlineFormSetFactory):
    model = bill_of_entry.RowDetails
    form_class = forms.ImportItemsForm
    factory_kwargs = {
        'extra': 0,
    }


class BillOfEntryUpdateDetailView(UpdateView):
    template_name = 'bill_of_entry/add.html'
    model = bill_of_entry.BillOfEntryModel
    form_class = forms.BillOfEntryForm

    def get_object(self, queryset=None):
        object = self.model.objects.get(bill_of_entry_number=self.kwargs.get('boe'))
        return object

    def get_success_url(self):
        boe = self.kwargs.get('boe')
        return reverse('bill-of-entry-ajax-list') + '?bill_of_entry_number=' + str(boe)


class BillOfEntryUpdateView(UpdateWithInlinesView):
    template_name = 'bill_of_entry/add.html'
    model = bill_of_entry.BillOfEntryModel
    fields = ()
    inlines = [BillOfEntryLicenseImportItemInline, ]

    def get_success_url(self):
        boe = self.kwargs.get('boe')
        return reverse('bill-of-entry-ajax-list') + '?bill_of_entry_number=' + str(boe)

    def dispatch(self, request, *args, **kwargs):
        # check if there is some video onsite
        license = self.get_object()
        return super(BillOfEntryUpdateView, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        object = self.model.objects.get(bill_of_entry_number=self.kwargs.get('boe'))
        return object

    def get_inlines(self):
        allotments = self.object.allotment.all()
        for allotment in allotments:
            if allotment.allotment_details.all().exists():
                for allotment_item in allotment.allotment_details.all():
                    if not RowDetails.objects.filter(bill_of_entry=self.object,
                                                     sr_number=allotment_item.item).exists():
                        row, bool = RowDetails.objects.get_or_create(bill_of_entry=self.object,
                                                                     sr_number=allotment_item.item)
                        if not row.cif_inr or row.cif_inr == 0:
                            row.cif_inr = allotment_item.cif_inr
                        if not row.cif_fc or row.cif_fc == 0:
                            row.cif_fc = allotment_item.cif_fc
                        if not row.cif_inr or row.qty == 0:
                            row.qty = allotment_item.qty
                        row.save()
                    allotment_item.is_boe = True
                    allotment_item.save()
        self.inlines = [BillOfEntryLicenseImportItemInline, ]
        return super(BillOfEntryUpdateView, self).get_inlines()


# Create your views here.

class BillOfEntryFetchView(FormView):
    template_name = 'bill_of_entry/fetch.html'
    form_class = forms.BillOfEntryCaptcha

    def get_context_data(self, **kwargs):
        context = super(BillOfEntryFetchView, self).get_context_data(**kwargs)
        from bill_of_entry.scripts.boe import fetch_cookies
        cookies, csrftoken = fetch_cookies()
        from bill_of_entry.scripts.boe import fetch_captcha
        context['captcha_url'] = fetch_captcha(cookies)
        import json
        context['fetch_cookies'] = json.dumps(cookies)
        context['csrftoken'] = csrftoken
        data = self.kwargs.get('data')
        from bill_of_entry.models import BillOfEntryModel
        context['remain_count'] = BillOfEntryModel.objects.filter(
            Q(is_fetch=False) | Q(appraisement=None) | Q(ooc_date=None) | Q(ooc_date='N.A.')).exclude(
            failed__gte=5).count()
        context['remain_captcha'] = context['remain_count'] / 3
        return context

    def post(self, request, *args, **kwargs):
        captcha = self.request.POST.get('captcha')
        import json
        cookies = json.loads(self.request.POST.get('cookies'))
        csrftoken = self.request.POST.get('csrftoken')
        status = True
        from bill_of_entry.models import BillOfEntryModel
        data_list = BillOfEntryModel.objects.filter(
            Q(is_fetch=False) | Q(appraisement=None) | Q(ooc_date=None) | Q(ooc_date='N.A.')).exclude(
            failed__gte=5).order_by(
            'bill_of_entry_date')
        for data in data_list:
            from bill_of_entry.scripts.utils import port_dict
            status = fetch_data_to_model.delay(cookies, csrftoken, port_dict, kwargs, captcha, data.pk)
        return HttpResponseRedirect(reverse('bill-of-entry-list'))


class BillOfEntryDeleteView(DeleteView):
    template_name = 'allotment/delete.html'
    model = bill_of_entry.BillOfEntryModel
    success_url = reverse_lazy('bill-of-entry-list')

    def get_object(self, queryset=None):
        object = self.model.objects.get(bill_of_entry_number=self.kwargs.get('boe'))
        return object


class DownloadPendingBillView(PDFTemplateResponseMixin, FilterView):
    table_class = tables.BillOfEntryTable
    filterset_class = filters.BillOfEntryFilter
    paginate_by = 500
    template_name = 'bill_of_entry/download.html'
    model = bill_of_entry.BillOfEntryModel

    def get_queryset(self):
        qs = self.model.objects.all()
        return qs.order_by('company', 'product_name', 'bill_of_entry_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total = 0
        total_list = [total + int(data.get_total_inr) for data in self.get_queryset()]
        context['total_cif'] = sum(total_list)
        import datetime
        context['today'] = datetime.datetime.now().date
        return context


class GenerateTransferLetterView(FormView):
    template_name = 'allotment/generate.html'
    model = bill_of_entry.BillOfEntryModel
    form_class = TlForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['type'] = True
        context['object'] = self.get_object()
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_object(self):
        return self.model.objects.get(bill_of_entry_number=self.kwargs.get('boe'))

    def get_initial(self):
        initial = super().get_initial()
        initial['company'] = str(self.get_object().company)
        initial['company_address_line1'] = str(self.get_object().company.address_line_1)
        initial['company_address_line2'] = str(self.get_object().company.address_line_2)
        return initial

    def post(self, request, *args, **kwargs):
        from shutil import make_archive
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)
        else:
            try:
                boe_id = self.kwargs.get('boe')
                boe = bill_of_entry.BillOfEntryModel.objects.get(bill_of_entry_number=boe_id)
                from datetime import datetime
                data = [{
                    'company': self.request.POST.get('company'),
                    'company_address_1': self.request.POST.get('company_address_line1'),
                    'company_address_2': self.request.POST.get('company_address_line2'),
                    'today': str(datetime.now().date()),
                    'license': item.sr_number.license.license_number,
                    'license_date': item.sr_number.license_date.strftime("%d/%m/%Y"),
                    'file_number': item.sr_number.license.file_number, 'quantity': item.qty,
                    'v_allotment_inr': round(item.cif_inr, 2),
                    'exporter_name': item.sr_number.license.exporter.name,
                    'v_allotment_usd': item.cif_fc} for item in
                    boe.item_details.all()]
                tl = self.request.POST.get('tl_choice')
                from core.models import TransferLetterModel
                transfer_letter = TransferLetterModel.objects.get(pk=tl)
                tl_path = transfer_letter.tl.path
                file_path = 'media/TL_' + str(boe_id) + '_' + transfer_letter.name.replace(' ', '_') + '/'
                from allotment.scripts.aro import generate_tl_software
                generate_tl_software(data=data, tl_path=tl_path, path=file_path)
                file_name = 'TL_' + str(boe_id) + '_' + transfer_letter.name.replace(' ', '_') + '.zip'
                path_to_zip = make_archive(file_path, "zip", file_path)
                zip_file = open(path_to_zip, 'rb')
                response = HttpResponse(zip_file, content_type='application/force-download')
                response['Content-Disposition'] = 'attachment; filename="%s"' % file_name
                url = request.headers.get('origin') + path_to_zip.split('lmanagement')[-1]
                return JsonResponse({'url': url, 'message': 'Success'})
            except Exception as e:
                print(e)
                return self.form_invalid(form)
