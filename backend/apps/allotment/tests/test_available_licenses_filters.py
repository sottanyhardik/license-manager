"""
Regression tests for the Allotment "available-licenses" action's Available
Qty / Available Value filters (backend/apps/allotment/views_actions.py).

Bug: the Available Value min/max filters compared against the stale stored
`available_value` column instead of the live computed value
(`available_value_calculated`, surfaced via `available_value_bulk_map`) that
the UI actually displays as Available CIF FC -- silently excluding licenses
whose displayed value clearly satisfied the filter. Reproduced on license
0311050782: stored `available_value` = 7.43, live value = 154802.90. The
Available Quantity filter was NOT affected -- it reads the same stored
`available_quantity` column the UI displays -- but is covered here too as a
straightforward regression guard.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentModel
from apps.allotment.views_actions import AllotmentActionViewSet
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel

User = get_user_model()

LIVE_VALUE = Decimal("154802.90")
STALE_STORED_VALUE = Decimal("7.43")


def test_max_suggestion_is_limited_by_cif_at_unit_price():
    """Max must produce a compatible Qty/CIF pair, not independent maxima."""
    payload = AllotmentActionViewSet._position_payload(
        actual_qty=Decimal("15749.000"),
        actual_cif=Decimal("2066.75"),
        required_qty=Decimal("2077.000"),
        required_cif=Decimal("2066.75"),
        unit_price=Decimal("8.821"),
    )

    suggestion = payload["basis_options"]["actual"]
    assert suggestion["max_qty"] == "2077.000"
    assert suggestion["max_cif"] == "2066.75"
    assert suggestion["allocation_limit"]["paired_max_qty"] == "234.000"
    assert suggestion["allocation_limit"]["paired_max_cif"] == "2064.12"


@pytest.fixture
def allotment_client(db):
    user = User.objects.create_user(
        username="allotment-filter-tester",
        email="allotment-filter-tester@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="ALLOTMENT_MANAGER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def allotment_obj(db):
    company = CompanyModel.objects.create(iec="4099999999", name="Allotment Owner Co")
    return AllotmentModel.objects.create(company=company)


@pytest.fixture
def stale_value_item(db):
    """An import item whose STORED `available_value` (7.43) is stale
    relative to its LIVE computed value (154802.90) -- mirrors the reported
    production bug on license 0311050782 / import item serial 13."""
    company = CompanyModel.objects.create(iec="4011050782", name="Allotment Filter Test Co")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="0311050782-TEST",
        license_date=date.today() - timedelta(days=60),
        license_expiry_date=date.today() + timedelta(days=90),
        exporter=company,
    )
    return LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=13,
        description="Milk Products",
        quantity=Decimal("50000.000"),
        available_quantity=Decimal("36017.670"),
        available_value=STALE_STORED_VALUE,
        condition_type="",
    )


def _mock_bulk_map(item_id, live_value):
    def _map(items):
        return {i.id: live_value for i in items if i.id == item_id}
    return _map


@pytest.fixture(autouse=True)
def live_actual_cif(monkeypatch):
    """The quantity-only fixtures still model a usable live CIF position.
    Value-specific tests replace this with their exact live balance map."""
    monkeypatch.setattr(
        "apps.license.services.condition_pool.available_value_bulk_map",
        lambda items: {item.id: LIVE_VALUE for item in items},
    )


def _get_available_licenses(client, allotment_obj, **params):
    url = f"/api/allotment-actions/{allotment_obj.id}/available-licenses/"
    params.setdefault("debit_based_on", "ACTUAL")
    return client.get(url, params)


class TestAvailableQuantityFilter:
    """available_quantity_gte/lte reads the same stored column the UI
    displays for Available Qty -- these are straightforward >=/<= checks,
    not part of the stale-value bug, but guarded here regardless."""

    def test_min_qty_below_available_quantity_includes_item(self, allotment_client, allotment_obj, stale_value_item):
        resp = _get_available_licenses(allotment_client, allotment_obj, available_quantity_gte="100")
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.data["available_items"]]
        assert stale_value_item.id in ids

    def test_min_qty_above_available_quantity_excludes_item(self, allotment_client, allotment_obj, stale_value_item):
        resp = _get_available_licenses(allotment_client, allotment_obj, available_quantity_gte="36018")
        ids = [row["id"] for row in resp.data["available_items"]]
        assert stale_value_item.id not in ids

    def test_max_qty_above_available_quantity_includes_item(self, allotment_client, allotment_obj, stale_value_item):
        resp = _get_available_licenses(allotment_client, allotment_obj, available_quantity_lte="50000")
        ids = [row["id"] for row in resp.data["available_items"]]
        assert stale_value_item.id in ids

    def test_max_qty_below_available_quantity_excludes_item(self, allotment_client, allotment_obj, stale_value_item):
        resp = _get_available_licenses(allotment_client, allotment_obj, available_quantity_lte="30000")
        ids = [row["id"] for row in resp.data["available_items"]]
        assert stale_value_item.id not in ids

    def test_zero_live_actual_cif_removes_candidate_server_side(self, allotment_client, allotment_obj, stale_value_item):
        with patch(
            "apps.license.services.condition_pool.available_value_bulk_map",
            side_effect=_mock_bulk_map(stale_value_item.id, Decimal("0.00")),
        ):
            resp = _get_available_licenses(allotment_client, allotment_obj)
        assert resp.status_code == 200
        assert stale_value_item.id not in [row["id"] for row in resp.data["available_items"]]


class TestAvailableValueFilterUsesLiveValue:
    """The core regression: available_value_gte/lte must compare against
    the LIVE computed value (what available_value_bulk_map returns / what
    the UI displays), never the stale stored `available_value` column."""

    def test_min_value_includes_item_when_live_value_clears_bar_even_though_stored_value_is_stale_and_low(
        self, allotment_client, allotment_obj, stale_value_item,
    ):
        with patch(
            "apps.license.services.condition_pool.available_value_bulk_map",
            side_effect=_mock_bulk_map(stale_value_item.id, LIVE_VALUE),
        ):
            resp = _get_available_licenses(allotment_client, allotment_obj, available_value_gte="1000")
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.data["available_items"]]
        # The OLD buggy filter compared 1000 against the stored 7.43 and
        # excluded this item. The live value (154802.90) clears 1000, so the
        # fixed filter must include it.
        assert stale_value_item.id in ids

    def test_min_value_above_live_value_excludes_item(self, allotment_client, allotment_obj, stale_value_item):
        with patch(
            "apps.license.services.condition_pool.available_value_bulk_map",
            side_effect=_mock_bulk_map(stale_value_item.id, LIVE_VALUE),
        ):
            resp = _get_available_licenses(allotment_client, allotment_obj, available_value_gte="200000")
        ids = [row["id"] for row in resp.data["available_items"]]
        assert stale_value_item.id not in ids

    def test_max_value_excludes_item_when_live_value_exceeds_cap_even_though_stored_value_would_pass(
        self, allotment_client, allotment_obj, stale_value_item,
    ):
        with patch(
            "apps.license.services.condition_pool.available_value_bulk_map",
            side_effect=_mock_bulk_map(stale_value_item.id, LIVE_VALUE),
        ):
            resp = _get_available_licenses(allotment_client, allotment_obj, available_value_lte="100000")
        ids = [row["id"] for row in resp.data["available_items"]]
        # The OLD buggy filter compared 100000 against the stored 7.43 and
        # would have included this item. The live value (154802.90) exceeds
        # the cap, so the fixed filter must exclude it.
        assert stale_value_item.id not in ids

    def test_max_value_above_live_value_includes_item(self, allotment_client, allotment_obj, stale_value_item):
        with patch(
            "apps.license.services.condition_pool.available_value_bulk_map",
            side_effect=_mock_bulk_map(stale_value_item.id, LIVE_VALUE),
        ):
            resp = _get_available_licenses(allotment_client, allotment_obj, available_value_lte="200000")
        ids = [row["id"] for row in resp.data["available_items"]]
        assert stale_value_item.id in ids

    def test_malformed_value_param_is_ignored_not_500(self, allotment_client, allotment_obj, stale_value_item):
        with patch(
            "apps.license.services.condition_pool.available_value_bulk_map",
            side_effect=_mock_bulk_map(stale_value_item.id, LIVE_VALUE),
        ):
            resp = _get_available_licenses(allotment_client, allotment_obj, available_value_gte="not-a-number")
        assert resp.status_code == 200
