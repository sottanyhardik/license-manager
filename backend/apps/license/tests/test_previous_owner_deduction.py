"""Previous-owner BOEs reduce the current licence's Available CIF and Available quantity.

Ownership is identified only by the BOE hide/restore audit trail (`ReconciliationLog`), never by
importer name or BOE date. Each debit is deducted once, even where a sale, an allocation row and an
allotment all touch the same BOE. Builds real rows through the report fixture.
"""

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.bill_of_entry.models import BillOfEntryModel
from apps.license.services.licence_balance_report import (
    PREVIOUS_OWNER_COVERED,
    PREVIOUS_OWNER_DEDUCTED,
    PREVIOUS_OWNER_PARTLY,
    build_licence_transactions,
)
from apps.license.services.licence_item_balance import RECONCILED
from apps.license.services.licence_item_drilldown import EXCESS_KIND, build_item_drilldown
from apps.license.tests import test_licence_balance_report as base
from apps.reconciliation.models import ReconciliationLog

D = Decimal


class PreviousOwnerFixture(base.ReportFixture):
    def mark_previous_owner(self, boe):
        """The audit trail that the app writes when a BOE is hidden as previous-owner usage."""
        BillOfEntryModel.objects.filter(pk=boe.pk).update(invoice_no="OTH")
        ReconciliationLog.objects.create(action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe)

    def previous_owner_boe(self, number, *, cif, qty, trades=()):
        boe, row = self._boe(number, cif=cif, qty=qty, trades=trades)
        self.mark_previous_owner(boe)
        return boe, row

    def drill(self):
        return build_item_drilldown(self.licence.id, self.item.id)

    def row(self, drill, number):
        return next(r for r in drill["boes"]["rows"] if r["kind"] == "BOE" and r["boe_number"] == number)


class AvailableBalanceTests(PreviousOwnerFixture):
    def test_previous_owner_boe_reduces_available_cif(self):
        self.previous_owner_boe("PO-1", cif="200", qty="200")
        item = self.item_report(self.report())
        self.assertEqual(item.cif["debited"], "200.00")
        self.assertEqual(item.cif["available"], "800.00")
        self.assertEqual(item.previous_owner_debit_cif, D("200.00"))

    def test_previous_owner_boe_reduces_available_quantity(self):
        self.previous_owner_boe("PO-2", cif="200", qty="200")
        item = self.item_report(self.report())
        self.assertEqual(item.qty["debited"], "200.000")
        self.assertEqual(item.qty["available"], "800.000")
        self.assertEqual(item.previous_owner_debit_qty, D("200.000"))

    def test_previous_owner_and_current_owner_debits_add_into_debited(self):
        self.previous_owner_boe("PO-3", cif="200", qty="200")
        self._boe("CUR-3", cif="50", qty="50")
        drill = self.drill()
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "250.00")
        self.assertEqual(drill["boes"]["totals"]["previous_owner_debit_cif"], "200.00")
        self.assertEqual(drill["boes"]["totals"]["uncovered_cif"], "50.00")
        self.assertEqual(drill["canonical"]["cif"]["available"], "750.00")

    def test_licence_summary_reports_the_previous_owner_debit_separately(self):
        self.previous_owner_boe("PO-4", cif="200", qty="200")
        report = self.report()
        self.assertEqual(report.previous_owner_debit_cif, D("200.00"))
        self.assertEqual(report.previous_owner_debit_qty, D("200.000"))
        self.assertEqual(report.summary_cif["available"], "800.00")


