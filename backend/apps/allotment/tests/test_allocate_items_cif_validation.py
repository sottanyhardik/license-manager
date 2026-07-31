"""
Regression tests for the Available CIF FC sufficiency check in
`AllotmentActionViewSet.allocate_items` (backend/apps/allotment/views_actions.py).

Bug: the check used a legacy is_restricted / ItemNameModel.restriction_percentage
/ "exception license" branch that (a) predates the condition_type-driven
`available_value_calculated` model and was never migrated here (see the "is_restricted
is no longer set from ItemNameModel.restriction_percentage" comments in
license/signals.py, license/tasks.py, license/utils/item_matcher.py), and (b)
trusted the stored `available_value` column outright whenever it was merely
non-zero -- treating a stale-but-positive value as fresh. Reproduced on
license item id 33740: is_restricted=True despite an empty condition_type,
stored available_value=7.43, live available_value_calculated=154802.90 --
the legacy branch used 7.43 and rejected a perfectly valid allocation.

The fix reads `available_value_calculated` directly (same source the
Available Value column and the "available-licenses" filter already use),
with no is_restricted/exception branching.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentModel
from apps.core.models import CompanyModel, HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel

User = get_user_model()


@pytest.fixture
def allotment_client(db):
    user = User.objects.create_user(
        username="allocate-items-tester",
        email="allocate-items-tester@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="ALLOTMENT_MANAGER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def _make_license(license_number, exporter):
    return LicenseDetailsModel.objects.create(
        license_number=license_number,
        license_date=date.today() - timedelta(days=60),
        license_expiry_date=date.today() + timedelta(days=90),
        exporter=exporter,
    )


def _make_restricted_item_name(name, restriction_percentage=Decimal("10.00")):
    """An ItemNameModel with a SION norm class + restriction_percentage set
    -- the OLD (legacy) signal `allocate_items` used to decide an item was
    "restricted" (see `has_restriction` in the pre-fix code). Mirrors real
    license item 33740's linkage to 'FRUIT JUICE - E5' / 'FRUIT/COCOA - E5'
    exactly, so these tests actually exercise the legacy branch instead of
    silently falling through it (an ItemNameModel with no sion_norm_class
    makes `has_restriction` False regardless of the bug)."""
    head_norm = HeadSIONNormsModel.objects.create(name=f"Head Norm for {name}")
    norm_class = SionNormClassModel.objects.create(head_norm=head_norm, norm_class=name[:10])
    return ItemNameModel.objects.create(
        name=name,
        sion_norm_class=norm_class,
        restriction_percentage=restriction_percentage,
    )


def _set_live_balance(license_obj, balance_cif):
    """Set the license's live balance_cif. MUST be called AFTER every
    LicenseImportItemsModel on this license is created -- creating an
    import item fires a signal that recalculates balance_cif from the
    (empty, in these tests) real ledger chain, overwriting any value set
    beforehand back to 0."""
    license_obj.balance.balance_cif = balance_cif
    license_obj.balance.save(update_fields=["balance_cif"])


@pytest.fixture
def allotment_obj(db):
    company = CompanyModel.objects.create(iec="4088888888", name="Allocate Items Owner Co")
    return AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000000.00"))


def _allocate(client, allotment_obj, item_id, qty, cif_fc):
    url = f"/api/allotment-actions/{allotment_obj.id}/allocate-items/"
    return client.post(
        url,
        {"allocations": [{"item_id": item_id, "qty": str(qty), "cif_fc": str(cif_fc)}]},
        format="json",
    )


class TestAllocateItemsUsesLiveBalance:
    def test_succeeds_despite_stale_is_restricted_flag_and_stale_stored_available_value(
        self, allotment_client, allotment_obj,
    ):
        # Reproduces license item id 33740 exactly: is_restricted=True even
        # though condition_type is empty (the derived flag went stale), and
        # a stored available_value (7.43) far below the live balance
        # (154802.90). The fix must ignore both and use the live value.
        company = CompanyModel.objects.create(iec="4011050782", name="Allocate Items Stale Flag Co")
        license_obj = _make_license("0311050782-ALLOC-TEST", company)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=13,
            description="Milk Products",
            quantity=Decimal("50000.000"),
            available_quantity=Decimal("36017.670"),
            available_value=Decimal("7.43"),   # stale stored value
            condition_type="",                 # "open" -- available_value_calculated == license balance
        )
        item.items.add(_make_restricted_item_name("FRUIT JUICE - E5 TEST"))
        # .update() bypasses the save()/m2m_changed signals that keep
        # is_restricted derived from condition_type in sync -- simulating
        # however the real record went stale (e.g. a bulk update), since a
        # normal .save() here gets immediately resynced back to False.
        LicenseImportItemsModel.objects.filter(id=item.id).update(is_restricted=True)
        _set_live_balance(license_obj, Decimal("154802.90"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "30439", "137827.79")

        assert resp.status_code == 201, resp.data
        assert resp.data["success"] == 1
        assert resp.data["errors"] == []

    def test_rejects_when_live_balance_genuinely_insufficient(self, allotment_client, allotment_obj):
        company = CompanyModel.objects.create(iec="4022222222", name="Allocate Items Insufficient Co")
        license_obj = _make_license("ALLOC-INSUFFICIENT-TEST", company)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Milk Products",
            quantity=Decimal("500.000"),
            available_quantity=Decimal("500.000"),
            available_value=Decimal("100.00"),
            condition_type="",
        )
        _set_live_balance(license_obj, Decimal("100.00"))

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "500.00")

        assert resp.status_code == 400, resp.data
        assert resp.data["success"] == 0
        assert len(resp.data["errors"]) == 1
        assert "Insufficient available CIF FC" in resp.data["errors"][0]["error"]
        assert "Available: 100.00" in resp.data["errors"][0]["error"]

    def test_succeeds_at_exactly_the_live_balance_boundary(self, allotment_client, allotment_obj):
        company = CompanyModel.objects.create(iec="4033333333", name="Allocate Items Boundary Co")
        license_obj = _make_license("ALLOC-BOUNDARY-TEST", company)
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

        resp = _allocate(allotment_client, allotment_obj, item.id, "100", "500.00")

        assert resp.status_code == 201, resp.data
        assert resp.data["success"] == 1
