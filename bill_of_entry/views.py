from django.db.models import Sum
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
# Create your views here.
from django.template.loader import get_template
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from easy_pdf.rendering import render_to_pdf
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import CreateWithInlinesView, UpdateWithInlinesView, InlineFormSetFactory

from bill_of_entry.models import RowDetails
from core.utils import PagedFilteredTableView
from license import models as license_models
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
