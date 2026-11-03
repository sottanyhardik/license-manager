"""Canonical sale ↔ BOE allocation rule: pure tests (no DB).

Pins the expected outcomes of the approved rule for CIF and for quantity, and
proves that no sale-covered BOE amount is deducted twice.
"""

from decimal import Decimal

from django.test import SimpleTestCase

from apps.license.services.sale_boe_allocation import (
    BOE_COVERED,
    BOE_UNCOVERED,
    SALE_COVERED,
    SALE_NOT_LINKED,
    SALE_OVER_LINKED,
    SALE_PARTIALLY_COVERED,
    AllocationError,
    BoeEntry,
    BoeLink,
    SaleEntry,
    compute_licence_item_balances,
    compute_utilisation,
)


def cif(original, sales, boes, links=(), allotment=0):
    return compute_utilisation(
        measure="cif",
        original=original,
        sales=[SaleEntry("S1", s) for s in sales] if not isinstance(sales, dict) else sales,
        boes=[BoeEntry(f"B{i}", b) for i, b in enumerate(boes, start=1)] if not isinstance(boes, dict) else boes,
        links=links,
        outstanding_allotment=allotment,
    )


def qty(original, sales, boes, links=(), allotment=0):
    return compute_utilisation(
        measure="qty",
        original=original,
        sales=[SaleEntry("S1", qty=s) for s in sales],
        boes=[BoeEntry(f"B{i}", qty=b) for i, b in enumerate(boes, start=1)],
        links=links,
        outstanding_allotment=allotment,
    )


class ApprovedTableCifTests(SimpleTestCase):
    """Section 13 table, CIF. Original 1,000; sale 500."""

    def test_sale_only(self):
        r = cif("1000", ["500"], [])
        self.assertEqual(r.available, Decimal("500.00"))
        self.assertEqual(r.sales[0].status, SALE_NOT_LINKED)
        self.assertEqual(r.sales[0].remaining_customer_entitlement, Decimal("500.00"))

    def test_partial_linked_boes_do_not_reduce_seller_twice(self):
        # BOEs 40 + 50 + 100 = 190 are linked to the 500 sale.
        links = [
            BoeLink("L1", "B1", "S1", "40"),
            BoeLink("L2", "B2", "S1", "50"),
            BoeLink("L3", "B3", "S1", "100"),
        ]
        r = cif("1000", ["500"], ["40", "50", "100"], links)
        self.assertEqual(r.utilised, Decimal("500.00"))
        self.assertEqual(r.available, Decimal("500.00"))
        self.assertEqual(r.sales[0].status, SALE_PARTIALLY_COVERED)
        self.assertEqual(r.sales[0].remaining_customer_entitlement, Decimal("310.00"))

    def test_fully_linked_sale(self):
        links = [BoeLink("L1", "B1", "S1", "500")]
        r = cif("1000", ["500"], ["500"], links)
        self.assertEqual(r.available, Decimal("500.00"))
        self.assertEqual(r.sales[0].status, SALE_COVERED)
        self.assertEqual(r.sales[0].remaining_customer_entitlement, Decimal("0.00"))

    def test_additional_uncovered_boe(self):
        links = [BoeLink(f"L{i}", f"B{i}", "S1", v) for i, v in enumerate(["40", "50", "100"], start=1)]
        r = cif("1000", ["500"], ["40", "50", "100", "30"], links)
        self.assertEqual(r.uncovered_boe_total, Decimal("30.00"))
        self.assertEqual(r.utilised, Decimal("530.00"))
        self.assertEqual(r.available, Decimal("470.00"))
        self.assertEqual(r.boes[-1].status, BOE_UNCOVERED)

    def test_boe_linked_after_creation(self):
        # Case E: the 30 BOE is linked after it was recorded. Available moves 470 → 500.
        links = [BoeLink(f"L{i}", f"B{i}", "S1", v) for i, v in enumerate(["40", "50", "100", "30"], start=1)]
        r = cif("1000", ["500"], ["40", "50", "100", "30"], links)
        self.assertEqual(r.available, Decimal("500.00"))
        self.assertEqual(r.boes[-1].status, BOE_COVERED)

    def test_boe_unlinked_from_sale(self):
        # Case F: the 30 BOE was linked, then unlinked. Available 500 → 470.
        links = [BoeLink(f"L{i}", f"B{i}", "S1", v) for i, v in enumerate(["40", "50", "100"], start=1)]
        r = cif("1000", ["500"], ["40", "50", "100", "30"], links)
        self.assertEqual(r.available, Decimal("470.00"))


