"""Regression tests: incentive licence Sold / Partial / Available status.

Source of truth (verified against the database, not assumed):
  * A sale is an ``IncentiveTradeLine`` whose trade is ``direction='SALE'`` and
    is not linked to another trade (``trade__linked_trade__isnull``). This is the
    same ``SALE_LINE_FILTERS`` rule the canonical ledger uses for DFIA licences.
  * ``sold_value`` = sum of those lines' ``license_value``.
  * ``balance_value`` = ``license_value - sold_value`` (negative when over-sold;
    never clamped to zero).
  * ``sold_status``: NO when sold == 0; YES when balance <= 0; else PARTIAL.
  * PURCHASE lines never change sold status.

``sold_value``/``balance_value``/``sold_status`` are a denormalised cache on
``IncentiveLicense``. These tests read the stored cache (what the list filter
and table see) and the serializer (what the UI renders).
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import CompanyModel, PortModel
from apps.license.models import IncentiveLicense
from apps.license.serializers.incentive import IncentiveLicenseSerializer
from apps.trade.models import IncentiveTradeLine, LicenseTrade

User = get_user_model()
LIST_URL = "/api/incentive-licenses/"
_SEQ = iter(range(1, 10_000_000))


def _next():
    return next(_SEQ)


@pytest.fixture
def parties(db):
    n = _next()
    exporter = CompanyModel.objects.create(iec=f"8{n:09d}", name=f"Exporter {n}")
    buyer = CompanyModel.objects.create(iec=f"7{n:09d}", name=f"Buyer {n}")
    seller = CompanyModel.objects.create(iec=f"6{n:09d}", name=f"Seller {n}")
    port = PortModel.objects.create(code=f"P{n:05d}", name=f"Port {n}")
    return {"exporter": exporter, "buyer": buyer, "seller": seller, "port": port}


def make_licence(parties, value="1000.00", number=None):
    n = _next()
    return IncentiveLicense.objects.create(
        license_type="RODTEP",
        license_number=number or f"LIC{n:08d}",
        license_date=date(2025, 12, 19),
        exporter=parties["exporter"],
        port_code=parties["port"],
        license_value=Decimal(value),
        is_active=True,
    )


def make_trade(parties, direction, *, from_company=None, to_company=None):
    n = _next()
    return LicenseTrade.objects.create(
        from_company=from_company or parties["seller"],
        to_company=to_company or parties["buyer"],
        direction=direction,
        invoice_number=f"INV-{direction[:2]}-{n:06d}",
        invoice_date=date(2025, 12, 23),
        license_type="INCENTIVE",
    )


def add_line(trade, licence, value, amount=None):
    return IncentiveTradeLine.objects.create(
        trade=trade,
        incentive_license=licence,
        license_value=Decimal(value),
        rate_pct=Decimal("97.250"),
        amount_inr=Decimal(amount if amount is not None else value),
    )


def stored(licence):
    """What the list filter and table read: the stored cache, not the serializer."""
    licence.refresh_from_db()
    return licence.sold_value, licence.balance_value, licence.sold_status


@pytest.fixture
def api_client(db):
    user = User.objects.create_user(username=f"sold_status_{_next()}", password="x-test-only")
    user.is_superuser = True
    user.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


# ---------------------------------------------------------------------------
# 1–4: lifecycle transitions driven by SALE lines
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_new_licence_without_sale_is_available(parties):
    lic = make_licence(parties, "1000.00")
    assert stored(lic) == (Decimal("0.00"), Decimal("1000.00"), "NO")


@pytest.mark.django_db
def test_full_completed_sale_is_sold(parties):
    lic = make_licence(parties, "1000.00")
    add_line(make_trade(parties, "SALE"), lic, "1000.00")
    assert stored(lic) == (Decimal("1000.00"), Decimal("0.00"), "YES")


@pytest.mark.django_db
def test_partial_completed_sale_is_partial(parties):
    lic = make_licence(parties, "1000.00")
    add_line(make_trade(parties, "SALE"), lic, "400.00")
    assert stored(lic) == (Decimal("400.00"), Decimal("600.00"), "PARTIAL")


@pytest.mark.django_db
def test_multiple_partial_sales_that_exhaust_entitlement_are_sold(parties):
    lic = make_licence(parties, "1000.00")
    add_line(make_trade(parties, "SALE"), lic, "400.00")
    add_line(make_trade(parties, "SALE"), lic, "600.00")
    assert stored(lic) == (Decimal("1000.00"), Decimal("0.00"), "YES")


@pytest.mark.django_db
def test_over_sale_stays_sold_with_negative_balance_not_clamped(parties):
    lic = make_licence(parties, "1000.00")
    add_line(make_trade(parties, "SALE"), lic, "1150.00")
    assert stored(lic) == (Decimal("1150.00"), Decimal("-150.00"), "YES")


# ---------------------------------------------------------------------------
# 5: only completed SALE lines count; PURCHASE lines never change status
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_purchase_line_does_not_make_licence_sold(parties):
    lic = make_licence(parties, "1000.00")
    add_line(make_trade(parties, "PURCHASE"), lic, "1000.00")
    assert stored(lic) == (Decimal("0.00"), Decimal("1000.00"), "NO")


# ---------------------------------------------------------------------------
# 6–8: cancellation / reversal / transfer
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_deleting_sale_trade_reverses_sold_status(parties):
    lic = make_licence(parties, "1000.00")
    sale = make_trade(parties, "SALE")
    add_line(sale, lic, "1000.00")
    assert stored(lic)[2] == "YES"

    sale.delete()  # cascades to its lines

    assert stored(lic) == (Decimal("0.00"), Decimal("1000.00"), "NO")


@pytest.mark.django_db
def test_deleting_one_sale_line_recalculates_without_that_line(parties):
    lic = make_licence(parties, "1000.00")
    keep = add_line(make_trade(parties, "SALE"), lic, "400.00")  # noqa: F841
    drop = add_line(make_trade(parties, "SALE"), lic, "600.00")

    drop.delete()

    # Expected: only the 400.00 line remains. Before the fix the pre_delete
    # recompute still summed the 600.00 line and stored sold = 1000.00 YES.
    assert stored(lic) == (Decimal("400.00"), Decimal("600.00"), "PARTIAL")


@pytest.mark.django_db
def test_moving_a_sale_line_to_another_licence_updates_both(parties):
    first = make_licence(parties, "1000.00")
    second = make_licence(parties, "1000.00")
    line = add_line(make_trade(parties, "SALE"), first, "1000.00")
    assert stored(first)[2] == "YES"

    line.incentive_license = second
    line.save()

    assert stored(first) == (Decimal("0.00"), Decimal("1000.00"), "NO")
    assert stored(second) == (Decimal("1000.00"), Decimal("0.00"), "YES")


@pytest.mark.django_db
def test_completed_transfer_counts_once_as_sale_and_purchase_side_is_ignored(parties):
    lic = make_licence(parties, "1000.00")
    sale = make_trade(parties, "SALE")
    purchase = make_trade(parties, "PURCHASE")
    add_line(sale, lic, "1000.00")
    add_line(purchase, lic, "1000.00")  # reciprocal side of the same movement
    assert stored(lic) == (Decimal("1000.00"), Decimal("0.00"), "YES")


# ---------------------------------------------------------------------------
# 9–10: stale denormalised cache and duplicate references
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_blank_cache_with_verified_sale_is_repaired_by_recalculation(parties):
    lic = make_licence(parties, "1000.00")
    # Bulk insert bypasses signals, leaving a blank cache next to a real sale.
    IncentiveTradeLine.objects.bulk_create([
        IncentiveTradeLine(
            trade=make_trade(parties, "SALE"), incentive_license=lic,
            license_value=Decimal("1000.00"), rate_pct=Decimal("97.25"),
            amount_inr=Decimal("1000.00"),
        )
    ])
    assert stored(lic) == (Decimal("0.00"), Decimal("1000.00"), "NO")  # stale

    lic.update_sold_status()

    assert stored(lic) == (Decimal("1000.00"), Decimal("0.00"), "YES")


@pytest.mark.django_db
def test_duplicate_purchase_lines_do_not_inflate_sold_value(parties):
    lic = make_licence(parties, "1000.00")
    purchase = make_trade(parties, "PURCHASE")
    add_line(purchase, lic, "1000.00")
    add_line(purchase, lic, "1000.00")  # duplicate reference on the purchase side
    add_line(make_trade(parties, "SALE"), lic, "400.00")
    assert stored(lic) == (Decimal("400.00"), Decimal("600.00"), "PARTIAL")


# ---------------------------------------------------------------------------
# 11: concurrent sales must not leave a stale or partial total
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_concurrent_sale_lines_converge_to_full_sold_status(parties):
    lic = make_licence(parties, "1000.00")
    trades = [make_trade(parties, "SALE") for _ in range(2)]
    barrier = Barrier(2)

    def insert(trade):
        try:
            barrier.wait()
            with transaction.atomic():
                add_line(trade, lic, "500.00")
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(insert, trades))

    assert stored(lic) == (Decimal("1000.00"), Decimal("0.00"), "YES")


# ---------------------------------------------------------------------------
# 12: filters and pagination read the corrected status
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_status_filter_returns_records_after_sale_and_reversal(parties, api_client):
    lic = make_licence(parties, "1000.00")
    sale = make_trade(parties, "SALE")
    add_line(sale, lic, "1000.00")

    sold = api_client.get(LIST_URL, {"sold_status": "YES", "page_size": 200}).json()
    assert lic.id in [row["id"] for row in sold["results"]]

    sale.delete()

    available = api_client.get(LIST_URL, {"sold_status": "NO", "page_size": 200}).json()
    assert lic.id in [row["id"] for row in available["results"]]
    sold_again = api_client.get(LIST_URL, {"sold_status": "YES", "page_size": 200}).json()
    assert lic.id not in [row["id"] for row in sold_again["results"]]


# ---------------------------------------------------------------------------
# Serializer (UI) and stored cache must agree
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_serializer_status_matches_stored_cache(parties):
    lic = make_licence(parties, "1000.00")
    add_line(make_trade(parties, "SALE"), lic, "1000.00")
    lic.refresh_from_db()
    data = IncentiveLicenseSerializer(lic).data
    assert data["sold_status"] == lic.sold_status == "YES"
    assert data["sold_value"] == 1000.0
    assert data["balance_value"] == 0.0


@pytest.mark.django_db
def test_saving_a_stale_licence_instance_does_not_clobber_sale_cache(parties):
    lic = make_licence(parties, "1000.00")
    stale = IncentiveLicense.objects.get(pk=lic.pk)  # loaded before the sale
    add_line(make_trade(parties, "SALE"), lic, "1000.00")
    assert stored(lic)[2] == "YES"

    stale.notes = "edited after the sale"
    stale.save()  # must not write sold=0 / NO back from the stale instance

    assert stored(lic) == (Decimal("1000.00"), Decimal("0.00"), "YES")


# ---------------------------------------------------------------------------
# Confirmed production example: licence 2512026163 (database row id=1).
# Verified relationships: PURCHASE trade 87 (SUP/25-26/166DOM) and SALE trade 89
# (LML/2025-26/0094), each with a 768600.00 licence_value line on this licence.
# Production state before repair: sold_value 0.00, balance_value 0.00, NO.
# Lines are inserted with bulk_create to reproduce that stale cache state.
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_confirmed_example_2512026163_stale_cache_is_repaired_to_sold(parties, tmp_path):
    from django.core.management import call_command

    lic = make_licence(parties, "768600.00", number="2512026163")
    IncentiveTradeLine.objects.bulk_create([
        IncentiveTradeLine(
            trade=make_trade(parties, "PURCHASE"), incentive_license=lic,
            license_value=Decimal("768600.00"), rate_pct=Decimal("97.250"),
            amount_inr=Decimal("747464.00"),
        ),
        IncentiveTradeLine(
            trade=make_trade(parties, "SALE"), incentive_license=lic,
            license_value=Decimal("768600.00"), rate_pct=Decimal("99.000"),
            amount_inr=Decimal("760914.00"),
        ),
    ])
    # Reproduce the production cache exactly: sold 0, balance 0, status NO.
    IncentiveLicense.objects.filter(pk=lic.pk).update(balance_value=Decimal("0.00"))
    assert stored(lic) == (Decimal("0.00"), Decimal("0.00"), "NO")

    call_command(
        "reconcile_incentive_license_status", "--apply", "--licence", "2512026163",
        "--report-dir", str(tmp_path),
    )

    assert stored(lic) == (Decimal("768600.00"), Decimal("0.00"), "YES")
    assert IncentiveLicenseSerializer(lic).data["sold_status"] == "YES"
