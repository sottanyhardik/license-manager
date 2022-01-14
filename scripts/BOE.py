import requests


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
    response = requests.get('https://enquiry.icegate.gov.in/enquiryatices/beTrackIces', headers=headers, cookies=cookies,
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
    response = requests.get('https://enquiry.icegate.gov.in/enquiryatices/CaptchaImg.jpg', headers=headers, cookies=cookies, verify=False)
    import base64
    encoded = base64.b64encode(response.content)
    encoded = 'data:image/jpeg;base64,' + encoded.decode('utf-8')
    return encoded



def bill_of_entry(data, cookies):
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Origin': 'https://enquiry.icegate.gov.in',
        'Upgrade-Insecure-Requests': '1',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'Referer': 'https://enquiry.icegate.gov.in/enquiryatices/beTrackIces',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en',
    }
    response = requests.post('https://enquiry.icegate.gov.in/enquiryatices/BETrack_Ices_action', headers=headers, cookies=cookies, data=data)

cookies, csrf = fetch_cookies()
data = {
  'csrfPreventionSalt': csrf,
  'beTrack_location': 'NHAVA SHEVA SEA (INNSA1)',
  'BE_NO': '3473524',
  'BE_DT': '2019/05/31',
  'captchaResp': '2llj6f'
}

bill_of_entry(data, cookies)