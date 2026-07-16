from django.db.models import Q
import pytest

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.utils.item_matcher import match_import_item_to_items


@pytest.fixture
def e_norms():
    head_norm = HeadSIONNormsModel.objects.create(name="E Norms")
    return {
        code: SionNormClassModel.objects.create(head_norm=head_norm, norm_class=code)
        for code in ("E1", "E5")
    }


@pytest.mark.django_db
def test_match_import_item_uses_applicable_norm_for_multi_norm_license(monkeypatch, e_norms):
    monkeypatch.setattr(
        "apps.license.utils.item_matcher.get_item_filters",
        lambda: [
            {
                "base_name": "DIETARY FIBRE",
                "norms": ["E5"],
                "filters": [Q(description__icontains="fibre")],
            }
        ],
    )
    expected = ItemNameModel.objects.create(
        name="DIETARY FIBRE - E5",
        sion_norm_class=e_norms["E5"],
    )
    ItemNameModel.objects.create(
        name="DIETARY FIBRE - E1",
        sion_norm_class=e_norms["E1"],
    )
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-001")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Dietary fibre blend",
    )

    matched = match_import_item_to_items(import_item, ["E1", "E5"])

    assert list(matched) == [expected]


@pytest.mark.django_db
def test_match_import_item_returns_empty_queryset_without_norms(monkeypatch):
    monkeypatch.setattr(
        "apps.license.utils.item_matcher.get_item_filters",
        lambda: [
            {
                "base_name": "SUGAR",
                "norms": ["E1"],
                "filters": [Q(description__icontains="sugar")],
            }
        ],
    )
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-002")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Sugar",
    )

    matched = match_import_item_to_items(import_item, [])

    assert not matched.exists()
