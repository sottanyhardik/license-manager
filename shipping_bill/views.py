import json
from io import BytesIO

import xlsxwriter
from django.contrib import messages
from django.http import HttpResponseRedirect
# Create your views here.
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, ListView

from ebrc.models import ShippingDetails
from scripts.shipping import fetch_cookies, fetch_captcha, fetch_data_to_model
from . import forms

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from django.http import HttpResponse

from lmanagement.tasks import dgft_shipping_details

from django.views import View
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.utils.timezone import now
from django.contrib.auth.mixins import LoginRequiredMixin

import pandas as pd

from .forms import ExcelUploadForm
from .models import FileUploadDetails, ShippingDetailsOther, ShippingBillDetailsModels


class ShippingBillDumpView(View):
    def get(self, request, data):
        output = BytesIO()
        # Feed a buffer to workbook
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet("users")
        for row in ShippingDetailsOther.objects.filter(file_id=data):
            if ShippingDetails.objects.filter(file_id=data, shipping_bill=row.shipping_bill).count() > 1:
                row.delete()
        shipping_bill_details = ShippingDetailsOther.objects.filter(file_id=data)
        bold = workbook.add_format({'bold': True})
        columns = ["Sr No",	"Location",	"Shipping Bill No",	"Shipping Bill Date",	"IEC",	"CHA No.",	"Job No.",
                   "Job Date",	"Port of Discharge",	"Total Package",	"Gross Weight",	"FOB(INR)",	"Total Cess",
                   "Drawback",	"STR",	"Total (DBK+STR)",	"LEO Date","DBK Scroll No",	"Scroll Date", "Time Of Upload",
                   "Customer File Number", "File Number"]
        # Fill first row with columns
        row = 0
        for i, elem in enumerate(columns):
            worksheet.write(row, i, elem, bold)
        row += 1
        # Now fill other rows with columns
        for index, shipping_bill in enumerate(shipping_bill_details):
            worksheet.write(row, 0, shipping_bill.sr_no)
            worksheet.write(row, 1, shipping_bill.shipping_port)
            worksheet.write(row, 2, shipping_bill.shipping_bill)
            worksheet.write(row, 3, shipping_bill.shipping_date)
            worksheet.write(row, 4, shipping_bill.iec)
            worksheet.write(row, 5, shipping_bill.cha_number)
            worksheet.write(row, 6, shipping_bill.job_no)
            worksheet.write(row, 7, shipping_bill.job_date)
            worksheet.write(row, 8, shipping_bill.port_of_discharge)
            worksheet.write(row, 9, shipping_bill.total_package)
            worksheet.write(row, 10, shipping_bill.gross_weight)
            worksheet.write(row, 11, shipping_bill.fob)
            worksheet.write(row, 12, shipping_bill.total_cess)
            worksheet.write(row, 13, shipping_bill.drawback)
            worksheet.write(row, 14, shipping_bill.str)
            worksheet.write(row, 15, shipping_bill.total)
            worksheet.write(row, 16, shipping_bill.leo_date)
            worksheet.write(row, 17, shipping_bill.dbk_scroll_no)
            worksheet.write(row, 18, shipping_bill.scroll_date)
            worksheet.write(row, 19, shipping_bill.time_of_upload)
            worksheet.write(row, 20, shipping_bill.custom_file_number)
            worksheet.write(row, 21, shipping_bill.file_number)
            row += 1
        # Close workbook for building file
        workbook.close()
        output.seek(0)
        response = HttpResponse(output.read(),
                                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        return response


class ShippingBillFetchView(FormView):
    template_name = 'shipping_bill/fetch.html'
    form_class = forms.ShippingBillCaptcha

    def get_context_data(self, **kwargs):
        context = super(ShippingBillFetchView, self).get_context_data(**kwargs)
        try:
            cookies, csrftoken = fetch_cookies()
            context['captcha_url'] = fetch_captcha(cookies)
            import json
            context['fetch_cookies'] = json.dumps(cookies)
            context['csrftoken'] = csrftoken
            messages.success(self.request, 'Connection Established.')
        except:
            messages.error(self.request, 'Error in Connecting IEC Gate Website.')
        data = self.kwargs.get('data')
        for row in ShippingDetails.objects.filter(file_id=data):
            if ShippingDetails.objects.filter(file_id=data, shipping_bill=row.shipping_bill).count() > 1:
                row.delete()
        context['remain_count'] = ShippingDetails.objects.filter(scroll_details=False, shipping_port__isnull=False, failed__lte=5, file_id=self.kwargs.get('data')).count()
        context['remain_captcha'] = context['remain_count']/3
        return context

    def post(self, request, *args, **kwargs):
        captcha = self.request.POST.get('captcha')
        cookies = json.loads(self.request.POST.get('cookies'))
        csrftoken = self.request.POST.get('csrftoken')
        from bill_of_entry.scripts.utils import port_dict
        data_dict = port_dict
        status = True
        shipping_bills = ShippingDetailsOther.objects.filter(scroll_date=None, failed__lte=2)
        for shipping_bill in shipping_bills:
            try:
                status = fetch_data_to_model(cookies, csrftoken, data_dict, kwargs, captcha, request=self.request, data=shipping_bill)
            except Exception as e:
                print(e)
        if ShippingDetailsOther.objects.filter(scroll_date=None, file_id=kwargs.get('data')).exclude(failed=5, port_of_discharge=None).exists():
            ShippingDetailsOther.objects.filter(scroll_date=None).update(failed=0)
            return HttpResponseRedirect(reverse('fetch_shipping_bill', kwargs={'data': kwargs.get('data')}))
        else:
            ShippingDetailsOther.objects.filter(scroll_date=None).update(failed=0)
            return HttpResponseRedirect(reverse('shipping_bill_detail_list', kwargs={'data': kwargs.get('data')}))


class ShippingBillList(ListView):
    template_name = 'shipping_bill/detail_list.html'
    model_name = ShippingDetailsOther
    context_object_name = 'ebrc_list'

    def get_queryset(self):
        return ShippingDetailsOther.objects.filter(file_id=self.kwargs['data']).order_by('-shipping_date')


class ShippingDGFTBillFetchView(View):

    def get(self, request, data):
        dgft_shipping_details.delay(data)
        return HttpResponseRedirect(reverse('shipping_bill_detail_list', kwargs={'data': data}))



class UploadExcelShippingBillView(LoginRequiredMixin, View):
    template_name = 'shipping_bill/upload_excel.html'
    form_class = ExcelUploadForm

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = self.form_class(request.POST, request.FILES)
        context = {'form': form}
        if form.is_valid():
            file = request.FILES['file']
            fs = FileSystemStorage()
            saved_file = fs.save(file.name, file)
            file_path = fs.path(saved_file)

            # Save file upload metadata
            file_meta = FileUploadDetails.objects.create(
                user=request.user,
                file_name=file.name,
                upload_time=now().strftime('%Y-%m-%d %H:%M:%S'),
            )

            try:
                xl = pd.ExcelFile(file_path)
                for sheet_name in xl.sheet_names:
                    df = xl.parse(sheet_name)
                    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]

                    for index, row in df.iterrows():
                        if 'iec' in df.columns:
                            ShippingDetailsOther.objects.create(
                                file_id=file_meta.id,
                                sr_no=row.get('sr_no'),
                                shipping_port=row.get('shipping_port'),
                                shipping_bill=row.get('shipping_bill'),
                                shipping_date=row.get('shipping_date'),
                                iec=row.get('iec'),
                                cha_number=row.get('cha_number'),
                                job_no=row.get('job_no'),
                                job_date=row.get('job_date'),
                                total_package=row.get('total_package'),
                                port_of_discharge=row.get('port_of_discharge'),
                                gross_weight=row.get('gross_weight'),
                                fob=row.get('fob'),
                                total_cess=row.get('total_cess'),
                                drawback=row.get('drawback'),
                                str=row.get('str'),
                                total=row.get('total'),
                                leo_date=row.get('leo_date'),
                                scroll_date=row.get('scroll_date'),
                                dbk_scroll_no=row.get('dbk_scroll_no'),
                                file_number=row.get('file_number'),
                                custom_file_number=row.get('custom_file_number'),
                                time_of_upload=now().strftime('%Y-%m-%d %H:%M:%S'),
                                fetch_status=False
                            )
                        else:
                            ShippingDetailsOther.objects.create(
                                file_id=file_meta.id,
                                sr_no=row.get('sr_no'),
                                shipping_port=row.get('port_code'),
                                shipping_bill=row.get('shipping_bill_number'),
                                shipping_date=row.get('shipping_bill_date'),
                            )
                context['success'] = "Upload and import successful!"
            except Exception as e:
                context['error'] = f"Failed to process file: {e}"

        return render(request, self.template_name, context)


