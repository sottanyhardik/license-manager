from datetime import datetime


def file_date_fun(t1, t2):
    t1 = t1.replace('/','')
    if 'RANI' in t2:
        t2 = '0393030717'
    else:
        t2 = '0388083719'
    import requests
    cookies = {
        'ASPSESSIONIDSSBRAQBD': 'BPHIPPMCLDMDBBMFMMIKPNGN',
    }
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'Origin': 'http://dgftcom.nic.in',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Referer': 'http://dgftcom.nic.in/licasp/LicTranStatusDes.asp',
        'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
    }
    data = {
        'T1': t1,
        'T2': t2,
        'button1': '<< Show >>'
    }
    response = requests.post('http://dgftcom.nic.in/licasp/LicTranStatusDes.asp', headers=headers, cookies=cookies,
         data=data, verify=False)
    try:
        file_date = str(response.text).split('DES File Date</font></b></td>\r\n\t\t\t \t\t\t   <td width="73%" height="19"><b><font color="#0000FF">')[-1].split('</font>')[0]
        date = datetime.strptime(file_date, '%m/%d/%Y')
        file_date = str(date.date())
    except:
        file_date = ''
    return file_date


import csv
list1 = []
with open('input.csv', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        dict_data = {
            'dfia_no': row['\ufeffdfia_no'],
            'dfia_dt': row['dfia_dt'],
            'dfia_exp': row['dfia_exp'],
            'file_no': row['file_no'],
            'exporter': row['exporter'],
            'file_date': row['file_date'],
        }
        file_date = file_date_fun(row['file_no'], row['exporter'])
        dict_data['file_date'] = file_date
        print(dict_data)
        list1.append(dict_data)



with open('names.csv', 'w', newline='') as csvfile:
    fieldnames = ['dfia_no', 'dfia_dt','dfia_exp','file_no','file_date','exporter']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(list1)
