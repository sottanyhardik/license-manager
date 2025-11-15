from django.views.generic import FormView
from django.http import JsonResponse, HttpResponse
from shutil import make_archive

from allotment.forms import TlForm
from .common import bill_of_entry
from .common import logger


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
        return self.model.objects.get(id=self.kwargs.get('pk'))

    def get_initial(self):
        initial = super().get_initial()
        obj = self.get_object()
        initial['company'] = str(obj.company)
        initial['company_address_line1'] = str(obj.company.address_line_1)
        initial['company_address_line2'] = str(obj.company.address_line_2)
        return initial

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)
        try:
            boe = bill_of_entry.BillOfEntryModel.objects.get(id=self.kwargs.get('pk'))
            from datetime import datetime
            data = [{
                'status': item.sr_number.license.purchase_status,
                'company': self.request.POST.get('company'),
                'company_address_1': self.request.POST.get('company_address_line1'),
                'company_address_2': self.request.POST.get('company_address_line2'),
                'today': str(datetime.now().date()),
                'license': item.sr_number.license.license_number,
                'license_date': item.sr_number.license_date.strftime("%d/%m/%Y"),
                'file_number': item.sr_number.license.file_number,
                'quantity': item.qty,
                'v_allotment_inr': round(item.cif_inr, 2),
                'exporter_name': item.sr_number.license.exporter.name,
                'v_allotment_usd': item.cif_fc,
                'boe': "BE NUMBER :- " + item.bill_of_entry.bill_of_entry_number
            } for item in boe.item_details.all()]

            be_number = boe.bill_of_entry_number
            tl = self.request.POST.get('tl_choice')
            from core.models import TransferLetterModel
            transfer_letter = TransferLetterModel.objects.get(pk=tl)
            tl_path = transfer_letter.tl.path
            file_path = 'media/TL_' + str(be_number) + '_' + transfer_letter.name.replace(' ', '_') + '/'
            from allotment.scripts.aro import generate_tl_software
            generate_tl_software(data=data, tl_path=tl_path, path=file_path,
                                 transfer_letter_name=transfer_letter.name.replace(' ', '_'))
            file_name = 'TL_' + str(be_number) + '_' + transfer_letter.name.replace(' ', '_') + '.zip'
            path_to_zip = make_archive(file_path.rstrip('/'), 'zip', file_path.rstrip('/'))
            zip_file = open(path_to_zip, 'rb')
            response = HttpResponse(zip_file, content_type='application/force-download')
            response['Content-Disposition'] = 'attachment; filename="%s"' % file_name
            url = request.headers.get('origin') + path_to_zip.split('lmanagement')[-1]
            return JsonResponse({'url': url, 'message': 'Success'})
        except Exception as e:
            logger.exception("Error generating transfer letter: %s", e)
            return self.form_invalid(form)