class ApprovedTableQuantityTests(SimpleTestCase):
    """Same table on quantity. Original 1,000 kg; sale 500 kg."""

    def test_sale_only(self):
        self.assertEqual(qty("1000", ["500"], []).available, Decimal("500.000"))

    def test_partial_linked_boes(self):
        links = [BoeLink("L1", "B1", "S1", qty="40"), BoeLink("L2", "B2", "S1", qty="50"), BoeLink("L3", "B3", "S1", qty="100")]
        r = qty("1000", ["500"], ["40", "50", "100"], links)
        self.assertEqual(r.available, Decimal("500.000"))
        self.assertEqual(r.sales[0].remaining_customer_entitlement, Decimal("310.000"))

    def test_additional_uncovered_boe(self):
        links = [BoeLink("L1", "B1", "S1", qty="40"), BoeLink("L2", "B2", "S1", qty="50"), BoeLink("L3", "B3", "S1", qty="100")]
        r = qty("1000", ["500"], ["40", "50", "100", "30"], links)
        self.assertEqual(r.available, Decimal("470.000"))

    def test_fully_linked(self):
        r = qty("1000", ["500"], ["500"], [BoeLink("L1", "B1", "S1", qty="500")])
        self.assertEqual(r.available, Decimal("500.000"))


class OverLinkingTests(SimpleTestCase):
    def test_over_linked_excess_is_counted_not_dropped(self):
        # Sale 500, BOEs linked 600. The 100 excess must still reduce the balance.
        links = [BoeLink("L1", "B1", "S1", "300"), BoeLink("L2", "B2", "S1", "300")]
        r = cif("1000", ["500"], ["300", "300"], links)
        self.assertEqual(r.over_linked_total, Decimal("100.00"))
        self.assertEqual(r.utilised, Decimal("600.00"))
        self.assertEqual(r.available, Decimal("400.00"))
        self.assertEqual(r.sales[0].status, SALE_OVER_LINKED)
        self.assertTrue(any("over-linked" in w for w in r.warnings))

    def test_over_linked_quantity(self):
        links = [BoeLink("L1", "B1", "S1", qty="300"), BoeLink("L2", "B2", "S1", qty="300")]
        r = qty("1000", ["500"], ["300", "300"], links)
        self.assertEqual(r.available, Decimal("400.000"))


class LifecycleTests(SimpleTestCase):
    def test_cancelled_sale_turns_linked_boes_into_uncovered_utilisation(self):
        # Case G: the sale and its links are removed. The 220 of BOEs remains as debit.
        r = cif("1000", [], ["40", "50", "100", "30"])
        self.assertEqual(r.uncovered_boe_total, Decimal("220.00"))
        self.assertEqual(r.available, Decimal("780.00"))

    def test_partial_sale_reduction_within_linked_amount(self):
        # Case H, reduction still covers all linked BOEs: sale 500 → 400, linked 190.
        links = [BoeLink(f"L{i}", f"B{i}", "S1", v) for i, v in enumerate(["40", "50", "100"], start=1)]
        r = cif("1000", ["400"], ["40", "50", "100"], links)
        self.assertEqual(r.available, Decimal("600.00"))
        self.assertEqual(r.over_linked_total, Decimal("0.00"))

    def test_partial_sale_reduction_below_linked_amount_becomes_over_linked(self):
        # Sale 500 → 150 with 190 still linked: 40 becomes excess utilisation, flagged.
        links = [BoeLink(f"L{i}", f"B{i}", "S1", v) for i, v in enumerate(["40", "50", "100"], start=1)]
        r = cif("1000", ["150"], ["40", "50", "100"], links)
        self.assertEqual(r.over_linked_total, Decimal("40.00"))
        self.assertEqual(r.utilised, Decimal("190.00"))
        self.assertEqual(r.available, Decimal("810.00"))

    def test_one_boe_split_across_two_sales(self):
        # BOE 100 covers 60 of sale A (60) and 40 of sale B (100).
        sales = [SaleEntry("A", "60"), SaleEntry("B", "100")]
        boes = [BoeEntry("B1", "100")]
        links = [BoeLink("LA", "B1", "A", "60"), BoeLink("LB", "B1", "B", "40")]
        r = compute_utilisation(measure="cif", original="1000", sales=sales, boes=boes, links=links)
        self.assertEqual(r.utilised, Decimal("160.00"))
        self.assertEqual(r.available, Decimal("840.00"))
        self.assertEqual(r.boes[0].status, BOE_COVERED)

    def test_multiple_customers_are_just_multiple_sales(self):
        sales = [SaleEntry("A", "300"), SaleEntry("B", "200")]
        links = [BoeLink("L1", "B1", "A", "300")]
        r = compute_utilisation(measure="cif", original="1000", sales=sales, boes=[BoeEntry("B1", "300")], links=links)
        self.assertEqual(r.utilised, Decimal("500.00"))
        self.assertEqual(r.available, Decimal("500.00"))


