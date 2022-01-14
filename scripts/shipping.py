import requests
from django.contrib import messages
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


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
    response = requests.get('https://enquiry.icegate.gov.in/enquiryatices/sbTrack', headers=headers, cookies=cookies,
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
    headers = {
        'Host': 'enquiry.icegate.gov.in',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:31.0) Gecko/20100101 Firefox/31.0',
        'Accept': 'image/png,image/*;q=0.8,*/*;q=0.5',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://enquiry.icegate.gov.in/enquiryatices/sbTrack',
    }
    response = requests.get('https://enquiry.icegate.gov.in/enquiryatices/CaptchaImg.jpg', headers=headers,
                            cookies=cookies, verify=False)
    import base64
    encoded = base64.b64encode(response.content)
    encoded = 'data:image/jpeg;base64,' + encoded.decode('utf-8')
    return encoded


def request_shipping_bill(cookies, csrftoken, port, shipping_bill, date, captcha, request=None):
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
        'sbTrack_location': port,
        'SB_NO': shipping_bill,
        'SB_DT': date,
        'captchaResp': captcha
    }
    try:
        response = requests.post('https://enquiry.icegate.gov.in/enquiryatices/SBTrack_Ices_action', headers=headers,
                                 cookies=cookies, data=data, verify=False)
        if shipping_bill in response.content.decode('utf-8'):
            return True
        else:
            return False
    except:
        from django.contrib import messages
        messages.error(request, 'Error in Connecting IEC Gate Website. Shipping Bill:' + shipping_bill)


def fetch_sb_details(cookies, data, request=None):
    headers = {
        'Host': 'enquiry.icegate.gov.in',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:31.0) Gecko/20100101 Firefox/31.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': 'https://enquiry.icegate.gov.in/enquiryatices/SBTrack_Ices_action',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }
    response = requests.post('https://enquiry.icegate.gov.in/enquiryatices/SB_IcesDetails_action', headers=headers,
                             cookies=cookies, data=data, verify=False)
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
        tds = [td.text for td in soup.findAll('td') if td.text.strip() != '']
        dict_data = {'iec': tds[[th.text for th in soup.findAll('th')].index("IEC")].replace('\xa0', ''),
                     'cha_number': tds[[th.text for th in soup.findAll('th')].index("CHA No.")].replace('\xa0', ''),
                     'job_no': tds[[th.text for th in soup.findAll('th')].index("Job No.")].replace('\xa0', ''),
                     'job_date': tds[[th.text for th in soup.findAll('th')].index("Job Date")].replace('\xa0', ''),
                     'total_package': tds[[th.text for th in soup.findAll('th')].index("Total Package")].replace('\xa0',
                                                                                                                 ''),
                     'port_of_discharge': tds[
                         [th.text for th in soup.findAll('th')].index("Port of Discharge")].replace('\xa0', ''),
                     'gross_weight': tds[[th.text for th in soup.findAll('th')].index("Gross Weight (Kg)")].replace('\xa0',
                                                                                                               ''),
                     'fob': tds[[th.text for th in soup.findAll('th')].index("FOB(INR)")].replace('\xa0', ''),
                     'total_cess': tds[[th.text for th in soup.findAll('th')].index("Total Cess (INR)")].replace('\xa0', ''),
                     'drawback': tds[[th.text for th in soup.findAll('th')].index("Drawback")].replace('\xa0', ''),
                     'str': tds[[th.text for th in soup.findAll('th')].index("STR")].replace('\xa0', ''),
                     'total': tds[[th.text for th in soup.findAll('th')].index("Total (DBK+STR)")].replace('\xa0', '')}
        return dict_data
    except Exception as e:
        print(e)
        return None


def fetch_current_status(cookies, data, request=None):
    headers = {
        'Host': 'enquiry.icegate.gov.in',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:31.0) Gecko/20100101 Firefox/31.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': 'https://enquiry.icegate.gov.in/enquiryatices/SBTrack_Ices_action',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }
    response = requests.post('https://enquiry.icegate.gov.in/enquiryatices/sbCURR_icesTrack_Action', headers=headers,
                             cookies=cookies, data=data, verify=False)
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
        tds = [td.text for td in soup.findAll('td') if td.text.strip() != '']
        dict_data = {
            'leo_date': tds[[th.text for th in soup.findAll('th')].index("LEO Date")].replace('\xa0', ''),
            'dbk_scroll_no': tds[[th.text for th in soup.findAll('th')].index("DBK Scroll No")].replace('\xa0', ''),
            'scroll_date': tds[[th.text for th in soup.findAll('th')].index("Scroll Date")].replace('\xa0', '')
        }
        return dict_data
    except Exception as e:
        print(e)
        return None


def fetch_data_to_model(cookies, csrftoken, data_dict, kwargs, captcha, request=None):
    from ebrc.models import ShippingDetails
    data = ShippingDetails.objects.filter(shipping_port__isnull=False, scroll_details=False, file_id=kwargs.get('data')).exclude(failed=5).order_by('-failed').first()
    if data:
        print("'''''''''''''''''\n{0}''''''''''''''''''''".format(data.shipping_bill))
        if not data:
            return True
        if not data.shipping_date:
            data.failed = 5
            data.save()
            return True
        date = data.shipping_date.strftime('%Y/%m/%d')
        if request_shipping_bill(cookies, csrftoken, data_dict[data.shipping_port], data.shipping_bill, date, captcha, request=request):
            dict_data = {
                'sbTrack_location': data_dict[data.shipping_port],
                'SB_NO': data.shipping_bill,
                'SB_DT': date
            }
            dict_sb_data = fetch_sb_details(cookies, dict_data, request=request)
            if dict_sb_data:
                data.iec = dict_sb_data['iec']
                data.cha_number = dict_sb_data['cha_number']
                data.job_no = dict_sb_data['job_no']
                data.job_date = dict_sb_data['job_date']
                data.total_package = dict_sb_data['total_package']
                data.port_of_discharge = dict_sb_data['port_of_discharge']
                data.gross_weight = dict_sb_data['gross_weight']
                data.fob = dict_sb_data['fob']
                data.total_cess = dict_sb_data['total_cess']
                data.drawback = dict_sb_data['drawback']
                data.str = dict_sb_data['str']
                data.total = dict_sb_data['total']
                data.save()
                try:
                    dict_cs_data = fetch_current_status(cookies, dict_data, request=request)
                    if dict_cs_data:
                        data.dbk_scroll_no = dict_cs_data['dbk_scroll_no']
                        data.scroll_date = dict_cs_data['scroll_date']
                        data.leo_date = dict_cs_data['leo_date']
                        data.scroll_details = True
                        data.save()
                        messages.success(request, 'Data Fetch Completely for Shipping Bill:' + data.shipping_bill)
                    else:
                        data.failed = data.failed + 1
                        data.save()
                        print(False)
                except:
                    messages.error(request, 'Error in Fetching Scroll Date. Shipping Bill:' + data.shipping_bill)
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

