"""
Integration coverage for a fixed architectural bug in E1's Auto-Plan
grouping: E1 used to group only by description (`auto_plan_shared.
group_by_desc`), a narrower key than the HSN-aware `plan_group_key` real
allotment-cap enforcement (`plan_enforcement.py::plan_status_for`, called
from `views_actions.py::allocate_items`) uses. Two items sharing one
description but DIFFERENT HS codes (the real shape of dev-DB licence
`0311045101`) used to get pooled by Auto-Plan into ONE plan saved entirely
on a single representative — whose OWN (HSN-aware) `plan_group_key` didn't
cover the other member, so `plan_status_for` found zero plan rows for that
member's narrower group and left it completely UNCONSTRAINED by any cap
(worse than E126/E132's double-counting: not over-enforcement, but a full
bypass). E1 now groups via the same canonical `plan_group_key` as
enforcement (`plan_grouping.merge_items_for_classification`), so both
members get their own correctly-scoped, independently-enforced cap.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentModel
from apps.core.models import CompanyModel, HSCodeModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.e1_auto_plan import compute_e1_auto_plan
from apps.license.services.plan_enforcement import save_plan_lines_for_license

User = get_user_model()


def _hs(code):
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


@pytest.fixture
def allotment_client(db):
    user = User.objects.create_user(
        username="e1-group-plan-cap-tester",
        email="e1-group-plan-cap-tester@example.com",
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
    company = CompanyModel.objects.create(iec="4044445555", name="E1 Group Plan Cap Owner Co")
    return AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000000.00"))


@pytest.fixture
def mixed_hsn_same_desc_license(db, monkeypatch):
    """Two import items, same description, DIFFERENT HS codes — the real
    shape of dev-DB licence 0311045101. Runs the REAL compute_e1_auto_plan
    + save_plan_lines_for_license pipeline this fix changed, not a
    hand-assembled end state."""
    company = CompanyModel.objects.create(iec="4033334444", name="E1 Group Plan Cap Split Co")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="E1-GROUP-PLAN-CAP-LIC",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=90),
        exporter=company,
    )
    item1 = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="Other Confectionery Ingredients",
        hs_code=_hs('08021100'),
        quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
        available_value=Decimal("100000.00"), condition_type="",
    )
    item2 = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=2, description="Other Confectionery Ingredients",
        hs_code=_hs('08029000'),
        quantity=Decimal("50.000"), available_quantity=Decimal("50.000"),
        available_value=Decimal("50000.00"), condition_type="",
    )
    # compute_e1_auto_plan reads the LIVE `get_balance_cif` property (backed
    # by the financial ledger), not the cached `LicenseBalance.balance_cif`
    # field — patch it directly, matching the convention in
    # test_e1_auto_plan.py's `_patch_balances`.
    monkeypatch.setattr(
        LicenseDetailsModel, "get_balance_cif", property(lambda self: Decimal("100000.00")),
    )
    # allocate-items itself checks `available_value_calculated`, which reads
    # the cached `LicenseBalance.balance_cif` field (a separate, denormalized
    # value from the live `get_balance_cif` above) — set it too so the
    # allocation endpoint sees the same balance the plan was generated against.
    license_obj.balance.balance_cif = Decimal("100000.00")
    license_obj.balance.save(update_fields=["balance_cif"])

    lines, _ = compute_e1_auto_plan(license_obj)
    save_plan_lines_for_license(license_obj, lines)

    return {"license": license_obj, "item1": item1, "item2": item2}


def _allocate(client, allotment_obj, item_id, qty, cif_fc):
    url = f"/api/allotment-actions/{allotment_obj.id}/allocate-items/"
    entry = {"item_id": item_id, "qty": str(qty), "cif_fc": str(cif_fc)}
    return client.post(url, {"allocations": [entry]}, format="json")


@pytest.mark.django_db
class TestE1MixedHsnGroupsPlanIndependently:
    def test_auto_plan_saves_two_separate_lines_not_pooled(self, mixed_hsn_same_desc_license):
        item1 = mixed_hsn_same_desc_license["item1"]
        item2 = mixed_hsn_same_desc_license["item2"]
        rows = list(LicenseItemPlan.objects.filter(license=mixed_hsn_same_desc_license["license"]))
        assert len(rows) == 2
        assert {r.import_item_id for r in rows} == {item1.id, item2.id}
        by_item = {r.import_item_id: r for r in rows}
        assert by_item[item1.id].planned_quantity == Decimal("100")
        assert by_item[item2.id].planned_quantity == Decimal("50")

    def test_item2_has_its_own_correctly_scoped_cap_not_unconstrained(
        self, allotment_client, allotment_obj, mixed_hsn_same_desc_license,
    ):
        item2 = mixed_hsn_same_desc_license["item2"]
        # item2's own plan cap is 50kg @ $3.00 = $150. $200 is chosen to be
        # decisive: it's ABOVE item2's own real cap ($150) but BELOW what a
        # pooled item1+item2 cap would have been ($450) — so this value can
        # only be rejected if item2 is enforced against its OWN correct
        # cap, not a pooled one and not left unconstrained (the two ways
        # the pre-fix bug could have let this through).
        resp = _allocate(allotment_client, allotment_obj, item2.id, "10", "200.00")
        assert resp.status_code == 400, resp.data
        assert resp.data["success"] == 0
        error = resp.data["errors"][0]
        assert error.get("plan_exceeded") is True
        assert Decimal(error["original_planned_cif_fc"]) == Decimal("150")

    def test_item2_debit_within_its_own_cap_succeeds(
        self, allotment_client, allotment_obj, mixed_hsn_same_desc_license,
    ):
        item2 = mixed_hsn_same_desc_license["item2"]
        resp = _allocate(allotment_client, allotment_obj, item2.id, "10", "30.00")  # 10 * 3.00
        assert resp.status_code == 201, resp.data

    def test_item1_cap_is_independent_of_item2s_group(
        self, allotment_client, allotment_obj, mixed_hsn_same_desc_license,
    ):
        item1 = mixed_hsn_same_desc_license["item1"]
        # item1's own cap is 100kg @ $3.00 = $300, entirely independent of
        # item2's group.
        resp = _allocate(allotment_client, allotment_obj, item1.id, "90", "270.00")
        assert resp.status_code == 201, resp.data
