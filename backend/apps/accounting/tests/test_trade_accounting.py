"""Trade -> invoice -> voucher -> party ledger -> payment -> settlement (prompt scenarios 1, 2, 4, 5)."""
from datetime import date
from decimal import Decimal

from django.db.models import ProtectedError
from django.test import TestCase

from apps.accounting.models import DocStatus, Invoice, Payment, Voucher
from apps.accounting.selectors.ledger import account_balance
from apps.accounting.services import AccountingError
from apps.accounting.services.books import party_account
from apps.accounting.services.chart import system_account
from apps.accounting.services.invoices import (
    confirm_invoice, invoice_from_trade, outstanding, payment_status, post_invoice, resync_trade_invoice,
)
from apps.accounting.services.payments import account_trade_payment, record_payment

from . import helpers as h

D = Decimal


def post_trade(trade, **kw):
    inv = invoice_from_trade(trade.pk, **kw)
    confirm_invoice(inv)
    return post_invoice(inv)


class PurchaseScenarioTests(TestCase):
    """Scenario 1 incl. the prompt's worked example: 10,00,000 + GST 1,80,000; TDS 20,000 -> payable 11,60,000."""

    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.supplier = h.company("Exporter Pvt Ltd", gst="27AAACE0000A1Z5", pan="AAACE0000A")
        self.bank = h.bank(self.entity)

    def test_purchase_posts_exactly_once_and_payable_settles(self):
        t = h.trade("PURCHASE", self.supplier, self.lm, D("1000000.00"))
        inv = post_trade(t, credit_days=30)
        self.assertEqual(inv.status, DocStatus.POSTED)
        self.assertEqual(inv.kind, "PURCHASE")
        # exactly once: re-linking returns the same invoice; re-posting is a no-op
        self.assertEqual(invoice_from_trade(t.pk).pk, inv.pk)
        post_invoice(inv)
        self.assertEqual(Voucher.objects.filter(source_type="INVOICE", source_id=inv.pk).count(), 1)
        supplier_acct = party_account(self.entity, self.supplier, payable=True)
        self.assertEqual(account_balance(supplier_acct), D("-1000000.00"))
        self.assertEqual(account_balance(system_account(self.entity, "PURCHASES")), D("1000000.00"))

        p1 = record_payment(entity=self.entity, direction="PAYMENT", party=self.supplier, bank_account=self.bank,
                            payment_date=date(2026, 5, 20), amount=D("400000.00"), reference="HDFCN12345678901",
                            allocations=[(inv, D("400000.00"))])
        self.assertEqual(outstanding(inv), D("600000.00"))
        self.assertEqual(payment_status(inv, today=date(2026, 5, 21)), "PARTIALLY_PAID")
        record_payment(entity=self.entity, direction="PAYMENT", party=self.supplier, bank_account=self.bank,
                       payment_date=date(2026, 5, 25), amount=D("600000.00"), allocations=[(inv, D("600000.00"))])
        self.assertEqual(outstanding(inv), D("0.00"))
        self.assertEqual(payment_status(inv), "PAID")
        self.assertEqual(account_balance(supplier_acct), D("0.00"))
        self.assertEqual(account_balance(self.bank.account), D("-1000000.00"))
        self.assertEqual(p1.voucher.voucher_type, "PAYMENT")

    def test_worked_example_gst_and_tds(self):
        from apps.accounting.services.invoices import LineInput, create_invoice
        section = h.tds_section(code="194Q", rate="2.000", threshold="0", mode="FULL")
        inv = create_invoice(entity=self.entity, kind="PURCHASE", party=self.supplier, number="SUP/001",
                             invoice_date=date(2026, 6, 1), tds_section=section,
                             lines=[LineInput(system_account(self.entity, "PURCHASES"), D("1000000.00"),
                                              "Goods", gst_rate=D("18"))])
        self.assertEqual(inv.cgst + inv.sgst, D("180000.00"))  # intra-state: CGST + SGST
        self.assertEqual(inv.gross_amount, D("1180000.00"))
        self.assertEqual(inv.tds_amount, D("20000.00"))
        self.assertEqual(inv.net_amount, D("1160000.00"))
        confirm_invoice(inv)
        post_invoice(inv)
        supplier_acct = party_account(self.entity, self.supplier, payable=True)
        self.assertEqual(account_balance(supplier_acct), D("-1160000.00"))
        self.assertEqual(account_balance(system_account(self.entity, "TDS_PAYABLE")), D("-20000.00"))
        self.assertEqual(account_balance(system_account(self.entity, "INPUT_CGST")), D("90000.00"))
        record_payment(entity=self.entity, direction="PAYMENT", party=self.supplier, bank_account=self.bank,
                       payment_date=date(2026, 6, 5), amount=D("1160000.00"), allocations=[(inv, D("1160000.00"))])
        self.assertEqual(outstanding(inv), D("0.00"))
        self.assertEqual(account_balance(supplier_acct), D("0.00"))

    def test_tds_threshold_excess_mode(self):
        from apps.accounting.services.invoices import LineInput, create_invoice
        section = h.tds_section(code="194Q", rate="0.100", threshold="5000000.00", mode="EXCESS")
        acct = system_account(self.entity, "PURCHASES")
        first = create_invoice(entity=self.entity, kind="PURCHASE", party=self.supplier, number="A",
                               invoice_date=date(2026, 6, 1), tds_section=section, lines=[h_line(acct, "4000000")])
        self.assertEqual(first.tds_amount, D("0.00"))
        confirm_invoice(first); post_invoice(first)
        second = create_invoice(entity=self.entity, kind="PURCHASE", party=self.supplier, number="B",
                                invoice_date=date(2026, 7, 1), tds_section=section, lines=[h_line(acct, "2000000")])
        self.assertEqual(second.tds_amount, D("1000.00"))  # 0.1% of the 10,00,000 above the threshold

    def test_trade_edit_after_posting_reverses_and_reposts(self):
        from apps.trade.models import LicenseTradeLine
        t = h.trade("PURCHASE", self.supplier, self.lm, D("500000.00"))
        inv = post_trade(t)
        first_voucher = inv.voucher
        line = t.lines.get()
        LicenseTradeLine.objects.filter(pk=line.pk).update(amount_inr=D("550000.00"), cif_inr=D("550000.00"))
        t.recompute_totals()
        from apps.accounting.services.invoices import trade_drift
        self.assertTrue(trade_drift(inv))
        inv = resync_trade_invoice(inv)
        first_voucher.refresh_from_db()
        self.assertEqual(first_voucher.status, "REVERSED")
        self.assertEqual(inv.status, DocStatus.POSTED)
        self.assertNotEqual(inv.voucher_id, first_voucher.pk)
        supplier_acct = party_account(self.entity, self.supplier, payable=True)
        self.assertEqual(account_balance(supplier_acct), D("-550000.00"))

    def test_posted_trade_cannot_be_deleted(self):
        t = h.trade("PURCHASE", self.supplier, self.lm, D("1000.00"))
        post_trade(t)
        with self.assertRaises(ProtectedError):
            t.delete()

    def test_draft_link_does_not_block_trade_delete(self):
        t = h.trade("PURCHASE", self.supplier, self.lm, D("1000.00"))
        invoice_from_trade(t.pk)
        t.delete()
        self.assertFalse(Invoice.objects.filter(trade_id=t.pk).exists())

    def test_existing_trade_payment_is_linked_once(self):
        from apps.trade.models import LicenseTradePayment
        t = h.trade("PURCHASE", self.supplier, self.lm, D("1000.00"))
        inv = post_trade(t)
        tp = LicenseTradePayment.objects.create(trade=t, date=date(2026, 5, 15), amount=D("600.00"), note="part")
        p = account_trade_payment(tp.pk, bank_account=self.bank)
        again = account_trade_payment(tp.pk, bank_account=self.bank)
        self.assertEqual(p.pk, again.pk)
        self.assertEqual(Payment.objects.filter(trade_payment=tp).count(), 1)
        self.assertEqual(outstanding(inv), D("400.00"))
        with self.assertRaises(ProtectedError):
            tp.delete()

    def test_trade_without_books_is_not_postable(self):
        stranger = h.company("No Books Co")
        t = h.trade("PURCHASE", self.supplier, stranger, D("10.00"))
        with self.assertRaises(AccountingError):
            invoice_from_trade(t.pk)


