from django.db.models import Sum
from django.http import JsonResponse, HttpResponse
# Create your views here.
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django_filters.views import FilterView
from easy_pdf.rendering import render_to_pdf
from easy_pdf.views import PDFTemplateResponseMixin

from core.utils import PagedFilteredTableView
from license import models as license_models
from . import forms, tables, filters
from . import models as allotments


class AllotmentView(FilterView):
    template_name = 'allotment/list.html'
    model = allotments.AllotmentModel
    filter_class = filters.AllotmentFilter
    page_head = 'Item List'

    def get_queryset(self):
        qs = self.model.objects.all()
        pk = self.request.GET.get('pk',None)
        if not pk:
            product_filtered_list = self.filter_class(self.request.GET, queryset=qs)
            return product_filtered_list.qs
        else:
            return self.model.objects.filter(id=self.request.GET.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.filter_class(self.request.GET)
        return context


class AllotmentCreateView(CreateView):
    template_name = 'allotment/add.html'
    model = allotments.AllotmentModel
    form_class = forms.AllotmentForm


class AllotmentUpdateView(UpdateView):
    template_name = 'allotment/add.html'
    model = allotments.AllotmentModel
    form_class = forms.AllotmentForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['allotment_object'] = allotments.AllotmentModel.objects.get(id=self.kwargs.get('pk'))
        return context


class AllotmentDeleteView(DeleteView):
    template_name = 'allotment/delete.html'
    model = allotments.AllotmentModel
    form_class = forms.AllotmentForm

    def get_success_url(self):
        return reverse('allotment-list') + '?type=AT&company=&is_be=false'


class StartAllotmentView(PagedFilteredTableView):
    template_name = 'allotment/item.html'
    model = license_models.LicenseImportItemsModel
    table_class = tables.AllotmentItemsTable
    filter_class = filters.AllotmentItemFilter
    page_head = 'Item List'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['allotment_object'] = allotments.AllotmentModel.objects.get(id=self.kwargs.get('pk'))
        return context


def allotment_data(request, pk):
    row_id = request.POST.get('row')
    allotment_id = request.POST.get('allotment')
    requested_allotment_quantity = float(request.POST.get('allotment_quantity', 0))
    requested_allotment_value = float(request.POST.get('allotment_value', 0))
    allotment = allotments.AllotmentModel.objects.get(id=allotment_id)
    if not requested_allotment_quantity == 0:
        requested_allotment_value = allotment.unit_value_per_unit * requested_allotment_quantity
    elif not requested_allotment_value == 0:
        requested_allotment_quantity = requested_allotment_value / allotment.unit_value_per_unit
    row = license_models.LicenseImportItemsModel.objects.get(id=row_id)
    row_balance_quantity = row.balance_quantity
    row_balance_cif_fc = row.balance_cif_fc
    try:
        allotment_item = allotments.AllotmentItems.objects.get(item=row, allotment=allotment)
        alloted_item_qty = allotment_item.qty
        alloted_item_cif_fc = allotment_item.cif_fc
        row_balance_quantity = row_balance_quantity + allotment_item.qty
        row_balance_cif_fc = row_balance_cif_fc + allotment_item.cif_fc
    except Exception as e:
        alloted_item_qty = 0
        alloted_item_cif_fc = 0
    previous_allotment_quantity = allotment.allotment_details.aggregate(Sum('qty'))['qty__sum']
    previous_allotment_cif_fc = allotment.allotment_details.aggregate(Sum('cif_fc'))['cif_fc__sum']
    if not previous_allotment_quantity:
        previous_allotment_quantity = 0
    if not previous_allotment_cif_fc:
        previous_allotment_cif_fc = 0
    previous_allotment_quantity = previous_allotment_quantity - alloted_item_qty
    previous_allotment_cif_fc = previous_allotment_cif_fc - alloted_item_cif_fc
    new_allotment_quantity = previous_allotment_quantity + requested_allotment_quantity
    new_allotment_cif_fc = previous_allotment_cif_fc + requested_allotment_value
    if round(allotment.required_value + 3, 2) < round(new_allotment_cif_fc, 2) or round(allotment.required_quantity,
                                                                                        2) < round(
        new_allotment_quantity, 2):
        return JsonResponse({'message': 'Please Reduce Allotment Exceed Required',
                             'status': False}, safe=False)
    if row_balance_quantity >= requested_allotment_quantity and row_balance_cif_fc >= requested_allotment_value:
        allotment_item, bool = allotments.AllotmentItems.objects.get_or_create(item=row, allotment=allotment)
        allotment_item.qty = int(requested_allotment_quantity)
        allotment_item.cif_fc = round(requested_allotment_quantity * allotment.unit_value_per_unit, 2)
        allotment_item.save()
        alloted_quantity = allotment.allotment_details.aggregate(Sum('qty'))['qty__sum']
        balance_quantity = allotment.required_quantity - alloted_quantity
        ind_balance_quantity = license_models.LicenseImportItemsModel.objects.get(id=row_id).balance_quantity
        ind_balance_value = license_models.LicenseImportItemsModel.objects.get(id=row_id).balance_cif_fc
        return JsonResponse({
            'allotment_quantity': round(allotment_item.qty, 2),
            'allotment_value': round(allotment_item.cif_fc, 2),
            'alloted_quantity': round(alloted_quantity, 2),
            'balance_quantity': round(balance_quantity, 2),
            'ind_balance_quantity': round(ind_balance_quantity, 2),
            'ind_balance_value': round(ind_balance_value, 2),
            'message': 'Allotment Done Sucessfully',
            'status': True}, safe=False)
    else:
        return JsonResponse({'message': 'Insufficient Value or Quantity',
                             'status': False}, safe=False)


class AllotmentVerifyView(PagedFilteredTableView):
    template_name = 'allotment/verify.html'
    model = allotments.AllotmentItems
    table_class = tables.AllotedItemsTable
    page_head = 'Item List'

    def get_queryset(self, **kwargs):
        return self.model.objects.filter(allotment=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['allotment_object'] = allotments.AllotmentModel.objects.get(id=self.kwargs.get('pk'))
        return context


class AllotmentDeleteItemsView(DeleteView):
    model = allotments.AllotmentItems
    template_name = 'allotment/delete.html'

    def get_success_url(self):
        return reverse('allotment-list') + '?pk=' + str(self.request.GET.get('allotment'))


class SendAllotmentView(PDFTemplateResponseMixin, DetailView):
    model = allotments.AllotmentModel
    template_name = 'allotment/send.html'

    def get(self, request, *args, **kwargs):
        object = self.get_object()
        context = {
            "object": self.get_object()
        }
        pdf = render_to_pdf('allotment/send.html', context)
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            filename = "Allotment_%s.pdf" % (str(object.id))
            content = "inline; filename='%s'" % (filename)
            download = request.GET.get("download")
            if download:
                content = "attachment; filename='%s'" % (filename)
            response['Content-Disposition'] = content
            return response
        return HttpResponse("Not found")
