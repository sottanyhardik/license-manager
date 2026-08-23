from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.models import CompanyModel, HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan


@pytest.fixture
def client(db):
    user = get_user_model().objects.create_user(username="allocation-initialization", password="test")
    group, _ = Group.objects.get_or_create(name="ALLOTMENT_MANAGER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    api_client = APIClient()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return api_client


def _allotment(target=None):
    company = CompanyModel.objects.create(iec="4099999999", name="Initialization Owner")
    return AllotmentModel.objects.create(company=company, planning_target_item=target)


def _active_line(target, *, active=True, deleted=False, cancelled=False):
    company = CompanyModel.objects.create(iec="4099999998", name="Initialization Licence Owner")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="INIT-LICENSE", license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30), exporter=company,
    )
    head = HeadSIONNormsModel.objects.create(name="Initialization norm")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="E132")
    license_obj.export_license.create(norm_class=sion)
    source = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, quantity=Decimal("10.000"),
        available_quantity=Decimal("10.000"), description="source",
    )
    return LicenseItemPlan.objects.create(
        license=license_obj, import_item=source, item_name=target,
        planned_quantity=Decimal("10.000"), planned_cif_fc=Decimal("10.00"),
        remaining_quantity=Decimal("10.000"), remaining_cif_fc=Decimal("10.00"),
        is_active=active, is_deleted=deleted, is_cancelled=cancelled,
    )


@pytest.mark.django_db
class TestAllocationInitialization:
    def test_active_target_plan_defaults_to_plan(self, client):
        target = ItemNameModel.objects.create(name="Canonical target")
        allotment = _allotment(target)
        _active_line(target)

        response = client.get(f"/api/allotment-actions/{allotment.pk}/allocation-initialization/")

        assert response.status_code == 200
        assert response.data["default_search_mode"] == "PLAN"
        assert response.data["default_allocation_basis"] == "PLAN"
        assert response.data["default_item"] == {"id": target.pk, "name": target.name}
        assert response.data["has_active_plan"] is True

    @pytest.mark.parametrize("state", [
        {"active": False}, {"active": False, "deleted": True}, {"active": False, "cancelled": True},
    ])
    def test_non_current_target_plan_defaults_to_actual(self, client, state):
        target = ItemNameModel.objects.create(name=f"Inactive target {state}")
        allotment = _allotment(target)
        _active_line(target, **state)

        response = client.get(f"/api/allotment-actions/{allotment.pk}/allocation-initialization/")

        assert response.status_code == 200
        assert response.data["default_search_mode"] == "ACTUAL"
        assert response.data["default_allocation_basis"] == "ACTUAL"
        assert response.data["default_item"] is None
        assert response.data["has_active_plan"] is False
        assert response.data["plan_status"] == "NO_ACTIVE_PLAN"

    def test_target_metadata_without_plan_defaults_to_actual(self, client):
        target = ItemNameModel.objects.create(name="Target without plan")
        allotment = _allotment(target)

        response = client.get(f"/api/allotment-actions/{allotment.pk}/allocation-initialization/")

        assert response.status_code == 200
        assert response.data["default_search_mode"] == "ACTUAL"
        assert response.data["default_item"] is None

    def test_duplicate_active_identity_defaults_safely_to_actual(self, client):
        target = ItemNameModel.objects.create(name="Duplicate target")
        allotment = _allotment(target)
        plan = _active_line(target)
        LicenseItemPlan.objects.create(
            license=plan.license, import_item=plan.import_item, item_name=target,
            planned_quantity=Decimal("10.000"), planned_cif_fc=Decimal("10.00"),
            remaining_quantity=Decimal("10.000"), remaining_cif_fc=Decimal("10.00"),
        )
        response = client.get(f"/api/allotment-actions/{allotment.pk}/allocation-initialization/")
        assert response.status_code == 200
        assert response.data["plan_status"] == "AMBIGUOUS_ACTIVE_PLAN"
        assert response.data["default_search_mode"] == "ACTUAL"
        assert response.data["default_item"] is None

    def test_exhausted_active_plan_remains_plan_default(self, client):
        target = ItemNameModel.objects.create(name="Exhausted target")
        allotment = _allotment(target)
        plan = _active_line(target)
        AllotmentItems.objects.create(
            allotment=allotment,
            item=plan.import_item,
            plan_line=plan,
            allocation_basis="PLAN",
            qty=plan.planned_quantity,
            cif_fc=plan.planned_cif_fc,
        )
        response = client.get(f"/api/allotment-actions/{allotment.pk}/allocation-initialization/")
        assert response.status_code == 200
        assert response.data["plan_status"] == "EXHAUSTED"
        assert response.data["default_search_mode"] == "PLAN"
        assert response.data["reason_code"] == "NO_PLANNED_BALANCE"
