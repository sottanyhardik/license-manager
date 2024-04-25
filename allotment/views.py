import pandas as pd
from django.db.models import Sum, F
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.generic import DetailView, CreateView, UpdateView, FormView
from django.views.generic.base import TemplateResponseMixin, ContextMixin, View
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
    ordering = ['modified_on']

    def get_queryset(self):
        qs = self.model.objects.all()
        pk = self.request.GET.get('pk', None)
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

    def get_success_url(self):
        return reverse('allotment-card', kwargs={'pk': self.object.pk})


class AllotmentUpdateView(UpdateView):
    template_name = 'allotment/add.html'
    model = allotments.AllotmentModel
    form_class = forms.AllotmentForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['allotment_object'] = allotments.AllotmentModel.objects.get(id=self.kwargs.get('pk'))
        return context

    def get_success_url(self):
        return reverse('allotment-details', kwargs={
            'pk': self.object.pk}) + '?item__name=' + self.object.item_name + "&remove_expired=false&remove_null=true&sort=license_expiry"


class AllotmentDeleteView(TemplateResponseMixin, ContextMixin, View):
    template_name = 'allotment/delete.html'
    model = allotments.AllotmentModel

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['type'] = True
        context['object'] = self.get_object()
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_object(self):
        return self.model.objects.get(id=self.kwargs.get('pk'))

    def post(self, request, *args, **kwargs):
        success_url = reverse('allotment-list')
        self.get_object().delete()
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(success_url)


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


class AllotmentVerifyView(DetailView):
    template_name = 'allotment/verify.html'
    model = allotments.AllotmentModel
    page_head = 'Item List'

    def get_object(self, queryset=None):
        return self.model.objects.get(pk=self.kwargs.get('pk'))


class AllotmentDeleteItemsView(TemplateResponseMixin, ContextMixin, View):
    model = allotments.AllotmentItems
    template_name = 'allotment/delete.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_object(self):
        return self.model.objects.get(id=self.kwargs.get('pk'))

    def post(self, request, *args, **kwargs):
        success_url = reverse('allotment-verify', kwargs={'pk': str(self.get_object().allotment_id)})
        self.get_object().delete()
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = self.get_object()
        return context


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
            content = "inline; filename=%s" % (filename)
            download = request.GET.get("download")
            if download:
                content = "attachment; filename=%s" % (filename)
            response['Content-Disposition'] = content
            return response
        return HttpResponse("Not found")


class CardView(DetailView):
    template_name = 'allotment/card.html'
    model = allotments.AllotmentModel

    def get_object(self, queryset=None):
        return self.model.objects.get(pk=self.kwargs.get('pk'))


class DownloadPendingAllotmentView(PDFTemplateResponseMixin, FilterView):
    template_name = 'allotment/download.html'
    model = allotments.AllotmentModel
    filter_class = filters.AllotmentFilter

    def get_queryset(self):
        product_filtered_list = self.filter_class(self.request.GET, queryset=self.model.objects.all())
        return product_filtered_list.qs.order_by('company', 'item_name', 'estimated_arrival_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total = 0
        total_list = [total + int(data.required_value) for data in self.get_queryset()]
        queryset = self.get_queryset().values('item_name').order_by('item_name').annotate(
            total_qty=Sum('required_quantity'), value=Sum(F('required_quantity') * F('unit_value_per_unit'))).distinct()
        context['queryset'] = queryset
        context['total_cif'] = sum(total_list)
        if self.request.GET.get('is_alloted') == 'true':
            context['is_alloted'] = True
        else:
            context['is_alloted'] = False
        import datetime
        context['today'] = datetime.datetime.now().date
        return context


class ARODocumentGenerateView(FormView):
    template_name = 'allotment/generate.html'
    model = allotments.AllotmentModel
    form_class = forms.AROForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['type'] = True
        context['object'] = self.get_object()
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_object(self):
        return self.model.objects.get(id=self.kwargs.get('pk'))

    def post(self, request, *args, **kwargs):
        from shutil import make_archive
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)
        else:
            try:
                allotment_id = self.kwargs.get('pk')
                allotment = allotments.AllotmentModel.objects.get(id=allotment_id)
                from datetime import datetime
                data = [{'dgft_address': self.request.POST.get('dgft_address'),
                         'mill_name': self.request.POST.get('mill_name'),
                         'company': self.request.POST.get('company'),
                         'company_address': self.request.POST.get('company_address'),
                         'mill_address': self.request.POST.get('mill_address'),
                         'from_company': self.request.POST.get('from_company'),
                         'today': str(datetime.now().date()),
                         'item': 'CARDAMOM',
                         'hs_code': '09083100',
                         'license': item.license_number, 'license_date': item.license_date,
                         'file_number': item.file_number, 'quantity': item.qty,
                         'v_allotment_inr': round(item.cif_fc * 83.90, 2), 'v_allotment_usd': item.cif_fc,
                         'sr_no': item.serial_number} for item in
                        allotment.allotment_details.all()]
                file_path = 'media/ARO_ALLOTMENT_' + str(allotment_id) + '/'
                from allotment.scripts.aro import generate_documents
                generate_documents(data=data, path=file_path)
                file_name = 'ARO_ALLOTMENT_' + str(allotment_id) + '.zip'
                path_to_zip = make_archive(file_path, "zip", file_path)
                zip_file = open(path_to_zip, 'rb')
                response = HttpResponse(zip_file, content_type='application/force-download')
                response['Content-Disposition'] = 'attachment; filename="%s"' % file_name
                url = request.headers.get('origin') + path_to_zip.split('lmanagement')[-1]
                return JsonResponse({'url': url, 'message': 'Success'})
            except Exception as e:
                print(e)
                return self.form_invalid(form)


