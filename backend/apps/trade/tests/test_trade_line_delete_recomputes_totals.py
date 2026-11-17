"""
Header totals must follow the lines when a line is deleted outside the trade
serializer's update path (docs/audits/TRADE_CIF_FOB_RECONCILIATION.md, drift
cause 8: a trade with 0 lines kept a stale total).
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.trade.models import LicenseTrade, LicenseTradeLine


def _line(trade, item, amount):
    return LicenseTradeLine.objects.create(
        trade=trade, sr_number=item, description="delete-recompute", mode="QTY",
        qty_kg=Decimal("10.0000"), rate_inr_per_kg=Decimal("1.000"), amount_inr=amount,
    )


@pytest.fixture
def item(test_license):
    from apps.license.models import LicenseImportItemsModel

    return LicenseImportItemsModel.objects.create(license=test_license, serial_number=78, description="del-item")


def _totals(trade):
    t = LicenseTrade.objects.get(pk=trade.pk)
    return t.subtotal_amount, t.roundoff, t.total_amount


@pytest.mark.django_db
def test_api_line_delete_recomputes_header(authenticated_client, test_trade, item):
    keep = _line(test_trade, item, Decimal("100.40"))
    drop = _line(test_trade, item, Decimal("50.25"))
    assert _totals(test_trade) == (Decimal("150.65"), Decimal("0.35"), Decimal("151.00"))

    r = authenticated_client.delete(reverse("trade:trade-line-detail", args=[drop.pk]))
    assert r.status_code == 204, getattr(r, "data", None)

    assert LicenseTradeLine.objects.filter(pk=keep.pk).exists()
    assert _totals(test_trade) == (Decimal("100.40"), Decimal("-0.40"), Decimal("100.00"))


@pytest.mark.django_db
def test_deleting_last_line_zeroes_header(test_trade, item):
    only = _line(test_trade, item, Decimal("1931139.00"))
    assert _totals(test_trade)[2] == Decimal("1931139.00")

    only.delete()

    assert _totals(test_trade) == (Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))


@pytest.mark.django_db
def test_queryset_delete_recomputes_header(test_trade, item):
    _line(test_trade, item, Decimal("10.00"))
    _line(test_trade, item, Decimal("20.00"))

    LicenseTradeLine.objects.filter(trade=test_trade, amount_inr=Decimal("20.00")).delete()

    assert _totals(test_trade)[0] == Decimal("10.00")


@pytest.mark.django_db
def test_incentive_line_delete_recomputes_header(test_company, test_company_2):
    from datetime import date

    from apps.core.models import PortModel
    from apps.license.models import IncentiveLicense
    from apps.trade.models import IncentiveTradeLine

    port = PortModel.objects.create(code="INCDEL", name="Incentive Delete Port")
    incentive = IncentiveLicense.objects.create(
        license_type="RODTEP", license_number="RODTEP-DEL-001", license_date=date(2026, 1, 1),
        license_expiry_date=date(2027, 12, 31), exporter=test_company, port_code=port,
        license_value=Decimal("5000.00"),
    )
    trade = LicenseTrade.objects.create(
        from_company=test_company, to_company=test_company_2, direction="PURCHASE",
        invoice_number="INV-INC-DEL-1", invoice_date=date(2026, 1, 15), license_type="INCENTIVE",
    )
    keep = IncentiveTradeLine.objects.create(
        trade=trade, incentive_license=incentive, license_value=Decimal("1000.00"),
        rate_pct=Decimal("10.000"), amount_inr=Decimal("100.00"),
    )
    drop = IncentiveTradeLine.objects.create(
        trade=trade, incentive_license=incentive, license_value=Decimal("2000.00"),
        rate_pct=Decimal("10.000"), amount_inr=Decimal("200.00"),
    )
    assert _totals(trade)[0] == Decimal("300.00")

    drop.delete()

    assert IncentiveTradeLine.objects.filter(pk=keep.pk).exists()
    assert _totals(trade) == (Decimal("100.00"), Decimal("0.00"), Decimal("100.00"))


@pytest.mark.django_db
def test_cascade_delete_of_trade_skips_recompute(test_trade, item):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    _line(test_trade, item, Decimal("10.00"))
    trade_pk = test_trade.pk
    table = LicenseTrade._meta.db_table

    with CaptureQueriesContext(connection) as ctx:
        LicenseTrade.objects.get(pk=trade_pk).delete()

    assert not LicenseTrade.objects.filter(pk=trade_pk).exists()
    updates = [q["sql"] for q in ctx.captured_queries if q["sql"].startswith("UPDATE") and table in q["sql"]]
    assert not any("subtotal_amount" in s for s in updates)
