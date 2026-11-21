"""Item Name merge engine: approval gate, reference re-pointing, financial invariance, rollback."""
from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.models import (
    CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameMerge, ItemNameMergeAudit, ItemNameMergeSource, ItemNameModel, PortModel,
    SionNormClassModel,
)
from apps.core.services import item_name_merge as engine
from apps.license.models import (
    ImportDescriptionMapping, LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel,
)

pytestmark = pytest.mark.django_db
THROUGH = LicenseImportItemsModel.items.through


def _norm(code):
    head, _ = HeadSIONNormsModel.objects.get_or_create(name="Test SION Head")
    return SionNormClassModel.objects.get_or_create(norm_class=code, defaults={"head_norm": head, "description": code})[0]


@pytest.fixture
def world():
    e1, e5 = _norm("E1"), _norm("E5")
    canonical = ItemNameModel.objects.create(name="ZZT MERGE BOARD")
    canonical.norms.add(e1, e5)
    src_a = ItemNameModel.objects.create(name="ZZT MERGE BOARD - E1", sion_norm_class=e1)
    src_b = ItemNameModel.objects.create(name="ZZT MERGE BOARD - E5", sion_norm_class=e5)
    other = ItemNameModel.objects.create(name="ZZT OTHER")
    company = CompanyModel.objects.create(iec="IECMRG0001", name="Merge Co")
    port, _ = PortModel.objects.get_or_create(code="INMRG1", defaults={"name": "Port"})
    lic = LicenseDetailsModel.objects.create(license_number="LIC-MERGE-1", license_date=date.today(),
                                             license_expiry_date=date.today(), exporter=company, port=port)
    hs, _ = HSCodeModel.objects.get_or_create(hs_code="48101900")
    only_src = LicenseImportItemsModel.objects.create(license=lic, hs_code=hs, serial_number=1, description="Board A",
                                                      quantity=Decimal("10.000"), cif_fc=Decimal("100.00"))
    both = LicenseImportItemsModel.objects.create(license=lic, hs_code=hs, serial_number=2, description="Board B",
                                                  quantity=Decimal("5.000"), cif_fc=Decimal("55.55"))
    untouched = LicenseImportItemsModel.objects.create(license=lic, hs_code=hs, serial_number=3, description="HDPE",
                                                       quantity=Decimal("1.000"), cif_fc=Decimal("9.99"))
    only_src.items.add(src_a)
    both.items.add(src_b, canonical)
    untouched.items.add(other)
    export = LicenseExportItemModel.objects.create(license=lic, description="Board export", item=src_a,
                                                   cif_fc=Decimal("500.00"))
    mapping = ImportDescriptionMapping.objects.create(key_hash="k" * 64, description_key="board", description="Board")
    mapping.items.add(src_b)
    return dict(canonical=canonical, src_a=src_a, src_b=src_b, other=other, lic=lic, only_src=only_src, both=both,
                untouched=untouched, export=export, mapping=mapping, e1=e1, e5=e5)


def _approve(w, *, norm_union=(), confirmed=True, approved_moves=4):  # fixture refs on sources: 2 import-item links, 1 export item, 1 description mapping
    m = ItemNameMerge.objects.create(group_key="ING-T", canonical=w["canonical"], approved_by="owner",
                                     approval_reference="test", approved_on=date.today(), final_confirmation=confirmed,
                                     norm_union=list(norm_union), preview={"approved_references_moved": approved_moves})
    for s in (w["src_a"], w["src_b"]):
        ItemNameMergeSource.objects.create(merge=m, source=s, original_name=s.name)
    return m


def _state(w):
    return {
        "through": sorted(THROUGH.objects.values_list("licenseimportitemsmodel_id", "itemnamemodel_id")),
        "export_item": LicenseExportItemModel.objects.get(pk=w["export"].pk).item_id,
        "mapping": sorted(w["mapping"].items.values_list("pk", flat=True)),
        "active": dict(ItemNameModel.objects.values_list("pk", "is_active")),
        "canonical_norms": sorted(w["canonical"].norms.values_list("norm_class", flat=True)),
    }


def test_relations_are_discovered_including_hidden_ones():
    labels = {r.label for r in engine.discover_relations()}
    assert {"license.LicenseImportItemsModel.items", "license.ImportDescriptionMapping.items",
            "license.LicenseExportItemModel.item", "bill_of_entry.BillOfEntryModel.planning_target_item",
            "allotment.AllotmentModel.planning_target_item", "license.SourceNameMapping.target",
            "license.ProductAlias.item"} <= labels
    assert not any(label.startswith("core.ItemNameMerge") for label in labels)


