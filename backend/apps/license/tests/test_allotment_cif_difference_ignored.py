"""Allotment CIF difference is ignored for every licence balance purpose.

The difference between an allotment's original CIF and the valid, current BOE-linked CIF on its item is
not utilisation, not reservation, not outstanding, not a debit, and not a review trigger. Only the valid
BOE-linked CIF counts. Quantity keeps its own rule and is not derived from CIF.

Regression values (SR 3, Vegetable Shortening, licence 0311051362):
  Original allotment CIF 14,900.36 (ALLOT-7186 14,060.20 + ALLOT-7297 840.16)
  Valid BOE-linked CIF   14,838.57 (14,001.17 + 837.40)
  Difference                61.79   (ignored)
  CIF counted in utilisation 14,838.57
"""

import uuid
from decimal import Decimal

from apps.allotment.models import AllotmentItems
from apps.license.models import LicenseDetailsModel
from apps.license.services.licence_balance_report import build_licence_balance_reports, serialise_licence_summary
from apps.license.tests.test_licence_item_drilldown import DrilldownFixture
from apps.reconciliation.models import InvoiceBOEAllocation

D = Decimal


class AllotmentDifferenceIgnoredTests(DrilldownFixture):
    def setUp(self):
        super().setUp()
        # A fresh item, so the amounts are exactly the regression values.
        self.sr3 = self._item(self.licence, serial=3, qty="12332.180", cif="20000.00")

    def _mode(self, value):
        LicenseDetailsModel.objects.filter(pk=self.licence.pk).update(individual_item_cif_override=value)

    def _two_allotments_linked(self):
        b_a, _ = self._boe("ALLOT-A-BOE", item=self.sr3, cif="14001.17", qty="11620")
        b_b, _ = self._boe("ALLOT-B-BOE", item=self.sr3, cif="837.40", qty="712")
        self._allotment(self.sr3, cif="14060.20", qty="11620", boes=[b_a])
        self._allotment(self.sr3, cif="840.16", qty="712", boes=[b_b])

    def _item_report(self):
        report = build_licence_balance_reports([self.licence.id], include_legacy=False)[self.licence.id]
        return report, self.item_report(report, item=self.sr3)

    # 1. Exact regression -----------------------------------------------------

    def test_difference_of_61_79_is_completely_ignored(self):
        self._two_allotments_linked()

        report, item = self._item_report()

        # Only the valid BOE-linked CIF counts: 14,838.57. The 61.79 is not reserved, not outstanding, not a debit.
        self.assertEqual(item.cif["debited"], "14838.57")
        self.assertEqual(item.cif["allotted"], "0.00")
        self.assertEqual(item.cif["invoiced"], "0.00")
        self.assertEqual(item.cif["available"], "5161.43")

    def test_drawer_shows_original_and_boe_linked_but_no_outstanding_difference(self):
        self._two_allotments_linked()

        drill = self.drill(item=self.sr3)
        rows = {r["reference"]: r for r in drill["allotments"]["rows"]}

        self.assertEqual(rows[next(k for k in rows if rows[k]["original_cif"] == "14060.20")]["boe_linked_cif"], "14001.17")
        self.assertEqual(rows[next(k for k in rows if rows[k]["original_cif"] == "840.16")]["boe_linked_cif"], "837.40")
        totals = drill["allotments"]["totals"]
        self.assertEqual(totals["original_cif"], "14900.36")
        self.assertEqual(totals["boe_linked_cif"], "14838.57")
        self.assertEqual(totals["outstanding_cif"], "0.00")
        for row in drill["allotments"]["rows"]:
            self.assertEqual(row["outstanding_cif"], "0.00")
            self.assertEqual(row["status"], "LINKED")
            self.assertNotIn("PARTIALLY LINKED", row["status"])
        self.assert_reconciled(drill)

    # 2. Only valid BOE-linked CIF counts; nothing is reserved or debited for the difference

    def test_difference_creates_no_reservation_or_debit_entry(self):
        self._two_allotments_linked()

        report, item = self._item_report()
        drill = self.drill(item=self.sr3)

        self.assertFalse(any(m.kind == "ALLOTMENT" for m in item.cif_ledger))
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "14838.57")
        self.assertEqual(drill["allotments"]["totals"]["outstanding_cif"], "0.00")
        self.assertNotIn("ALLOT_AND_SALE_OVERLAP_UNVERIFIED", item.flags)

    def test_difference_does_not_reduce_available_licence_cif(self):
        self._two_allotments_linked()
        for value in (None, True):
            self._mode(value)
            report = build_licence_balance_reports([self.licence.id], include_legacy=False)[self.licence.id]
            # 20,000 + 1,000 (the setUp item) - 14,838.57 - nothing for the 61.79 difference.
            self.assertEqual(report.summary_cif["available"], "6161.43", f"override={value}")

    def test_difference_does_not_trigger_a_reconciliation_or_review_status(self):
        self._two_allotments_linked()

        _report, item = self._item_report()
        drill = self.drill(item=self.sr3)

        self.assertEqual(drill["reconciliation"]["status"], "RECONCILED", drill["reconciliation"])
        self.assertNotIn("ALLOT_AND_SALE_OVERLAP_UNVERIFIED", item.flags)
        self.assertEqual(item.cif["status"], "LICENCE-LEVEL CONTROL")

    # 3. Aggregation, exclusions and double counting -----------------------

    def test_multiple_allotments_aggregate_their_boe_linked_cif_only(self):
        self._two_allotments_linked()

        drill = self.drill(item=self.sr3)
        totals = drill["allotments"]["totals"]

        self.assertEqual(totals["boe_linked_cif"], "14838.57")
        self.assertEqual(totals["outstanding_cif"], "0.00")
        self.assertEqual(totals["original_cif"], "14900.36")

    def test_invoice_and_boe_are_counted_once_when_the_boe_is_sold(self):
        self._two_allotments_linked()
        trade, _line = self._sale(invoice="SR3-SALE", cif="14838.57", qty="12332.000", item=self.sr3)
        for boe in self._boes_on(self.sr3):
            trade.boes.add(boe)

        _report, item = self._item_report()

        # Covered by the sale, so the sale is the single count. The allotments add nothing on top.
        self.assertEqual(item.cif["invoiced"], "14838.57")
        self.assertEqual(item.cif["debited"], "0.00")
        self.assertEqual(item.cif["allotted"], "0.00")
        self.assertEqual(item.cif["available"], "5161.43")

    def test_superseded_boe_allocation_is_excluded(self):
        boe, row = self._boe("SUP-BOE", item=self.sr3, cif="100", qty="100")
        trade, line = self._sale(invoice="SUP-SALE", cif="100", qty="100", item=self.sr3)
        trade.boes.add(boe)  # the BOE must belong to the sale before an allocation can link it
        self._allocate(row, line, "100", "100")
        # A superseded allocation for the same row and line must not count.
        InvoiceBOEAllocation.objects.create(
            row_details=row, trade_line=line, allocated_cif_fc=D("999"), allocated_cif_inr=D("999") * D("84.5"),
            allocated_qty=D("999"), status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=False,
        )

        _report, item = self._item_report()

        self.assertEqual(item.cif["invoiced_boe_covered"], "100.00")
        self.assertEqual(item.cif["debited"], "0.00")

    def test_cancelled_allotment_is_excluded_from_every_figure(self):
        self._two_allotments_linked()
        self._allotment(self.sr3, cif="500.00", qty="500")
        AllotmentItems.objects.filter(item=self.sr3, cif_fc=D("500.00")).update(status="RELEASED")

        report, item = self._item_report()
        drill = self.drill(item=self.sr3)

        self.assertEqual(item.cif["allotted"], "0.00")
        self.assertEqual(drill["allotments"]["totals"]["cancelled_cif_excluded"], "500.00")
        self.assertEqual(drill["allotments"]["totals"]["outstanding_cif"], "0.00")

    # 4. Rules that are not this difference stay unchanged ----------------

    def test_unlinked_allotment_is_still_a_full_reservation(self):
        # No BOE link at all: the whole allotment is reserved (D-1). The difference rule does not apply.
        self._allotment(self.sr3, cif="500.00", qty="500")

        _report, item = self._item_report()

        self.assertEqual(item.cif["allotted"], "500.00")

    def test_boe_linked_on_another_licence_still_needs_review(self):
        other_licence = self._licence("03" + str(uuid.uuid4().int)[:8])
        other_item = self._item(other_licence, serial=1, qty="10.000", cif="10.00")
        foreign, _ = self._boe("FOREIGN-SR3", item=other_item, cif="30", qty="30")
        self._allotment(self.sr3, cif="100", qty="100", boes=[foreign])

        drill = self.drill(item=self.sr3)
        row = drill["allotments"]["rows"][-1]

        self.assertEqual(row["status"], "REVIEW REQUIRED")
        self.assertEqual(row["outstanding_cif"], "100.00")

    # 5. One calculation: balance, drawer and licence agree ---------------

    def test_item_balance_drawer_and_licence_agree(self):
        self._two_allotments_linked()

        report, item = self._item_report()
        drill = self.drill(item=self.sr3)
        summary = serialise_licence_summary(report)

        self.assertEqual(item.cif["allotted"], drill["allotments"]["totals"]["outstanding_cif"])
        self.assertEqual(item.cif["debited"], drill["boes"]["totals"]["debited_cif"])
        self.assertEqual(drill["canonical"]["cif"]["available"], item.cif["available"])
        # The licence total is the sum of its items, and the difference contributes nothing to it.
        self.assertEqual(D(summary["cif"]["allotted"]), sum((D(i.cif["allotted"]) for i in report.items), D("0")))
        self.assertEqual(summary["cif"]["allotted"], "0.00")

    def _boes_on(self, item):
        from apps.bill_of_entry.models import BillOfEntryModel, RowDetails

        ids = RowDetails.objects.filter(sr_number=item, transaction_type="D").values_list("bill_of_entry_id", flat=True)
        return BillOfEntryModel.objects.filter(id__in=ids)
