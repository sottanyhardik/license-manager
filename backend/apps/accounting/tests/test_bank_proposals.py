"""Invoice proposals for bank lines: propose -> human confirms -> one receipt/payment via the central engine,
oldest bills first, excess as advance, learned narration aliases, and the duplicate guards."""
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.accounting.models import BankMatch, LineStatus, NarrationAlias, Payment, StatementLine, Voucher
from apps.accounting.services import AccountingError
from apps.accounting.services.bank_proposals import (
    confirm_many, confirm_proposal, counterparty_key, name_score, proposal_for, proposals_for,
)
from apps.accounting.services.banking import import_statement
from apps.accounting.services.invoices import confirm_invoice, invoice_from_trade, outstanding, post_invoice
from apps.accounting.services.payments import record_payment

from . import helpers as h
from .test_api import client_with

D = Decimal


def posted(trade):
    inv = invoice_from_trade(trade.pk)
    confirm_invoice(inv)
    return post_invoice(inv)


class NarrationParsingTests(SimpleTestCase):
    def test_counterparty_key_drops_channel_words_utrs_and_bank_codes(self):
        self.assertEqual(counterparty_key("RTGS-HDFCR52025031012345-ABC EXIM PVT LTD"), "ABC EXIM PVT LTD")
        self.assertEqual(counterparty_key("522627002894-IMPS CIB JASH MERCAN"), "JASH MERCAN")
        self.assertEqual(counterparty_key("CHQ DEP/575378/OWMUM3/SBIN/SHIV/PUNEET CARS PVT"), "SHIV PUNEET CARS PVT")

    def test_name_score_handles_bank_truncation_and_legal_words(self):
        self.assertEqual(name_score("JASH MERCAN", "Jash Mercantile Pvt Ltd"), 1.0)
        self.assertEqual(name_score("ABC EXIM", "ABC Exim Private Limited"), 1.0)
        self.assertLess(name_score("FIRST MUMBA", "First Mumbai Traders"), 1.0)
        self.assertEqual(name_score("GOOGLEADSW", "Jash Mercantile Pvt Ltd"), 0.0)


class BankProposalTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.bank = h.bank(self.entity, opening=D("0"))
        self.customer = h.company("Jash Mercantile Pvt Ltd", gst="24AAACJ0000A1Z5")
        self.supplier = h.company("Abc Exim Pvt Ltd", gst="27AAACA0000A1Z5")
        self.old = posted(h.trade("SALE", self.lm, self.customer, D("10000.00"), on=date(2026, 5, 1)))
        self.new = posted(h.trade("SALE", self.lm, self.customer, D("20000.00"), on=date(2026, 5, 10)))
        self.future = posted(h.trade("SALE", self.lm, self.customer, D("7000.00"), on=date(2026, 6, 20)))
        self.bill = posted(h.trade("PURCHASE", self.supplier, self.lm, D("50000.00"), on=date(2026, 5, 3)))

    def _import(self, rows: str):
        csv = "Date,Narration,Ref No,Withdrawal Amt,Deposit Amt,Balance\n" + rows
        import_statement(self.bank, file_name="s.csv", content=csv.encode())
        return list(StatementLine.objects.filter(bank_account=self.bank).order_by("id"))

    def test_oldest_bills_first_and_confirm_posts_one_receipt(self):
        due_old, due_new = outstanding(self.old), outstanding(self.new)
        amount = due_old + due_new - D("5000.00")
        line, = self._import(f"15/05/2026,522627002894-IMPS CIB JASH MERCAN,522627002894,,{amount},\n")
        p = proposal_for(line)
        self.assertEqual((p.party, p.source, p.direction), (self.customer, "name", "RECEIPT"))
        self.assertEqual([(a.invoice, a.amount) for a in p.allocations], [(self.old, due_old), (self.new, due_new - 5000)])
        self.assertEqual(p.advance, D("0.00"))
        self.assertNotIn(self.future, [a.invoice for a in p.allocations])  # dated after the bank line
        self.assertEqual(p.confidence, "high")

        vouchers_before = Voucher.objects.count()
        payment = confirm_proposal(line, party=self.customer)
        self.assertEqual(Voucher.objects.count(), vouchers_before + 1)
        self.assertEqual((payment.direction, payment.amount, payment.reference, payment.mode),
                         ("RECEIPT", amount, "522627002894", "IMPS"))
        self.assertEqual((outstanding(self.old), outstanding(self.new)), (D("0.00"), D("5000.00")))
        line.refresh_from_db()
        self.assertEqual(line.status, LineStatus.MATCHED)
        self.assertEqual(line.matches.get().method, BankMatch.PROPOSAL)
        alias = NarrationAlias.objects.get(entity=self.entity)
        self.assertEqual((alias.key, alias.direction, alias.party, alias.hits), ("JASH MERCAN", "RECEIPT", self.customer, 1))
        with self.assertRaises(AccountingError) as again:  # never booked twice
            confirm_proposal(line, party=self.customer)
        self.assertEqual(again.exception.code, "already_matched")

    def test_undo_puts_the_line_back_and_nets_the_books(self):
        from apps.accounting.selectors.ledger import account_balance
        from apps.accounting.services.bank_proposals import undo_confirmation
        due = outstanding(self.old)
        line, = self._import(f"15/05/2026,522627002894-IMPS CIB JASH MERCAN,522627002894,,{due},\n")
        payment = confirm_proposal(line, party=self.customer)
        line = undo_confirmation(payment)
        self.assertEqual((line.status, line.matched_amount), (LineStatus.UNMATCHED, D("0.00")))
        payment.refresh_from_db()
        self.assertEqual(payment.status, "REVERSED")
        self.assertEqual(outstanding(self.old), due)  # the bill is open again
        self.assertEqual(account_balance(self.bank.account), D("0.00"))
        self.assertFalse(NarrationAlias.objects.exists())  # the alias it taught is forgotten
        self.assertEqual(proposal_for(line).blocked, "")  # it can be proposed and confirmed again
        confirm_proposal(line, party=self.customer)
        with self.assertRaises(AccountingError):
            undo_confirmation(payment)  # already reversed

    def test_excess_stays_on_account_as_advance(self):
        total = outstanding(self.old) + outstanding(self.new)
        line, = self._import(f"15/05/2026,NEFT JASH MERCANTILE,,,{total + D('2500.00')},\n")
        p = proposal_for(line)
        self.assertEqual(p.advance, D("2500.00"))
        self.assertEqual(p.confidence, "medium")
        payment = confirm_proposal(line, party=self.customer)
        self.assertEqual(sum(s.amount for s in payment.settlements.all()), total)

    def test_payment_side_settles_purchase_bill(self):
        due = outstanding(self.bill)
        line, = self._import(f"06/05/2026,RTGS-HDFCR52026050612345-ABC EXIM PVT LTD,,{due},,\n")
        p = proposal_for(line)
        self.assertEqual((p.party, p.direction, p.exact_bill), (self.supplier, "PAYMENT", True))
        confirm_proposal(line, party=self.supplier)
        self.assertEqual(outstanding(self.bill), D("0.00"))

    def test_learned_alias_resolves_an_unreadable_narration(self):
        first, second = self._import(
            "11/05/2026,BY TRANSFER XJ TRADING HOUSE,,,1000.00,\n12/05/2026,BY TRANSFER XJ TRADING HOUSE,,,2000.00,\n")
        self.assertIsNone(proposal_for(first).party)  # no name match: the human chooses
        confirm_proposal(first, party=self.customer)
        p = proposal_for(second)
        self.assertEqual((p.party, p.source, p.confidence), (self.customer, "alias", "high"))

    def test_existing_book_entry_or_used_utr_is_never_booked_again(self):
        record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                       payment_date=date(2026, 5, 14), amount=D("10000.00"), reference="HDFCN52026051499")
        line, = self._import("15/05/2026,NEFT CR-HDFCN52026051499-JASH MERCANTILE,HDFCN52026051499,,10000.00,\n")
        self.assertEqual(proposal_for(line).blocked, "existing_book_entry")
        self.assertEqual(proposals_for(self.bank), [])
        payments = Payment.objects.count()
        with self.assertRaises(AccountingError):
            confirm_proposal(line, party=self.customer)
        self.assertEqual(Payment.objects.count(), payments)

    def test_own_account_transfer_is_refused(self):
        line, = self._import("15/05/2026,IMPS 533908822460 FROM LABDHI MERCANTILE LLP,533908822460,,900.00,\n")
        self.assertIsNone(proposal_for(line).party)
        with self.assertRaises(AccountingError) as err:
            confirm_proposal(line, party=self.lm)
        self.assertEqual(err.exception.code, "own_account")

    def test_proposals_query_count_is_flat(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                       payment_date=date(2026, 5, 2), amount=D("10.00"))  # book pool is non-empty
        self._import("15/05/2026,NEFT JASH MERCANTILE,,,500.00,\n")
        with CaptureQueriesContext(connection) as one:
            proposals_for(self.bank)
        self._import("".join(f"1{d}/05/2026,NEFT JASH MERCANTILE {d},,,{d}00.00,\n" for d in range(6, 10)))
        with CaptureQueriesContext(connection) as five:
            self.assertEqual(len(proposals_for(self.bank)), 5)
        self.assertEqual(len(five), len(one))

    def test_confirm_many_reports_failures_without_rolling_back_others(self):
        good, bad = self._import("15/05/2026,NEFT JASH MERCANTILE,,,500.00,\n16/05/2026,TRF SELF,,,600.00,\n")
        result = confirm_many(self.bank, [(good.pk, self.customer.pk), (bad.pk, self.lm.pk), (999999, self.customer.pk)])
        self.assertEqual([c["line_id"] for c in result["confirmed"]], [good.pk])
        self.assertEqual(sorted(e["code"] for e in result["errors"]), ["not_found", "own_account"])


class BankProposalApiTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.bank = h.bank(self.entity, opening=D("0"))
        self.customer = h.company("Jash Mercantile Pvt Ltd")
        self.inv = posted(h.trade("SALE", self.lm, self.customer, D("10000.00"), on=date(2026, 5, 1)))
        csv = f"Date,Narration,Ref No,Withdrawal Amt,Deposit Amt\n15/05/2026,IMPS CIB JASH MERCAN,,,{outstanding(self.inv)}\n"
        import_statement(self.bank, file_name="s.csv", content=csv.encode())
        self.line = StatementLine.objects.get(bank_account=self.bank)
        self.approver = client_with("ACCOUNTS_APPROVER")
        self.viewer = client_with("ACCOUNTS_VIEWER")

    def test_viewer_lists_proposals_but_only_approver_confirms(self):
        r = self.viewer.get(f"/api/accounting/bank-accounts/{self.bank.pk}/proposals/")
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        row, = body["proposals"]
        self.assertEqual((row["line"]["id"], row["party"]["id"], row["confidence"], row["direction"]),
                         (self.line.pk, self.customer.pk, "high", "RECEIPT"))
        self.assertEqual(row["allocations"][0]["invoice_id"], self.inv.pk)
        self.assertEqual(body["summary"]["high"], 1)

        url = f"/api/accounting/bank-accounts/{self.bank.pk}/proposals/confirm/"
        payload = {"items": [{"line_id": self.line.pk, "party_id": self.customer.pk}]}
        self.assertEqual(self.viewer.post(url, payload, format="json").status_code, 403)
        r = self.approver.post(url, payload, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()["confirmed"]), 1)
        self.assertEqual(outstanding(self.inv), D("0.00"))
        payment_id = r.json()["confirmed"][0]["payment_id"]
        undo_url = f"/api/accounting/bank-proposals/{payment_id}/undo/"
        self.assertEqual(self.viewer.post(undo_url).status_code, 403)
        undone = self.approver.post(undo_url)
        self.assertEqual(undone.status_code, 200, undone.content)
        self.assertEqual(undone.json()["status"], "UNMATCHED")

    def test_preview_with_another_party_and_alias_list_delete(self):
        other = h.company("Some Other Party")
        r = self.viewer.get(f"/api/accounting/statement-lines/{self.line.pk}/proposal/", {"party_id": other.pk})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["party"]["id"], r.json()["source"], r.json()["advance"]),
                         (other.pk, "chosen", str(self.line.amount)))
        self.approver.post(f"/api/accounting/bank-accounts/{self.bank.pk}/proposals/confirm/",
                           {"items": [{"line_id": self.line.pk, "party_id": self.customer.pk}]}, format="json")
        aliases = self.viewer.get("/api/accounting/narration-aliases/", {"entity": self.lm.pk}).json()["aliases"]
        self.assertEqual([(a["key"], a["party_id"]) for a in aliases], [("JASH MERCAN", self.customer.pk)])
        self.assertEqual(self.viewer.delete(f"/api/accounting/narration-aliases/{aliases[0]['id']}/").status_code, 403)
        self.assertEqual(self.approver.delete(f"/api/accounting/narration-aliases/{aliases[0]['id']}/").status_code, 200)
        self.assertFalse(NarrationAlias.objects.exists())


