# Create your views here.
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import DetailView, FormView
from extra_views import CreateWithInlinesView, UpdateWithInlinesView, InlineFormSetFactory

from bill_of_entry.models import RowDetails
from bill_of_entry.scripts.boe import fetch_data_to_model
from core.utils import PagedFilteredTableView
from . import forms, tables, filters
from . import models as bill_of_entry


class BillOfEntryView(PagedFilteredTableView):
    template_name = 'core/list.html'
    model = bill_of_entry.BillOfEntryModel
    table_class = tables.BillOfEntryTable
    filter_class = filters.BillOfEntryFilter
    page_head = 'Item List'


class BillOfEntryCreateView(CreateWithInlinesView):
    template_name = 'core/add.html'
    model = bill_of_entry.BillOfEntryModel
    form_class = forms.BillOfEntryForm
    inlines = []

    # def form_valid(self, form):
    #     if not form.instance.created_by:
    #         form.instance.created_by = self.request.user
    #         form.instance.created_on = datetime.datetime.now()
    #     form.instance.modified_by = self.request.user
    #     form.instance.modified_on = datetime.datetime.now()
    #     return super().form_valid(form)


class BillOfEntryDetailView(DetailView):
    template_name = 'bill_of_entry/detail.html'
    model = bill_of_entry.BillOfEntryModel


class BillOfEntryLicenseImportItemInline(InlineFormSetFactory):
    model = bill_of_entry.RowDetails
    form_class = forms.ImportItemsForm
    factory_kwargs = {
        'extra': 0,
    }


class BillOfEntryUpdateView(UpdateWithInlinesView):
    template_name = 'core/add.html'
    model = bill_of_entry.BillOfEntryModel
    form_class = forms.BillOfEntryForm
    inlines = [BillOfEntryLicenseImportItemInline,]

    def dispatch(self, request, *args, **kwargs):
        # check if there is some video onsite
        license = self.get_object()
        return super(BillOfEntryUpdateView, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        object = self.model.objects.get(id=self.kwargs.get('pk'))
        return object

    def get_inlines(self):
        allotment = self.object.allotment
        if allotment:
            if allotment.allotment_details.all().exists():
                for allotment_item in allotment.allotment_details.all():
                    row, bool = RowDetails.objects.get_or_create(bill_of_entry=self.object,sr_number=allotment_item.item)
                    row.cif_inr = allotment_item.cif_inr
                    row.cif_fc = allotment_item.cif_fc
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
        context['remain_count'] = bill_of_entry.BillOfEntryModel.objects.filter(is_fetch=False).order_by('bill_of_entry_date', 'id').count()
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
            return HttpResponseRedirect(reverse('bill_of_entry'))
        else:
            return HttpResponseRedirect(reverse('bill_of_entry'))


