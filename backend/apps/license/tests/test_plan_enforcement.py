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
