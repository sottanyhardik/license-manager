# # Create your views here.
# import csv
# import io
#
# from django.contrib import messages
# from django.http import HttpResponse
# from django.http import HttpResponseRedirect
# from django.shortcuts import redirect
# from django.urls import reverse
# from django.views import View
# from django.views.generic import TemplateView, CreateView, UpdateView, DetailView
# from extra_views import UpdateWithInlinesView, InlineFormSetFactory
# from tablib import Dataset
#
# from core.scripts.sion import fetch_sion_data
# from core.utils import PagedFilteredTableView, safe_parse_date
# from . import models, tables, filters, forms
# from .models import MEISMODEL
# from .scripts.ledger import create_object
#
#
# class DashboardView(TemplateView):
#     template_name = 'blank.html'
#
#     def get_context_data(self, **kwargs):
#         context = super(DashboardView, self).get_context_data(**kwargs)
#         context['page_title'] = "Dashboard"
#         return context
#
#
# class CreateCompanyView(CreateView):
#     model = models.CompanyModel
#     template_name = 'core/add.html'
#     fields = "__all__"
#
#
# class UpdateCompanyView(UpdateView):
#     model = models.CompanyModel
#     template_name = 'core/add.html'
#     fields = "__all__"
#
#
# class ListCompanyView(PagedFilteredTableView):
#     template_name = 'core/list.html'
#     model = models.CompanyModel
#     table_class = tables.CompanyClassTable
#     filter_class = filters.CompanyFilter
#
#
# class SIONExportInline(InlineFormSetFactory):
#     model = models.SIONExportModel
#     form_class = forms.SIONExportForm
#     factory_kwargs = {
#         'extra': 0,
#         'max_num': 1
#     }
#
#
# class SIONImportInline(InlineFormSetFactory):
#     model = models.SIONImportModel
#     form_class = forms.SIONImportForm
#     factory_kwargs = {
#         'extra': 0,
#     }
#
#
# class ListSionView(PagedFilteredTableView):
#     template_name = 'core/list.html'
#     model = models.SionNormClassModel
#     table_class = tables.SionNormClassTable
#     filter_class = filters.SionNormClassFilter
#
#
# class SionDetailView(DetailView):
#     model = models.SionNormClassModel
#     template_name = 'sion/detail.html'
#     context_object_name = 'sion_norm'
#
#     def get_object(self, queryset=None):
#         return self.model.objects.get(id=self.kwargs.get('pk'))
#
#
# class UpdateSionView(UpdateWithInlinesView):
#     template_name = 'core/add.html'
#     model = models.SionNormClassModel
#     form_class = forms.SionNormClassForm
#     inlines = [SIONExportInline, SIONImportInline]
#
#     def get_object(self, queryset=None):
#         object = self.model.objects.get(id=self.kwargs.get('pk'))
#         fetch_sion_data(object)
#         return object
#
#
#
# class CreateHSNCodeView(CreateView):
#     model = models.HSCodeModel
#     template_name = 'core/add.html'
#     fields = "__all__"
#
#
# class ListHSNView(PagedFilteredTableView):
#     template_name = 'core/list.html'
#     model = models.HSCodeModel
#     table_class = tables.HSCodeTable
#     filter_class = filters.HSNCodeFilter
#
#
# class CreateItemView(CreateView):
#     model = models.ItemNameModel
#     template_name = 'core/add.html'
#     fields = "__all__"
#
#
# class ListItemView(PagedFilteredTableView):
#     template_name = 'core/list.html'
#     model = models.ItemNameModel
#     table_class = tables.ItemNameTable
#     filter_class = filters.ItemFilter
#
#
# class UpdateItemView(UpdateView):
#     model = models.ItemNameModel
#     template_name = 'core/add.html'
#     fields = "__all__"
#
#
# class UpdateHSNCodeView(UpdateView):
#     model = models.HSCodeModel
#     template_name = 'core/add.html'
#     fields = "__all__"
#
#     def get_success_url(self):
#         from django.urls import reverse
#         return reverse('hs-code-update', kwargs={'pk': self.object.pk})
#
#
# class LedgerSuccess(TemplateView):
#     template_name = 'core/message.html'
#
#
# class UploadLedger(TemplateView):
#     template_name = 'core/ledger.html'
#
#     def get_context_data(self, **kwargs):
#         context = super(UploadLedger, self).get_context_data(**kwargs)
#         return context
#
#     def post(self, request, **kwargs):
#         files = request.FILES.getlist('ledger')
#
#         for file_sequence_number, uploaded_file in enumerate(files, start=1):
#             try:
#                 # Decode the uploaded file and wrap it for csv.reader
#                 decoded_file = uploaded_file.read().decode('utf-8-sig')
#                 decoded_file = decoded_file.replace(': ', '')
#                 decoded_file = decoded_file.replace(' ', '')
#                 csvfile = io.StringIO(decoded_file)
#
#                 reader = csv.reader(csvfile)
#
#                 rows = []
#                 for row in reader:
#                     if not any(field.strip() for field in row):
#                         continue
#                     rows.append(row)
#
#                 from scripts.parse_ledger import parse_license_data
#                 dict_list = parse_license_data(rows)
#
#                 for dict_data in dict_list:
#                     create_object(dict_data)
#                     messages.success(request, f"✅ Created DFIA: {dict_data.get('lic_no', 'Unknown')}")
#
#                 messages.success(
#                     request,
#                     f"✅ File {uploaded_file.name} processed: {len(dict_list)} licenses created."
#                 )
#
#             except Exception as e:
#                 messages.error(request, f"❌ Error processing file {uploaded_file.name}: {str(e)}")
#
#         return HttpResponseRedirect(reverse('ledger-complete'))
#
#
# class TemplateListView(TemplateView):
#     template_name = 'base.html'
#
#
# class MEISTLVIEW(TemplateView):
#     template_name = 'core/list.html'
#     model = models.MEISMODEL
#
#
# class UploadMEISView(TemplateView):
#     template_name = 'upload.html'
#
#     def post(self, request, *args, **kwargs):
#         dataset = Dataset()
#         new_orders = self.request.FILES['myfile']
#         imported_data = dataset.load(new_orders.read())
#         models.MEISMODEL.objects.all().delete()
#         for data in imported_data.dict:
#             meis = models.MEISMODEL()
#             meis.importer = data['Importer']
#             meis.exporter = data['Exporter']
#             dfia = str(data['DFIA']).split('.')[0]
#             if len(dfia) == 9:
#                 meis.dfia_no = '0' + dfia
#             else:
#                 meis.dfia_no = dfia
#             meis.dfia_date = data['DFIA_DT']
#             meis.cif_inr = data['CIF_INR']
#             meis.file_number = data['FILE_NUMBER']
#             meis.save()
#         return redirect("meis-upload")
#
#     def get_context_data(self, **kwargs):
#         context = super(UploadMEISView, self).get_context_data(**kwargs)
#         context['page_title'] = 'Upload Order List'
#         context['object_list'] = MEISMODEL.objects.all()
#         return context
#
#
# class GenerateTransferLetterMEISView(View):
#
#     def get(self, request, *args, **kwargs):
#         from shutil import make_archive
#         from datetime import datetime
#         meis_list = models.MEISMODEL.objects.all()
#         data = [{
#             'id': item.id,
#             'company': item.importer,
#             'today': str(datetime.now().date()),
#             'license': item.dfia_no,
#             'license_date': item.dfia_date,
#             'file_number': item.file_no,
#             'v_allotment_inr': item.cif_inr,
#             'exporter_name': item.exporter} for item in
#             meis_list]
#         from core.models import TransferLetterModel
#         value = self.request.GET.get('type')
#         if value == 'empty':
#             transfer_letter = TransferLetterModel.objects.get(name='GE EMPTY MEIS')
#         else:
#             transfer_letter = TransferLetterModel.objects.get(name='GE FILLED MEIS')
#         tl_path = transfer_letter.tl.path
#         file_path = 'media/TL_' + 'meis' + '_' + transfer_letter.name.replace(' ', '_') + '/'
#         transfer_letter_name = transfer_letter.name.replace(' ', '_')
#         from allotment.scripts.aro import generate_tl_software
#         generate_tl_software(data=data, tl_path=tl_path, path=file_path, transfer_letter_name=transfer_letter_name)
#         file_name = 'TL_' + 'meis' + '_' + 'GE' + '.zip'
#         path_to_zip = make_archive(file_path, "zip", file_path)
#         zip_file = open(path_to_zip, 'rb')
#         response = HttpResponse(zip_file, content_type='application/force-download')
#         response['Content-Disposition'] = 'attachment; filename="%s"' % file_name
#         return response
#
#
# from django.views.decorators.csrf import csrf_exempt
# from django.http import JsonResponse
# from django.utils.dateparse import parse_datetime
# from license.models import LicenseDetailsModel, LicenseTransferModel
# from core.models import CompanyModel
# import json
#
#
# @csrf_exempt
# def save_license_transfer(request):
#     if request.method == "POST":
#         try:
#             data = json.loads(request.body)
#
#             license_number = data["license_number"]
#             license_date = data["license_date"]
#             exporter_iec = data["exporter_iec"]
#
#             # Find the license
#             dfia = LicenseDetailsModel.objects.get(
#                 license_number=license_number, license_date=license_date, exporter__iec=exporter_iec
#             )
#
#             # Handle current owner
#             owner_data = data.get("current_owner")
#             if owner_data:
#                 current_owner, _ = CompanyModel.objects.update_or_create(
#                     iec=owner_data["iec"],
#                     defaults={"name": owner_data.get("name")}
#                 )
#                 dfia.current_owner = current_owner
#                 dfia.save()
#
#             # Handle transfers
#             for transfer in data.get("transfers", []):
#                 from_company, _ = CompanyModel.objects.update_or_create(
#                     iec=transfer["from_iec"],
#                     defaults={"name": transfer.get("from_iec_entity_name")}
#                 )
#                 to_company, _ = CompanyModel.objects.update_or_create(
#                     iec=transfer["to_iec"],
#                     defaults={"name": transfer.get("to_iec_entity_name")}
#                 )
#
#                 LicenseTransferModel.objects.update_or_create(
#                     license=dfia,
#                     from_company=from_company,
#                     to_company=to_company,
#                     transfer_initiation_date=parse_datetime(transfer["transfer_initiation_date"]),
#                     defaults={
#                         "transfer_status": transfer.get("transfer_status"),
#                         "transfer_date": safe_parse_date(transfer.get("transfer_date")),
#                         "transfer_acceptance_date": parse_datetime(
#                             transfer.get("transfer_acceptance_date")) if transfer.get(
#                             "transfer_acceptance_date") else None,
#                         "cbic_status": transfer.get("cbic_status"),
#                         "cbic_response_date": parse_datetime(transfer.get("cbic_response_date")) if transfer.get(
#                             "cbic_response_date") else None,
#                         "user_id_transfer_initiation": transfer.get("user_id_transfer_initiation"),
#                         "user_id_acceptance": transfer.get("user_id_acceptance"),
#                     }
#                 )
#
#             return JsonResponse({"status": "success"}, status=201)
#
#         except Exception as e:
#             return JsonResponse({"status": "error", "message": str(e)}, status=400)
#     return JsonResponse({"status": "invalid method"}, status=405)
