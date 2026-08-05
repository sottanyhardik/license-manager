"""
Integration coverage for a fixed production bug: `allocate_items`'s
"Utilization-plan cap" gate (`views_actions.py` ~line 746,
`plan_enforcement.py::plan_status_for`) aggregates `LicenseItemPlan` rows
across a whole `plan_group_key` group (HSN + normalized description), the
same grouping the Item Plan UI and Excel exporters use. Before
`e126_auto_plan.py`/`e132_auto_plan.py` became group-aware, a licence whose
import items were re-serialized (e.g. by DGFT) into several sibling rows
sharing one physical product could end up with a STALE, already-generated
split preserved on the original row while its NEW siblings got an
independent fresh split — the group's `plan_status_for` cap then summed
BOTH, doubling the enforced total. This is not a display-only bug: it can
let a real debit through past the intended plan cap, or wrongly reject a
legitimate one.

`compute_e132_auto_plan`/`compute_e126_auto_plan` now group by
`plan_group_key` (`plan_grouping.merge_items_for_classification`) and
anchor a group's ENTIRE plan on its representative import item (lowest
serial number) — consolidating any legacy per-member split balances onto it
— so `plan_status_for`'s group-summed cap can never be double-counted by
scattered per-member plan rows again. This file proves that end-to-end
through the real `allocate_items` endpoint, not just the pure planning
functions (already covered in `apps/license/tests/test_e132_auto_plan.py`
and `test_e126_auto_plan.py`).
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
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.e132_auto_plan import compute_e132_auto_plan
from apps.license.services.e132_plan import CHEESE, PKO
from apps.license.services.plan_enforcement import save_plan_lines_for_license

User = get_user_model()

VEG_OIL_DESC = "Relevant Vegetable Oil viz Palm Kernel (1513) or Dairy Fat 0406 Vegetable Oil"


@pytest.fixture
def allotment_client(db):
    user = User.objects.create_user(
        username="group-plan-cap-tester",
        email="group-plan-cap-tester@example.com",
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
    company = CompanyModel.objects.create(iec="4066667777", name="Group Plan Cap Owner Co")
    return AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000000.00"))


@pytest.fixture
def resynced_group_with_legacy_split(db):
    """Models the reported production scenario: one physical product,
    re-serialized by DGFT into 3 sibling import items sharing the same
    HSN + description. The original (now much smaller) row still carries a
    PKO 40 / Cheese 60 split generated before the resync; its two new
    siblings have no plan of their own. Auto-Plan + save consolidates this
    onto the representative (lowest serial number) — this fixture runs that
    real pipeline, not a hand-built end state, so it exercises the actual
    fix.
    """
    company = CompanyModel.objects.create(iec="4055556666", name="Group Plan Cap Split Co")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="GROUP-PLAN-CAP-LIC",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=90),
        exporter=company,
    )
    pko_name, _ = ItemNameModel.objects.get_or_create(name=PKO)
    cheese_name, _ = ItemNameModel.objects.get_or_create(name=CHEESE)

    # `quantity`/`available_quantity` set generously (200, well above the
    # legacy split's 100) and self-consistently — a real allotment's
    # post-save signal recomputes `available_quantity` from `quantity` minus
    # debited amounts, so only setting `available_quantity` alone wouldn't
    # survive a real debit. This isolates the tests below to the PLAN cap
    # (100, from the preserved split) rather than the unrelated physical-
    # stock cap.
    representative = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description=VEG_OIL_DESC,
        quantity=Decimal("200.000"), available_quantity=Decimal("200.000"),
        available_value=Decimal("100000.00"), condition_type="",
    )
    LicenseItemPlan.objects.create(
        license=license_obj, import_item=representative, item_name=pko_name,
        planned_quantity=Decimal("40"), unit_price=Decimal("1.80"), planned_cif_fc=Decimal("72"),
        remaining_quantity=Decimal("40"), remaining_cif_fc=Decimal("72"),
    )
    LicenseItemPlan.objects.create(
        license=license_obj, import_item=representative, item_name=cheese_name,
        planned_quantity=Decimal("60"), unit_price=Decimal("5.50"), planned_cif_fc=Decimal("330"),
        remaining_quantity=Decimal("60"), remaining_cif_fc=Decimal("330"),
    )
    sibling1 = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=2, description=VEG_OIL_DESC,
        quantity=Decimal("50.000"), available_quantity=Decimal("50.000"),
        available_value=Decimal("50000.00"), condition_type="",
    )
    sibling2 = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=3, description=VEG_OIL_DESC,
        quantity=Decimal("60.000"), available_quantity=Decimal("60.000"),
        available_value=Decimal("60000.00"), condition_type="",
    )

    license_obj.balance.balance_cif = Decimal("100000.00")
    license_obj.balance.save(update_fields=["balance_cif"])

    # Run the REAL pipeline this fix changed — not a hand-assembled end state.
    lines, _ = compute_e132_auto_plan(license_obj)
    save_plan_lines_for_license(license_obj, lines)

    return {
        "license": license_obj, "representative": representative,
        "sibling1": sibling1, "sibling2": sibling2,
    }


def _allocate(client, allotment_obj, item_id, qty, cif_fc):
    url = f"/api/allotment-actions/{allotment_obj.id}/allocate-items/"
    entry = {"item_id": item_id, "qty": str(qty), "cif_fc": str(cif_fc)}
    return client.post(url, {"allocations": [entry]}, format="json")


@pytest.mark.django_db
class TestGroupPlanCapIsNotDoubleCounted:
    def test_auto_plan_consolidates_onto_one_representative_not_all_three_members(
        self, resynced_group_with_legacy_split,
    ):
        rep = resynced_group_with_legacy_split["representative"]
        sib1 = resynced_group_with_legacy_split["sibling1"]
        sib2 = resynced_group_with_legacy_split["sibling2"]

        rows = list(LicenseItemPlan.objects.filter(license=resynced_group_with_legacy_split["license"]))
        # Exactly the preserved pair — never doubled by an extra fresh split
        # for the siblings' own availability.
        assert len(rows) == 2
        assert {r.import_item_id for r in rows} == {rep.id}
        assert sib1.id not in {r.import_item_id for r in rows}
        assert sib2.id not in {r.import_item_id for r in rows}
        assert sum(r.planned_quantity for r in rows) == Decimal("100")
        assert sum(r.planned_cif_fc for r in rows) == Decimal("402")

    def test_debit_within_the_true_consolidated_cap_succeeds(
        self, allotment_client, allotment_obj, resynced_group_with_legacy_split,
    ):
        rep = resynced_group_with_legacy_split["representative"]
        # 90 <= the group's TRUE consolidated plan cap (100) and well within
        # the representative's own physical available_quantity (200).
        resp = _allocate(allotment_client, allotment_obj, rep.id, "90", "200.00")
        assert resp.status_code == 201, resp.data

    def test_debit_exceeding_the_true_consolidated_cap_is_rejected(
        self, allotment_client, allotment_obj, resynced_group_with_legacy_split,
    ):
        rep = resynced_group_with_legacy_split["representative"]
        # 150 is well within the representative's own physical
        # available_quantity (200) — the physical-stock check alone would
        # NOT catch this. Under the bug this fix addresses, a group's
        # inflated (doubled) cap would also have let this through. The
        # correct, consolidated cap is 100, so this must be rejected.
        resp = _allocate(allotment_client, allotment_obj, rep.id, "150", "50.00")
        assert resp.status_code == 400, resp.data  # 400 = every requested allocation failed
        assert resp.data["success"] == 0
        error = resp.data["errors"][0]
        assert error.get("plan_exceeded") is True
        assert Decimal(error["original_planned_quantity"]) == Decimal("100")

    def test_debit_at_exactly_the_cap_succeeds_and_next_unit_is_rejected(
        self, allotment_client, allotment_obj, resynced_group_with_legacy_split,
    ):
        rep = resynced_group_with_legacy_split["representative"]
        first = _allocate(allotment_client, allotment_obj, rep.id, "100", "402.00")
        assert first.status_code == 201, first.data
        assert first.data["success"] == 1

        # Live balance recompute after the first allotment (same pattern
        # documented in test_allocate_items_plan_line_balance.py) — refresh
        # before the second call so the physical-stock checks stay accurate.
        resynced_group_with_legacy_split["license"].balance.balance_cif = Decimal("100000.00")
        resynced_group_with_legacy_split["license"].balance.save(update_fields=["balance_cif"])

        second = _allocate(allotment_client, allotment_obj, rep.id, "1", "1.00")
        assert second.status_code == 400, second.data  # 400 = every requested allocation failed
        assert second.data["success"] == 0
        assert second.data["errors"][0].get("plan_exceeded") is True
