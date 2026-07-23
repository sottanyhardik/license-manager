from datetime import date
from decimal import Decimal

import pytest

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel
from apps.core.models import CompanyModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.plan_enforcement import (
    live_allotted_qty,
    live_allotted_qty_for,
    live_allotted_value,
    live_allotted_value_for,
    plan_status_for,
    save_plan_lines_for_license,
)


@pytest.fixture
def company():
    return CompanyModel.objects.create(iec="2234567890", name="Plan Exporter")


@pytest.fixture
def port():
    return PortModel.objects.create(code="INPLN1", name="Plan Port")


@pytest.fixture
def import_item(company, port):
    license_obj = LicenseDetailsModel.objects.create(
        license_number="PLAN-ENFORCE-001",
        license_date=date.today(),
        license_expiry_date=date.today(),
        exporter=company,
        port=port,
    )
    return LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Plan item",
        quantity=Decimal("100.000"),
        available_quantity=Decimal("100.000"),
        cif_fc=Decimal("1000.00"),
    )


def _allotment(company, *, row_type="AT"):
    return AllotmentModel.objects.create(
        company=company,
        type=row_type,
        item_name="Plan item",
        required_quantity=Decimal("1.00"),
    )


@pytest.mark.django_db
def test_live_allotted_helpers_sum_only_non_boe_at_rows(import_item, company, port):
    included = _allotment(company, row_type="AT")
    aro = _allotment(company, row_type="AR")
    boe_allotment = _allotment(company, row_type="AT")
    boe = BillOfEntryModel.objects.create(
        company=company,
        bill_of_entry_number="BOE-PLAN-001",
        bill_of_entry_date=date.today(),
        port=port,
    )
    boe.allotment.add(boe_allotment)

    AllotmentItems.objects.create(
        allotment=included,
        item=import_item,
        qty=Decimal("5.500"),
        cif_fc=Decimal("55.25"),
    )
    AllotmentItems.objects.create(
        allotment=aro,
        item=import_item,
        qty=Decimal("7.000"),
        cif_fc=Decimal("70.00"),
    )
    AllotmentItems.objects.create(
        allotment=boe_allotment,
        item=import_item,
        qty=Decimal("9.000"),
        cif_fc=Decimal("90.00"),
    )

    assert live_allotted_qty(import_item) == Decimal("5.5")
    assert live_allotted_value(import_item) == Decimal("55.25")
    assert live_allotted_qty_for([import_item.id, import_item.id, import_item]) == Decimal("5.5")
    assert live_allotted_value_for([import_item.id, import_item.id, import_item]) == Decimal("55.25")


@pytest.mark.django_db
def test_live_allotted_helpers_return_zero_for_invalid_inputs(company):
    orphan_allotment = _allotment(company, row_type="AT")
    AllotmentItems.objects.create(
        allotment=orphan_allotment,
        item=None,
        qty=Decimal("99.000"),
        cif_fc=Decimal("99.99"),
    )

    assert live_allotted_qty(None) == Decimal("0.000")
    assert live_allotted_value(None) == Decimal("0")
    assert live_allotted_qty_for(None) == Decimal("0.000")
    assert live_allotted_value_for(None) == Decimal("0")
    assert live_allotted_qty_for([None, ""]) == Decimal("0.000")
    assert live_allotted_value_for([None, ""]) == Decimal("0")


@pytest.mark.django_db
def test_plan_status_for_resets_used_when_plan_is_replaced(import_item, company):
    """
    Regression test for a real production scenario: an item is auto-planned
    for 76,571 units, gets fully allotted against that plan (Used == Original,
    fine), then the plan is edited down to just the 13,247 units still
    available. `plan_status_for` must treat "Used" as allotments made SINCE
    the CURRENT plan was (re)saved — old allotments predating it are out of
    scope for it, so Remaining should equal the new Original exactly, not a
    nonsensical -63,324 (Original minus ALL-time usage, including usage from
    before the re-plan).

    Goes through `save_plan_lines_for_license` (the real save path used by
    bulk_upsert/auto-plan) rather than constructing `LicenseItemPlan` rows
    directly, so this also catches bugs in the baseline-snapshotting itself.
    """
    old_allotment = _allotment(company, row_type="AT")
    AllotmentItems.objects.create(
        allotment=old_allotment,
        item=import_item,
        qty=Decimal("76571.000"),
        cif_fc=Decimal("137827.80"),
    )

    # Re-plan: replace with a smaller cap matching what's left available.
    save_plan_lines_for_license(import_item.license, [{
        "import_item": import_item.id,
        "planned_quantity": Decimal("13247.000"),
        "unit_price": Decimal("1.80"),
        "planned_cif_fc": Decimal("23844.60"),
    }])

    status = plan_status_for(import_item)
    assert status["original_quantity"] == Decimal("13247.000")
    assert status["used_quantity"] == Decimal("0.000")
    assert status["remaining_quantity"] == Decimal("13247.000")
    assert status["original_cif_fc"] == Decimal("23844.60")
    assert status["used_cif_fc"] == Decimal("0.00")
    assert status["remaining_cif_fc"] == Decimal("23844.60")


@pytest.mark.django_db
def test_plan_status_for_counts_allotments_made_after_replan(import_item, company):
    """New allotments made AFTER the current plan was saved must still count."""
    save_plan_lines_for_license(import_item.license, [{
        "import_item": import_item.id,
        "planned_quantity": Decimal("13247.000"),
        "unit_price": Decimal("1.80"),
        "planned_cif_fc": Decimal("23844.60"),
    }])
    new_allotment = _allotment(company, row_type="AT")
    AllotmentItems.objects.create(
        allotment=new_allotment,
        item=import_item,
        qty=Decimal("1000.000"),
        cif_fc=Decimal("1800.00"),
    )

    status = plan_status_for(import_item)
    assert status["used_quantity"] == Decimal("1000.000")
    assert status["remaining_quantity"] == Decimal("12247.000")


@pytest.mark.django_db
def test_plan_status_for_used_survives_amended_allotment_row(import_item, company):
    """
    Regression test for the specific bug that broke a `created_on`-based
    "since" filter: `allocate_items` AMENDS an existing `AllotmentItems` row
    in place (`existing.qty += qty`) when the same allotment gets more of the
    same item added to it, rather than creating a new row — so that row's
    `created_on` never advances. A fix based on filtering by timestamp would
    silently miss any such amendment made after a re-plan. The baseline
    snapshot must not have this blind spot: it only cares about the CURRENT
    all-time total, not which row (or when) carries it.
    """
    allotment = _allotment(company, row_type="AT")
    row = AllotmentItems.objects.create(
        allotment=allotment, item=import_item,
        qty=Decimal("63324.000"), cif_fc=Decimal("113983.20"),
    )

    save_plan_lines_for_license(import_item.license, [{
        "import_item": import_item.id,
        "planned_quantity": Decimal("13247.000"),
        "unit_price": Decimal("1.80"),
        "planned_cif_fc": Decimal("23844.60"),
    }])
    assert plan_status_for(import_item)["remaining_quantity"] == Decimal("13247.000")

    # Amend the SAME row (as allocate_items does), simulating "13,246 more
    # allotted after the re-plan" — created_on is untouched by this update.
    row.qty += Decimal("13246.000")
    row.cif_fc += Decimal("23842.80")
    row.save(update_fields=["qty", "cif_fc"])

    status = plan_status_for(import_item)
    assert status["used_quantity"] == Decimal("13246.000")
    assert status["remaining_quantity"] == Decimal("1.000")
    assert status["remaining_cif_fc"] == Decimal("1.80")
