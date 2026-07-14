"""Unit tests for the `export_masters_mds` management command.

Fabricates a tiny graph in the source (`core`) models, runs the exporter, and
asserts the JSON is id-free, natural-key-keyed, and expresses every FK as the
parent's natural key — including the 3 SION models the legacy audit misses.
"""
import json
import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.core.models import (
    CompanyModel,
    ExchangeRateModel,
    HeadSIONNormsModel,
    HSCodeModel,
    ItemGroupModel,
    ItemNameModel,
    ProductDescriptionModel,
    SionNormClassModel,
    SIONExportModel,
    SIONImportModel,
    SionNormCondition,
    SionNormNote,
    UnitPriceModel,
)

NS = uuid.UUID("6f1a9d2e-0c4b-5a7e-8b3f-2d9c1e4a7b60")


def _uid(model, parent_nk, sig):
    return str(uuid.uuid5(NS, f"{model}|{parent_nk or ''}|{sig or ''}"))


@pytest.fixture
def small_graph(db):
    head = HeadSIONNormsModel.objects.create(name="Textiles")
    norm = SionNormClassModel.objects.create(head_norm=head, norm_class="E1", description="d", is_active=True)
    grp = ItemGroupModel.objects.create(name="GRP1")
    hs = HSCodeModel.objects.create(hs_code="12345678", product_description="Cotton", unit_price=Decimal("10.00"), unit="KG")
    CompanyModel.objects.create(iec="IEC0000001", name="Acme", bill_colour="#333")
    ItemNameModel.objects.create(name="Widget", group=grp, sion_norm_class=norm, display_order=1)
    ExchangeRateModel.objects.create(
        date=date(2026, 1, 1), usd=Decimal("83"), euro=Decimal("90"),
        pound_sterling=Decimal("105"), chinese_yuan=Decimal("11"),
    )
    SIONExportModel.objects.create(norm_class=norm, description="cloth", quantity=Decimal("5.00"), unit="KG")
    SIONImportModel.objects.create(
        norm_class=norm, hsn_code=hs, serial_number=1, description="yarn",
        quantity=Decimal("2.00"), unit="KG",
    )
    SionNormNote.objects.create(sion_norm=norm, note_text="note one", display_order=0)
    SionNormCondition.objects.create(sion_norm=norm, condition_text="cond one", display_order=0)
    ProductDescriptionModel.objects.create(hs_code=hs, product_description="premium cotton")
    UnitPriceModel.objects.create(name="SKU1", unit_price=Decimal("9.99"), label="per kg")
    return head


@pytest.fixture
def export(tmp_path, small_graph):
    out = tmp_path / "export.json"
    call_command("export_masters_mds", "--out", str(out))
    return json.loads(out.read_text())


def test_all_17_masters_present(export):
    expected = {
        "Company", "Port", "ItemGroup", "HSCode", "SchemeCode", "NotificationNumber",
        "ExchangeRate", "HeadSIONNorm", "SIONNormClass", "ItemHead", "ItemName",
        "SIONExport", "SIONImport", "SIONNormNote", "SIONNormCondition",
        "ProductDescription", "UnitPrice",
    }
    assert expected == set(export["tables"].keys())


def test_no_integer_ids_leak(export):
    # No record carries a raw "id"; keys are natural keys or uids.
    for t in export["tables"].values():
        for rec in t["records"]:
            assert "id" not in rec["data"]


def test_company_media_is_path_string(export):
    c = export["tables"]["Company"]["records"][0]
    # ImageField exported as string (empty when unset), not a FieldFile
    assert isinstance(c["data"]["logo"], str)
    assert c["key"] == "IEC0000001"


def test_sion_norm_class_fk_by_parent_natural_key(export):
    rec = export["tables"]["SIONNormClass"]["records"][0]
    assert rec["key"] == "E1"
    # head_norm expressed as HeadSIONNorm's synthetic uid
    assert rec["data"]["head_norm__uid"] == _uid("HeadSIONNorm", "", "Textiles")


def test_sion_export_covered_with_synthetic_uid(export):
    rec = export["tables"]["SIONExport"]["records"][0]
    assert rec["data"]["norm_class__norm_class"] == "E1"
    assert rec["key"] == _uid("SIONExport", "E1", "cloth|5.00|KG")


def test_sion_import_covered_with_fk_natural_keys(export):
    rec = export["tables"]["SIONImport"]["records"][0]
    assert rec["data"]["norm_class__norm_class"] == "E1"
    assert rec["data"]["hsn_code__hs_code"] == "12345678"


def test_head_sion_norm_covered(export):
    rec = export["tables"]["HeadSIONNorm"]["records"][0]
    assert rec["data"]["name"] == "Textiles"
    assert rec["key"] == _uid("HeadSIONNorm", "", "Textiles")


def test_item_name_fks_by_natural_key(export):
    rec = export["tables"]["ItemName"]["records"][0]
    assert rec["data"]["group__name"] == "GRP1"
    assert rec["data"]["sion_norm_class__norm_class"] == "E1"


def test_product_description_and_unit_price_keyless(export):
    pd = export["tables"]["ProductDescription"]["records"][0]
    assert pd["data"]["hs_code__hs_code"] == "12345678"
    up = export["tables"]["UnitPrice"]["records"][0]
    assert up["data"]["name"] == "SKU1"