class DuplicateDeductionTests(PreviousOwnerFixture):
    def test_previous_owner_boe_covered_by_a_sale_is_not_deducted_again(self):
        trade, _ = self._sale(invoice="PO-S1", cif="200", qty="200")
        self.previous_owner_boe("PO-5", cif="200", qty="200", trades=[trade])
        drill = self.drill()
        row = self.row(drill, "PO-5")
        self.assertEqual(row["status"], PREVIOUS_OWNER_COVERED)
        self.assertEqual(drill["boes"]["totals"]["previous_owner_debit_cif"], "0.00")
        # The sale is deducted once, as invoiced; the covered BOE adds nothing on top.
        self.assertEqual(drill["canonical"]["cif"]["available"], "800.00")
        self.assertEqual(drill["invoices"]["totals"]["sold_cif"], "200.00")

    def test_partly_covered_previous_owner_boe_deducts_only_the_uncovered_part(self):
        trade, line = self._sale(invoice="PO-S2", cif="100", qty="100")
        _boe, row = self.previous_owner_boe("PO-6", cif="300", qty="300", trades=[trade])
        self._allocate(row, line, "100", "100")
        drill = self.drill()
        boe = self.row(drill, "PO-6")
        self.assertEqual(boe["status"], PREVIOUS_OWNER_PARTLY)
        self.assertEqual((boe["covered_cif"], boe["debited_cif"]), ("100.00", "200.00"))
        self.assertEqual(drill["boes"]["totals"]["previous_owner_debit_cif"], "200.00")
        self.assertEqual(drill["canonical"]["cif"]["available"], "700.00")

    def test_previous_owner_boe_on_an_allotment_is_counted_once(self):
        boe, _ = self.previous_owner_boe("PO-7", cif="60", qty="60")
        self._allotment(self.item, cif="100", qty="100", boes=[boe])
        drill = self.drill()
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "60.00")
        self.assertEqual(drill["allotments"]["totals"]["outstanding_cif"], "0.00")
        # 1000 - 60 (BOE). The allotment's 40 difference is ignored. Not 1000 - 60 - 100, not 1000 - 60 - 40.
        self.assertEqual(drill["canonical"]["cif"]["available"], "940.00")
        self.assertEqual(drill["reconciliation"]["status"], RECONCILED)

    def test_overlap_of_sale_allocation_and_allotment_deducts_each_part_once(self):
        trade, line = self._sale(invoice="PO-S3", cif="100", qty="100")
        boe, row = self.previous_owner_boe("PO-8", cif="300", qty="300", trades=[trade])
        self._allocate(row, line, "100", "100")
        self._allotment(self.item, cif="100", qty="100", boes=[boe])
        drill = self.drill()
        # Uncovered BOE part 200 (debited), sale 100 (invoiced), allotment fully consumed by the BOE on this item.
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "200.00")
        self.assertEqual(drill["invoices"]["totals"]["sold_cif"], "100.00")
        self.assertEqual(drill["allotments"]["totals"]["outstanding_cif"], "0.00")
        self.assertEqual(drill["canonical"]["cif"]["available"], "700.00")
        self.assertEqual(drill["reconciliation"]["status"], RECONCILED)


class OverLinkedOwnershipTests(PreviousOwnerFixture):
    def test_excess_of_a_sale_linked_only_to_previous_owner_boes_is_previous_owner_debit(self):
        trade, _ = self._sale(invoice="OX-1", cif="100", qty="100")
        self.previous_owner_boe("OX-A", cif="300", qty="300", trades=[trade])
        drill = self.drill()
        excess = [r for r in drill["boes"]["rows"] if r["kind"] == EXCESS_KIND][0]
        self.assertTrue(excess["previous_owner"])
        self.assertEqual(drill["boes"]["totals"]["previous_owner_debit_cif"], "200.00")
        self.assertEqual(drill["boes"]["totals"]["over_linked_cif"], "0.00")
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "200.00")
        # The BOE (300) is deducted once in total: 100 as the invoiced sale plus 200 as excess debit.
        self.assertEqual(drill["canonical"]["cif"]["available"], "700.00")
        item = self.item_report(self.report())
        self.assertEqual(item.previous_owner_debit_cif, D("200.00"))
        self.assertNotIn("OVER_LINKED_MIXED_OWNERSHIP", item.flags)

    def test_excess_of_a_sale_with_mixed_owner_boes_is_not_attributed_and_is_flagged(self):
        trade, _ = self._sale(invoice="OX-2", cif="100", qty="100")
        self.previous_owner_boe("OX-B", cif="150", qty="150", trades=[trade])
        self._boe("OX-C", cif="150", qty="150", trades=[trade])
        drill = self.drill()
        excess = [r for r in drill["boes"]["rows"] if r["kind"] == EXCESS_KIND][0]
        self.assertFalse(excess["previous_owner"])
        self.assertIn("OVER_LINKED_MIXED_OWNERSHIP", excess["flags"][0])
        self.assertEqual(drill["boes"]["totals"]["previous_owner_debit_cif"], "0.00")
        self.assertEqual(drill["boes"]["totals"]["over_linked_cif"], "200.00")
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], "200.00")
        item = self.item_report(self.report())
        self.assertIn("OVER_LINKED_MIXED_OWNERSHIP", item.flags)
        self.assertEqual(item.cif["debited"], "200.00")


