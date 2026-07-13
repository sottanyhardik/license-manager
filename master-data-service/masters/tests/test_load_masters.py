"""Unit tests for the MDS `load_masters` hydration command.

Uses a small fabricated export dict (the same shape `export_masters_mds` writes)
to prove: topological FK resolution, business-key vs uid upsert, idempotency,
and warn+skip on missing parents.
"""
import json
import uuid

import pytest
from django.core.management import call_command

from masters.models import (
    Company,
    ExchangeRate,
    HeadSIONNorm,
    HSCode,
    ItemGroup,
    ItemName,
    ProductDescription,
    SIONExport,
    SIONImport,
    SIONNormClass,
    SIONNormCondition,
    SIONNormNote,
    UnitPrice,
)

# Shared uuid5 recipe (must mirror export_masters_mds).
NS = uuid.UUID("6f1a9d2e-0c4b-5a7e-8b3f-2d9c1e4a7b60")


def _uid(model, parent_nk, sig):
    return str(uuid.uuid5(NS, f"{model}|{parent_nk or ''}|{sig or ''}"))


HEAD_UID = _uid("HeadSIONNorm", "", "Textiles")


def _fixture_export():
    return {
        "source": "test",
        "generated_at": "2026-07-03T00:00:00",
        "tables": {
            "HeadSIONNorm": {"key_field": "uid", "count": 1, "records": [
                {"key": HEAD_UID, "data": {"name": "Textiles"}},
            ]},
            "ItemGroup": {"key_field": "name", "count": 1, "records": [
                {"key": "GRP1", "data": {"name": "GRP1"}},
            ]},
            "Company": {"key_field": "iec", "count": 1, "records": [
                {"key": "IEC0000001", "data": {
                    "iec": "IEC0000001", "name": "Acme", "pan": None, "gst_number": None,
                    "contact_person": None, "phone_number": None, "email": None,
                    "address_line_1": "", "address_line_2": "",
                    "logo": "companies/1/logo.png", "signature": "", "stamp": "",
                    "bill_colour": "#333", "bank_account_number": None, "bank_name": None,
                    "ifsc_code": None, "account_type": None,
                }},
            ]},
            "HSCode": {"key_field": "hs_code", "count": 1, "records": [
                {"key": "12345678", "data": {
                    "hs_code": "12345678", "product_description": "Cotton",
                    "unit_price": "10.00", "basic_duty": None, "unit": "KG",
                    "policy": None, "note": None,
                }},
            ]},
            "ExchangeRate": {"key_field": "date", "count": 1, "records": [
                {"key": "2026-01-01", "data": {
                    "date": "2026-01-01", "usd": "83.0000", "euro": "90.0000",
                    "pound_sterling": "105.0000", "chinese_yuan": "11.0000",
                }},
            ]},
            "SIONNormClass": {"key_field": "norm_class", "count": 2, "records": [
                {"key": "E1", "data": {
                    "norm_class": "E1", "description": "desc", "is_active": True,
                    "head_norm__uid": HEAD_UID,
                }},
                # orphan: references a HeadSIONNorm uid that does not exist -> skip
                {"key": "E2", "data": {
                    "norm_class": "E2", "description": "orphan", "is_active": False,
                    "head_norm__uid": str(uuid.uuid4()),
                }},
            ]},
            "ItemName": {"key_field": "name", "count": 1, "records": [
                {"key": "Widget", "data": {
                    "name": "Widget", "is_active": True, "restriction_percentage": "0.00",
                    "display_order": 1, "group__name": "GRP1",
                    "sion_norm_class__norm_class": "E1",
                }},
            ]},
            "SIONExport": {"key_field": "uid", "count": 1, "records": [
                {"key": _uid("SIONExport", "E1", "cloth|5.00|KG"), "data": {
                    "description": "cloth", "quantity": "5.00", "unit": "KG",
                    "norm_class__norm_class": "E1",
                }},
            ]},
            "SIONImport": {"key_field": "uid", "count": 1, "records": [
                {"key": _uid("SIONImport", "E1", "1|yarn|2.00|KG||12345678"), "data": {
                    "serial_number": 1, "description": "yarn", "quantity": "2.00",
                    "unit": "KG", "condition": None, "norm_class__norm_class": "E1",
                    "hsn_code__hs_code": "12345678",
                }},
            ]},
            "SIONNormNote": {"key_field": "uid", "count": 1, "records": [
                {"key": _uid("SIONNormNote", "E1", "0|note one"), "data": {
                    "note_text": "note one", "display_order": 0,
                    "sion_norm__norm_class": "E1",
                }},
            ]},
            "SIONNormCondition": {"key_field": "uid", "count": 1, "records": [
                {"key": _uid("SIONNormCondition", "E1", "0|cond one"), "data": {
                    "condition_text": "cond one", "display_order": 0,
                    "sion_norm__norm_class": "E1",
                }},
            ]},
            "ProductDescription": {"key_field": "uid", "count": 1, "records": [
                {"key": _uid("ProductDescription", "12345678", "premium cotton"), "data": {
                    "product_description": "premium cotton", "hs_code__hs_code": "12345678",
                }},
            ]},
            "UnitPrice": {"key_field": "uid", "count": 1, "records": [
                {"key": _uid("UnitPrice", "", "SKU1|9.99|per kg"), "data": {
                    "name": "SKU1", "unit_price": "9.99", "label": "per kg",
                }},
            ]},
        },
    }


