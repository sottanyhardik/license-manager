from bs4 import BeautifulSoup

from eScrap.models import CompanyLicenseModel, CompanyListModel
from datetime import date
from datetime import datetime

def fetch_iec_details(cookies, captcha):
    import requests

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Origin': 'https://icegate.gov.in',
        'Referer': 'https://icegate.gov.in/EnqMod/licenseDGFT/pages/inputDetailsForEDI',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
        'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    companies = CompanyListModel.objects.filter(is_fetch=False)
    for company in companies:
        data = {
            'selLocationCd': 'INNSA1',
            'searchIecNo': company.iec_number,
            'licenseStartDate': '2022/01/01',
            'licenseEndDate': '2022/07/26',
            'captchaValue': captcha,
        }
        response = requests.post('https://icegate.gov.in/EnqMod/licenseDGFT/pages/searchLicenseDGFTForEDI', cookies=cookies,
                                 headers=headers, data=data)
        soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
        table = soup.find('table')
        trs = table.findAll('tr')
        for tr in trs:
            if not 'License No' in tr.text and not 'error code' in tr.text and not tr.text == '':
                tds = tr.findAll('td')
                print(tds)
                if len(tds) != 0:
                    license, bool = CompanyLicenseModel.objects.get_or_create(license_no=tds[2].text, company=company)
                    license.status = tds[1].text
                    license.scheme =tds[3].text
                    license.license_date =datetime.strptime(tds[4].text.replace('\xa0', ''), '%d-%b-%Y')
                    license.dgft_transmission_date =datetime.strptime(tds[5].text.replace('\xa0', ''), '%d-%b-%Y')
                    license.date_of_integration =datetime.strptime(tds[6].text.replace('\xa0', ''), '%d-%b-%Y')
                    license.error_code =tds[7].text
                    license.file_number =tds[8].text
                    license.save()
        company.is_fetch = True
        company.save()