def test_execute_requires_explicit_confirmation(world):
    m = _approve(world)
    with pytest.raises(engine.MergeError, match="Explicit confirmation"):
        engine.execute(m.pk, confirm=False, executed_by="t")
    assert ItemNameMerge.objects.get(pk=m.pk).status == ItemNameMerge.APPROVED


def test_execute_requires_final_confirmation_on_record(world):
    m = _approve(world, confirmed=False)
    before = _state(world)
    with pytest.raises(engine.MergeError, match="final confirmation"):
        engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)
    assert _state(world) == before


def test_command_refuses_without_confirm_flag(world):
    _approve(world)
    with pytest.raises(CommandError, match="--confirm"):
        call_command("item_name_merge", "execute", "ING-T")


def test_execute_repoints_dedups_deactivates_and_keeps_financials(world):
    w = world
    m = _approve(w)
    fin_before = engine.financial_snapshot([w["canonical"].pk, w["src_a"].pk, w["src_b"].pk])
    m = engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)

    assert m.status == ItemNameMerge.EXECUTED and m.verification["financial_difference"] == 0
    through = THROUGH.objects
    assert set(through.filter(licenseimportitemsmodel_id=w["only_src"].pk).values_list("itemnamemodel_id", flat=True)) == {w["canonical"].pk}
    assert set(through.filter(licenseimportitemsmodel_id=w["both"].pk).values_list("itemnamemodel_id", flat=True)) == {w["canonical"].pk}
    assert set(through.filter(licenseimportitemsmodel_id=w["untouched"].pk).values_list("itemnamemodel_id", flat=True)) == {w["other"].pk}
    assert LicenseExportItemModel.objects.get(pk=w["export"].pk).item_id == w["canonical"].pk
    assert list(w["mapping"].items.values_list("pk", flat=True)) == [w["canonical"].pk]
    # Sources preserved (never deleted), deactivated, resolvable to the canonical.
    for s in (w["src_a"], w["src_b"]):
        s.refresh_from_db()
        assert s.is_active is False
        assert ItemNameMergeSource.objects.get(source=s, is_current=True).merge.canonical_id == w["canonical"].pk
    # Quantities/CIF untouched, nothing double counted.
    assert engine.financial_snapshot([w["canonical"].pk, w["src_a"].pk, w["src_b"].pk]) == fin_before
    assert LicenseImportItemsModel.objects.get(pk=w["both"].pk).cif_fc == Decimal("55.55")
    ops = list(m.audit.values_list("operation", flat=True))
    assert ops.count("M2M_MOVE") == 2 and ops.count("M2M_DEDUP") == 1 and ops.count("REPOINT") == 1 and ops.count("DEACTIVATE") == 2


def test_executed_merge_cannot_run_twice_and_sources_cannot_be_merged_again(world):
    m = _approve(world)
    engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)
    with pytest.raises(engine.MergeError, match="only APPROVED"):
        engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)
    other = ItemNameMerge.objects.create(group_key="ING-T2", canonical=world["other"], approved_by="owner",
                                         approval_reference="t", approved_on=date.today(), final_confirmation=True,
                                         preview={"approved_references_moved": 0})
    ItemNameMergeSource.objects.create(merge=other, source=world["src_a"], original_name="x")
    with pytest.raises(engine.MergeError, match="already merged"):
        engine.execute(other.pk, confirm=True, executed_by="t", allow_reference_moves=True)


def test_unapproved_source_norm_blocks_merge(world):
    world["src_a"].norms.add(_norm("E132"))
    m = _approve(world)
    before = _state(world)
    with pytest.raises(engine.MergeError, match="not approved for union"):
        engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)
    assert _state(world) == before
    assert "E132" in ItemNameMerge.objects.get(pk=m.pk).error


def test_approved_norm_union_is_added_and_rolled_back(world):
    world["src_a"].norms.add(_norm("E132"))
    m = _approve(world, norm_union=["E132"])
    before = _state(world)
    engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)
    assert "E132" in world["canonical"].norms.values_list("norm_class", flat=True)
    engine.rollback(m.pk, confirm=True, reversed_by="t")
    assert _state(world) == before


