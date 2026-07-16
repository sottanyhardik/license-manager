from datetime import date
from decimal import Decimal

import pytest

from apps.core.models import CompanyModel, ItemNameModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.plan_grouping import group_ids_of, plan_group_key


@pytest.fixture
def company():
    return CompanyModel.objects.create(iec="3234567890", name="Grouping Exporter")


@pytest.fixture
def port():
    return PortModel.objects.create(code="INGRP1", name="Grouping Port")


@pytest.fixture
def license_obj(company, port):
    return LicenseDetailsModel.objects.create(
        license_number="PLAN-GROUP-001",
        license_date=date.today(),
        license_expiry_date=date.today(),
        exporter=company,
        port=port,
    )


def _import_item(license_obj, serial_number, description=""):
    return LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=serial_number,
        description=description,
        quantity=Decimal("10.000"),
        available_quantity=Decimal("10.000"),
    )


@pytest.mark.django_db
def test_plan_grouping_uses_trimmed_uppercase_description(license_obj):
    item_a = _import_item(license_obj, 1, "  Refined Sugar ")
    item_b = _import_item(license_obj, 2, "refined sugar")
    item_c = _import_item(license_obj, 3, "Raw Sugar")

    assert plan_group_key(item_a) == "REFINED SUGAR"
    assert group_ids_of(item_a) == [item_a.id, item_b.id]
    assert group_ids_of(item_c) == [item_c.id]


@pytest.mark.django_db
def test_plan_grouping_falls_back_to_sorted_item_names(license_obj):
    borax = ItemNameModel.objects.create(name="borax")
    rutile = ItemNameModel.objects.create(name="Rutile")
    item = _import_item(license_obj, 1)
    item.items.add(rutile, borax)

    assert plan_group_key(item) == "N:BORAX, RUTILE"
    assert group_ids_of(item) == [item.id]


def test_plan_grouping_handles_invalid_inputs_without_queries():
    assert plan_group_key(None) == "ID:None"
    assert group_ids_of(None) == []
    assert group_ids_of(LicenseImportItemsModel(description="Unsaved")) == []
