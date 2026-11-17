"""Regression tests for the second review round (independent ERP audit C1–C2, H1–H4, M1–M9; DB and
security reviews). Each test reproduces the auditor's scenario and asserts the corrected result."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounting.models import AccountingAuditEvent, LineStatus, StatementLine, Voucher
from apps.accounting.selectors.ledger import account_balance
from apps.accounting.selectors.reports import balance_sheet, cash_flow, consolidated
from apps.accounting.services import AccountingError
from apps.accounting.services.banking import (
    auto_match, import_statement, move_to_suspense, reclassify_suspense,
)
from apps.accounting.services.books import party_account, set_period_lock
from apps.accounting.services.chart import system_account
from apps.accounting.services.invoices import (
    LineInput, confirm_invoice, create_invoice, invoice_from_trade, outstanding, payment_status, post_invoice,
    resync_trade_invoice,
)
from apps.accounting.services.loans import create_loan, interest_outstanding, record_repayment
from apps.accounting.services.masters import configure_books
from apps.accounting.services.migration import dry_run, execute
from apps.accounting.services.payments import account_trade_payment, allocate_on_account, record_payment
from apps.accounting.services.posting import cr, create_draft, dr, post_draft, post_voucher, reverse_manual_voucher
from apps.accounts.models import User

from . import helpers as h

D = Decimal
FY = (date(2026, 4, 1), date(2027, 3, 31))


def post(inv):
    confirm_invoice(inv)
    return post_invoice(inv)


class CashAndSettlementTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.bank = h.bank(self.entity)
        self.customer = h.company("Importer Ltd", gst="27AAACI0000A1Z5")

    def test_c1_trade_payment_after_manual_receipt_is_linked_not_double_counted(self):
        from apps.trade.models import LicenseTradePayment
        t = h.trade("SALE", self.lm, self.customer, D("10000.00"))
        inv = post(invoice_from_trade(t.pk))
        manual = record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                                payment_date=date(2026, 5, 20), amount=D("10000"), allocations=[(inv, D("10000"))])
        tp = LicenseTradePayment.objects.create(trade=t, date=date(2026, 5, 20), amount=D("10000.00"), note="NEFT")
        with self.assertRaises(AccountingError) as ctx:
            account_trade_payment(tp.pk, bank_account=self.bank)
        self.assertEqual(ctx.exception.code, "possible_duplicate")
        linked = account_trade_payment(tp.pk, bank_account=None, existing_payment=manual)
        self.assertEqual(linked.pk, manual.pk)
        self.assertEqual(account_balance(self.bank.account), D("10000.00"))  # counted once

    def test_m1_notes_are_not_overdue_bills_and_are_capped(self):
        bill = post(invoice_from_trade(h.trade("SALE", self.lm, self.customer, D("10000.00")).pk))
        record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                       payment_date=date(2026, 5, 20), amount=D("8000"), allocations=[(bill, D("8000"))])
        cn = post(create_invoice(entity=self.entity, kind="CREDIT_NOTE", party=self.customer, number="CN1",
                                 invoice_date=date(2026, 5, 25), against_invoice=bill,
                                 lines=[LineInput(system_account(self.entity, "SALES_RETURNS"), D("5000"))]))
        self.assertEqual(outstanding(bill), D("0.00"))
        self.assertEqual(outstanding(cn), D("3000.00"))  # unapplied credit, visible
        self.assertEqual(payment_status(cn), "UNAPPLIED_CREDIT")
        with self.assertRaises(AccountingError) as ctx:
            create_invoice(entity=self.entity, kind="CREDIT_NOTE", party=self.customer, number="CN2",
                           invoice_date=date(2026, 5, 25), against_invoice=bill,
                           lines=[LineInput(system_account(self.entity, "SALES_RETURNS"), D("10001"))])
        self.assertEqual(ctx.exception.code, "note_exceeds_bill")

    def test_m2_suspense_reclassified_on_account_can_be_allocated_later(self):
        line = import_statement(self.bank, file_name="s.csv",
                                content=b"Date,Narration,Debit,Credit,Balance\n02/05/2026,UPI,,700.00,700.00\n").new_lines[0]
        item = move_to_suspense(line, reason="?")
        item = reclassify_suspense(item, target=party_account(self.entity, self.customer, payable=False), note="cust")
        bill = post(invoice_from_trade(h.trade("SALE", self.lm, self.customer, D("700.00")).pk))
        allocate_on_account(item.resolution_voucher, bill, D("700"))
        self.assertEqual(outstanding(bill), D("0.00"))
        with self.assertRaises(AccountingError):
            allocate_on_account(item.resolution_voucher, bill, D("1"))

    def test_m5_customer_tds_cannot_be_booked_twice(self):
        section = h.tds_section(code="194Q", rate="0.100", threshold="0", mode="FULL")
        inv = post(create_invoice(entity=self.entity, kind="SALES", party=self.customer, number="S1",
                                  invoice_date=date(2026, 5, 1), tds_section=section,
                                  lines=[LineInput(system_account(self.entity, "SALES"), D("100000"))]))
        with self.assertRaises(AccountingError) as ctx:
            record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                           payment_date=date(2026, 5, 2), amount=D("99800"), tds_amount=D("100"),
                           allocations=[(inv, D("99900"))])
        self.assertEqual(ctx.exception.code, "tds_already_on_bill")

    def test_m9_two_equal_receipts_near_the_line_stay_ambiguous(self):
        for d in (date(2026, 5, 7), date(2026, 5, 8)):
            record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                           payment_date=d, amount=D("5000"))
        import_statement(self.bank, file_name="x.csv",
                         content=b"Date,Narration,Debit,Credit,Balance\n10/05/2026,NEFT CR,,5000.00,5000.00\n")
        self.assertEqual(auto_match(self.bank).get("ambiguous"), 1)
        self.assertEqual(StatementLine.objects.get().status, LineStatus.UNMATCHED)


class TaxTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.vendor = h.company("Transport Co", gst="27AAACT0000T1Z5", pan="AAACT0000T")

    def _bill(self, number, amount, section, on=date(2026, 5, 1), party=None):
        return post(create_invoice(entity=self.entity, kind="EXPENSE", party=party or self.vendor, number=number,
                                   invoice_date=on, tds_section=section,
                                   lines=[LineInput(system_account(self.entity, "FREIGHT"), D(amount))]))

    def test_h2_full_mode_catches_up_the_whole_aggregate_once(self):
        section = h.tds_section(code="194C", rate="1.000", threshold="100000", mode="FULL")
        tds = [self._bill(f"F{i}", "25000", section).tds_amount for i in range(3)]
        self.assertEqual(tds, [D("0.00")] * 3)
        fourth = self._bill("F4", "30000", section)
        self.assertEqual(fourth.tds_amount, D("1050.00"))  # 1% of 1,05,000
        fifth = self._bill("F5", "10000", section)
        self.assertEqual(fifth.tds_amount, D("100.00"))  # no second catch-up

    def test_h4_lower_deduction_certificate_limit(self):
        from apps.accounting.models import LowerDeductionCertificate
        section = h.tds_section(code="194J", rate="10.000", threshold="0", mode="FULL")
        LowerDeductionCertificate.objects.create(party=self.vendor, section_code="194J", certificate_no="LDC1",
                                                 rate=D("2"), valid_from=date(2026, 4, 1), valid_to=date(2027, 3, 31),
                                                 amount_limit=D("100000"))
        self.assertEqual(self._bill("J1", "100000", section).tds_amount, D("2000.00"))
        self.assertEqual(self._bill("J2", "100000", section).tds_amount, D("10000.00"))  # limit used up

    def test_m4_unregistered_recipient_is_intra_state(self):
        consumer = h.company("Walk-in Buyer")  # no GSTIN
        inv = create_invoice(entity=self.entity, kind="COMMISSION_RECEIVABLE", party=consumer, number="C1",
                             invoice_date=date(2026, 5, 1),
                             lines=[LineInput(system_account(self.entity, "COMMISSION_INCOME"), D("10000"),
                                              gst_rate=D("18"))])
        self.assertEqual((inv.cgst, inv.sgst, inv.igst), (D("900.00"), D("900.00"), D("0.00")))


class ConsolidationAndReportsTests(TestCase):
    def test_h1_only_intra_group_dealings_are_eliminated(self):
        a, b, c, d = (h.company(n) for n in ("A2", "B2", "C2", "D2"))
        ea, eb, _ec, _ed = (h.books(x) for x in (a, b, c, d))
        post(invoice_from_trade(h.trade("SALE", a, c, D("500000")).pk))      # A2 -> C2 (outside the set)
        post(invoice_from_trade(h.trade("PURCHASE", d, b, D("500000")).pk))  # B2 <- D2 (outside the set)
        report = consolidated([ea, eb], *FY)
        self.assertEqual(report["eliminations"]["eliminated"], D("0"))

    def test_c2_unrealised_profit_warning_and_stock_reserve(self):
        from apps.trade.services.trade_service import copy_sale_to_purchase
        a, b, s = h.company("Group A"), h.company("Group B"), h.company("Supplier S")
        ea, eb = h.books(a), h.books(b)
        post(invoice_from_trade(h.trade("PURCHASE", s, a, D("800000")).pk))
        sale = h.trade("SALE", a, b, D("1000000"))
        _x, purchase, _ = copy_sale_to_purchase(sale.pk)
        post(invoice_from_trade(sale.pk))
        post(invoice_from_trade(purchase.pk))
        post_draft(create_draft(entity=eb, voucher_type="JOURNAL", voucher_date=date(2027, 3, 31),
                                lines=[dr(system_account(eb, "CLOSING_STOCK"), D("1000000")),
                                       cr(system_account(eb, "STOCK_CHANGE"), D("1000000"))], narration="closing stock"))
        plain = consolidated([ea, eb], *FY)
        self.assertTrue(any("unrealised" in w for w in plain["warnings"]))
        self.assertEqual(plain["profit_and_loss"]["gross_profit"], D("200000.00"))
        reserved = consolidated([ea, eb], *FY, stock_reserve=D("200000"))
        self.assertEqual(reserved["profit_and_loss"]["gross_profit"], D("0.00"))
        self.assertFalse(any("unrealised" in w for w in reserved["warnings"]))
        self.assertTrue(reserved["balance_sheet"]["balanced"])

    def test_ic_commission_is_eliminated(self):
        a, b = h.company("Comm A"), h.company("Comm B")
        ea, eb = h.books(a), h.books(b)
        post(invoice_from_trade(h.trade("COMMISSION_SALE", a, b, D("50000")).pk))
        post(invoice_from_trade(h.trade("COMMISSION_PURCHASE", a, b, D("50000")).pk))
        report = consolidated([ea, eb], *FY)
        self.assertEqual(report["eliminations"]["commission"]["eliminated"], D("50000.00"))
        self.assertEqual(report["profit_and_loss"]["lines"]["commission_income"], D("0.00"))

    def test_m3_cash_flow_opening_balance_is_not_operating_cash(self):
        e = h.books(h.company("CF Co"))
        bank = h.bank(e, opening=D("1000000"))
        cf = cash_flow(e, *FY)
        self.assertEqual((cf["opening_cash"], cf["sections"]["operating"]), (D("1000000.00"), D("0")))
        self.assertTrue(cf["agrees_with_ledger"])
        self.assertEqual(account_balance(bank.account), D("1000000.00"))

    def test_overdraft_is_a_liability(self):
        e = h.books(h.company("OD Co"))
        h.bank(e, opening=D("-5000"))
        bs = balance_sheet(e, FY[1])
        self.assertIn("BANK_OVERDRAFT", {x["head"] for x in bs["liabilities"]})
        self.assertTrue(bs["balanced"])


class LifecycleTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP")
        self.entity = h.books(self.lm)
        self.bank = h.bank(self.entity)
        self.supplier = h.company("Exporter Pvt Ltd")

    def test_m6_resync_in_locked_period_reposts_in_open_period(self):
        from apps.trade.models import LicenseTradeLine
        t = h.trade("PURCHASE", self.supplier, self.lm, D("1000.00"), on=date(2026, 4, 10))
        inv = post(invoice_from_trade(t.pk))
        set_period_lock(self.entity.financial_years.get().periods.get(period_no=1), True)
        LicenseTradeLine.objects.filter(trade=t).update(amount_inr=D("1200.00"), cif_inr=D("1200.00"))
        t.recompute_totals()
        inv = resync_trade_invoice(inv)
        self.assertEqual(inv.status, "POSTED")
        self.assertNotEqual(inv.voucher.date.month, 4)
        self.assertEqual(account_balance(party_account(self.entity, self.supplier, payable=True)), D("-1200.00"))

    def test_m7_backdated_repayment_trues_up_interest(self):
        borrower = h.company("Borrower")
        loan = create_loan(entity=self.entity, party=borrower, direction="GIVEN", principal=D("100000"),
                           interest_rate=D("10"), start_date=date(2026, 5, 1), bank_account=self.bank)
        from apps.accounting.services.loans import accrue_interest
        accrue_interest(loan, period_end=date(2026, 5, 31))  # 31 days on 1L = 849.32
        record_repayment(loan, on=date(2026, 5, 15), principal=D("100000"))
        # interest due is only 1-14 May on 1L = 383.56
        self.assertEqual(interest_outstanding(loan), D("383.56"))

    def test_m8_in_period_payment_of_pre_books_trade_is_migrated_on_account(self):
        from apps.trade.models import LicenseTradePayment
        customer = h.company("Old Customer")
        t = h.trade("SALE", self.lm, customer, D("30000"), on=date(2026, 3, 15))  # before books start (1 Apr)
        tp = LicenseTradePayment.objects.create(trade=t, date=date(2026, 4, 10), amount=D("30000"), note="late")
        items = {(i.source_type, i.source_id): i.classification for i in dry_run(self.entity).items.all()}
        self.assertEqual(items[("TRADE_PAYMENT", tp.pk)], "READY")
        execute(self.entity, bank_account=self.bank, confirm=True)
        self.assertEqual(account_balance(self.bank.account), D("30000.00"))
        self.assertEqual(account_balance(party_account(self.entity, customer, payable=False)), D("-30000.00"))

    def test_maker_checker_covers_bills_and_reversals(self):
        maker, checker = (User.objects.create_user(username=n, password="x") for n in ("mk", "ck"))
        configure_books(self.entity, require_maker_checker=True, user=checker)
        ev = AccountingAuditEvent.objects.filter(action="BOOKS_CONFIGURED").latest("id")
        self.assertEqual(ev.detail["changes"]["require_maker_checker"], [False, True])
        inv = create_invoice(entity=self.entity, kind="EXPENSE", party=self.supplier, number="E", user=maker,
                             invoice_date=date(2026, 5, 1),
                             lines=[LineInput(system_account(self.entity, "RENT"), D("100"))])
        from apps.accounting.models import Invoice
        Invoice.objects.filter(pk=inv.pk).update(created_by=maker)
        confirm_invoice(inv, user=maker)
        with self.assertRaises(AccountingError):
            post_invoice(inv, user=maker)
        inv = post_invoice(inv, user=checker)
        v = post_draft(create_draft(entity=self.entity, voucher_type="JOURNAL", voucher_date=date(2026, 5, 2),
                                    lines=[dr(self.bank.account, D("1")), cr(system_account(self.entity, "CAPITAL"), D("1"))],
                                    narration="j", user=maker), user=checker)
        with self.assertRaises(AccountingError):
            reverse_manual_voucher(v, reason="x", user=checker)
        reverse_manual_voucher(v, reason="x", user=maker)

    def test_posted_voucher_narration_and_poster_frozen_in_db(self):
        v, _ = post_voucher(entity=self.entity, voucher_type="JOURNAL", voucher_date=date(2026, 5, 1),
                            lines=[dr(self.bank.account, D("5")), cr(system_account(self.entity, "CAPITAL"), D("5"))],
                            narration="orig", source_type="TEST", source_id=1)
        for field, value in (("narration", "edited"), ("posted_at", None), ("source_event", "X")):
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    Voucher.objects.filter(pk=v.pk).update(**{field: value})


class ApiHardeningTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP")
        self.entity = h.books(self.lm)
        user = User.objects.create_user(username="viewer1", password="x")
        user.groups.add(Group.objects.get_or_create(name="ACCOUNTS_APPROVER")[0])
        self.client = APIClient()
        self.client.force_authenticate(user)

    def test_bad_filter_ids_are_400_not_500(self):
        r = self.client.get(f"/api/accounting/invoices/?entity={self.lm.pk}&party_id=abc")
        self.assertEqual(r.status_code, 400)
        r = self.client.get(f"/api/accounting/payments/?entity={self.lm.pk}&bank_account_id=x")
        self.assertEqual(r.status_code, 400)

    def test_statement_row_cap(self):
        from apps.accounting.services import banking
        bank = h.bank(self.entity)
        rows = "Date,Narration,Debit,Credit,Balance\n" + "".join(
            f"01/05/2026,R{i},,1.00,{i}.00\n" for i in range(banking.MAX_ROWS + 2))
        with self.assertRaises(AccountingError) as ctx:
            import_statement(bank, file_name="big.csv", content=rows.encode())
        self.assertEqual(ctx.exception.code, "too_many_rows")
