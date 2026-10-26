"""C969 link review: read-only list of lines whose saved item disagrees with their product name."""
from decimal import Decimal

import pytest

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.c969_link_review import c969_link_mismatches


@pytest.fixture
def norms():
    head = HeadSIONNormsModel.objects.create(name="Link review")
    return {c: SionNormClassModel.objects.create(head_norm=head, norm_class=c) for c in ("C969", "E5")}


@pytest.fixture
def items(norms):
    return {
        n: ItemNameModel.objects.create(name=n, sion_norm_class=norms["C969"])
        for n in ("AUTOMOTIVE BATTERY", "SEAT ASSEMBLY", "BEARING", "FRONT WHEELRIM", "COLD ROLLED STEEL")
    }


def _line(licence, serial, description, *items_):
    line = LicenseImportItemsModel.objects.create(license=licence, serial_number=serial, description=description, quantity=Decimal("1"))
    line.items.set(items_)
    return line


@pytest.fixture
def licence(norms):
    lic = LicenseDetailsModel.objects.create(license_number="LINK-REV-001")
    LicenseExportItemModel.objects.create(license=lic, norm_class=norms["C969"], cif_fc=Decimal("100"))
    return lic


@pytest.mark.django_db
def test_wrong_saved_item_is_listed_with_its_expected_item(licence, items):
    wrong = _line(licence, 1, "Automotive Battery-8507", items["SEAT ASSEMBLY"])

    result = c969_link_mismatches()

    assert result["count"] == 1
    assert result["rows"] == [{
        "import_item_id": wrong.pk,
        "licence_id": licence.pk,
        "licence_number": "LINK-REV-001",
        "description": "Automotive Battery-8507",
        "saved_items": ["SEAT ASSEMBLY"],
        "expected_item": "AUTOMOTIVE BATTERY",
    }]


@pytest.mark.django_db
def test_correct_and_unlinked_lines_are_not_listed(licence, items):
    _line(licence, 1, "Front Wheel Rim", items["FRONT WHEELRIM"])
    _line(licence, 2, "Front Wheel Rim")  # unlinked: nothing saved to disagree with
    _line(licence, 3, "(DELETED)", items["BEARING"])  # no product name, so nothing to verify against

    assert c969_link_mismatches() == {"count": 0, "rows": []}


@pytest.mark.django_db
def test_extra_saved_item_counts_as_a_mismatch(licence, items):
    _line(licence, 1, "Relevant cold rolled steel (Sheets / Wide coils)", items["BEARING"], items["COLD ROLLED STEEL"])

    result = c969_link_mismatches()

    assert result["count"] == 1
    assert result["rows"][0]["saved_items"] == ["BEARING", "COLD ROLLED STEEL"]
    assert result["rows"][0]["expected_item"] == "COLD ROLLED STEEL"


@pytest.mark.django_db
def test_review_changes_nothing(licence, items):
    wrong = _line(licence, 1, "Automotive Battery-8507", items["SEAT ASSEMBLY"])

    c969_link_mismatches()

    assert list(wrong.items.values_list("name", flat=True)) == ["SEAT ASSEMBLY"]


@pytest.mark.django_db
def test_other_norms_are_not_reviewed(norms, items):
    lic = LicenseDetailsModel.objects.create(license_number="LINK-REV-E5")
    LicenseExportItemModel.objects.create(license=lic, norm_class=norms["E5"], cif_fc=Decimal("100"))
    _line(lic, 1, "Automotive Battery-8507", items["SEAT ASSEMBLY"])

    assert c969_link_mismatches() == {"count": 0, "rows": []}
