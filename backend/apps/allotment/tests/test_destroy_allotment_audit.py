"""destroy_allotment writes one AuditEvent snapshot, atomically with the delete."""
from decimal import Decimal
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentItems, AllotmentModel, AuditEvent
from apps.core.models import CompanyModel

User = get_user_model()


@pytest.fixture
def user(db):
    u = User.objects.create_user(username="allot-audit", email="aa@example.com", password="pw-Audit-123")
    u.is_superuser = u.is_staff = True
    u.save()
    return u


@pytest.fixture
def client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return c


@pytest.fixture
def company(db):
    return CompanyModel.objects.create(name="Audit Co", iec="IEC888888")


def test_delete_writes_snapshot(client, user, company, test_license):
    from apps.license.models import LicenseImportItemsModel
    item = LicenseImportItemsModel.objects.create(license=test_license, serial_number=88, description="x")
    a = AllotmentModel.objects.create(company=company)
    AllotmentItems.objects.create(allotment=a, item=item, qty=Decimal("5.000"), cif_fc=Decimal("10.00"), cif_inr=Decimal("800.00"))
    pk = a.pk

    assert client.delete(f"/api/allotments/{pk}/").status_code == 204

    ev = AuditEvent.objects.get()
    assert ev.actor == user
    assert ev.company_before == company
    assert ev.allocation_item is None
    snap = ev.details
    assert snap["allotment_id"] == pk
    assert snap["company_id"] == company.pk
    assert snap["items"] == [{"item_id": item.pk, "qty": "5.000", "cif_fc": "10.00", "cif_inr": "800.00"}]
    assert ev.created_on is not None


def test_failed_delete_leaves_no_audit(client, company):
    a = AllotmentModel.objects.create(company=company)

    def boom(self, *args, **kwargs):
        raise RuntimeError("boom")

    with mock.patch.object(AllotmentModel, "delete", boom):
        assert client.delete(f"/api/allotments/{a.pk}/").status_code == 500
    assert AllotmentModel.objects.filter(pk=a.pk).exists()
    assert AuditEvent.objects.count() == 0
