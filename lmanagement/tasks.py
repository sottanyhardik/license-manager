from __future__ import absolute_import, unicode_literals

from scripts.dgft_shipping_bill import get_shipping_dgft_cookies, get_dgft_shipping_details
from .celery import app


@app.task
def add(x, y):
    return x + y


@app.task
def fetch_file(data,cookies,captcha):
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
    from shipping_bill.models import ShippingDetails
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
            print(dict_data)
            shipping.custom_file_number = dict_data['custom_file_number']
            shipping.file_number = dict_data['file_number']
            shipping.time_of_upload = dict_data['time_of_upload']
            shipping.save()
        else:
            pass