class NegativeAndPrecisionTests(SimpleTestCase):
    def test_negative_available_is_reported_not_floored(self):
        r = cif("1000", ["1200"], [])
        self.assertEqual(r.available, Decimal("-200.00"))
        self.assertTrue(r.is_over_utilised)
        self.assertEqual(r.over_utilised_amount, Decimal("200.00"))

    def test_decimal_exactness(self):
        # Sale 0.10 covered by 0.10 of a 0.20 BOE: uncovered 0.10. Utilised 0.20, available 0.80.
        r = cif("1.00", ["0.10"], ["0.20"], [BoeLink("L1", "B1", "S1", "0.10")])
        self.assertEqual(r.utilised, Decimal("0.20"))
        self.assertEqual(r.available, Decimal("0.80"))

    def test_quantity_is_quantised_to_three_places(self):
        r = qty("100", ["33.3333"], [])
        self.assertEqual(r.available, Decimal("66.667"))

    def test_outstanding_allotment_reduces_available(self):
        r = cif("1000", ["500"], [], allotment="200")
        self.assertEqual(r.utilised, Decimal("700.00"))
        self.assertEqual(r.available, Decimal("300.00"))


class InvariantGuardTests(SimpleTestCase):
    def test_boe_cannot_cover_more_than_its_own_amount(self):
        links = [BoeLink("L1", "B1", "A", "70"), BoeLink("L2", "B1", "B", "50")]
        with self.assertRaises(AllocationError):
            compute_utilisation(
                measure="cif", original="1000",
                sales=[SaleEntry("A", "70"), SaleEntry("B", "50")],
                boes=[BoeEntry("B1", "100")], links=links,
            )

    def test_link_to_unknown_sale_is_rejected(self):
        with self.assertRaises(AllocationError):
            compute_utilisation(
                measure="cif", original="1000", sales=[SaleEntry("A", "10")],
                boes=[BoeEntry("B1", "10")], links=[BoeLink("L1", "B1", "Z", "10")],
            )

    def test_duplicate_link_id_is_rejected(self):
        with self.assertRaises(AllocationError):
            compute_utilisation(
                measure="cif", original="1000", sales=[SaleEntry("A", "10")],
                boes=[BoeEntry("B1", "10")],
                links=[BoeLink("L1", "B1", "A", "5"), BoeLink("L1", "B1", "A", "5")],
            )

    def test_float_is_rejected(self):
        with self.assertRaises(TypeError):
            compute_utilisation(measure="cif", original=1000.0, sales=[], boes=[])

    def test_negative_input_is_rejected(self):
        with self.assertRaises(AllocationError):
            compute_utilisation(measure="cif", original="1000", sales=[SaleEntry("A", "-5")], boes=[])

    def test_unknown_measure_is_rejected(self):
        with self.assertRaises(AllocationError):
            compute_utilisation(measure="kg", original="1", sales=[], boes=[])

    def test_cif_and_quantity_are_independent(self):
        # Changing quantity must not change CIF and vice versa.
        base = dict(
            original_cif="1000", original_qty="1000",
            cif_sales=[SaleEntry("A", "500", qty="500")],
        )
        cif_only = compute_utilisation(measure="cif", original=base["original_cif"],
                                       sales=[SaleEntry("A", "500", qty="999")], boes=[])
        qty_only = compute_utilisation(measure="qty", original=base["original_qty"],
                                       sales=[SaleEntry("A", "500", qty="999")], boes=[])
        self.assertEqual(cif_only.available, Decimal("500.00"))
        self.assertEqual(qty_only.available, Decimal("1.000"))

    def test_item_balances_require_matching_items(self):
        with self.assertRaises(AllocationError):
            compute_licence_item_balances(cif={"i1": {"original": "1", "sales": [], "boes": []}}, qty={})


class NoDoubleCountTests(SimpleTestCase):
    """Every combination must satisfy: utilised = sold + uncovered BOE + over-linked + allotment."""

    def test_identity_holds_across_scenarios(self):
        scenarios = [
            ("500", ["500"], ["190"], [("B1", "190")]),
            ("1000", ["500", "200"], ["90", "400"], [("B1", "90"), ("B2", "200")]),
            ("1000", ["100"], ["250"], [("B1", "250")]),
        ]
        for original, sale_amts, boe_amts, pairs in scenarios:
            sales = [SaleEntry(f"S{i}", v) for i, v in enumerate(sale_amts, start=1)]
            boes = [BoeEntry(f"B{i}", v) for i, v in enumerate(boe_amts, start=1)]
            links = [BoeLink(f"L{i}", b, "S1", v) for i, (b, v) in enumerate(pairs, start=1)]
            r = compute_utilisation(measure="cif", original=original, sales=sales, boes=boes, links=links)
            self.assertEqual(
                r.utilised,
                r.sold_total + r.uncovered_boe_total + r.over_linked_total + r.outstanding_allotment,
            )
