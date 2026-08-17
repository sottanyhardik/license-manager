from datetime import date
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan


pytestmark = pytest.mark.django_db
User = get_user_model()
BASE_URL = "/api/license-item-plans/"


def _company(iec, name):
    return CompanyModel.objects.create(iec=iec, name=name)


def _license(company, number):
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company,
        license_number=number,
        license_date=date.today(),
        license_expiry_date=date.today(),
    )
    item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Scoped planning item",
        quantity=Decimal("10.000"),
        available_quantity=Decimal("10.000"),
    )
    plan = LicenseItemPlan.objects.create(
        license=license_obj,
        import_item=item,
        planned_quantity=Decimal("5.000"),
        unit_price=Decimal("1.00"),
        planned_cif_fc=Decimal("5.00"),
    )
    return license_obj, item, plan


def _client(company=None, *, superuser=False):
    user = User.objects.create_user(
        username=f"planning-security-{User.objects.count()}",
        password="safe-test-password",
        company=company,
        is_superuser=superuser,
        is_staff=superuser,
    )
    if not superuser:
        group, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
        user.groups.add(group)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_plan_list_and_retrieve_are_company_scoped():
    company_a = _company("9000000001", "Planning A")
    company_b = _company("9000000002", "Planning B")
    _, _, plan_a = _license(company_a, "PLAN-SEC-A")
    _, _, plan_b = _license(company_b, "PLAN-SEC-B")
    client = _client(company_a)

    response = client.get(BASE_URL)
    assert response.status_code == 200
    payload = response.data.get("results", response.data)
    assert {row["id"] for row in payload} == {plan_a.id}

    response = client.get(f"{BASE_URL}{plan_b.id}/")
    assert response.status_code == 404


def test_norm_prefill_and_bulk_upsert_reject_foreign_license():
    company_a = _company("9000000011", "Planning A")
    company_b = _company("9000000012", "Planning B")
    _license(company_a, "PLAN-SEC-ACTION-A")
    foreign_license, foreign_item, _ = _license(company_b, "PLAN-SEC-ACTION-B")
    client = _client(company_a)

    response = client.get(f"{BASE_URL}norm-prefill/?license={foreign_license.id}")
    assert response.status_code == 404

    response = client.post(
        f"{BASE_URL}bulk-upsert/",
        {
            "license": foreign_license.id,
            "lines": [{
                "import_item": foreign_item.id,
                "planned_quantity": "1.000",
                "unit_price": "1.00",
                "planned_cif_fc": "1.00",
            }],
        },
        format="json",
    )
    assert response.status_code in (400, 403, 404)


def test_superuser_retains_cross_company_visibility():
    company_a = _company("9000000021", "Planning A")
    company_b = _company("9000000022", "Planning B")
    _, _, plan_a = _license(company_a, "PLAN-SEC-SUPER-A")
    _, _, plan_b = _license(company_b, "PLAN-SEC-SUPER-B")
    client = _client(superuser=True)

    response = client.get(BASE_URL)
    assert response.status_code == 200
    payload = response.data.get("results", response.data)
    assert {plan_a.id, plan_b.id}.issubset({row["id"] for row in payload})