class RecordPaymentFromBankLineTests(TestCase):
    """Record payment / receipt screen: pick the bank transaction; posting also matches it."""

    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.bank = h.bank(self.entity, opening=D("0"))
        self.customer = h.company("Jash Mercantile Pvt Ltd")
        self.inv = posted(h.trade("SALE", self.lm, self.customer, D("10000.00"), on=date(2026, 5, 1)))
        self.due = outstanding(self.inv)
        csv = ("Date,Narration,Ref No,Withdrawal Amt,Deposit Amt\n"
               f"15/05/2026,IMPS 522627002894 JASH MERCAN,522627002894,,{self.due}\n"
               "16/05/2026,NEFT SOMEONE ELSE,,,700.00\n17/05/2026,RTGS JASH MERCANTILE,,300.00,\n")
        import_statement(self.bank, file_name="s.csv", content=csv.encode())
        self.line = StatementLine.objects.get(bank_account=self.bank, narration__startswith="IMPS")
        self.approver = client_with("ACCOUNTS_APPROVER")
        self.viewer = client_with("ACCOUNTS_VIEWER")

    def _post(self, client, **extra):
        body = {"entity": self.lm.pk, "direction": "RECEIPT", "party_id": self.customer.pk, "amount": str(self.due),
                "statement_line_id": self.line.pk, "allocations": [{"invoice_id": self.inv.pk, "amount": str(self.due)}]}
        return client.post("/api/accounting/payments/", {**body, **extra}, format="json")

    def test_party_bank_lines_are_ranked_and_side_filtered(self):
        r = self.viewer.get(f"/api/accounting/parties/{self.customer.pk}/bank-lines/",
                            {"entity": self.lm.pk, "direction": "RECEIPT"})
        self.assertEqual(r.status_code, 200, r.content)
        lines = r.json()["lines"]
        self.assertEqual([ln["id"] for ln in lines], [self.line.pk])  # the withdrawal and the other party are out
        self.assertEqual((lines[0]["mode"], lines[0]["source"], lines[0]["remaining"]), ("IMPS", "name", str(self.due)))
        searched = self.viewer.get(f"/api/accounting/parties/{self.customer.pk}/bank-lines/",
                                   {"entity": self.lm.pk, "direction": "RECEIPT", "search": "SOMEONE"}).json()["lines"]
        self.assertEqual(len(searched), 1)

    def test_post_with_bank_line_books_and_matches_once(self):
        self.assertEqual(self._post(self.viewer).status_code, 403)
        r = self._post(self.approver)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["reference"], r.json()["mode"], r.json()["date"]), ("522627002894", "IMPS", "2026-05-15"))
        self.line.refresh_from_db()
        self.assertEqual((self.line.status, self.line.matches.get().method), (LineStatus.MATCHED, BankMatch.MANUAL))
        self.assertEqual(outstanding(self.inv), D("0.00"))
        self.assertTrue(NarrationAlias.objects.filter(key="JASH MERCAN", party=self.customer).exists())
        again = self._post(self.approver)
        self.assertEqual((again.status_code, again.json()["code"]), (400, "already_matched"))

    def test_line_can_be_settled_in_parts_but_not_beyond_it(self):
        half = (self.due / 2).quantize(D("0.01"))
        r = self._post(self.approver, amount=str(half), allocations=[{"invoice_id": self.inv.pk, "amount": str(half)}],
                       reference="PART-1")
        self.assertEqual(r.status_code, 201, r.content)
        self.line.refresh_from_db()
        self.assertEqual(self.line.status, LineStatus.PARTIAL)
        over = self._post(self.approver, amount=str(self.due), allocations=[], reference="PART-2")
        self.assertEqual((over.status_code, over.json()["code"]), (400, "over_match"))

    def test_direction_and_bank_must_agree_with_the_line(self):
        wrong = self._post(self.approver, direction="PAYMENT", allocations=[])
        self.assertEqual((wrong.status_code, wrong.json()["code"]), (400, "direction_mismatch"))
        other_bank = h.bank(self.entity, number="999888777666")
        mismatch = self._post(self.approver, bank_account_id=other_bank.pk)
        self.assertEqual(mismatch.status_code, 400, mismatch.content)
        self.assertFalse(Payment.objects.exists())


