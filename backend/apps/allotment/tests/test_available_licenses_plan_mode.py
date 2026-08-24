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
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.models import CompanyModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan

User = get_user_model()


@pytest.fixture(autouse=True)
def live_actual_cif(monkeypatch):
    """Candidate fixtures represent usable licence positions, so give them a
    live (not stored-plan) CIF balance.  Production obtains this through the
    condition pool; the focused plan-query fixtures intentionally do not set
    up that unrelated ledger."""
    monkeypatch.setattr(
        "apps.license.services.condition_pool.available_value_bulk_map",
        lambda items: {item.id: Decimal("1000000.00") for item in items},
    )


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
    def test_plan_candidate_query_count_is_constant_for_a_paginated_response(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        """The ledger status pass must not turn row count into extra queries.

        PLAN availability needs a full, authoritative status pass before it
        can paginate.  This regression guard exercises one row and the whole
        matching page and asserts that serialising the additional plan row
        does not add a per-row database query.  It deliberately uses a small
        tolerance for authentication/backend framework bookkeeping while
        catching an N+1 return in this endpoint.
        """
        # Add enough split lines to distinguish a bounded batch read from an
        # accidental per-row relation/aggregate query.
        for index in range(6):
            item_name = ItemNameModel.objects.create(name=f"PERF-PLAN-{index}")
            LicenseItemPlan.objects.create(
                license=veg_oil_split["license"],
                import_item=veg_oil_split["import_item"],
                item_name=item_name,
                planned_quantity=Decimal("1.000"),
                unit_price=Decimal("1.00"),
                planned_cif_fc=Decimal("1.00"),
                remaining_quantity=Decimal("1.000"),
                remaining_cif_fc=Decimal("1.00"),
            )

        with CaptureQueriesContext(connection) as one_row_queries:
            one_row = _get_available_licenses(
                allotment_client, allotment_obj, debit_based_on="PLAN", page_size=1,
            )
        with CaptureQueriesContext(connection) as full_page_queries:
            full_page = _get_available_licenses(
                allotment_client, allotment_obj, debit_based_on="PLAN", page_size=20,
            )

        assert one_row.status_code == full_page.status_code == 200
        assert len(full_page.data["available_items"]) == 8
        # The status, availability and serializer maps are fixed batches.  A
        # 16-query cold-request ceiling leaves authentication/metadata room
        # while rejecting an additional per-plan-line relation lookup.
        assert len(full_page_queries) <= 16
        # Batch loaders and relation prefetches make query volume independent
        # of page rows.  A small allowance covers serializer work only needed
        # when a populated page exposes a second related import item, while
        # still rejecting a per-row query regression across eight rows.
        assert len(full_page_queries) <= len(one_row_queries) + 2

    def test_actual_mode_shows_full_import_item_quantity_unaffected_by_plan(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        # Backward compatibility: default (Actual) mode must be completely
        # unaware of the plan split — one row, full 100kg, exactly like
        # before this feature existed.
        resp = _get_available_licenses(allotment_client, allotment_obj, debit_based_on="ACTUAL")
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
        # The shared Actual/Plan stat bar consumes the canonical long names;
        # Plan rows must therefore expose the exact same original and live
        # plan values as their legacy aliases.
        assert Decimal(by_name["PKO - PLANMODE-TEST"]["original_planned_quantity"]) == Decimal("30.000")
        assert Decimal(by_name["PKO - PLANMODE-TEST"]["original_planned_cif_fc"]) == Decimal("54.00")
        assert Decimal(by_name["PKO - PLANMODE-TEST"]["original_planned_qty"]) == Decimal("30.000")
        assert Decimal(by_name["PKO - PLANMODE-TEST"]["original_planned_cif"]) == Decimal("54.00")

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

    def test_plan_line_is_shared_across_all_source_rows_in_its_physical_group(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        representative = veg_oil_split["import_item"]
        sibling = LicenseImportItemsModel.objects.create(
            license=representative.license,
            serial_number=15,
            description=representative.description,
            quantity=Decimal("25.000"),
            available_quantity=Decimal("25.000"),
        )
        response = _get_available_licenses(allotment_client, allotment_obj, debit_based_on="plan")
        assert response.status_code == 200, response.data
        pko_rows = [row for row in response.data["available_items"] if row["planned_item_name"] == "PKO - PLANMODE-TEST"]
        assert {row["import_item_id"] for row in pko_rows} == {representative.id, sibling.id}
        assert {row["plan_line_id"] for row in pko_rows} == {veg_oil_split["pko_line"].id}
        assert {Decimal(row["plan_position"]["remaining_qty"]) for row in pko_rows} == {Decimal("30.000")}

    def test_fully_consumed_plan_line_is_excluded(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        # Raw source availability can never revive an exhausted plan line.
        # A plan residual is ledger-derived; stale mutable `remaining_*`
        # columns must not hide or revive a plan line.
        AllotmentItems.objects.create(
            allotment=allotment_obj,
            item=veg_oil_split["import_item"],
            plan_line=veg_oil_split["pko_line"],
            allocation_basis="PLAN",
            qty=Decimal("30.000"),
            cif_fc=Decimal("54.00"),
        )

        resp = _get_available_licenses(allotment_client, allotment_obj, debit_based_on="plan")
        by_id = {r["id"]: r for r in resp.data["available_items"]}
        assert veg_oil_split["pko_line"].id not in by_id
        assert veg_oil_split["cheese_line"].id in by_id


@pytest.mark.django_db
class TestPlannedItemNameFilter:
    def test_selected_plan_item_overrides_route_target(self, allotment_client, allotment_obj, veg_oil_split, item_names):
        allotment_obj.planning_target_item = item_names["CHEESE - PLANMODE-TEST"]
        allotment_obj.save(update_fields=["planning_target_item"])

        response = _get_available_licenses(
            allotment_client,
            allotment_obj,
            debit_based_on="PLAN",
            planning_target_item_id=item_names["PKO - PLANMODE-TEST"].id,
        )

        assert response.status_code == 200
        assert response.data["available_items"]
        assert all(row["planned_item_name"] == "PKO - PLANMODE-TEST" for row in response.data["available_items"])

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
            debit_based_on="ACTUAL",
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

    def test_range_filter_uses_effective_plan_limit_not_raw_plan_residual(
        self, allotment_client, allotment_obj, veg_oil_split, monkeypatch,
    ):
        # PKO retains 30 in its plan, but only 20 is live on the licence.
        # A PLAN min of 25 must exclude it; filtering the plan residual alone
        # would incorrectly return it.
        veg_oil_split["import_item"].available_quantity = Decimal("20.000")
        veg_oil_split["import_item"].save(update_fields=["available_quantity"])
        response = _get_available_licenses(
            allotment_client, allotment_obj, debit_based_on="PLAN", available_quantity_gte="25",
        )
        ids = {row["id"] for row in response.data["available_items"]}
        assert veg_oil_split["pko_line"].id not in ids
        assert veg_oil_split["cheese_line"].id not in ids