@pytest.fixture
def export_file(tmp_path):
    path = tmp_path / "export.json"
    path.write_text(json.dumps(_fixture_export()))
    return str(path)


@pytest.mark.django_db
def test_load_hydrates_all_masters(export_file):
    call_command("load_masters", "--in", export_file)

    assert HeadSIONNorm.objects.count() == 1
    assert ItemGroup.objects.count() == 1
    assert Company.objects.get(iec="IEC0000001").name == "Acme"
    # ImageField path exported as plain string into CharField
    assert Company.objects.get(iec="IEC0000001").logo == "companies/1/logo.png"
    assert HSCode.objects.count() == 1
    assert ExchangeRate.objects.count() == 1

    # E1 resolved its head_norm; E2 orphan skipped
    assert SIONNormClass.objects.count() == 1
    e1 = SIONNormClass.objects.get(norm_class="E1")
    assert e1.head_norm.name == "Textiles"

    # children resolved to E1
    assert ItemName.objects.get(name="Widget").sion_norm_class == e1
    assert ItemName.objects.get(name="Widget").group.name == "GRP1"
    assert SIONExport.objects.get().norm_class == e1
    imp = SIONImport.objects.get()
    assert imp.norm_class == e1 and imp.hsn_code.hs_code == "12345678"
    assert SIONNormNote.objects.get().sion_norm == e1
    assert SIONNormCondition.objects.get().sion_norm == e1
    assert ProductDescription.objects.get().hs_code.hs_code == "12345678"
    assert UnitPrice.objects.get().name == "SKU1"


@pytest.mark.django_db
def test_load_is_idempotent(export_file):
    call_command("load_masters", "--in", export_file)
    first = {
        "company": Company.objects.count(),
        "norm": SIONNormClass.objects.count(),
        "export": SIONExport.objects.count(),
        "import": SIONImport.objects.count(),
        "pd": ProductDescription.objects.count(),
        "unit": UnitPrice.objects.count(),
    }
    # re-run: no duplicates (uuid5 + natural-key upsert converge)
    call_command("load_masters", "--in", export_file)
    assert Company.objects.count() == first["company"]
    assert SIONNormClass.objects.count() == first["norm"]
    assert SIONExport.objects.count() == first["export"]
    assert SIONImport.objects.count() == first["import"]
    assert ProductDescription.objects.count() == first["pd"]
    assert UnitPrice.objects.count() == first["unit"]


@pytest.mark.django_db
def test_orphan_norm_class_is_skipped_not_written(export_file):
    call_command("load_masters", "--in", export_file)
    assert not SIONNormClass.objects.filter(norm_class="E2").exists()


@pytest.mark.django_db
def test_update_changes_existing_row(export_file, tmp_path):
    call_command("load_masters", "--in", export_file)
    # mutate the company name and reload -> update, not insert
    data = _fixture_export()
    data["tables"]["Company"]["records"][0]["data"]["name"] = "Acme Renamed"
    p2 = tmp_path / "export2.json"
    p2.write_text(json.dumps(data))
    call_command("load_masters", "--in", str(p2))
    assert Company.objects.count() == 1
    assert Company.objects.get(iec="IEC0000001").name == "Acme Renamed"
