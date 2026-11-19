"""Owner decision 2026-11-19 (decision 3): Sunflower Oil counts toward the Olive Oil entitlement on E5 as well as
E126 — HSN 1512 + "sunflower", never when the record carries the PKO (1513) signal, never on E132 / A3627.
Exercises the real ``get_item_filters`` configuration (no monkeypatching)."""
import pytest

from apps.core.models import HeadSIONNormsModel, HSCodeModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.utils.item_matcher import get_item_filters, match_import_item_to_items


def _norm(code: str) -> SionNormClassModel:
    return SionNormClassModel.objects.create(head_norm=HeadSIONNormsModel.objects.create(name=f"{code} Norms"), norm_class=code)


def _record(n: int, hsn: str, description: str) -> LicenseImportItemsModel:
    licence = LicenseDetailsModel.objects.create(license_number=f"SUNFLOWER-{n:03d}")
    return LicenseImportItemsModel.objects.create(license=licence, serial_number=1, hs_code=HSCodeModel.objects.get_or_create(hs_code=hsn)[0],
                                                  description=description)


def _names(qs) -> list[str]:
    return sorted(qs.values_list("name", flat=True))


@pytest.fixture
def olive_masters(db):
    e5, e126 = _norm("E5"), _norm("E126")
    _norm("E132")
    _norm("A3627")
    return {"E5": ItemNameModel.objects.create(name="OLIVE OIL - E5", sion_norm_class=e5),
            "E126": ItemNameModel.objects.create(name="OLIVE OIL - E126", sion_norm_class=e126)}


@pytest.mark.django_db
@pytest.mark.parametrize("norm", ["E5", "E126"])
def test_sunflower_oil_counts_as_olive_oil_on_e5_and_e126(olive_masters, norm):
    record = _record(1, "15121190", "Refined Sunflower Oil")
    assert _names(match_import_item_to_items(record, [norm])) == [f"OLIVE OIL - {norm}"]


@pytest.mark.django_db
@pytest.mark.parametrize("norm", ["E5", "E126"])
def test_a_pko_signal_keeps_sunflower_wording_out_of_olive_oil(olive_masters, norm):
    record = _record(2, "15131900", "Sunflower / Palm kernel oil")
    assert "OLIVE OIL" not in " ".join(_names(match_import_item_to_items(record, [norm])))


@pytest.mark.django_db
def test_hsn_1512_without_sunflower_wording_is_not_olive_oil_on_e5(olive_masters):
    record = _record(3, "15121190", "Rice bran oil")
    assert "OLIVE OIL" not in " ".join(_names(match_import_item_to_items(record, ["E5"])))


@pytest.mark.django_db
@pytest.mark.parametrize("norm", ["E132", "A3627"])
def test_sunflower_is_never_olive_oil_on_restricted_norms(olive_masters, norm):
    record = _record(4, "15121190", "Refined Sunflower Oil")
    assert "OLIVE OIL" not in " ".join(_names(match_import_item_to_items(record, [norm])))


def test_configuration_scopes_the_sunflower_clause_to_e5_and_e126_only():
    clauses = [c for c in get_item_filters() if c["base_name"] == "OLIVE OIL" and any("sunflower" in str(f).lower() for f in c["filters"])]
    assert clauses and all(sorted(c["norms"]) == ["E126", "E5"] for c in clauses)


@pytest.mark.django_db
def test_bulk_auto_link_links_e5_sunflower_to_olive_oil(olive_masters):
    from decimal import Decimal

    from apps.license.models import LicenseExportItemModel
    from apps.license.utils.item_matcher import bulk_auto_link_license_items
    record = _record(5, "15121190", "Refined Sunflower Oil")
    LicenseExportItemModel.objects.create(license=record.license, norm_class=SionNormClassModel.objects.get(norm_class="E5"), cif_fc=Decimal("1"))
    record.items.clear()  # the save signal may already have linked it — exercise the bulk path explicitly
    assert bulk_auto_link_license_items(record.license) == 1
    assert _names(record.items.all()) == ["OLIVE OIL - E5"]


@pytest.mark.django_db
def test_licence_with_e5_and_e126_gets_exactly_one_olive_master(olive_masters):
    record = _record(6, "15121190", "Refined Sunflower Oil")
    olive = [n for n in _names(match_import_item_to_items(record, ["E5", "E126"])) if n.startswith("OLIVE OIL")]
    assert olive == ["OLIVE OIL - E5"]  # first licence norm decides, exactly as for the existing OLIVE OIL clause
