from datetime import date
from decimal import Decimal

import pytest

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.models import CompanyModel, HSCodeModel, ItemNameModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.plan_enforcement import save_plan_lines_for_license
from apps.license.services.plan_utilization import plan_utilization_rows


@pytest.fixture
def company():
    return CompanyModel.objects.create(iec="4234567890", name="Utilization Exporter")


@pytest.fixture
def port():
    return PortModel.objects.create(code="INUTL1", name="Utilization Port")


@pytest.fixture
def license_obj(company, port):
    return LicenseDetailsModel.objects.create(
        license_number="PLAN-UTIL-001",
        license_date=date.today(),
        license_expiry_date=date.today(),
        exporter=company,
        port=port,
    )


def _import_item(license_obj, serial_number, description="", hs_code=None, **kwargs):
    defaults = dict(
        quantity=Decimal("10.000"),
        available_quantity=Decimal("10.000"),
        available_value=Decimal("100.00"),
    )
    defaults.update(kwargs)
    return LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=serial_number,
        description=description,
        hs_code=hs_code,
        **defaults,
    )


def _allotment(company, *, row_type="AT"):
    return AllotmentModel.objects.create(
        company=company,
        type=row_type,
        item_name="Utilization item",
        required_quantity=Decimal("1.00"),
    )


@pytest.mark.django_db
def test_merges_by_description_and_picks_lowest_serial_as_representative(license_obj):
    hs = HSCodeModel.objects.create(hs_code="15119090")
    item_23 = _import_item(license_obj, 23, "Refined Cane Sugar", hs_code=hs)
    item_3 = _import_item(license_obj, 3, "refined cane sugar")
    item_13 = _import_item(license_obj, 13, " REFINED CANE SUGAR ")
    other = _import_item(license_obj, 5, "Raw Sugar")

    rows = plan_utilization_rows(license_obj)

    assert len(rows) == 2
    sugar_row = rows[0]
    assert sugar_row["group_id"] == item_3.id  # lowest serial number wins
    assert sugar_row["serials"] == [3, 13, 23]
    assert sugar_row["member_ids"] == [item_3.id, item_13.id, item_23.id]  # serial order
    assert sugar_row["hs_code"] == "15119090"  # first non-empty across members
    assert sugar_row["available_quantity"] == Decimal("30.000")
    assert sugar_row["total_quantity"] == Decimal("30.000")
    assert sugar_row["balance_cif_fc"] == Decimal("300.00")

    raw_row = rows[1]
    assert raw_row["group_id"] == other.id
    assert raw_row["serials"] == [5]


@pytest.mark.django_db
def test_falls_back_to_item_names_then_id_for_description(license_obj):
    borax = ItemNameModel.objects.create(name="borax")
    rutile = ItemNameModel.objects.create(name="Rutile")
    named = _import_item(license_obj, 1)
    named.items.add(rutile, borax)
    unnamed = _import_item(license_obj, 2)

    rows = {r["group_id"]: r for r in plan_utilization_rows(license_obj)}

    assert rows[named.id]["description"] == "borax, Rutile"
    assert rows[named.id]["item_names"] == [
        {"id": borax.id, "name": "borax"},
        {"id": rutile.id, "name": "Rutile"},
    ]
    assert rows[unnamed.id]["description"] == f"ID:{unnamed.id}"
    assert rows[unnamed.id]["item_names"] == []


@pytest.mark.django_db
def test_splits_and_plan_status_are_unioned_and_group_level(license_obj, company):
    item_3 = _import_item(license_obj, 3, "Liquid Glucose")
    item_13 = _import_item(license_obj, 13, "liquid glucose")

    save_plan_lines_for_license(license_obj, [{
        "import_item": item_3.id,  # representative (lowest serial)
        "planned_quantity": Decimal("6.000"),
        "unit_price": Decimal("2.00"),
        "planned_cif_fc": Decimal("12.00"),
    }])

    allotment = _allotment(company)
    AllotmentItems.objects.create(
        allotment=allotment, item=item_13,  # allotted against the OTHER member
        qty=Decimal("4.000"), cif_fc=Decimal("8.00"),
    )

    rows = plan_utilization_rows(license_obj)
    assert len(rows) == 1
    row = rows[0]

    assert row["has_plan"] is True
    assert row["original_quantity"] == Decimal("6.000")
    assert row["used_quantity"] == Decimal("4.000")
    assert row["remaining_quantity"] == Decimal("2.000")
    assert row["original_cif_fc"] == Decimal("12.00")
    assert row["used_cif_fc"] == Decimal("8.00")
    assert row["remaining_cif_fc"] == Decimal("4.00")
    assert len(row["splits"]) == 1
    assert row["splits"][0]["planned_quantity"] == 6.0


@pytest.mark.django_db
def test_has_plan_false_when_group_has_no_plan_rows(license_obj):
    _import_item(license_obj, 1, "Unplanned Item")

    rows = plan_utilization_rows(license_obj)

    assert rows[0]["has_plan"] is False
    assert "original_quantity" not in rows[0]


@pytest.mark.django_db
def test_grand_totals_match_the_ungrouped_raw_item_sums(license_obj):
    _import_item(license_obj, 3, "Refined Cane Sugar", available_quantity=Decimal("5.000"),
                 quantity=Decimal("5.000"), available_value=Decimal("50.00"))
    _import_item(license_obj, 13, "Refined Cane Sugar", available_quantity=Decimal("7.000"),
                 quantity=Decimal("7.000"), available_value=Decimal("70.00"))
    _import_item(license_obj, 23, "Refined Cane Sugar", available_quantity=Decimal("2.000"),
                 quantity=Decimal("2.000"), available_value=Decimal("20.00"))
    _import_item(license_obj, 5, "Raw Sugar", available_quantity=Decimal("3.000"),
                 quantity=Decimal("3.000"), available_value=Decimal("30.00"))

    raw_items = list(license_obj.import_license.all())
    raw_avail_total = sum((i.available_quantity for i in raw_items), Decimal("0"))
    raw_qty_total = sum((i.quantity for i in raw_items), Decimal("0"))
    raw_cif_total = sum((i.available_value for i in raw_items), Decimal("0"))

    rows = plan_utilization_rows(license_obj)
    assert len(rows) == 2  # merged: Refined Cane Sugar (x3) + Raw Sugar

    grouped_avail_total = sum((r["available_quantity"] for r in rows), Decimal("0"))
    grouped_qty_total = sum((r["total_quantity"] for r in rows), Decimal("0"))
    grouped_cif_total = sum((r["balance_cif_fc"] for r in rows), Decimal("0"))

    assert grouped_avail_total == raw_avail_total
    assert grouped_qty_total == raw_qty_total
    assert grouped_cif_total == raw_cif_total


@pytest.mark.django_db
def test_accepts_explicit_items_and_precomputed_plan_map(license_obj):
    item_1 = _import_item(license_obj, 1, "Filtered Item")
    _import_item(license_obj, 2, "Excluded Item")  # not passed in `items`

    rows = plan_utilization_rows(license_obj, items=[item_1], plan_map={})
    assert len(rows) == 1
    assert rows[0]["group_id"] == item_1.id


def test_handles_no_import_items_without_error():
    class _FakeManager:
        def all(self):
            return []

    class _FakeLicense:
        id = 999999
        import_license = _FakeManager()

    assert plan_utilization_rows(_FakeLicense(), plan_map={}) == []