def test_reference_count_changed_since_approval_requires_reconfirmation(world):
    m = _approve(world, approved_moves=0)  # owner approved a preview that moved 0 refs; there are more now
    before = _state(world)
    with pytest.raises(engine.MergeError, match="re-confirm"):
        engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)
    assert _state(world) == before


def test_financial_difference_aborts_and_marks_failed(world, monkeypatch):
    m = _approve(world)
    before = _state(world)
    real = engine.financial_snapshot
    calls = {"n": 0}

    def drifting(ids):
        calls["n"] += 1
        snap = real(ids)
        if calls["n"] == 2:
            snap["item_plans"] += 1
        return snap

    monkeypatch.setattr(engine, "financial_snapshot", drifting)
    with pytest.raises(engine.FinancialInvarianceError):
        engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)
    assert _state(world) == before  # whole transaction rolled back
    m.refresh_from_db()
    assert m.status == ItemNameMerge.FAILED and "financial difference" in m.error
    assert not ItemNameMergeAudit.objects.filter(merge=m).exists()


def test_rollback_restores_exact_previous_state(world):
    m = _approve(world)
    before = _state(world)
    engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)
    m = engine.rollback(m.pk, confirm=True, reversed_by="t")
    assert m.status == ItemNameMerge.REVERSED
    assert _state(world) == before
    assert not ItemNameMergeSource.objects.filter(merge=m, is_current=True).exists()
    assert m.audit.filter(phase="ROLLBACK").count() == m.audit.filter(phase="EXECUTE").count()


def test_rollback_refuses_when_record_changed_after_merge(world):
    m = _approve(world)
    engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)
    LicenseExportItemModel.objects.filter(pk=world["export"].pk).update(item=world["other"])  # later user change
    with pytest.raises(engine.MergeError, match="changed since the merge"):
        engine.rollback(m.pk, confirm=True, reversed_by="t")
    assert ItemNameMerge.objects.get(pk=m.pk).status == ItemNameMerge.EXECUTED
    assert LicenseExportItemModel.objects.get(pk=world["export"].pk).item_id == world["other"].pk


def test_register_only_takes_confirmed_merges(world, tmp_path):
    import json
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"decisions": [
        {"group": "ING-OK", "decision": "MERGE", "state": "APPROVED", "final_confirmation": True,
         "canonical": world["canonical"].pk, "sources": [world["src_a"].pk], "confirmed_on": "2026-11-21",
         "preview": {"references_moved": 2}},
        {"group": "ING-NOCONF", "decision": "MERGE", "state": "APPROVED", "final_confirmation": False,
         "canonical": world["canonical"].pk, "sources": [world["src_b"].pk], "confirmed_on": "2026-11-21"},
        {"group": "ING-KEEP", "decision": "KEEP SEPARATE", "state": "REJECTED"},
    ]}))
    before = _state(world)
    call_command("item_name_merge", "register", "--decisions", str(f), "--approved-by", "owner")
    assert list(ItemNameMerge.objects.values_list("group_key", flat=True)) == ["ING-OK"]
    assert _state(world) == before  # registering changes no item data


def test_reference_moving_merge_is_refused_by_default(world):
    m = _approve(world)
    before = _state(world)
    with pytest.raises(engine.MergeError, match="reference-moving merges are disabled"):
        engine.execute(m.pk, confirm=True, executed_by="t")
    assert _state(world) == before


def test_missing_approved_reference_count_is_refused(world):
    m = _approve(world, approved_moves=None)
    with pytest.raises(engine.MergeError, match="no reference count"):
        engine.execute(m.pk, confirm=True, executed_by="t", allow_reference_moves=True)


def test_zero_reference_merge_executes_without_override(world):
    lonely = ItemNameModel.objects.create(name="ZZT LONELY ALIAS")
    m = ItemNameMerge.objects.create(group_key="ING-Z", canonical=world["canonical"], approved_by="owner",
                                     approval_reference="t", approved_on=date.today(), final_confirmation=True,
                                     preview={"approved_references_moved": 0})
    ItemNameMergeSource.objects.create(merge=m, source=lonely, original_name=lonely.name)
    m = engine.execute(m.pk, confirm=True, executed_by="t")
    lonely.refresh_from_db()
    assert m.status == ItemNameMerge.EXECUTED and lonely.is_active is False and ItemNameModel.objects.filter(pk=lonely.pk).exists()
