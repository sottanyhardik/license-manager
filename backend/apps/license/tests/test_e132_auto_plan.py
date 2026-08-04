"""Tests for the E132 Auto-Plan service (services/e132_auto_plan.py).

`compute_e132_auto_plan` is the only DB-aware layer of the E132 planner — it
loads import items, reads this licence's existing `LicenseItemPlan` rows for
the Vegetable Oil 40/60 split (Rule 8's "existing debit adjustment"), and
delegates the actual classification/waterfall to the pure
`services.e132_plan` engine (already unit-tested in test_e132_plan.py).

These tests focus on what only this adapter can be responsible for: DB
mapping (ItemNameModel ids), the MIN_PLAN_QTY gate, and — the important new
behavior — reading prior `LicenseItemPlan` rows so re-running Auto-Plan
reconciles to the correct cumulative PKO/Cheese target instead of drifting,
zeroing out, or double counting.
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
class TestVegOilSplitDebitAdjustment:
    def test_fresh_split_targets_40_60_of_original_quantity(self, item_names):
        license_obj, patcher = _make_license("LIC-E132-SPLIT-FRESH", Decimal('100000'))
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

    def test_reruns_reconcile_to_target_not_naive_resplit(self, item_names):
        # The exact worked example from the business spec: 100kg item, PKO
        # already planned 30kg → this run must produce PKO=40 (10 new +
        # 30 already) / Cheese=60 in TOTAL — never 28/42 (naive re-split of
        # the 70kg physically remaining) and never 70/60 (ignoring history).
        license_obj, patcher = _make_license("LIC-E132-SPLIT-RERUN", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('70'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('30'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('54'),
            )

            lines, _ = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 40.0
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_target_already_fully_met_is_a_stable_fixed_point(self, item_names):
        # Simulate a THIRD run: the previous run already reconciled to the
        # full 40/60 target. Re-running again with nothing else changed must
        # reproduce exactly 40/60 — not drift, not zero out.
        license_obj, patcher = _make_license("LIC-E132-SPLIT-STABLE", Decimal('100000'))
        try:
            import_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[PKO],
                planned_quantity=Decimal('40'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('72'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=import_item, item_name=item_names[CHEESE],
                planned_quantity=Decimal('60'), unit_price=Decimal('5.50'), planned_cif_fc=Decimal('330'),
            )

            lines, _ = compute_e132_auto_plan(license_obj)
            by_name_id = {l['item_name']: l for l in lines}

            assert by_name_id[item_names[PKO].id]['planned_quantity'] == 40.0
            assert by_name_id[item_names[CHEESE].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_explicit_cheese_ignores_existing_pko_history(self, item_names):
        # An explicit Cheese+Vegetable+Oil item must always plan 100% of its
        # own available quantity to Cheese, regardless of any unrelated PKO
        # plan history sitting on a DIFFERENT import item.
        license_obj, patcher = _make_license("LIC-E132-EXPLICIT-CHEESE", Decimal('100000'))
        try:
            veg_oil_item = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description=VEG_OIL_DESC,
                hs_code=_hs('15132900'),
                quantity=Decimal('100'), available_quantity=Decimal('70'),
            )
            LicenseItemPlan.objects.create(
                license=license_obj, import_item=veg_oil_item, item_name=item_names[PKO],
                planned_quantity=Decimal('30'), unit_price=Decimal('1.80'), planned_cif_fc=Decimal('54'),
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

            # The unrelated Vegetable Oil item's own split is unaffected.
            veg_oil_lines = {l['item_name']: l for l in lines if l['import_item'] == veg_oil_item.id}
            assert veg_oil_lines[item_names[PKO].id]['planned_quantity'] == 40.0
            assert veg_oil_lines[item_names[CHEESE].id]['planned_quantity'] == 60.0
        finally:
            patcher.stop()

    def test_split_scoped_per_import_item_not_licence_wide(self, item_names):
        # Two separate 100kg Vegetable Oil items on the same licence each get
        # their OWN independent 40/60 target — not a pooled licence-wide split.
        license_obj, patcher = _make_license("LIC-E132-SPLIT-PER-ITEM", Decimal('1000000'))
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
