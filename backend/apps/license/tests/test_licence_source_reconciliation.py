"""Licence-wide source reconciliation: per-item differences and allocation issues.

Built from the same per-item drill-downs as the item view, so the endpoint cannot disagree with
the Items & Balance drawers. Builds real rows through the report fixture.
"""

import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.license.services.licence_balance_report import build_licence_transactions
from apps.license.services.licence_item_drilldown import build_licence_source_reconciliation
from apps.license.tests import test_licence_balance_report as base


class SourceReconciliationFixture(base.ReportFixture):
    def items_by_sr(self, payload):
        return {i["sr"]: i for i in payload["items"]}


class SourceReconciliationTests(SourceReconciliationFixture):
    def test_clean_item_reconciles_with_no_issues(self):
        trade, _ = self._sale(invoice="CLEAN-1", cif="200", qty="200")
        self._boe("CLEAN-B", cif="200", qty="200", trades=[trade])
        payload = build_licence_source_reconciliation(self.licence.id)
        item = self.items_by_sr(payload)["1"]
        self.assertEqual(item["reconciliation"]["status"], "RECONCILED")
        self.assertEqual(item["issues"], [])
        self.assertEqual(payload["items_not_reconciled"], 0)
        self.assertEqual(payload["issue_count"], 0)

    def test_cross_item_boe_is_an_allocation_issue_with_quantity_and_cif(self):
        other = self._item(self.licence, serial=2, qty="100.000", cif="100.00")
        trade, _ = self._sale(invoice="X-1", cif="50", qty="50", item=other)
        self._boe("X-B", cif="50", qty="50", trades=[trade])
        payload = build_licence_source_reconciliation(self.licence.id)
        issues = self.items_by_sr(payload)["1"]["issues"]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["kind"], "BOE")
        self.assertEqual(issues[0]["reference"], "X-B")
        self.assertEqual(issues[0]["amount"], {"qty": "50.000", "cif": "50.00"})
        self.assertEqual(issues[0]["status"], "LINKED TO ANOTHER ITEM'S SALE (review)")

    def test_over_linked_sale_reports_the_boes_and_the_invoice(self):
        trade, _ = self._sale(invoice="OV-1", cif="500", qty="500")
        self._boe("OV-A", cif="300", qty="300", trades=[trade])
        self._boe("OV-B", cif="300", qty="300", trades=[trade])
        issues = self.items_by_sr(build_licence_source_reconciliation(self.licence.id))["1"]["issues"]
        kinds = sorted(i["kind"] for i in issues)
        self.assertEqual(kinds, ["BOE", "BOE", "INVOICE"])
        invoice = next(i for i in issues if i["kind"] == "INVOICE")
        self.assertEqual(invoice["reference"], "OV-1")
        self.assertEqual(invoice["amount"], {"qty": "500.000", "cif": "500.00"})

    def test_excess_of_mixed_owner_boes_is_flagged_for_review(self):
        trade, _ = self._sale(invoice="MX-1", cif="100", qty="100")
        boe, _ = self._boe("MX-A", cif="150", qty="150", trades=[trade])
        from apps.bill_of_entry.models import BillOfEntryModel
        from apps.reconciliation.models import ReconciliationLog

        BillOfEntryModel.objects.filter(pk=boe.pk).update(invoice_no="OTH")
        ReconciliationLog.objects.create(action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe)
        self._boe("MX-B", cif="150", qty="150", trades=[trade])
        issues = self.items_by_sr(build_licence_source_reconciliation(self.licence.id))["1"]["issues"]
        excess = [i for i in issues if i["reference"].startswith("Excess on")]
        self.assertEqual(len(excess), 1)
        self.assertTrue(any("MIXED" in flag for flag in excess[0]["flags"]))

    def test_allotment_linked_to_a_boe_on_another_licence_is_an_issue(self):
        other_licence = self._licence("03" + str(uuid.uuid4().int)[:8])
        other_item = self._item(other_licence, serial=1, qty="10.000", cif="10.00")
        foreign, _ = self._boe("FOR-1", item=other_item, cif="30", qty="30")
        self._allotment(self.item, cif="100", qty="100", boes=[foreign])
        issues = self.items_by_sr(build_licence_source_reconciliation(self.licence.id))["1"]["issues"]
        allotment = [i for i in issues if i["kind"] == "ALLOTMENT"]
        self.assertEqual(len(allotment), 1)
        self.assertEqual(allotment[0]["status"], "REVIEW REQUIRED")
        self.assertEqual(allotment[0]["amount"], {"qty": "100.000", "cif": "100.00"})

    def test_item_reconciliation_matches_the_item_drilldown(self):
        trade, _ = self._sale(invoice="M-1", cif="300", qty="300")
        self._boe("M-B", cif="120", qty="120", trades=[trade])
        self._allotment(self.item, cif="50", qty="50")
        payload = build_licence_source_reconciliation(self.licence.id)
        row = self.items_by_sr(payload)["1"]
        self.assertEqual(row["reconciliation"]["status"], "RECONCILED")
        self.assertEqual(row["canonical_status"], self.item_report(self.report()).status)


class SourceReconciliationApiTests(SourceReconciliationFixture):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username="sr-" + uuid.uuid4().hex[:6], password="x")
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_endpoint_returns_the_reconciliation_for_each_item(self):
        self._sale(invoice="E-1", cif="100", qty="100")
        response = self.api.get(f"/api/licence-balances/{self.licence.id}/source-reconciliation/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["license_id"], self.licence.id)
        self.assertEqual(body["items"][0]["reconciliation"]["status"], "RECONCILED")
        self.assertIn("issues", body["items"][0])

    def test_unknown_licence_is_404(self):
        self.assertEqual(self.api.get("/api/licence-balances/987654321/source-reconciliation/").status_code, 404)

    def test_user_without_a_licence_role_is_refused(self):
        outsider = get_user_model().objects.create_user(username="sro-" + uuid.uuid4().hex[:6], password="x")
        client = APIClient()
        client.force_authenticate(outsider)
        self.assertEqual(client.get(f"/api/licence-balances/{self.licence.id}/source-reconciliation/").status_code, 403)

    def test_endpoint_is_read_only_for_a_viewer(self):
        self.assertIn(self.api.post(f"/api/licence-balances/{self.licence.id}/source-reconciliation/", {}).status_code, (403, 405))


class TransactionQuantityTests(SourceReconciliationFixture):
    def test_boe_rows_carry_covered_and_uncovered_quantity_next_to_cif(self):
        trade, line = self._sale(invoice="Q-1", cif="500", qty="500")
        _boe, row = self._boe("Q-B", cif="300", qty="300", trades=[trade])
        self._allocate(row, line, "100", "100")
        boe = next(b for b in build_licence_transactions(self.licence.id)["boes"] if b["boe_number"] == "Q-B")
        self.assertEqual((boe["covered_cif"], boe["covered_qty"]), ("100.00", "100.000"))
        self.assertEqual((boe["uncovered_cif"], boe["uncovered_qty"]), ("200.00", "200.000"))
        self.assertEqual(boe["linked_sale_invoices"], ["Q-1"])
