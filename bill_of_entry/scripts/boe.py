"""
Robust ICEGATE BE fetch helpers.
- Uses requests.Session() to manage cookies & redirects.
- Returns cookie snapshots (dict) + csrf token (string) for celery-safe passing.
- fetch_captcha accepts either a cookie dict or a requests.Session.
- Defensive checks on Content-Type and status_code; logs snippet when things go wrong.
"""

import base64
import logging
from typing import Tuple, Optional, Dict, Any

import requests
from bs4 import BeautifulSoup

# optionally disable insecure warnings if you pass verify=False
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ICEGATE_BASE = "https://enquiry.icegate.gov.in"
BE_TRACK_PATH = "/enquiryatices/beTrackIces"
CAPTCHA_PATH = "/enquiryatices/CaptchaImg.jpg"
BE_ACTION = "/enquiryatices/BETrack_Ices_action"
BE_DETAILS = "/enquiryatices/BE_IcesDetails_action"
BE_CURRST = "/enquiryatices/BE_IcesCURRST_action"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def create_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def _ensure_session(cookies_or_session: Optional[Any]) -> requests.Session:
    """
    Return a requests.Session. If input is already a session, return it.
    If a dict is provided, create a session and load those cookies.
    If None, return a fresh session.
    """
    if isinstance(cookies_or_session, requests.Session):
        return cookies_or_session
    sess = create_session()
    if isinstance(cookies_or_session, dict):
        sess.cookies.update(cookies_or_session)
    return sess


def fetch_cookies(verify: bool = False) -> Tuple[Dict[str, str], Optional[str]]:
    """
    Fetch the BE track page to obtain cookies & CSRF token.
    Returns (cookie_dict_snapshot, csrf_value_or_None).
    """
    sess = create_session()
    url = ICEGATE_BASE + BE_TRACK_PATH
    resp = sess.get(url, verify=verify, allow_redirects=True)
    logger.info("GET %s -> %s", url, resp.status_code)
    logger.debug("Cookies after GET: %s", sess.cookies.get_dict())

    # parse CSRF securely with BeautifulSoup
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        csrf_elem = soup.find("input", {"name": "csrfPreventionSalt"})
        csrf = csrf_elem["value"] if csrf_elem and csrf_elem.has_attr("value") else None
        if not csrf:
            logger.warning("CSRF token not found on initial page (fetched page snippet):\n%s", resp.text[:800])
    except Exception as e:
        logger.exception("Error parsing CSRF: %s", e)
        csrf = None

    # return cookie snapshot (json-serializable) and csrf
    return sess.cookies.get_dict(), csrf


