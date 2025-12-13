import os
import requests


def fetch_scrip_ownership(
    scrip_number: str,
    scrip_issue_date: str,
    iec_number: str,
    app_id: str,
    session_id: str,
    csrf_token: str,
    proxy: str = None
):
    """
    Fetch the current ownership and transfer status of a scrip from DGFT.

    Args:
        proxy: Optional proxy URL (e.g., "http://proxy.example.com:8080" or "socks5://proxy.example.com:1080")
               If not provided, will check DGFT_PROXY environment variable
    """
    url = "https://www.dgft.gov.in/CP/webHP"

    headers = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Referer": "https://www.dgft.gov.in/CP/?opt=adnavce-authorisation",
        "Origin": "https://www.dgft.gov.in",
        "X-Requested-With": "XMLHttpRequest",
        "DNT": "1",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Sec-CH-UA": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        "Sec-CH-UA-Platform": '"macOS"',
        "Sec-CH-UA-Mobile": "?0"
    }

    cookies = {
        "JSESSIONID": session_id
    }

    params = {
        "requestType": "ApplicationRH",
        "actionVal": "viewScripOwnership",
        "screenId": "90000549",
        "_csrf": csrf_token
    }

    data = {
        "scripNumber": scrip_number,
        "scripIssueDate": scrip_issue_date,
        "iecNumber": iec_number,
        "appId": app_id
    }

    # Get proxy from parameter or environment variable
    proxy_url = proxy or os.getenv('DGFT_PROXY')
    proxies = None

    if proxy_url:
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }

    try:
        response = requests.post(
            url,
            params=params,
            cookies=cookies,
            headers=headers,
            data=data,
            proxies=proxies,
            timeout=30
        )
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        print(f"❌ Error fetching scrip ownership: {e}")
        return None
