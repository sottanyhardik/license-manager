from bs4 import BeautifulSoup

from core.models import PortModel
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
    ports = PortModel.objects.all()
    company = CompanyListModel.objects.filter(is_fetch=False).last()
    from lmanagement.tasks import fetch_company_license
    for port in ports:
        fetch_company_license.delay(company.pk,captcha,cookies,headers, port.code)
    company.is_fetch = True
    company.save()

