"""Test fixtures built on the real Trade module (no mocks of trade behaviour)."""
from __future__ import annotations

import itertools
from datetime import date
from decimal import Decimal

from apps.accounting.models import TdsSection
from apps.accounting.services.books import activate_books
from apps.accounting.services.payments import create_bank_account
from apps.core.models import CompanyModel

_iec = itertools.count(9_000_000_001)
_lic = itertools.count(1)


def company(name: str, gst: str = "", pan: str = "") -> CompanyModel:
    kwargs = {"name": name, "iec": f"{next(_iec):010d}"}
    if gst:
        kwargs["gst_number"] = gst
    if pan:
        kwargs["pan"] = pan
    return CompanyModel.objects.create(**kwargs)


def books(c: CompanyModel, start: date = date(2026, 4, 1)):
    return activate_books(c, start)


def bank(entity, number: str = "000111222333", opening: Decimal | None = None):
    return create_bank_account(entity, bank_name="HDFC Bank", account_number=number, ifsc="HDFC0000001",
                               opening_balance=opening)


def trade(direction: str, seller: CompanyModel, buyer: CompanyModel, amount: Decimal, *,
          number: str | None = None, on: date = date(2026, 5, 10), qty: Decimal = Decimal("100.0000")):
    from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
    from apps.trade.models import LicenseTrade, LicenseTradeLine
    exporter = seller if direction in ("PURCHASE", "COMMISSION_PURCHASE") else buyer
    n = next(_lic)
    lic = LicenseDetailsModel.objects.create(license_number=f"03110{n:05d}", exporter=exporter,
                                             license_date=date(2026, 4, 1), license_expiry_date=date(2027, 4, 1))
    item = LicenseImportItemsModel.objects.create(license=lic, serial_number=1, description="DFIA item")
    t = LicenseTrade.objects.create(direction=direction, from_company=seller, to_company=buyer,
                                    invoice_number=number or f"T/{direction[:3]}/{n}", invoice_date=on)
    LicenseTradeLine.objects.create(
        trade=t, sr_number=item, description=f"DFIA {lic.license_number}", mode=LicenseTradeLine.MODE_CIF_INR,
        qty_kg=qty, cif_fc=amount, exc_rate=Decimal("1.0000"), cif_inr=amount, pct=Decimal("100.000"),
        amount_inr=amount,
    )
    t.refresh_from_db()
    return t


def tds_section(code: str = "194Q", rate: str = "0.100", threshold: str = "5000000.00", mode: str = "EXCESS"):
    return TdsSection.objects.create(
        code=code, description=f"TDS {code} (test configuration)", rate_individual=Decimal(rate),
        rate_other=Decimal(rate), rate_no_pan=Decimal("5.000"), threshold_aggregate=Decimal(threshold),
        threshold_mode=mode, effective_from=date(2020, 4, 1),
    )


def immediate_constraints() -> None:
    """Fire deferred DB triggers inside a TestCase transaction (there is no COMMIT in tests)."""
    from django.db import connection
    with connection.cursor() as cur:
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