def fetch_captcha(cookies_or_session: Optional[Any], verify: bool = False) -> Optional[str]:
    """
    Fetch the captcha image and return a base64 data URL string like:
      'data:image/jpeg;base64,...'
    Accepts either a requests.Session or the cookie dict returned by fetch_cookies().
    Returns None if captcha couldn't be fetched or returned non-image content.
    """
    sess = _ensure_session(cookies_or_session)
    headers = {
        "Referer": ICEGATE_BASE + BE_TRACK_PATH,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    url = ICEGATE_BASE + CAPTCHA_PATH
    resp = sess.get(url, headers=headers, verify=verify, allow_redirects=True)
    logger.info("GET captcha -> %s %s", resp.status_code, resp.headers.get("Content-Type"))
    logger.debug("Session cookies after captcha GET: %s", sess.cookies.get_dict())

    content_type = resp.headers.get("Content-Type", "")
    if resp.status_code != 200 or not content_type.startswith("image"):
        # The server returned HTML (error/block) or redirect; log snippet to help debug.
        snippet = resp.text[:1000] if resp.text else str(resp.content)[:1000]
        logger.warning("Captcha endpoint did not return an image. status=%s content-type=%s snippet:\n%s",
                       resp.status_code, content_type, snippet)
        return None

    encoded = "data:image/jpeg;base64," + base64.b64encode(resp.content).decode("utf-8")
    return encoded


def request_bill_of_entry(cookies_or_session: Any, csrftoken: str, port: str, be_no: str, date: str,
                          captcha: str, verify: bool = False) -> Tuple[bool, str]:
    """
    Submit the BE track form. Uses a session (recreates from cookie dict if needed).
    Returns (found_boolean, response_text_snippet).
    """
    sess = _ensure_session(cookies_or_session)
    headers = {
        "Referer": ICEGATE_BASE + BE_TRACK_PATH,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "csrfPreventionSalt": csrftoken or "",
        "beTrack_location": port,
        "BE_NO": be_no,
        "BE_DT": date,
        "captchaResp": captcha
    }
    url = ICEGATE_BASE + BE_ACTION
    resp = sess.post(url, headers=headers, data=data, verify=verify, allow_redirects=True)
    logger.info("POST BE action -> %s", resp.status_code)
    text = resp.text or ""
    if be_no and be_no in text:
        return True, text[:2000]
    logger.debug("BE number not found in response; snippet: %s", text[:1200])
    return False, text[:1200]


def be_details(cookies_or_session: Any, data: Dict[str, Any], verify: bool = False) -> Optional[Dict[str, str]]:
    """
    Fetch BE details (IEC, CHA Number, Appraisement, OOC DATE).
    `data` should be the required form payload for the details endpoint (from your view/task).
    Returns dict or None.
    """
    sess = _ensure_session(cookies_or_session)
    headers = {
        "Origin": ICEGATE_BASE,
        "Referer": ICEGATE_BASE + BE_ACTION,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = sess.post(ICEGATE_BASE + BE_DETAILS, headers=headers, data=data, verify=verify, allow_redirects=True)
    logger.info("POST BE_DETAILS -> %s", resp.status_code)
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        if soup.find(text="No Record found"):
            return None

        dict_data = {}
        # safer mapping by searching th/td pairs
        ths = soup.find_all("th")
        tds = soup.find_all("td")
        for idx, th in enumerate(ths):
            key = th.text.strip()
            if idx < len(tds):
                val = tds[idx].text.replace("\xa0", "").strip()
                if key == "IEC":
                    dict_data["iec"] = val
                elif key == "CHA Number":
                    dict_data["cha"] = val

        # now fetch CURRST action for appraisement / ooc date
        resp2 = sess.post(ICEGATE_BASE + BE_CURRST, headers=headers, data=data, verify=verify, allow_redirects=True)
        logger.info("POST BE_CURRST -> %s", resp2.status_code)
        soup2 = BeautifulSoup(resp2.text, "html.parser")
        ths2 = soup2.find_all("th")
        tds2 = soup2.find_all("td")
        for idx, th in enumerate(ths2):
            key = th.text.strip()
            if idx < len(tds2):
                val = tds2[idx].text.replace("\xa0", "").strip()
                if key == "APPRAISEMENT":
                    dict_data["appraisement"] = val
                elif key == "OOC DATE":
                    dict_data["ooc_date"] = val

        return dict_data if dict_data else None
    except Exception as e:
        logger.exception("Error parsing BE details: %s", e)
        return None


def rms_details(cookies_or_session: Any, data: Dict[str, Any], verify: bool = False) -> Optional[Dict[str, str]]:
    """
    Fetch RMS details (APPRAISEMENT chiefly).
    """
    sess = _ensure_session(cookies_or_session)
    headers = {
        "Origin": ICEGATE_BASE,
        "Referer": ICEGATE_BASE + BE_ACTION,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = sess.post(ICEGATE_BASE + BE_CURRST, headers=headers, data=data, verify=verify, allow_redirects=True)
    logger.info("POST BE_CURRST (rms) -> %s", resp.status_code)
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        ths = soup.find_all("th")
        tds = soup.find_all("td")
        dict_data = {}
        for idx, th in enumerate(ths):
            key = th.text.strip()
            if idx < len(tds) and key == "APPRAISEMENT":
                dict_data["appraisement"] = tds[idx].text.replace("\xa0", "").strip()
        return dict_data if dict_data else None
    except Exception as e:
        logger.exception("Error parsing RMS details: %s", e)
        return None


# --- scrap variants for icegate.gov.in (licenseDGFT) ---

def fetch_cookies_scrap(verify: bool = False) -> Tuple[Dict[str, str], Optional[str]]:
    sess = create_session()
    url = "https://icegate.gov.in/EnqMod/licenseDGFT/pages/inputDetailsForEDI"
    resp = sess.get(url, verify=verify, allow_redirects=True)
    logger.info("GET %s -> %s", url, resp.status_code)
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        csrf_elem = soup.find("input", {"name": "csrfPreventionSalt"})
        csrf = csrf_elem["value"] if csrf_elem and csrf_elem.has_attr("value") else None
    except Exception as e:
        logger.exception("Error parsing csrf for scrap: %s", e)
        csrf = None
    return sess.cookies.get_dict(), csrf


def fetch_captcha_scrap(cookies_or_session: Any, verify: bool = False) -> Tuple[Optional[str], Dict[str, str]]:
    sess = _ensure_session(cookies_or_session)
    headers = {
        "Referer": "https://icegate.gov.in/EnqMod/licenseDGFT/pages/inputDetailsForEDI",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    # some sites append jsessionid in URL; allowing redirects will handle it
    url = "https://icegate.gov.in/EnqMod/CaptchaImg.jpg"
    resp = sess.get(url, headers=headers, verify=verify, allow_redirects=True)
    logger.info("GET captcha_scrap -> %s %s", resp.status_code, resp.headers.get("Content-Type"))
    if resp.status_code != 200 or not (resp.headers.get("Content-Type", "").startswith("image")):
        logger.warning("Captcha scrap did not return an image; snippet: %s", resp.text[:400])
        return None, sess.cookies.get_dict()
    encoded = "data:image/jpeg;base64," + base64.b64encode(resp.content).decode("utf-8")
    return encoded, sess.cookies.get_dict()

