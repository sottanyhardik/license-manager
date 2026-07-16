from decimal import Decimal

import pytest

from apps.core.models import ItemGroupModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel


@pytest.mark.django_db
def test_license_item_group_data_sums_matching_group_rows():
    license_obj = LicenseDetailsModel.objects.create(license_number="GROUP-TEST-001")
    group = ItemGroupModel.objects.create(name="Glass Formers")
    item_a = ItemNameModel.objects.create(name="Rutile", group=group)
    item_b = ItemNameModel.objects.create(name="Borax", group=group)

    import_item_a = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        quantity=Decimal("12.500"),
        available_quantity=Decimal("8.250"),
    )
    import_item_a.items.add(item_a)
    import_item_b = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=2,
        quantity=Decimal("7.500"),
        available_quantity=Decimal("3.750"),
    )
    import_item_b.items.add(item_b)

    group_data = license_obj.get_item_group_data("Glass Formers")

    assert group_data["quantity_sum"] == Decimal("20.000")
    assert group_data["available_quantity_sum"] == Decimal("12.000")
    assert license_obj.get_item_head_data("Glass Formers") == group_data
