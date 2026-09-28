"""DGFT ownership fetch helper.

Moved from backend/data_script/fetch_ownership.py.
"""

import logging
import os
import random
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DGFT_URL = settings.DGFT_OWNERSHIP_URL
REQUEST_TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 4
BASE_RETRY_DELAY_SECONDS = 5

DGFT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8,hi;q=0.7",
    "Cache-Control": "max-age=0",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "Referer": "https://www.dgft.gov.in/CP/?opt=adnavce-authorisation",
    "Origin": "https://www.dgft.gov.in",
    "X-Requested-With": "XMLHttpRequest",
    "DNT": "1",
    "Priority": "u=1, i",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-CH-UA": '"Google Chrome";v="153", "Chromium";v="153", "Not_A Brand";v="8"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
}

# Rotate User-Agent to avoid bot detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
]


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
                 If not provided, will check DGFT_PROXY or DGFT_HTTP_PROXY environment variable.
                 Useful for CloudFront WAF bypass on production servers.
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
    proxy_url = _clean_optional(proxy) or _clean_optional(os.getenv("DGFT_PROXY")) or _clean_optional(os.getenv("DGFT_HTTP_PROXY"))
    proxies = None

    if proxy_url:
        proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }
        logger.info("Using proxy for DGFT request: %s", proxy_url[:50] if len(proxy_url) > 50 else proxy_url)

    logger.debug("Fetching scrip ownership for %s issued %s (IEC: %s)", required_values["scrip_number"], required_values["scrip_issue_date"], required_values["iec_number"])

    # Use session for persistent cookie handling and better bot detection evasion
    session = requests.Session()

    for attempt in range(MAX_ATTEMPTS):
        try:
            # Rotate User-Agent to avoid bot detection on retries
            headers = DGFT_HEADERS.copy()
            headers["User-Agent"] = random.choice(USER_AGENTS)
            session.headers.update(headers)

            # Add slight delay to appear human (not immediate bot)
            if attempt > 0:
                time.sleep(random.uniform(0.5, 2.0))

            response = session.post(
                DGFT_URL,
                params=params,
                cookies=cookies,
                data=data,
                proxies=proxies,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
            if response.status_code == 429:
                wait = 2**attempt * BASE_RETRY_DELAY_SECONDS  # 5s, 10s, 20s, 40s
                logger.warning("Rate limited (429). Retrying in %ds... (attempt %d/%d)", wait, attempt + 1, MAX_ATTEMPTS)
                time.sleep(wait)
                continue

            if response.status_code >= 400:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_body = response.text[:500]  # First 500 chars
                    error_msg += f": {error_body}"
                except Exception:
                    pass
                logger.error("DGFT returned error: %s", error_msg)
                if response.status_code >= 500:
                    # Server error, retry
                    if attempt < MAX_ATTEMPTS - 1:
                        wait = 2**attempt * BASE_RETRY_DELAY_SECONDS
                        logger.warning("Server error. Retrying in %ds... (attempt %d/%d)", wait, attempt + 1, MAX_ATTEMPTS)
                        time.sleep(wait)
                        continue
                    return None
                # Client error (4xx), don't retry
                return None

            response.raise_for_status()
            return response
        except requests.Timeout as e:
            if attempt < MAX_ATTEMPTS - 1:
                wait = 2**attempt * BASE_RETRY_DELAY_SECONDS
                logger.warning("Request timeout (exceeded %ds). Retrying in %ds... (attempt %d/%d)", REQUEST_TIMEOUT_SECONDS, wait, attempt + 1, MAX_ATTEMPTS)
                time.sleep(wait)
            else:
                logger.error("Timeout after %d attempts", MAX_ATTEMPTS)
                return None
        except requests.ConnectionError as e:
            if attempt < MAX_ATTEMPTS - 1:
                wait = 2**attempt * BASE_RETRY_DELAY_SECONDS
                logger.warning("Connection error: %s. Retrying in %ds... (attempt %d/%d)", e, wait, attempt + 1, MAX_ATTEMPTS)
                time.sleep(wait)
            else:
                logger.error("Connection failed after %d attempts: %s", MAX_ATTEMPTS, e)
                return None
        except requests.RequestException as e:
            if attempt < MAX_ATTEMPTS - 1:
                wait = 2**attempt * BASE_RETRY_DELAY_SECONDS
                logger.warning("Request error: %s. Retrying in %ds... (attempt %d/%d)", e, wait, attempt + 1, MAX_ATTEMPTS)
                time.sleep(wait)
            else:
                logger.error("Error fetching scrip ownership after %d attempts: %s", MAX_ATTEMPTS, e)
                return None
    return None
