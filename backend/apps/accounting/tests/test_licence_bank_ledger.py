"""`GET /api/accounting/licence-bank-ledger/<license_id>/` — structural (never amount-based) linkage."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounting.models import (
    BankMatch, Invoice, InvoiceLine, Payment, Settlement, StatementImport, StatementLine, Voucher,
)
from apps.accounts.models import User
from apps.trade.models import LicenseTradePayment

from . import helpers as h

D = Decimal


def client_with(*roles, superuser=False):
    n = User.objects.count()
    user = User.objects.create_user(username=f"lbl{n}_{'_'.join(roles)}", password="x", is_superuser=superuser)
    for r in roles:
        user.groups.add(Group.objects.get_or_create(name=r)[0])
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class LicenceBankLedgerTests(TestCase):
    def setUp(self):
        self.us = h.company("Us Ltd")
        self.supplier = h.company("Supplier")
        self.entity = h.books(self.us)
        self.bank = h.bank(self.entity)
        self.fy = self.entity.financial_years.first()
        self.viewer = client_with("ACCOUNTS_VIEWER")
        self.n = 0

    # ---- builders ----
    def voucher(self):
        self.n += 1
        return Voucher.objects.create(entity=self.entity, financial_year=self.fy, voucher_type="PAYMENT",
                                      date=date(2026, 5, 20), total=D("1"), status="DRAFT")

    def invoice(self, trade, number=None):
        self.n += 1
        inv = Invoice.objects.create(entity=self.entity, kind="PURCHASE", party=self.supplier,
                                     number=number or f"INV-{self.n}", date=date(2026, 5, 10))
        InvoiceLine.objects.create(invoice=inv, line_no=1, account=self.bank.account, amount=D("100"), trade=trade)
        return inv

    def payment(self, amount="1000.00", status="POSTED", direction="PAYMENT", on=date(2026, 5, 20),
                tds="0", trade_payment=None, reference="UTR1", with_voucher=True):
        return Payment.objects.create(
            entity=self.entity, direction=direction, party=self.supplier, bank_account=self.bank, date=on,
            amount=D(amount), tds_amount=D(tds), reference=reference, status=status,
            voucher=self.voucher() if with_voucher else None, trade_payment=trade_payment)

    def settle(self, payment, invoice, amount, active=True):
        return Settlement.objects.create(entity=self.entity, invoice=invoice, voucher=self.voucher(),
                                         payment=payment, amount=D(amount), is_active=active)

    def match(self, payment, amount, txn=date(2026, 5, 21), active=True, ref="BANKREF"):
        imp = StatementImport.objects.create(bank_account=self.bank, file_name="s.csv", file_format="csv")
        self.n += 1
        sl = StatementLine.objects.create(bank_account=self.bank, statement_import=imp, txn_date=txn,
                                          reference=ref, debit=D(amount), fingerprint=f"fp{self.n}")
        BankMatch.objects.create(statement_line=sl, voucher=payment.voucher, amount=D(amount), method="MANUAL",
                                 is_active=active)
        return sl

    def get(self, lic, client=None):
        return (client or self.viewer).get(f"/api/accounting/licence-bank-ledger/{lic.pk}/")

    def lic_of(self, trade):
        return trade.lines.first().sr_number.license

    # ---- tests ----
    def test_settlement_linked_payment_and_multi_invoice_single_row(self):
        t = h.trade("PURCHASE", self.supplier, self.us, D("5000"))
        lic = self.lic_of(t)
        inv1, inv2 = self.invoice(t, "A1"), self.invoice(t, "A2")
        p = self.payment("1000.00")
        self.settle(p, inv1, "400.00")
        self.settle(p, inv2, "300.00")
        r = self.get(lic)
        self.assertEqual(r.status_code, 200)
        rows = r.json()["rows"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["payment_id"], p.pk)
        self.assertEqual(row["allocated_to_licence"], "700.00")
        self.assertEqual(row["unallocated"], "300.00")
        self.assertEqual({i["number"] for i in row["invoices"]}, {"A1", "A2"})
        self.assertEqual(row["direction"], "PAYMENT")
        s = r.json()["summary"]
        self.assertEqual((s["transaction_count"], s["total_payments"], s["total_receipts"]), (1, "1000.00", "0.00"))
        self.assertEqual((s["total_allocated"], s["total_unallocated"]), ("700.00", "300.00"))

    def test_trade_payment_linked_payment_not_double_counted(self):
        t = h.trade("PURCHASE", self.supplier, self.us, D("5000"))
        lic = self.lic_of(t)
        tp = LicenseTradePayment.objects.create(trade=t, date=date(2026, 5, 15), amount=D("600.00"))
        p = self.payment("600.00", trade_payment=tp)
        r = self.get(lic).json()
        self.assertEqual(len(r["rows"]), 1)
        self.assertEqual(r["rows"][0]["allocated_to_licence"], "600.00")
        # The trade-payment link is the allocation: traceable to the trade invoice and not also "unallocated".
        self.assertEqual(r["rows"][0]["unallocated"], "0.00")
        self.assertEqual(r["rows"][0]["invoices"], [
            {"invoice_id": None, "number": t.invoice_number, "trade_id": t.pk, "amount": "600.00"}])
        self.assertEqual(r["summary"]["total_allocated"], "600.00")
        self.assertEqual(r["summary"]["total_unallocated"], "0.00")
        # An accounting invoice referencing the trade (no settlement yet) is listed as the linked invoice.
        inv = self.invoice(t, number="ACC-INV-1")
        row = self.get(lic).json()["rows"][0]
        self.assertEqual(row["invoices"], [{"invoice_id": inv.pk, "number": "ACC-INV-1", "trade_id": t.pk, "amount": "600.00"}])
        # also settled against a licence invoice: allocation comes from the settlement only
        self.settle(p, inv, "600.00")
        row = self.get(lic).json()["rows"][0]
        self.assertEqual(row["allocated_to_licence"], "600.00")
        self.assertEqual(row["unallocated"], "0.00")

    def test_receipt_direction_and_tds_in_unallocated(self):
        t = h.trade("SALE", self.us, self.supplier, D("5000"))
        lic = self.lic_of(t)
        p = self.payment("900.00", direction="RECEIPT", tds="100.00")
        self.settle(p, self.invoice(t), "400.00")
        s = self.get(lic).json()
        self.assertEqual(s["summary"]["total_receipts"], "900.00")
        self.assertEqual(s["summary"]["total_payments"], "0.00")
        self.assertEqual(s["rows"][0]["unallocated"], "600.00")

    def test_reconciliation_states(self):
        t = h.trade("PURCHASE", self.supplier, self.us, D("5000"))
        lic = self.lic_of(t)
        inv = self.invoice(t)
        full = self.payment("1000.00", on=date(2026, 5, 1), reference="F")
        part = self.payment("1000.00", on=date(2026, 5, 2), reference="P")
        none = self.payment("1000.00", on=date(2026, 5, 3), reference="N")
        inactive = self.payment("1000.00", on=date(2026, 5, 4), reference="I")
        novoucher = self.payment("1000.00", on=date(2026, 5, 5), reference="V", with_voucher=False)
        for p in (full, part, none, inactive, novoucher):
            self.settle(p, inv, "100.00")
        self.match(full, "1000.00")
        self.match(part, "400.00")
        self.match(inactive, "1000.00", active=False)
        by = {r["reference"]: r for r in self.get(lic).json()["rows"]}
        self.assertEqual(by["F"]["reconciliation"], "RECONCILED")
        self.assertEqual(by["F"]["statement_lines"][0]["reference"], "BANKREF")
        self.assertEqual(by["P"]["reconciliation"], "PARTIAL")
        self.assertEqual(by["N"]["reconciliation"], "UNRECONCILED")
        self.assertEqual(by["I"]["reconciliation"], "UNRECONCILED")
        self.assertEqual(by["V"]["reconciliation"], "UNRECONCILED")
        self.assertEqual([r["reference"] for r in self.get(lic).json()["rows"]], ["F", "P", "N", "I", "V"])

    def test_cancelled_reversed_and_inactive_settlements_excluded(self):
        t = h.trade("PURCHASE", self.supplier, self.us, D("5000"))
        lic = self.lic_of(t)
        inv = self.invoice(t)
        keep = self.payment(status="DRAFT", reference="KEEP")
        self.settle(keep, inv, "100.00")
        for st in ("CANCELLED", "REVERSED"):
            self.settle(self.payment(status=st, reference=st), inv, "100.00")
        dead = self.payment(reference="DEAD")
        self.settle(dead, inv, "100.00", active=False)
        rows = self.get(lic).json()["rows"]
        self.assertEqual([r["reference"] for r in rows], ["KEEP"])
        self.assertEqual(rows[0]["status"], "DRAFT")

    def test_other_licence_excluded(self):
        t1 = h.trade("PURCHASE", self.supplier, self.us, D("5000"))
        t2 = h.trade("PURCHASE", self.supplier, self.us, D("5000"))
        self.settle(self.payment(reference="MINE"), self.invoice(t1), "100.00")
        self.settle(self.payment(reference="OTHER"), self.invoice(t2), "100.00")
        rows = self.get(self.lic_of(t1)).json()["rows"]
        self.assertEqual([r["reference"] for r in rows], ["MINE"])

    def test_empty_licence(self):
        t = h.trade("PURCHASE", self.supplier, self.us, D("5000"))
        r = self.get(self.lic_of(t)).json()
        self.assertEqual(r["rows"], [])
        self.assertEqual(r["summary"]["transaction_count"], 0)

    def test_query_count_is_flat(self):
        t = h.trade("PURCHASE", self.supplier, self.us, D("5000"))
        inv = self.invoice(t)

        def build(n):
            for i in range(n):
                p = self.payment(reference=f"Q{self.n}")
                self.settle(p, inv, "10.00")
                self.match(p, "10.00")
        lic = self.lic_of(t)
        build(1)
        with self.assertNumQueries(self._count(lic)):
            self.get(lic)
        build(4)
        with self.assertNumQueries(self._count(lic, probe=False)):
            self.get(lic)

    _first = None

    def _count(self, lic, probe=True):
        if probe:
            from django.db import connection
            from django.test.utils import CaptureQueriesContext
            with CaptureQueriesContext(connection) as ctx:
                self.get(lic)
            LicenceBankLedgerTests._first = len(ctx)
        return LicenceBankLedgerTests._first

    def test_permissions_and_404(self):
        t = h.trade("PURCHASE", self.supplier, self.us, D("5000"))
        lic = self.lic_of(t)
        self.assertEqual(self.get(lic, client_with("TRADE_VIEWER")).status_code, 403)
        self.assertEqual(self.get(lic, client_with("LICENSE_VIEWER")).status_code, 403)
        self.assertEqual(self.get(lic, client_with()).status_code, 403)
        self.assertEqual(self.get(lic, client_with("ACCOUNTS_VIEWER")).status_code, 200)
        self.assertEqual(self.get(lic, client_with(superuser=True)).status_code, 200)
        r = self.viewer.get("/api/accounting/licence-bank-ledger/99999999/")
        self.assertEqual(r.status_code, 404)
