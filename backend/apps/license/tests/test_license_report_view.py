from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import pytest

from apps.core.models import (
    CompanyModel,
    HeadSIONNormsModel,
    HSCodeModel,
    NotificationNumber,
    PurchaseStatus,
    SchemeCode,
    SionNormClassModel,
)
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel


User = get_user_model()


@pytest.fixture
def license_viewer_client(db):
    user = User.objects.create_user(
        username="license-report-viewer",
        email="license-report-viewer@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="LICENSE_VIEWER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def report_masters(db):
    head_norm = HeadSIONNormsModel.objects.create(name="E Norms")
    return {
        "parle": CompanyModel.objects.create(iec="1111111111", name="Parle Products Pvt Ltd"),
        "other": CompanyModel.objects.create(iec="2222222222", name="Other Foods Pvt Ltd"),
        "notification": NotificationNumber.objects.create(code="N24", label="Notification 2024"),
        "scheme": SchemeCode.objects.create(code="DFIA", label="DFIA"),
        "purchase_status": PurchaseStatus.objects.create(code="GE", label="GE Purchase"),
        "hs_code": HSCodeModel.objects.create(hs_code="19053100", product_description="Biscuits"),
        "norm_class": SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E1"),
    }


def _create_report_license(license_number, exporter, masters, *, expired=False, balance=Decimal("250.00")):
    license_obj = LicenseDetailsModel.objects.create(
        license_number=license_number,
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30) if not expired else date.today() - timedelta(days=1),
        exporter=exporter,
        notification_number=masters["notification"],
        scheme_code=masters["scheme"],
        purchase_status=masters["purchase_status"],
        file_number=f"FILE-{license_number}",
    )
    LicenseExportItemModel.objects.create(
        license=license_obj,
        description="Export Biscuits",
        norm_class=masters["norm_class"],
        cif_fc=Decimal("100.25"),
        cif_inr=Decimal("8400.00"),
    )
    LicenseExportItemModel.objects.create(
        license=license_obj,
        description="Export Biscuits 2",
        norm_class=masters["norm_class"],
        cif_fc=Decimal("50.75"),
        cif_inr=Decimal("4200.00"),
    )
    LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Import Sugar",
        hs_code=masters["hs_code"],
        quantity=Decimal("10.000"),
        cif_fc=Decimal("15.50"),
        cif_inr=Decimal("1300.00"),
    )
    license_obj.balance.balance_cif = balance
    license_obj.balance.save(update_fields=["balance_cif"])
    return license_obj


