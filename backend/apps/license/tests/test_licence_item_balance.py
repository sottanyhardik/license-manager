"""Licence item movement balance: pure tests (no DB).

Covers the brief's item-level examples for CIF and quantity, the identity
Original = Debited + Allotted + Invoiced + Available, unit handling, unmapped
amounts and aggregation. DB-backed and API tests are not in this module.
"""

from decimal import Decimal

from django.test import SimpleTestCase

from apps.license.services.licence_item_balance import (
    OVER_UTILISED,
    RECONCILED,
    REVIEW_REQUIRED,
    UNIT_UNVERIFIED,
    UNMAPPED_ITEM,
    aggregate_items,
    build_item_balance,
    normalise_unit,
)
from apps.license.services.sale_boe_allocation import (
    AllocationError,
    BoeEntry,
    BoeLink,
    SaleEntry,
)


def qty_item(**kwargs):
    kwargs.setdefault("unit", "kg")
    return build_item_balance(measure="qty", **kwargs)


class BriefExampleTests(SimpleTestCase):
    """Brief §2 example: original 1,000; debited 540; allotted 160; invoiced 100; available 200."""

    def _boes(self):
        # Debited 540 comes from BOEs not covered by any sale (uncovered).
        return [BoeEntry("B1", cif=200, qty=200), BoeEntry("B2", cif=340, qty=340)]

    def test_quantity_example_balances_to_200(self):
        r = qty_item(original=1000, sales=[SaleEntry("S1", qty=100)], boes=self._boes(), outstanding_allotment=160)
        self.assertEqual(r.debited, Decimal("540.000"))
        self.assertEqual(r.allotted, Decimal("160.000"))
        self.assertEqual(r.invoiced, Decimal("100.000"))
        self.assertEqual(r.available, Decimal("200.000"))
        self.assertTrue(r.identity_ok)
        self.assertEqual(r.status, RECONCILED)

    def test_cif_equivalent_uses_cif_amounts_not_quantity(self):
        r = build_item_balance(
            measure="cif", original=1000,
            sales=[SaleEntry("S1", cif=100, qty=999)],  # qty must not leak into CIF
            boes=[BoeEntry("B1", cif=200, qty=1), BoeEntry("B2", cif=340, qty=1)],
            outstanding_allotment=160,
        )
        self.assertEqual(r.available, Decimal("200.00"))
        self.assertTrue(r.identity_ok)


class SaleCoverageTests(SimpleTestCase):
    def test_sale_covered_boe_is_inside_invoiced_not_debited(self):
        # Sale 500; BOEs 40+50+100 linked. Invoiced 500 (of which 190 BOE-covered); debited 0.
        links = [BoeLink("L1", "B1", "S1", "40"), BoeLink("L2", "B2", "S1", "50"), BoeLink("L3", "B3", "S1", "100")]
        r = build_item_balance(
            measure="cif", original=1000,
            sales=[SaleEntry("S1", cif=500)],
            boes=[BoeEntry("B1", cif=40), BoeEntry("B2", cif=50), BoeEntry("B3", cif=100)],
            links=links,
        )
        self.assertEqual(r.invoiced, Decimal("500.00"))
        self.assertEqual(r.invoiced_boe_covered, Decimal("190.00"))
        self.assertEqual(r.debited, Decimal("0.00"))
        self.assertEqual(r.available, Decimal("500.00"))

    def test_uncovered_boe_is_debited(self):
        links = [BoeLink("L1", "B1", "S1", "190")]
        r = build_item_balance(
            measure="cif", original=1000,
            sales=[SaleEntry("S1", cif=500)],
            boes=[BoeEntry("B1", cif=190), BoeEntry("B2", cif=30)],
            links=links,
        )
        self.assertEqual(r.debited, Decimal("30.00"))
        self.assertEqual(r.available, Decimal("470.00"))

    def test_over_linked_excess_is_debited_and_flagged(self):
        links = [BoeLink("L1", "B1", "S1", "300"), BoeLink("L2", "B2", "S1", "300")]
        r = build_item_balance(
            measure="cif", original=1000,
            sales=[SaleEntry("S1", cif=500)],
            boes=[BoeEntry("B1", cif=300), BoeEntry("B2", cif=300)],
            links=links,
        )
        self.assertEqual(r.debited, Decimal("100.00"))
        self.assertEqual(r.available, Decimal("400.00"))
        self.assertIn("OVER_LINKED", r.flags)
        self.assertEqual(r.status, REVIEW_REQUIRED)