class GenerateTransferLetterView(FormView):
    template_name = 'allotment/generate.html'
    model = allotments.AllotmentModel
    form_class = forms.TlForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['type'] = True
        context['object'] = self.get_object()
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_initial(self):
        initial = super().get_initial()
        initial['company'] = str(self.get_object().company)
        initial['company_address_line1'] = str(self.get_object().company.address_line_1)
        initial['company_address_line2'] = str(self.get_object().company.address_line_2)
        return initial

    def get_object(self):
        return self.model.objects.get(id=self.kwargs.get('pk'))

    def post(self, request, *args, **kwargs):
        from shutil import make_archive
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)
        else:
            try:
                allotment_id = self.kwargs.get('pk')
                allotment = allotments.AllotmentModel.objects.get(id=allotment_id)
                from datetime import datetime
                data = [{
                    'company': self.request.POST.get('company'),
                    'company_address_1': self.request.POST.get('company_address_line1'),
                    'company_address_2': self.request.POST.get('company_address_line2'),
                    'today': str(datetime.now().date()),
                    'license': item.license_number, 'license_date': item.license_date.strftime("%d/%m/%Y"),
                    'file_number': item.file_number, 'quantity': item.qty,
                    'v_allotment_inr': round(item.cif_fc * 84.25, 2),
                    'exporter_name': item.exporter.name,
                    'v_allotment_usd': item.cif_fc} for item in
                    allotment.allotment_details.all()]
                tl = self.request.POST.get('tl_choice')
                from core.models import TransferLetterModel
                transfer_letter = TransferLetterModel.objects.get(pk=tl)
                tl_path = transfer_letter.tl.path
                file_path = 'media/TL_' + str(allotment_id) + '_' + transfer_letter.name.replace(' ', '_') + '/'
                from allotment.scripts.aro import generate_tl_software
                generate_tl_software(data=data, tl_path=tl_path, path=file_path,
                                     transfer_letter_name=transfer_letter.name.replace(' ', '_'))
                file_name = 'TL_' + str(allotment_id) + '_' + transfer_letter.name.replace(' ', '_') + '.zip'
                path_to_zip = make_archive(file_path, "zip", file_path)
                zip_file = open(path_to_zip, 'rb')
                response = HttpResponse(zip_file, content_type='application/force-download')
                response['Content-Disposition'] = 'attachment; filename="%s"' % file_name
                url = request.headers.get('origin') + path_to_zip.split('lmanagement')[-1]
                return JsonResponse({'url': url, 'message': 'Success'})
            except Exception as e:
                print(e)
                return self.form_invalid(form)


class PandasDownloadPendingAllotmentView(PDFTemplateResponseMixin, FilterView):
    template_name = 'allotment/download.html'
    model = allotments.AllotmentModel
    filter_class = filters.AllotmentFilter

    def get_queryset(self):
        qs = self.model.objects.all()
        product_filtered_list = self.filter_class(self.request.GET, queryset=qs)
        return product_filtered_list.qs.order_by('company', 'item_name', 'estimated_arrival_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total = 0
        total_list = [total + int(data.required_value) for data in self.get_queryset()]
        queryset = self.get_queryset().values('item_name').order_by('item_name').annotate(
            total_qty=Sum('required_quantity'), value=Sum(F('required_quantity') * F('unit_value_per_unit'))).distinct()
        context['queryset'] = queryset
        context['total_cif'] = sum(total_list)
        import datetime
        context['today'] = datetime.datetime.now().date
        df = pd.DataFrame(list(
            self.get_queryset().values('modified_on', 'port__code', 'required_quantity', 'unit_value_per_unit',
                                       'item_name', 'invoice', 'bl_detail', 'estimated_arrival_date')))
        df = df.assign(required_value=round(df['required_quantity'] * df['unit_value_per_unit'], 2))
        context['df'] = df.groupby(['item_name']).agg(
            {'required_quantity': 'sum', 'unit_value_per_unit': 'mean', 'required_value': 'sum'}).to_html(
            classes='table')
        return context
