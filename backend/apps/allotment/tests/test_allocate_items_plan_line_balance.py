"""
Tests for plan-line balance tracking in `AllotmentActionViewSet.allocate_items`
(backend/apps/allotment/views_actions.py).

Business rule: once Auto-Plan generates a Vegetable Oil PKO/Cheese split,
those planned quantities become FIXED commitments.  Each Plan debit retains
its exact `plan_line_id`, and residual capacity is derived from that ledger
identity.  No mutable plan counter may be decremented or reconstructed using
the plan line's rounded unit price.
"""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentModel, AllotmentItems
from apps.core.models import CompanyModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.plan_enforcement import plan_line_status_for

User = get_user_model()


@pytest.fixture
def allotment_client(db):
    user = User.objects.create_user(
        username="plan-line-balance-tester",
        email="plan-line-balance-tester@example.com",
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
    company = CompanyModel.objects.create(iec="4099998888", name="Plan Line Balance Owner Co")
    return AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000000.00"))


def _set_live_balance(license_obj, balance_cif):
    """Give the license genuine export-item credit so its LIVE Financial
    Ledger balance equals `balance_cif`. BL-AVAIL-01 made `available_value_
    calculated`'s fallback read `LicenseBalanceCalculator.
    calculate_financial_balance` directly, so writing to the (now-bypassed)
    cached `LicenseBalance.balance_cif` column no longer has any effect --
    genuine ledger data is required. Idempotent per license (update_or_create)."""
    LicenseExportItemModel.objects.update_or_create(
        license=license_obj, defaults={"cif_fc": balance_cif},
    )


@pytest.fixture
def veg_oil_split(db):
    """A 100kg Vegetable Oil import item already Auto-Planned as PKO 40kg /
    Cheese 60kg — the canonical starting point for every example in the
    business spec."""
    company = CompanyModel.objects.create(iec="4077778888", name="Plan Line Balance Split Co")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="PLAN-LINE-BALANCE-LIC",
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
        available_value=Decimal("100000.00"),
        condition_type="",
    )
    _set_live_balance(license_obj, Decimal("100000.00"))
    pko_name = ItemNameModel.objects.create(name="PKO - PLANLINE-TEST")
    cheese_name = ItemNameModel.objects.create(name="CHEESE - PLANLINE-TEST")
    pko_line = LicenseItemPlan.objects.create(
        license=license_obj, import_item=import_item, item_name=pko_name,
        planned_quantity=Decimal("40"), unit_price=Decimal("1.80"), planned_cif_fc=Decimal("72"),
        remaining_quantity=Decimal("40"), remaining_cif_fc=Decimal("72"),
    )
    cheese_line = LicenseItemPlan.objects.create(
        license=license_obj, import_item=import_item, item_name=cheese_name,
        planned_quantity=Decimal("60"), unit_price=Decimal("5.50"), planned_cif_fc=Decimal("330"),
        remaining_quantity=Decimal("60"), remaining_cif_fc=Decimal("330"),
    )
    return {
        "license": license_obj, "import_item": import_item,
        "pko_line": pko_line, "cheese_line": cheese_line,
    }


def _allocate(client, allotment_obj, item_id, qty, cif_fc, plan_line_id=None):
    url = f"/api/allotment-actions/{allotment_obj.id}/allocate-items/"
    entry = {"item_id": item_id, "qty": str(qty), "cif_fc": str(cif_fc)}
    if plan_line_id is not None:
        entry["plan_line_id"] = plan_line_id
    return client.post(url, {"allocations": [entry]}, format="json")


