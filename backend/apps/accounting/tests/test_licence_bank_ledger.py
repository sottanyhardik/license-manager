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

    # ---- per-trade bank settlement (`trades`) and bank-side summary ----
    def sibling_trade(self, t, direction, amount, number):
        """Another trade on the SAME licence (line on the same import item)."""
        from apps.trade.models import LicenseTrade, LicenseTradeLine
        seller, buyer = (self.supplier, self.us) if direction == "PURCHASE" else (self.us, self.supplier)
        other = LicenseTrade.objects.create(direction=direction, from_company=seller, to_company=buyer,
                                            invoice_number=number, invoice_date=date(2026, 5, 11))
        LicenseTradeLine.objects.create(trade=other, sr_number=t.lines.first().sr_number, description="sibling",
                                        mode=LicenseTradeLine.MODE_CIF_INR, qty_kg=D("1.0000"), cif_fc=D(amount),
                                        exc_rate=D("1.0000"), cif_inr=D(amount), pct=D("100.000"), amount_inr=D(amount))
        other.refresh_from_db()
        return other

    def trades_of(self, lic):
        r = self.get(lic).json()
        return r, {t["trade_id"]: t for t in r["trades"]}

    def test_trade_bank_status_unpaid_partial_paid_and_not_linked(self):
        unpaid = h.trade("PURCHASE", self.supplier, self.us, D("1000"))
        lic = self.lic_of(unpaid)
        partial = self.sibling_trade(unpaid, "PURCHASE", "1000", "P-PART")
        full = self.sibling_trade(unpaid, "PURCHASE", "1000", "P-FULL")
        p1 = self.payment("400.00", reference="UTR-PART")
        self.settle(p1, self.invoice(partial), "400.00")
        # Several bank payments settle one invoice: both listed, both counted.
        p2, p3 = self.payment("600.00", reference="UTR-F1"), self.payment("400.00", reference="UTR-F2")
        inv_full = self.invoice(full)
        self.settle(p2, inv_full, "600.00")
        self.settle(p3, inv_full, "400.00")
        r, t = self.trades_of(lic)
        self.assertEqual((t[unpaid.pk]["status"], t[unpaid.pk]["linked"], t[unpaid.pk]["allocations"]), ("UNPAID", False, []))
        self.assertEqual((t[partial.pk]["status"], t[partial.pk]["bank_settled"], t[partial.pk]["outstanding"]), ("PARTIAL", "400.00", "600.00"))
        self.assertEqual((t[full.pk]["status"], t[full.pk]["bank_settled"], t[full.pk]["outstanding"]), ("PAID", "1000.00", "0.00"))
        self.assertEqual([a["reference"] for a in t[full.pk]["allocations"]], ["UTR-F1", "UTR-F2"])
        self.assertTrue(all(x["direction"] == "PURCHASE" for x in r["trades"]))
        # Outstanding purchase = 1000 (unpaid) + 600 (partial) + 0.
        self.assertEqual(r["summary"]["total_outstanding_purchase"], "1600.00")
        self.assertEqual(r["summary"]["total_outstanding_sales"], "0.00")

    def test_sale_receipts_partial_full_none_and_one_receipt_across_two_invoices_counted_once(self):
        none = h.trade("SALE", self.us, self.supplier, D("1000"))
        lic = self.lic_of(none)
        a = self.sibling_trade(none, "SALE", "500", "S-A")
        b = self.sibling_trade(none, "SALE", "800", "S-B")
        receipt = self.payment("1000.00", direction="RECEIPT", reference="UTR-REC")
        self.settle(receipt, self.invoice(a), "500.00")   # full
        self.settle(receipt, self.invoice(b), "300.00")   # partial
        r, t = self.trades_of(lic)
        self.assertEqual(t[none.pk]["status"], "UNPAID")
        self.assertEqual((t[a.pk]["status"], t[a.pk]["outstanding"]), ("PAID", "0.00"))
        self.assertEqual((t[b.pk]["status"], t[b.pk]["outstanding"]), ("PARTIAL", "500.00"))
        # The bank receipt appears once; its allocation breakdown is per invoice.
        self.assertEqual(len(r["rows"]), 1)
        self.assertEqual([x["allocated"] for x in t[a.pk]["allocations"] + t[b.pk]["allocations"]], ["500.00", "300.00"])
        s = r["summary"]
        self.assertEqual((s["total_credits"], s["total_withdrawals"]), ("1000.00", "0.00"))
        self.assertEqual((s["total_allocated_receipts"], s["total_allocated_payments"]), ("800.00", "0.00"))
        # 200 of the receipt is not allocated to any invoice (unallocated credit).
        self.assertEqual((s["total_unallocated_credits"], s["total_unallocated_withdrawals"]), ("200.00", "0.00"))
        self.assertEqual(s["total_outstanding_sales"], "1500.00")
        self.assertEqual(r["rows"][0]["bank_direction"], "DEPOSIT")

    def test_unallocated_withdrawal_reversed_and_draft_not_counted_bank_side_from_statement(self):
        t = h.trade("PURCHASE", self.supplier, self.us, D("1000"))
        lic = self.lic_of(t)
        inv = self.invoice(t)
        posted = self.payment("900.00", reference="UTR-POSTED")
        self.settle(posted, inv, "500.00")   # 400 of the withdrawal stays unallocated
        self.match(posted, "900.00")          # statement debit → WITHDRAWAL, reconciled
        draft = self.payment("300.00", status="DRAFT", reference="UTR-DRAFT")
        self.settle(draft, inv, "300.00")
        reversed_ = self.payment("200.00", status="REVERSED", reference="UTR-REV")
        self.settle(reversed_, inv, "200.00")
        r, trades = self.trades_of(lic)
        row = trades[t.pk]
        # Only the POSTED allocation counts; the draft is listed (status DRAFT, not counted); reversed is absent.
        self.assertEqual((row["bank_settled"], row["outstanding"], row["status"]), ("500.00", "500.00", "PARTIAL"))
        self.assertEqual(sorted((a["reference"], a["counted"]) for a in row["allocations"]),
                         [("UTR-DRAFT", False), ("UTR-POSTED", True)])
        posted_row = next(x for x in r["rows"] if x["reference"] == "UTR-POSTED")
        self.assertEqual((posted_row["bank_direction"], posted_row["reconciliation"]), ("WITHDRAWAL", "RECONCILED"))
        self.assertEqual(posted_row["statement_lines"][0]["bank_direction"], "WITHDRAWAL")
        self.assertEqual(r["summary"]["total_unallocated_withdrawals"], "400.00")
        self.assertNotIn("UTR-REV", {x["reference"] for x in r["rows"]})
        # Totals reconcile with the rows.
        s = r["summary"]
        self.assertEqual(Decimal(s["total_withdrawals"]), sum(Decimal(x["amount"]) for x in r["rows"] if x["bank_direction"] == "WITHDRAWAL"))

    def test_licence_without_bank_activity_lists_trades_as_not_linked(self):
        t = h.trade("SALE", self.us, self.supplier, D("750"))
        r, trades = self.trades_of(self.lic_of(t))
        self.assertEqual(r["rows"], [])
        self.assertEqual((trades[t.pk]["status"], trades[t.pk]["linked"], trades[t.pk]["outstanding"]), ("UNPAID", False, "750.00"))
        self.assertEqual(r["summary"]["total_outstanding_sales"], "750.00")
