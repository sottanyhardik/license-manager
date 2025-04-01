import requests


import requests
def fetch_scrip_ownership(scrip_number: str, scrip_issue_date: str, iec_number: str, app_id: str, session_id: str, csrf_token: str):
    url = 'https://www.dgft.gov.in/CP/webHP'
    cookies = {'JSESSIONID': session_id}
    headers = {
        'accept': '*/*',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'dnt': '1',
        'origin': 'https://www.dgft.gov.in',
        'priority': 'u=1, i',
        'referer': 'https://www.dgft.gov.in/CP/?opt=adnavce-authorisation',
        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }
    params = {
        'requestType': 'ApplicationRH',
        'actionVal': 'viewScripOwnership',
        'screenId': '90000549',
        '_csrf': csrf_token,
    }
    data = {
        'scripNumber': scrip_number,
        'scripIssueDate': scrip_issue_date,
        'iecNumber': iec_number,
        'appId': app_id,
    }
    response = requests.post(url, params=params, cookies=cookies, headers=headers, data=data)
    return response