class SplitBulkLineTests(TestCase):
    """'BU : <batch>' bank bulk uploads: one debit split into one payment per supplier, matched to the one line."""

    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.bank = h.bank(self.entity, opening=D("0"))
        self.a = h.company("Alpha Exim Pvt Ltd")
        self.b = h.company("Beta Traders")
        self.bill_a = posted(h.trade("PURCHASE", self.a, self.lm, D("50000.00"), on=date(2026, 5, 1)))
        self.bill_b = posted(h.trade("PURCHASE", self.b, self.lm, D("20000.00"), on=date(2026, 5, 2)))
        self.due_a, self.due_b = outstanding(self.bill_a), outstanding(self.bill_b)
        total = self.due_a + self.due_b - D("10000.00")
        csv = f"Date,Narration,Ref No,Withdrawal Amt,Deposit Amt\n26/05/2026,BU : 2056141 Transfer 26.05.2026,,{total},\n"
        import_statement(self.bank, file_name="s.csv", content=csv.encode())
        self.line = StatementLine.objects.get(bank_account=self.bank)
        self.total = total
        self.approver = client_with("ACCOUNTS_APPROVER")
        self.viewer = client_with("ACCOUNTS_VIEWER")

    def test_bulk_line_is_flagged(self):
        p = proposal_for(self.line)
        self.assertEqual((p.is_bulk, p.confidence), (True, "bulk"))
        body = self.viewer.get(f"/api/accounting/bank-accounts/{self.bank.pk}/proposals/", {"confidence": "bulk"}).json()
        self.assertEqual((body["summary"]["bulk"], body["proposals"][0]["is_bulk"]), (1, True))

    def test_split_books_one_payment_per_row_matched_to_the_line(self):
        from apps.accounting.services.bank_proposals import split_line
        rows = [(self.a, self.due_a - D("5000.00")), (self.b, self.due_b - D("5000.00"))]
        payments = split_line(self.line, rows)
        self.assertEqual([(p.party, p.direction, p.amount) for p in payments],
                         [(self.a, "PAYMENT", rows[0][1]), (self.b, "PAYMENT", rows[1][1])])
        self.line.refresh_from_db()
        self.assertEqual(self.line.status, LineStatus.MATCHED)
        self.assertEqual(sorted(m.method for m in self.line.matches.all()), [BankMatch.SPLIT, BankMatch.SPLIT])
        self.assertEqual((outstanding(self.bill_a), outstanding(self.bill_b)), (D("5000.00"), D("5000.00")))

    def test_rows_must_add_up_and_nothing_posts_otherwise(self):
        from apps.accounting.services.bank_proposals import split_line
        with self.assertRaises(AccountingError) as err:
            split_line(self.line, [(self.a, D("100.00"))])
        self.assertEqual(err.exception.code, "split_total_mismatch")
        with self.assertRaises(AccountingError):
            split_line(self.line, [(self.a, self.total - D("1.00")), (self.lm, D("1.00"))])  # own account
        self.assertFalse(Payment.objects.exists())

    def test_same_party_twice_never_settles_a_bill_twice(self):
        from apps.accounting.services.bank_proposals import plan_split
        first, second = plan_split(self.line, [(self.a, self.due_a - D("5000.00")), (self.a, D("8000.00"))])
        self.assertEqual([a.amount for a in first.allocations], [self.due_a - D("5000.00")])
        self.assertEqual([a.amount for a in second.allocations], [D("5000.00")])
        self.assertEqual(second.advance, D("3000.00"))

    def test_api_dry_run_book_and_undo(self):
        url = f"/api/accounting/statement-lines/{self.line.pk}/split/"
        rows = [{"party_id": self.a.pk, "amount": str(self.due_a - D("5000.00"))},
                {"party_id": self.b.pk, "amount": str(self.due_b - D("5000.00"))}]
        preview = self.viewer.post(url, {"rows": rows, "dry_run": True}, format="json")
        self.assertEqual(preview.status_code, 403)  # read-only roles cannot even plan a posting
        preview = self.approver.post(url, {"rows": rows, "dry_run": True}, format="json")
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()["rows"][0]["allocations"][0]["invoice_id"], self.bill_a.pk)
        self.assertFalse(Payment.objects.exists())
        booked = self.approver.post(url, {"rows": rows}, format="json")
        self.assertEqual(booked.status_code, 200, booked.content)
        self.assertEqual(len(booked.json()["payments"]), 2)
        self.assertEqual(self.viewer.delete(url).status_code, 403)
        undone = self.approver.delete(url)
        self.assertEqual(undone.status_code, 200, undone.content)
        self.assertEqual(undone.json()["status"], "UNMATCHED")
        self.assertEqual((outstanding(self.bill_a), outstanding(self.bill_b)), (self.due_a, self.due_b))
        self.assertEqual(Payment.objects.filter(status="REVERSED").count(), 2)