def h_line(acct, amount):
    from apps.accounting.services.invoices import LineInput
    return LineInput(acct, D(amount), "Goods")


class SalesAndCommissionScenarioTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.customer = h.company("Importer Ltd", gst="24AAACI0000A1Z5")
        self.bank = h.bank(self.entity)

    def test_sale_creates_receivable_and_receipt_with_tds_settles(self):
        t = h.trade("SALE", self.lm, self.customer, D("200000.00"))
        inv = post_trade(t)
        self.assertEqual(inv.kind, "SALES")
        cust = party_account(self.entity, self.customer, payable=False)
        self.assertEqual(account_balance(cust), D("200000.00"))
        self.assertEqual(account_balance(system_account(self.entity, "SALES")), D("-200000.00"))
        record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                       payment_date=date(2026, 6, 1), amount=D("199800.00"), tds_amount=D("200.00"),
                       allocations=[(inv, D("200000.00"))])
        self.assertEqual(outstanding(inv), D("0.00"))
        self.assertEqual(account_balance(cust), D("0.00"))
        self.assertEqual(account_balance(system_account(self.entity, "TDS_RECEIVABLE")), D("200.00"))

    def test_advance_then_allocation(self):
        from apps.accounting.services.payments import allocate_payment, unallocated
        adv = record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                             payment_date=date(2026, 5, 1), amount=D("50000.00"))
        self.assertEqual(unallocated(adv), D("50000.00"))
        t = h.trade("SALE", self.lm, self.customer, D("80000.00"))
        inv = post_trade(t)
        allocate_payment(adv, inv, D("50000.00"))
        self.assertEqual(outstanding(inv), D("30000.00"))
        with self.assertRaises(AccountingError):
            allocate_payment(adv, inv, D("1.00"))

    def test_one_receipt_settles_two_invoices(self):
        a = post_trade(h.trade("SALE", self.lm, self.customer, D("100.00")))
        b = post_trade(h.trade("SALE", self.lm, self.customer, D("250.00")))
        record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                       payment_date=date(2026, 6, 1), amount=D("350.00"), allocations=[(a, D("100")), (b, D("250"))])
        self.assertEqual((outstanding(a), outstanding(b)), (D("0.00"), D("0.00")))

    def test_over_allocation_rejected(self):
        a = post_trade(h.trade("SALE", self.lm, self.customer, D("100.00")))
        with self.assertRaises(AccountingError):
            record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                           payment_date=date(2026, 6, 1), amount=D("150.00"), allocations=[(a, D("150"))])

    def test_commission_trades_post_to_commission_heads(self):
        agent = h.company("Agent & Co")
        paid = post_trade(h.trade("COMMISSION_PURCHASE", agent, self.lm, D("5000.00")))
        recd = post_trade(h.trade("COMMISSION_SALE", self.lm, agent, D("3000.00")))
        self.assertEqual(paid.kind, "COMMISSION_PAYABLE")
        self.assertEqual(recd.kind, "COMMISSION_RECEIVABLE")
        self.assertEqual(account_balance(system_account(self.entity, "COMMISSION_EXPENSE")), D("5000.00"))
        self.assertEqual(account_balance(system_account(self.entity, "COMMISSION_INCOME")), D("-3000.00"))
        # one party ledger per agent, net of both
        self.assertEqual(account_balance(party_account(self.entity, agent, payable=True)), D("-2000.00"))

    def test_credit_note_adjusts_bill(self):
        from apps.accounting.services.invoices import LineInput, create_invoice
        inv = post_trade(h.trade("SALE", self.lm, self.customer, D("1000.00")))
        cn = create_invoice(entity=self.entity, kind="CREDIT_NOTE", party=self.customer, number="CN/1",
                            invoice_date=date(2026, 6, 1), against_invoice=inv,
                            lines=[LineInput(system_account(self.entity, "SALES_RETURNS"), D("300.00"), "return")])
        confirm_invoice(cn)
        post_invoice(cn)
        self.assertEqual(outstanding(inv), D("700.00"))
        self.assertEqual(account_balance(party_account(self.entity, self.customer, payable=False)), D("700.00"))


