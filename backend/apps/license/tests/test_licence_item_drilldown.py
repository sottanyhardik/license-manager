"""Database-backed tests for the item drill-down (BOE debits, customer allotments, invoices).

Builds real records through the same fixture as test_licence_balance_report and checks that every
drill-down group reconciles to the item table. Money is compared as strings, as the API returns it.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import BillOfEntryModel
from apps.license.services.licence_balance_report import (
    CROSS_ITEM_STATUS,
    OVER_LINKED_BOE_STATUS,
    PREVIOUS_OWNER_DEDUCTED,
    build_licence_balance_reports,
    build_licence_transactions,
)
from apps.license.services.licence_item_balance import RECONCILED, UNIT_UNVERIFIED
from apps.license.services.licence_item_drilldown import (
    LINKED_BOE_WITHOUT_DEBIT,
    NOTE_NOT_NETTED,
    EXCESS_KIND,
    RELEASE_RECORDED,
    SALE_OVERLAP,
    _check,
    build_item_drilldown,
)
from apps.license.tests import test_licence_balance_report as base
from apps.reconciliation.models import ReconciliationLog
from apps.trade.models import LicenseTrade, LicenseTradeLine

D = Decimal
MISMATCH = "MISMATCH"


class DrilldownFixture(base.ReportFixture):
    def drill(self, item=None, licence=None):
        licence = licence or self.licence
        return build_item_drilldown(licence.id, (item or self.item).id)

    def boe_rows(self, drill):
        return [r for r in drill["boes"]["rows"] if r["kind"] == "BOE"]

    def row_for(self, drill, number):
        return next(r for r in self.boe_rows(drill) if r["boe_number"] == number)

    def assert_reconciled(self, drill):
        self.assertEqual(drill["reconciliation"]["status"], RECONCILED, drill["reconciliation"])

    def purchase(self, *, invoice, cif, qty, item=None):
        item = item or self.item
        trade = LicenseTrade.objects.create(
            direction="PURCHASE", invoice_number=invoice, invoice_date=base.date.today(),
            from_company=self.customer, to_company=self.seller,
        )
        LicenseTradeLine.objects.create(trade=trade, sr_number=item, cif_fc=D(cif), cif_inr=D(cif) * D("84.5"), qty_kg=D(qty))
        return trade


class BoeDebitDrilldownTests(DrilldownFixture):
    def test_multiple_boes_covered_by_one_sale_are_listed_and_not_debited(self):
        trade, _ = self._sale(invoice="D-1", cif="500", qty="500")
        self._boe("D-A", cif="40", qty="40", trades=[trade])
        self._boe("D-B", cif="100", qty="100", trades=[trade])
        drill = self.drill()
        self.assertEqual(len(self.boe_rows(drill)), 2)
        self.assertEqual({r["status"] for r in self.boe_rows(drill)}, {"COVERED BY SALE"})
        self.assertEqual(drill["boes"]["totals"]["covered_cif"], "140.00")
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "0.00")
        self.assert_reconciled(drill)

    def test_partly_allocated_boe_keeps_original_covered_and_uncovered_amounts(self):
        trade, line = self._sale(invoice="D-2", cif="100", qty="100")
        _boe, row = self._boe("D-P", cif="300", qty="300", trades=[trade])
        self._allocate(row, line, "100", "100")
        drill = self.drill()
        boe = self.row_for(drill, "D-P")
        self.assertEqual(boe["status"], "PARTIALLY COVERED")
        self.assertEqual((boe["boe_cif"], boe["covered_cif"], boe["debited_cif"]), ("300.00", "100.00", "200.00"))
        self.assertEqual(boe["sale_links"][0]["basis"], "ALLOCATION")
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "200.00")
        self.assert_reconciled(drill)

    def test_uncovered_boe_is_a_full_debit(self):
        self._boe("U-1", cif="30", qty="30")
        drill = self.drill()
        boe = self.row_for(drill, "U-1")
        self.assertEqual(boe["status"], "UNCOVERED")
        self.assertEqual(boe["debited_cif"], "30.00")
        self.assertEqual(boe["sale_links"], [])
        self.assert_reconciled(drill)

    def test_over_linked_excess_is_its_own_debit_row_and_totals_match(self):
        trade, _ = self._sale(invoice="O-1", cif="500", qty="500")
        self._boe("O-A", cif="300", qty="300", trades=[trade])
        self._boe("O-B", cif="300", qty="300", trades=[trade])
        drill = self.drill()
        self.assertEqual({r["status"] for r in self.boe_rows(drill)}, {OVER_LINKED_BOE_STATUS})
        excess = [r for r in drill["boes"]["rows"] if r["kind"] == EXCESS_KIND]
        self.assertEqual(len(excess), 1)
        self.assertEqual(excess[0]["debited_cif"], "100.00")
        self.assertEqual(excess[0]["invoice_number"], "O-1")
        self.assertEqual(drill["boes"]["totals"]["over_linked_cif"], "100.00")
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "100.00")
        self.assert_reconciled(drill)

    def test_boe_linked_to_an_allotment_lists_the_allotment(self):
        boe, _ = self._boe("A-1", cif="60", qty="60")
        allotment = self._allotment(self.item, cif="100", qty="100", boes=[boe])
        drill = self.drill()
        self.assertEqual(self.row_for(drill, "A-1")["allotment_ids"], [allotment.id])
        self.assert_reconciled(drill)

    def test_boe_split_across_two_allocations_lists_both_and_counts_once(self):
        trade_a, line_a = self._sale(invoice="M-A", cif="100", qty="100")
        trade_b, line_b = self._sale(invoice="M-B", cif="150", qty="150")
        _boe, row = self._boe("M-1", cif="400", qty="400", trades=[trade_a, trade_b])
        self._allocate(row, line_a, "100", "100")
        self._allocate(row, line_b, "150", "150")
        drill = self.drill()
        matches = [r for r in self.boe_rows(drill) if r["boe_number"] == "M-1"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[0]["sale_links"]), 2)
        self.assertEqual(matches[0]["covered_cif"], "250.00")
        self.assertEqual(matches[0]["debited_cif"], "150.00")
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "150.00")
        self.assert_reconciled(drill)

    def test_previous_owner_boe_is_deducted_and_reported_as_its_own_debit(self):
        boe, _ = self._boe("H-1", cif="80", qty="80")
        BillOfEntryModel.objects.filter(pk=boe.pk).update(invoice_no="OTH")
        ReconciliationLog.objects.create(action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe)
        drill = self.drill()
        boe_row = self.row_for(drill, "H-1")
        self.assertEqual(boe_row["status"], PREVIOUS_OWNER_DEDUCTED)
        self.assertTrue(boe_row["previous_owner"])
        self.assertEqual(boe_row["debited_cif"], "80.00")
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "80.00")
        self.assertEqual(drill["boes"]["totals"]["previous_owner_debit_cif"], "80.00")
        self.assertEqual(drill["boes"]["totals"]["previous_owner_rows"], 1)
        self.assert_reconciled(drill)

    def test_boe_debiting_this_item_but_linked_to_another_items_sale_is_cross_item(self):
        other = self._item(self.licence, serial=2, qty="100.000", cif="100.00")
        trade, _ = self._sale(invoice="X-1", cif="50", qty="50", item=other)
        self._boe("X-B", cif="50", qty="50", trades=[trade])
        drill = self.drill()
        self.assertEqual(self.row_for(drill, "X-B")["status"], CROSS_ITEM_STATUS)
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "50.00")
        self.assert_reconciled(drill)

    def test_mts_unit_withholds_quantity_but_keeps_cif_reconciled(self):
        mts = self._item(self.licence, serial=2, qty="100.000", cif="100.00", unit="mts")
        self._boe("T-1", item=mts, cif="40", qty="40")
        drill = self.drill(item=mts)
        self.assertEqual(drill["item"]["unit_status"], UNIT_UNVERIFIED)
        self.assertEqual(drill["canonical"]["qty"], {})
        self.assertIsNone(drill["boes"]["totals"]["debited_qty"])
        self.assertIsNone(self.row_for(drill, "T-1")["boe_qty"])
        self.assertEqual({c["status"] for c in drill["reconciliation"]["qty"]}, {UNIT_UNVERIFIED})
        self.assertEqual(drill["reconciliation"]["status"], RECONCILED)


class AllotmentDrilldownTests(DrilldownFixture):
    def test_allotment_without_any_boe_is_unlinked_and_fully_outstanding(self):
        self._allotment(self.item, cif="100", qty="100")
        drill = self.drill()
        row = drill["allotments"]["rows"][0]
        self.assertEqual(row["status"], "UNLINKED")
        self.assertEqual(row["outstanding_cif"], "100.00")
        self.assertEqual(drill["allotments"]["totals"]["outstanding_cif"], "100.00")
        self.assert_reconciled(drill)

    def test_allotment_fully_covered_by_a_boe_on_this_item_is_linked(self):
        boe, _ = self._boe("L-1", cif="100", qty="100")
        self._allotment(self.item, cif="100", qty="100", boes=[boe])
        drill = self.drill()
        row = drill["allotments"]["rows"][0]
        self.assertEqual(row["status"], "LINKED")
        self.assertEqual(row["boe_linked_cif"], "100.00")
        self.assertEqual(row["outstanding_cif"], "0.00")
        self.assertTrue(row["linked_boes"][0]["on_this_item"])
        self.assert_reconciled(drill)

    def test_allotment_partly_covered_keeps_residue_outstanding(self):
        boe, _ = self._boe("P-1", cif="60", qty="60")
        self._allotment(self.item, cif="100", qty="100", boes=[boe])
        drill = self.drill()
        row = drill["allotments"]["rows"][0]
        self.assertEqual(row["status"], "PARTIALLY LINKED")
        self.assertEqual((row["original_cif"], row["boe_linked_cif"], row["outstanding_cif"]), ("100.00", "60.00", "40.00"))
        self.assertEqual(drill["allotments"]["totals"]["outstanding_cif"], "40.00")
        self.assert_reconciled(drill)

    def test_allotment_with_several_boes_lists_each_beneath_it(self):
        b1, _ = self._boe("W-1", cif="30", qty="30")
        b2, _ = self._boe("W-2", cif="20", qty="20")
        self._allotment(self.item, cif="100", qty="100", boes=[b1, b2])
        drill = self.drill()
        row = drill["allotments"]["rows"][0]
        self.assertEqual({b["boe_number"] for b in row["linked_boes"]}, {"W-1", "W-2"})
        self.assertEqual(row["boe_linked_cif"], "50.00")
        self.assertEqual(row["outstanding_cif"], "50.00")
        self.assert_reconciled(drill)

    def test_allotment_linked_to_a_boe_on_another_licence_needs_review(self):
        other_licence = self._licence("03" + str(uuid.uuid4().int)[:8])
        other_item = self._item(other_licence, serial=1, qty="10.000", cif="10.00")
        foreign, _ = self._boe("F-1", item=other_item, cif="30", qty="30")
        self._allotment(self.item, cif="100", qty="100", boes=[foreign])
        drill = self.drill()
        row = drill["allotments"]["rows"][0]
        self.assertEqual(row["status"], "REVIEW REQUIRED")
        self.assertEqual(row["outstanding_cif"], "100.00")
        self.assertFalse(row["linked_boes"][0]["on_this_item"])
        self.assertIn("A linked BOE does not debit this item", row["flags"])
        self.assert_reconciled(drill)

    def test_released_allotment_is_cancelled_and_excluded_from_outstanding(self):
        allotment = self._allotment(self.item, cif="50", qty="50")
        AllotmentItems.objects.filter(allotment=allotment).update(status="RELEASED")
        self._allotment(self.item, cif="100", qty="100")
        drill = self.drill()
        cancelled = [r for r in drill["allotments"]["rows"] if r["status"] == "CANCELLED"]
        self.assertEqual(len(cancelled), 1)
        self.assertEqual(drill["allotments"]["totals"]["cancelled_cif_excluded"], "50.00")
        self.assertEqual(drill["allotments"]["totals"]["outstanding_cif"], "100.00")
        self.assert_reconciled(drill)

    def test_invoice_link_is_reported_as_not_recorded_not_inferred(self):
        self._sale(invoice="IL-1", cif="100", qty="100")
        self._allotment(self.item, cif="100", qty="100")
        drill = self.drill()
        row = drill["allotments"]["rows"][0]
        self.assertIsNone(row["invoice_linked_cif"])
        self.assertIsNone(drill["allotments"]["totals"]["invoice_linked_cif"])
        self.assertIn(SALE_OVERLAP, row["flags"])

    def test_released_quantity_on_an_active_allotment_is_flagged_not_deducted(self):
        self._allotment(self.item, cif="100", qty="100")
        AllotmentItems.objects.filter(item=self.item).update(released_quantity=D("10"))
        drill = self.drill()
        row = drill["allotments"]["rows"][0]
        self.assertIn(RELEASE_RECORDED, row["flags"])
        self.assertEqual(row["outstanding_cif"], "100.00")


class InvoiceDrilldownTests(DrilldownFixture):
    def invoice(self, drill, number):
        return next(r for r in drill["invoices"]["rows"] if r["invoice_number"] == number)

    def test_sale_with_no_boe_is_not_linked_and_is_current_balance(self):
        self._sale(invoice="N-1", cif="100", qty="100")
        drill = self.drill()
        row = self.invoice(drill, "N-1")
        self.assertEqual(row["status"], "NOT LINKED")
        self.assertEqual((row["covered_by_boe_cif"], row["uncovered_cif"]), ("0.00", "100.00"))
        self.assertTrue(row["counts_in_current_balance"])
        self.assertEqual(row["current_balance_cif"], "100.00")
        self.assertEqual(drill["invoices"]["totals"]["sold_cif"], "100.00")
        self.assert_reconciled(drill)

    def test_sale_partly_covered_by_one_boe(self):
        trade, _ = self._sale(invoice="P-1", cif="500", qty="500")
        self._boe("PB-1", cif="200", qty="200", trades=[trade])
        drill = self.drill()
        row = self.invoice(drill, "P-1")
        self.assertEqual(row["status"], "PARTIALLY COVERED BY BOE")
        self.assertEqual((row["covered_by_boe_cif"], row["uncovered_cif"]), ("200.00", "300.00"))
        self.assertEqual(len(row["linked_boes"]), 1)
        self.assert_reconciled(drill)

    def test_sale_fully_covered_by_its_boe(self):
        trade, _ = self._sale(invoice="F-1", cif="190", qty="190")
        self._boe("FB-1", cif="190", qty="190", trades=[trade])
        drill = self.drill()
        self.assertEqual(self.invoice(drill, "F-1")["status"], "COVERED BY BOE")
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "0.00")
        self.assert_reconciled(drill)

    def test_sale_linked_to_several_boes_lists_each(self):
        trade, _ = self._sale(invoice="MB-1", cif="500", qty="500")
        self._boe("MB-A", cif="40", qty="40", trades=[trade])
        self._boe("MB-B", cif="50", qty="50", trades=[trade])
        drill = self.drill()
        row = self.invoice(drill, "MB-1")
        self.assertEqual({b["boe_number"] for b in row["linked_boes"]}, {"MB-A", "MB-B"})
        self.assertEqual(row["covered_by_boe_cif"], "90.00")
        self.assert_reconciled(drill)

    def test_boe_shared_by_two_invoices_is_listed_under_each_and_not_double_counted(self):
        trade_a, line_a = self._sale(invoice="SH-A", cif="100", qty="100")
        trade_b, line_b = self._sale(invoice="SH-B", cif="150", qty="150")
        _boe, row = self._boe("SH-1", cif="300", qty="300", trades=[trade_a, trade_b])
        self._allocate(row, line_a, "100", "100")
        self._allocate(row, line_b, "150", "150")
        drill = self.drill()
        self.assertEqual(self.invoice(drill, "SH-A")["linked_boes"][0]["boe_number"], "SH-1")
        self.assertEqual(self.invoice(drill, "SH-B")["linked_boes"][0]["boe_number"], "SH-1")
        self.assertEqual(drill["invoices"]["totals"]["sold_cif"], "250.00")
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "50.00")
        self.assert_reconciled(drill)

    def test_credit_note_on_the_sale_side_is_counted_and_flagged_not_netted(self):
        self._sale(invoice="CREDIT NOTE CN-1 LGL/1", cif="50", qty="50")
        drill = self.drill()
        row = self.invoice(drill, "CREDIT NOTE CN-1 LGL/1")
        self.assertEqual(row["document_type"], "CREDIT NOTE")
        self.assertEqual(row["referenced_invoice"], "CN-1 LGL/1")
        self.assertIn(NOTE_NOT_NETTED, row["flags"])
        self.assertEqual(drill["invoices"]["totals"]["sold_cif"], "50.00")
        self.assert_reconciled(drill)

    def test_debit_note_on_the_sale_side_is_counted_and_flagged_not_netted(self):
        self._sale(invoice="DEBIT NOTE DN-1 LGL/2", cif="25", qty="25")
        drill = self.drill()
        row = self.invoice(drill, "DEBIT NOTE DN-1 LGL/2")
        self.assertEqual(row["document_type"], "DEBIT NOTE")
        self.assertIn(NOTE_NOT_NETTED, row["flags"])
        self.assertEqual(drill["invoices"]["totals"]["sold_cif"], "25.00")

    def test_over_linked_invoice_shows_excess_counted_as_utilisation(self):
        trade, _ = self._sale(invoice="OV-1", cif="500", qty="500")
        self._boe("OV-A", cif="300", qty="300", trades=[trade])
        self._boe("OV-B", cif="300", qty="300", trades=[trade])
        drill = self.drill()
        row = self.invoice(drill, "OV-1")
        self.assertEqual(row["over_linked_cif"], "100.00")
        self.assertEqual(row["status"], "OVER-LINKED: excess counted as utilisation")
        self.assert_reconciled(drill)

    def test_linked_boe_that_debits_another_item_is_flagged_for_review(self):
        other = self._item(self.licence, serial=2, qty="100.000", cif="100.00")
        trade, _ = self._sale(invoice="RV-1", cif="50", qty="50")
        self._boe("RV-B", item=other, cif="50", qty="50", trades=[trade])
        drill = self.drill()
        row = self.invoice(drill, "RV-1")
        self.assertIn(LINKED_BOE_WITHOUT_DEBIT, row["flags"])
        self.assertEqual(row["boes_without_debit_on_item"][0]["boe_number"], "RV-B")

    def test_purchase_trades_are_not_listed_as_sales(self):
        self.purchase(invoice="PUR-1", cif="70", qty="70")
        self._sale(invoice="SAL-1", cif="10", qty="10")
        drill = self.drill()
        self.assertEqual([r["invoice_number"] for r in drill["invoices"]["rows"]], ["SAL-1"])
        self.assertEqual(drill["invoices"]["totals"]["sold_cif"], "10.00")


class InvoiceQuantityTotalsTests(DrilldownFixture):
    def test_invoice_totals_carry_quantity_next_to_cif(self):
        trade, _ = self._sale(invoice="IQ-1", cif="500", qty="500")
        self._boe("IQ-B", cif="200", qty="200", trades=[trade])
        totals = self.drill()["invoices"]["totals"]
        self.assertEqual(
            (totals["sold_qty"], totals["covered_by_boe_qty"], totals["uncovered_qty"], totals["over_linked_qty"]),
            ("500.000", "200.000", "300.000", "0.000"),
        )


class ConsistencyTests(DrilldownFixture):
    def build_mixed_item(self):
        trade_a, _ = self._sale(invoice="MX-A", cif="500", qty="500")
        self._sale(invoice="MX-B", cif="100", qty="100")
        self._boe("MX-1", cif="190", qty="190", trades=[trade_a])
        self._boe("MX-2", cif="300", qty="300", trades=[trade_a])
        self._boe("MX-3", cif="30", qty="30")
        boe, _ = self._boe("MX-4", cif="60", qty="60")
        self._allotment(self.item, cif="80", qty="80", boes=[boe])
        self._allotment(self.item, cif="20", qty="20")

    def test_drawer_totals_equal_item_table_figures(self):
        self.build_mixed_item()
        drill = self.drill()
        canonical = drill["canonical"]["cif"]
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], canonical["debited"])
        self.assertEqual(drill["allotments"]["totals"]["outstanding_cif"], canonical["allotted"])
        self.assertEqual(drill["invoices"]["totals"]["sold_cif"], canonical["invoiced"])
        self.assertEqual(drill["item"]["original_cif"], "1000.00")
        self.assert_reconciled(drill)
        self.assertTrue(all(c["status"] == RECONCILED for c in drill["reconciliation"]["cif"]))

    def test_item_totals_add_up_to_the_licence_summary(self):
        self.build_mixed_item()
        second = self._item(self.licence, serial=2, qty="200.000", cif="200.00")
        self._boe("SUM-1", item=second, cif="45", qty="45")
        licence_summary = build_licence_balance_reports([self.licence.id], include_legacy=False)[self.licence.id].summary_cif
        debited = sum((Decimal(self.drill(item=i)["boes"]["totals"]["debited_cif"]) for i in (self.item, second)), D("0"))
        allotted = sum((Decimal(self.drill(item=i)["allotments"]["totals"]["outstanding_cif"]) for i in (self.item, second)), D("0"))
        invoiced = sum((Decimal(self.drill(item=i)["invoices"]["totals"]["sold_cif"]) for i in (self.item, second)), D("0"))
        self.assertEqual(format(debited, "f"), licence_summary["debited"])
        self.assertEqual(format(allotted, "f"), licence_summary["allotted"])
        self.assertEqual(format(invoiced, "f"), licence_summary["invoiced"])

    def test_cif_and_quantity_are_independent(self):
        trade, _ = self._sale(invoice="IND-1", cif="100", qty="40")
        self._boe("IND-B", cif="150", qty="60", trades=[trade])
        drill = self.drill()
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "50.00")
        self.assertEqual(drill["boes"]["totals"]["debited_qty"], "20.000")
        self.assertEqual(drill["invoices"]["totals"]["sold_qty"], "40.000")
        self.assert_reconciled(drill)

    def test_money_and_quantity_are_returned_as_strings_or_none(self):
        self.build_mixed_item()
        drill = self.drill()
        for group in ("boes", "allotments", "invoices"):
            for key, value in drill[group]["totals"].items():
                if key.endswith("_rows"):
                    self.assertIsInstance(value, int, (group, key))
                    continue
                self.assertTrue(value is None or isinstance(value, str), (group, key, value))
            for row in drill[group]["rows"]:
                for key, value in row.items():
                    if key.endswith(("_cif", "_qty", "_inr")):
                        self.assertTrue(value is None or isinstance(value, str), (group, key, value))

    def test_boe_statuses_match_the_transactions_endpoint(self):
        self.build_mixed_item()
        drill = self.drill()
        tx = build_licence_transactions(self.licence.id)
        expected = {(b["boe_number"], b["status"]) for b in tx["boes"] if b["item_id"] == self.item.id}
        actual = {(r["boe_number"], r["status"]) for r in self.boe_rows(drill)}
        self.assertEqual(actual, expected)

    def test_reconciliation_flags_a_difference_and_passes_equal_figures(self):
        self.assertEqual(_check("debited", D("10.004"), D("10.00"), "cif")["status"], RECONCILED)
        self.assertEqual(_check("debited", D("10.00"), D("9.99"), "cif")["status"], MISMATCH)
        self.assertEqual(_check("debited", D("10.00"), None, "cif")["status"], "NOT COMPUTED")

    def test_half_up_rounding_matches_the_canonical_engine(self):
        # 0.005 rounds up to 0.01 in the canonical engine (ROUND_HALF_UP); the drill-down must agree.
        self.assertEqual(_check("debited", D("0.005"), D("0.01"), "cif")["status"], RECONCILED)

    def test_unknown_item_on_this_licence_returns_none(self):
        other = self._licence("03" + str(uuid.uuid4().int)[:8])
        foreign = self._item(other, serial=1, qty="1.000", cif="1.00")
        self.assertIsNone(build_item_drilldown(self.licence.id, foreign.id))
        self.assertIsNone(build_item_drilldown(self.licence.id, 987654321))


class DrilldownApiTests(DrilldownFixture):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username="lm-" + uuid.uuid4().hex[:6], password="x")
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def url(self, item=None):
        return f"/api/licence-balances/{self.licence.id}/items/{(item or self.item).id}/drilldown/"

    def test_endpoint_returns_three_groups_and_a_reconciliation(self):
        trade, _ = self._sale(invoice="API-1", cif="100", qty="100")
        self._boe("API-B", cif="40", qty="40", trades=[trade])
        self._allotment(self.item, cif="20", qty="20")
        response = self.api.get(self.url())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual({"boes", "allotments", "invoices", "reconciliation"} - set(body), set())
        self.assertEqual(body["reconciliation"]["status"], RECONCILED)
        self.assertEqual(body["invoices"]["totals"]["sold_cif"], "100.00")

    def test_unknown_item_is_404(self):
        self.assertEqual(self.api.get(f"/api/licence-balances/{self.licence.id}/items/987654321/drilldown/").status_code, 404)

    def test_user_without_a_licence_role_is_refused(self):
        outsider = get_user_model().objects.create_user(username="out-" + uuid.uuid4().hex[:6], password="x")
        client = APIClient()
        client.force_authenticate(outsider)
        self.assertEqual(client.get(self.url()).status_code, 403)

    def test_endpoint_refuses_writes_for_a_viewer(self):
        # LicensePermission allows only safe methods for read roles, so writes are refused before any handler runs.
        self.assertIn(self.api.post(self.url(), {}).status_code, (403, 405))
        self.assertIn(self.api.delete(self.url()).status_code, (403, 405))
