"""Regression tests for the independent review findings (H1–H5, M1–M8)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.models import LineStatus, StatementLine, Voucher
from apps.accounting.selectors.ledger import account_balance
from apps.accounting.selectors.reports import ageing, cash_flow
from apps.accounting.services import AccountingError
from apps.accounting.services.banking import (
    auto_match, bank_reconciliation, import_statement, manual_match, move_to_suspense, reclassify_suspense,
)
from apps.accounting.services.books import party_account
from apps.accounting.services.chart import system_account
from apps.accounting.services.invoices import (
    LineInput, confirm_invoice, create_invoice, invoice_from_trade, outstanding, post_invoice, resync_trade_invoice,
    reverse_invoice,
)
from apps.accounting.services.loans import create_loan, principal_outstanding, record_repayment
from apps.accounting.services.payments import record_payment, reverse_payment
from apps.accounting.services.posting import cr, dr, post_voucher, reverse_manual_voucher

from . import helpers as h

D = Decimal


def post(inv):
    confirm_invoice(inv)
    return post_invoice(inv)


class ReviewRegressionTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.bank = h.bank(self.entity, number="A-1")
        self.supplier = h.company("Exporter Pvt Ltd", gst="27AAACE0000A1Z5")
        self.customer = h.company("Importer Ltd")

    def _purchase_bill(self, amount="10000.00", number="B1"):
        return post(create_invoice(entity=self.entity, kind="PURCHASE", party=self.supplier, number=number,
                                   invoice_date=date(2026, 5, 1),
                                   lines=[LineInput(system_account(self.entity, "PURCHASES"), D(amount), "goods")]))

    def test_h1_reversing_a_note_restores_the_bill(self):
        bill = self._purchase_bill()
        note = post(create_invoice(entity=self.entity, kind="DEBIT_NOTE", party=self.supplier, number="DN1",
                                   invoice_date=date(2026, 5, 5), against_invoice=bill,
                                   lines=[LineInput(system_account(self.entity, "PURCHASE_RETURNS"), D("2000"), "ret")]))
        self.assertEqual(outstanding(bill), D("8000.00"))
        reverse_invoice(note, reason="raised in error")
        self.assertEqual(outstanding(bill), D("10000.00"))
        self.assertEqual(-account_balance(party_account(self.entity, self.supplier, payable=True)), outstanding(bill))
        reverse_invoice(bill, reason="cleanup")  # no longer blocked by a dead settlement

    def test_h2_document_vouchers_cannot_be_reversed_directly(self):
        bill = self._purchase_bill()
        with self.assertRaises(AccountingError) as ctx:
            reverse_manual_voucher(bill.voucher, reason="x")
        self.assertEqual(ctx.exception.code, "document_owned")

    def test_h3_reclassify_cannot_over_allocate_or_cross_direction(self):
        a = self._purchase_bill(number="P1")
        csv = "Date,Narration,Debit,Credit,Balance\n02/05/2026,UNKNOWN,,1000.00,1000.00\n"
        line = import_statement(self.bank, file_name="s.csv", content=csv.encode()).new_lines[0]
        item = move_to_suspense(line, reason="?")
        supplier_ledger = party_account(self.entity, self.supplier, payable=True)
        with self.assertRaises(AccountingError) as ctx:  # money IN cannot settle a purchase bill
            reclassify_suspense(item, target=supplier_ledger, note="n", allocations=[(a, D("500"))])
        self.assertEqual(ctx.exception.code, "direction_mismatch")
        s1 = post(invoice_from_trade(h.trade("SALE", self.lm, self.customer, D("5000.00")).pk))
        with self.assertRaises(AccountingError) as ctx:
            reclassify_suspense(item, target=party_account(self.entity, self.customer, payable=False), note="n",
                                allocations=[(s1, D("5000"))])
        self.assertEqual(ctx.exception.code, "over_allocation")

    def test_h4_contra_matches_on_both_banks(self):
        bank_b = h.bank(self.entity, number="B-2")
        post_voucher(entity=self.entity, voucher_type="CONTRA", voucher_date=date(2026, 5, 3),
                     lines=[dr(self.bank.account, D("50000")), cr(bank_b.account, D("50000"))],
                     narration="transfer", source_type="MANUAL", source_id=99)
        import_statement(self.bank, file_name="a.csv",
                         content=b"Date,Narration,Debit,Credit,Balance\n03/05/2026,TRF FROM B,,50000.00,50000.00\n")
        import_statement(bank_b, file_name="b.csv",
                         content=b"Date,Narration,Debit,Credit,Balance\n03/05/2026,TRF TO A,50000.00,,-50000.00\n")
        auto_match(self.bank)
        auto_match(bank_b)
        self.assertEqual(set(StatementLine.objects.values_list("status", flat=True)), {LineStatus.MATCHED})
        self.assertEqual(bank_reconciliation(bank_b, date(2026, 5, 31))["difference"], D("0.00"))

    def test_h5_resync_moves_bill_to_corrected_party(self):
        from apps.trade.models import LicenseTrade
        t = h.trade("PURCHASE", self.supplier, self.lm, D("7000.00"))
        inv = post(invoice_from_trade(t.pk))
        other = h.company("Real Supplier")
        LicenseTrade.objects.filter(pk=t.pk).update(from_company=other)
        inv = resync_trade_invoice(inv)
        self.assertEqual(inv.party_id, other.pk)
        self.assertEqual(account_balance(party_account(self.entity, self.supplier, payable=True)), D("0.00"))
        self.assertEqual(account_balance(party_account(self.entity, other, payable=True)), D("-7000.00"))

    def test_m3_identical_same_day_repayments_both_post(self):
        loan = create_loan(entity=self.entity, party=self.customer, direction="GIVEN", principal=D("100000"),
                           interest_rate=D("0"), start_date=date(2026, 4, 1), bank_account=self.bank)
        record_repayment(loan, on=date(2026, 5, 1), principal=D("10000"))
        record_repayment(loan, on=date(2026, 5, 1), principal=D("10000"))
        self.assertEqual(principal_outstanding(loan), D("80000.00"))

    def test_m4_ageing_as_of_ignores_later_settlements(self):
        bill = self._purchase_bill()
        record_payment(entity=self.entity, direction="PAYMENT", party=self.supplier, bank_account=self.bank,
                       payment_date=date(2026, 6, 10), amount=D("10000"), allocations=[(bill, D("10000"))])
        self.assertEqual(ageing(self.entity, receivable=False, as_of=date(2026, 5, 31))["totals"]["total"], D("10000.00"))
        self.assertEqual(ageing(self.entity, receivable=False, as_of=date(2026, 6, 30))["totals"]["total"], D("0"))

    def test_bounced_cheque_reconciles_and_past_brs_is_stable(self):
        """Reversing a cleared receipt keeps its bank match; the reversal matches the bank's return line."""
        p = record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                           payment_date=date(2026, 5, 20), amount=D("1000"), reference="CHQ000111")
        import_statement(self.bank, file_name="may.csv",
                         content=b"Date,Narration,Ref,Debit,Credit,Balance\n20/05/2026,CHQ DEP,CHQ000111,,1000.00,1000.00\n")
        auto_match(self.bank)
        self.assertEqual(bank_reconciliation(self.bank, date(2026, 5, 31))["difference"], D("0.00"))
        reverse_payment(p, reason="cheque returned", reversal_date=date(2026, 6, 10))
        self.assertEqual(StatementLine.objects.get().status, LineStatus.MATCHED)  # the deposit really happened
        self.assertEqual(bank_reconciliation(self.bank, date(2026, 5, 31))["difference"], D("0.00"))  # past is stable
        import_statement(self.bank, file_name="jun.csv",
                         content=b"Date,Narration,Ref,Debit,Credit,Balance\n10/06/2026,CHQ RETURN,CHQ000111,1000.00,,0.00\n")
        auto_match(self.bank)
        self.assertEqual(set(StatementLine.objects.values_list("status", flat=True)), {LineStatus.MATCHED})
        brs = bank_reconciliation(self.bank, date(2026, 6, 30))
        self.assertEqual((brs["difference"], brs["unpresented"], brs["book_balance"]), (D("0.00"), [], D("0.00")))

    def test_payment_reversed_before_reaching_bank_nets_off(self):
        p = record_payment(entity=self.entity, direction="PAYMENT", party=self.supplier, bank_account=self.bank,
                           payment_date=date(2026, 5, 2), amount=D("300"))
        reverse_payment(p, reason="entered twice", reversal_date=date(2026, 5, 3))
        self.assertEqual(bank_reconciliation(self.bank, date(2026, 5, 31))["unpresented"], [])

    def test_m6_cash_flow_is_exact_with_tds_on_interest(self):
        loan = create_loan(entity=self.entity, party=self.customer, direction="TAKEN", principal=D("1000"),
                           interest_rate=D("0"), start_date=date(2026, 4, 1), bank_account=self.bank)
        post_voucher(entity=self.entity, voucher_type="LOAN_REPAYMENT", voucher_date=date(2026, 5, 1), lines=[
            cr(self.bank.account, D("1090")), dr(loan.principal_account, D("1000")),
            dr(system_account(self.entity, "INTEREST_EXPENSE"), D("100")),
            cr(system_account(self.entity, "TDS_PAYABLE"), D("10"))], narration="repay", source_type="TEST", source_id=1)
        cf = cash_flow(self.entity, date(2026, 4, 1), date(2027, 3, 31))
        self.assertEqual(cf["sections"]["financing"], D("0.00"))  # +1000 received, -1000 repaid
        self.assertEqual(cf["sections"]["operating"], D("-90.00"))
        self.assertTrue(cf["agrees_with_ledger"])

    def test_m7_tds_threshold_recomputed_at_posting(self):
        section = h.tds_section(code="194C", rate="1.000", threshold="30000.00", mode="FULL")
        acct = system_account(self.entity, "FREIGHT")
        carrier = h.company("Carrier Pvt Ltd", pan="AAACC0000C")
        a = create_invoice(entity=self.entity, kind="EXPENSE", party=carrier, number="E1",
                           invoice_date=date(2026, 5, 1), tds_section=section, lines=[LineInput(acct, D("20000"))])
        self.assertEqual(a.tds_amount, D("0.00"))  # alone it is below the 30,000 threshold
        b = create_invoice(entity=self.entity, kind="EXPENSE", party=carrier, number="E2",
                           invoice_date=date(2026, 5, 2), tds_section=section, lines=[LineInput(acct, D("20000"))])
        post(a)
        b = post(b)
        # FULL mode: crossing the 30,000 aggregate makes TDS due on the whole 40,000 (catch-up of bill A).
        self.assertEqual(b.tds_amount, D("400.00"))

    def test_manual_voucher_reverse_still_allowed(self):
        from apps.accounting.services.posting import create_draft, post_draft
        v = post_draft(create_draft(entity=self.entity, voucher_type="JOURNAL", voucher_date=date(2026, 5, 1),
                                    lines=[dr(self.bank.account, D("1")), cr(system_account(self.entity, "CAPITAL"), D("1"))],
                                    narration="j"))
        rev = reverse_manual_voucher(v, reason="test")
        self.assertEqual(rev.reversal_of_id, v.pk)
        self.assertEqual(Voucher.objects.get(pk=v.pk).status, "REVERSED")

    def test_zero_weight_allocation_is_a_clean_error(self):
        t = h.trade("SALE", self.lm, self.customer, D("100"), qty=D("0"))
        with self.assertRaises(AccountingError):
            create_invoice(entity=self.entity, kind="EXPENSE", party=self.supplier, number="Z",
                           invoice_date=date(2026, 5, 1),
                           lines=[LineInput(system_account(self.entity, "FREIGHT"), D("10"),
                                            allocation={"method": "QUANTITY", "trade_ids": [t.pk]})])

    def test_split_match_is_unchanged(self):
        r1 = record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                            payment_date=date(2026, 5, 2), amount=D("100"))
        line = import_statement(self.bank, file_name="x.csv",
                                content=b"Date,Narration,Debit,Credit,Balance\n02/05/2026,X,,250.00,250.00\n").new_lines[0]
        manual_match(line, [(r1.voucher, D("100"))])
        line.refresh_from_db()
        self.assertEqual(line.status, LineStatus.PARTIAL)
