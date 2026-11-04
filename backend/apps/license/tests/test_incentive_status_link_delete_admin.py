"""Regression tests for review findings H1 (link/unlink/partner-delete), M1 (admin
edits to derived cache fields), M2 (header-path recalculation), L1 (over-sold repair)."""
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.contrib import admin
from django.core.management import call_command

from apps.core.models import CompanyModel, PortModel
from apps.license.models import IncentiveLicense
from apps.trade.models import IncentiveTradeLine, LicenseTrade
from apps.trade.services.trade_service import link_trades

_SEQ = iter(range(1, 10_000_000))


def _n():
    return next(_SEQ)


@pytest.fixture
def parties(db):
    n = _n()
    return {
        "exporter": CompanyModel.objects.create(iec=f"2{n:09d}", name=f"Exp {n}"),
        "buyer": CompanyModel.objects.create(iec=f"1{n:09d}", name=f"Buy {n}"),
        "port": PortModel.objects.create(code=f"L{n:05d}", name=f"Port {n}"),
    }


def _licence(parties, value="1000.00"):
    n = _n()
    return IncentiveLicense.objects.create(
        license_type="RODTEP", license_number=f"LNK{n:08d}", license_date=date(2025, 12, 19),
        exporter=parties["exporter"], port_code=parties["port"],
        license_value=Decimal(value), is_active=True,
    )


def _trade(parties, direction):
    n = _n()
    return LicenseTrade.objects.create(
        from_company=parties["exporter"], to_company=parties["buyer"], direction=direction,
        invoice_number=f"LNK-{direction[:2]}-{n}", invoice_date=date(2025, 12, 23), license_type="INCENTIVE",
    )


def _sale_line(trade, licence, value):
    # Normal create (signals active) so the cache is consistent before each test step.
    return IncentiveTradeLine.objects.create(
        trade=trade, incentive_license=licence, license_value=Decimal(value),
        rate_pct=Decimal("97.25"), amount_inr=Decimal(value),
    )


def _stored(licence):
    licence.refresh_from_db()
    return licence.sold_value, licence.balance_value, licence.sold_status


# ---- H1: linking changes the SALE rule (linked trades are excluded) -------------
@pytest.mark.django_db
def test_linking_a_sale_to_a_partner_recalculates_status_both_ways(parties):
    lic = _licence(parties, "1000.00")
    sale = _trade(parties, "SALE")
    partner = _trade(parties, "PURCHASE")
    _sale_line(sale, lic, "1000.00")
    assert _stored(lic)[2] == "YES"

    link_trades(trade_pk=sale.pk, partner_pk=partner.pk)
    # Under SALE_LINE_FILTERS a linked trade is not a qualifying external sale.
    assert _stored(lic) == (Decimal("0.00"), Decimal("1000.00"), "NO")

    link_trades(trade_pk=sale.pk, partner_pk=None)
    assert _stored(lic) == (Decimal("1000.00"), Decimal("0.00"), "YES")


@pytest.mark.django_db
def test_deleting_a_linked_partner_restores_the_sale(parties):
    lic = _licence(parties, "1000.00")
    sale = _trade(parties, "SALE")
    partner = _trade(parties, "PURCHASE")
    _sale_line(sale, lic, "1000.00")
    link_trades(trade_pk=sale.pk, partner_pk=partner.pk)
    assert _stored(lic)[2] == "NO"

    # SET_NULL on the surviving sale is a queryset update: no signal, so the
    # pre/post_delete capture is what recalculates the licence.
    partner.delete()

    assert _stored(lic) == (Decimal("1000.00"), Decimal("0.00"), "YES")


# ---- M2 / header path: a trade direction edit recalculates its lines' licences --
@pytest.mark.django_db
def test_changing_trade_direction_to_purchase_clears_sold_status(parties):
    lic = _licence(parties, "1000.00")
    sale = _trade(parties, "SALE")
    _sale_line(sale, lic, "1000.00")
    assert _stored(lic)[2] == "YES"

    sale.direction = "PURCHASE"
    sale.save()

    assert _stored(lic) == (Decimal("0.00"), Decimal("1000.00"), "NO")


# ---- M1: derived cache fields are read-only in the admin ----------------------
@pytest.mark.django_db
def test_admin_does_not_offer_derived_cache_fields_for_editing():
    import apps.license.admin  # noqa: F401  (registers the admin classes)

    model_admin = admin.site._registry[IncentiveLicense]
    assert {"sold_value", "balance_value", "sold_status"} <= set(model_admin.readonly_fields)


# ---- L1: an over-sold licence with a stale cache is repaired -------------------
@pytest.mark.django_db
def test_oversold_licence_with_stale_cache_is_repaired_and_still_flagged(parties, tmp_path):
    lic = _licence(parties, "1000.00")
    sale = _trade(parties, "SALE")
    IncentiveTradeLine.objects.bulk_create([
        IncentiveTradeLine(trade=sale, incentive_license=lic, license_value=Decimal("1150.00"),
                           rate_pct=Decimal("97.25"), amount_inr=Decimal("1150.00"))
    ])
    IncentiveLicense.objects.filter(pk=lic.pk).update(
        sold_value=Decimal("0.00"), balance_value=Decimal("1000.00"), sold_status="NO",
    )

    call_command("reconcile_incentive_license_status", "--apply", "--licence", lic.license_number,
                 "--report-dir", str(tmp_path), stdout=StringIO())

    assert _stored(lic) == (Decimal("1150.00"), Decimal("-150.00"), "YES")
    csv_text = next(tmp_path.glob("incentive_status_reconciliation_*.csv")).read_text(encoding="utf-8")
    assert "OVERSOLD" in csv_text
