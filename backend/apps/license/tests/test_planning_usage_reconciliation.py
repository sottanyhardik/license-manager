from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import ANY

import pytest

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.core.models import CompanyModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.serializers import LicenseItemPlanSerializer
from apps.license.services.planning_usage_reconciliation import (
    aggregate_license_usage,
    normalize_planning_family,
    reconcile_license_plans,
)


@pytest.mark.parametrize(("name", "family"), [
    ("PKO", "PKO"),
    (" palm   kernel oil ", "PKO"),
    ("PALM KERNEL", "PKO"),
    ("PALM KERNEL OIL - E126", "PKO"),
    ("OLIVE OIL", "OLIVE_OIL"),
    ("Olive Oil - E126", "OLIVE_OIL"),
    ("CHEESE", "CHEESE"),
    ("CREAM", "CHEESE"),
    ("BUTTER", "CHEESE"),
    ("UNKNOWN PRODUCT", None),
])
def test_family_mapping(name, family):
    assert normalize_planning_family(name) == family


@pytest.fixture
def reconciliation_setup(db):
    company = CompanyModel.objects.create(iec="LEVEL2REC", name="Level 2 Reconciliation")
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company,
        license_number="LEVEL2-PLAN",
        license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30),
    )
    pko = ItemNameModel.objects.create(name="PALM KERNEL OIL - E126", is_active=True)
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="Vegetable oil", unit="KG",
        quantity=Decimal("321138"), available_quantity=Decimal("321138"),
    )
    import_item.items.add(pko)
    plan = LicenseItemPlan.objects.create(
        license=license_obj, import_item=import_item, item_name=pko,
        planned_quantity=Decimal("321138"), unit_price=Decimal("1.80"),
        planned_cif_fc=Decimal("578048.40"),
    )
    return company, license_obj, import_item, plan


@pytest.mark.django_db
def test_reconciliation_subtracts_boe_and_only_unlinked_allotment(reconciliation_setup):
    company, license_obj, import_item, plan = reconciliation_setup
    boe = BillOfEntryModel.objects.create(company=company, bill_of_entry_number="BOE-L2-1", product_name="PKO")
    RowDetails.objects.create(
        bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
        qty=Decimal("20000"), cif_fc=Decimal("40000"),
    )

    open_allotment = AllotmentModel.objects.create(
        company=company, item_name="PALM KERNEL", required_quantity=Decimal("5000"),
        unit_value_per_unit=Decimal("2"),
    )
    AllotmentItems.objects.create(
        allotment=open_allotment, item=import_item, qty=Decimal("5000"), cif_fc=Decimal("10000"),
    )

    linked_allotment = AllotmentModel.objects.create(
        company=company, item_name="PKO", required_quantity=Decimal("10000"),
        unit_value_per_unit=Decimal("5"), is_boe=True,
    )
    AllotmentItems.objects.create(
        allotment=linked_allotment, item=import_item, qty=Decimal("10000"), cif_fc=Decimal("50000"), is_boe=True,
    )
    boe.allotment.add(linked_allotment)

    result = reconcile_license_plans(license_obj.id)["plans"][plan.id]
    assert result["boe_used_quantity"] == Decimal("20000")
    assert result["boe_used_cif"] == Decimal("40000")
    assert result["unlinked_allotment_quantity"] == Decimal("5000")
    assert result["unlinked_allotment_cif"] == Decimal("10000")
    assert result["effective_used_quantity"] == Decimal("25000")
    assert result["effective_used_cif"] == Decimal("50000")
    assert result["remaining_quantity"] == Decimal("296138")
    assert result["remaining_cif"] == Decimal("528048.40")
    assert result["reconciliation_status"] == "PARTIALLY_UTILIZED"

    payload = LicenseItemPlanSerializer(plan).data
    assert payload["planned_quantity"] == "321138.000"
    assert payload["planned_cif_fc"] == "578048.40"
    assert payload["remaining_quantity"] == "296138.000"
    assert payload["remaining_cif"] == "528048.40"
    assert payload["status"] == "PARTIALLY_UTILIZED"


@pytest.mark.django_db
def test_linked_allotment_and_boe_are_not_double_counted(reconciliation_setup):
    company, license_obj, import_item, _plan = reconciliation_setup
    allotment = AllotmentModel.objects.create(
        company=company, item_name="PKO", required_quantity=Decimal("10000"),
        unit_value_per_unit=Decimal("5"),
    )
    AllotmentItems.objects.create(
        allotment=allotment, item=import_item, qty=Decimal("10000"), cif_fc=Decimal("50000"),
    )
    boe = BillOfEntryModel.objects.create(company=company, bill_of_entry_number="BOE-L2-DEDUPE", product_name="PKO")
    boe.allotment.add(allotment)
    RowDetails.objects.create(
        bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
        qty=Decimal("10000"), cif_fc=Decimal("50000"),
    )

    pko = aggregate_license_usage(license_obj.id)["families"]["PKO"]
    assert pko["boe_used_quantity"] == Decimal("10000")
    assert pko["boe_used_cif"] == Decimal("50000")
    assert pko["unlinked_allotment_quantity"] == Decimal("0")
    assert pko["unlinked_allotment_cif"] == Decimal("0")


@pytest.mark.django_db
def test_unknown_usage_is_reported_not_applied(reconciliation_setup):
    company, license_obj, import_item, plan = reconciliation_setup
    unknown = ItemNameModel.objects.create(name="MYSTERY POWDER", is_active=True)
    import_item.items.clear()
    import_item.items.add(unknown)
    boe = BillOfEntryModel.objects.create(company=company, bill_of_entry_number="BOE-UNKNOWN", product_name="MYSTERY POWDER")
    RowDetails.objects.create(
        bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
        qty=Decimal("25"), cif_fc=Decimal("75"),
    )

    result = reconcile_license_plans(license_obj.id)
    assert result["plans"][plan.id]["effective_used_quantity"] == Decimal("0")
    assert result["unmapped_usage"] == [{
        "source": "BOE", "record_id": ANY,
        "record_number": "BOE-UNKNOWN", "product_name": "MYSTERY POWDER",
        "quantity": Decimal("25"), "cif_fc": Decimal("75"),
    }]
