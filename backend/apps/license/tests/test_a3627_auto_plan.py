"""Tests for the A3627 Auto-Plan service (services/a3627_auto_plan.py).

Mirrors the structure/conventions of test_e5_auto_plan.py and
test_e132_auto_plan.py: a `_create_license`/`_make_license` helper that
patches `LicenseDetailsModel.get_balance_cif` per-instance, and assertions
against the raw `lines`/`remaining_cif` returned by `compute_a3627_auto_plan`.

Business spec under test (4-priority waterfall, each "allocate max possible
quantity, deduct value, move to next"):
    1. RUTILE            — avg import price < $3.00 -> $2.50, else -> $3.50
    2. TITANIUM DIOXIDE   — fixed $2.00
    3. SODA ASH           — fixed $0.70
    4. PP                 — fixed $1.20
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models import CompanyModel, HSCodeModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.a3627_auto_plan import (
    PP_PRICE,
    RUTILE_PRICE_HIGH,
    RUTILE_PRICE_LOW,
    SODA_ASH_PRICE,
    TITANIUM_DIOXIDE_PRICE,
    compute_a3627_auto_plan,
)


def _hs(code):
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


def _create_license(license_number):
    company = CompanyModel.objects.create(iec=f"IEC{license_number[-7:]}", name="A3627 Auto-Plan Test Exporter")
    port, _ = PortModel.objects.get_or_create(code="INAPT2", defaults={"name": "A3627 Auto-Plan Test Port"})
    return LicenseDetailsModel.objects.create(
        license_number=license_number,
        license_date=date.today(),
        license_expiry_date=date.today(),
        exporter=company,
        port=port,
    )


def _patch_balances(balance_by_license_id: dict):
    """Instance-aware `get_balance_cif` stub — same convention as
    test_e5_auto_plan.py's `_patch_balances` (keyed by license pk so
    multi-licence tests can never leak one licence's balance into another)."""
    return patch.object(
        LicenseDetailsModel, "get_balance_cif",
        property(lambda self: balance_by_license_id[self.id]),
    )


def _make_license(license_number, balance_cif):
    license_obj = _create_license(license_number)
    patcher = _patch_balances({license_obj.id: balance_cif})
    patcher.start()
    return license_obj, patcher


def _rutile_item(license_obj, serial_number, quantity, cif_fc, description="Rutile Glass Formers with Borax", hs_code=None):
    """A RUTILE-classified import item: description must satisfy
    item_matcher's RUTILE filter (contains 'Rutile'/'Glass Formers'/'Formers'
    AND 'borax'). `quantity`/`cif_fc` drive the average import price;
    `available_quantity` is set equal to `quantity` (fresh, unconsumed)."""
    return LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=serial_number, description=description,
        hs_code=hs_code, quantity=quantity, available_quantity=quantity, cif_fc=cif_fc,
    )


def _titanium_item(license_obj, serial_number, quantity, description="Titanium Dioxide other than Anatase Grade"):
    return LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=serial_number, description=description,
        quantity=quantity, available_quantity=quantity,
    )


def _soda_ash_item(license_obj, serial_number, quantity, description="Soda Ash Light"):
    return LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=serial_number, description=description,
        quantity=quantity, available_quantity=quantity,
    )


def _pp_item(license_obj, serial_number, quantity, description="Polypropylene Granules"):
    return LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=serial_number, description=description,
        hs_code=_hs("39023000"), quantity=quantity, available_quantity=quantity,
    )


