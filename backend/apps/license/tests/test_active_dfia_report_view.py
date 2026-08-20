"""
Tests for the Active DFIA Report (backend/apps/license/views/active_dfia_report.py).

BL-LEDGER-02 regression coverage: this report used to read the cached
`LicenseBalance.balance_cif` column for both display (`balance_cif`,
`total_debits`, `wastage_cif`) and the `is_null` (>=200 / <200) filter.
That cache is only refreshed by a background task/manual "Update Balance"
trigger, and the reconciliation allocation functions
(`create_invoice_boe_allocation` etc.) never touch it -- so it can drift
from the true live balance. The view was switched to read the LIVE,
batched `LicenseBalanceCalculator.calculate_financial_balance_for_licenses()`
for both concerns, matching the convention already used by the License
List / Item Report / Item Pivot Report views.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import pytest

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.reconciliation.services import allocation_service
from apps.trade.models import LicenseTrade, LicenseTradeLine


User = get_user_model()

ACTIVE_DFIA_URL_NAME = "license:licenses-active-dfia-report"


def _stub_get_item_data(self, item_name):
    return {"available_quantity_sum": Decimal("0"), "quantity_sum": Decimal("0")}


_STUB_BISCUITS_CALC = {
    "cif_juice": Decimal("0"), "restricted_value": Decimal("0"),
    "qty_swp": Decimal("0"), "cif_swp": Decimal("0"),
    "qty_cheese": Decimal("0"), "cif_cheese": Decimal("0"),
    "qty_wpc": Decimal("0"), "cif_wpc": Decimal("0"),
    "veg_oil": {"rbd_oil": Decimal("0"), "cif_rbd_oil": Decimal("0"), "pko_oil": Decimal("0"),
                "cif_pko_oil": Decimal("0"), "olive_oil": Decimal("0"), "cif_olive_oil": Decimal("0"),
                "pomace_oil": Decimal("0"), "cif_pomace_oil": Decimal("0")},
    "available_value": Decimal("0"),
}


@pytest.fixture(autouse=True)
def _workaround_broken_get_item_data():
    """
    PRE-EXISTING, UNRELATED bugs (not part of BL-LEDGER-02, discovered
    while writing this suite) in `apps/license/models/core.py` that make
    `active_dfia_report` completely non-functional -- for ANY license,
    independent of the BL-LEDGER-02 fix:

    1. `LicenseDetailsModel.get_item_data()`'s restricted-item branch does
       `(self.get_per_cif or {}).get(...)` -- but `get_per_cif` is a plain
       method (its own docstring: "Removed @cached_property to ensure
       fresh calculation after updates"), not a property, so the
       un-called bound method (always truthy) is passed to `.get(...)`
       and raises `AttributeError`. Same bug at `core.py:650`
       (`cif_value_balance_biscuits`).
    2. `import_license_grouped` (backing `get_item_data()`'s non-restricted
       branch) does `.values(..., "items__unit_price")`, but
       `ItemNameModel` no longer has a `unit_price` field -- raises
       `FieldError`.

    `active_dfia_report` calls `get_item_by_name`/`get_item_by_head`
    (-> `get_item_data`) unconditionally for every license, so either bug
    alone 500s every request. Fixing this shared, high-blast-radius
    core-model method is out of scope for this batch (see CLAUDE.md's
    guidance on `core/models.py` changes -- `get_per_cif` alone has other
    call sites, e.g. `item_report.py:64`, with the same latent bug), so
    this fixture stubs `get_item_data` and `cif_value_balance_biscuits`
    -- ONLY in these tests -- to their own already-existing "nothing to
    report" defaults, so the BL-LEDGER-02 read-side fix can actually be
    exercised end-to-end. Reported separately as a follow-up finding.
    """
    with patch.object(LicenseDetailsModel, "get_item_data", new=_stub_get_item_data), \
         patch.object(
             LicenseDetailsModel, "cif_value_balance_biscuits",
             new_callable=PropertyMock, return_value=_STUB_BISCUITS_CALC,
         ):
        yield


@pytest.fixture
def license_viewer_client(db):
    """The Active DFIA report is a reporting surface, not licence CRUD.

    ``LICENSE_VIEWER`` may read its tenant-scoped CRUD rows but must not use
    this cross-company report action.  It is intentionally exercised through
    the established report role below.
    """
    user = User.objects.create_user(
        username="active-dfia-viewer",
        email="active-dfia-viewer@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="REPORT_VIEWER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def _client_for(*, username, company=None, role=None, superuser=False):
    if superuser:
        user = User.objects.create_superuser(
            username=username,
            password="RoleP@ssw0rd123",
            company=company,
        )
    else:
        user = User.objects.create_user(
            username=username,
            password="RoleP@ssw0rd123",
            company=company,
        )
    if role:
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def dfia_masters(db):
    return {
        "parle": CompanyModel.objects.create(iec="5111111111", name="Parle DFIA Foods"),
    }


def _make_dfia_license(number, exporter, *, export_cif=Decimal("151.00"), balance=Decimal("0")):
    license_obj = LicenseDetailsModel.objects.create(
        license_number=number,
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30),
        exporter=exporter,
    )
    LicenseExportItemModel.objects.create(
        license=license_obj,
        description="Export item",
        cif_fc=export_cif,
        cif_inr=export_cif * Decimal("84.5"),
    )
    LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Import item",
        quantity=Decimal("10.000"),
        available_quantity=Decimal("10.000"),
    )
    license_obj.balance.balance_cif = balance
    license_obj.balance.save(update_fields=["balance_cif"])
    return license_obj


@pytest.mark.django_db
def test_active_dfia_report_balance_cif_uses_live_calc_not_cache(license_viewer_client, dfia_masters):
    license_obj = _make_dfia_license(
        "DFIA-LIVE-001", dfia_masters["parle"], export_cif=Decimal("151.00"), balance=Decimal("999.99"),
    )
    expected_live_balance = LicenseBalanceCalculator.calculate_financial_balance(license_obj)
    assert expected_live_balance == Decimal("151.00")
    assert license_obj.balance.balance_cif == Decimal("999.99")  # cache deliberately stale

    response = license_viewer_client.get(
        reverse(ACTIVE_DFIA_URL_NAME), {"exporter": dfia_masters["parle"].id, "is_null": "all"},
    )
    assert response.status_code == status.HTTP_200_OK
    licenses = response.data["groups"][0]["notifications"][0]["licenses"]
    row = next(r for r in licenses if r["id"] == license_obj.id)
    assert row["balance_cif"] == pytest.approx(float(expected_live_balance))
    assert row["total_debits"] == pytest.approx(0.0)
    assert row["wastage_cif"] == pytest.approx(float(expected_live_balance) * 0.10)


@pytest.mark.django_db
def test_active_dfia_report_balance_matches_live_calc_with_allocation(license_viewer_client, dfia_masters):
    """BL-LEDGER-02: displayed balance_cif must reflect a reconciliation
    allocation's effect even though `create_invoice_boe_allocation` never
    refreshes the cached column."""
    license_obj = _make_dfia_license(
        "DFIA-ALLOC-001", dfia_masters["parle"], export_cif=Decimal("151.00"), balance=Decimal("999.99"),
    )
    import_item = license_obj.import_license.first()

    boe = BillOfEntryModel.objects.create(
        company=dfia_masters["parle"], bill_of_entry_number="BOE-DFIA-ALLOC-001",
        bill_of_entry_date=date.today(), exchange_rate=Decimal("84.50"),
    )
    row = RowDetails.objects.create(
        bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
        cif_fc=Decimal("100.00"), cif_inr=Decimal("8450.00"), qty=Decimal("1.000"),
    )
    trade = LicenseTrade.objects.create(
        direction=LicenseTrade.DIR_SALE, from_company=dfia_masters["parle"],
        invoice_number="INV-DFIA-ALLOC-001", invoice_date=date.today(),
    )
    trade_line = LicenseTradeLine.objects.create(
        trade=trade, sr_number=import_item, description="Sale line",
        mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=Decimal("100.00"),
        cif_inr=Decimal("8450.00"), qty_kg=Decimal("1.0000"),
    )
    allocation_service.create_invoice_boe_allocation(
        trade_line, row, qty=Decimal("0"), cif_fc=Decimal("100.00"),
        cif_inr=Decimal("8450.00"), user=None,
    )

    expected_live_balance = LicenseBalanceCalculator.calculate_financial_balance(license_obj)
    assert expected_live_balance == Decimal("51.00")

    response = license_viewer_client.get(
        reverse(ACTIVE_DFIA_URL_NAME), {"exporter": dfia_masters["parle"].id, "is_null": "all"},
    )
    assert response.status_code == status.HTTP_200_OK
    licenses = response.data["groups"][0]["notifications"][0]["licenses"]
    row_data = next(r for r in licenses if r["id"] == license_obj.id)
    assert row_data["balance_cif"] == pytest.approx(float(expected_live_balance))


@pytest.mark.django_db
def test_active_dfia_report_is_null_filter_ignores_stale_cache(license_viewer_client, dfia_masters):
    """`is_null=false` (default) must include/exclude licenses based on the
    LIVE balance, not the cached column -- deliberately set up so the
    cache alone would give the WRONG answer in each direction."""
    stale_low = _make_dfia_license(
        "DFIA-STALE-LOW-001", dfia_masters["parle"], export_cif=Decimal("300.00"), balance=Decimal("50.00"),
    )
    stale_high = _make_dfia_license(
        "DFIA-STALE-HIGH-001", dfia_masters["parle"], export_cif=Decimal("50.00"), balance=Decimal("500.00"),
    )

    response = license_viewer_client.get(
        reverse(ACTIVE_DFIA_URL_NAME), {"exporter": dfia_masters["parle"].id, "is_null": "false"},
    )
    assert response.status_code == status.HTTP_200_OK
    returned_ids = {
        lic["id"]
        for group in response.data["groups"]
        for notif in group["notifications"]
        for lic in notif["licenses"]
    }
    assert stale_low.id in returned_ids
    assert stale_high.id not in returned_ids


@pytest.mark.django_db
def test_active_dfia_report_empty_exporter_filter_has_stable_zero_summary(
    license_viewer_client, dfia_masters,
):
    """An empty valid filter result is a report, not an internal error."""
    other_exporter = CompanyModel.objects.create(
        iec="5222222222", name="Other DFIA Exporter",
    )
    _make_dfia_license("DFIA-OTHER-001", other_exporter, export_cif=Decimal("400.00"))

    response = license_viewer_client.get(
        reverse(ACTIVE_DFIA_URL_NAME),
        {"exporter": dfia_masters["parle"].id, "is_null": "all"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["groups"] == []
    assert response.data["grand_totals"] == {}
    assert response.data["summary"] == {
        "total_licenses": 0,
        "total_sion_norms": 0,
        "total_cif": 0,
        "balance_cif": 0,
    }


@pytest.mark.django_db
def test_active_dfia_report_rejects_invalid_exporter_filter(license_viewer_client):
    response = license_viewer_client.get(
        reverse(ACTIVE_DFIA_URL_NAME), {"exporter": "not-an-id"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["exporter"] == "Invalid exporter ID."


@pytest.mark.django_db
def test_active_dfia_report_uses_report_permission_and_filtered_response_scope(dfia_masters):
    """Only documented report-capable roles may use this cross-company action.

    Report roles intentionally have reporting visibility across companies;
    the explicit exporter filter must still return only that exporter's rows.
    A licence viewer or trade viewer cannot infer licence data merely by
    knowing the report route or another company's exporter id.
    """
    selected = _make_dfia_license("DFIA-AUTH-SELECTED", dfia_masters["parle"])
    other_exporter = CompanyModel.objects.create(iec="5333333333", name="Other DFIA Exporter")
    other = _make_dfia_license("DFIA-AUTH-OTHER", other_exporter)
    buyer = CompanyModel.objects.create(iec="5444444444", name="DFIA Buyer")
    seller = CompanyModel.objects.create(iec="5555555555", name="DFIA Seller")
    unrelated = CompanyModel.objects.create(iec="5666666666", name="Unrelated Company")
    params = {"exporter": dfia_masters["parle"].id, "is_null": "all"}

    owner_client = _client_for(
        username="active-dfia-owner", company=dfia_masters["parle"], role="LICENSE_MANAGER",
    )
    buyer_client = _client_for(username="active-dfia-buyer", company=buyer, role="TRADE_MANAGER")
    seller_client = _client_for(username="active-dfia-seller", company=seller, role="TRADE_VIEWER")
    unrelated_client = _client_for(
        username="active-dfia-unrelated", company=unrelated, role="LICENSE_VIEWER",
    )
    admin_client = _client_for(username="active-dfia-admin", superuser=True)

    for client in (owner_client, buyer_client, admin_client):
        response = client.get(reverse(ACTIVE_DFIA_URL_NAME), params)
        assert response.status_code == status.HTTP_200_OK
        returned_numbers = {
            row["license_number"]
            for group in response.data["groups"]
            for notification in group["notifications"]
            for row in notification["licenses"]
        }
        assert returned_numbers == {selected.license_number}
        assert other.license_number not in str(response.data)

    for client in (seller_client, unrelated_client):
        response = client.get(reverse(ACTIVE_DFIA_URL_NAME), params)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert selected.license_number not in str(response.data)

    anonymous = APIClient().get(reverse(ACTIVE_DFIA_URL_NAME), params)
    assert anonymous.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}
    assert selected.license_number not in str(anonymous.data)


@pytest.mark.django_db
def test_active_dfia_report_query_count_stays_flat(license_viewer_client, dfia_masters):
    """Batched live-balance calc must not reintroduce an N+1: query count
    should stay flat as the number of licenses grows.

    This isolates JUST the BL-LEDGER-02 batched-calc fix by also patching
    `get_per_cif()` (used for the unrelated `ten_percent_balance` figure)
    to return `None` -- what it already returns for these norm-class-less
    fixtures once actually invoked. `get_per_cif()` itself is a SEPARATE,
    pre-existing, non-batched, per-license-expensive method (it calls
    `self.get_balance_cif`, another live per-object calculation, for
    EVERY license) that was never actually reached before this task's
    incidental `get_per_cif` / `get_per_cif()` call-site fix -- because the
    missing `()` bug short-circuited it. It is a real N+1 in its own
    right, but a distinct one from what BL-LEDGER-02 is about; reported
    separately as a follow-up finding rather than silently masked here.
    """
    for i in range(5):
        _make_dfia_license(f"DFIA-QCOUNT-{i:03d}", dfia_masters["parle"])

    with patch.object(LicenseDetailsModel, "get_per_cif", return_value=None):
        with CaptureQueriesContext(connection) as ctx:
            response = license_viewer_client.get(
                reverse(ACTIVE_DFIA_URL_NAME), {"exporter": dfia_masters["parle"].id, "is_null": "all"},
            )
        assert response.status_code == status.HTTP_200_OK
        small_query_count = len(ctx.captured_queries)

        for i in range(5, 15):
            _make_dfia_license(f"DFIA-QCOUNT-{i:03d}", dfia_masters["parle"])

        with CaptureQueriesContext(connection) as ctx:
            response = license_viewer_client.get(
                reverse(ACTIVE_DFIA_URL_NAME), {"exporter": dfia_masters["parle"].id, "is_null": "all"},
            )
        assert response.status_code == status.HTTP_200_OK
        larger_query_count = len(ctx.captured_queries)

    # Two OTHER pre-existing, unrelated per-license queries remain in this
    # view regardless of the BL-LEDGER-02 fix -- `license_obj.export_license
    # .aggregate(...)` for `total_cif` bypasses the `export_license` prefetch
    # cache, and `get_item_by_head()` -> `import_license_group_grouped`
    # (a separate cached_property) queries once per license too. Both are
    # small, real, out-of-scope N+1s (~2 queries/license observed), flagged
    # as a follow-up finding. The threshold below is deliberately generous
    # enough to tolerate that already-present ~2/license cost while still
    # failing hard if the BL-LEDGER-02 batched calc itself regresses into a
    # per-license loop (which would add several MORE queries per license on
    # top, per the audit's ~11.8 queries/license naive-loop measurement).
    per_license_budget = 3
    extra_licenses = 10
    assert larger_query_count <= small_query_count + (extra_licenses * per_license_budget), (
        f"query count grew from {small_query_count} (5 licenses) to "
        f"{larger_query_count} (15 licenses) -- looks like an N+1 well beyond "
        f"the known, separate ~2/license cost this test already tolerates"
    )
