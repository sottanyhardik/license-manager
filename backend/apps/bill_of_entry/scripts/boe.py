"""
Robust ICEGATE BE fetch helpers.
- Uses requests.Session() to manage cookies & redirects.
- Returns cookie snapshots (dict) + csrf token (string) for celery-safe passing.
- fetch_captcha accepts either a cookie dict or a requests.Session.
- Defensive checks on Content-Type and status_code; logs snippet when things go wrong.
"""

import base64
import logging
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import Any, Final

import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ICEGATE_BASE: Final = "https://enquiry.icegate.gov.in"
BE_TRACK_PATH: Final = "/enquiryatices/beTrackIces"
CAPTCHA_PATH: Final = "/enquiryatices/CaptchaImg.jpg"
BE_ACTION: Final = "/enquiryatices/BETrack_Ices_action"
BE_DETAILS: Final = "/enquiryatices/BE_IcesDetails_action"
BE_CURRST: Final = "/enquiryatices/BE_IcesCURRST_action"
DEFAULT_TIMEOUT: Final = 15
MAX_LOG_SNIPPET: Final = 1000

DEFAULT_HEADERS: Final = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class _IcegateHTMLParser(HTMLParser):
    def __init__(self, input_name: str | None = None):
        super().__init__(convert_charrefs=True)
        self.input_name = input_name
        self.input_value: str | None = None
        self._current_cell: str | None = None
        self._buffer: list[str] = []
        self.cells: list[tuple[str, str]] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "input" and attr_map.get("name") == self.input_name:
            self.input_value = attr_map.get("value") or ""
        if tag in {"th", "td"}:
            self._current_cell = tag
            self._buffer = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._current_cell:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == self._current_cell:
            self.cells.append((tag, "".join(self._buffer).replace("\xa0", "").strip()))
            self._current_cell = None
            self._buffer = []


def create_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def _safe_text_snippet(response: requests.Response, limit: int = MAX_LOG_SNIPPET) -> str:
    try:
        text = response.text or ""
    except (LookupError, UnicodeDecodeError):
        text = ""
    return text[:limit] if text else repr(response.content[:limit])


def _clean_form_value(value: Any) -> str:
    return str(value or "").strip()


def _input_value(html: str, name: str) -> str | None:
    parser = _IcegateHTMLParser(input_name=name)
    parser.feed(html or "")
    return parser.input_value


def _contains_text(html: str, needle: str) -> bool:
    parser = _IcegateHTMLParser()
    parser.feed(html or "")
    return needle in "".join(parser.text_parts)


def _table_pairs(html: str) -> list[tuple[str, str]]:
    parser = _IcegateHTMLParser()
    parser.feed(html or "")
    headers = [text for tag, text in parser.cells if tag == "th"]
    values = [text for tag, text in parser.cells if tag == "td"]
    return list(zip(headers, values, strict=False))


def _ensure_session(cookies_or_session: Any | None) -> requests.Session:
    """
    Return a requests.Session. If input is already a session, return it.
    If a dict is provided, create a session and load those cookies.
    If None, return a fresh session.
    """
    if isinstance(cookies_or_session, requests.Session):
        return cookies_or_session
    sess = create_session()
    if isinstance(cookies_or_session, Mapping):
        sess.cookies.update({str(key): str(value) for key, value in cookies_or_session.items()})
    return sess


