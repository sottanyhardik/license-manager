"""
Tests for plan-line balance tracking in `AllotmentActionViewSet.allocate_items`
(backend/apps/allotment/views_actions.py).

Business rule: once Auto-Plan generates a Vegetable Oil PKO/Cheese split,
those planned quantities become FIXED commitments. A real debit has no
item_name of its own (`AllotmentItems.item` only references the underlying
import item), so the shared `available_quantity` can't tell which plan line
a debit was meant to draw down. The fix: the Plan-mode grid already knows
exactly which `LicenseItemPlan` row an allocation originates from and sends
it as `plan_line_id` — `allocate_items` uses that to decrement THAT line's
own `remaining_quantity`/`remaining_cif_fc` directly, independent of any
sibling plan line on the same import item.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentModel
from apps.core.models import CompanyModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan

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
class TestPlanLineBalanceDecrement:
    def test_allocating_from_pko_reduces_only_pko(self, allotment_client, allotment_obj, veg_oil_split):
        resp = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "20", "36.00", plan_line_id=veg_oil_split["pko_line"].id,
        )
        assert resp.status_code == 201, resp.data

        veg_oil_split["pko_line"].refresh_from_db()
        veg_oil_split["cheese_line"].refresh_from_db()
        assert veg_oil_split["pko_line"].remaining_quantity == Decimal("20")
        assert veg_oil_split["pko_line"].remaining_cif_fc == Decimal("36.00")   # 20 × 1.80
        # Cheese's row must remain COMPLETELY unchanged.
        assert veg_oil_split["cheese_line"].remaining_quantity == Decimal("60")
        assert veg_oil_split["cheese_line"].remaining_cif_fc == Decimal("330")

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

        veg_oil_split["pko_line"].refresh_from_db()
        veg_oil_split["cheese_line"].refresh_from_db()
        assert veg_oil_split["pko_line"].remaining_quantity == Decimal("0")
        assert veg_oil_split["pko_line"].remaining_cif_fc == Decimal("0.00")
        assert veg_oil_split["cheese_line"].remaining_quantity == Decimal("60")   # still untouched

    def test_allocating_from_cheese_after_pko_only_reduces_cheese(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        # Example 3 from the spec: PKO already at 20 remaining (from a prior
        # 20kg debit), then debit 10kg from Cheese.
        veg_oil_split["pko_line"].remaining_quantity = Decimal("20")
        veg_oil_split["pko_line"].remaining_cif_fc = Decimal("36.00")
        veg_oil_split["pko_line"].save(update_fields=["remaining_quantity", "remaining_cif_fc"])

        resp = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "10", "55.00", plan_line_id=veg_oil_split["cheese_line"].id,
        )
        assert resp.status_code == 201, resp.data

        veg_oil_split["pko_line"].refresh_from_db()
        veg_oil_split["cheese_line"].refresh_from_db()
        assert veg_oil_split["pko_line"].remaining_quantity == Decimal("20")  # unaffected
        assert veg_oil_split["cheese_line"].remaining_quantity == Decimal("50")  # 60 - 10
        assert veg_oil_split["cheese_line"].remaining_cif_fc == Decimal("275.00")  # 50 × 5.50

    def test_remaining_never_goes_negative(self, allotment_client, allotment_obj, veg_oil_split):
        # Over-allocating beyond a plan line's own remaining balance still
        # succeeds (the broader available_quantity/CIF checks are what
        # actually gate the real debit) but must clamp the plan line's
        # remaining at 0, never negative.
        resp = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "40", "72.00", plan_line_id=veg_oil_split["pko_line"].id,
        )
        assert resp.status_code == 201, resp.data
        veg_oil_split["pko_line"].refresh_from_db()
        assert veg_oil_split["pko_line"].remaining_quantity == Decimal("0")

    def test_missing_plan_line_id_leaves_plan_lines_untouched(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        # Actual-mode allocations (no plan_line_id) must behave exactly as
        # before this feature — the real allotment succeeds, no plan line
        # is touched at all.
        resp = _allocate(allotment_client, allotment_obj, veg_oil_split["import_item"].id, "20", "36.00")
        assert resp.status_code == 201, resp.data

        veg_oil_split["pko_line"].refresh_from_db()
        veg_oil_split["cheese_line"].refresh_from_db()
        assert veg_oil_split["pko_line"].remaining_quantity == Decimal("40")
        assert veg_oil_split["cheese_line"].remaining_quantity == Decimal("60")

    def test_stale_plan_line_id_does_not_fail_the_allocation(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        nonexistent_id = veg_oil_split["cheese_line"].id + 999999
        resp = _allocate(
            allotment_client, allotment_obj, veg_oil_split["import_item"].id,
            "5", "9.00", plan_line_id=nonexistent_id,
        )
        assert resp.status_code == 201, resp.data
        assert resp.data["success"] == 1