class AllotmentAndNegativeTests(SimpleTestCase):
    def test_cancelled_allotment_releases_reservation(self):
        r = build_item_balance(measure="cif", original=1000, sales=[], boes=[], outstanding_allotment=0)
        self.assertEqual(r.available, Decimal("1000.00"))

    def test_negative_available_is_shown_and_flagged(self):
        r = build_item_balance(measure="cif", original=100, sales=[SaleEntry("S1", cif=150)], boes=[])
        self.assertEqual(r.available, Decimal("-50.00"))
        self.assertTrue(r.is_over_utilised)
        self.assertEqual(r.over_utilised_amount, Decimal("50.00"))
        self.assertEqual(r.status, OVER_UTILISED)


class UnitAndMappingTests(SimpleTestCase):
    def test_kg_case_variants_normalise(self):
        self.assertEqual(normalise_unit("KG"), ("kg", "VERIFIED"))
        self.assertEqual(normalise_unit(" Kg "), ("kg", "VERIFIED"))

    def test_mts_is_unverified_and_requires_review(self):
        unit, status = normalise_unit("mts")
        self.assertEqual(status, UNIT_UNVERIFIED)
        r = qty_item(original="166831.32", sales=[], boes=[], unit="mts")
        self.assertEqual(r.status, REVIEW_REQUIRED)
        self.assertIn(UNIT_UNVERIFIED, r.flags)

    def test_missing_unit_is_unverified(self):
        r = build_item_balance(measure="qty", original=10, sales=[], boes=[], unit=None)
        self.assertEqual(r.unit_status, UNIT_UNVERIFIED)

    def test_unmapped_amount_is_reported_and_not_deducted(self):
        r = build_item_balance(measure="cif", original=1000, sales=[], boes=[BoeEntry("B1", cif=100)], unmapped="25")
        self.assertEqual(r.unmapped, Decimal("25"))
        self.assertEqual(r.available, Decimal("900.00"))
        self.assertEqual(r.status, UNMAPPED_ITEM)

    def test_float_unmapped_is_rejected(self):
        with self.assertRaises(TypeError):
            build_item_balance(measure="cif", original=1, sales=[], boes=[], unmapped=0.5)

    def test_negative_unmapped_is_rejected(self):
        with self.assertRaises(AllocationError):
            build_item_balance(measure="cif", original=1, sales=[], boes=[], unmapped="-1")


class AggregationTests(SimpleTestCase):
    def test_item_totals_sum_to_licence_and_keep_identity(self):
        a = build_item_balance(measure="cif", original=1000, sales=[SaleEntry("S1", cif=500)], boes=[BoeEntry("B1", cif=30)])
        b = build_item_balance(measure="cif", original=500, sales=[], boes=[BoeEntry("B2", cif=100)])
        total = aggregate_items([a, b])
        self.assertEqual(total.original, Decimal("1500.00"))
        self.assertEqual(total.debited, Decimal("130.00"))
        self.assertEqual(total.invoiced, Decimal("500.00"))
        self.assertEqual(total.available, Decimal("870.00"))
        self.assertTrue(total.identity_ok)

    def test_cif_and_quantity_cannot_be_aggregated_together(self):
        c = build_item_balance(measure="cif", original=1, sales=[], boes=[])
        q = qty_item(original=1, sales=[], boes=[])
        with self.assertRaises(AllocationError):
            aggregate_items([c, q])

    def test_mixed_quantity_units_are_refused(self):
        a = qty_item(original=10, sales=[], boes=[], unit="kg")
        b = qty_item(original=10, sales=[], boes=[], unit="mts")
        with self.assertRaises(AllocationError):
            aggregate_items([a, b])

    def test_unmapped_is_carried_into_licence_total(self):
        a = build_item_balance(measure="cif", original=100, sales=[], boes=[], unmapped="5")
        b = build_item_balance(measure="cif", original=100, sales=[], boes=[])
        total = aggregate_items([a, b])
        self.assertEqual(total.unmapped, Decimal("5"))
        self.assertEqual(total.status, UNMAPPED_ITEM)
