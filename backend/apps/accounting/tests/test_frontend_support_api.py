"""API additions for the accounting frontend: draft editing, party summary, dashboard advances.

Authored with the frontend round (2026-11-17); not yet executed (testing deferred to the
coordinated testing phase)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from . import helpers as h
from .test_api import client_with

D = Decimal


class FrontendSupportApiTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.supplier = h.company("Exporter Pvt Ltd")
        self.approver = client_with("ACCOUNTS_APPROVER")
        self.manager = client_with("ACCOUNTS_MANAGER")
        self.viewer = client_with("ACCOUNTS_VIEWER")
        r = self.approver.post("/api/accounting/entities/", {"company_id": self.lm.pk, "books_start_date": "2026-04-01"},
                               format="json")
        self.assertEqual(r.status_code, 201, r.content)
        accounts = self.viewer.get("/api/accounting/accounts/", {"entity": self.lm.pk}).json()["accounts"]
        general = [a for a in accounts if a["kind"] == "GENERAL" and a["is_active"]]
        self.a, self.b = general[0]["id"], general[1]["id"]

    def _draft(self, client, amount="100.00"):
        r = client.post("/api/accounting/vouchers/", {
            "entity": self.lm.pk, "voucher_type": "JOURNAL", "date": "2026-05-10", "narration": "first",
            "lines": [{"account_id": self.a, "debit": amount}, {"account_id": self.b, "credit": amount}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_edit_draft_replaces_lines_and_keeps_balance_rule(self):
        v = self._draft(self.manager)
        r = self.manager.patch(f"/api/accounting/vouchers/{v['id']}/", {
            "narration": "edited", "date": "2026-05-11",
            "lines": [{"account_id": self.a, "debit": "250.00"}, {"account_id": self.b, "credit": "250.00"}],
        }, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual((body["narration"], body["date"], body["total"], body["status"]),
                         ("edited", "2026-05-11", "250.00", "DRAFT"))
        self.assertEqual(len(body["lines"]), 2)
        unbalanced = self.manager.patch(f"/api/accounting/vouchers/{v['id']}/", {
            "lines": [{"account_id": self.a, "debit": "10.00"}, {"account_id": self.b, "credit": "9.00"}],
        }, format="json")
        self.assertEqual(unbalanced.status_code, 400, unbalanced.content)

    def test_viewer_cannot_edit_and_posted_voucher_is_immutable(self):
        v = self._draft(self.manager)
        body = {"lines": [{"account_id": self.a, "debit": "5.00"}, {"account_id": self.b, "credit": "5.00"}]}
        self.assertEqual(self.viewer.patch(f"/api/accounting/vouchers/{v['id']}/", body, format="json").status_code, 403)
        self.assertEqual(self.approver.post(f"/api/accounting/vouchers/{v['id']}/post/").status_code, 200)
        r = self.manager.patch(f"/api/accounting/vouchers/{v['id']}/", body, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(self.viewer.get(f"/api/accounting/vouchers/{v['id']}/").json()["total"], "100.00")

    def test_party_summary_and_dashboard_advances(self):
        bank = self.approver.post("/api/accounting/bank-accounts/", {
            "entity": self.lm.pk, "bank_name": "HDFC", "account_number": "50100", "opening_balance": "100000.00",
        }, format="json").json()
        trade = h.trade("PURCHASE", self.supplier, self.lm, D("1000.00"), on=date(2026, 5, 3))
        inv = self.approver.post("/api/accounting/invoices/from-trade/", {"trade_id": trade.pk}, format="json").json()
        self.assertEqual(self.approver.post(f"/api/accounting/invoices/{inv['id']}/post/").status_code, 200)
        r = self.approver.post("/api/accounting/payments/", {
            "entity": self.lm.pk, "direction": "PAYMENT", "party_id": self.supplier.pk, "bank_account_id": bank["id"],
            "date": "2026-05-20", "amount": "1500.00", "allocations": [],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)

        summary = self.viewer.get("/api/accounting/parties/summary/",
                                  {"entity": self.lm.pk, "start": "2026-04-01", "end": "2027-03-31"}).json()
        row = next(p for p in summary["parties"] if p["party_id"] == self.supplier.pk)
        self.assertTrue(row["is_supplier"])
        self.assertEqual(row["payable"], "1000.00", "the bill is still open: nothing was allocated")
        self.assertEqual(row["balance"], "500.00", "GL: paid 1500 against a 1000 bill → 500 debit")

        dash = self.viewer.get("/api/accounting/reports/dashboard/",
                               {"entity": self.lm.pk, "start": "2026-04-01", "end": "2027-03-31"}).json()
        self.assertEqual(dash["advances_paid"], "1500.00")
        self.assertEqual(dash["advances_received"], "0.00")
