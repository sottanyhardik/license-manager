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
    """CRITICAL business rule: the PKO/Olive-Oil split is always 40%/60% of
    the import item's CURRENT `available_quantity` — never its
    original/total import quantity."""

    def test_fresh_split_targets_40_60_of_available_quantity(self, item_names):
        # balance_cif == exactly the default 40/60 split's value (372) so the
        # wastage-rebalance pass has nothing to do here.
        license_obj, patcher = _make_license("LIC-E126-SPLIT-FRESH", Decimal('372'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 40.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_split_follows_available_quantity_down_after_real_consumption(self, item_names):
        # 100kg originally imported, 40kg already really allotted/debited
        # elsewhere -> available_quantity is now 60kg. The split must be
        # 40%/60% of THAT 60kg (24/36) — never of the original 100.
        license_obj, patcher = _make_license("LIC-E126-SPLIT-AFTER-DEBIT", Decimal('223.2'))  # 24×1.80 + 36×5.00
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('60'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 24.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 36.0
        finally:
            patcher.stop()

    def test_reruns_with_no_existing_split_and_unchanged_available_quantity_are_stable(self, item_names):
        license_obj, patcher = _make_license("LIC-E126-SPLIT-RERUN", Decimal('372'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 40.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_split_scoped_per_import_item_not_licence_wide(self, item_names):
        # Two separate 100kg/200kg split items on the same licence each get
        # their OWN independent 40/60 target — not a pooled licence-wide split.
        license_obj, patcher = _make_license("LIC-E126-SPLIT-PER-ITEM", Decimal('1116'))  # 372 + 744
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('200'), available_quantity=Decimal('200'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            pko_total = sum(l['planned_quantity'] for l in lines if l['item_name'] == item_names[PKO].id)
            olive_total = sum(l['planned_quantity'] for l in lines if l['item_name'] == item_names[OLIVE_OIL].id)
            # Item 1: 40/60, Item 2: 80/120 → totals 120/180.
            assert pko_total == 120.0
            assert olive_total == 180.0
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestPkoOliveWastageRebalanceAutoPlan:
    """End-to-end (DB-level) coverage for the wastage-reduction rebalance:
    when the licence's live Balance CIF exceeds the default 40/60 split's
    value, `compute_e126_auto_plan` shifts quantity from PKO to Olive Oil to
    close the gap. The pure-function math is exercised exhaustively in
    test_e126_plan.py::TestPkoOliveWastageRebalance — this only confirms the
    DB-aware adapter wires it through correctly."""

    def test_leftover_balance_shifts_pko_into_olive_oil(self, item_names):
        # Default split value = 372 (40×1.80 + 60×5.00). Give a much larger
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

            # PKO fully converted (max possible gain 40×3.20=128 can't come
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
        balance = Decimal('300') + Decimal('422')  # Nuts (100×3.00) + split default(372) + 50 surplus
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
            assert by_name_id[item_names[PKO].id]['planned_quantity'] < 40.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] > 60.0
            assert remaining_cif == pytest.approx(0.0, abs=0.01)
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

        license_obj, patcher = _make_license("LIC-E126-PRESERVE-FRESH", Decimal('372'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 40.0
            assert 'remaining_quantity' not in by_name_id[item_names[PKO].id]
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 60.0

            saved = save_plan_lines_for_license(license_obj, lines)
            saved_by_name_id = {p.item_name_id: p for p in saved}
            assert saved_by_name_id[item_names[PKO].id].remaining_quantity == Decimal('40')
            assert saved_by_name_id[item_names[PKO].id].remaining_cif_fc == Decimal('72')
            assert saved_by_name_id[item_names[OLIVE_OIL].id].remaining_quantity == Decimal('60')
            assert saved_by_name_id[item_names[OLIVE_OIL].id].remaining_cif_fc == Decimal('300')
        finally:
            patcher.stop()

    def test_existing_partially_consumed_plan_is_preserved_not_recalculated(self, item_names):
        # PKO already partially consumed via a plan-line-aware allocation
        # (remaining=20 of its original 40) — a second Auto-Plan run must
        # re-emit exactly 20, never regenerate a fresh 40.
        license_obj, patcher = _make_license("LIC-E126-PRESERVE-PARTIAL", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=SPLIT_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('40'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('72'),
                remaining_quantity=Decimal('20'), remaining_cif_fc=Decimal('36'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[OLIVE_OIL],
                planned_quantity=Decimal('60'), unit_price=Decimal('5.00'), planned_cif_fc=Decimal('300'),
                remaining_quantity=Decimal('60'), remaining_cif_fc=Decimal('300'),
            )

            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            # Preserved exactly — NOT the fresh 40/60 the engine would
            # otherwise compute from available_quantity=100, and NOT a
            # rebalanced value either (a huge 100000 balance would normally
            # trigger wastage-rebalancing on a FRESH split).
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 20.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_preserved_even_after_available_quantity_shrinks(self, item_names):
        # Some of the import item's quantity was consumed by something
        # UNRELATED to this split (available_quantity dropped 100 -> 70),
        # but the existing PKO/Olive-Oil plan must still be preserved
        # exactly — never recalculated as 40%/60% of the new, smaller
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
                planned_quantity=Decimal('40'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('72'),
                remaining_quantity=Decimal('40'), remaining_cif_fc=Decimal('72'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[OLIVE_OIL],
                planned_quantity=Decimal('60'), unit_price=Decimal('5.00'), planned_cif_fc=Decimal('300'),
                remaining_quantity=Decimal('60'), remaining_cif_fc=Decimal('300'),
            )

            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            # NOT 28/42 (40%/60% of the new 70) -- the original 40/60 stands.
            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 40.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 60.0
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
                planned_quantity=Decimal('40'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('72'),
                remaining_quantity=Decimal('0'), remaining_cif_fc=Decimal('0'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[OLIVE_OIL],
                planned_quantity=Decimal('60'), unit_price=Decimal('5.00'), planned_cif_fc=Decimal('300'),
                remaining_quantity=Decimal('60'), remaining_cif_fc=Decimal('300'),
            )

            lines, _ = compute_e126_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 0.0
            assert by_name_id[item_names[OLIVE_OIL].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()
