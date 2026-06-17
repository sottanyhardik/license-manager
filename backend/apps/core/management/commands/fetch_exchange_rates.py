"""
Fetch the latest customs exchange rates from DGFT and store them in
core.ExchangeRateModel.

Run manually:
    python manage.py fetch_exchange_rates

Schedule via Celery beat / cron once a day:
    0 7 * * *   python manage.py fetch_exchange_rates --quiet

The DGFT public endpoint returns only the latest effective date, so running
this daily ensures every rate change gets captured on the day it's published.
"""
import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal
from http.cookiejar import CookieJar

from django.core.management.base import BaseCommand

from apps.core.models import ExchangeRateModel


logger = logging.getLogger(__name__)

LANDING_URL = "https://www.dgft.gov.in/CP/?opt=currency-list-exchange-rates"
API_URL_TPL = (
    "https://www.dgft.gov.in/CP/webHP?"
    "requestType=ApplicationRH&actionVal=service"
    "&screen=viewRates&screenId=9000012354&_csrf={csrf}"
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

# Currency code in DGFT response → field name on ExchangeRateModel
CURRENCY_FIELD_MAP = {
    "USD": "usd",
    "EUR": "euro",
    "GBP": "pound_sterling",
    "CNY": "chinese_yuan",
}


def _fetch_dgft_rates(timeout=30):
    """Fetch the latest exchange rates from DGFT (returns the raw 'data' list).
    Uses stdlib only — no external requests dependency.
    """
    cookie_jar = CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar)
    )

    # Full Chrome-on-Mac headers — DGFT's WAF blocks minimal headers as bots
    browser_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="123", "Google Chrome";v="123", "Not?A_Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    # 1. Hit the landing page to obtain JSESSIONID + CSRF token
    landing_req = urllib.request.Request(LANDING_URL, headers=browser_headers)
    with opener.open(landing_req, timeout=timeout) as resp:
        raw = resp.read()
        # Handle gzip transparently (urllib doesn't auto-decompress)
        if resp.headers.get("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        elif resp.headers.get("Content-Encoding") == "br":
            try:
                import brotli
                raw = brotli.decompress(raw)
            except ImportError:
                # Retry without br
                pass
        landing_html = raw.decode("utf-8", errors="replace")
    csrf_match = re.search(r'name="_csrf"\s+content="([a-f0-9-]+)"', landing_html)
    if not csrf_match:
        raise RuntimeError("CSRF token not found on DGFT landing page")
    csrf = csrf_match.group(1)

    # 2. POST to the API with the cookies attached
    api_url = API_URL_TPL.format(csrf=csrf)
    payload = urllib.parse.urlencode({
        "dataJson[formData]": json.dumps({
            "dateFrom": "",
            "dateTo": "",
            "currencyCodeInput": "",
        })
    }).encode("utf-8")
    api_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://www.dgft.gov.in",
        "Referer": LANDING_URL,
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Ch-Ua": '"Chromium";v="123", "Google Chrome";v="123", "Not?A_Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    req = urllib.request.Request(api_url, data=payload, headers=api_headers, method="POST")
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        body = raw.decode("utf-8", errors="replace")
    data = json.loads(body)
    return data.get("data", [])


class Command(BaseCommand):
    help = "Fetch latest customs exchange rates from DGFT and store in ExchangeRateModel"

    def add_arguments(self, parser):
        parser.add_argument("--quiet", action="store_true", help="Suppress per-rate output")
        parser.add_argument("--force", action="store_true",
                            help="Update existing record for the date if rates differ")

    def handle(self, *args, **opts):
        quiet = opts["quiet"]
        force = opts["force"]

        try:
            records = _fetch_dgft_rates()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"DGFT fetch failed: {e}"))
            return

        if not records:
            self.stdout.write(self.style.WARNING("DGFT returned no records."))
            return

        # Group by effdate
        by_date = {}
        for r in records:
            effdate = r.get("effdate")
            code = r.get("currcode")
            if not effdate or code not in CURRENCY_FIELD_MAP:
                continue
            rate = r.get("importval")
            fcr_unit = r.get("fcrUnit") or 1
            if rate is None:
                continue
            # Normalise to "per 1 unit of foreign currency"
            normalized = Decimal(str(rate)) / Decimal(str(fcr_unit))
            by_date.setdefault(effdate, {})[CURRENCY_FIELD_MAP[code]] = normalized.quantize(Decimal("0.0001"))

        if not by_date:
            self.stdout.write(self.style.WARNING("DGFT returned no USD/EUR/GBP/CNY rates."))
            return

        created = updated = skipped = 0
        for date_str, fields in sorted(by_date.items()):
            try:
                rate_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write(self.style.WARNING(f"Skipping unparseable date: {date_str}"))
                continue

            # Need ALL four currencies for a complete row (model fields are NOT NULL)
            missing = [k for k in CURRENCY_FIELD_MAP.values() if k not in fields]
            if missing:
                self.stderr.write(self.style.WARNING(
                    f"{date_str}: missing {missing} — skipping (DGFT did not publish all currencies)"))
                continue

            existing = ExchangeRateModel.objects.filter(date=rate_date).first()
            if existing is None:
                ExchangeRateModel.objects.create(date=rate_date, **fields)
                created += 1
                if not quiet:
                    self.stdout.write(self.style.SUCCESS(
                        f"  CREATED {date_str}: USD={fields['usd']} EUR={fields['euro']} "
                        f"GBP={fields['pound_sterling']} CNY={fields['chinese_yuan']}"))
            else:
                # Check if values differ
                changed = any(
                    getattr(existing, k) != v for k, v in fields.items()
                )
                if changed and force:
                    for k, v in fields.items():
                        setattr(existing, k, v)
                    existing.save()
                    updated += 1
                    if not quiet:
                        self.stdout.write(self.style.WARNING(f"  UPDATED {date_str} (rates changed)"))
                else:
                    skipped += 1
                    if not quiet:
                        self.stdout.write(f"  SKIPPED {date_str} (already exists)")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone — created={created}, updated={updated}, skipped={skipped}"
        ))
