"""Canonical allocation scenarios against the production action endpoints."""
from datetime import date, timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.allotment.services.paired_allocation_max import calculate_paired_allocation_max
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel


pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def api():
    user = User.objects.create_user(username="canonical-allocation", password="test-pass-123")
    group, _ = Group.objects.get_or_create(name="ALLOTMENT_MANAGER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def company():
    return CompanyModel.objects.create(iec="9090909090", name="Canonical Allocation Co")


def source(company, suffix, qty="500.000", cif="5000.00"):
    license_obj = LicenseDetailsModel.objects.create(
        license_number=f"CANON-{suffix}", exporter=company,
        license_date=date.today() - timedelta(days=1), license_expiry_date=date.today() + timedelta(days=90),
    )
    LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal(cif))
    item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="Canonical Item",
        quantity=Decimal(qty), available_quantity=Decimal(qty), condition_type="",
    )
    license_obj.balance.balance_cif = Decimal(cif)
    license_obj.balance.save(update_fields=["balance_cif"])
    return item


def allotment(company, qty="1000.000", price="10.000"):
    return AllotmentModel.objects.create(
        company=company, item_name="Canonical Item", required_quantity=Decimal(qty), unit_value_per_unit=Decimal(price),
    )


def allocate(api, target, item_id, qty, cif=None):
    cif = Decimal(cif) if cif is not None else Decimal(qty) * Decimal(target.unit_value_per_unit)
    return api.post(
        f"/api/allotment-actions/{target.pk}/allocate-items/",
        {"allocations": [{"item_id": item_id, "qty": str(qty), "cif_fc": str(cif)}]}, format="json",
    )


