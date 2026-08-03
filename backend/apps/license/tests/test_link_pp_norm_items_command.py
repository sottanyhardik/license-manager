from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.signals import suspend_license_flag_recalc


@pytest.fixture
def pp_norm():
    head_norm = HeadSIONNormsModel.objects.create(name="PP Head")
    return SionNormClassModel.objects.create(head_norm=head_norm, norm_class="PP")


def _make_pp_license(pp_norm, *, license_number, descriptions):
    license_obj = LicenseDetailsModel.objects.create(license_number=license_number)
    license_obj.export_license.create(norm_class=pp_norm)
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
def test_no_pp_licenses_reports_and_exits_cleanly():
    stdout = StringIO()

    call_command("link_pp_norm_items", stdout=stdout)

    assert "No licences found with SION norm class 'PP'" in stdout.getvalue()


@pytest.mark.django_db
def test_links_pp_norm_items_across_licenses(pp_norm):
    _license_obj, items = _make_pp_license(
        pp_norm, license_number="PPCMD-001", descriptions=["LLDPE film roll", "Unrelated widget"],
    )

    stdout = StringIO()
    call_command("link_pp_norm_items", stdout=stdout)

    items[0].refresh_from_db()
    items[1].refresh_from_db()
    assert list(items[0].items.values_list("name", flat=True)) == ["LDPE - COMMON"]
    assert not items[1].items.exists()
    assert "linked 1 import item(s)" in stdout.getvalue()


@pytest.mark.django_db
def test_dry_run_does_not_create_or_link_anything(pp_norm):
    _license_obj, items = _make_pp_license(
        pp_norm, license_number="PPCMD-002", descriptions=["HDPE granules"],
    )

    stdout = StringIO()
    call_command("link_pp_norm_items", "--dry-run", stdout=stdout)

    items[0].refresh_from_db()
    assert not items[0].items.exists()
    assert not ItemNameModel.objects.filter(name="HDPE - COMMON").exists()
    assert "PP_RULE_HDPE_COMMON -> 'HDPE - COMMON'" in stdout.getvalue()
    assert "Would match 1 import item(s)" in stdout.getvalue()


@pytest.mark.django_db
def test_does_not_relink_already_linked_items_without_clear(pp_norm):
    _license_obj, items = _make_pp_license(
        pp_norm, license_number="PPCMD-003", descriptions=["PAPER 250 GSM"],
    )
    legacy_name = ItemNameModel.objects.create(name="LEGACY PAPER TAG")
    items[0].items.add(legacy_name)

    call_command("link_pp_norm_items", stdout=StringIO())

    items[0].refresh_from_db()
    linked_names = set(items[0].items.values_list("name", flat=True))
    assert linked_names == {"LEGACY PAPER TAG"}
    assert not ItemNameModel.objects.filter(name="PAPER BOARD - COMMON").exists()


@pytest.mark.django_db
def test_clear_reclassifies_previously_linked_items(pp_norm):
    _license_obj, items = _make_pp_license(
        pp_norm, license_number="PPCMD-004", descriptions=["PAPER 250 GSM"],
    )
    legacy_name = ItemNameModel.objects.create(name="LEGACY PAPER TAG")
    items[0].items.add(legacy_name)

    call_command("link_pp_norm_items", "--clear", stdout=StringIO())

    items[0].refresh_from_db()
    linked_names = set(items[0].items.values_list("name", flat=True))
    assert linked_names == {"PAPER BOARD - COMMON"}


@pytest.mark.django_db
def test_license_filter_limits_to_one_license(pp_norm):
    _license_a, items_a = _make_pp_license(
        pp_norm, license_number="PPCMD-005", descriptions=["HDPE granules"],
    )
    _license_b, items_b = _make_pp_license(
        pp_norm, license_number="PPCMD-006", descriptions=["HDPE granules"],
    )

    call_command("link_pp_norm_items", "--license", "PPCMD-005", stdout=StringIO())

    items_a[0].refresh_from_db()
    items_b[0].refresh_from_db()
    assert items_a[0].items.exists()
    assert not items_b[0].items.exists()


@pytest.mark.django_db
def test_unknown_license_number_raises_command_error(pp_norm):
    with pytest.raises(CommandError):
        call_command("link_pp_norm_items", "--license", "NOPE-DOES-NOT-EXIST", stdout=StringIO())


@pytest.mark.django_db
def test_non_pp_licenses_are_never_touched():
    head_norm = HeadSIONNormsModel.objects.create(name="E1 Head")
    e1_norm = SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E1")
    license_obj = LicenseDetailsModel.objects.create(license_number="PPCMD-NONPP-001")
    license_obj.export_license.create(norm_class=e1_norm)
    with suspend_license_flag_recalc():
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="HDPE granules",
        )

    stdout = StringIO()
    call_command("link_pp_norm_items", stdout=stdout)

    item.refresh_from_db()
    assert not item.items.exists()
    assert "0 licence(s) found" in stdout.getvalue()
