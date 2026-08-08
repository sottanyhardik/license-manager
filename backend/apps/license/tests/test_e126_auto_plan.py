"""Tests for the E126 Auto-Plan service (services/e126_auto_plan.py).

`compute_e126_auto_plan` is the only DB-aware layer of the E126 planner — it
loads import items and delegates classification/waterfall/rebalance entirely
to the pure `services.e126_plan` engine (already unit-tested in
test_e126_plan.py). A split-eligible item with NO existing plan gets a fresh
40%/60% PKO/Olive-Oil split of its CURRENT `available_quantity` (never its
original/total import quantity). But once that split is generated, it
becomes a FIXED commitment: a SECOND run must NOT recalculate it — it must
re-emit the existing plan lines' CURRENT `remaining_quantity`/
`remaining_cif_fc` unchanged, even if `available_quantity` has since moved.
Mirrors test_e132_auto_plan.py's structure exactly (PKO/Olive-Oil replacing
PKO/Cheese; no explicit-override/RBD/Yeast/Aluminium equivalents exist for
E126).

DFIA NIL / DFIA Balance / residual-balance handling is explicitly OUT OF
SCOPE and not exercised here — see e126_plan.py's module docstring.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, PortModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.e126_auto_plan import compute_e126_auto_plan
from apps.license.services.e126_plan import NUT_NUTS, OLIVE_OIL, PKO, PLANNING_ORDER


def _hs(code):
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


def _create_license(license_number):
    company = CompanyModel.objects.create(iec=f"IEC{license_number[-7:]}", name="E126 Auto-Plan Test Exporter")
    port, _ = PortModel.objects.get_or_create(code="INAPT3", defaults={"name": "E126 Auto-Plan Test Port"})
    return LicenseDetailsModel.objects.create(
        license_number=license_number,
        license_date=date.today(),
        license_expiry_date=date.today(),
        exporter=company,
        port=port,
    )


def _patch_balances(balance_by_license_id: dict):
    return patch.object(
        LicenseDetailsModel, "get_balance_cif",
        property(lambda self: balance_by_license_id[self.id]),
    )


def _make_license(license_number, balance_cif):
    license_obj = _create_license(license_number)
    patcher = _patch_balances({license_obj.id: balance_cif})
    patcher.start()
    return license_obj, patcher


@pytest.fixture
def item_names(db):
    """Ensure the three E126 planning-item ItemNameModel rows exist so
    `compute_e126_auto_plan` can resolve `item_name` ids."""
    head_norm = HeadSIONNormsModel.objects.create(name="E126 Auto-Plan Test Norms")
    norm = SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E126")
    out = {}
    for name in PLANNING_ORDER:
        obj, _ = ItemNameModel.objects.get_or_create(name=name, defaults={"sion_norm_class": norm})
        out[name] = obj
    return out


SPLIT_DESC = "Relevant Oil viz Palm Kernel (1513) or Olive 1509 blend"


@pytest.mark.django_db
class TestComputeE126AutoPlanBasics:
    def test_no_import_items_plans_nothing(self, item_names):
        license_obj, patcher = _make_license("LIC-E126-AUTOPLAN-EMPTY", Decimal('5000'))
        try:
            lines, remaining_cif = compute_e126_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('5000')
        finally:
            patcher.stop()

    def test_item_below_min_plan_qty_is_not_planned(self, item_names):
        license_obj, patcher = _make_license("LIC-E126-AUTOPLAN-TINY", Decimal('10000'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Cashew Nuts",
                hs_code=_hs('08021100'),
                quantity=Decimal('49'), available_quantity=Decimal('49'),
            )
            lines, remaining_cif = compute_e126_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('10000')
        finally:
            patcher.stop()

    def test_plain_categories_plan_at_fixed_price(self, item_names):
        license_obj, patcher = _make_license("LIC-E126-AUTOPLAN-PLAIN", Decimal('100000'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Cashew Nuts",
                hs_code=_hs('08021100'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Pure Palm Kernel Oil",
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=3, description="Extra Virgin Olive Oil",
                hs_code=_hs('1509'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, remaining_cif = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[NUT_NUTS].id]['planned_cif_fc'] == 300.0    # 100 × 3.00
            assert by_name_id[item_names[PKO].id]['planned_cif_fc'] == 180.0         # 100 × 1.80
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_cif_fc'] == 500.0   # 100 × 5.00
            assert remaining_cif == pytest.approx(100000 - 300 - 180 - 500)
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestPkoOliveSplitAvailableQuantity:
    """CRITICAL business rule: the PKO/Olive-Oil split is always 50%/50% of
    the import item's CURRENT `available_quantity` — never its
    original/total import quantity. This is the INITIAL allocation, before
    any Balance CIF optimization is performed."""

    def test_fresh_split_targets_50_50_of_available_quantity(self, item_names):
        # balance_cif == exactly the default 50/50 split's value (340) so the
        # wastage-rebalance pass has nothing to do here.
        license_obj, patcher = _make_license("LIC-E126-SPLIT-FRESH", Decimal('340'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 50.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 50.0
        finally:
            patcher.stop()

    def test_split_follows_available_quantity_down_after_real_consumption(self, item_names):
        # 100kg originally imported, 40kg already really allotted/debited
        # elsewhere -> available_quantity is now 60kg. The split must be
        # 50%/50% of THAT 60kg (30/30) — never of the original 100.
        license_obj, patcher = _make_license("LIC-E126-SPLIT-AFTER-DEBIT", Decimal('204'))  # 30×1.80 + 30×5.00
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('60'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 30.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 30.0
        finally:
            patcher.stop()

    def test_reruns_with_no_existing_split_and_unchanged_available_quantity_are_stable(self, item_names):
        license_obj, patcher = _make_license("LIC-E126-SPLIT-RERUN", Decimal('340'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 50.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 50.0
        finally:
            patcher.stop()

    def test_same_hsn_and_description_items_are_pooled_into_one_group(self, item_names):
        # Two import items sharing the SAME hs_code + description are the
        # SAME `plan_group_key` (plan_grouping.py) — the canonical grouping
        # every other planning-aware part of the app (display, real
        # allotment-cap enforcement) already uses. Auto-Plan pools them into
        # ONE group-level 50/50 split of their SUMMED available quantity
        # (100+200=300), anchored on the representative (lowest
        # serial_number) — never two independent per-item splits.
        license_obj, patcher = _make_license("LIC-E126-SPLIT-POOLED", Decimal('1020'))  # 150×1.80 + 150×5.00
        try:
            item1 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            item2 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('200'), available_quantity=Decimal('200'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)

            pko_lines = [l for l in lines if l['item_name'] == item_names[PKO].id]
            olive_lines = [l for l in lines if l['item_name'] == item_names[OLIVE_OIL].id]

            # Exactly ONE PKO row and ONE Olive Oil row for the whole
            # group — never one per member.
            assert len(pko_lines) == 1
            assert len(olive_lines) == 1
            assert pko_lines[0]['planned_quantity'] == 150.0
            assert olive_lines[0]['planned_quantity'] == 150.0

            # Anchored on the representative (lowest serial_number = item1).
            assert pko_lines[0]['import_item'] == item1.id
            assert olive_lines[0]['import_item'] == item1.id
            assert all(l['import_item'] != item2.id for l in lines)
        finally:
            patcher.stop()

    def test_different_description_items_are_never_pooled(self, item_names):
        # Same HSN, DIFFERENT description -> different plan_group_key ->
        # two independent groups, each with its own 50/50 split.
        license_obj, patcher = _make_license("LIC-E126-SPLIT-DIFF-DESC", Decimal('1020'))
        try:
            item1 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            item2 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description=SPLIT_DESC + " VARIANT B",
                hs_code=_hs('15132900'),
                quantity=Decimal('200'), available_quantity=Decimal('200'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)

            pko_lines = [l for l in lines if l['item_name'] == item_names[PKO].id]
            olive_lines = [l for l in lines if l['item_name'] == item_names[OLIVE_OIL].id]

            assert len(pko_lines) == 2
            assert len(olive_lines) == 2
            assert {l['import_item'] for l in pko_lines} == {item1.id, item2.id}
        finally:
            patcher.stop()

    def test_different_hsn_items_are_never_pooled(self, item_names):
        # DIFFERENT HSN, same description -> different plan_group_key ->
        # two independent groups, each with its own 50/50 split.
        license_obj, patcher = _make_license("LIC-E126-SPLIT-DIFF-HSN", Decimal('1020'))
        try:
            item1 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            item2 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description=SPLIT_DESC,
                hs_code=_hs('99999999'),
                quantity=Decimal('200'), available_quantity=Decimal('200'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)

            pko_lines = [l for l in lines if l['item_name'] == item_names[PKO].id]
            olive_lines = [l for l in lines if l['item_name'] == item_names[OLIVE_OIL].id]

            assert len(pko_lines) == 2
            assert len(olive_lines) == 2
            assert {l['import_item'] for l in pko_lines} == {item1.id, item2.id}
        finally:
            patcher.stop()

    def test_representative_is_lowest_serial_number(self, item_names):
        # The group's plan is always anchored on the LOWEST serial_number
        # member, regardless of insertion order or which member has the
        # larger quantity.
        license_obj, patcher = _make_license("LIC-E126-REPRESENTATIVE", Decimal('1020'))
        try:
            # Insert the HIGHER serial number first, to confirm ordering by
            # serial_number (not creation order / DB id) decides it.
            item_serial_5 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=5, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('200'), available_quantity=Decimal('200'),
            )
            item_serial_2 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            assert lines
            assert all(l['import_item'] == item_serial_2.id for l in lines)
            assert all(l['import_item'] != item_serial_5.id for l in lines)
        finally:
            patcher.stop()

    def test_scattered_legacy_balances_across_group_members_are_consolidated(self, item_names):
        # Regression test for a reported production bug: a DGFT
        # re-serialization split one large item into several new sibling
        # rows sharing the same HSN+description. The ORIGINAL item still
        # carries a stale PKO/Olive-Oil split generated before the split
        # (now sitting on a smaller, shrunk `available_quantity`); the new
        # siblings have no plan of their own yet. A fresh Auto-Plan run
        # must consolidate the existing split onto the group's
        # representative — NOT also generate a second, independent fresh
        # split for the group's summed availability (the exact mechanism
        # that doubled the reported bug's total).
        license_obj, patcher = _make_license("LIC-E126-SCATTERED-LEGACY", Decimal('100000'))
        try:
            original_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('10'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=original_item, item_name=item_names[PKO],
                planned_quantity=Decimal('40'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('72'),
                remaining_quantity=Decimal('40'), remaining_cif_fc=Decimal('72'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=original_item, item_name=item_names[OLIVE_OIL],
                planned_quantity=Decimal('60'), unit_price=Decimal('5.00'), planned_cif_fc=Decimal('300'),
                remaining_quantity=Decimal('60'), remaining_cif_fc=Decimal('300'),
            )
            # New sibling rows created by the resync — same HSN+description,
            # no plan of their own.
            sibling1 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('50'), available_quantity=Decimal('50'),
            )
            sibling2 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=3, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('60'), available_quantity=Decimal('60'),
            )

            lines, _ = compute_e126_auto_plan(license_obj)

            pko_lines = [l for l in lines if l['item_name'] == item_names[PKO].id]
            olive_lines = [l for l in lines if l['item_name'] == item_names[OLIVE_OIL].id]

            # Exactly one PKO row and one Olive Oil row for the WHOLE
            # group — the preserved balance, never doubled by an
            # additional fresh split of the group's summed availability.
            assert len(pko_lines) == 1
            assert len(olive_lines) == 1
            assert pko_lines[0]['planned_quantity'] == 40.0
            assert olive_lines[0]['planned_quantity'] == 60.0

            # Anchored on the group's representative (lowest serial_number).
            assert pko_lines[0]['import_item'] == original_item.id
            assert olive_lines[0]['import_item'] == original_item.id
            assert all(l['import_item'] not in (sibling1.id, sibling2.id) for l in lines)
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestPkoOliveWastageRebalanceAutoPlan:
    """End-to-end (DB-level) coverage for the wastage-reduction rebalance:
    when the licence's live Balance CIF exceeds the default 50/50 split's
    value, `compute_e126_auto_plan` shifts quantity from PKO to Olive Oil to
    close the gap. The pure-function math is exercised exhaustively in
    test_e126_plan.py::TestPkoOliveWastageRebalance — this only confirms the
    DB-aware adapter wires it through correctly."""

    def test_leftover_balance_shifts_pko_into_olive_oil(self, item_names):
        # Default split value = 340 (50×1.80 + 50×5.00). Give a much larger
        # balance so the leftover gets absorbed by converting PKO to Olive Oil.
        license_obj, patcher = _make_license("LIC-E126-REBALANCE-BASIC", Decimal('100000'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, remaining_cif = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            # PKO fully converted (max possible gain 50×3.20=160 can't come
            # close to using up a 100000 balance) — no PKO line at all.
            assert item_names[PKO].id not in by_name_id
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 100.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_cif_fc'] == 500.0  # 100 × 5.00
        finally:
            patcher.stop()

    def test_reruns_with_unchanged_available_quantity_are_stable(self, item_names):
        license_obj, patcher = _make_license("LIC-E126-REBALANCE-STABLE", Decimal('100000'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            run1, remaining1 = compute_e126_auto_plan(license_obj)
            run2, remaining2 = compute_e126_auto_plan(license_obj)
            key = lambda l: (l['import_item'], l['item_name'], l['planned_quantity'])
            assert sorted(run1, key=key) == sorted(run2, key=key)
            assert remaining1 == remaining2
        finally:
            patcher.stop()

    def test_partial_rebalance_leaves_other_categories_untouched(self, item_names):
        # A licence with Nuts + a split item, balance just large enough to
        # fully fund Nuts plus a partial PKO->Olive-Oil shift. Nuts' allocation
        # must be exactly its own fixed-price value either way. (Nuts
        # quantity must be >= MIN_PLAN_QTY=50 or it's silently excluded.)
        balance = Decimal('300') + Decimal('390')  # Nuts (100×3.00) + split default(340) + 50 surplus
        license_obj, patcher = _make_license("LIC-E126-REBALANCE-PARTIAL", balance)
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Cashew Nuts",
                hs_code=_hs('08021100'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, remaining_cif = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            assert by_name_id[item_names[NUT_NUTS].id]['planned_cif_fc'] == 300.0
            assert by_name_id[item_names[PKO].id]['planned_quantity'] < 50.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] > 50.0
            # The rebalanced split's exact quantities (34.375 / 65.625) are
            # fractional, so each side is floored to a whole unit before
            # being saved (34 / 65). planned_cif_fc must always equal
            # planned_quantity * unit_price, so the value of the fractional
            # remainder (0.375 units on each side) is genuinely unspent —
            # it is NOT recorded against any planned_quantity anywhere, and
            # must show up here as leftover, not be silently absorbed.
            pko_line = by_name_id[item_names[PKO].id]
            olive_line = by_name_id[item_names[OLIVE_OIL].id]
            assert pko_line['planned_cif_fc'] == pytest.approx(
                pko_line['planned_quantity'] * pko_line['unit_price'], abs=0.01
            )
            assert olive_line['planned_cif_fc'] == pytest.approx(
                olive_line['planned_quantity'] * olive_line['unit_price'], abs=0.01
            )
            assert remaining_cif == pytest.approx(3.8, abs=0.01)
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestPkoOliveSplitPreservedOnceGenerated:
    """CRITICAL business rule: once Auto-Plan generates the PKO/Olive-Oil
    split, it becomes a FIXED commitment. A second Auto-Plan run must never
    regenerate or recalculate it — it must re-emit the existing plan lines'
    CURRENT remaining_quantity/remaining_cif_fc unchanged, even if
    available_quantity has since moved (up or down)."""

    def test_no_existing_plan_gets_fresh_split_with_remaining_equal_to_planned(self, item_names):
        from apps.license.services.plan_enforcement import save_plan_lines_for_license

        license_obj, patcher = _make_license("LIC-E126-PRESERVE-FRESH", Decimal('340'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 50.0
            assert 'remaining_quantity' not in by_name_id[item_names[PKO].id]
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 50.0

            saved = save_plan_lines_for_license(license_obj, lines)
            saved_by_name_id = {p.item_name_id: p for p in saved}
            assert saved_by_name_id[item_names[PKO].id].remaining_quantity == Decimal('50')
            assert saved_by_name_id[item_names[PKO].id].remaining_cif_fc == Decimal('90')
            assert saved_by_name_id[item_names[OLIVE_OIL].id].remaining_quantity == Decimal('50')
            assert saved_by_name_id[item_names[OLIVE_OIL].id].remaining_cif_fc == Decimal('250')
        finally:
            patcher.stop()

    def test_existing_partially_consumed_plan_is_preserved_not_recalculated(self, item_names):
        # PKO already partially consumed via a plan-line-aware allocation
        # (remaining=20 of its original 50) — a second Auto-Plan run must
        # re-emit exactly 20, never regenerate a fresh 50.
        license_obj, patcher = _make_license("LIC-E126-PRESERVE-PARTIAL", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('50'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('90'),
                remaining_quantity=Decimal('20'), remaining_cif_fc=Decimal('36'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[OLIVE_OIL],
                planned_quantity=Decimal('50'), unit_price=Decimal('5.00'), planned_cif_fc=Decimal('250'),
                remaining_quantity=Decimal('50'), remaining_cif_fc=Decimal('250'),
            )

            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            # Preserved exactly — NOT the fresh 50/50 the engine would
            # otherwise compute from available_quantity=100, and NOT a
            # rebalanced value either (a huge 100000 balance would normally
            # trigger wastage-rebalancing on a FRESH split).
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 20.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 50.0
        finally:
            patcher.stop()

    def test_preserved_even_after_available_quantity_shrinks(self, item_names):
        # Some of the import item's quantity was consumed by something
        # UNRELATED to this split (available_quantity dropped 100 -> 70),
        # but the existing PKO/Olive-Oil plan must still be preserved
        # exactly — never recalculated as 50%/50% of the new, smaller
        # available_quantity.
        license_obj, patcher = _make_license("LIC-E126-PRESERVE-AFTER-SHRINK", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('70'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('50'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('90'),
                remaining_quantity=Decimal('50'), remaining_cif_fc=Decimal('90'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[OLIVE_OIL],
                planned_quantity=Decimal('50'), unit_price=Decimal('5.00'), planned_cif_fc=Decimal('250'),
                remaining_quantity=Decimal('50'), remaining_cif_fc=Decimal('250'),
            )

            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            # NOT 35/35 (50%/50% of the new 70) -- the original 50/50 stands.
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 50.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 50.0
        finally:
            patcher.stop()

    def test_fully_consumed_plan_line_still_reported_at_zero(self, item_names):
        # PKO fully drained (remaining=0) must still be re-emitted (at 0),
        # not silently dropped — see e126_auto_plan.py's preservation branch.
        license_obj, patcher = _make_license("LIC-E126-PRESERVE-ZERO", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('50'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('90'),
                remaining_quantity=Decimal('0'), remaining_cif_fc=Decimal('0'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[OLIVE_OIL],
                planned_quantity=Decimal('50'), unit_price=Decimal('5.00'), planned_cif_fc=Decimal('250'),
                remaining_quantity=Decimal('50'), remaining_cif_fc=Decimal('250'),
            )

            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 0.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 50.0
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestCorruptedPreservedPlanIsRejected:
    """Regression coverage for a reported production bug: a stale/legacy
    `LicenseItemPlan` row (not created by this engine — e.g. left behind by
    a DGFT re-serialization, or a hand-edited `bulk_upsert` row) carrying a
    unit price ABOVE the fixed ceiling must never be blindly re-emitted by
    the "preserve once generated" rule. `compute_e126_auto_plan` rejects the
    WHOLE item's plan (never a partial save) and logs a warning instead."""

    def test_preserved_price_above_fixed_ceiling_rejects_whole_item(self, item_names):
        # PKO's stored price ($4.84) is above its $1.80 ceiling — exactly the
        # reported bug's numbers. The item's plan (both PKO and its sibling
        # Olive Oil line) must be dropped entirely, not re-emitted.
        license_obj, patcher = _make_license("LIC-E126-CORRUPT-PRICE", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('50'), unit_price=Decimal('4.84'), planned_cif_fc=Decimal('242'),
                remaining_quantity=Decimal('50'), remaining_cif_fc=Decimal('242'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[OLIVE_OIL],
                planned_quantity=Decimal('50'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('90'),
                remaining_quantity=Decimal('50'), remaining_cif_fc=Decimal('90'),
            )

            lines, _ = compute_e126_auto_plan(license_obj)
            item_lines = [l for l in lines if l['import_item'] == import_item.id]

            assert item_lines == []
        finally:
            patcher.stop()

    def test_preserved_price_within_ceiling_is_unaffected(self, item_names):
        # A legitimately capped/reduced price (still <= the fixed ceiling)
        # must NOT be rejected — only prices ABOVE the ceiling are invalid.
        license_obj, patcher = _make_license("LIC-E126-VALID-CAPPED-PRICE", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('50'), unit_price=Decimal('1.00'), planned_cif_fc=Decimal('50'),
                remaining_quantity=Decimal('50'), remaining_cif_fc=Decimal('50'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[OLIVE_OIL],
                planned_quantity=Decimal('50'), unit_price=Decimal('3.00'), planned_cif_fc=Decimal('150'),
                remaining_quantity=Decimal('50'), remaining_cif_fc=Decimal('150'),
            )

            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 50.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 50.0
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestFractionalQuantityCifInvariant:
    """Regression coverage: every FRESH (non-preserved)
    LicenseItemPlan line's `planned_cif_fc` must equal
    `planned_quantity * unit_price` using the FLOORED planned_quantity —
    never the engine's original, un-floored quantity — whenever a group's
    classified/split quantity is fractional. Covers the split-eligible
    PKO/Olive-Oil path AND the plain (non-split) fixed-price path, since
    both flow through the exact same fresh-generation branch in
    `compute_e126_auto_plan`."""

    def test_exact_finding_reproduction_101_units(self, item_names):
        # Verbatim reproduction of the reported defect: available_quantity
        # =101 -> 50.5/50.5 split. balance_cif is set to exactly the
        # UN-floored 50.5/50.5 split's value (343.40) so the separate
        # wastage-rebalance pass has nothing to shift and this test isolates
        # only the floor/cif-recompute defect.
        license_obj, patcher = _make_license("LIC-E126-FRACTIONAL-101", Decimal('343.40'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('101'), available_quantity=Decimal('101'),
            )
            lines, remaining_cif = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            pko_line = by_name_id[item_names[PKO].id]
            olive_line = by_name_id[item_names[OLIVE_OIL].id]

            # The 101st (fractional) unit must never appear in any recorded
            # planned_quantity anywhere...
            assert pko_line['planned_quantity'] == 50.0
            assert olive_line['planned_quantity'] == 50.0
            # ...and its value must therefore NOT be billed against
            # planned_cif_fc either — this is the exact defect: the old code
            # saved cif=90.90/252.50 (from the un-floored 50.5 qty) here.
            assert pko_line['planned_cif_fc'] == pytest.approx(90.00, abs=0.001)
            assert olive_line['planned_cif_fc'] == pytest.approx(250.00, abs=0.001)
            assert pko_line['planned_cif_fc'] == pytest.approx(
                pko_line['planned_quantity'] * pko_line['unit_price'], abs=0.001
            )
            assert olive_line['planned_cif_fc'] == pytest.approx(
                olive_line['planned_quantity'] * olive_line['unit_price'], abs=0.001
            )
            # The unused 101st unit's value (3.40) now genuinely shows up as
            # leftover instead of being silently absorbed as "100% planned".
            assert remaining_cif == pytest.approx(3.40, abs=0.01)
        finally:
            patcher.stop()

    def test_plain_fixed_price_category_with_fractional_available_quantity(self, item_names):
        # Same root-cause code path also applies to a PLAIN (non-split)
        # category — Nuts here — whenever the group's available_quantity
        # itself is fractional (this occurs for real in production data;
        # see the finding's db_context.py evidence of 22/2401 import items
        # with fractional available_quantity).
        license_obj, patcher = _make_license("LIC-E126-PLAIN-FRACTIONAL", Decimal('100000'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Cashew Nuts",
                hs_code=_hs('08021100'),
                quantity=Decimal('100.7'), available_quantity=Decimal('100.7'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            nuts_line = by_name_id[item_names[NUT_NUTS].id]

            assert nuts_line['planned_quantity'] == 100.0
            # Old (buggy) behavior would have saved 100.7 * 3.00 = 302.10.
            assert nuts_line['planned_cif_fc'] == pytest.approx(300.00, abs=0.001)
            assert nuts_line['planned_cif_fc'] == pytest.approx(
                nuts_line['planned_quantity'] * nuts_line['unit_price'], abs=0.001
            )
        finally:
            patcher.stop()

    @pytest.mark.parametrize("avail", ["100.1", "100.9", "142.3"])
    def test_invariant_holds_across_a_range_of_fractional_available_quantities(self, item_names, avail):
        # Boundary sweep: the qty*price=value invariant must hold for every
        # fractional available_quantity, not just the finding's single
        # reproduction value. balance_cif is pinned to the exact (un-floored)
        # default 50/50 split value for each avail so the wastage-rebalance
        # pass never engages and this isolates the floor/cif defect only.
        avail_dec = Decimal(avail)
        balance_cif = avail_dec * Decimal('3.4')  # 0.5*1.80 + 0.5*5.00 = 3.4/unit
        license_obj, patcher = _make_license(f"LIC-E126-FRACTIONAL-SWEEP-{avail}", balance_cif)
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=avail_dec, available_quantity=avail_dec,
            )
            lines, remaining_cif = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            pko_line = by_name_id[item_names[PKO].id]
            olive_line = by_name_id[item_names[OLIVE_OIL].id]

            assert pko_line['planned_cif_fc'] == pytest.approx(
                pko_line['planned_quantity'] * pko_line['unit_price'], abs=0.001
            )
            assert olive_line['planned_cif_fc'] == pytest.approx(
                olive_line['planned_quantity'] * olive_line['unit_price'], abs=0.001
            )
            assert remaining_cif >= -0.001  # never a negative "leftover"
        finally:
            patcher.stop()

    def test_fix_applies_identically_across_different_companies(self, item_names):
        # The defect and its fix are purely a function of available_quantity
        # / unit_price — company/exporter identity must never matter. Runs
        # two INDEPENDENT licenses (each `_create_license` call creates its
        # own CompanyModel) with different fractional available_quantity and
        # confirms both are corrected independently with no cross-talk.
        # A single patcher covering BOTH license ids — `get_balance_cif` is
        # patched at the CLASS level, so two independent `_make_license`
        # calls would stack and each would clobber the other's dict the
        # moment a signal (e.g. on import-item save) re-reads the property
        # for the "wrong" license.
        license_a = _create_license("LIC-E126-FRACTIONAL-COMPANY-A")
        license_b = _create_license("LIC-E126-FRACTIONAL-COMPANY-B")
        patcher = _patch_balances({license_a.id: Decimal('343.40'), license_b.id: Decimal('207.4')})
        patcher.start()
        try:
            assert license_a.exporter_id != license_b.exporter_id

            LicenseImportItemsModel.objects.create(
                license=license_a, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('101'), available_quantity=Decimal('101'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_b, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('61'), available_quantity=Decimal('61'),
            )

            lines_a, remaining_a = compute_e126_auto_plan(license_a)
            lines_b, remaining_b = compute_e126_auto_plan(license_b)

            by_a = {l['item_name']: l for l in lines_a}
            by_b = {l['item_name']: l for l in lines_b}

            # License A: 101 units -> 50/50, cif 90.00/250.00, remaining 3.40
            assert by_a[item_names[PKO].id]['planned_cif_fc'] == pytest.approx(90.00, abs=0.001)
            assert by_a[item_names[OLIVE_OIL].id]['planned_cif_fc'] == pytest.approx(250.00, abs=0.001)
            assert remaining_a == pytest.approx(3.40, abs=0.01)

            # License B: 61 units -> 30.5/30.5 -> floors to 30/30, cif
            # 54.00/150.00, remaining 3.40 (independent of License A).
            assert by_b[item_names[PKO].id]['planned_quantity'] == 30.0
            assert by_b[item_names[OLIVE_OIL].id]['planned_quantity'] == 30.0
            assert by_b[item_names[PKO].id]['planned_cif_fc'] == pytest.approx(54.00, abs=0.001)
            assert by_b[item_names[OLIVE_OIL].id]['planned_cif_fc'] == pytest.approx(150.00, abs=0.001)
            assert remaining_b == pytest.approx(3.40, abs=0.01)
        finally:
            patcher.stop()

    def test_preserved_branch_is_deliberately_untouched_by_this_fix(self, item_names):
        # Characterization test (NOT a defect assertion): the fix explicitly
        # only touches the FRESH (non-preserved) branch. A preserved plan
        # line's `remaining_cif_fc` is re-emitted VERBATIM from the stored
        # row (never recomputed from the floored `remaining_quantity`), per
        # the "never regenerate or recalculate a preserved split" business
        # rule. This pins that documented, intentional scope boundary so a
        # future change doesn't silently start "fixing" the preserved branch
        # too without an explicit decision to do so.
        license_obj, patcher = _make_license("LIC-E126-PRESERVED-UNTOUCHED-FRACTIONAL", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            # A pre-existing (already committed) preserved row whose stored
            # remaining_cif_fc does NOT equal floor(remaining_quantity) *
            # unit_price (62.10 != 34 * 1.80 = 61.20) — e.g. left over from
            # before this fix existed, or from a legitimate partial-debit
            # history. The preserved branch must re-emit it unchanged.
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('50'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('90'),
                remaining_quantity=Decimal('34.5'), remaining_cif_fc=Decimal('62.10'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[OLIVE_OIL],
                planned_quantity=Decimal('50'), unit_price=Decimal('5.00'), planned_cif_fc=Decimal('250'),
                remaining_quantity=Decimal('50'), remaining_cif_fc=Decimal('250'),
            )

            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            pko_line = by_name_id[item_names[PKO].id]

            # Quantity is floored for display (existing, unrelated behavior)...
            assert pko_line['planned_quantity'] == 34.0
            # ...but cif is preserved VERBATIM — NOT recomputed as 34*1.80.
            assert pko_line['planned_cif_fc'] == pytest.approx(62.10, abs=0.001)
        finally:
            patcher.stop()
