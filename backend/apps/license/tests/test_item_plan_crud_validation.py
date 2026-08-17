"""
Regression tests for the plain `LicenseItemPlanViewSet` CRUD endpoints
(create/update/destroy) — the only utilization-plan write path that had NO
capacity / CIF-pool cap enforcement at all (see `_validate_plan_line_cap` in
`apps/license/views/item_plan.py`, added alongside these tests).

`bulk_upsert` and the auto-plan engines already enforced:
  * per-group capacity: Σ planned_quantity for an item's plan-group ≤
    (live-allotted + available) summed across the group,
  * shared CIF pool: Σ planned_cif_fc across the licence ≤ licence balance,
cumulatively (never row-by-row). These tests prove the plain create/update/
destroy endpoints enforce the SAME caps, cumulatively, without double-
counting a row being edited, and that delete always succeeds (it can only
free capacity, never consume it).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Sum
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import CompanyModel
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan,
)

User = get_user_model()

PLANS_URL = "/api/license-item-plans/"


@pytest.fixture
def license_manager_client(db, planned_license):
    license_obj, _ = planned_license
    user = User.objects.create_user(
        username="item-plan-crud-manager",
        email="item-plan-crud-manager@example.com",
        password="RoleP@ssw0rd123",
        company=license_obj.exporter,
    )
    group, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def planned_license(db):
    """A single-item licence: available_quantity=100.000, balance_cif=1000.00."""
    company = CompanyModel.objects.create(iec="6234567890", name="Plan CRUD Exporter")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="PLAN-CRUD-001",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30),
        exporter=company,
    )
    LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("1000.00"))
    item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="Plan CRUD Item",
        quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
    )
    return license_obj, item


def _create(client, item, qty, cif, **extra):
    payload = {
        "import_item": item.id,
        "planned_quantity": str(qty),
        "unit_price": "1.00",
        "planned_cif_fc": str(cif),
    }
    payload.update(extra)
    return client.post(PLANS_URL, payload, format="json")


@pytest.mark.django_db
def test_create_exactly_at_capacity_and_cif_is_valid(license_manager_client, planned_license):
    """Edge case: planned == available exactly → VALID."""
    license_obj, item = planned_license
    resp = _create(license_manager_client, item, "100.000", "1000.00")
    assert resp.status_code == 201, resp.data
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 1


@pytest.mark.django_db
def test_create_exceeding_available_quantity_is_rejected(license_manager_client, planned_license):
    license_obj, item = planned_license
    resp = _create(license_manager_client, item, "100.001", "500.00")
    assert resp.status_code == 400, resp.data
    assert "Quantity Exceeded" in str(resp.data)
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 0


@pytest.mark.django_db
def test_create_exceeding_available_cif_is_rejected(license_manager_client, planned_license):
    license_obj, item = planned_license
    resp = _create(license_manager_client, item, "50.000", "1000.01")
    assert resp.status_code == 400, resp.data
    assert "Value Exceeded" in str(resp.data)
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 0


@pytest.mark.django_db
def test_quantity_valid_but_cif_exceeded_is_rejected(license_manager_client, planned_license):
    license_obj, item = planned_license
    resp = _create(license_manager_client, item, "10.000", "1000.01")
    assert resp.status_code == 400, resp.data
    assert "Value Exceeded" in str(resp.data)


@pytest.mark.django_db
def test_cif_valid_but_quantity_exceeded_is_rejected(license_manager_client, planned_license):
    license_obj, item = planned_license
    resp = _create(license_manager_client, item, "100.001", "1.00")
    assert resp.status_code == 400, resp.data
    assert "Quantity Exceeded" in str(resp.data)


@pytest.mark.django_db
def test_cumulative_rows_exactly_consuming_balance_are_valid(license_manager_client, planned_license):
    """Multiple rows whose SUM exactly equals available qty/CIF → VALID."""
    license_obj, item = planned_license
    resp1 = _create(license_manager_client, item, "60.000", "600.00")
    assert resp1.status_code == 201, resp1.data
    resp2 = _create(license_manager_client, item, "40.000", "400.00")
    assert resp2.status_code == 201, resp2.data
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 2


@pytest.mark.django_db
def test_cumulative_rows_exceeding_quantity_are_rejected(license_manager_client, planned_license):
    """Plan A=600/1000 CIF-room aside, qty 60 + 50 = 110 > 100 → INVALID."""
    license_obj, item = planned_license
    resp1 = _create(license_manager_client, item, "60.000", "300.00")
    assert resp1.status_code == 201, resp1.data
    resp2 = _create(license_manager_client, item, "50.000", "200.00")
    assert resp2.status_code == 400, resp2.data
    assert "Quantity Exceeded" in str(resp2.data)
    # Second (invalid) row must not have been persisted.
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 1


@pytest.mark.django_db
def test_cumulative_rows_exceeding_cif_are_rejected(license_manager_client, planned_license):
    """Qty stays within capacity but Σ CIF across rows exceeds balance."""
    license_obj, item = planned_license
    resp1 = _create(license_manager_client, item, "10.000", "600.00")
    assert resp1.status_code == 201, resp1.data
    resp2 = _create(license_manager_client, item, "10.000", "500.00")
    assert resp2.status_code == 400, resp2.data
    assert "Value Exceeded" in str(resp2.data)
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 1


@pytest.mark.django_db
def test_editing_plan_line_does_not_double_count_its_own_old_value(license_manager_client, planned_license):
    """
    Two rows sum exactly to capacity (50 + 50 = 100). Re-saving one row with
    its UNCHANGED value must still succeed — if the validator failed to
    exclude the row's own prior value before re-checking, this would
    incorrectly compute 50 (other row) + 50 (stale old) + 50 (new) = 150 and
    reject a no-op edit.
    """
    license_obj, item = planned_license
    r1 = _create(license_manager_client, item, "50.000", "500.00")
    r2 = _create(license_manager_client, item, "50.000", "500.00")
    assert r1.status_code == 201 and r2.status_code == 201

    row1_id = r1.data["id"]
    resp = license_manager_client.patch(
        f"{PLANS_URL}{row1_id}/",
        {"planned_quantity": "50.000", "planned_cif_fc": "500.00"},
        format="json",
    )
    assert resp.status_code == 200, resp.data


@pytest.mark.django_db
def test_editing_plan_line_to_exceed_group_capacity_is_rejected(license_manager_client, planned_license):
    license_obj, item = planned_license
    r1 = _create(license_manager_client, item, "50.000", "500.00")
    r2 = _create(license_manager_client, item, "50.000", "500.00")
    assert r1.status_code == 201 and r2.status_code == 201

    row1_id = r1.data["id"]
    resp = license_manager_client.patch(
        f"{PLANS_URL}{row1_id}/",
        {"planned_quantity": "60.000"},
        format="json",
    )
    # 60 (edited row1) + 50 (row2, unaffected) = 110 > 100 capacity.
    assert resp.status_code == 400, resp.data
    assert "Quantity Exceeded" in str(resp.data)
    row1 = LicenseItemPlan.objects.get(pk=row1_id)
    assert row1.planned_quantity == Decimal("50.000")


@pytest.mark.django_db
def test_editing_plan_line_can_shrink_freely(license_manager_client, planned_license):
    license_obj, item = planned_license
    r1 = _create(license_manager_client, item, "100.000", "1000.00")
    assert r1.status_code == 201, r1.data

    row1_id = r1.data["id"]
    resp = license_manager_client.patch(
        f"{PLANS_URL}{row1_id}/",
        {"planned_quantity": "10.000", "planned_cif_fc": "100.00"},
        format="json",
    )
    assert resp.status_code == 200, resp.data


@pytest.mark.django_db
def test_deleting_a_plan_line_frees_capacity_for_a_new_one(license_manager_client, planned_license):
    license_obj, item = planned_license
    r1 = _create(license_manager_client, item, "100.000", "1000.00")
    assert r1.status_code == 201, r1.data
    row1_id = r1.data["id"]

    del_resp = license_manager_client.delete(f"{PLANS_URL}{row1_id}/")
    assert del_resp.status_code == 204, del_resp.data
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 0

    r2 = _create(license_manager_client, item, "100.000", "1000.00")
    assert r2.status_code == 201, r2.data


def _authed_client(user):
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.mark.django_db(transaction=True)
def test_concurrent_creates_cannot_collectively_exceed_capacity():
    """
    Two concurrent requests each planning 60/100 units (60 + 60 = 120 > 100)
    must not both succeed — the `select_for_update` lock in
    `_validate_plan_line_cap` serializes them onto the same committed total,
    so exactly one is accepted and the other sees the now-current sum and is
    rejected. Uses `transaction=True` (real commits, real DB connections per
    thread) because the default `db` fixture's transaction-wrapped tests
    don't let a second thread observe a first thread's row lock at all.
    """
    import threading

    from django.db import connections

    company = CompanyModel.objects.create(iec="8234567890", name="Concurrency Exporter")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="PLAN-CRUD-CONCURRENT",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30),
        exporter=company,
    )
    LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("10000.00"))
    item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="Concurrency Item",
        quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
    )
    user = User.objects.create_user(
        username="item-plan-concurrent", email="item-plan-concurrent@example.com",
        password="RoleP@ssw0rd123",
        company=company,
    )
    group, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(group)

    results = {}

    def worker(key):
        try:
            client = _authed_client(user)
            resp = _create(client, item, "60.000", "600.00")
            results[key] = resp.status_code
        finally:
            connections.close_all()

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert sorted(results.values()) == [201, 400], results
    total_qty = LicenseItemPlan.objects.filter(license=license_obj).aggregate(
        t=Sum("planned_quantity"),
    )["t"] or Decimal("0")
    assert total_qty <= Decimal("100.000")


@pytest.mark.django_db
def test_zero_available_balance_blocks_any_positive_plan(db):
    company = CompanyModel.objects.create(iec="7234567890", name="Zero Balance Exporter")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="PLAN-CRUD-ZERO",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30),
        exporter=company,
    )
    # No LicenseExportItemModel → balance_cif is 0; item has 0 available.
    item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="Zero Item",
        quantity=Decimal("0.000"), available_quantity=Decimal("0.000"),
    )
    user = User.objects.create_user(
        username="item-plan-zero", email="item-plan-zero@example.com",
        password="RoleP@ssw0rd123", company=company,
    )
    group, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(group)
    resp = _create(_authed_client(user), item, "0.001", "0.01")
    assert resp.status_code == 400, resp.data