class TestCanonicalAllocationScenarios:
    def test_01_normal(self, api, company):
        item, target = source(company, "01"), allotment(company)
        assert allocate(api, target, item.pk, "100").status_code == 201

    def test_02_partial(self, api, company):
        item, target = source(company, "02", qty="300.000", cif="3000.00"), allotment(company)
        assert allocate(api, target, item.pk, "200").status_code == 201

    def test_03_full(self, api, company):
        item, target = source(company, "03", qty="1000.000", cif="10000.00"), allotment(company)
        assert allocate(api, target, item.pk, "1000").status_code == 201
        target.refresh_from_db()
        assert target.balanced_quantity == Decimal("0.000")

    def test_04_over_quantity_rejected(self, api, company):
        item, target = source(company, "04", qty="300.000", cif="3000.00"), allotment(company)
        response = allocate(api, target, item.pk, "301")
        assert response.status_code == 400
        assert response.data["errors"][0]["code"] == "ALLOTMENT_QTY_EXCEEDS_ACTUAL"

    def test_05_zero_rejected(self, api, company):
        item, target = source(company, "05"), allotment(company)
        response = allocate(api, target, item.pk, "0", "0")
        assert response.status_code == 400

    def test_06_decimal_quantity(self, api, company):
        item, target = source(company, "06"), allotment(company)
        assert allocate(api, target, item.pk, "123.456", "1234.56").status_code == 201
        assert AllotmentItems.objects.get().qty == Decimal("123.456")

    def test_07_cross_company_actual_capacity_is_validated_not_rejected_by_owner(self, api, company):
        other = CompanyModel.objects.create(iec="8080808080", name="Other Co")
        assert allocate(api, allotment(company), source(other, "07").pk, "100").status_code == 201

    def test_08_multiple_licenses_same_company(self, api, company):
        target = allotment(company)
        assert allocate(api, target, source(company, "08A").pk, "100").status_code == 201
        assert allocate(api, target, source(company, "08B").pk, "100").status_code == 201
        assert AllotmentItems.objects.count() == 2

    def test_09_multiple_source_items(self, api, company):
        target = allotment(company)
        assert allocate(api, target, source(company, "09A").pk, "100").status_code == 201
        assert allocate(api, target, source(company, "09B").pk, "150").status_code == 201
        assert target.allotment_details.count() == 2

    def test_10_repeat_merges_same_ledger_identity(self, api, company):
        item, target = source(company, "10"), allotment(company)
        assert allocate(api, target, item.pk, "100").status_code == 201
        assert allocate(api, target, item.pk, "50").status_code == 201
        assert AllotmentItems.objects.get(allotment=target, item=item).qty == Decimal("150.000")

    def test_11_delete_releases(self, api, company):
        item, target = source(company, "11"), allotment(company)
        row = allocate(api, target, item.pk, "100").data["created_items"][0]["id"]
        assert api.delete(f"/api/allotment-actions/{target.pk}/delete-item/{row}/").status_code == 200
        assert not AllotmentItems.objects.filter(pk=row).exists()

    def test_12_duplicate_delivery_keeps_one_row(self, api, company):
        item, target = source(company, "12"), allotment(company)
        allocate(api, target, item.pk, "50")
        allocate(api, target, item.pk, "50")
        assert AllotmentItems.objects.filter(allotment=target, item=item).count() == 1

    def test_12a_final_allocation_replay_is_rejected(self, api, company):
        target = allotment(company, qty="24443.000", price="4.451")
        first = source(company, "12A", qty="22546.000", cif="100352.25")
        final = source(company, "12B", qty="1897.000", cif="8443.54")
        assert allocate(api, target, first.pk, "22546", "100352.25").status_code == 201
        first_final = allocate(api, target, final.pk, "1897", "8443.54")
        assert first_final.status_code == 201, first_final.data
        target.refresh_from_db()
        assert target.alloted_quantity == Decimal("24443.000")
        assert target.allotted_value == Decimal("108795.79")
        assert target.balanced_quantity == Decimal("0.000")
        replay = allocate(api, target, final.pk, "1897", "8443.54")
        assert replay.status_code == 400
        assert replay.data["code"] == "ALLOTMENT_REQUIREMENT_EXHAUSTED"
        assert AllotmentItems.objects.filter(allotment=target, item=final).count() == 1

    @pytest.mark.django_db(transaction=True)
    def test_12b_concurrent_final_confirms_serialize_on_locked_allotment(self, company):
        """Two independent request connections race for one final requirement.

        This deliberately uses neither mocked transactions nor mocked locks:
        the second request must wait on the parent allotment row, then see the
        first request's committed ledger debit and fail the exhaustion gate.
        """
        target = allotment(company, qty="24443.000", price="4.451")
        prior = source(company, "12B-P", qty="22546.000", cif="100352.25")
        left = source(company, "12B-L", qty="1897.000", cif="8443.54")
        right = source(company, "12B-R", qty="1897.000", cif="8443.54")
        user = User.objects.create_user(username="concurrent-allocation", password="test-pass-123")
        group, _ = Group.objects.get_or_create(name="ALLOTMENT_MANAGER")
        user.groups.add(group)
        token = str(RefreshToken.for_user(user).access_token)
        setup_client = APIClient()
        setup_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        assert allocate(setup_client, target, prior.pk, "22546", "100352.25").status_code == 201
        start = Barrier(2)

        def submit(item):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
                start.wait(timeout=10)
                response = allocate(client, target, item.pk, "1897", "8443.54")
                return response.status_code, getattr(response, "data", {})
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, (left, right)))

        statuses = sorted(status for status, _ in results)
        assert statuses == [201, 400], results
        rejected = next(data for status, data in results if status == 400)
        assert rejected["code"] == "ALLOTMENT_REQUIREMENT_EXHAUSTED"
        target.refresh_from_db()
        assert target.alloted_quantity == Decimal("24443.000")
        assert target.allotted_value == Decimal("108795.79")
        assert target.balanced_quantity == Decimal("0.000")
        assert AllotmentItems.objects.filter(allotment=target).count() == 2

    def test_13_parent_cap_blocks_second_source(self, api, company):
        target = allotment(company, qty="100.000")
        assert allocate(api, target, source(company, "13A").pk, "100").status_code == 201
        assert allocate(api, target, source(company, "13B").pk, "1").status_code == 400

    def test_14_invalid_batch_rolls_back_valid_sibling(self, api, company):
        good, bad, target = source(company, "14A"), source(company, "14B", qty="10.000", cif="100.00"), allotment(company)
        response = api.post(f"/api/allotment-actions/{target.pk}/allocate-items/", {"allocations": [
            {"item_id": good.pk, "qty": "10", "cif_fc": "100"}, {"item_id": bad.pk, "qty": "11", "cif_fc": "110"},
        ]}, format="json")
        assert response.status_code == 400 and response.data["success"] == 0 and len(response.data["errors"]) == 1
        assert not AllotmentItems.objects.filter(allotment=target).exists()

    def test_15_missing_source_rejected(self, api, company):
        response = allocate(api, allotment(company), 999999999, "1")
        assert response.status_code == 400 and "not found" in response.data["errors"][0]["error"].lower()

    def test_16_pair_mismatch_rejected(self, api, company):
        item, target = source(company, "16"), allotment(company)
        response = allocate(api, target, item.pk, "10", "99.99")
        assert response.status_code == 400 and response.data["errors"][0]["code"] == "ALLOCATION_PAIR_MISMATCH"

    def test_17_large_batch(self, api, company):
        target = allotment(company, qty="2000.000")
        items = [source(company, f"17{i:03}", qty="10.000", cif="100.00") for i in range(100)]
        response = api.post(f"/api/allotment-actions/{target.pk}/allocate-items/", {"allocations": [
            {"item_id": item.pk, "qty": "10", "cif_fc": "100"} for item in items
        ]}, format="json")
        assert response.status_code == 201 and response.data["success"] == 100

    def test_18_max_intersects_cif_and_quantity_caps(self):
        maximum = calculate_paired_allocation_max(
            quantity_ceiling=Decimal("500"), cif_ceiling=Decimal("2066.75"),
            unit_price=Decimal("8.821"), quantity_step=Decimal("1"),
        )
        assert maximum.quantity == Decimal("234") and maximum.cif == Decimal("2064.12")

    @pytest.mark.parametrize("case,qty,cif", [(19, "1", "10"), (20, "25", "250"), (21, "500", "5000")])
    def test_19_20_21_canonical_value_pair(self, api, company, case, qty, cif):
        item, target = source(company, f"{case}"), allotment(company)
        assert allocate(api, target, item.pk, qty, cif).status_code == 201

    def test_22_save_reopen_consistency(self, api, company):
        item, target = source(company, "22"), allotment(company)
        assert allocate(api, target, item.pk, "100").status_code == 201
        target.refresh_from_db()
        assert target.alloted_quantity == Decimal("100.000") and target.allotted_value == Decimal("1000.00")

    def test_23_cif_requirement_cap_blocks_later_debit(self, api, company):
        target = allotment(company, qty="500.000")
        assert allocate(api, target, source(company, "23A").pk, "500").status_code == 201
        assert allocate(api, target, source(company, "23B").pk, "1").status_code == 400
