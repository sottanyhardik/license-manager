"""Tests for the E1 Auto-Plan service (services/e1_auto_plan.py).

`compute_e1_auto_plan` is a thin adapter over the shared engine
(`services.e1_plan.plan_e1_items`) — these tests exercise the adapter's
grouping / DB-mapping logic and, critically, assert PARITY: the same item
set run directly through `plan_e1_items` must produce the same total
planned CIF that `compute_e1_auto_plan` returns, so Auto-Plan and reporting
can never silently drift apart again.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models import CompanyModel, HSCodeModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.e1_auto_plan import compute_e1_auto_plan
from apps.license.services.e1_plan import E1Item, classify_e1_item, plan_e1_items
from apps.license.services.plan_grouping import validate_group_plan_lines


def _hs(code):
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


def _create_license(license_number):
    company = CompanyModel.objects.create(iec=f"IEC{license_number[-7:]}", name="E1 Auto-Plan Test Exporter")
    port, _ = PortModel.objects.get_or_create(code="INAPT1", defaults={"name": "Auto-Plan Test Port"})
    return LicenseDetailsModel.objects.create(
        license_number=license_number,
        license_date=date.today(),
        license_expiry_date=date.today(),
        exporter=company,
        port=port,
    )


def _patch_balances(balance_by_license_id: dict):
    """Instance-aware `get_balance_cif` stub — keyed by license pk, so a test
    covering multiple licences at once gets each its own value."""
    return patch.object(
        LicenseDetailsModel, "get_balance_cif",
        property(lambda self: balance_by_license_id[self.id]),
    )


def _make_license(license_number, balance_cif):
    license_obj = _create_license(license_number)
    patcher = _patch_balances({license_obj.id: balance_cif})
    patcher.start()
    return license_obj, patcher


@pytest.mark.django_db
class TestComputeE1AutoPlanParity:

    def test_mixed_licence_matches_shared_engine_totals(self):
        balance = Decimal('20000')
        license_obj, patcher = _make_license("LIC-E1-AUTOPLAN-MIXED", balance)
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Other Confectionery Ingredients",
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Cocoa Mass",
                hs_code=_hs('18031000'),
                quantity=Decimal('60'), available_quantity=Decimal('60'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=3, description="Skimmed Milk Powder",
                hs_code=_hs('04041000'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=4, description="Egg Albumin",
                hs_code=_hs('35021100'),
                quantity=Decimal('60'), available_quantity=Decimal('60'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=5, description="Fruit Juice Concentrate",
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=6, description="Tartaric Acid",
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=7, description="Aluminium Foil",
                hs_code=_hs('76071190'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=8, description="Polypropylene Granules",
                hs_code=_hs('39021000'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )

            lines, remaining_cif = compute_e1_auto_plan(license_obj)

            # Rebuild the same item set directly against the shared engine —
            # same category/qty, same Auto-Plan options — and confirm the
            # dollar totals match exactly. This is the concrete guard against
            # Auto-Plan and reporting ever computing different numbers again.
            direct_items = [
                E1Item(key='conf', category=classify_e1_item('', '', 'Other Confectionery Ingredients'), qty=Decimal('100')),
                E1Item(key='cocoa', category=classify_e1_item('', '18031000', 'Cocoa Mass'), qty=Decimal('60')),
                E1Item(key='milk', category=classify_e1_item('', '04041000', 'Skimmed Milk Powder'), qty=Decimal('100')),
                E1Item(key='egg', category=classify_e1_item('', '35021100', 'Egg Albumin'), qty=Decimal('60')),
                E1Item(key='juice', category=classify_e1_item('', '', 'Fruit Juice Concentrate'), qty=Decimal('100')),
                E1Item(key='tartaric', category=classify_e1_item('', '', 'Tartaric Acid'), qty=Decimal('100')),
                E1Item(key='foil', category=classify_e1_item('', '76071190', 'Aluminium Foil'), qty=Decimal('100')),
                E1Item(key='pp', category=classify_e1_item('', '39021000', 'Polypropylene Granules'), qty=Decimal('100')),
            ]
            direct_result = plan_e1_items(direct_items, balance, min_plan_qty=Decimal('50'))

            total_auto_plan_cif = sum((Decimal(str(l['planned_cif_fc'])) for l in lines), Decimal('0'))
            total_direct_cif = sum((l.planned_cif for l in direct_result.lines), Decimal('0'))
            assert total_auto_plan_cif == total_direct_cif
            assert Decimal(str(round(remaining_cif, 2))) == direct_result.remaining_cif.quantize(Decimal('0.01'))

            # All 8 stages actually produced a line.
            assert any('Step 1' in l['note'] for l in lines)
            assert any('Step 2' in l['note'] for l in lines)
            assert any('DWP' in l['note'] or 'SWP' in l['note'] for l in lines)
            assert any('Step 4' in l['note'] for l in lines)
            assert any('Step 5' in l['note'] for l in lines)
            assert any('Step 6' in l['note'] for l in lines)
            assert any('Step 7' in l['note'] for l in lines)
            assert any('Step 8' in l['note'] for l in lines)
        finally:
            patcher.stop()

    def test_item_below_min_plan_qty_is_not_planned(self):
        balance = Decimal('10000')
        license_obj, patcher = _make_license("LIC-E1-AUTOPLAN-TINY", balance)
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Other Confectionery Ingredients",
                quantity=Decimal('49'), available_quantity=Decimal('49'),
            )
            lines, remaining_cif = compute_e1_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == balance
        finally:
            patcher.stop()

    def test_no_import_items_plans_nothing(self):
        license_obj, patcher = _make_license("LIC-E1-AUTOPLAN-EMPTY", Decimal('5000'))
        try:
            lines, remaining_cif = compute_e1_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('5000')
        finally:
            patcher.stop()

    def test_unclassified_items_are_left_unplanned(self):
        balance = Decimal('10000')
        license_obj, patcher = _make_license("LIC-E1-AUTOPLAN-UNCLASSIFIED", balance)
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Refined Cane Sugar",
                hs_code=_hs('17019990'),
                quantity=Decimal('1000'), available_quantity=Decimal('1000'),
            )
            lines, remaining_cif = compute_e1_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == balance
        finally:
            patcher.stop()

    def test_zero_balance_plans_nothing(self):
        license_obj, patcher = _make_license("LIC-E1-AUTOPLAN-ZEROBAL", Decimal('0'))
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Other Confectionery Ingredients",
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, remaining_cif = compute_e1_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('0')
        finally:
            patcher.stop()

    def test_milk_step_only_invokes_shared_milk_splitter_for_milk_products(self):
        # Egg Albumin (a plain generic step) must NOT be priced via the milk
        # splitter's DWP/SWP ceilings (4.40/1.50) — only Milk Products (step 3)
        # delegates to split_milk_0404. Egg Albumin's own $25 ceiling comes
        # from the generic routine (Step 4).
        balance = Decimal('100000')
        license_obj, patcher = _make_license("LIC-E1-AUTOPLAN-MILKSCOPE", balance)
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Skimmed Milk Powder",
                hs_code=_hs('04041000'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Egg Albumin",
                hs_code=_hs('35021100'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lines, _ = compute_e1_auto_plan(license_obj)
            egg_lines = [l for l in lines if 'Step 4' in l['note']]
            milk_lines = [l for l in lines if 'DWP' in l['note'] or 'SWP' in l['note']]
            assert egg_lines and egg_lines[0]['unit_price'] == 25.0
            assert milk_lines and all(l['unit_price'] in (5.0, 1.5, 4.4) for l in milk_lines)
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestComputeE1AutoPlanGrouping:
    """E1 now groups via the SAME canonical `plan_group_key` (HSN +
    normalized description) every other Auto-Plan engine and every plan-
    consuming layer (enforcement, display, exports) uses — previously E1
    grouped by description ALONE (`auto_plan_shared.group_by_desc`), a
    narrower key that could pool two items plan_status_for's HSN-aware
    enforcement would treat as separate groups (a real, if rare, bug: the
    whole pooled plan sat on one representative whose own HSN-based group
    didn't cover the other member, leaving it unconstrained). Real dev-DB
    licence `0311045101` has exactly this shape (two items, same
    description, different HS codes) — these tests mirror it."""

    def test_same_description_and_hsn_items_are_pooled_into_one_group(self):
        balance = Decimal('100000')
        license_obj, patcher = _make_license("LIC-E1-GROUP-POOLED", balance)
        try:
            hsn = _hs('08021100')
            item1 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Other Confectionery Ingredients",
                hs_code=hsn, quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            item2 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Other Confectionery Ingredients",
                hs_code=hsn, quantity=Decimal('50'), available_quantity=Decimal('50'),
            )
            lines, _ = compute_e1_auto_plan(license_obj)

            # Pooled into ONE group (150kg @ $3.00 = $450), anchored on the
            # representative (lowest serial_number = item1) — never two
            # independent lines.
            assert len(lines) == 1
            assert lines[0]['import_item'] == item1.id
            assert lines[0]['planned_quantity'] == 150.0
            assert lines[0]['planned_cif_fc'] == 450.0
            assert all(l['import_item'] != item2.id for l in lines)
        finally:
            patcher.stop()

    def test_same_description_different_hsn_items_are_never_pooled(self):
        # The exact fix this migration delivers: same description, DIFFERENT
        # HS codes must plan (and therefore enforce) SEPARATELY — mirrors
        # real licence 0311045101's shape.
        balance = Decimal('100000')
        license_obj, patcher = _make_license("LIC-E1-GROUP-DIFF-HSN", balance)
        try:
            item1 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Other Confectionery Ingredients",
                hs_code=_hs('08021100'), quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            item2 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Other Confectionery Ingredients",
                hs_code=_hs('08029000'), quantity=Decimal('50'), available_quantity=Decimal('50'),
            )
            lines, _ = compute_e1_auto_plan(license_obj)

            assert len(lines) == 2
            by_item = {l['import_item']: l for l in lines}
            assert by_item[item1.id]['planned_quantity'] == 100.0
            assert by_item[item2.id]['planned_quantity'] == 50.0
        finally:
            patcher.stop()

    def test_representative_is_lowest_serial_number(self):
        # Create the HIGHER-serial item FIRST (so it gets the LOWER DB id)
        # to prove serial_number decides the representative, not id or
        # creation order — the real DGFT-resync shape found in dev-DB data.
        balance = Decimal('100000')
        license_obj, patcher = _make_license("LIC-E1-GROUP-REP", balance)
        try:
            hsn = _hs('08021100')
            higher_serial_lower_id = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=12, description="Other Confectionery Ingredients",
                hs_code=hsn, quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            lower_serial_higher_id = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Other Confectionery Ingredients",
                hs_code=hsn, quantity=Decimal('50'), available_quantity=Decimal('50'),
            )
            assert higher_serial_lower_id.id < lower_serial_higher_id.id  # sanity

            lines, _ = compute_e1_auto_plan(license_obj)
            assert len(lines) == 1
            assert lines[0]['import_item'] == lower_serial_higher_id.id
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestComputeE1AutoPlanIsIdempotent:
    """E1 has no "preserve once generated" concept — every run is a fresh
    recompute — so re-running Auto-Plan against unchanged data must settle
    to IDENTICAL persisted rows every time: same representative, same
    totals, no duplication and no drift to a different member of the group
    across runs. `save_plan_lines_for_license`'s `delete_existing=True`
    default makes this true by construction, but the group's chosen
    representative must also stay stable run-to-run for that guarantee to
    actually hold."""

    def test_rerunning_and_resaving_produces_identical_rows(self):
        from apps.license.models import LicenseItemPlan
        from apps.license.services.plan_enforcement import save_plan_lines_for_license

        balance = Decimal('100000')
        license_obj, patcher = _make_license("LIC-E1-IDEMPOTENT", balance)
        try:
            hsn = _hs('08021100')
            item1 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Other Confectionery Ingredients",
                hs_code=hsn, quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Other Confectionery Ingredients",
                hs_code=hsn, quantity=Decimal('50'), available_quantity=Decimal('50'),
            )

            lines_first, _ = compute_e1_auto_plan(license_obj)
            save_plan_lines_for_license(license_obj, lines_first)
            first_run = list(
                LicenseItemPlan.objects.filter(license=license_obj)
                .values_list('import_item_id', 'planned_quantity', 'planned_cif_fc')
            )

            lines_second, _ = compute_e1_auto_plan(license_obj)
            save_plan_lines_for_license(license_obj, lines_second)
            second_run = list(
                LicenseItemPlan.objects.filter(license=license_obj)
                .values_list('import_item_id', 'planned_quantity', 'planned_cif_fc')
            )

            assert lines_first == lines_second
            assert len(first_run) == 1
            assert first_run == second_run
            assert first_run[0][0] == item1.id
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestE1SharedValidatorAgreesWithRealOutput:
    """E1 runs `validate_fresh_plan_lines` at runtime (qty/non-negative
    checks only — see e1_auto_plan.py's module docstring for why no
    price-ceiling check applies), not the stricter `validate_group_plan_lines`
    E126/E132 use. This proves E1's real computed output would ALSO satisfy
    the stricter validator's price-ceiling check, not just the lighter one
    actually wired in — extra proof the waterfall is structurally bounded,
    not just an untested assumption."""

    def test_shared_validator_accepts_real_pooled_e1_output(self):
        balance = Decimal('100000')
        license_obj, patcher = _make_license("LIC-E1-VALIDATOR-CHECK", balance)
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Other Confectionery Ingredients",
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Other Confectionery Ingredients",
                quantity=Decimal('50'), available_quantity=Decimal('50'),
            )
            lines, _ = compute_e1_auto_plan(license_obj)
            assert len(lines) == 1

            assert validate_group_plan_lines(
                lines, ['OTHER CONFECTIONERY INGREDIENTS'], Decimal('150'),
                {'OTHER CONFECTIONERY INGREDIENTS': Decimal('3.00')}, is_preserved=False,
            ) is True
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestComputeE1AutoPlanPerLicenceIsolation:
    """No planning calculation or balance may leak between licences — each
    call to `compute_e1_auto_plan` must use only that licence's own items
    and starting balance."""

    def test_two_licences_interleaved_do_not_affect_each_other(self):
        licence_a = _create_license("LIC-E1-ISO-A")
        LicenseImportItemsModel.objects.create(
            license=licence_a, serial_number=1, description="Other Confectionery Ingredients",
            quantity=Decimal('100'), available_quantity=Decimal('100'),
        )
        LicenseImportItemsModel.objects.create(
            license=licence_a, serial_number=2, description="Aluminium Foil",
            hs_code=_hs('76071190'),
            quantity=Decimal('100'), available_quantity=Decimal('100'),
        )

        licence_b = _create_license("LIC-E1-ISO-B")
        LicenseImportItemsModel.objects.create(
            license=licence_b, serial_number=1, description="Skimmed Milk Powder",
            hs_code=_hs('04041000'),
            quantity=Decimal('200'), available_quantity=Decimal('200'),
        )
        LicenseImportItemsModel.objects.create(
            license=licence_b, serial_number=2, description="Polypropylene Granules",
            hs_code=_hs('39021000'),
            quantity=Decimal('1000'), available_quantity=Decimal('1000'),
        )

        # Deliberately very different balances — if A's balance ever leaked
        # into B (or vice versa), the totals below would not add up to each
        # licence's OWN starting balance.
        patcher = _patch_balances({licence_a.id: Decimal('1000'), licence_b.id: Decimal('50000')})
        patcher.start()
        try:
            lines_a1, remaining_a1 = compute_e1_auto_plan(licence_a)
            lines_b, remaining_b = compute_e1_auto_plan(licence_b)
            lines_a2, remaining_a2 = compute_e1_auto_plan(licence_a)  # re-run, interleaved with B

            # A's result is identical regardless of whether B was planned
            # in between — no shared/global state carried over.
            assert lines_a1 == lines_a2
            assert remaining_a1 == remaining_a2

            total_a = sum((Decimal(str(l['planned_cif_fc'])) for l in lines_a1), Decimal('0'))
            total_b = sum((Decimal(str(l['planned_cif_fc'])) for l in lines_b), Decimal('0'))
            assert total_a + Decimal(str(round(remaining_a1, 2))) == Decimal('1000')
            assert total_b + Decimal(str(round(remaining_b, 2))) == Decimal('50000')
        finally:
            patcher.stop()
