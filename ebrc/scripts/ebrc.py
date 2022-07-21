import datetime

from bs4 import BeautifulSoup

from ebrc.models import EbrcDetails, ShippingDetails


def get_cookies():
    import requests
    headers = {
        'Host': 'dgftebrc.nic.in:8100',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:31.0) Gecko/20100101 Firefox/31.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    response = requests.get('http://dgftebrc.nic.in:8100/BRCQueryTrade/index.jsp', headers=headers)
    cookies = response.headers['Set-Cookie'].split(';')[0].split('JSESSIONID=')[-1]
    return cookies


def get_captcha(fetch_cookies):
    import requests
    cookies = {
        'JSESSIONID': fetch_cookies,
    }
    headers = {
        'Host': 'dgftebrc.nic.in:8100',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:31.0) Gecko/20100101 Firefox/31.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cache-Control': 'max-age=0',
    }
    response = requests.get('http://dgftebrc.nic.in:8100/BRCQueryTrade/index.jsp', headers=headers, cookies=cookies)
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table')
    img = table.find('img')
    captcha = img.get('src')
    return captcha


def get_list_shipping_bills(fetch_cookies, iec, ifsc, captext, file, shipping_bill='', sr_no=None):
    shipping_bill = shipping_bill.strip()
    try:
        import requests
        cookies = {
            'JSESSIONID': fetch_cookies,
        }
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Origin': 'http://dgftebrc.nic.in:8100',
            'Referer': 'http://dgftebrc.nic.in:8100/BRCQueryTrade/index.jsp',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
        }

        data = {
            'iec': iec,
            'ifsc': ifsc,
            'fdate': '',
            'tdate': '',
            'sno': shipping_bill,
            'sdate': '',
            'sport': '',
            'billid': '',
            'brcno': '',
            'brcstat': 'A',
            'utilstat': ' ',
            'captext': captext,
            'B1': 'Show Details',
        }
        response = requests.post('http://dgftebrc.nic.in:8100/BRCQueryTrade/brcIssuedTrade.jsp', cookies=cookies,
                                 headers=headers, data=data, verify=False)
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.findAll('table')[-1]
        if 'BRC No' in table.text:
            trs = table.findAll('tr')
            del trs[0]
            if trs:
                for tr in trs:
                    tds = tr.findAll('td')
                    brc_date = tds[1].text
                    brc_status = tds[2].text
                    shipping_bill_no = tds[3].text.strip()
                    shipping_port = tds[4].text
                    shipping_date = tds[5].text
                    realised_value = tds[6].text
                    currency = tds[7].text
                    date_of_realisation = tds[8].text
                    brc_utilisation_status = tds[9].text
                    ebrcNumb = tds[10].find("input", {"id": "ebrcNumb"}).get('value')
                    recid = tds[10].find("input", {"id": "recid"}).get('value')
                    iec = tds[10].find("input", {"id": "iec"}).get('value')
                    shipping_bill, bool = ShippingDetails.objects.get_or_create(shipping_bill=shipping_bill_no,
                                                                                file_id=file)
                    shipping_bill.shipping_port = shipping_port
                    shipping_bill.shipping_date = datetime.datetime.strptime(shipping_date, '%d.%m.%Y')
                    shipping_bill.save()
                    ebrc, bool = EbrcDetails.objects.get_or_create(
                        shipping_bill=shipping_bill,
                        brc_date=brc_date, brc_status=brc_status,
                        realised_value=realised_value, currency=currency,
                        date_of_realisation=date_of_realisation,
                        brc_utilisation_status=brc_utilisation_status,
                        ebrcNumb=ebrcNumb
                    )
                    ebrc.recid = recid
                    ebrc.save()
                    try:
                        directory = "media/brc/{0}/".format(str(file))
                        import os
                        if not os.path.exists(directory):
                            os.makedirs(directory)
                        file_name = '{0}{1}_{2}.pdf'.format(directory, str(shipping_bill.shipping_bill), str(ebrc.id))
                        print(file_name)
                        data = get_pdf(fetch_cookies, ebrcNumb, iec, recid, file_name)
                    except:
                        pass
                return True
            else:
                return False
        elif 'BRC Status' in table.text:
            trs = table.findAll('tr')
            del trs[0]
            if trs:
                for tr in trs:
                    tds = tr.findAll('td')
                    shipping_bill_no = tds[3].text.strip()
                    shipping_port = tds[4].text
                    shipping_date = tds[5].text
                    shipping_bill, bool = ShippingDetails.objects.get_or_create(shipping_bill=shipping_bill_no,
                                                                                file_id=file)
                    shipping_bill.shipping_port = shipping_port
                    shipping_bill.shipping_date = datetime.datetime.strptime(shipping_date, '%d.%m.%Y')
                    shipping_bill.save()
                return True
            else:
                return False

        else:
            return False
    except Exception as e:
        print('{0}-{1}={2}'.format(shipping_bill, iec, ifsc))
        print(e)
        return False


def get_pdf(fetch_cookies, ebrcNumb, iec, recid, file_name):
    import requests
    cookies = {
        'JSESSIONID': fetch_cookies,
    }
    headers = {
        'Host': 'dgftebrc.nic.in:8100',
        'Cache-Control': 'max-age=0',
        'Origin': 'http://dgftebrc.nic.in:8100',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Referer': 'http://dgftebrc.nic.in:8100/BRCQueryTrade/brcIssuedTrade.jsp',
        'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        'AlexaToolbar-ALX_NS_PH': 'AlexaToolbar/alx-4.0.3',
    }
    data = {
        'ebrcNumb': ebrcNumb,
        'iec': iec,
        'recid': recid,
        'B1': 'Print'
    }
    response = requests.post('http://dgftebrc.nic.in:8100/BRCQueryTrade/eBRCPrint.jsp', headers=headers,
                             cookies=cookies, data=data)
    import pdfkit
    pdfkit \
        .from_string(response.content.decode('utf-8'), file_name)
    return True
