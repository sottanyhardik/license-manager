import re

import requests
from bs4 import BeautifulSoup
from django_rq import job

from core.models import HSCodeDutyModel, ProductDescriptionModel

cookies = {
    'JSESSIONID': '132B3A095CDA9ED2089404CD6FC43BDA',
    'TS015cbc79': '016b3f3df4cb7de623877d653a684e3fdc325a09a591aa2bdb1c88462faa2b7ad719fa346bfffb3740104e8dbec18a6ad28e87164e096134e6486bc684f532f0f3d720aeed',
    'TS013f8d96': '016b3f3df46a82cc5266ef92e7ec24a4dfd045a15b6eef0f58cd35a9685a40cd667bef40eb1c1bb74c9473ac3637eca8bdcd903702',
    'style': 'blue',
}

headers = {
    'Host': 'www.icegate.gov.in',
    'Origin': 'https://www.icegate.gov.in',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1 Safari/605.1.15',
    'Referer': 'https://www.icegate.gov.in/Webappl/Trade-Guide-on-Imports',
    'Accept-Language': 'en-gb',
}


def fetch_hs_code():
    hs_list = ["%.2d" % i for i in range(1, 100)]
    for hs_2 in hs_list:
        data = {
            'cth': hs_2,
            'item': '',
            'cntrycd': '',
            'submitbutton': 'Search'
        }
        response = requests.post('https://www.icegate.gov.in/Webappl/Tariff-head-details', headers=headers,
                                 cookies=cookies, data=data)
        soup = BeautifulSoup(response.content, 'html.parser')
        hs_codes = soup.findAll('input', {'name': 'cth'})
        [HSCodeDutyModel.objects.get_or_create(hs_code=hs.get('value')) for hs in hs_codes]


def repair(text, backwards=False):
    left_bracket, right_bracket = "<", ">"
    if backwards:
        left_bracket, right_bracket = ">", "<"
    i = 0
    while i < len(text):
        if text[i] == left_bracket:
            j = i + 1
            while j < len(text) and re.match(r"[/\w]", text[j]):
                j += 1
                if backwards and text[j - 1] == "/":
                    break
            if j >= len(text) or text[j] != right_bracket:
                text = text[:j] + right_bracket + text[j:]
            i = j
        i += 1
    return text


def repair_tags(html):
    return repair(repair(html[::-1], True)[::-1])


@job
def fetch_duty_details(hs_code):
    headers = {
        'Host': 'www.icegate.gov.in',
        'Cache-Control': 'max-age=0',
        'Origin': 'https://www.icegate.gov.in',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36',
        'Sec-Fetch-Dest': 'document',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Referer': 'https://www.icegate.gov.in/Webappl/Tariff-head-details',
        'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
    }
    data = {
        'cth': hs_code
    }
    response = requests.post('https://www.icegate.gov.in/Webappl/Structure-of-Duty-for-selected-Tariff',
                             headers=headers, cookies=cookies, data=data)
    htmp_parser = response.content.decode('utf-8').lower()
    soup = BeautifulSoup(htmp_parser, 'html.parser')
    html_repair = soup.prettify().strip()
    html_repair = html_repair.replace('</tr>\n   </tbody>\n  </table>\n </body>\n</html>\n', '')
    html_repair = str(html_repair).replace('</tr>\n<td', '<td')
    soup = BeautifulSoup(html_repair, 'html.parser')
    file = open('Failed.html', 'w')
    file.write(html_repair)
    file.close()
    soup = BeautifulSoup(html_repair, 'html.parser')
    table = soup.find_all('table')
    if table:
        try:
            table = table[1]
            trs = table.find_all('tr')
            hs_code_obj, bool = HSCodeDutyModel.objects.get_or_create(hs_code=hs_code)
            hs_code_obj.product_description = table.findAll('tr')[1].text.replace('\n', '').strip().split(':')[1]
            for tr in trs:
                if 'basic customs duty' in tr.text:
                    hs_code_obj.basic_custom_duty = tr.findAll('td')[5].text.strip()
                elif 'Additional Duty Of customs'.lower() in tr.text:
                    hs_code_obj.additional_duty_of_customs = tr.findAll('td')[5].text.strip()
                elif 'Custom Health CESS'.lower() in tr.text:
                    hs_code_obj.custom_health_CESS = tr.findAll('td')[5].text.strip()
                elif 'Social Welfare Surcharge'.lower() in tr.text:
                    hs_code_obj.social_welfare_surcharge = tr.findAll('td')[5].text.strip()
                elif 'Additional CVD'.lower() in tr.text:
                    hs_code_obj.additional_CVD = tr.findAll('td')[5].text.strip()
                elif 'IGST Levy'.lower() in tr.text:
                    hs_code_obj.IGST_levy = tr.findAll('td')[5].text.strip()
                elif 'Compensation Cess'.lower() in tr.text:
                    hs_code_obj.compensation_cess = tr.findAll('td')[5].text.strip()
                elif 'Total Duty'.lower() in tr.text:
                    hs_code_obj.total_duty = tr.findAll('td')[5].text.strip()
                elif 'Sample calculation for Assessable value Rs. 100000'.lower() in tr.text:
                    hs_code_obj.sample_on_lakh = tr.findAll('td')[5].text.strip()
                    break
            hs_code_obj.is_fetch = True
            hs_code_obj.save()
        except Exception as e:
            print(e)


