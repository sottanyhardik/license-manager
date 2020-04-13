import requests


def fetch_cookies():
    import requests
    cookies = {
        'style': 'blue',
    }
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en',
    }
    response = requests.get('https://www.icegate.gov.in/EnqMod/', headers=headers, cookies=cookies, verify=False)
    cookies = {}
    strings = response.headers['Set-Cookie'].split(';')
    for string in strings:
        if 'JSESSIONID' in string:
            cookies['JSESSIONID'] = string.split('JSESSIONID=')[-1]
        elif 'BIGipServerICEGATE_LOGIN_APP_6565' in string:
            cookies['BIGipServerICEGATE_LOGIN_APP_6565'] = string.split('BIGipServerICEGATE_LOGIN_APP_6565=')[-1]
        elif 'TS01b48377' in string:
            cookies['TS01b48377'] = string.split('TS01b48377=')[-1]
        elif 'TS013f8d96' in string:
            cookies['TS013f8d96'] = string.split('TS013f8d96=')[-1]
    return cookies


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


def request_company(cookies, iec, captcha):
    import requests
    cookies = {
        'JSESSIONID': 'FE9A5200A1021EB7E91801071146E7DE',
        'TS01b48377': '016b3f3df41f95d071b0d0f82797b78a67ce6daa8d35e8b5424fa648b264eb8b1e116ac14a1b789e081306106c7e48a5b703a8c85ca33151e4d704de1660180cd18bec20ed',
        'BIGipServerICEGATE_LOGIN_APP_6565': '2013856010.42265.0000',
        'TS013f8d96': '016b3f3df4a442ab48f4ef6afc8051d3c76746ddcc35e8b5424fa648b264eb8b1e116ac14a6de1ee853be3f2246fae03f49e5741f0770f1b8c6559b008611a0a1f31faab92',
        'style': 'blue',
    }
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Origin': 'https://www.icegate.gov.in',
        'Upgrade-Insecure-Requests': '1',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'Referer': 'https://www.icegate.gov.in/EnqMod/',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en',
    }
    data = {
        'searchIECode': iec,
        'captchaResp': '8sA2jO'
    }
    response = requests.post('https://www.icegate.gov.in/EnqMod/searchIecCodeAction', headers=headers, cookies=cookies,
                             data=data, verify=False)
    reponse_content = response.content.decode('utf-8')
    if 'IEC Status' in reponse_content:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(reponse_content, 'html.parser')
            dict_data = {'address': ''}
            pagetable = soup.find('table', id="pagetable")
            trs = pagetable.findAll('tr')
            for tr in trs:
                tds = tr.findAll('td')
                if tds:
                    if tds[0].text.strip() == 'IE Code':
                        dict_data['iec'] = tds[1].text.strip()
                    elif tds[0].text.strip() == 'Name':
                        dict_data['company_name'] = tds[1].text.strip()
                    elif tds[0].text.strip() == 'Address' or tds[0].text.strip() == '':
                        dict_data['address'] = dict_data['address'] + tds[1].text.strip()
                    elif tds[0].text.strip() == 'PAN' or tds[1].text.strip() == '':
                        dict_data['pan'] = tds[1].text.strip()
            return dict_data
        except Exception as e:
            print(e)
            return None
    else:
        file = open("resp_text.html", "w")
        file.write(response.text)
        file.close()
        return False


def fetch_data_to_model(cookies, captcha):
    from core.models import CompanyModel
    data = CompanyModel.objects.filter(is_fetch=False).exclude(failed=5).order_by('id').first()
    if data:
        data_dict = request_company(cookies, data.iec, captcha)
        if data_dict:
            data.address = data_dict['address']
            if 'pan' in list(data_dict.keys()):
                data.pan_card = data_dict['pan']
            data.name = data_dict['company_name']
            data.is_fetch = True
            data.save()
            return True
        else:
            data.failed = data.failed + 1
            data.save()
            print(False)
            return False
    else:
        return False
