# Create your views here.
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, DeleteView, UpdateView, CreateView
from django_filters.views import FilterView
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import CreateWithInlinesView, UpdateWithInlinesView, InlineFormSetFactory

from bill_of_entry.models import RowDetails
from bill_of_entry.scripts.boe import fetch_data_to_model
from core.utils import PagedFilteredTableView
from . import forms, tables, filters
from . import models as bill_of_entry


class BillOfEntryView(FilterView):
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


class BillOfEntryUpdateView(UpdateWithInlinesView):
    template_name = 'bill_of_entry/add.html'
    model = bill_of_entry.BillOfEntryModel
    fields = ()
    inlines = [BillOfEntryLicenseImportItemInline, ]

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
        context['remain_count'] = bill_of_entry.BillOfEntryModel.objects.filter(is_fetch=False).order_by(
            'bill_of_entry_date', 'id').count()
        context['remain_captcha'] = context['remain_count'] / 3
        return context

    def post(self, request, *args, **kwargs):
        captcha = self.request.POST.get('captcha')
        import json
        cookies = json.loads(self.request.POST.get('cookies'))
        csrftoken = self.request.POST.get('csrftoken')
        status = True
        while status:
            from bill_of_entry.scripts.utils import port_dict
            status = fetch_data_to_model(cookies, csrftoken, port_dict, kwargs, captcha)
        if bill_of_entry.BillOfEntryModel.objects.filter(is_fetch=False).exclude(failed=5).exists():
            return HttpResponseRedirect(reverse('bill-of-entry-list'))
        else:
            return HttpResponseRedirect(reverse('bill-of-entry-list'))


class BillOfEntryDeleteView(DeleteView):
    template_name = 'allotment/delete.html'
    model = bill_of_entry.BillOfEntryModel
    success_url = reverse_lazy('bill-of-entry-list')

    def get_object(self, queryset=None):
        object = self.model.objects.get(bill_of_entry_number=self.kwargs.get('boe'))
        return object


class DownloadPendingBillView(PDFTemplateResponseMixin, FilterView):
    template_name = 'bill_of_entry/download.html'
    model = bill_of_entry.BillOfEntryModel
    filter_class = filters.BillOfEntryFilter

    def get_queryset(self):
        qs = self.model.objects.all()
        product_filtered_list = self.filter_class(self.request.GET, queryset=qs)
        return product_filtered_list.qs.order_by('company','bill_of_entry_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total = 0
        total_list = [total + int(data.get_total_inr) for data in self.get_queryset()]
        context['total_cif'] = sum(total_list)
        import datetime
        context['today'] = datetime.datetime.now().date
        return context