def fetch_duty():
    from fetch_hs_codes import fetch_duty_details
    hs_codes = HSCodeDutyModel.objects.filter(is_fetch=False).order_by('hs_code')
    for hs_code in hs_codes:
        print(hs_code.hs_code)
        fetch_duty_details.delay(hs_code.hs_code)


@job
def fetch_product_description(hs_code):
    product_descriptions = []
    for i in range(0, 6):
        import requests
        cookies = {
            '__zlcmid': 'xPj0qmjdP3owEH',
            '__auc': 'bc8c979c17115e3758d742816cb',
            '_ga': 'GA1.2.1289090600.1585210160',
            '_gid': 'GA1.2.849945841.1585210160',
            'PHPSESSID': '7a50c84276d1d2d9d3b7d9e22ecdd19b',
        }
        headers = {
            'Host': 'www.eximpulse.com',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1 Safari/605.1.15',
            'Accept-Language': 'en-gb',
        }
        params = (
            ('tpages', str(i)),
        )
        url = "https://www.eximpulse.com/import-hscode-{0}.htm".format(hs_code)
        response = requests.get(url, headers=headers, params=params,
                                cookies=cookies)
        htmp_parser = response.content.decode('utf-8').lower()
        soup = BeautifulSoup(htmp_parser, 'html.parser')
        table = soup.find('table')
        trs = table.find_all('tr')
        for tr in trs:
            tds = tr.findAll('td')
            if not len(tds) == 0:
                product_descriptions.append(tds[4].text)
    uproduct_descriptions = list(set(product_descriptions))
    hs_code_obj = HSCodeDutyModel.objects.get(hs_code=hs_code)
    [ProductDescriptionModel.objects.get_or_create(hs_code=hs_code_obj, product_description=product_description) for
     product_description in uproduct_descriptions]


def fetch_pd():
    from fetch_hs_codes import fetch_product_description
    hs_codes = HSCodeDutyModel.objects.filter(is_fetch=False).order_by('hs_code')
    for hs_code in hs_codes:
        print(hs_code.hs_code)
        fetch_product_description.delay(hs_code.hs_code)


@job
def fetch_xlx(hs_code):
    import requests
    cookies = {
        'PHPSESSID': '12e217e5af7f15b7622a2c30ac448c40',
        '_ga': 'GA1.2.1760074702.1585554696',
        '_gid': 'GA1.2.541674515.1585554696',
        '__auc': 'b84664481712a6ca87b5bbef865',
        '__zlcmid': 'xTj1SOQhO2vYb4',
        '__asc': '4dafe1cb1712a9231223fbf1bb8',
        '_gat': '1',
    }
    headers = {
        'Host': 'www.eximpulse.com',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36',
        'Sec-Fetch-Dest': 'document',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
    }
    url = 'https://www.eximpulse.com/import-hscode-{0}.htm'.format(hs_code)
    response = requests.get(url, headers=headers, cookies=cookies)
    htmp_parser = response.content.decode('utf-8')
    soup = BeautifulSoup(htmp_parser, 'html.parser')
    excel = soup.select("a[href*=iexcel]")[0]["href"]
    string = excel.split('hscode=')[-1].split('&')[0]
    params = (
        ('pd', ''),
        ('hscode', string),
        ('origin', ''),
        ('port', ''),
        ('month', ''),
        ('unit', ''),
    )
    response = requests.get('https://www.eximpulse.com/iexcel.php', headers=headers, params=params, cookies=cookies)
    url = response.content.decode('utf-8').split('href=')[-1].split('</script>')[0].replace("'", '')
    resp = requests.get(url)
    file_name = hs_code + '.xls'
    output = open(file_name, 'wb')
    output.write(resp.content)
    output.close()
    HSCodeDutyModel.objects.filter(hs_code=hs_code).update(is_fetch_xls=True)


def fetch_xls():
    from fetch_hs_codes import fetch_xlx
    hs_codes = HSCodeDutyModel.objects.filter(is_fetch_xls=False).order_by('hs_code')
    for hs_code in hs_codes:
        print(hs_code.hs_code)
        fetch_xlx.delay(hs_code.hs_code)