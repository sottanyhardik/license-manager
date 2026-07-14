"""
Tests for the deterministic `uid` on the 7 keyless masters (ADR-001 Decision 6).

The critical property proved here: the uid a consumer row computes on `save()`
is IDENTICAL to the uid the MDS exporter assigns for the same logical row. If
they ever diverge, the mirror sync would create duplicates instead of converging.
These tests fabricate a small graph, run the exporter, and assert per-model that
`model.uid == export["tables"][...]["records"][i]["key"]`.
"""
import json
import uuid
from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.core.models import (
    HeadSIONNormsModel,
    HSCodeModel,
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
def graph(db):
    head = HeadSIONNormsModel.objects.create(name="Textiles")
    norm = SionNormClassModel.objects.create(head_norm=head, norm_class="E1", description="d", is_active=True)
    hs = HSCodeModel.objects.create(hs_code="12345678", product_description="Cotton", unit_price=Decimal("10.00"), unit="KG")
    exp = SIONExportModel.objects.create(norm_class=norm, description="cloth", quantity=Decimal("5.00"), unit="KG")
    imp = SIONImportModel.objects.create(
        norm_class=norm, hsn_code=hs, serial_number=1, description="yarn",
        quantity=Decimal("2.00"), unit="KG",
    )
    note = SionNormNote.objects.create(sion_norm=norm, note_text="note one", display_order=0)
    cond = SionNormCondition.objects.create(sion_norm=norm, condition_text="cond one", display_order=0)
    pd = ProductDescriptionModel.objects.create(hs_code=hs, product_description="premium cotton")
    up = UnitPriceModel.objects.create(name="SKU1", unit_price=Decimal("9.99"), label="per kg")
    return dict(head=head, norm=norm, hs=hs, exp=exp, imp=imp, note=note, cond=cond, pd=pd, up=up)


def test_save_populates_uid_deterministically(graph):
    # Every keyless row gets a uuid5 (version 5), not a random uuid4.
    for obj in (graph["head"], graph["exp"], graph["imp"], graph["note"],
                graph["cond"], graph["pd"], graph["up"]):
        assert obj.uid is not None
        # save() sets a str; the field returns a UUID after a DB round-trip.
        assert uuid.UUID(str(obj.uid)).version == 5


def test_uid_matches_expected_recipe(graph):
    assert str(graph["head"].uid) == _uid("HeadSIONNorm", "", "Textiles")
    assert str(graph["exp"].uid) == _uid("SIONExport", "E1", "cloth|5.00|KG")
    assert str(graph["imp"].uid) == _uid("SIONImport", "E1", "1|yarn|2.00|KG||12345678")
    assert str(graph["note"].uid) == _uid("SIONNormNote", "E1", "0|note one")
    assert str(graph["cond"].uid) == _uid("SIONNormCondition", "E1", "0|cond one")
    assert str(graph["pd"].uid) == _uid("ProductDescription", "12345678", "premium cotton")
    assert str(graph["up"].uid) == _uid("UnitPrice", "", "SKU1|9.99|per kg")


def test_consumer_uid_equals_exporter_key(graph, tmp_path):
    """The whole point: model.save() uid == exporter's emitted key for that row."""
    out = tmp_path / "export.json"
    call_command("export_masters_mds", "--out", str(out))
    tables = json.loads(out.read_text())["tables"]

    def key(table):
        return tables[table]["records"][0]["key"]

    assert str(graph["head"].uid) == key("HeadSIONNorm")
    assert str(graph["exp"].uid) == key("SIONExport")
    assert str(graph["imp"].uid) == key("SIONImport")
    assert str(graph["note"].uid) == key("SIONNormNote")
    assert str(graph["cond"].uid) == key("SIONNormCondition")
    assert str(graph["pd"].uid) == key("ProductDescription")
    assert str(graph["up"].uid) == key("UnitPrice")


def test_uid_is_stable_across_resave(graph):
    exp = graph["exp"]
    original = str(exp.uid)
    exp.save()  # re-save must not change an already-set uid
    exp.refresh_from_db()
    assert str(exp.uid) == original


def test_uid_recomputes_when_blanked(graph):
    exp = graph["exp"]
    expected = str(exp.uid)
    exp.uid = None
    exp.save()
    assert str(exp.uid) == expected  # save() backfills a missing uid deterministically
