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
from datetime import datetime
from decimal import Decimal

import requests
from django.core.management.base import BaseCommand

from core.models import ExchangeRateModel


logger = logging.getLogger(__name__)

LANDING_URL = "https://www.dgft.gov.in/CP/?opt=currency-list-exchange-rates"
API_URL_TPL = (
    "https://www.dgft.gov.in/CP/webHP?"
    "requestType=ApplicationRH&actionVal=service"
    "&screen=viewRates&screenId=9000012354&_csrf={csrf}"
)

# Currency code in DGFT response → field name on ExchangeRateModel
CURRENCY_FIELD_MAP = {
    "USD": "usd",
    "EUR": "euro",
    "GBP": "pound_sterling",
    "CNY": "chinese_yuan",
}


def _fetch_dgft_rates(timeout=20):
    """Fetch the latest exchange rates from DGFT (returns the raw 'data' list)."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    })

    # 1. Hit the landing page to get JSESSIONID + CSRF token
    landing = session.get(LANDING_URL, timeout=timeout, verify=True)
    landing.raise_for_status()
    csrf_match = re.search(r'name="_csrf"\s+content="([a-f0-9-]+)"', landing.text)
    if not csrf_match:
        raise RuntimeError("CSRF token not found on DGFT landing page")
    csrf = csrf_match.group(1)

    # 2. POST to the API with the session cookies
    api_url = API_URL_TPL.format(csrf=csrf)
    payload = {
        "dataJson[formData]": json.dumps({
            "dateFrom": "",
            "dateTo": "",
            "currencyCodeInput": "",
        })
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://www.dgft.gov.in",
        "Referer": LANDING_URL,
        "X-Requested-With": "XMLHttpRequest",
    }
    resp = session.post(api_url, headers=headers, data=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
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