@pytest.mark.django_db
class TestRutileAveragePriceThreshold:

    def test_avg_below_3_uses_low_price(self):
        """avg = 285 / 100 = 2.85 < 3.00 -> RUTILE priced @2.50."""
        balance = Decimal('1000')
        license_obj, patcher = _make_license("LIC-A3627-AVG-285", balance)
        try:
            _rutile_item(license_obj, 1, Decimal('100'), Decimal('285.00'))
            lines, remaining_cif = compute_a3627_auto_plan(license_obj)

            assert len(lines) == 1
            assert lines[0]['unit_price'] == float(RUTILE_PRICE_LOW)
            assert lines[0]['planned_quantity'] == 100.0
            assert lines[0]['planned_cif_fc'] == 250.0
            assert Decimal(str(round(remaining_cif, 2))) == balance - Decimal('250.00')
        finally:
            patcher.stop()

    def test_avg_exactly_3_uses_high_price(self):
        """avg = 300 / 100 = 3.00 -> the ">= 3.00" branch -> priced @3.50."""
        balance = Decimal('1000')
        license_obj, patcher = _make_license("LIC-A3627-AVG-300", balance)
        try:
            _rutile_item(license_obj, 1, Decimal('100'), Decimal('300.00'))
            lines, remaining_cif = compute_a3627_auto_plan(license_obj)

            assert len(lines) == 1
            assert lines[0]['unit_price'] == float(RUTILE_PRICE_HIGH)
            assert lines[0]['planned_quantity'] == 100.0
            assert lines[0]['planned_cif_fc'] == 350.0
            assert Decimal(str(round(remaining_cif, 2))) == balance - Decimal('350.00')
        finally:
            patcher.stop()

    def test_avg_above_3_uses_high_price(self):
        """avg = 322 / 100 = 3.22 >= 3.00 -> RUTILE priced @3.50."""
        balance = Decimal('1000')
        license_obj, patcher = _make_license("LIC-A3627-AVG-322", balance)
        try:
            _rutile_item(license_obj, 1, Decimal('100'), Decimal('322.00'))
            lines, remaining_cif = compute_a3627_auto_plan(license_obj)

            assert len(lines) == 1
            assert lines[0]['unit_price'] == float(RUTILE_PRICE_HIGH)
            assert lines[0]['planned_cif_fc'] == 350.0
            assert Decimal(str(round(remaining_cif, 2))) == balance - Decimal('350.00')
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestWaterfallOrderAndConsumption:

    def test_remaining_flows_through_titanium_soda_ash_pp_in_order(self):
        """avg = 285/100 = 2.85 -> RUTILE @2.50. Balance flows through all 4
        priorities, in order, each consuming what it can before handing the
        rest to the next."""
        balance = Decimal('1000')
        license_obj, patcher = _make_license("LIC-A3627-WATERFALL", balance)
        try:
            _rutile_item(license_obj, 1, Decimal('100'), Decimal('285.00'))
            _titanium_item(license_obj, 2, Decimal('50'))
            _soda_ash_item(license_obj, 3, Decimal('200'))
            _pp_item(license_obj, 4, Decimal('1000'))

            lines, remaining_cif = compute_a3627_auto_plan(license_obj)

            by_note_prefix = {l['note']: l for l in lines}
            assert len(lines) == 4

            rutile_line = next(l for l in lines if 'Rutile' in l['note'])
            titanium_line = next(l for l in lines if 'Titanium' in l['note'])
            soda_ash_line = next(l for l in lines if 'Soda Ash' in l['note'])
            pp_line = next(l for l in lines if l['note'].endswith('PP)'))

            assert rutile_line['planned_quantity'] == 100.0
            assert rutile_line['planned_cif_fc'] == 250.0    # 100 * 2.50
            assert titanium_line['planned_quantity'] == 50.0
            assert titanium_line['planned_cif_fc'] == 100.0  # 50 * 2.00
            assert soda_ash_line['planned_quantity'] == 200.0
            assert soda_ash_line['planned_cif_fc'] == 140.0  # 200 * 0.70
            # Remaining after Rutile+Titanium+SodaAsh = 1000 - 250 - 100 - 140 = 510
            assert pp_line['planned_quantity'] == 425.0      # floor(510 / 1.20)
            assert pp_line['planned_cif_fc'] == 510.0

            assert Decimal(str(round(remaining_cif, 2))) == Decimal('0.00')
        finally:
            patcher.stop()

    def test_entire_value_consumed_by_rutile_alone(self):
        """Small balance, huge RUTILE availability -> Rutile absorbs the
        whole balance; Titanium/Soda Ash/PP get no lines at all (not even
        zero-value lines)."""
        balance = Decimal('100')
        license_obj, patcher = _make_license("LIC-A3627-RUTILE-ONLY", balance)
        try:
            _rutile_item(license_obj, 1, Decimal('1000'), Decimal('2850.00'))  # avg 2.85 -> $2.50
            _titanium_item(license_obj, 2, Decimal('500'))
            _soda_ash_item(license_obj, 3, Decimal('500'))
            _pp_item(license_obj, 4, Decimal('500'))

            lines, remaining_cif = compute_a3627_auto_plan(license_obj)

            assert len(lines) == 1
            assert 'Rutile' in lines[0]['note']
            assert lines[0]['planned_quantity'] == 40.0   # floor(100 / 2.50)
            assert lines[0]['planned_cif_fc'] == 100.0
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('0.00')
        finally:
            patcher.stop()

    def test_zero_balance_plans_nothing(self):
        balance = Decimal('0')
        license_obj, patcher = _make_license("LIC-A3627-ZERO-BALANCE", balance)
        try:
            _rutile_item(license_obj, 1, Decimal('100'), Decimal('250.00'))
            _titanium_item(license_obj, 2, Decimal('50'))
            _soda_ash_item(license_obj, 3, Decimal('200'))
            _pp_item(license_obj, 4, Decimal('1000'))

            lines, remaining_cif = compute_a3627_auto_plan(license_obj)

            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('0.00')
        finally:
            patcher.stop()

    def test_no_import_items_plans_nothing(self):
        license_obj, patcher = _make_license("LIC-A3627-EMPTY", Decimal('5000'))
        try:
            lines, remaining_cif = compute_a3627_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('5000')
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestPartialMultiItemAllocation:

    def test_second_group_in_same_category_gets_nothing_once_budget_exhausted(self):
        """Two DISTINCT RUTILE groups (different descriptions -> never
        pooled). The category's affordable quantity runs out mid-category:
        the first group (lower serial) gets planned in full; the second
        gets nothing — same "process within category in given order"
        convention every other Auto-Plan engine follows (e.g. e5_plan.py's
        oils sub-steps)."""
        balance = Decimal('300')
        license_obj, patcher = _make_license("LIC-A3627-MULTI-GROUP", balance)
        try:
            item1 = _rutile_item(
                license_obj, 1, Decimal('200'), Decimal('540.00'),
                description="Rutile Glass Formers Borax Batch A",
            )
            item2 = _rutile_item(
                license_obj, 2, Decimal('200'), Decimal('540.00'),
                description="Rutile Glass Formers Borax Batch B",
            )
            # avg = (540 + 540) / (200 + 200) = 2.70 -> $2.50
            lines, remaining_cif = compute_a3627_auto_plan(license_obj)

            assert len(lines) == 1
            assert lines[0]['import_item'] == item1.id
            assert lines[0]['planned_quantity'] == 120.0   # floor(300 / 2.50)
            assert lines[0]['planned_cif_fc'] == 300.0
            assert all(l['import_item'] != item2.id for l in lines)
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('0.00')
        finally:
            patcher.stop()

    def test_same_description_and_hsn_rutile_items_are_pooled_into_one_group(self):
        hsn = _hs('32061010')
        balance = Decimal('100000')
        license_obj, patcher = _make_license("LIC-A3627-GROUP-POOLED", balance)
        try:
            item1 = _rutile_item(license_obj, 1, Decimal('100'), Decimal('250.00'), hs_code=hsn)
            item2 = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Rutile Glass Formers with Borax",
                hs_code=hsn, quantity=Decimal('50'), available_quantity=Decimal('50'), cif_fc=Decimal('125.00'),
            )
            lines, _ = compute_a3627_auto_plan(license_obj)

            assert len(lines) == 1
            assert lines[0]['import_item'] == item1.id
            assert lines[0]['planned_quantity'] == 150.0
            assert lines[0]['planned_cif_fc'] == 375.0   # 150 * 2.50 (avg = 375/150 = 2.50 -> LOW)
            assert all(l['import_item'] != item2.id for l in lines)
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestRoundingEdges:

    def test_soda_ash_floors_to_whole_unit_and_leftover_flows_to_pp(self):
        """Balance of $10.05 against SODA ASH @0.70: floor(10.05/0.70)=14
        (9.80 used), the $0.25 leftover flows to PP, which is too small to
        buy even 1 unit @1.20 -> ends up as untouched remaining_cif."""
        balance = Decimal('10.05')
        license_obj, patcher = _make_license("LIC-A3627-ROUNDING", balance)
        try:
            _soda_ash_item(license_obj, 1, Decimal('1000'))
            _pp_item(license_obj, 2, Decimal('1000'))

            lines, remaining_cif = compute_a3627_auto_plan(license_obj)

            assert len(lines) == 1
            assert 'Soda Ash' in lines[0]['note']
            assert lines[0]['planned_quantity'] == 14.0
            assert lines[0]['planned_cif_fc'] == 9.8
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('0.25')
        finally:
            patcher.stop()

    def test_exact_division_leaves_zero_remaining(self):
        balance = Decimal('510.00')
        license_obj, patcher = _make_license("LIC-A3627-EXACT", balance)
        try:
            _pp_item(license_obj, 1, Decimal('1000'))
            lines, remaining_cif = compute_a3627_auto_plan(license_obj)

            assert len(lines) == 1
            assert lines[0]['planned_quantity'] == 425.0
            assert lines[0]['planned_cif_fc'] == 510.0
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('0.00')
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestPlannerFactoryAndDetectNormWiring:

    def test_detect_norm_resolves_a3627(self):
        from apps.core.models import SionNormClassModel, HeadSIONNormsModel
        from apps.license.services.norm_plan import detect_norm

        head, _ = HeadSIONNormsModel.objects.get_or_create(name="A3627 head")
        norm_obj, _ = SionNormClassModel.objects.get_or_create(
            norm_class="A3627", defaults={"head_norm": head},
        )
        license_obj = _create_license("LIC-A3627-DETECT")
        license_obj.export_license.create(norm_class=norm_obj)

        assert detect_norm(license_obj) == "A3627"

    def test_planner_factory_registers_a3627(self):
        from apps.license.services.planner_factory import PlannerFactory

        assert PlannerFactory.is_supported("A3627")
        assert "A3627" in PlannerFactory.supported_norms()

    def test_planner_factory_run_delegates_to_compute_a3627_auto_plan(self):
        from apps.license.services.planner_factory import PlannerFactory

        balance = Decimal('1000')
        license_obj, patcher = _make_license("LIC-A3627-FACTORY", balance)
        try:
            _rutile_item(license_obj, 1, Decimal('100'), Decimal('285.00'))
            result = PlannerFactory.run(license_obj, "A3627")

            assert len(result.lines) == 1
            assert result.lines[0]['planned_cif_fc'] == 250.0
            assert result.remaining_cif == pytest.approx(750.0)
        finally:
            patcher.stop()
