"""Allocation caps for independent plan lines on similarly-described E1 inputs.

The retired E1 planner used to manufacture plan rows as a side effect of a
special-purpose service. Allocation authority is now the explicit
``LicenseItemPlan`` selected by a PLAN debit. This keeps the important
regression: similarly named inputs with different HS codes must not let one
item's planned capacity authorize another item's debit.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentModel
from apps.core.models import CompanyModel, HSCodeModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan

User = get_user_model()


def _hs(code):
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


@pytest.fixture
def allotment_client(db):
    user = User.objects.create_user(username="e1-group-plan-cap-tester", password="RoleP@ssw0rd123")
    group, _ = Group.objects.get_or_create(name="ALLOTMENT_MANAGER")
    user.groups.add(group)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def allotment_obj(db):
    company = CompanyModel.objects.create(iec="4044445555", name="E1 Group Plan Cap Owner Co")
    return AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000000.00"))


@pytest.fixture
def mixed_hsn_same_desc_license(db):
    company = CompanyModel.objects.create(iec="4033334444", name="E1 Group Plan Cap Split Co")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="E1-GROUP-PLAN-CAP-LIC", license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=90), exporter=company,
    )
    item1 = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="Other Confectionery Ingredients",
        hs_code=_hs("08021100"), quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
        available_value=Decimal("100000.00"), condition_type="",
    )
    item2 = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=2, description="Other Confectionery Ingredients",
        hs_code=_hs("08029000"), quantity=Decimal("50.000"), available_quantity=Decimal("50.000"),
        available_value=Decimal("50000.00"), condition_type="",
    )
    LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
    target, _ = ItemNameModel.objects.get_or_create(name="E1 CAP TARGET")
    line1 = LicenseItemPlan.objects.create(license=license_obj, import_item=item1, item_name=target,
        planned_quantity=Decimal("100"), planned_cif_fc=Decimal("300"), unit_price=Decimal("3.00"))
    line2 = LicenseItemPlan.objects.create(license=license_obj, import_item=item2, item_name=target,
        planned_quantity=Decimal("50"), planned_cif_fc=Decimal("150"), unit_price=Decimal("3.00"))
    return {"license": license_obj, "item1": item1, "item2": item2, "line1": line1, "line2": line2}


def _allocate(client, allotment, item, plan_line, qty, cif_fc):
    return client.post(f"/api/allotment-actions/{allotment.id}/allocate-items/", {
        "allocations": [{"item_id": item.id, "plan_line_id": plan_line.id, "qty": str(qty), "cif_fc": str(cif_fc)}],
    }, format="json")


@pytest.mark.django_db
class TestE1MixedHsnPlanLinesAreIndependent:
    def test_each_item_retains_its_own_explicit_plan_line(self, mixed_hsn_same_desc_license):
        rows = LicenseItemPlan.objects.filter(license=mixed_hsn_same_desc_license["license"])
        assert {row.import_item_id for row in rows} == {mixed_hsn_same_desc_license["item1"].id, mixed_hsn_same_desc_license["item2"].id}

    def test_item2_cannot_use_item1_or_pooled_capacity(self, allotment_client, allotment_obj, mixed_hsn_same_desc_license):
        data = mixed_hsn_same_desc_license
        response = _allocate(allotment_client, allotment_obj, data["item2"], data["line2"], "10", "200.00")
        assert response.status_code == 400, response.data
        error = response.data["errors"][0]
        assert error["code"] == "ALLOTMENT_CIF_EXCEEDS_PLAN"
        assert Decimal(error["max_cif"]) == Decimal("150")

    def test_item2_debit_within_its_own_cap_succeeds(self, allotment_client, allotment_obj, mixed_hsn_same_desc_license):
        data = mixed_hsn_same_desc_license
        response = _allocate(allotment_client, allotment_obj, data["item2"], data["line2"], "10", "30.00")
        assert response.status_code == 201, response.data

    def test_item1_capacity_is_independent(self, allotment_client, allotment_obj, mixed_hsn_same_desc_license):
        data = mixed_hsn_same_desc_license
        response = _allocate(allotment_client, allotment_obj, data["item1"], data["line1"], "90", "270.00")
        assert response.status_code == 201, response.data
