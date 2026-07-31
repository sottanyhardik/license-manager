"""Tests for the E5 Auto-Plan service (services/e5_auto_plan.py).

`compute_e5_auto_plan` is a thin adapter over the shared engine
(`services.e5_plan.plan_e5_items`) — these tests exercise the adapter's
grouping / DB-mapping logic and, critically, assert PARITY: the same item
set run directly through `plan_e5_items` must produce the same total
planned CIF that `compute_e5_auto_plan` returns, so Auto-Plan and reporting
can never silently drift apart again.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models import CompanyModel, HSCodeModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.e5_auto_plan import compute_e5_auto_plan
from apps.license.services.e5_plan import E5Item, classify_e5_item, plan_e5_items


def _hs(code):
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


def _create_license(license_number):
    company = CompanyModel.objects.create(iec=f"IEC{license_number[-7:]}", name="Auto-Plan Test Exporter")
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
    covering multiple licences at once gets each its own value (a plain
    `PropertyMock(return_value=...)` would apply the SAME value to every
    instance, which would silently mask a real cross-licence leak)."""
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
class TestComputeE5AutoPlanParity:

    def test_mixed_licence_matches_shared_engine_totals(self):
        balance = Decimal('10000')
        license_obj, patcher = _make_license("LIC-E5-AUTOPLAN-MIXED", balance)
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Dietary Fibre",
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=2, description="Milk & Milk Products",
                hs_code=_hs('04041010'),
                quantity=Decimal('100'), available_quantity=Decimal('100'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=3, description="Egg Albumin",
                hs_code=_hs('35021100'),
                quantity=Decimal('60'), available_quantity=Decimal('60'),
            )
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=4, description="Wheat Flour",
                quantity=Decimal('1000'), available_quantity=Decimal('1000'),
            )

            lines, remaining_cif = compute_e5_auto_plan(license_obj)

            # Rebuild the same item set directly against the shared engine —
            # same category/qty, same Auto-Plan options — and confirm the
            # dollar totals match exactly. This is the concrete guard against
            # Auto-Plan and reporting ever computing different numbers again.
            direct_items = [
                E5Item(key='df', category=classify_e5_item('', '', 'Dietary Fibre'), qty=Decimal('100')),
                E5Item(key='milk', category=classify_e5_item('', '04041010', 'Milk & Milk Products'), qty=Decimal('100')),
                E5Item(key='egg', category=classify_e5_item('', '35021100', 'Egg Albumin'), qty=Decimal('60')),
                E5Item(key='wf', category=classify_e5_item('Wheat Flour', '', 'Wheat Flour'), qty=Decimal('1000')),
            ]
            direct_result = plan_e5_items(direct_items, balance, min_plan_qty=Decimal('50'), floor_qty=True)

            total_auto_plan_cif = sum((Decimal(str(l['planned_cif_fc'])) for l in lines), Decimal('0'))
            total_direct_cif = sum((l.planned_cif for l in direct_result.lines), Decimal('0'))
            assert total_auto_plan_cif == total_direct_cif
            assert Decimal(str(round(remaining_cif, 2))) == direct_result.remaining_cif.quantize(Decimal('0.01'))

            # 0404 (DWP+SWP) and 3502 (WPC) both got planned — no averaging,
            # no branch left unplanned just because the other type is present.
            assert any('DWP' in l['note'] for l in lines)
            assert any('WPC' in l['note'] for l in lines)
        finally:
            patcher.stop()

    def test_item_below_min_plan_qty_is_not_planned(self):
        balance = Decimal('10000')
        license_obj, patcher = _make_license("LIC-E5-AUTOPLAN-TINY", balance)
        try:
            LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=1, description="Dietary Fibre",
                quantity=Decimal('49'), available_quantity=Decimal('49'),
            )
            lines, remaining_cif = compute_e5_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == balance
        finally:
            patcher.stop()

    def test_no_import_items_plans_nothing(self):
        license_obj, patcher = _make_license("LIC-E5-AUTOPLAN-EMPTY", Decimal('5000'))
        try:
            lines, remaining_cif = compute_e5_auto_plan(license_obj)
            assert lines == []
            assert Decimal(str(round(remaining_cif, 2))) == Decimal('5000')
        finally:
            patcher.stop()


@pytest.mark.django_db
class TestComputeE5AutoPlanPerLicenceIsolation:
    """No planning calculation or balance may leak between licences — each
    call to `compute_e5_auto_plan` must use only that licence's own items
    and starting balance, matching the batch `auto_plan_all` endpoint
    (views/item_plan.py), which runs this in a loop over many licences in
    a single request."""

    def test_two_licences_interleaved_do_not_affect_each_other(self):
        licence_a = _create_license("LIC-E5-ISO-A")
        LicenseImportItemsModel.objects.create(
            license=licence_a, serial_number=1, description="Dietary Fibre",
            quantity=Decimal('100'), available_quantity=Decimal('100'),
        )
        LicenseImportItemsModel.objects.create(
            license=licence_a, serial_number=2, description="Wheat Flour",
            quantity=Decimal('1000'), available_quantity=Decimal('1000'),
        )

        licence_b = _create_license("LIC-E5-ISO-B")
        LicenseImportItemsModel.objects.create(
            license=licence_b, serial_number=1, description="Milk & Milk Products",
            hs_code=_hs('04041030'),
            quantity=Decimal('200'), available_quantity=Decimal('200'),
        )
        LicenseImportItemsModel.objects.create(
            license=licence_b, serial_number=2, description="Wheat Flour",
            quantity=Decimal('1000'), available_quantity=Decimal('1000'),
        )

        # Deliberately very different balances — if A's balance ever leaked
        # into B (or vice versa), the totals below would not add up to each
        # licence's OWN starting balance.
        patcher = _patch_balances({licence_a.id: Decimal('1000'), licence_b.id: Decimal('50000')})
        patcher.start()
        try:
            lines_a1, remaining_a1 = compute_e5_auto_plan(licence_a)
            lines_b, remaining_b = compute_e5_auto_plan(licence_b)
            lines_a2, remaining_a2 = compute_e5_auto_plan(licence_a)  # re-run, interleaved with B

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
