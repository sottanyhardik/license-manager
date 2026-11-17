"""Scenarios 3 (expense), 6 (historical migration), 7 (full chain to TB/P&L/BS), loans, consolidation."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.models import Invoice, MigrationItem, Voucher
from apps.accounting.selectors.ledger import account_balance, trial_balance
from apps.accounting.selectors.reports import (
    ageing, balance_sheet, cash_flow, consolidated, dashboard, profit_and_loss, trade_profitability,
)
from apps.accounting.services import AccountingError
from apps.accounting.services.chart import system_account
from apps.accounting.services.invoices import (
    LineInput, confirm_invoice, create_invoice, invoice_from_trade, outstanding, post_invoice,
)
from apps.accounting.services.loans import (
    accrue_interest, close_loan, create_loan, interest_outstanding, principal_outstanding, record_repayment,
)
from apps.accounting.services.migration import dry_run, execute, reconcile
from apps.accounting.services.payments import record_payment

from . import helpers as h

D = Decimal
FY = (date(2026, 4, 1), date(2027, 3, 31))


def post(inv):
    confirm_invoice(inv)
    return post_invoice(inv)


class FullChainTests(TestCase):
    """Scenario 7: trade -> invoice -> voucher -> ledger -> payment -> bank -> settlement -> TB, P&L, BS."""

    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.bank = h.bank(self.entity, opening=D("500000.00"))
        self.supplier = h.company("Exporter Pvt Ltd", gst="27AAACE0000A1Z5")
        self.customer = h.company("Importer Ltd", gst="24AAACI0000A1Z5")
        self.transporter = h.company("Freight Movers", gst="27AAACF0000A1Z5")

    def test_chain(self):
        purchase = h.trade("PURCHASE", self.supplier, self.lm, D("300000.00"), on=date(2026, 5, 1))
        sale = h.trade("SALE", self.lm, self.customer, D("360000.00"), on=date(2026, 6, 1))
        p_inv = post(invoice_from_trade(purchase.pk))
        s_inv = post(invoice_from_trade(sale.pk))
        # Scenario 3: trade-linked freight expense with GST, allocated to the sale trade.
        exp = post(create_invoice(
            entity=self.entity, kind="EXPENSE", party=self.transporter, number="FM/77", invoice_date=date(2026, 6, 2),
            lines=[LineInput(system_account(self.entity, "FREIGHT"), D("10000.00"), "Courier", gst_rate=D("18"),
                             allocation={"method": "VALUE", "trade_ids": [sale.pk]})]))
        self.assertEqual(exp.gross_amount, D("11800.00"))
        record_payment(entity=self.entity, direction="PAYMENT", party=self.supplier, bank_account=self.bank,
                       payment_date=date(2026, 5, 5), amount=D("300000.00"), allocations=[(p_inv, D("300000.00"))])
        record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                       payment_date=date(2026, 6, 20), amount=D("360000.00"), allocations=[(s_inv, D("360000.00"))])
        record_payment(entity=self.entity, direction="PAYMENT", party=self.transporter, bank_account=self.bank,
                       payment_date=date(2026, 6, 25), amount=D("11800.00"), allocations=[(exp, D("11800.00"))])
        self.assertEqual([outstanding(i) for i in (p_inv, s_inv, exp)], [D("0.00")] * 3)

        tb = trial_balance(self.entity, start=FY[0], end=FY[1], fy_start=FY[0])
        self.assertTrue(tb["balanced"])
        pl = profit_and_loss(self.entity, *FY)
        self.assertTrue(pl["agrees_with_ledger"])
        self.assertEqual(pl["net_sales"], D("360000.00"))
        self.assertEqual(pl["gross_profit"], D("50000.00"))  # 360k - 300k purchase - 10k freight
        self.assertEqual(pl["net_profit"], D("50000.00"))
        bs = balance_sheet(self.entity, FY[1])
        self.assertTrue(bs["balanced"])
        self.assertEqual(account_balance(self.bank.account), D("548200.00"))
        cf = cash_flow(self.entity, *FY)
        self.assertTrue(cf["agrees_with_ledger"])
        prof = trade_profitability(self.entity, *FY)
        by_trade = {r["trade_id"]: r for r in prof["rows"]}
        self.assertEqual(by_trade[sale.pk]["revenue"], D("360000.00"))
        self.assertEqual(by_trade[sale.pk]["expenses"], D("10000.00"))
        self.assertEqual(by_trade[purchase.pk]["direct_cost"], D("300000.00"))
        dash = dashboard(self.entity, *FY)
        self.assertEqual(dash["bank_balance"], D("548200.00"))
        self.assertEqual(dash["receivables"], D("0"))

    def test_ageing_buckets(self):
        s_inv = post(invoice_from_trade(h.trade("SALE", self.lm, self.customer, D("1000.00"),
                                                on=date(2026, 5, 1)).pk, credit_days=30))
        report = ageing(self.entity, receivable=True, as_of=date(2026, 7, 15))  # due 31-05, 45 days overdue
        self.assertEqual(report["totals"]["31-60"], D("1000.00"))
        self.assertEqual(outstanding(s_inv), D("1000.00"))


class LoanTests(TestCase):
    def setUp(self):
        self.entity = h.books(h.company("Labdhi Global LLP"))
        self.bank = h.bank(self.entity, opening=D("2000000.00"))
        self.lender = h.company("Family Trust")

    def test_loan_taken_principal_never_hits_pl_and_interest_accrues(self):
        loan = create_loan(entity=self.entity, party=self.lender, direction="TAKEN", principal=D("1000000.00"),
                           interest_rate=D("12"), start_date=date(2026, 4, 1), bank_account=self.bank)
        self.assertEqual(principal_outstanding(loan), D("1000000.00"))
        pl = profit_and_loss(self.entity, *FY)
        self.assertEqual(pl["net_profit"], D("0"))
        acc = accrue_interest(loan, period_end=date(2026, 4, 30))  # 30 days @12% on 10L = 9,863.01
        self.assertEqual(acc.amount, D("9863.01"))
        self.assertEqual(accrue_interest(loan, period_end=date(2026, 4, 30)).pk, acc.pk)  # idempotent
        self.assertEqual(interest_outstanding(loan), D("9863.01"))
        record_repayment(loan, on=date(2026, 5, 15), principal=D("400000.00"), interest=D("9863.01"))
        self.assertEqual(principal_outstanding(loan), D("600000.00"))
        # May: 1-14 on 10L (accrued at repayment) ; then 15-31 on 6L
        accrue_interest(loan, period_end=date(2026, 5, 31))
        expected = D("4602.74") + D("3353.42")
        self.assertEqual(interest_outstanding(loan), expected)
        pl = profit_and_loss(self.entity, *FY)
        self.assertEqual(pl["lines"]["interest_expense"]["amount"], D("9863.01") + expected)

    def test_closed_loan_stops_accruing(self):
        loan = create_loan(entity=self.entity, party=self.lender, direction="GIVEN", principal=D("100000.00"),
                           interest_rate=D("10"), start_date=date(2026, 4, 1), bank_account=self.bank)
        accrue_interest(loan, period_end=date(2026, 4, 30))
        record_repayment(loan, on=date(2026, 4, 30), principal=D("100000.00"), interest=interest_outstanding(loan))
        close_loan(loan, on=date(2026, 4, 30))
        loan.refresh_from_db()
        self.assertEqual((principal_outstanding(loan), interest_outstanding(loan)), (D("0"), D("0")))
        accruals = loan.accruals.count()
        accrue_interest(loan, period_end=date(2026, 6, 30))
        self.assertEqual(loan.accruals.count(), accruals)  # nothing accrues after closure
        self.assertEqual(interest_outstanding(loan), D("0"))
        with self.assertRaises(AccountingError):
            record_repayment(loan, on=date(2026, 6, 1), interest=D("1"))


class MigrationTests(TestCase):
    """Scenario 6: inventory -> dry run -> already/missing accounting -> execute -> reconcile -> no duplicates."""

    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP")
        self.entity = h.books(self.lm, start=date(2025, 4, 1))
        self.bank = h.bank(self.entity, number="999")
        self.supplier = h.company("Old Supplier")
        self.customer = h.company("Old Customer")

    def test_dry_run_execute_reconcile(self):
        from apps.trade.models import LicenseTradePayment
        old_p = h.trade("PURCHASE", self.supplier, self.lm, D("1000.00"), on=date(2025, 6, 1))
        old_s = h.trade("SALE", self.lm, self.customer, D("1500.00"), on=date(2025, 7, 1))
        LicenseTradePayment.objects.create(trade=old_s, date=date(2025, 7, 10), amount=D("1500.00"), note="NEFT")
        no_party = h.trade("SALE", self.lm, self.customer, D("50.00"), on=date(2025, 8, 1))
        type(no_party).objects.filter(pk=no_party.pk).update(to_company=None)
        already = h.trade("SALE", self.lm, self.customer, D("70.00"), on=date(2026, 5, 1))
        post(invoice_from_trade(already.pk))

        run = dry_run(self.entity)
        cls = {(i.source_type, i.source_id): i.classification for i in run.items.all()}
        self.assertEqual(cls[("TRADE", old_p.pk)], "READY")
        self.assertEqual(cls[("TRADE", no_party.pk)], "NEEDS_REVIEW")
        self.assertEqual(cls[("TRADE", already.pk)], "ALREADY_ACCOUNTED")
        self.assertEqual(Voucher.objects.filter(source_type="INVOICE").count(), 1, "dry run must not post")

        with self.assertRaises(AccountingError):
            execute(self.entity, bank_account=self.bank, confirm=False)
        run2 = execute(self.entity, bank_account=self.bank, confirm=True)
        outcomes = {(i.source_type, i.source_id): i.outcome for i in run2.items.all()}
        self.assertEqual(outcomes[("TRADE", old_p.pk)], "MIGRATED")
        self.assertEqual(outcomes[("TRADE", no_party.pk)], "SKIPPED")
        self.assertEqual(outcomes[("TRADE", already.pk)], "SKIPPED")
        self.assertEqual(outstanding(Invoice.objects.get(trade=old_s)), D("0.00"))

        # Re-running is a no-op: nothing is posted twice.
        vouchers = Voucher.objects.count()
        execute(self.entity, bank_account=self.bank, confirm=True)
        self.assertEqual(Voucher.objects.count(), vouchers)
        rec = reconcile(self.entity)
        self.assertEqual(rec["2025-26"]["difference"], D("50.00"))  # the unpostable trade stays visible
        self.assertEqual(rec["2026-27"]["difference"], D("0.00"))
        self.assertTrue(MigrationItem.objects.filter(run=run2, outcome="SKIPPED", source_id=no_party.pk).exists())


class ConsolidationTests(TestCase):
    def test_intercompany_eliminated(self):
        from apps.trade.services.trade_service import copy_sale_to_purchase
        lm, lg = h.company("Labdhi Mercantile LLP"), h.company("Labdhi Global LLP")
        e_lm, e_lg = h.books(lm), h.books(lg)
        outsider = h.company("Final Buyer")
        sale = h.trade("SALE", lm, lg, D("100000.00"))
        _s, purchase, _ = copy_sale_to_purchase(sale.pk)
        post(invoice_from_trade(sale.pk))
        post(invoice_from_trade(purchase.pk))
        post(invoice_from_trade(h.trade("SALE", lg, outsider, D("130000.00")).pk))
        report = consolidated([e_lm, e_lg], *FY)
        self.assertEqual(report["eliminations"]["eliminated"], D("100000.00"))
        self.assertEqual(report["eliminations"]["unmatched_difference"], D("0.00"))
        self.assertEqual(report["eliminations"]["intercompany_balance_difference"], D("0.00"))
        self.assertEqual(report["profit_and_loss"]["net_sales"], D("130000.00"))
        # group profit = 1,00,000 (LM, no external cost in this test) + 30,000 (LG) — intercompany nets out
        self.assertEqual(report["profit_and_loss"]["net_profit"], D("130000.00"))
        self.assertEqual(report["profit_and_loss"]["lines"]["purchases"], D("0.00"))
        # entity books stay separate
        self.assertEqual(profit_and_loss(e_lm, *FY)["net_profit"], D("100000.00"))
        self.assertEqual(profit_and_loss(e_lg, *FY)["net_profit"], D("30000.00"))
