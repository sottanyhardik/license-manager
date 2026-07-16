from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Q

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel


@pytest.fixture
def simple_item_filters(monkeypatch):
    definitions = [
        {
            "base_name": "SUGAR",
            "norms": ["E1"],
            "filters": [Q(description__icontains="sugar")],
        }
    ]
    monkeypatch.setattr(
        "apps.license.management.commands.populate_license_items.get_item_filters",
        lambda: definitions,
    )
    return definitions


@pytest.fixture
def e1_norm():
    head_norm = HeadSIONNormsModel.objects.create(name="E1 Head")
    return SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E1")


@pytest.fixture
def matching_import_item(e1_norm):
    license_obj = LicenseDetailsModel.objects.create(license_number="POP-LIC-001")
    LicenseExportItemModel.objects.create(
        license=license_obj,
        norm_class=e1_norm,
        description="Export entitlement",
    )
    return LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Refined sugar crystals",
    )


@pytest.mark.django_db
def test_populate_license_items_dry_run_does_not_create_or_link(simple_item_filters, matching_import_item):
    stdout = StringIO()

    call_command("populate_license_items", "--dry-run", stdout=stdout)

    assert not ItemNameModel.objects.filter(name="SUGAR - E1").exists()
    assert matching_import_item.items.count() == 0
    assert "Would create: SUGAR - E1" in stdout.getvalue()


@pytest.mark.django_db
def test_populate_license_items_does_not_clear_existing_links_without_clear(simple_item_filters, matching_import_item):
    existing_item = ItemNameModel.objects.create(name="EXISTING ITEM")
    matching_import_item.items.add(existing_item)

    call_command("populate_license_items", "--batch-size", "1", stdout=StringIO())

    linked_names = set(matching_import_item.items.values_list("name", flat=True))
    assert linked_names == {"EXISTING ITEM", "SUGAR - E1"}


@pytest.mark.django_db
def test_populate_license_items_clear_removes_existing_links_before_rebuild(simple_item_filters, matching_import_item):
    existing_item = ItemNameModel.objects.create(name="EXISTING ITEM")
    matching_import_item.items.add(existing_item)

    call_command("populate_license_items", "--clear", stdout=StringIO())

    linked_names = set(matching_import_item.items.values_list("name", flat=True))
    assert linked_names == {"SUGAR - E1"}


@pytest.mark.django_db
def test_populate_license_items_is_repeat_safe(simple_item_filters, matching_import_item):
    call_command("populate_license_items", "--batch-size", "1", stdout=StringIO())
    call_command("populate_license_items", "--batch-size", "1", stdout=StringIO())

    item = ItemNameModel.objects.get(name="SUGAR - E1")
    assert matching_import_item.items.filter(id=item.id).count() == 1
    assert ItemNameModel.objects.filter(name="SUGAR - E1").count() == 1


def test_populate_license_items_rejects_invalid_batch_size(simple_item_filters):
    with pytest.raises(CommandError, match="Batch size must be greater than zero"):
        call_command("populate_license_items", "--batch-size", "0", stdout=StringIO())


@pytest.mark.django_db
def test_populate_license_items_rejects_malformed_item_definition(monkeypatch):
    monkeypatch.setattr(
        "apps.license.management.commands.populate_license_items.get_item_filters",
        lambda: [{"base_name": " ", "norms": ["E1"], "filters": [Q(description__icontains="sugar")]}],
    )

    with pytest.raises(CommandError, match="blank base_name"):
        call_command("populate_license_items", stdout=StringIO())


@pytest.mark.django_db
def test_populate_license_items_rolls_back_when_linking_fails(
    simple_item_filters,
    matching_import_item,
    monkeypatch,
):
    def fail_linking(*args, **kwargs):
        raise RuntimeError("forced link failure")

    monkeypatch.setattr(
        "apps.license.management.commands.populate_license_items.Command._bulk_add_item_links",
        fail_linking,
    )

    with pytest.raises(RuntimeError, match="forced link failure"):
        call_command("populate_license_items", stdout=StringIO())

    assert not ItemNameModel.objects.filter(name="SUGAR - E1").exists()
    assert matching_import_item.items.count() == 0
