def get_shipping_dgft_cookies():
    import requests
    headers = {
        'Host': 'dgftcom.nic.in',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36',
        'DNT': '1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        'AlexaToolbar-ALX_NS_PH': 'AlexaToolbar/alx-4.0.3',
    }
    response = requests.get('http://dgftcom.nic.in/licasp/sbdetformnew.asp', headers=headers)
    return response.headers['Set-Cookie'].split('; ')[0]


def get_dgft_shipping_details(cookie, data):
    try:
        import requests
        cookies = {
            'ASPSESSIONIDCCBCTRBC': cookie,
        }
        headers = {
            'Host': 'dgftcom.nic.in',
            'Cache-Control': 'max-age=0',
            'Origin': 'http://dgftcom.nic.in',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Referer': 'http://dgftcom.nic.in/licasp/sbdetformnew.asp',
            'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
            'AlexaToolbar-ALX_NS_PH': 'AlexaToolbar/alx-4.0.3',
        }
        response = requests.post('http://dgftcom.nic.in/licasp/newsbdet.asp', headers=headers, cookies=cookies, data=data)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
        file_number = soup.findAll('tr')[-1].findAll('td')[6].text.replace('\xa0','')
        custom_file_number = soup.findAll('tr')[-1].findAll('td')[5].text.replace('\xa0','')
        time_of_upload = soup.findAll('tr')[-1].findAll('td')[3].text.replace('\xa0','')
        dict_data = {
            'file_number':file_number,
            'custom_file_number':custom_file_number,
            'time_of_upload':time_of_upload
        }
        return dict_data
    except Exception as e:
        print(e)
        return False


