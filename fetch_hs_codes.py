from core.models import HSCodeDutyModel

cookies = {
    'JSESSIONID': '5BBAA00543167D4C7960BAFEA82434B1',
    'style': 'blue',
}

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
    'Referer': 'https://www.icegate.gov.in/Webappl/Trade-Guide-on-Imports',
    'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
}


def fetch_hs_code():
    from bs4 import BeautifulSoup
    import requests
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


import re


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


from django_rq import job


@job
def fetch_duty_details(hs_code):
    from bs4 import BeautifulSoup
    import requests
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
