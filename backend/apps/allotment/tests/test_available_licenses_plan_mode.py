"""
Tests for the Allotment "available-licenses" action's Plan mode
(`debit_based_on=plan`) — backend/apps/allotment/views_actions.py's
`_available_licenses_plan_mode`.

Plan mode switches the grid to one row per `LicenseItemPlan` line instead of
per `LicenseImportItemsModel` row, so an import item split across multiple
planned items (e.g. E132 Auto-Plan's Vegetable Oil -> PKO + Cheese) shows as
separate rows, each with only its own planned quantity/value — never the
parent import item's full amount. Actual mode (the default) must remain
byte-for-byte unchanged; see test_available_licenses_filters.py for that
existing coverage, which this file does not duplicate.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentModel
from apps.core.models import CompanyModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan

User = get_user_model()


@pytest.fixture
def allotment_client(db):
    user = User.objects.create_user(
        username="allotment-plan-mode-tester",
        email="allotment-plan-mode-tester@example.com",
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
    company = CompanyModel.objects.create(iec="4088888888", name="Plan Mode Allotment Owner Co")
    return AllotmentModel.objects.create(company=company)


@pytest.fixture
def item_names(db):
    return {
        name: ItemNameModel.objects.create(name=name)
        for name in ("PKO - PLANMODE-TEST", "CHEESE - PLANMODE-TEST", "NUTS - PLANMODE-TEST")
    }


@pytest.fixture
def veg_oil_split(db, item_names):
    """One 100kg Vegetable Oil import item, planned as PKO 30kg / Cheese 70kg
    — the canonical split-planning example."""
    company = CompanyModel.objects.create(iec="4077777777", name="Plan Mode Split Test Co")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="PLANMODE-SPLIT-LIC",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=90),
        exporter=company,
    )
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Relevant Vegetable Oil",
        quantity=Decimal("100.000"),
        available_quantity=Decimal("100.000"),
    )
    pko_line = LicenseItemPlan.objects.create(
        license=license_obj, import_item=import_item, item_name=item_names["PKO - PLANMODE-TEST"],
        planned_quantity=Decimal("30.000"), unit_price=Decimal("1.80"), planned_cif_fc=Decimal("54.00"),
        remaining_quantity=Decimal("30.000"), remaining_cif_fc=Decimal("54.00"),
    )
    cheese_line = LicenseItemPlan.objects.create(
        license=license_obj, import_item=import_item, item_name=item_names["CHEESE - PLANMODE-TEST"],
        planned_quantity=Decimal("70.000"), unit_price=Decimal("5.50"), planned_cif_fc=Decimal("385.00"),
        remaining_quantity=Decimal("70.000"), remaining_cif_fc=Decimal("385.00"),
    )
    return {"license": license_obj, "import_item": import_item, "pko_line": pko_line, "cheese_line": cheese_line}


def _get_available_licenses(client, allotment_obj, **params):
    url = f"/api/allotment-actions/{allotment_obj.id}/available-licenses/"
    return client.get(url, params)


@pytest.mark.django_db
class TestPlanModeSplitRows:
    def test_actual_mode_shows_full_import_item_quantity_unaffected_by_plan(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        # Backward compatibility: default (Actual) mode must be completely
        # unaware of the plan split — one row, full 100kg, exactly like
        # before this feature existed.
        resp = _get_available_licenses(allotment_client, allotment_obj)
        assert resp.status_code == 200
        rows = [r for r in resp.data["available_items"] if r["id"] == veg_oil_split["import_item"].id]
        assert len(rows) == 1
        assert Decimal(rows[0]["available_quantity"]) == Decimal("100.000")
        assert "planned_item_name" not in rows[0] or rows[0].get("planned_item_name") is None

    def test_plan_mode_shows_two_separate_rows_with_own_quantities(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        resp = _get_available_licenses(allotment_client, allotment_obj, debit_based_on="plan")
        assert resp.status_code == 200
        rows = resp.data["available_items"]

        import_item_id = veg_oil_split["import_item"].id
        split_rows = [r for r in rows if r.get("import_item_id") == import_item_id]
        assert len(split_rows) == 2

        by_name = {r["planned_item_name"]: r for r in split_rows}
        assert set(by_name) == {"PKO - PLANMODE-TEST", "CHEESE - PLANMODE-TEST"}
        assert Decimal(by_name["PKO - PLANMODE-TEST"]["available_quantity"]) == Decimal("30.000")
        assert Decimal(by_name["CHEESE - PLANMODE-TEST"]["available_quantity"]) == Decimal("70.000")
        assert Decimal(by_name["PKO - PLANMODE-TEST"]["planned_quantity"]) == Decimal("30.000")
        assert Decimal(by_name["CHEESE - PLANMODE-TEST"]["planned_quantity"]) == Decimal("70.000")

        # Row ids must be unique per split row (the LicenseItemPlan line's
        # own id), not the shared underlying import item id.
        assert split_rows[0]["id"] != split_rows[1]["id"]
        assert {split_rows[0]["id"], split_rows[1]["id"]} == {
            veg_oil_split["pko_line"].id, veg_oil_split["cheese_line"].id,
        }

    def test_plan_mode_never_shows_full_100kg_on_either_split_row(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        # The bug this feature fixes: neither split row may show the parent
        # import item's full quantity.
        resp = _get_available_licenses(allotment_client, allotment_obj, debit_based_on="plan")
        for row in resp.data["available_items"]:
            if row.get("import_item_id") == veg_oil_split["import_item"].id:
                assert Decimal(row["available_quantity"]) != Decimal("100.000")

    def test_fully_consumed_plan_line_remains_visible_but_is_blocked(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        # Keep a selected exhausted child visible so the UI can explain why
        # raw source availability cannot be allotted.
        veg_oil_split["pko_line"].remaining_quantity = Decimal("0")
        veg_oil_split["pko_line"].remaining_cif_fc = Decimal("0")
        veg_oil_split["pko_line"].save(update_fields=["remaining_quantity", "remaining_cif_fc"])

        resp = _get_available_licenses(allotment_client, allotment_obj, debit_based_on="plan")
        by_id = {r["id"]: r for r in resp.data["available_items"]}
        assert veg_oil_split["pko_line"].id in by_id
        assert by_id[veg_oil_split["pko_line"].id]["can_create_allotment"] is False
        assert by_id[veg_oil_split["pko_line"].id]["reason_code"] == "NO_PLANNED_BALANCE"
        assert Decimal(by_id[veg_oil_split["pko_line"].id]["max_allotment_qty"]) == Decimal("0")
        assert veg_oil_split["cheese_line"].id in by_id


@pytest.mark.django_db
class TestPlannedItemNameFilter:
    def test_selecting_pko_shows_only_pko_row(self, allotment_client, allotment_obj, veg_oil_split, item_names):
        resp = _get_available_licenses(
            allotment_client, allotment_obj, debit_based_on="plan",
            planned_item_names=str(item_names["PKO - PLANMODE-TEST"].id),
        )
        assert resp.status_code == 200
        rows = resp.data["available_items"]
        assert all(r["planned_item_name"] == "PKO - PLANMODE-TEST" for r in rows)
        assert any(r["id"] == veg_oil_split["pko_line"].id for r in rows)
        assert not any(r["id"] == veg_oil_split["cheese_line"].id for r in rows)

    def test_filter_is_ignored_in_actual_mode(self, allotment_client, allotment_obj, veg_oil_split, item_names):
        # Backward compatibility: the new filter must not affect Actual mode.
        resp = _get_available_licenses(
            allotment_client, allotment_obj,
            planned_item_names=str(item_names["PKO - PLANMODE-TEST"].id),
        )
        assert resp.status_code == 200
        rows = [r for r in resp.data["available_items"] if r["id"] == veg_oil_split["import_item"].id]
        assert len(rows) == 1
        assert Decimal(rows[0]["available_quantity"]) == Decimal("100.000")


@pytest.mark.django_db
class TestPlanModeRangeFilters:
    """available_quantity_gte/lte and available_value_gte/lte, in Plan mode,
    target planned_quantity/planned_cif_fc directly (plain stored columns —
    no live-computed-value step needed here)."""

    def test_min_qty_above_pko_share_excludes_pko_but_keeps_cheese(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        resp = _get_available_licenses(
            allotment_client, allotment_obj, debit_based_on="plan", available_quantity_gte="50",
        )
        ids = [r["id"] for r in resp.data["available_items"]]
        assert veg_oil_split["pko_line"].id not in ids   # 30kg < 50
        assert veg_oil_split["cheese_line"].id in ids    # 70kg >= 50

    def test_max_value_below_cheese_share_excludes_cheese_but_keeps_pko(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        resp = _get_available_licenses(
            allotment_client, allotment_obj, debit_based_on="plan", available_value_lte="100",
        )
        ids = [r["id"] for r in resp.data["available_items"]]
        assert veg_oil_split["pko_line"].id in ids        # $54 <= $100
        assert veg_oil_split["cheese_line"].id not in ids  # $385 > $100

    def test_malformed_range_param_is_ignored_not_500(self, allotment_client, allotment_obj, veg_oil_split):
        resp = _get_available_licenses(
            allotment_client, allotment_obj, debit_based_on="plan", available_quantity_gte="not-a-number",
        )
        assert resp.status_code == 200