class MultiEntityTests(TestCase):
    """Scenario 5: a paired intercompany transfer posts once in each entity's own books."""

    def test_intercompany_pair_posts_in_both_books_separately(self):
        from apps.trade.services.trade_service import copy_sale_to_purchase
        lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        lg = h.company("Labdhi Global LLP", gst="27AAAFG0000A1Z5")
        e_lm, e_lg = h.books(lm), h.books(lg)
        sale = h.trade("SALE", lm, lg, D("75000.00"))
        _src, purchase, _ = copy_sale_to_purchase(sale.pk)
        s_inv, p_inv = post_trade(sale), post_trade(purchase)
        self.assertEqual((s_inv.entity_id, p_inv.entity_id), (lm.pk, lg.pk))
        self.assertEqual(account_balance(system_account(e_lm, "INTERCOMPANY_SALES")), D("-75000.00"))
        self.assertEqual(account_balance(system_account(e_lg, "INTERCOMPANY_PURCHASES")), D("75000.00"))
        self.assertEqual(account_balance(system_account(e_lm, "PURCHASES")), D("0"))
        self.assertEqual(account_balance(system_account(e_lg, "SALES")), D("0"))
        self.assertEqual(party_account(e_lm, lg, payable=False).intercompany_entity_id, lg.pk)

    def test_pair_with_external_party_posts_only_own_leg(self):
        from apps.trade.services.trade_service import copy_purchase_to_sale
        lm = h.company("Labdhi Mercantile LLP")
        h.books(lm)
        supplier = h.company("Outside Exporter")
        purchase = h.trade("PURCHASE", supplier, lm, D("1000.00"))
        _src, sale_copy, _ = copy_purchase_to_sale(purchase.pk)
        post_trade(purchase)
        with self.assertRaises(AccountingError) as ctx:  # sale copy belongs to the supplier's books (not ours)
            invoice_from_trade(sale_copy.pk)
        self.assertEqual(ctx.exception.code, "no_books")