def fetch_cookies(verify: bool = False, timeout: int | float = DEFAULT_TIMEOUT) -> tuple[dict[str, str], str | None]:
    """
    Fetch the BE track page to obtain cookies & CSRF token.
    Returns (cookie_dict_snapshot, csrf_value_or_None).
    """
    sess = create_session()
    url = ICEGATE_BASE + BE_TRACK_PATH
    try:
        resp = sess.get(url, verify=verify, allow_redirects=True, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return sess.cookies.get_dict(), None
    logger.info("GET %s -> %s", url, resp.status_code)
    logger.debug("Cookies after GET: %s", sess.cookies.get_dict())
    if resp.status_code != 200:
        logger.warning("Initial BE page returned status=%s snippet=%s", resp.status_code, _safe_text_snippet(resp, 800))
        return sess.cookies.get_dict(), None

    # parse CSRF with the standard-library HTML parser
    try:
        csrf = _input_value(resp.text, "csrfPreventionSalt")
        if not csrf:
            logger.warning("CSRF token not found on initial page (fetched page snippet):\n%s", _safe_text_snippet(resp, 800))
    except Exception as e:
        logger.exception("Error parsing CSRF: %s", e)
        csrf = None

    # return cookie snapshot (json-serializable) and csrf
    return sess.cookies.get_dict(), csrf


def fetch_captcha(cookies_or_session: Any | None, verify: bool = False, timeout: int | float = DEFAULT_TIMEOUT) -> str | None:
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
    try:
        resp = sess.get(url, headers=headers, verify=verify, allow_redirects=True, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("GET captcha failed: %s", exc)
        return None
    logger.info("GET captcha -> %s %s", resp.status_code, resp.headers.get("Content-Type"))
    logger.debug("Session cookies after captcha GET: %s", sess.cookies.get_dict())

    content_type = resp.headers.get("Content-Type", "")
    if resp.status_code != 200 or not content_type.startswith("image"):
        # The server returned HTML (error/block) or redirect; log snippet to help debug.
        snippet = _safe_text_snippet(resp)
        logger.warning("Captcha endpoint did not return an image. status=%s content-type=%s snippet:\n%s",
                       resp.status_code, content_type, snippet)
        return None

    encoded = "data:image/jpeg;base64," + base64.b64encode(resp.content).decode("utf-8")
    return encoded


def request_bill_of_entry(cookies_or_session: Any, csrftoken: str, port: str, be_no: str, date: str,
                          captcha: str, verify: bool = False, timeout: int | float = DEFAULT_TIMEOUT) -> tuple[bool, str]:
    """
    Submit the BE track form. Uses a session (recreates from cookie dict if needed).
    Returns (found_boolean, response_text_snippet).
    """
    sess = _ensure_session(cookies_or_session)
    headers = {
        "Referer": ICEGATE_BASE + BE_TRACK_PATH,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    be_no_clean = _clean_form_value(be_no)
    data = {
        "csrfPreventionSalt": _clean_form_value(csrftoken),
        "beTrack_location": _clean_form_value(port),
        "BE_NO": be_no_clean,
        "BE_DT": _clean_form_value(date),
        "captchaResp": _clean_form_value(captcha),
    }
    if not all(data.values()):
        logger.warning("BE action request missing required form values.")
        return False, "missing required form values"
    url = ICEGATE_BASE + BE_ACTION
    try:
        resp = sess.post(url, headers=headers, data=data, verify=verify, allow_redirects=True, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("POST BE action failed: %s", exc)
        return False, str(exc)
    logger.info("POST BE action -> %s", resp.status_code)
    text = resp.text or ""
    if resp.status_code == 200 and be_no_clean in text:
        return True, text[:2000]
    logger.debug("BE number not found in response; snippet: %s", text[:1200])
    return False, text[:1200]


def be_details(cookies_or_session: Any, data: Mapping[str, Any], verify: bool = False,
               timeout: int | float = DEFAULT_TIMEOUT) -> dict[str, str] | None:
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
    try:
        resp = sess.post(ICEGATE_BASE + BE_DETAILS, headers=headers, data=data, verify=verify,
                         allow_redirects=True, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("POST BE_DETAILS failed: %s", exc)
        return None
    logger.info("POST BE_DETAILS -> %s", resp.status_code)
    try:
        if _contains_text(resp.text, "No Record found"):
            return None

        dict_data = {}
        for key, val in _table_pairs(resp.text):
            if key == "IEC":
                dict_data["iec"] = val
            elif key == "CHA Number":
                dict_data["cha"] = val

        # now fetch CURRST action for appraisement / ooc date
        resp2 = sess.post(ICEGATE_BASE + BE_CURRST, headers=headers, data=data, verify=verify,
                          allow_redirects=True, timeout=timeout)
        logger.info("POST BE_CURRST -> %s", resp2.status_code)
        for key, val in _table_pairs(resp2.text):
            if key == "APPRAISEMENT":
                dict_data["appraisement"] = val
            elif key == "OOC DATE":
                dict_data["ooc_date"] = val

        return dict_data if dict_data else None
    except Exception as e:
        logger.exception("Error parsing BE details: %s", e)
        return None


def rms_details(cookies_or_session: Any, data: Mapping[str, Any], verify: bool = False,
                timeout: int | float = DEFAULT_TIMEOUT) -> dict[str, str] | None:
    """
    Fetch RMS details (APPRAISEMENT chiefly).
    """
    sess = _ensure_session(cookies_or_session)
    headers = {
        "Origin": ICEGATE_BASE,
        "Referer": ICEGATE_BASE + BE_ACTION,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        resp = sess.post(ICEGATE_BASE + BE_CURRST, headers=headers, data=data, verify=verify,
                         allow_redirects=True, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("POST BE_CURRST (rms) failed: %s", exc)
        return None
    logger.info("POST BE_CURRST (rms) -> %s", resp.status_code)
    try:
        dict_data = {}
        for key, val in _table_pairs(resp.text):
            if key == "APPRAISEMENT":
                dict_data["appraisement"] = val
        return dict_data if dict_data else None
    except Exception as e:
        logger.exception("Error parsing RMS details: %s", e)
        return None


# --- scrap variants for icegate.gov.in (licenseDGFT) ---

def fetch_cookies_scrap(verify: bool = False, timeout: int | float = DEFAULT_TIMEOUT) -> tuple[dict[str, str], str | None]:
    sess = create_session()
    url = "https://icegate.gov.in/EnqMod/licenseDGFT/pages/inputDetailsForEDI"
    try:
        resp = sess.get(url, verify=verify, allow_redirects=True, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("GET scrap cookies failed: %s", exc)
        return sess.cookies.get_dict(), None
    logger.info("GET %s -> %s", url, resp.status_code)
    try:
        csrf = _input_value(resp.text, "csrfPreventionSalt")
    except Exception as e:
        logger.exception("Error parsing csrf for scrap: %s", e)
        csrf = None
    return sess.cookies.get_dict(), csrf


def fetch_captcha_scrap(cookies_or_session: Any, verify: bool = False,
                        timeout: int | float = DEFAULT_TIMEOUT) -> tuple[str | None, dict[str, str]]:
    sess = _ensure_session(cookies_or_session)
    headers = {
        "Referer": "https://icegate.gov.in/EnqMod/licenseDGFT/pages/inputDetailsForEDI",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    # some sites append jsessionid in URL; allowing redirects will handle it
    url = "https://icegate.gov.in/EnqMod/CaptchaImg.jpg"
    try:
        resp = sess.get(url, headers=headers, verify=verify, allow_redirects=True, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("GET captcha_scrap failed: %s", exc)
        return None, sess.cookies.get_dict()
    logger.info("GET captcha_scrap -> %s %s", resp.status_code, resp.headers.get("Content-Type"))
    if resp.status_code != 200 or not (resp.headers.get("Content-Type", "").startswith("image")):
        logger.warning("Captcha scrap did not return an image; snippet: %s", _safe_text_snippet(resp, 400))
        return None, sess.cookies.get_dict()
    encoded = "data:image/jpeg;base64," + base64.b64encode(resp.content).decode("utf-8")
    return encoded, sess.cookies.get_dict()