class IdentificationTests(PreviousOwnerFixture):
    def test_boe_marked_oth_without_a_hide_record_is_a_current_owner_boe(self):
        boe, _ = self._boe("OTH-1", cif="200", qty="200")
        BillOfEntryModel.objects.filter(pk=boe.pk).update(invoice_no="OTH")
        drill = self.drill()
        row = self.row(drill, "OTH-1")
        self.assertFalse(row["previous_owner"])
        self.assertEqual(row["status"], "UNCOVERED")
        self.assertEqual(drill["boes"]["totals"]["previous_owner_debit_cif"], "0.00")
        self.assertEqual(drill["boes"]["totals"]["uncovered_cif"], "200.00")

    def test_restored_boe_is_a_current_owner_boe(self):
        boe, _ = self._boe("RST-1", cif="200", qty="200")
        BillOfEntryModel.objects.filter(pk=boe.pk).update(invoice_no="OTH")
        ReconciliationLog.objects.create(action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe)
        ReconciliationLog.objects.create(action=ReconciliationLog.ACTION_RESTORE_BOE, bill_of_entry=boe)
        drill = self.drill()
        self.assertFalse(self.row(drill, "RST-1")["previous_owner"])
        self.assertEqual(drill["boes"]["totals"]["uncovered_cif"], "200.00")

    def test_an_older_date_or_a_foreign_importer_name_alone_does_not_make_a_previous_owner(self):
        boe, _ = self._boe("DT-1", cif="70", qty="70")
        BillOfEntryModel.objects.filter(pk=boe.pk).update(bill_of_entry_date=date(2015, 1, 1), company=self.seller)
        drill = self.drill()
        self.assertFalse(self.row(drill, "DT-1")["previous_owner"])
        self.assertEqual(drill["boes"]["totals"]["previous_owner_rows"], 0)


class PresentationTests(PreviousOwnerFixture):
    def test_boe_detail_shows_quantity_and_cif_for_the_previous_owner_boe(self):
        self.previous_owner_boe("PRS-1", cif="200", qty="180")
        row = self.row(self.drill(), "PRS-1")
        self.assertEqual(row["status"], PREVIOUS_OWNER_DEDUCTED)
        self.assertTrue(row["previous_owner"])
        self.assertEqual((row["boe_qty"], row["boe_cif"]), ("180.000", "200.00"))
        self.assertEqual((row["debited_qty"], row["debited_cif"]), ("180.000", "200.00"))

    def test_the_item_debit_breakdown_includes_the_previous_owner_boe(self):
        self.previous_owner_boe("PRS-2", cif="200", qty="200")
        drill = self.drill()
        self.assertIn("PRS-2", [r["boe_number"] for r in drill["boes"]["rows"]])
        self.assertEqual(drill["boes"]["totals"]["debited_cif"], drill["canonical"]["cif"]["debited"])
        self.assertEqual(drill["boes"]["totals"]["debited_qty"], drill["canonical"]["qty"]["debited"])

    def test_available_reconciles_exactly_with_the_canonical_calculation(self):
        trade, _ = self._sale(invoice="PRS-S", cif="150", qty="150")
        self.previous_owner_boe("PRS-3", cif="200", qty="200")
        self._boe("PRS-4", cif="30", qty="30")
        self._allotment(self.item, cif="20", qty="20")
        drill = self.drill()
        self.assertEqual(drill["reconciliation"]["status"], RECONCILED)
        cif = drill["canonical"]["cif"]
        original = D("1000.00")
        self.assertEqual(
            original - D(drill["boes"]["totals"]["debited_cif"]) - D(drill["allotments"]["totals"]["outstanding_cif"]) - D(drill["invoices"]["totals"]["sold_cif"]),
            D(cif["available"]),
        )
        qty = drill["canonical"]["qty"]
        self.assertEqual(D(qty["available"]), D("1000.000") - D(drill["boes"]["totals"]["debited_qty"]) - D(drill["allotments"]["totals"]["outstanding_qty"]) - D(drill["invoices"]["totals"]["sold_qty"]))

    def test_transactions_endpoint_labels_the_previous_owner_boe(self):
        self.previous_owner_boe("PRS-5", cif="200", qty="200")
        boes = [b for b in build_licence_transactions(self.licence.id)["boes"] if b["boe_number"] == "PRS-5"]
        self.assertEqual(boes[0]["status"], PREVIOUS_OWNER_DEDUCTED)
        self.assertTrue(boes[0]["previous_owner"])

    def test_ledger_has_a_previous_owner_debit_and_ends_at_available(self):
        self.previous_owner_boe("PRS-6", cif="200", qty="200")
        item = self.item_report(self.report())
        debit = [r for r in item.cif_ledger if r.kind == "BOE_DEBIT"]
        self.assertEqual(len(debit), 1)
        self.assertTrue(debit[0].previous_owner)
        live = [r for r in item.cif_ledger if not r.memo]
        self.assertEqual(live[-1].running_balance, D(item.cif["available"]))

    def test_drilldown_endpoint_exposes_the_previous_owner_fields(self):
        self.previous_owner_boe("PRS-7", cif="200", qty="200")
        user = get_user_model().objects.create_user(username="po-" + uuid.uuid4().hex[:6], password="x")
        user.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        client = APIClient()
        client.force_authenticate(user)
        response = client.get(f"/api/licence-balances/{self.licence.id}/items/{self.item.id}/drilldown/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["boes"]["totals"]["previous_owner_debit_cif"], "200.00")
        self.assertEqual(body["boes"]["totals"]["previous_owner_debit_qty"], "200.000")
        self.assertTrue(next(r for r in body["boes"]["rows"] if r["boe_number"] == "PRS-7")["previous_owner"])