@pytest.mark.django_db
def test_parle_license_report_returns_grouped_json(license_viewer_client, report_masters):
    _create_report_license("PARLE-REPORT-001", report_masters["parle"], report_masters)
    _create_report_license("OTHER-REPORT-001", report_masters["other"], report_masters)

    response = license_viewer_client.get(reverse("license:licenses-parle-license-report"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["summary"]["total_licenses"] == 1
    assert response.data["summary"]["grand_total_cif"] == 151.0
    group = response.data["groups"][0]
    assert group["notification_number"] == "N24"
    license_data = group["licenses"][0]
    assert license_data["license_number"] == "PARLE-REPORT-001"
    assert license_data["purchase_status"] == "GE"
    assert license_data["purchase_status_label"] == "GE Purchase"
    assert license_data["export_items"][0]["norm_class"] == "E1"
    assert license_data["import_items"][0]["hs_code"] == "19053100"


@pytest.mark.django_db
def test_parle_license_report_validates_query_params(license_viewer_client):
    response = license_viewer_client.get(
        reverse("license:licenses-parle-license-report"),
        {"exporter": "not-an-id", "is_expired": "definitely"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "exporter" in response.data
    assert "is_expired" in response.data


@pytest.mark.django_db
def test_parle_license_report_filters_boolean_params(license_viewer_client, report_masters):
    active = _create_report_license(
        "PARLE-ACTIVE-001",
        report_masters["parle"],
        report_masters,
        expired=False,
        # Cache is deliberately stale/irrelevant here -- the `is_null`
        # filter must key off the LIVE balance (BL-LEDGER-02), not this
        # cached column. The license's real export CIF (bumped below)
        # drives whether it clears the >= 200 threshold, not this value.
        balance=Decimal("250.00"),
    )
    # Bump this license's live balance (Opening Balance == total export
    # CIF, no debits/allotments/BOEs) comfortably above the 200 threshold
    # so `is_null=false` including it is actually driven by real data, not
    # by the stale cache.
    LicenseExportItemModel.objects.create(
        license=active,
        description="Export Biscuits Bonus",
        norm_class=report_masters["norm_class"],
        cif_fc=Decimal("200.00"),
        cif_inr=Decimal("16000.00"),
    )
    _create_report_license(
        "PARLE-EXPIRED-001",
        report_masters["parle"],
        report_masters,
        expired=True,
        balance=Decimal("100.00"),
    )

    response = license_viewer_client.get(
        reverse("license:licenses-parle-license-report"),
        {"is_expired": "false", "is_null": "false", "exporter": report_masters["parle"].id},
    )

    assert response.status_code == status.HTTP_200_OK
    licenses = response.data["groups"][0]["licenses"]
    assert [row["id"] for row in licenses] == [active.id]


@pytest.mark.django_db
def test_parle_license_report_is_null_filter_ignores_stale_cache(license_viewer_client, report_masters):
    """BL-LEDGER-02 regression: the `is_null` (balance threshold) filter
    must be resolved against the LIVE batched balance, never the cached
    `LicenseBalance.balance_cif` column -- which reconciliation allocation
    writes never refresh and can therefore be stale in EITHER direction.

    - `stale_low`: cache says 50 (< 200) but live balance (export CIF,
      no debits) is 300 (>= 200) -- must be INCLUDED by is_null=false.
    - `stale_high`: cache says 500 (>= 200) but live balance is only 50
      (< 200) -- must be EXCLUDED by is_null=false.

    If the endpoint still trusted the cache, both results would flip.
    """
    stale_low = _create_report_license(
        "PARLE-STALE-LOW-001", report_masters["parle"], report_masters, balance=Decimal("50.00"),
    )
    LicenseExportItemModel.objects.create(
        license=stale_low, description="Bonus", norm_class=report_masters["norm_class"],
        cif_fc=Decimal("149.00"), cif_inr=Decimal("0"),
    )  # total export CIF: 100.25 + 50.75 + 149.00 = 300.00 (live balance)

    stale_high = _create_report_license(
        "PARLE-STALE-HIGH-001", report_masters["parle"], report_masters, balance=Decimal("500.00"),
    )
    # Zero out this license's export items so its live balance is small,
    # deliberately diverging from the stale, much-higher cached value.
    LicenseExportItemModel.objects.filter(license=stale_high).delete()
    LicenseExportItemModel.objects.create(
        license=stale_high, description="Tiny", norm_class=report_masters["norm_class"],
        cif_fc=Decimal("50.00"), cif_inr=Decimal("0"),
    )

    response = license_viewer_client.get(
        reverse("license:licenses-parle-license-report"),
        {"is_null": "false", "exporter": report_masters["parle"].id},
    )
    assert response.status_code == status.HTTP_200_OK
    returned_ids = {
        row["id"] for group in response.data["groups"] for row in group["licenses"]
    }
    assert stale_low.id in returned_ids
    assert stale_high.id not in returned_ids


@pytest.mark.django_db
def test_parle_license_report_balance_cif_matches_live_calc_with_allocation(license_viewer_client, report_masters):
    """BL-LEDGER-02 regression: the displayed `balance_cif` must match the
    live-computed Financial Available Balance -- including when a
    reconciliation allocation exists (`create_invoice_boe_allocation`),
    which never refreshes the cached `LicenseBalance.balance_cif` column.
    """
    from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
    from apps.core.constants import DEBIT
    from apps.license.services.balance_calculator import LicenseBalanceCalculator
    from apps.reconciliation.services import allocation_service
    from apps.trade.models import LicenseTrade, LicenseTradeLine

    license_obj = _create_report_license(
        "PARLE-ALLOC-001", report_masters["parle"], report_masters, balance=Decimal("999.99"),
    )
    # Opening balance == total export CIF == 151.00 (100.25 + 50.75), no
    # purchase/hidden BOE.
    import_item = license_obj.import_license.first()

    boe = BillOfEntryModel.objects.create(
        company=report_masters["parle"],
        bill_of_entry_number="BOE-ALLOC-001",
        bill_of_entry_date=date.today(),
        exchange_rate=Decimal("84.50"),
    )
    row = RowDetails.objects.create(
        bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
        cif_fc=Decimal("100.00"), cif_inr=Decimal("8450.00"), qty=Decimal("1.000"),
    )
    trade = LicenseTrade.objects.create(
        direction=LicenseTrade.DIR_SALE, from_company=report_masters["parle"],
        invoice_number="INV-ALLOC-001", invoice_date=date.today(),
    )
    trade_line = LicenseTradeLine.objects.create(
        trade=trade, sr_number=import_item, description="Sale line",
        mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=Decimal("100.00"),
        cif_inr=Decimal("8450.00"), qty_kg=Decimal("1.0000"),
    )
    # This is the exact allocation-service call BL-LEDGER-02 identified as
    # never refreshing `LicenseBalance.balance_cif` -- fully matches the BOE
    # row to the sale line so `calculate_debit()` nets it to 0 and only the
    # matching sale line (via `calculate_trade()`) debits the license.
    allocation_service.create_invoice_boe_allocation(
        trade_line, row, qty=Decimal("0"), cif_fc=Decimal("100.00"),
        cif_inr=Decimal("8450.00"), user=None,
    )

    expected_live_balance = LicenseBalanceCalculator.calculate_financial_balance(license_obj)
    assert expected_live_balance == Decimal("51.00")  # 151.00 - 100.00 (sale) - 0 (fully allocated BOE)

    # The cached column drifts from this true live value precisely because
    # BL-LEDGER-02's allocation functions never refresh it: other write
    # paths (the RowDetails/LicenseTrade post_save signals) DO refresh the
    # cache, but only against the pre-allocation state (BOE row still
    # counted as a fully unmatched debit) -- so by the time the allocation
    # nets it out, the cache is stuck below the true post-allocation
    # balance. Assert the drift actually exists (cache != live) so this
    # test would fail loudly if some unrelated change made them coincide
    # by accident, then assert the endpoint reports the LIVE value.
    license_obj.balance.refresh_from_db(fields=["balance_cif"])
    assert license_obj.balance.balance_cif != expected_live_balance

    response = license_viewer_client.get(
        reverse("license:licenses-parle-license-report"),
        {"exporter": report_masters["parle"].id},
    )
    assert response.status_code == status.HTTP_200_OK
    row_data = next(
        r for group in response.data["groups"] for r in group["licenses"] if r["id"] == license_obj.id
    )
    assert row_data["balance_cif"] == pytest.approx(float(expected_live_balance))


@pytest.mark.django_db
def test_parle_license_report_query_count_stays_flat(license_viewer_client, report_masters):
    """BL-LEDGER-02 regression: swapping cached-column reads for the batched
    `calculate_financial_balance_for_licenses()` call must NOT reintroduce
    an N+1 -- query count should stay flat as the number of licenses grows,
    not scale linearly with it."""
    from django.test.utils import CaptureQueriesContext
    from django.db import connection

    for i in range(5):
        _create_report_license(f"PARLE-QCOUNT-{i:03d}", report_masters["parle"], report_masters)

    with CaptureQueriesContext(connection) as ctx:
        response = license_viewer_client.get(
            reverse("license:licenses-parle-license-report"),
            {"exporter": report_masters["parle"].id},
        )
    assert response.status_code == status.HTTP_200_OK
    small_query_count = len(ctx.captured_queries)

    for i in range(5, 15):
        _create_report_license(f"PARLE-QCOUNT-{i:03d}", report_masters["parle"], report_masters)

    with CaptureQueriesContext(connection) as ctx:
        response = license_viewer_client.get(
            reverse("license:licenses-parle-license-report"),
            {"exporter": report_masters["parle"].id},
        )
    assert response.status_code == status.HTTP_200_OK
    larger_query_count = len(ctx.captured_queries)

    # Query count must not grow with the number of licenses (batched calc,
    # not per-license loop) -- allow a little slack but reject anything
    # that looks like O(N) growth.
    assert larger_query_count <= small_query_count + 3, (
        f"query count grew from {small_query_count} (5 licenses) to "
        f"{larger_query_count} (15 licenses) -- looks like an N+1"
    )
