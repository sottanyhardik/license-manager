# Moved from backend/data_script/fetch_ownership.py
import logging
import os
import time
import requests

logger = logging.getLogger(__name__)


def fetch_scrip_ownership(
    scrip_number: str,
    scrip_issue_date: str,
    iec_number: str,
    app_id: str,
    session_id: str,
    csrf_token: str,
    proxy: str = None,
    aws_alb: str = None,
):
    """
    Fetch the current ownership and transfer status of a scrip from DGFT.

    Args:
        proxy:   Optional proxy URL (e.g., "http://proxy.example.com:8080" or "socks5://proxy.example.com:1080")
                 If not provided, will check DGFT_PROXY environment variable.
        aws_alb: Optional AWSALB sticky-session cookie. DGFT now sits behind an
                 AWS load balancer; without this, requests can be routed to a
                 backend instance that doesn't recognize JSESSIONID.
    """
    url = "https://www.dgft.gov.in/CP/webHP"

    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-GB,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Referer": "https://www.dgft.gov.in/CP/?opt=adnavce-authorisation",
        "Origin": "https://www.dgft.gov.in",
        "X-Requested-With": "XMLHttpRequest",
        "DNT": "1",
        "Priority": "u=1, i",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Sec-CH-UA": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "Sec-CH-UA-Platform": '"macOS"',
        "Sec-CH-UA-Mobile": "?0"
    }

    cookies = {
        "JSESSIONID": session_id,
    }
    if aws_alb:
        cookies["AWSALB"] = aws_alb

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

    for attempt in range(4):
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
            if response.status_code == 429:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s, 40s
                logger.warning("Rate limited (429). Retrying in %ds... (attempt %d/4)", wait, attempt + 1)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            if attempt < 3:
                wait = 2 ** attempt * 5
                logger.warning("Request error: %s. Retrying in %ds... (attempt %d/4)", e, wait, attempt + 1)
                time.sleep(wait)
            else:
                logger.error("Error fetching scrip ownership: %s", e)
                return None
    return None
