"""HTTP contract: permissions, Decimal-as-string money, and the trade -> bank workflow through the API."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User

from . import helpers as h

D = Decimal


def client_with(*roles, username=None) -> APIClient:
    user = User.objects.create_user(username=username or "_".join(roles).lower() or "plain", password="x")
    for role in roles:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    c = APIClient()
    c.force_authenticate(user)
    return c


class AccountingApiTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.supplier = h.company("Exporter Pvt Ltd")
        self.approver = client_with("ACCOUNTS_APPROVER")
        self.manager = client_with("ACCOUNTS_MANAGER")
        self.viewer = client_with("ACCOUNTS_VIEWER")
        self.outsider = client_with("TRADE_VIEWER")

    def _activate(self):
        r = self.approver.post("/api/accounting/entities/", {"company_id": self.lm.pk, "books_start_date": "2026-04-01"},
                               format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_permissions(self):
        self.assertEqual(APIClient().get("/api/accounting/entities/").status_code, 401)
        self.assertEqual(self.outsider.get("/api/accounting/entities/").status_code, 403)
        self.assertEqual(self.viewer.get("/api/accounting/entities/").status_code, 200)
        r = self.manager.post("/api/accounting/entities/", {"company_id": self.lm.pk, "books_start_date": "2026-04-01"},
                              format="json")
        self.assertEqual(r.status_code, 403, "only approvers activate books")
        self._activate()
        trade = h.trade("PURCHASE", self.supplier, self.lm, D("1000.00"))
        r = self.viewer.post("/api/accounting/invoices/from-trade/", {"trade_id": trade.pk}, format="json")
        self.assertEqual(r.status_code, 403)
        inv = self.manager.post("/api/accounting/invoices/from-trade/", {"trade_id": trade.pk}, format="json").json()
        self.assertEqual(self.manager.post(f"/api/accounting/invoices/{inv['id']}/confirm/").status_code, 200)
        self.assertEqual(self.manager.post(f"/api/accounting/invoices/{inv['id']}/post/").status_code, 403,
                         "managers draft/confirm; approvers post")
        self.assertEqual(self.approver.post(f"/api/accounting/invoices/{inv['id']}/post/").status_code, 200)

    def test_workflow_and_money_as_strings(self):
        entity = self._activate()
        self.assertEqual(entity["id"], self.lm.pk, "entity id is the existing company id")
        discovered = self.viewer.get("/api/accounting/entities/").json()["discovered"]
        self.assertTrue(any(d["company_id"] == self.lm.pk for d in discovered) or discovered == [])
        bank = self.approver.post("/api/accounting/bank-accounts/", {
            "entity": self.lm.pk, "bank_name": "HDFC", "account_number": "50100", "opening_balance": "100000.00",
        }, format="json").json()
        self.assertEqual(bank["book_balance"], "100000.00")
        trade = h.trade("PURCHASE", self.supplier, self.lm, D("25000.00"), on=date(2026, 5, 3))
        inv = self.approver.post("/api/accounting/invoices/from-trade/", {"trade_id": trade.pk, "credit_days": 15},
                                 format="json").json()
        inv = self.approver.post(f"/api/accounting/invoices/{inv['id']}/post/").json()
        self.assertEqual(inv["status"], "POSTED")
        self.assertEqual(inv["net_amount"], "25000.00")
        tracking = self.viewer.get(f"/api/accounting/trades/?entity={self.lm.pk}").json()
        self.assertEqual(tracking["results"][0]["accounting_status"], "ACCOUNTED")
        pay = self.approver.post("/api/accounting/payments/", {
            "entity": self.lm.pk, "direction": "PAYMENT", "party_id": self.supplier.pk, "bank_account_id": bank["id"],
            "date": "2026-05-10", "amount": "25000.00", "reference": "HDFCR52026051000123456",
            "allocations": [{"invoice_id": inv["id"], "amount": "25000.00"}],
        }, format="json")
        self.assertEqual(pay.status_code, 201, pay.content)
        detail = self.viewer.get(f"/api/accounting/invoices/{inv['id']}/").json()
        self.assertEqual((detail["outstanding"], detail["payment_status"]), ("0.00", "PAID"))

        csv = ("Date,Narration,Ref No,Debit,Credit,Balance\n"
               "10/05/2026,RTGS DR-EXPORTER,HDFCR52026051000123456,25000.00,,75000.00\n")
        up = self.manager.post(f"/api/accounting/bank-accounts/{bank['id']}/statements/",
                               {"file": SimpleUploadedFile("s.csv", csv.encode())}, format="multipart")
        self.assertEqual(up.status_code, 201, up.content)
        self.assertEqual(up.json()["rows_new"], 1)
        self.assertEqual(self.manager.post(f"/api/accounting/bank-accounts/{bank['id']}/auto-match/").json(),
                         {"utr": 1})
        brs = self.viewer.get(f"/api/accounting/bank-accounts/{bank['id']}/reconciliation/?as_of=2026-05-31").json()
        self.assertEqual((brs["book_balance"], brs["statement_balance"], brs["difference"]),
                         ("75000.00", "75000.00", "0.00"))

        tb = self.viewer.get(f"/api/accounting/reports/trial-balance/?entity={self.lm.pk}&fy=2026-27").json()
        self.assertTrue(tb["balanced"])
        pl = self.viewer.get(f"/api/accounting/reports/profit-loss/?entity={self.lm.pk}&fy=2026-27").json()
        self.assertEqual(pl["lines"]["purchases"]["amount"], "25000.00")
        bs = self.viewer.get(f"/api/accounting/reports/balance-sheet/?entity={self.lm.pk}&as_of=2027-03-31").json()
        self.assertTrue(bs["balanced"])
        dash = self.viewer.get(f"/api/accounting/reports/dashboard/?entity={self.lm.pk}&fy=2026-27").json()
        self.assertEqual(dash["bank_balance"], "75000.00")

    def test_errors_are_400_with_code(self):
        self._activate()
        trade = h.trade("SALE", self.lm, self.supplier, D("10.00"))
        inv = self.approver.post("/api/accounting/invoices/from-trade/", {"trade_id": trade.pk}, format="json").json()
        r = self.approver.post(f"/api/accounting/invoices/{inv['id']}/reverse/", {"reason": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "not_posted")
        self.assertEqual(self.viewer.get("/api/accounting/reports/nope/?entity=%d" % self.lm.pk).status_code, 400)

    def test_manual_journal_draft_then_post(self):
        self._activate()
        accts = self.viewer.get(f"/api/accounting/accounts/?entity={self.lm.pk}").json()["accounts"]
        by_role = {a["system_role"]: a["id"] for a in accts if a["system_role"]}
        draft = self.manager.post("/api/accounting/vouchers/", {
            "entity": self.lm.pk, "voucher_type": "JOURNAL", "date": "2026-06-30", "narration": "Closing stock",
            "lines": [{"account_id": by_role["CLOSING_STOCK"], "debit": "5000.00"},
                      {"account_id": by_role["STOCK_CHANGE"], "credit": "5000.00"}],
        }, format="json")
        self.assertEqual(draft.status_code, 201, draft.content)
        vid = draft.json()["id"]
        self.assertEqual(self.manager.post(f"/api/accounting/vouchers/{vid}/post/").status_code, 403)
        posted = self.approver.post(f"/api/accounting/vouchers/{vid}/post/").json()
        self.assertEqual(posted["status"], "POSTED")
        self.assertEqual(self.approver.delete(f"/api/accounting/vouchers/{vid}/").status_code, 400)
