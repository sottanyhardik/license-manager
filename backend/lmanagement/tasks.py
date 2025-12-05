from __future__ import absolute_import, unicode_literals

import logging
from celery import shared_task
from django.db.models import Q

from bill_of_entry.scripts.boe import request_bill_of_entry, be_details
from core.models import PortModel
from backend.scripts.dgft_shipping_bill import get_shipping_dgft_cookies, get_dgft_shipping_details
from .celery import app

logger = logging.getLogger(__name__)


@app.task
def add(x, y):
    return x + y


@app.task
def fetch_file(data, cookies, captcha):
    from ebrc.models import FileUploadDetails
    file = FileUploadDetails.objects.get(pk=data)
    from ebrc.models import ShippingDetails
    shipping_list = ShippingDetails.objects.filter(ebrc=False, file=file)
    if shipping_list.exists():
        for shipping in shipping_list:
            list_ifsc = file.ifsc.split(',')
            for ifsc in list_ifsc:
                from ebrc.scripts.ebrc import get_list_shipping_bills
                status = get_list_shipping_bills(cookies, file.iec, ifsc, captcha, data, shipping.shipping_bill)
                if status:
                    break
    else:
        from ebrc.scripts.ebrc import get_list_shipping_bills
        list_ifsc = file.ifsc.split(',')
        for ifsc in list_ifsc:
            status = get_list_shipping_bills(cookies, file.iec, ifsc, captcha, data)
            if status:
                break


@app.task
def dgft_shipping_details(data):
    from shipping_bill.models import FileUploadDetails
    file = FileUploadDetails.objects.get(pk=data)
    from ebrc.models import ShippingDetails
    shipping_list = ShippingDetails.objects.filter(file_id=data)
    cookie = get_shipping_dgft_cookies()
    for shipping in shipping_list:
        data = {
            'D5': file.iec_code,
            'D8': shipping.shipping_port,
            'T5': shipping.shipping_bill,
            'button1': 'SB-Detail'
        }
        dict_data = get_dgft_shipping_details(cookie, data)
        if dict_data:
            logger.info(f"DGFT shipping details for {shipping.shipping_bill}: {dict_data}")
            shipping.custom_file_number = dict_data['custom_file_number']
            shipping.file_number = dict_data['file_number']
            shipping.time_of_upload = dict_data['time_of_upload']
            shipping.save()
        else:
            pass


@app.task
def fetch_data_to_model(cookies, csrftoken, data_dict, captcha, data_id):
    from bill_of_entry.models import BillOfEntryModel
    data = BillOfEntryModel.objects.filter(pk=data_id).filter(
        Q(is_fetch=False) | Q(appraisement=None) | Q(ooc_date=None) | Q(ooc_date='N.A.')).order_by('failed').first()
    if data:
        logger.info(f"Processing bill of entry: {data.bill_of_entry_number}")
        if not data:
            return True
        if not data.bill_of_entry_date:
            data.failed = 5
            data.save()
            return True
        date = data.bill_of_entry_date.strftime('%Y/%m/%d')
        if request_bill_of_entry(cookies, csrftoken, data_dict[data.port.code], data.bill_of_entry_number, date,
                                 captcha):
            dict_data = {
                'BE_NO': data.bill_of_entry_number,
                'BE_DT': date,
                'beTrack_location': data.port,
                '': ''
            }
            dict_sb_data = be_details(cookies, dict_data)
            if dict_sb_data:
                from core.models import CompanyModel
                company, bool = CompanyModel.objects.get_or_create(iec=dict_sb_data['iec'])
                from bill_of_entry.models import BillOfEntryModel
                BillOfEntryModel.objects.filter(bill_of_entry_number=data.bill_of_entry_number).update(company=company,
                                                                                                       is_fetch=True)
                boe = BillOfEntryModel.objects.get(bill_of_entry_number=data.bill_of_entry_number,
                                                   bill_of_entry_date=data.bill_of_entry_date)
                if 'cha' in list(dict_sb_data.keys()):
                    boe.cha = dict_sb_data['cha']
                if 'appraisement' in list(dict_sb_data.keys()):
                    boe.appraisement = dict_sb_data['appraisement']
                if 'ooc_date' in list(dict_sb_data.keys()):
                    boe.ooc_date = dict_sb_data['ooc_date']
                boe.save()
            else:
                data.failed = data.failed + 1
                data.save()
                logger.warning(f"Failed to fetch BE details for {data.bill_of_entry_number}")
        else:
            data.failed = data.failed + 1
            data.save()
            logger.warning(f"Failed to request bill of entry for {data.bill_of_entry_number}")
        return True
    else:
        return False


# @app.task
# def fetch_company_license(company_id, captcha, cookies, headers, port):
#     from bs4 import BeautifulSoup
#     from datetime import date
#     from datetime import datetime
#     company = CompanyListModel.objects.get(pk=company_id)
#     data = {
#         'selLocationCd': port,
#         'searchIecNo': company.iec_number,
#         'licenseStartDate': '2022/01/01',
#         'licenseEndDate': datetime.now().strftime("%Y/%m/%d"),
#         'captchaValue': captcha,
#     }
#     import requests
#     response = requests.post('https://icegate.gov.in/EnqMod/licenseDGFT/pages/searchLicenseDGFTForEDI',
#                              cookies=cookies,
#                              headers=headers, data=data)
#     soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
#     table = soup.find('table')
#     trs = table.findAll('tr')
#     for tr in trs:
#         if not 'License No' in tr.text and not 'error code' in tr.text and not tr.text == '':
#             tds = tr.findAll('td')
#             print(tds)
#             if len(tds) != 0:
#                 license, bool = CompanyLicenseModel.objects.get_or_create(license_no=tds[2].text, company=company)
#                 license.status = tds[1].text
#                 license.scheme = tds[3].text
#                 license.port = port
#                 license.license_date = datetime.strptime(tds[4].text.replace('\xa0', ''), '%d-%b-%Y')
#                 license.dgft_transmission_date = datetime.strptime(tds[5].text.replace('\xa0', ''), '%d-%b-%Y')
#                 license.date_of_integration = datetime.strptime(tds[6].text.replace('\xa0', ''), '%d-%b-%Y')
#                 license.error_code = tds[7].text
#                 license.file_number = tds[8].text
#                 license.save()
#     port_obj = PortModel.objects.get(code=port)
#     company.port.add(port_obj)
#     company.is_fetch = True
#     company.save()


@shared_task
def delete_license_details_by_numbers(license_numbers):
    """
    Deletes LicenseDetailsModel entries matching the given license_numbers.
    Expects a list of strings.
    """
    from license.models import LicenseDetailsModel
    data = LicenseDetailsModel.objects.get(license_number=license_numbers).delete()
    return f"Deleted {data} LicenseDetailsModel records with license_numbers: {license_numbers}"
