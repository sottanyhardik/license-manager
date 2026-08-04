"""Tests for the E132 Auto-Plan service (services/e132_auto_plan.py).

`compute_e132_auto_plan` is the only DB-aware layer of the E132 planner — it
loads import items and delegates classification/waterfall/rebalance entirely
to the pure `services.e132_plan` engine (already unit-tested in
test_e132_plan.py). A Vegetable Oil item with NO existing plan gets a fresh
40%/60% PKO/Cheese split of its CURRENT `available_quantity` (never its
original/total import quantity). But once that split is generated, it
becomes a FIXED commitment: a SECOND run must NOT recalculate it — it must
re-emit the existing plan lines' CURRENT `remaining_quantity`/
`remaining_cif_fc` unchanged, even if `available_quantity` has since moved.
(Real debits attributed to a specific plan line — via `plan_line_id` in
`allocate_items` — are covered in
apps/allotment/tests/test_allocate_items_plan_line_balance.py.)

These tests focus on what only this adapter can be responsible for: DB
mapping (ItemNameModel ids), the MIN_PLAN_QTY gate, confirming a FRESH split
tracks `available_quantity`, and confirming an EXISTING split is preserved
rather than regenerated.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, PortModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.e132_auto_plan import compute_e132_auto_plan
from apps.license.services.e132_plan import ALUMINIUM, CHEESE, NUT_NUTS, PKO, PLANNING_ORDER, RBD, YEAST


def _hs(code):
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


def _create_license(license_number):
    company = CompanyModel.objects.create(iec=f"IEC{license_number[-7:]}", name="E132 Auto-Plan Test Exporter")
    port, _ = PortModel.objects.get_or_create(code="INAPT2", defaults={"name": "E132 Auto-Plan Test Port"})
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
    """Ensure the six E132 planning-item ItemNameModel rows exist so
    `compute_e132_auto_plan` can resolve `item_name` ids — mirrors what
    `seed_e132_plan_items` does in production. Uses get_or_create because
    these rows are already seeded into the test DB by data migrations
    (0007-0010_seed_e132_*)."""
    head_norm = HeadSIONNormsModel.objects.create(name="E132 Auto-Plan Test Norms")
    norm = SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E132")
    out = {}
    for name in PLANNING_ORDER:
        obj, _ = ItemNameModel.objects.get_or_create(name=name, defaults={"sion_norm_class": norm})
        out[name] = obj
    return out


VEG_OIL_DESC = "Relevant Vegetable Oil viz Palm Kernel (1513) or Dairy Fat 0406 Vegetable Oil"


@pytest.mark.django_db
class TestComputeE132AutoPlanBasics:
    def test_no_import_items_plans_nothing(self, item_names):
        license_obj, patcher = _make_license("LIC-E132-AUTOPLAN-EMPTY", Decimal('5000'))
        try:
            lines, remaining_cif = compute_e132_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('5000')
        finally:
            patcher.stop()

    def test_item_below_min_plan_qty_is_not_planned(self, item_names):
        license_obj, patcher = _make_license("LIC-E132-AUTOPLAN-TINY", Decimal('10000'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Cashew Nuts",
                hs_code=_hs('08021100'),
                quantity=Decimal('49'), available_quantity=Decimal('49'),
            )
            lines, remaining_cif = compute_e132_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('10000')
        finally:
            patcher.stop()

    def test_plain_categories_plan_at_fixed_price(self, item_names):
        license_obj, patcher = _make_license("LIC-E132-AUTOPLAN-PLAIN", Decimal('100000'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Cashew Nuts",
                hs_code=_hs('08021100'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Bakers Yeast",
                hs_code=_hs('2106'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=3, description="RBD Oil",
                hs_code=_hs('1510'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=4, description="Aluminium Foil",
                hs_code=_hs('7607'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, remaining_cif = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[NUT_NUTS].id]['planned_cif_fc'] == 300.0   # 100 × 3.00
            assert by_name_id[item_names[YEAST].id]['planned_cif_fc'] == 500.0      # 100 × 5.00
            assert by_name_id[item_names[RBD].id]['planned_cif_fc'] == 120.0        # 100 × 1.20
            assert by_name_id[item_names[ALUMINIUM].id]['planned_cif_fc'] == 450.0  # 100 × 4.50
            assert remaining_cif == pytest.approx(100000 - 300 - 500 - 120 - 450)
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestVegOilSplitAvailableQuantity:
    """CRITICAL business rule: the Vegetable Oil PKO/Cheese split is always
    40%/60% of the import item's CURRENT `available_quantity` — never its
    original/total import quantity. Because `available_quantity` already
    self-corrects the moment a REAL allotment debits it, re-running
    Auto-Plan simply recomputes 40%/60% of whatever it currently is — no
    separate "already planned" bookkeeping is needed for this to be stable
    and idempotent."""

    def test_fresh_split_targets_40_60_of_available_quantity(self, item_names):
        # balance_cif == exactly the default 40/60 split's value (402) so the
        # wastage-rebalance pass (see TestVegOilWastageRebalanceAutoPlan)
        # has nothing to do here — this test is about the raw split only.
        license_obj, patcher = _make_license("LIC-E132-SPLIT-FRESH", Decimal('402'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, _ = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 40.0
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_split_follows_available_quantity_down_after_real_consumption(self, item_names):
        # 100kg originally imported, 40kg already really allotted/debited
        # elsewhere -> available_quantity is now 60kg. The split must be
        # 40%/60% of THAT 60kg (24/36) — never of the original 100.
        license_obj, patcher = _make_license("LIC-E132-SPLIT-AFTER-DEBIT", Decimal('241.2'))  # 24×1.80 + 36×5.50
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('60'),
            )
            lines, _ = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 24.0
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] == 36.0
        finally:
            patcher.stop()

    def test_reruns_with_no_existing_split_and_unchanged_available_quantity_are_stable(self, item_names):
        # No PKO/Cheese plan exists yet for this item, so both runs get the
        # engine's fresh 40/60 computation — identical, since nothing
        # (available_quantity, balance) changed between them. (Once a split
        # DOES exist, see TestVegOilSplitPreservedOnceGenerated — a rerun
        # must preserve it, not recompute it, even from unchanged inputs.)
        license_obj, patcher = _make_license("LIC-E132-SPLIT-RERUN", Decimal('402'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )

            lines, _ = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 40.0
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_explicit_cheese_ignores_unrelated_history(self, item_names):
        # An explicit Cheese+Vegetable+Oil item must always plan 100% of its
        # own available quantity to Cheese, regardless of an unrelated,
        # already-generated (and partially consumed) PKO/Cheese split
        # sitting on a DIFFERENT import item — which must simply be
        # preserved as-is, not regenerated or allowed to interfere.
        license_obj, patcher = _make_license("LIC-E132-EXPLICIT-CHEESE", Decimal('100000'))
        try:
            veg_oil_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=veg_oil_item, item_name=item_names[PKO],
                planned_quantity=Decimal('40'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('72'),
                remaining_quantity=Decimal('30'), remaining_cif_fc=Decimal('54'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=veg_oil_item, item_name=item_names[CHEESE],
                planned_quantity=Decimal('60'), unit_price=Decimal('5.50'), planned_cif_fc=Decimal('330'),
                remaining_quantity=Decimal('60'), remaining_cif_fc=Decimal('330'),
            )
            explicit_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2,
                description="Cheese Vegetable Oil Blend (1513)",
                hs_code=_hs('15132901'),
                quantity=Decimal('50'), available_quantity=Decimal('50'),
            )

            lines, _ = compute_e132_auto_plan(license_obj)
            explicit_lines = [l for l in lines if l['import_item'] == explicit_item.id]

            assert len(explicit_lines) == 1
            assert explicit_lines[0]['item_name'] == item_names[CHEESE].id
            assert explicit_lines[0]['planned_quantity'] == 50.0

            # The unrelated Vegetable Oil item's preserved (partially
            # consumed) split is unaffected — PKO stays at its preserved 30
            # remaining, never regenerated back to a fresh 40.
            veg_oil_lines = {l['item_name']: l for l in lines if l['import_item'] == veg_oil_item.id}
            assert veg_oil_lines[item_names[PKO].id]['planned_quantity'] == 30.0
            assert veg_oil_lines[item_names[CHEESE].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_split_scoped_per_import_item_not_licence_wide(self, item_names):
        # Two separate 100kg Vegetable Oil items on the same licence each get
        # their OWN independent 40/60 target — not a pooled licence-wide split.
        # balance_cif == exactly both items' default-split value combined
        # (402 + 804 = 1206) so the wastage-rebalance pass has nothing left
        # over to touch here.
        license_obj, patcher = _make_license("LIC-E132-SPLIT-PER-ITEM", Decimal('1206'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('200'), available_quantity=Decimal('200'),
            )
            lines, _ = compute_e132_auto_plan(license_obj)
            pko_total = sum(l['planned_quantity'] for l in lines if l['item_name'] == item_names[PKO].id)
            cheese_total = sum(l['planned_quantity'] for l in lines if l['item_name'] == item_names[CHEESE].id)
            # Item 1: 40/60, Item 2: 80/120 → totals 120/180.
            assert pko_total == 120.0
            assert cheese_total == 180.0
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestVegOilWastageRebalanceAutoPlan:
    """End-to-end (DB-level) coverage for the wastage-reduction rebalance:
    when the licence's live Balance CIF exceeds the default 40/60 split's
    value, `compute_e132_auto_plan` shifts quantity from PKO to Cheese to
    close the gap. The pure-function math is exercised exhaustively in
    test_e132_plan.py::TestVegOilWastageRebalance — this only confirms the
    DB-aware adapter wires it through correctly."""

    def test_leftover_balance_shifts_pko_into_cheese(self, item_names):
        # Default split value = 402 (40×1.80 + 60×5.50). Give a much larger
        # balance so the leftover gets absorbed by converting PKO to Cheese.
        license_obj, patcher = _make_license("LIC-E132-REBALANCE-BASIC", Decimal('100000'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, remaining_cif = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            # PKO fully converted (max possible gain 40×3.70=148 can't come
            # close to using up a 100000 balance) — no PKO line at all.
            assert item_names[PKO].id not in by_name_id
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] == 100.0
            assert by_name_id[item_names[CHEESE].id]['planned_cif_fc'] == 550.0  # 100 × 5.50
        finally:
            patcher.stop()

    def test_reruns_with_unchanged_available_quantity_are_stable(self, item_names):
        # Calling compute_e132_auto_plan twice in a row with nothing else
        # changed (same available_quantity, same balance) must reproduce
        # IDENTICAL results — a pure recompute, never drifting.
        license_obj, patcher = _make_license("LIC-E132-REBALANCE-STABLE", Decimal('100000'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            run1, remaining1 = compute_e132_auto_plan(license_obj)
            run2, remaining2 = compute_e132_auto_plan(license_obj)
            key = lambda l: (l['import_item'], l['item_name'], l['planned_quantity'])
            assert sorted(run1, key=key) == sorted(run2, key=key)
            assert remaining1 == remaining2
        finally:
            patcher.stop()

    def test_partial_rebalance_leaves_other_categories_untouched(self, item_names):
        # A licence with Nuts + a Vegetable Oil split item, balance just
        # large enough to fully fund Nuts plus a partial PKO->Cheese shift.
        # Nuts' allocation must be exactly its own fixed-price value either
        # way. (Nuts quantity must be >= MIN_PLAN_QTY=50 or it's silently
        # excluded — see e132_auto_plan.py.)
        balance = Decimal('300') + Decimal('452')  # Nuts (100×3.00) + veg-oil default(402) + 50 surplus
        license_obj, patcher = _make_license("LIC-E132-REBALANCE-PARTIAL", balance)
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Cashew Nuts",
                hs_code=_hs('08021100'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, remaining_cif = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            assert by_name_id[item_names[NUT_NUTS].id]['planned_cif_fc'] == 300.0
            assert by_name_id[item_names[PKO].id]['planned_quantity'] < 40.0
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] > 60.0
            assert remaining_cif == pytest.approx(0.0, abs=0.01)
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestVegOilSplitPreservedOnceGenerated:
    """CRITICAL business rule: once Auto-Plan generates the PKO/Cheese
    split, it becomes a FIXED commitment. A second Auto-Plan run must never
    regenerate or recalculate it — it must re-emit the existing plan lines'
    CURRENT remaining_quantity/remaining_cif_fc unchanged, even if
    available_quantity has since moved (up or down)."""

    def test_no_existing_plan_gets_fresh_split_with_remaining_equal_to_planned(self, item_names):
        # A fresh line dict carries no explicit remaining_quantity/
        # remaining_cif_fc (matching every other E132 category) — it's
        # `save_plan_lines_for_license`'s job to default those to the
        # planned amount at creation. Verify the actual PERSISTED outcome.
        from apps.license.services.plan_enforcement import save_plan_lines_for_license

        license_obj, patcher = _make_license("LIC-E132-PRESERVE-FRESH", Decimal('402'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, _ = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 40.0
            assert 'remaining_quantity' not in by_name_id[item_names[PKO].id]
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] == 60.0

            saved = save_plan_lines_for_license(license_obj, lines)
            saved_by_name_id = {p.item_name_id: p for p in saved}
            assert saved_by_name_id[item_names[PKO].id].remaining_quantity == Decimal('40')
            assert saved_by_name_id[item_names[PKO].id].remaining_cif_fc == Decimal('72')
            assert saved_by_name_id[item_names[CHEESE].id].remaining_quantity == Decimal('60')
            assert saved_by_name_id[item_names[CHEESE].id].remaining_cif_fc == Decimal('330')
        finally:
            patcher.stop()

    def test_existing_partially_consumed_plan_is_preserved_not_recalculated(self, item_names):
        # PKO already partially consumed via a plan-line-aware allocation
        # (remaining=20 of its original 40) — a second Auto-Plan run must
        # re-emit exactly 20, never regenerate a fresh 40.
        license_obj, patcher = _make_license("LIC-E132-PRESERVE-PARTIAL", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('40'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('72'),
                remaining_quantity=Decimal('20'), remaining_cif_fc=Decimal('36'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[CHEESE],
                planned_quantity=Decimal('60'), unit_price=Decimal('5.50'), planned_cif_fc=Decimal('330'),
                remaining_quantity=Decimal('60'), remaining_cif_fc=Decimal('330'),
            )

            lines, _ = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            # Preserved exactly — NOT the fresh 40/60 the engine would
            # otherwise compute from available_quantity=100, and NOT a
            # rebalanced value either (a huge 100000 balance would normally
            # trigger wastage-rebalancing on a FRESH split).
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 20.0
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_preserved_even_after_available_quantity_shrinks(self, item_names):
        # Some of the import item's quantity was consumed by something
        # UNRELATED to this split (available_quantity dropped 100 -> 70),
        # but the existing PKO/Cheese plan must still be preserved exactly —
        # never recalculated as 40%/60% of the new, smaller available_quantity.
        license_obj, patcher = _make_license("LIC-E132-PRESERVE-AFTER-SHRINK", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('70'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('40'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('72'),
                remaining_quantity=Decimal('40'), remaining_cif_fc=Decimal('72'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[CHEESE],
                planned_quantity=Decimal('60'), unit_price=Decimal('5.50'), planned_cif_fc=Decimal('330'),
                remaining_quantity=Decimal('60'), remaining_cif_fc=Decimal('330'),
            )

            lines, _ = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            # NOT 28/42 (40%/60% of the new 70) -- the original 40/60 stands.
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 40.0
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_fully_consumed_plan_line_still_reported_at_zero(self, item_names):
        # PKO fully drained (remaining=0) must still be re-emitted (at 0),
        # not silently dropped — see e132_auto_plan.py's preservation branch.
        license_obj, patcher = _make_license("LIC-E132-PRESERVE-ZERO", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('40'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('72'),
                remaining_quantity=Decimal('0'), remaining_cif_fc=Decimal('0'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[CHEESE],
                planned_quantity=Decimal('60'), unit_price=Decimal('5.50'), planned_cif_fc=Decimal('330'),
                remaining_quantity=Decimal('60'), remaining_cif_fc=Decimal('330'),
            )

            lines, _ = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 0.0
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()
