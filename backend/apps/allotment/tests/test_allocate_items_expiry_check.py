"""
Regression tests for the license-expiry guard in
`AllotmentActionViewSet.allocate_items` (backend/apps/allotment/views_actions.py).

Bug: allocate-items never checked license_expiry_date (or is_expired) before
creating an AllotmentItems row -- only available_quantity, the live CIF-FC
balance, and the utilization-plan cap were enforced. A license whose
license_expiry_date was already in the past, but still had a positive
available_quantity/available_value_calculated on its import items (the
balance fields are not zeroed out just because a license expires), could
still be allocated against successfully.

The fix rejects the allocation (400, per-item error, no AllotmentItems row
created) whenever the item's license_expiry_date is strictly before today --
the same comparison the `license_status=active`/`expired` filters elsewhere
in this same view already use for listing. A license expiring today (not yet
past its expiry date) or in the future is unaffected, and the check runs
before any of the existing balance/plan checks so it does not change their
behavior for non-expired licenses.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentModel, AllotmentItems
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel

User = get_user_model()


@pytest.fixture
def allotment_client(db):
    user = User.objects.create_user(
        username="allocate-items-expiry-tester",
        email="allocate-items-expiry-tester@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="ALLOTMENT_MANAGER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def _make_license(license_number, exporter, expiry_date):
    return LicenseDetailsModel.objects.create(
        license_number=license_number,
        license_date=date.today() - timedelta(days=200),
        license_expiry_date=expiry_date,
        exporter=exporter,
    )


def _set_live_balance(license_obj, balance_cif):
    """Give the license genuine export-item credit so its LIVE Financial
    Ledger balance equals `balance_cif`. BL-AVAIL-01 made `available_value_
    calculated`'s fallback read `LicenseBalanceCalculator.
    calculate_financial_balance` directly, so writing to the (now-bypassed)
    cached `LicenseBalance.balance_cif` column no longer has any effect --
    genuine ledger data is required. Idempotent per license (update_or_create)
    so re-calling it after an intervening allocation is harmless."""
    LicenseExportItemModel.objects.update_or_create(
        license=license_obj, defaults={"cif_fc": balance_cif},
    )


@pytest.fixture
def allotment_obj(db):
    company = CompanyModel.objects.create(iec="4099999999", name="Allocate Items Expiry Owner Co")
    return AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000000.00"))


def _allocate(client, allotment_obj, item_id, qty, cif_fc):
    url = f"/api/allotment-actions/{allotment_obj.id}/allocate-items/"
    return client.post(
        url,
        {"allocations": [{"item_id": item_id, "qty": str(qty), "cif_fc": str(cif_fc)}]},
        format="json",
    )


class TestAllocateItemsRejectsExpiredLicense:
    def test_rejects_allocation_against_expired_license_with_positive_balance(
        self, allotment_client, allotment_obj,
    ):
        # Mirrors the audited production shape exactly: license_expiry_date
        # in the past, but available_quantity/available_value_calculated
        # (via balance_cif) still positive -- expiry does not zero out the
        # stored balance fields, so only an explicit expiry gate can catch this.
        company = CompanyModel.objects.create(iec="4011046335", name="Expired License Co")
        license_obj = _make_license(
            "0311046335-EXP-TEST", company, date.today() - timedelta(days=1)
        )
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("10000.000"),
            available_quantity=Decimal("9625.000"),
            available_value=Decimal("50000.00"),
            condition_type="",
        )
        _set_live_balance(license_obj, Decimal("50000.00"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "500.00")

        assert resp.status_code == 400, resp.data
        assert resp.data["success"] == 0
        assert len(resp.data["errors"]) == 1
        assert "expired" in resp.data["errors"][0]["error"].lower()
        assert not AllotmentItems.objects.filter(allotment=allotment_obj, item=item).exists()

    def test_rejects_even_when_license_expired_yesterday_only(self, allotment_client, allotment_obj):
        company = CompanyModel.objects.create(iec="4011046297", name="Expired Yesterday Co")
        license_obj = _make_license(
            "0311046297-EXP-TEST", company, date.today() - timedelta(days=1)
        )
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type="",
        )
        _set_live_balance(license_obj, Decimal("500.00"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "100.00")

        assert resp.status_code == 400, resp.data
        assert "expired" in resp.data["errors"][0]["error"].lower()


class TestAllocateItemsUnaffectedForNonExpiredLicenses:
    def test_succeeds_for_license_expiring_today_is_not_treated_as_expired(
        self, allotment_client, allotment_obj,
    ):
        # A license whose expiry date IS today has not yet expired (matches
        # the existing license_status=active/expired filter convention of
        # `license_expiry_date < today`, not `<= today`).
        company = CompanyModel.objects.create(iec="4022229999", name="Expires Today Co")
        license_obj = _make_license("EXPIRES-TODAY-TEST", company, date.today())
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type="",
        )
        _set_live_balance(license_obj, Decimal("500.00"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "100.00")

        assert resp.status_code == 201, resp.data
        assert resp.data["success"] == 1
        assert resp.data["errors"] == []

    def test_succeeds_for_future_expiry_license_unchanged(self, allotment_client, allotment_obj):
        company = CompanyModel.objects.create(iec="4033339999", name="Future Expiry Co")
        license_obj = _make_license(
            "FUTURE-EXPIRY-TEST", company, date.today() + timedelta(days=90)
        )
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type="",
        )
        _set_live_balance(license_obj, Decimal("500.00"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "100.00")

        assert resp.status_code == 201, resp.data
        assert resp.data["success"] == 1
        assert resp.data["errors"] == []


class TestAllocateItemsExpiryAcrossDateRangeBoundaries:
    """Regression scope: the expiry gate is a plain date comparison
    (license_expiry_date < today) and must behave identically regardless of
    how far in the past/future the expiry date sits, and must not choke on a
    null expiry date (the field is nullable at the DB level even though
    every row observed in production has one set)."""

    def test_rejects_license_expired_long_ago(self, allotment_client, allotment_obj):
        company = CompanyModel.objects.create(iec="4055551111", name="Expired Long Ago Co")
        license_obj = _make_license(
            "EXPIRED-LONG-AGO-TEST", company, date.today() - timedelta(days=1000)
        )
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type="",
        )
        _set_live_balance(license_obj, Decimal("500.00"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "100.00")

        assert resp.status_code == 400, resp.data
        assert "expired" in resp.data["errors"][0]["error"].lower()
        assert not AllotmentItems.objects.filter(allotment=allotment_obj, item=item).exists()

    def test_succeeds_for_license_expiring_tomorrow(self, allotment_client, allotment_obj):
        company = CompanyModel.objects.create(iec="4055552222", name="Expires Tomorrow Co")
        license_obj = _make_license(
            "EXPIRES-TOMORROW-TEST", company, date.today() + timedelta(days=1)
        )
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type="",
        )
        _set_live_balance(license_obj, Decimal("500.00"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "100.00")

        assert resp.status_code == 201, resp.data
        assert resp.data["success"] == 1

    def test_succeeds_for_license_expiring_years_in_the_future(self, allotment_client, allotment_obj):
        company = CompanyModel.objects.create(iec="4055553333", name="Far Future Expiry Co")
        license_obj = _make_license(
            "FAR-FUTURE-EXPIRY-TEST", company, date.today() + timedelta(days=3650)
        )
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type="",
        )
        _set_live_balance(license_obj, Decimal("500.00"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "100.00")

        assert resp.status_code == 201, resp.data
        assert resp.data["success"] == 1

    def test_succeeds_for_license_with_null_expiry_date(self, allotment_client, allotment_obj):
        # license_expiry_date is nullable at the DB/model level. The fix
        # guards with `if license_expiry_date and ...` specifically so a
        # missing expiry date is never misread as "expired" -- it should
        # fall through to the existing balance/plan checks unchanged.
        company = CompanyModel.objects.create(iec="4055554444", name="Null Expiry Co")
        license_obj = _make_license("NULL-EXPIRY-TEST", company, None)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type="",
        )
        _set_live_balance(license_obj, Decimal("500.00"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "100.00")

        assert resp.status_code == 201, resp.data
        assert resp.data["success"] == 1
        assert resp.data["errors"] == []


class TestAllocateItemsExpiryAcrossConditionTypes:
    """Regression scope: the expiry gate runs before the condition_type-
    driven available-value branch (open / "AU" / "N%" pool) and must reject
    an expired license identically regardless of which branch its items
    would otherwise take, while leaving each branch's own (already-covered
    elsewhere) balance behavior untouched when the license is not expired."""

    @pytest.mark.parametrize("condition_type", ["", "AU", "5%"])
    def test_rejects_expired_license_regardless_of_condition_type(
        self, allotment_client, allotment_obj, condition_type,
    ):
        company = CompanyModel.objects.create(
            iec=f"406000{abs(hash(condition_type)) % 10000:04d}",
            name=f"Expired Condition {condition_type or 'OPEN'} Co",
        )
        license_obj = _make_license(
            f"EXPIRED-COND-{condition_type or 'OPEN'}-TEST", company, date.today() - timedelta(days=5)
        )
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type=condition_type,
        )
        _set_live_balance(license_obj, Decimal("500.00"))

        # Deliberately request 0 qty/CIF so a rejection can only be coming
        # from the expiry gate, never from insufficient balance/pool math
        # (percentage pools depend on real export-side credit, which is out
        # of scope for this expiry-focused test and is already covered by
        # test_allocate_items_cif_validation.py for the open branch).
        resp = _allocate(allotment_client, allotment_obj, item.id, "0", "0.00")

        assert resp.status_code == 400, resp.data
        assert "expired" in resp.data["errors"][0]["error"].lower()
        assert not AllotmentItems.objects.filter(allotment=allotment_obj, item=item).exists()

    @pytest.mark.parametrize("condition_type", ["", "AU"])
    def test_succeeds_for_non_expired_license_regardless_of_condition_type(
        self, allotment_client, allotment_obj, condition_type,
    ):
        # "AU" resolves available_value_calculated identically to the open
        # branch (license balance, non-transferable), so it can be exercised
        # with the same real balance setup as the open case. The "N%" pool
        # branch is covered above (rejection path only) and is unaffected by
        # this fix either way, since the expiry gate runs before it.
        company = CompanyModel.objects.create(
            iec=f"406111{abs(hash(condition_type)) % 10000:04d}",
            name=f"Active Condition {condition_type or 'OPEN'} Co",
        )
        license_obj = _make_license(
            f"ACTIVE-COND-{condition_type or 'OPEN'}-TEST", company, date.today() + timedelta(days=60)
        )
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type=condition_type,
        )
        _set_live_balance(license_obj, Decimal("500.00"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "100.00")

        assert resp.status_code == 201, resp.data
        assert resp.data["success"] == 1
        assert resp.data["errors"] == []


class TestAllocateItemsExpiryScopedPerCompanyInSameRequest:
    """Regression scope: one company's expired license must not leak a
    rejection onto -- or a pass onto -- an unrelated company's item, even
    when both are submitted together in a single allocate-items call."""

    def test_batch_with_two_companies_rejects_only_the_expired_one(
        self, allotment_client, allotment_obj,
    ):
        expired_company = CompanyModel.objects.create(iec="4077771111", name="Batch Expired Co")
        active_company = CompanyModel.objects.create(iec="4077772222", name="Batch Active Co")

        expired_license = _make_license(
            "BATCH-EXPIRED-TEST", expired_company, date.today() - timedelta(days=10)
        )
        expired_item = LicenseImportItemsModel.objects.create(
            license=expired_license,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type="",
        )
        _set_live_balance(expired_license, Decimal("500.00"))

        active_license = _make_license(
            "BATCH-ACTIVE-TEST", active_company, date.today() + timedelta(days=60)
        )
        active_item = LicenseImportItemsModel.objects.create(
            license=active_license,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("500.00"),
            condition_type="",
        )
        _set_live_balance(active_license, Decimal("500.00"))

        url = f"/api/allotment-actions/{allotment_obj.id}/allocate-items/"
        resp = allotment_client.post(
            url,
            {"allocations": [
                {"item_id": expired_item.id, "qty": "100", "cif_fc": "100.00"},
                {"item_id": active_item.id, "qty": "100", "cif_fc": "100.00"},
            ]},
            format="json",
        )

        # Overall status is 201 whenever at least one item succeeds (mixed
        # batch result) -- see allocate_items' final Response: it is 400
        # only when created_items is empty. The per-item errors array is
        # what actually reports the expired item's rejection.
        assert resp.status_code == 201, resp.data
        assert resp.data["success"] == 1
        assert len(resp.data["errors"]) == 1
        assert resp.data["errors"][0]["item_id"] == expired_item.id
        assert "expired" in resp.data["errors"][0]["error"].lower()

        assert not AllotmentItems.objects.filter(allotment=allotment_obj, item=expired_item).exists()
        assert AllotmentItems.objects.filter(allotment=allotment_obj, item=active_item).exists()
