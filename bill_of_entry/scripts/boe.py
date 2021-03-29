import requests
from django.db.models import Q


def fetch_cookies():
    cookies = {
        'style': 'blue',
    }
    headers = {
        'Host': 'enquiry.icegate.gov.in',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:31.0) Gecko/20100101 Firefox/31.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    response = requests.get('https://enquiry.icegate.gov.in/enquiryatices/beTrackIces', headers=headers,
                            cookies=cookies,
                            verify=False)
    page = response.content.decode('utf-8')
    csrftoken = page.split('name="csrfPreventionSalt" value="')[-1].split('"')[0]
    cookies = {
        'JSESSIONID': response.headers['Set-Cookie'].split(';')[0].split('JSESSIONID=')[-1],
        'style': 'blue',
        'BIGipServerapp_trackenquiry_test':
            response.headers['Set-Cookie'].split('BIGipServerapp_trackenquiry_test=')[-1].split(';')[0],
        'BIGipServerEnquiry_Icegate_443':
            response.headers['Set-Cookie'].split('BIGipServerEnquiry_Icegate_443=')[-1].split(';')[0],
    }
    return cookies, csrftoken


def fetch_captcha(cookies):
    import requests
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en',
    }
    response = requests.get('https://enquiry.icegate.gov.in/enquiryatices/CaptchaImg.jpg', headers=headers,
                            cookies=cookies, verify=False)
    import base64
    encoded = base64.b64encode(response.content)
    encoded = 'data:image/jpeg;base64,' + encoded.decode('utf-8')
    return encoded


def request_bill_of_entry(cookies, csrftoken, port, be_no, date, captcha):
    headers = {
        'Host': 'enquiry.icegate.gov.in',
        'Cache-Control': 'max-age=0',
        'Origin': 'https://enquiry.icegate.gov.in',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Referer': 'https://enquiry.icegate.gov.in/enquiryatices/sbTrack',
        'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        'AlexaToolbar-ALX_NS_PH': 'AlexaToolbar/alx-4.0.3',
    }
    data = {
        'csrfPreventionSalt': csrftoken,
        'beTrack_location': port,
        'BE_NO': be_no,
        'BE_DT': date,
        'captchaResp': captcha
    }
    response = requests.post('https://enquiry.icegate.gov.in/enquiryatices/BETrack_Ices_action', headers=headers,
                             cookies=cookies, data=data, verify=False)
    if be_no in response.content.decode('utf-8'):
        return True
    else:
        return False


def be_details(cookies, data):
    headers = {
        'Origin': 'https://enquiry.icegate.gov.in',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': '*/*',
        'Referer': 'https://enquiry.icegate.gov.in/enquiryatices/BETrack_Ices_action',
        'Connection': 'keep-alive',
    }
    response = requests.post('https://enquiry.icegate.gov.in/enquiryatices/BE_IcesDetails_action', headers=headers,
                             cookies=cookies, data=data, verify=False)
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
        tds = [td.text for td in soup.findAll('td') if td.text.strip() != '']
        dict_data = {}
        for index, ddata in enumerate(soup.findAll('th')):
            if ddata.text == 'IEC':
                dict_data['iec'] = soup.findAll('td')[index].text.replace('\xa0', '')
            elif ddata.text == 'CHA No.':
                dict_data['cha'] = soup.findAll('td')[index].text.replace('\xa0', '')
        response = requests.post('https://www.enquiry.icegate.gov.in/enquiryatices/BE_IcesCURRST_action', headers=headers,
                                 cookies=cookies, data=data, verify=False)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
        for index, data in enumerate(soup.findAll('th')):
            if data.text == 'APPRAISEMENT':
                dict_data['appraisement'] = soup.findAll('td')[index].text.replace('\xa0', '')
        return dict_data
    except Exception as e:
        print(e)
        return None


def rms_details(cookies, data):
    import requests
    headers = {
        'Origin': 'https://enquiry.icegate.gov.in',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': '*/*',
        'Referer': 'https://enquiry.icegate.gov.in/enquiryatices/BETrack_Ices_action',
        'Connection': 'keep-alive',
    }
    response = requests.post('https://www.enquiry.icegate.gov.in/enquiryatices/BE_IcesCURRST_action', headers=headers,
                             cookies=cookies, data=data, verify=True)
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
        tds = [td.text for td in soup.findAll('td') if td.text.strip() != '']
        dict_data = {}
        for index, data in enumerate(soup.findAll('th')):
            if data.text == 'APPRAISEMENT':
                dict_data['appraisement'] = soup.findAll('td')[index].text.replace('\xa0', '')
        return dict_data
    except Exception as e:
        print(e)
        return None


def fetch_data_to_model(cookies, csrftoken, data_dict, kwargs, captcha):
    from bill_of_entry.models import BillOfEntryModel
    data = BillOfEntryModel.objects.filter(is_fetch=False).exclude(failed=5).order_by('id').first()
    if data:
        print("'''''''''''''''''\n{0}''''''''''''''''''''".format(data.bill_of_entry_number))
        if not data:
            return True
        if not data.bill_of_entry_date:
            data.failed = 5
            data.save()
            return True
        date = data.bill_of_entry_date.strftime('%Y/%m/%d')
        if request_bill_of_entry(cookies, csrftoken, data_dict[data.port.code], data.bill_of_entry_number, date, captcha):
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
                BillOfEntryModel.objects.filter(bill_of_entry_number=data.bill_of_entry_number).update(cha=dict_sb_data['cha'],company=company, is_fetch=True)
            else:
                data.failed = data.failed + 1
                data.save()
                print(False)

        else:
            data.failed = data.failed + 1
            data.save()
            print(False)
        return True
    else:
        return False


def fetch_data_to_model(cookies, csrftoken, data_dict, kwargs, captcha):
    from bill_of_entry.models import BillOfEntryModel
    data = BillOfEntryModel.objects.filter(Q(is_fetch=False)|Q(appraisement=None)).exclude(failed=5).order_by('id').first()
    if data:
        print("'''''''''''''''''\n{0}''''''''''''''''''''".format(data.bill_of_entry_number))
        if not data:
            return True
        if not data.bill_of_entry_date:
            data.failed = 5
            data.save()
            return True
        date = data.bill_of_entry_date.strftime('%Y/%m/%d')
        if request_bill_of_entry(cookies, csrftoken, data_dict[data.port.code], data.bill_of_entry_number, date, captcha):
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
                boe = BillOfEntryModel.objects.get(bill_of_entry_number=data.bill_of_entry_number)
                if 'cha' in list(dict_sb_data.keys()):
                    boe.cha = dict_sb_data['cha']
                if 'appraisement' in list(dict_sb_data.keys()):
                    boe.appraisement = dict_sb_data['appraisement']
                boe.save()
            else:
                data.failed = data.failed + 1
                data.save()
                print(False)
        else:
            data.failed = data.failed + 1
            data.save()
            print(False)
        return True
    else:
        return False

