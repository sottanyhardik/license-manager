"""DGFT ownership fetch helper.

Moved from backend/data_script/fetch_ownership.py.
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

DGFT_URL = "https://www.dgft.gov.in/CP/webHP"
REQUEST_TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 4
BASE_RETRY_DELAY_SECONDS = 5

DGFT_HEADERS = {
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
    "Sec-CH-UA-Mobile": "?0",
}


def _clean_optional(value: str | None) -> str | None:
    """Return a stripped string or None for empty/whitespace-only input."""
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def fetch_scrip_ownership(
    scrip_number: str,
    scrip_issue_date: str,
    iec_number: str,
    app_id: str,
    session_id: str,
    csrf_token: str,
    proxy: str | None = None,
    aws_alb: str | None = None,
) -> requests.Response | None:
    """
    Fetch the current ownership and transfer status of a scrip from DGFT.

    Args:
        proxy:   Optional proxy URL (e.g., "http://proxy.example.com:8080" or "socks5://proxy.example.com:1080")
                 If not provided, will check DGFT_PROXY environment variable.
        aws_alb: Optional AWSALB sticky-session cookie. DGFT now sits behind an
                 AWS load balancer; without this, requests can be routed to a
                 backend instance that doesn't recognize JSESSIONID.
    """
    required_values = {
        "scrip_number": _clean_optional(scrip_number),
        "scrip_issue_date": _clean_optional(scrip_issue_date),
        "iec_number": _clean_optional(iec_number),
        "app_id": _clean_optional(app_id),
        "session_id": _clean_optional(session_id),
        "csrf_token": _clean_optional(csrf_token),
    }
    missing = [name for name, value in required_values.items() if value is None]
    if missing:
        logger.error("Cannot fetch DGFT ownership; missing required value(s): %s", ", ".join(missing))
        return None

    cookies = {
        "JSESSIONID": required_values["session_id"],
    }
    clean_aws_alb = _clean_optional(aws_alb)
    if clean_aws_alb:
        cookies["AWSALB"] = clean_aws_alb

    params = {
        "requestType": "ApplicationRH",
        "actionVal": "viewScripOwnership",
        "screenId": "90000549",
        "_csrf": required_values["csrf_token"],
    }

    data = {
        "scripNumber": required_values["scrip_number"],
        "scripIssueDate": required_values["scrip_issue_date"],
        "iecNumber": required_values["iec_number"],
        "appId": required_values["app_id"],
    }

    # Get proxy from parameter or environment variable
    proxy_url = _clean_optional(proxy) or _clean_optional(os.getenv("DGFT_PROXY"))
    proxies = None

    if proxy_url:
        proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }

    for attempt in range(MAX_ATTEMPTS):
        try:
            response = requests.post(
                DGFT_URL,
                params=params,
                cookies=cookies,
                headers=DGFT_HEADERS,
                data=data,
                proxies=proxies,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code == 429:
                wait = 2**attempt * BASE_RETRY_DELAY_SECONDS  # 5s, 10s, 20s, 40s
                logger.warning("Rate limited (429). Retrying in %ds... (attempt %d/%d)", wait, attempt + 1, MAX_ATTEMPTS)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            if attempt < MAX_ATTEMPTS - 1:
                wait = 2**attempt * BASE_RETRY_DELAY_SECONDS
                logger.warning("Request error: %s. Retrying in %ds... (attempt %d/%d)", e, wait, attempt + 1, MAX_ATTEMPTS)
                time.sleep(wait)
            else:
                logger.error("Error fetching scrip ownership: %s", e)
                return None
    return None
