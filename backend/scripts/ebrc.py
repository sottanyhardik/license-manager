

def fetch_page():
    import requests
    cookies = {
        'JSESSIONID': 'BC891F473BEB3A641FDFCFC7C35DB089',
        'style': 'blue',
        'BIGipServerapp_trackenquiry_test': '1259012362.42265.0000',
        'BIGipServerEnquiry_Icegate_443': '3791782154.20480.0000',
    }
    headers = {
        'Host': 'enquiry.icegate.gov.in',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:31.0) Gecko/20100101 Firefox/31.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cache-Control': 'max-age=0',
    }
    response = requests.get('https://enquiry.icegate.gov.in/enquiryatices/sbTrack', headers=headers, cookies=cookies)
    page = response.content.decode('utf-8')
    return page


def fetch_captcha():
    import requests
    cookies = {
        'JSESSIONID': 'BC891F473BEB3A641FDFCFC7C35DB089',
        'style': 'blue',
        'BIGipServerapp_trackenquiry_test': '1259012362.42265.0000',
        'BIGipServerEnquiry_Icegate_443': '3791782154.20480.0000',
    }
    headers = {
        'Host': 'enquiry.icegate.gov.in',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:31.0) Gecko/20100101 Firefox/31.0',
        'Accept': 'image/png,image/*;q=0.8,*/*;q=0.5',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://enquiry.icegate.gov.in/enquiryatices/sbTrack',
        'Cache-Control': 'max-age=0',
    }
    response = requests.get('https://enquiry.icegate.gov.in/enquiryatices/CaptchaImg.jpg', headers=headers,
                            cookies=cookies, verify=False)
    page = response.content.decode('utf-8')
    return page
