from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.signals import suspend_license_flag_recalc


@pytest.fixture
def make_norm():
    head_norm = HeadSIONNormsModel.objects.create(name="Packaging Cmd Norms")

    def _make(code):
        return SionNormClassModel.objects.create(head_norm=head_norm, norm_class=code)

    return _make


def _make_license(norm, *, license_number, descriptions):
    license_obj = LicenseDetailsModel.objects.create(license_number=license_number)
    license_obj.export_license.create(norm_class=norm)
    with suspend_license_flag_recalc():
        items = [
            LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=idx,
                description=desc,
            )
            for idx, desc in enumerate(descriptions, start=1)
        ]
    return license_obj, items


@pytest.mark.django_db
def test_no_licenses_reports_and_exits_cleanly():
    stdout = StringIO()

    call_command("link_packaging_items", stdout=stdout)

    assert "No matching licences found." in stdout.getvalue()


@pytest.mark.django_db
def test_links_packaging_items_using_licence_norm(make_norm):
    e1_norm = make_norm('E1')
    _license_obj, items = _make_license(
        e1_norm, license_number="PKGCMD-001", descriptions=["LLDPE film roll", "Unrelated widget"],
    )

    stdout = StringIO()
    call_command("link_packaging_items", stdout=stdout)

    items[0].refresh_from_db()
    items[1].refresh_from_db()
    assert list(items[0].items.values_list("name", flat=True)) == ["LDPE - E1"]
    assert not items[1].items.exists()
    assert "linked 1 import item(s)" in stdout.getvalue()


@pytest.mark.django_db
def test_dry_run_does_not_create_or_link_anything(make_norm):
    e5_norm = make_norm('E5')
    _license_obj, items = _make_license(
        e5_norm, license_number="PKGCMD-002", descriptions=["HDPE granules"],
    )

    stdout = StringIO()
    call_command("link_packaging_items", "--dry-run", stdout=stdout)

    items[0].refresh_from_db()
    assert not items[0].items.exists()
    assert not ItemNameModel.objects.filter(name="HDPE - E5").exists()
    assert "RULE_HDPE -> 'HDPE' -> 'HDPE - E5'" in stdout.getvalue()
    assert "Would match 1 import item(s)" in stdout.getvalue()


@pytest.mark.django_db
def test_does_not_relink_already_linked_items_without_clear(make_norm):
    e132_norm = make_norm('E132')
    _license_obj, items = _make_license(
        e132_norm, license_number="PKGCMD-003", descriptions=["Printing Paper 250 GSM"],
    )
    legacy_name = ItemNameModel.objects.create(name="LEGACY PAPER TAG")
    items[0].items.add(legacy_name)

    call_command("link_packaging_items", stdout=StringIO())

    items[0].refresh_from_db()
    linked_names = set(items[0].items.values_list("name", flat=True))
    assert linked_names == {"LEGACY PAPER TAG"}
    assert not ItemNameModel.objects.filter(name="PAPER BOARD - E132").exists()


@pytest.mark.django_db
def test_clear_reclassifies_previously_linked_items(make_norm):
    e132_norm = make_norm('E132')
    _license_obj, items = _make_license(
        e132_norm, license_number="PKGCMD-004", descriptions=["Printing Paper 250 GSM"],
    )
    legacy_name = ItemNameModel.objects.create(name="LEGACY PAPER TAG")
    items[0].items.add(legacy_name)

    call_command("link_packaging_items", "--clear", stdout=StringIO())

    items[0].refresh_from_db()
    linked_names = set(items[0].items.values_list("name", flat=True))
    assert linked_names == {"PAPER BOARD - E132"}


@pytest.mark.django_db
def test_license_filter_limits_to_one_license(make_norm):
    e1_norm = make_norm('E1')
    _license_a, items_a = _make_license(
        e1_norm, license_number="PKGCMD-005", descriptions=["HDPE granules"],
    )
    _license_b, items_b = _make_license(
        e1_norm, license_number="PKGCMD-006", descriptions=["HDPE granules"],
    )

    call_command("link_packaging_items", "--license", "PKGCMD-005", stdout=StringIO())

    items_a[0].refresh_from_db()
    items_b[0].refresh_from_db()
    assert items_a[0].items.exists()
    assert not items_b[0].items.exists()


@pytest.mark.django_db
def test_norm_filter_limits_to_licenses_with_that_norm(make_norm):
    e1_norm = make_norm('E1')
    e5_norm = make_norm('E5')
    _license_a, items_a = _make_license(
        e1_norm, license_number="PKGCMD-007", descriptions=["HDPE granules"],
    )
    _license_b, items_b = _make_license(
        e5_norm, license_number="PKGCMD-008", descriptions=["HDPE granules"],
    )

    call_command("link_packaging_items", "--norm", "E1", stdout=StringIO())

    items_a[0].refresh_from_db()
    items_b[0].refresh_from_db()
    assert list(items_a[0].items.values_list("name", flat=True)) == ["HDPE - E1"]
    assert not items_b[0].items.exists()


@pytest.mark.django_db
def test_unknown_license_number_raises_command_error(make_norm):
    make_norm('E1')
    with pytest.raises(CommandError):
        call_command("link_packaging_items", "--license", "NOPE-DOES-NOT-EXIST", stdout=StringIO())


@pytest.mark.django_db
def test_licenses_without_any_norm_are_skipped():
    license_obj = LicenseDetailsModel.objects.create(license_number="PKGCMD-NO-NORM-001")
    with suspend_license_flag_recalc():
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="HDPE granules",
        )

    stdout = StringIO()
    call_command("link_packaging_items", stdout=stdout)

    item.refresh_from_db()
    assert not item.items.exists()
    assert "0 licence(s) found" in stdout.getvalue()
