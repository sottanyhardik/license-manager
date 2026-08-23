"""
Regression tests for `LicenseItemPlanViewSet.bulk_upsert`'s per-group capacity
check (`apps/license/views/item_plan.py`) after `plan_grouping.plan_group_key`
became HSN-aware (HSN + normalized description, not description alone).

Real-world case: license 0311009149 has three import items sharing the
description "RELEVANT TARTARIC ACID (FOOD GRADE RELEVANT )" split across two
HSNs (29181400: qty 9458.810; 29181200 x2: qty 153.000 + 549.110). Under the
OLD description-only grouping all three pooled into one capacity (10160.920),
and a real saved plan used exactly that pooled total on the representative
item. Under the NEW HSN-aware grouping, the 29181400 item is its own group
with its own capacity (9458.810 only) — the same save must now be rejected,
and a correctly-split save (one line per HSN sub-group) must succeed.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import CompanyModel, HSCodeModel
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan,
)

User = get_user_model()

BULK_UPSERT_URL = "/api/license-item-plans/bulk-upsert/"


@pytest.fixture
def license_manager_client(db, tartaric_acid_license):
    license_obj = tartaric_acid_license[0]
    user = User.objects.create_user(
        username="item-plan-manager",
        email="item-plan-manager@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def _hs(code):
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


@pytest.fixture
def tartaric_acid_license(db):
    company = CompanyModel.objects.create(iec="5234567890", name="Tartaric Acid Exporter")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="0311009149-TEST",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30),
        exporter=company,
    )
    LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("50000.00"))
    desc = "RELEVANT TARTARIC ACID (FOOD GRADE RELEVANT )"
    item_29181400 = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=4, description=desc,
        hs_code=_hs("29181400"),
        quantity=Decimal("9458.810"), available_quantity=Decimal("9458.810"),
    )
    item_29181200_a = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=14, description=desc,
        hs_code=_hs("29181200"),
        quantity=Decimal("153.000"), available_quantity=Decimal("153.000"),
    )
    item_29181200_b = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=24, description=desc,
        hs_code=_hs("29181200"),
        quantity=Decimal("549.110"), available_quantity=Decimal("549.110"),
    )
    return license_obj, item_29181400, item_29181200_a, item_29181200_b


@pytest.mark.django_db
def test_pooling_two_different_hsn_items_under_one_plan_line_is_capped_to_its_hsn_group(
    license_manager_client, tartaric_acid_license,
):
    # This reproduces the OLD (description-only) behaviour that let a single
    # plan line on one item (HSN 29181400, capacity 9458.810) absorb the
    # total pooled across BOTH HSNs (10160.920). HSN grouping must prevent that:
    # the valid 29181400 portion is saved and the exact unavailable portion is
    # returned as a shortage rather than abandoning the rest of the plan.
    license_obj, item_29181400, item_a, item_b = tartaric_acid_license

    resp = license_manager_client.post(BULK_UPSERT_URL, {
        "license": license_obj.id,
        "lines": [{
            "import_item": item_29181400.id,
            "item_name": None,
            "planned_quantity": "10160.920",
            "unit_price": "1.50",
            "planned_cif_fc": "15241.38",
            "note": "",
        }],
    }, format="json")

    assert resp.status_code == 200, resp.data
    assert resp.data["saved"] == 1
    (line,) = resp.data["lines"]
    assert Decimal(str(line["planned_quantity"])) == Decimal("9458.810")
    assert Decimal(str(line["requested_planned_qty"])) == Decimal("10160.920")
    assert Decimal(str(line["effective_planned_qty"])) == Decimal("9458.810")
    assert Decimal(str(line["capped_qty"])) == Decimal("702.110")
    assert line["was_quantity_capped"] is True


@pytest.mark.django_db
def test_correctly_split_plan_across_hsn_groups_is_accepted(
    license_manager_client, tartaric_acid_license,
):
    license_obj, item_29181400, item_a, item_b = tartaric_acid_license

    resp = license_manager_client.post(BULK_UPSERT_URL, {
        "license": license_obj.id,
        "lines": [
            {
                "import_item": item_29181400.id, "item_name": None,
                "planned_quantity": "9458.810", "unit_price": "1.50",
                "planned_cif_fc": "14188.22", "note": "",
            },
            {
                "import_item": item_a.id, "item_name": None,
                "planned_quantity": "702.110", "unit_price": "1.50",
                "planned_cif_fc": "1053.17", "note": "",
            },
        ],
    }, format="json")

    assert resp.status_code == 200, resp.data
    assert resp.data["saved"] == 2
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 2


@pytest.mark.django_db
def test_pooling_within_the_same_hsn_subgroup_still_works(
    license_manager_client, tartaric_acid_license,
):
    # item_a and item_b are the SAME HSN (29181200) and description — they
    # remain one pooled group (153.000 + 549.110 = 702.110 capacity), same
    # as before this change.
    license_obj, item_29181400, item_a, item_b = tartaric_acid_license

    resp = license_manager_client.post(BULK_UPSERT_URL, {
        "license": license_obj.id,
        "lines": [{
            "import_item": item_a.id, "item_name": None,
            "planned_quantity": "702.110", "unit_price": "1.50",
            "planned_cif_fc": "1053.17", "note": "",
        }],
    }, format="json")

    assert resp.status_code == 200, resp.data