@pytest.mark.django_db
class TestPlanLineLedgerResidual:
    def test_hosted_shape_accepts_plan_residual_with_independent_cif_limit(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        """Regression for the 1033 / $18,601.24 PLAN allocation shape.

        The plan permits up to $25,825 while the allotment's canonical unit
        value makes the submitted $18,601.24 pair valid.  The plan is a cap,
        not an instruction to debit its whole remaining CIF.
        """
        item = veg_oil_split["import_item"]
        line = veg_oil_split["pko_line"]
        item.quantity = item.available_quantity = Decimal("1033.000")
        item.save(update_fields=["quantity", "available_quantity"])
        _set_live_balance(veg_oil_split["license"], Decimal("43562.68"))
        line.planned_quantity = line.remaining_quantity = Decimal("1033.000")
        line.planned_cif_fc = line.remaining_cif_fc = Decimal("25825.00")
        line.save(update_fields=[
            "planned_quantity", "remaining_quantity", "planned_cif_fc", "remaining_cif_fc",
        ])
        allotment_obj.unit_value_per_unit = Decimal("18.007")
        allotment_obj.save(update_fields=["unit_value_per_unit"])

        response = _allocate(
            allotment_client, allotment_obj, item.id, "1033.000", "18601.24", plan_line_id=line.id,
        )

        assert response.status_code == 201, response.data
        saved = AllotmentItems.objects.get(id=response.data["created_items"][0]["id"])
        assert saved.qty == Decimal("1033.000")
        assert saved.cif_fc == Decimal("18601.24")
        residual = plan_line_status_for(line)
        assert residual["remaining_quantity"] == Decimal("0.000")
        assert residual["remaining_cif_fc"] == Decimal("7223.76")

    def test_plan_line_allocation_can_follow_legacy_unmapped_plan_debit(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        """The old item/allotment uniqueness must not block a mapped PLAN row."""
        item = veg_oil_split["import_item"]
        line = veg_oil_split["pko_line"]
        AllotmentItems.objects.create(
            allotment=allotment_obj,
            item=item,
            qty=Decimal("10.000"),
            cif_fc=Decimal("18.00"),
            allocation_basis="PLAN",
            search_mode="PLAN",
            plan_line=None,
        )

        response = _allocate(
            allotment_client, allotment_obj, item.id, "20.000", "36.00", plan_line_id=line.id,
        )

        assert response.status_code == 201, response.data
        rows = AllotmentItems.objects.filter(allotment=allotment_obj, item=item)
        assert rows.count() == 2
        mapped = rows.get(plan_line=line)
        assert mapped.qty == Decimal("20.000")
        assert mapped.cif_fc == Decimal("36.00")

    def test_unexpected_write_failure_is_logged_and_returns_safe_500(
        self, allotment_client, allotment_obj, veg_oil_split, caplog,
    ):
        with patch(
            "apps.allotment.views_actions.AllotmentItems.save",
            side_effect=RuntimeError("database implementation defect"),
        ):
            response = _allocate(
                allotment_client,
                allotment_obj,
                veg_oil_split["import_item"].id,
                "20",
                "36.00",
                plan_line_id=veg_oil_split["pko_line"].id,
            )

        assert response.status_code == 500
        assert response.data == {"error": "Failed to allocate licence item."}
        assert "database implementation defect" not in str(response.data)
        assert not AllotmentItems.objects.filter(allotment=allotment_obj).exists()
        assert any(record.message == "Allocation failed" for record in caplog.records)

    def test_allocating_from_pko_reduces_only_pko(self, allotment_client, allotment_obj, veg_oil_split):
        resp = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "20", "36.00", plan_line_id=veg_oil_split["pko_line"].id,
        )
        assert resp.status_code == 201, resp.data

        pko = plan_line_status_for(veg_oil_split["pko_line"])
        cheese = plan_line_status_for(veg_oil_split["cheese_line"])
        assert pko["remaining_quantity"] == Decimal("20")
        assert pko["remaining_cif_fc"] == Decimal("36.00")
        assert cheese["remaining_quantity"] == Decimal("60")
        assert cheese["remaining_cif_fc"] == Decimal("330")

    def test_second_allocation_drains_pko_to_zero(self, allotment_client, allotment_obj, veg_oil_split):
        _allocate(allotment_client, allotment_obj, veg_oil_split["import_item"].id,
                  "20", "36.00", plan_line_id=veg_oil_split["pko_line"].id)
        # No-op re-affirmation: `_set_live_balance` is idempotent, and the
        # genuine export credit it wrote is unaffected by the first
        # allocation (the live balance already correctly nets the resulting
        # outstanding AT allotment on its own). Kept for clarity/defensiveness.
        _set_live_balance(veg_oil_split["license"], Decimal("100000.00"))
        resp = _allocate(allotment_client, allotment_obj, veg_oil_split["import_item"].id,
                          "20", "36.00", plan_line_id=veg_oil_split["pko_line"].id)
        assert resp.status_code == 201, resp.data

        pko = plan_line_status_for(veg_oil_split["pko_line"])
        cheese = plan_line_status_for(veg_oil_split["cheese_line"])
        assert pko["remaining_quantity"] == Decimal("0")
        assert pko["remaining_cif_fc"] == Decimal("0.00")
        assert cheese["remaining_quantity"] == Decimal("60")

    def test_plan_allocation_removes_only_its_exhausted_child_from_the_refreshed_queue(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        """A debit consumes its exact plan child without hiding a sibling
        that retains real source-row quantity."""
        response = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "40", "72.00", plan_line_id=veg_oil_split["pko_line"].id,
        )
        assert response.status_code == 201, response.data

        veg_oil_split["import_item"].refresh_from_db()
        assert veg_oil_split["import_item"].available_quantity == Decimal("60.00")
        assert plan_line_status_for(veg_oil_split["pko_line"])["remaining_quantity"] == Decimal("0")

        # The exhausted plan child is removed, but its sibling remains because
        # it is a distinct persisted plan identity sharing the same source row.
        queue = allotment_client.get(
            f"/api/allotment-actions/{allotment_obj.id}/available-licenses/",
            {"debit_based_on": "PLAN", "page_size": 20},
        )
        assert queue.status_code == 200
        returned_ids = {row["id"] for row in queue.data["available_items"]}
        assert veg_oil_split["pko_line"].id not in returned_ids
        assert veg_oil_split["cheese_line"].id in returned_ids

    def test_full_source_row_plan_debit_removes_the_candidate_after_refresh(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        """When a selected plan line owns all remaining source quantity, a
        full debit must leave Actual Qty at zero and remove it from the next
        PLAN candidate response."""
        veg_oil_split["cheese_line"].delete()
        pko = veg_oil_split["pko_line"]
        pko.planned_quantity = Decimal("100")
        pko.planned_cif_fc = Decimal("180.00")
        pko.remaining_quantity = Decimal("100")
        pko.remaining_cif_fc = Decimal("180.00")
        pko.save(update_fields=["planned_quantity", "planned_cif_fc", "remaining_quantity", "remaining_cif_fc"])

        response = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "100", "180.00", plan_line_id=pko.id,
        )
        assert response.status_code == 201, response.data

        veg_oil_split["import_item"].refresh_from_db()
        from apps.license.services.balance_calculator import ItemBalanceCalculator
        assert ItemBalanceCalculator.calculate_available_quantity(veg_oil_split["import_item"]) == Decimal("0.00")
        assert veg_oil_split["import_item"].available_quantity == Decimal("0.00")
        assert plan_line_status_for(pko)["remaining_quantity"] == Decimal("0")

        queue = allotment_client.get(
            f"/api/allotment-actions/{allotment_obj.id}/available-licenses/",
            {"debit_based_on": "PLAN", "page_size": 20},
        )
        assert queue.status_code == 200
        assert pko.id not in {row["id"] for row in queue.data["available_items"]}

    def test_committed_allocation_runs_one_inline_durable_replan(
        self, allotment_client, allotment_obj, veg_oil_split, django_capture_on_commit_callbacks,
    ):
        """Allocation is the explicit synchronous exception to ordinary
        signal-driven replan delivery: it records one durable request then
        executes that exact request after commit."""
        with patch(
            "apps.license.services.replan_requests.mark_license_replan_source_changed",
            return_value=SimpleNamespace(pk=321),
        ) as mark_replan, patch(
            "apps.license.tasks.replan_license_task.run",
        ) as run_replan, django_capture_on_commit_callbacks(execute=True):
            response = _allocate(
                allotment_client, allotment_obj, veg_oil_split["import_item"].id,
                "20", "36.00", plan_line_id=veg_oil_split["pko_line"].id,
            )

        assert response.status_code == 201, response.data
        mark_replan.assert_called_once_with(
            license_id=veg_oil_split["license"].id,
            reason="allotment_committed",
            source_model="allotment.AllotmentItems",
            source_pk=str(allotment_obj.id),
            dispatch=False,
        )
        run_replan.assert_called_once_with(321)

    def test_deleting_an_allocation_runs_one_inline_durable_replan(
        self, allotment_client, allotment_obj, veg_oil_split, django_capture_on_commit_callbacks,
    ):
        created = AllotmentItems.objects.create(
            allotment=allotment_obj,
            item=veg_oil_split["import_item"],
            plan_line=veg_oil_split["pko_line"],
            allocation_basis="PLAN",
            search_mode="PLAN",
            qty=Decimal("20.000"),
            cif_fc=Decimal("36.00"),
        )
        with patch(
            "apps.license.services.replan_requests.mark_license_replan_source_changed",
            return_value=SimpleNamespace(pk=654),
        ) as mark_replan, patch(
            "apps.license.tasks.replan_license_task.run",
        ) as run_replan, django_capture_on_commit_callbacks(execute=True):
            response = allotment_client.delete(
                f"/api/allotment-actions/{allotment_obj.id}/delete-item/{created.id}/",
            )

        assert response.status_code == 200, response.data
        assert not AllotmentItems.objects.filter(pk=created.id).exists()
        mark_replan.assert_called_once_with(
            license_id=veg_oil_split["license"].id,
            reason="allotment_deleted",
            source_model="allotment.AllotmentItems",
            source_pk=str(allotment_obj.id),
            dispatch=False,
        )
        run_replan.assert_called_once_with(654)

    def test_allocating_from_cheese_after_pko_only_reduces_cheese(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        # Stale mutable counters must not influence the ledger residual.
        veg_oil_split["pko_line"].remaining_quantity = Decimal("20")
        veg_oil_split["pko_line"].remaining_cif_fc = Decimal("36.00")
        veg_oil_split["pko_line"].save(update_fields=["remaining_quantity", "remaining_cif_fc"])

        resp = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "10", "55.00", plan_line_id=veg_oil_split["cheese_line"].id,
        )
        assert resp.status_code == 201, resp.data

        pko = plan_line_status_for(veg_oil_split["pko_line"])
        cheese = plan_line_status_for(veg_oil_split["cheese_line"])
        assert pko["remaining_quantity"] == Decimal("40")
        assert cheese["remaining_quantity"] == Decimal("50")
        assert cheese["remaining_cif_fc"] == Decimal("275.00")

    def test_exhausted_plan_line_rejects_direct_api_allocation(self, allotment_client, allotment_obj, veg_oil_split):
        """Raw source availability must not bypass a zero split-child plan."""
        # A stale stored zero must not reject an unspent line.
        veg_oil_split["pko_line"].remaining_quantity = Decimal("0")
        veg_oil_split["pko_line"].remaining_cif_fc = Decimal("0")
        veg_oil_split["pko_line"].save(update_fields=["remaining_quantity", "remaining_cif_fc"])
        first = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "40", "72.00", plan_line_id=veg_oil_split["pko_line"].id,
        )
        assert first.status_code == 201, first.data
        resp = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "1", "1.80", plan_line_id=veg_oil_split["pko_line"].id,
        )
        assert resp.status_code == 400, resp.data
        error = resp.data["errors"][0]
        assert error["code"] == "NO_PLANNED_BALANCE"
        assert error["message"] == "PKO - PLANLINE-TEST has no remaining planned quantity or value."
        assert error["allocation_basis"] == "PLAN"
        assert error["max_qty"] == "0.000"
        assert error["max_cif"] == "0.00"
        assert plan_line_status_for(veg_oil_split["pko_line"])["remaining_quantity"] == Decimal("0")

    def test_missing_plan_line_id_leaves_plan_lines_untouched(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        # Actual-mode allocations (no plan_line_id) must behave exactly as
        # before this feature — the real allotment succeeds, no plan line
        # is touched at all.
        resp = _allocate(allotment_client, allotment_obj, veg_oil_split["import_item"].id, "20", "36.00")
        assert resp.status_code == 201, resp.data

        assert plan_line_status_for(veg_oil_split["pko_line"])["remaining_quantity"] == Decimal("40")
        assert plan_line_status_for(veg_oil_split["cheese_line"])["remaining_quantity"] == Decimal("60")

    def test_stale_plan_line_id_is_rejected_without_raw_availability_fallback(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        nonexistent_id = veg_oil_split["cheese_line"].id + 999999
        resp = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "5", "9.00", plan_line_id=nonexistent_id,
        )
        assert resp.status_code == 400, resp.data
        assert resp.data["success"] == 0
        assert resp.data["errors"][0]["code"] == "NO_PLANNED_BALANCE"

    def test_deleting_ledger_debit_restores_the_same_plan_line(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        response = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "20", "36.00", plan_line_id=veg_oil_split["pko_line"].id,
        )
        assert response.status_code == 201, response.data
        assert plan_line_status_for(veg_oil_split["pko_line"])["remaining_quantity"] == Decimal("20")

        AllotmentItems.objects.get(id=response.data["created_items"][0]["id"]).delete()
        residual = plan_line_status_for(veg_oil_split["pko_line"])
        assert residual["remaining_quantity"] == Decimal("40")
        assert residual["remaining_cif_fc"] == Decimal("72.00")
