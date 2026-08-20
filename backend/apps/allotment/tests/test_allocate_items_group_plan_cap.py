"""Integration coverage for exact plan-line allocation caps.

PLAN allocations use a selected plan-line ledger identity. Two target splits
on one import row cannot borrow or double-count one another's capacity.
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
from apps.license.services.plan_enforcement import plan_line_status_for

User = get_user_model()


@pytest.fixture
def allotment_client(db):
    user = User.objects.create_user(username="group-plan-cap-tester", password="RoleP@ssw0rd123")
    group, _ = Group.objects.get_or_create(name="ALLOTMENT_MANAGER")
    user.groups.add(group)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def allotment_obj(db):
    company = CompanyModel.objects.create(iec="4066667777", name="Group Plan Cap Owner Co")
    return AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000000.00"))


@pytest.fixture
def target_split(db):
    company = CompanyModel.objects.create(iec="4055556666", name="Group Plan Cap Split Co")
    license_obj = LicenseDetailsModel.objects.create(license_number="GROUP-PLAN-CAP-LIC",
        license_date=date.today() - timedelta(days=30), license_expiry_date=date.today() + timedelta(days=90), exporter=company)
    item = LicenseImportItemsModel.objects.create(license=license_obj, serial_number=1, description="Relevant Vegetable Oil",
        quantity=Decimal("200.000"), available_quantity=Decimal("200.000"), available_value=Decimal("100000.00"), condition_type="")
    LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
    pko, _ = ItemNameModel.objects.get_or_create(name="PKO - GROUP CAP")
    cheese, _ = ItemNameModel.objects.get_or_create(name="CHEESE - GROUP CAP")
    pko_line = LicenseItemPlan.objects.create(license=license_obj, import_item=item, item_name=pko,
        planned_quantity=Decimal("40"), planned_cif_fc=Decimal("72"), unit_price=Decimal("1.80"))
    cheese_line = LicenseItemPlan.objects.create(license=license_obj, import_item=item, item_name=cheese,
        planned_quantity=Decimal("60"), planned_cif_fc=Decimal("330"), unit_price=Decimal("5.50"))
    return {"item": item, "pko_line": pko_line, "cheese_line": cheese_line}


def _allocate(client, allotment, item, line, qty, cif_fc):
    return client.post(f"/api/allotment-actions/{allotment.id}/allocate-items/", {
        "allocations": [{"item_id": item.id, "plan_line_id": line.id, "qty": str(qty), "cif_fc": str(cif_fc)}],
    }, format="json")


@pytest.mark.django_db
class TestPlanLineCapIsNotDoubleCounted:
    def test_two_target_splits_have_exact_independent_caps(self, target_split):
        assert plan_line_status_for(target_split["pko_line"])["original_quantity"] == Decimal("40")
        assert plan_line_status_for(target_split["cheese_line"])["original_quantity"] == Decimal("60")

    def test_debit_within_selected_line_cap_succeeds(self, allotment_client, allotment_obj, target_split):
        data = target_split
        response = _allocate(allotment_client, allotment_obj, data["item"], data["cheese_line"], "50", "275.00")
        assert response.status_code == 201, response.data

    def test_debit_cannot_borrow_other_split_capacity(self, allotment_client, allotment_obj, target_split):
        data = target_split
        response = _allocate(allotment_client, allotment_obj, data["item"], data["pko_line"], "50", "90.00")
        assert response.status_code == 400, response.data
        assert response.data["errors"][0]["code"] == "ALLOTMENT_QTY_EXCEEDS_PLAN"
        assert Decimal(response.data["errors"][0]["max_qty"]) == Decimal("40")

    def test_exact_cap_succeeds_then_next_unit_is_rejected(self, allotment_client, allotment_obj, target_split):
        data = target_split
        first = _allocate(allotment_client, allotment_obj, data["item"], data["cheese_line"], "60", "330.00")
        assert first.status_code == 201, first.data
        second = _allocate(allotment_client, allotment_obj, data["item"], data["cheese_line"], "1", "5.50")
        assert second.status_code == 400, second.data
        assert second.data["errors"][0]["code"] == "NO_PLANNED_BALANCE"
