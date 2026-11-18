"""`GET .../overview-payment-ledgers/` — trade settlement ledgers per licence."""
import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin
from apps.trade.models import LicenseTrade, LicenseTradeLine, LicenseTradePayment

D = Decimal


class PaymentLedgersTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())
        self.company = self.make_company()
        self.other = self.make_company("Counterparty")
        self.lic = self.make_license(self.company)
        self.item = self.make_item(self.lic, 1)

    def trade(self, direction, amount, on=None, item=None, number=None):
        t = LicenseTrade.objects.create(
            direction=direction,
            from_company=self.other if direction.endswith("PURCHASE") else self.company,
            to_company=self.company if direction.endswith("PURCHASE") else self.other,
            invoice_number=number or f"INV-{uuid.uuid4().hex[:6]}", invoice_date=on)
        self.line(t, item or self.item, amount)
        return t

    def line(self, t, item, amount):
        LicenseTradeLine.objects.create(
            trade=t, sr_number=item, description="x", mode=LicenseTradeLine.MODE_CIF_INR,
            cif_fc=D(amount), exc_rate=D("1.0000"), cif_inr=D(amount), pct=D("100"), amount_inr=D(amount))
        t.refresh_from_db()

    def get(self):
        r = self.client.get(f"/api/licenses/{self.lic.id}/overview-payment-ledgers/")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_split_status_and_summary(self):
        paid = self.trade(LicenseTrade.DIR_PURCHASE, "1000", date(2026, 5, 1))
        part = self.trade(LicenseTrade.DIR_PURCHASE, "2000", date(2026, 4, 1))
        over = self.trade(LicenseTrade.DIR_PURCHASE, "500", date(2026, 3, 1))
        sale = self.trade(LicenseTrade.DIR_SALE, "3000", date(2026, 6, 1))
        LicenseTradePayment.objects.create(trade=paid, date=date(2026, 5, 2), amount=D("1000"), note="full")
        LicenseTradePayment.objects.create(trade=part, date=date(2026, 4, 5), amount=D("300"))
        LicenseTradePayment.objects.create(trade=part, date=date(2026, 4, 9), amount=D("200"))
        LicenseTradePayment.objects.create(trade=over, date=date(2026, 5, 2), amount=D("700"))
        data = self.get()
        p = data["purchase"]
        self.assertEqual([r["trade_id"] for r in p["rows"]], [over.id, part.id, paid.id])
        by = {r["trade_id"]: r for r in p["rows"]}
        self.assertEqual(by[paid.id]["status"], "PAID")
        self.assertEqual(by[part.id]["status"], "PARTIAL")
        self.assertEqual(float(by[part.id]["settled"]), 500.0)
        self.assertEqual(float(by[part.id]["outstanding"]), 1500.0)
        self.assertEqual(by[over.id]["status"], "PAID")
        self.assertEqual(float(by[over.id]["outstanding"]), -200.0)
        self.assertEqual(len(by[part.id]["payments"]), 2)
        self.assertIsNone(by[part.id]["gst"])
        s = p["summary"]
        rows = p["rows"]
        self.assertEqual(s["invoice_count"], 3)
        self.assertEqual(s["total_amount"], sum(r["total"] for r in rows))
        self.assertEqual(s["total_settled"], sum(r["settled"] for r in rows))
        self.assertEqual(s["total_outstanding"], sum(r["outstanding"] for r in rows))
        self.assertEqual(float(s["total_outstanding"]), float(s["total_amount"]) - float(s["total_settled"]))
        # sale side
        self.assertEqual([r["trade_id"] for r in data["sale"]["rows"]], [sale.id])
        self.assertEqual(data["sale"]["rows"][0]["status"], "UNPAID")
        self.assertEqual(data["sale"]["rows"][0]["company_name"], "Counterparty")
        self.assertEqual(data["purchase"]["rows"][0]["company_name"], "Counterparty")

    def test_licence_amount_only_this_licence_and_unrelated_excluded(self):
        other_lic = self.make_license(self.company)
        other_item = self.make_item(other_lic, 1)
        t = self.trade(LicenseTrade.DIR_PURCHASE, "1000", date(2026, 5, 1))
        self.line(t, other_item, "400")
        unrelated = self.trade(LicenseTrade.DIR_PURCHASE, "50", date(2026, 5, 1), item=other_item)
        data = self.get()
        rows = data["purchase"]["rows"]
        self.assertEqual([r["trade_id"] for r in rows], [t.id])
        self.assertNotIn(unrelated.id, [r["trade_id"] for r in rows])
        self.assertEqual(float(rows[0]["licence_amount"]), 1000.0)
        self.assertEqual(float(rows[0]["total"]), 1400.0)

    def test_payment_bank_reference_and_document(self):
        t = self.trade(LicenseTrade.DIR_PURCHASE, "1000", date(2026, 5, 1))
        t.purchase_invoice_copy.save("inv.pdf", ContentFile(b"%PDF"), save=True)
        LicenseTradePayment.objects.create(trade=t, date=date(2026, 5, 2), amount=D("100"), note="n")
        row = self.get()["purchase"]["rows"][0]
        self.assertEqual(row["document"]["kind"], "purchase_invoice_copy")
        self.assertIn("inv", row["document"]["url"])
        self.assertEqual(row["payments"][0]["note"], "n")
        self.assertIsNone(row["payments"][0]["bank_reference"])
        t2 = self.trade(LicenseTrade.DIR_SALE, "10", date(2026, 5, 1))
        self.assertIsNone([r for r in self.get()["sale"]["rows"]][0]["document"])

    def test_permissions(self):
        c = APIClient()
        user = self.make_plain_user()
        user.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        c.force_authenticate(user=user)
        url = f"/api/licenses/{self.lic.id}/overview-payment-ledgers/"
        self.assertEqual(c.get(url).status_code, 200)
        c2 = APIClient()
        c2.force_authenticate(user=self.make_plain_user())
        self.assertEqual(c2.get(url).status_code, 403)
