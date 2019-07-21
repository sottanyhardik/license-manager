from bs4 import BeautifulSoup
import requests
from core import models
from core.models import SIONExportModel, SIONImportModel, ItemNameModel


def request_sion_heads():
    url = 'http://www.eximguru.com/ionorms-sion/default.aspx'
    r = requests.get(url)
    data = r.text
    soup = BeautifulSoup(data, features="xml")
    table = soup.findAll("table", {"class": "table table-bordered table-striped"})[1]
    for link in table.findAll('a'):
        url = link['href']
        text = link.text.replace('SION OR IO NORMS OF ', '')
        head, bool = models.HeadSIONNormsModel.objects.get_or_create(url=url)
        head.name = text
        head.save()


def request_sion_class_heads(head):
    r = requests.get(head.url)
    data = r.text
    soup = BeautifulSoup(data, features="xml")
    text = soup.text
    if head.tpages and head.tpages == 1:
        if 'pages' in text:
            tpages = int(text.split('pages')[0].split(',')[-1].strip())
            head.tpages = tpages
            head.save()
        else:
            tpages = 1
    else:
        tpages = head.tpages
    if tpages == 1:
        table = soup.findAll("table", {"class": "table table-bordered table-striped"})[1]
        trs = table.findAll('tr')
        del trs[0]
        for tr in trs:
            tds = tr.findAll('td')
            a = tds[0].find('a')
            url = 'http://www.eximguru.com/ionorms-sion/' + a['href']
            norm_class = a.text
            norm_name = tds[1].text.replace('Input Output Norms of ', '')
            sion_class, bool = models.SionNormClassModel.objects.get_or_create(head_norm=head, url=url)
            sion_class.norm_name = norm_name
            sion_class.norm_class = norm_class
            sion_class.save()
            head.tpages = tpages
            head.is_fetch = True
            head.save()
    else:
        while head.tcurrent <= head.tpages:
            table = soup.findAll("table", {"class": "table table-bordered table-striped"})[1]
            trs = table.findAll('tr')
            del trs[0]
            for tr in trs:
                tds = tr.findAll('td')
                a = tds[0].find('a')
                url = 'http://www.eximguru.com/ionorms-sion/' + a['href'].replace('../', '')
                norm_class = a.text
                norm_name = tds[1].text.replace('Input Output Norms of ', '')
                sion_class, bool = models.SionNormClassModel.objects.get_or_create(head_norm=head, url=url)
                sion_class.norm_name = norm_name
                sion_class.norm_class = norm_class
                sion_class.save()
            if head.tcurrent == head.tpages:
                head.is_fetch = True
                head.save()
                break
            elif head.tcurrent == 1:
                head.tcurrent = head.tcurrent + 1
                next_url = '/standard-input-output-norms-export-product0{0}.aspx'.format(head.tcurrent)
                head.url = head.url.replace('.aspx', next_url)
                r = requests.get(head.url)
                data = r.text
                soup = BeautifulSoup(data, features="xml")
            else:
                head.tcurrent = head.tcurrent + 1
                url_split = head.url.split('/')
                del url_split[-1]
                merge_url = '/'.join(url_split)
                next_url = '/standard-input-output-norms-export-product0{0}.aspx'.format(head.tcurrent)
                head.url = merge_url + next_url
                r = requests.get(head.url)
                data = r.text
                soup = BeautifulSoup(data, features="xml")
            head.save()


def fetch_sion_data(cdata):
    if not cdata.is_fetch and cdata.url:
        r = requests.get(cdata.url)
        data = r.text
        soup = BeautifulSoup(data, "lxml")
        tables = soup.findAll('table')
        export_table = tables[1]
        tds = export_table.findAll('tr')[-3].findAll('td')
        sion, bool = SIONExportModel.objects.get_or_create(norm_class=cdata)
        sion.item_description = tds[2].text
        sion.quantity = tds[3].text.split(' ')[0]
        sion.unit = ''.join(tds[3].text.split(' ')[1:])
        sion.save()
        import_table = tables[5]
        trs = import_table.findAll('tr')
        del trs[0]
        sr_no = 1
        for tr in trs:
            if not '\n\n\n' == tr.text:
                tds = tr.findAll('td')
                item_description = tds[2].text.strip()
                item, bool = ItemNameModel.objects.get_or_create(name=item_description.lower())
                sion, bool = SIONImportModel.objects.get_or_create(norm_class=cdata,
                                                                   item=item)

                if not '%' in tds[3]:
                    try:
                        float(tds[3].text.split(' ')[0])
                        sion.quantity = tds[3].text.split(' ')[0]
                        sion.unit = ''.join(tds[3].text.split(' ')[1:])
                        sion.sr_no = sr_no
                        sr_no = sr_no + 1
                    except:
                        sion.condition = tds[3].text
                else:
                    sion.condition = tds[3].text
            sion.save()
        cdata.is_fetch = True
        cdata.save()


def fetch_sion_class():
    heads = models.HeadSIONNormsModel.objects.filter(is_fetch=False).order_by('id')
    for head in heads:
        try:
            request_sion_class_heads(head)
        except:
            pass
