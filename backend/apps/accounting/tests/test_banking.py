"""Bank account -> upload -> normalise -> duplicates -> UTR match -> amount match -> manual/split ->
suspense -> reclassification -> voucher -> bank ledger -> reconciliation."""
import io
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.accounting.domain.statement import (
    StatementFormatError, detect_mapping, extract_utr, find_header_row, normalise_row, parse_amount, parse_date,
)
from apps.accounting.models import BankMatch, LineStatus, StatementLine, SuspenseItem, Voucher
from apps.accounting.selectors.ledger import account_balance
from apps.accounting.services import AccountingError
from apps.accounting.services.banking import (
    auto_match, bank_reconciliation, candidates_for, import_statement, manual_match, move_to_suspense,
    reclassify_suspense, resolve_suspense_by_match, unmatch,
)
from apps.accounting.services.books import party_account
from apps.accounting.services.chart import system_account
from apps.accounting.services.invoices import confirm_invoice, invoice_from_trade, outstanding, post_invoice
from apps.accounting.services.payments import record_payment

from . import helpers as h

D = Decimal

CSV = (
    "HDFC BANK LTD\nStatement of account 000111222333\n\n"
    "Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance\n"
    "02/05/2026,NEFT CR-HDFCN52026050212-IMPORTER LTD,HDFCN52026050212,02/05/2026,,\"1,18,000.00\",\"1,18,000.00\"\n"
    "05/05/2026,RTGS DR-EXPORTER PVT LTD,,05/05/2026,\"50,000.00\",,\"68,000.00\"\n"
    "07/05/2026,BANK CHARGES GST,,07/05/2026,236.00,,\"67,764.00\"\n"
    "09/05/2026,UPI-UNKNOWN SENDER,,09/05/2026,,\"5,000.00\",\"72,764.00\"\n"
    "12/05/2026,NEFT CR-IMPORTER LTD,,12/05/2026,,\"30,000.00\",\"1,02,764.00\"\n"
)


class StatementParsingTests(SimpleTestCase):
    def test_header_aliases_and_amount_formats(self):
        mapping = detect_mapping(["Txn Date", "Description", "Debit", "Credit", "Balance", "UTR No"])
        self.assertEqual(set(mapping), {"txn_date", "narration", "debit", "credit", "balance", "reference"})
        self.assertEqual(parse_amount("1,18,000.00"), D("118000.00"))
        self.assertEqual(parse_amount("(250.50)"), D("-250.50"))
        self.assertEqual(parse_amount("1,000.00 Cr"), D("1000.00"))
        self.assertEqual(parse_date("02-May-2026"), date(2026, 5, 2))

    def test_signed_amount_column_with_dr_cr_flag(self):
        mapping = detect_mapping(["Date", "Particulars", "Amount", "Dr/Cr"])
        line = normalise_row(["01/06/2026", "NEFT", "2,500.00", "DR"], mapping, 2)
        self.assertEqual((line.debit, line.credit), (D("2500.00"), D("0.00")))

    def test_missing_columns_rejected(self):
        with self.assertRaises(StatementFormatError):
            detect_mapping(["Narration", "Balance"])

    def test_misspelt_withdrawal_header_and_deep_preamble(self):
        # Synthetic copy of a real bank export layout: ~28 preamble rows, "Withdrawl Amt" (sic), newest first.
        header = ["Transaction Date", "Transaction Details", "Cheque ID", "Value Date", "Withdrawl Amt", "Deposit Amt",
                  "Balance (₹)", None]
        rows = [["ACCOUNT DETAILS"]] + [[f"preamble {i}", None] for i in range(27)] + [header]
        self.assertEqual(find_header_row(rows), 28)
        mapping = detect_mapping(header)
        self.assertEqual(header[mapping["debit"]], "Withdrawl Amt")
        line = normalise_row(["11/03/2025", "NEFT DR-SUPPLIER", None, "11/03/2025", 2500, None, 97500.0, None],
                             mapping, 30)
        self.assertEqual((line.debit, line.credit, line.balance), (D("2500.00"), D("0.00"), D("97500.00")))
        with self.assertRaises(StatementFormatError):  # footer rows are rejected, not imported
            normalise_row(["Opening Balance:", "₹ 0.00", "Count Of Debit:", "1"], mapping, 40)

    def test_one_sided_debit_credit_mapping_rejected(self):
        # An unrecognised withdrawal column must not silently drop every debit.
        with self.assertRaises(StatementFormatError):
            detect_mapping(["Date", "Narration", "Paid Out", "Deposit Amt", "Balance"])

    def test_utr_extraction(self):
        self.assertEqual(extract_utr("NEFT CR-HDFCN52026050212-IMPORTER"), "HDFCN52026050212")
        self.assertEqual(extract_utr("IMPS 612345678901 PAYMENT"), "612345678901")


class BankingWorkflowTests(TestCase):
    def setUp(self):
        self.lm = h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5")
        self.entity = h.books(self.lm)
        self.bank = h.bank(self.entity, opening=D("0"))
        self.customer = h.company("Importer Ltd", gst="24AAACI0000A1Z5")
        self.supplier = h.company("Exporter Pvt Ltd", gst="27AAACE0000A1Z5")
        sale = h.trade("SALE", self.lm, self.customer, D("118000.00"), on=date(2026, 5, 1))
        self.sale_inv = invoice_from_trade(sale.pk)
        confirm_invoice(self.sale_inv)
        self.sale_inv = post_invoice(self.sale_inv)
        # Book side already has the receipt (with UTR) and the supplier payment (no UTR).
        self.receipt = record_payment(
            entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
            payment_date=date(2026, 5, 2), amount=D("118000.00"), reference="HDFCN52026050212",
            allocations=[(self.sale_inv, D("118000.00"))])
        self.payment = record_payment(
            entity=self.entity, direction="PAYMENT", party=self.supplier, bank_account=self.bank,
            payment_date=date(2026, 5, 4), amount=D("50000.00"))

    def _import(self, content=CSV, name="hdfc.csv"):
        return import_statement(self.bank, file_name=name, content=content.encode())

    def test_end_to_end_reconciliation(self):
        result = self._import()
        st = result.statement_import
        self.assertEqual((st.rows_new, st.rows_duplicate, st.rows_rejected), (5, 0, 0))

        # Duplicate detection: the same file twice imports nothing new.
        again = self._import()
        self.assertEqual((again.statement_import.rows_new, again.statement_import.rows_duplicate), (0, 5))
        self.assertEqual(StatementLine.objects.filter(bank_account=self.bank).count(), 5)

        vouchers_before = Voucher.objects.count()
        outcome = auto_match(self.bank)
        self.assertEqual(Voucher.objects.count(), vouchers_before, "matching must never post")
        self.assertEqual(outcome.get("utr"), 1)
        self.assertEqual(outcome.get("amount"), 1)
        lines = {ln.narration[:14]: ln for ln in StatementLine.objects.filter(bank_account=self.bank)}
        utr_line = lines["NEFT CR-HDFCN5"]
        self.assertEqual(utr_line.status, LineStatus.MATCHED)
        self.assertEqual(utr_line.matches.get().method, BankMatch.AUTO_REFERENCE)
        self.assertEqual(lines["RTGS DR-EXPORT"].matches.get().voucher_id, self.payment.voucher_id)

        # Bank charges: unidentified -> suspense -> reclassify to Bank Charges (through the posting engine).
        charges = lines["BANK CHARGES G"]
        item = move_to_suspense(charges, reason="Charges not yet booked")
        self.assertEqual(account_balance(system_account(self.entity, "SUSPENSE")), D("236.00"))
        reclassify_suspense(item, target=system_account(self.entity, "BANK_CHARGES"), note="Monthly charges")
        item.refresh_from_db()
        self.assertEqual(item.status, SuspenseItem.RESOLVED)
        self.assertEqual(account_balance(system_account(self.entity, "SUSPENSE")), D("0.00"))
        self.assertEqual(account_balance(system_account(self.entity, "BANK_CHARGES")), D("236.00"))
        charges.refresh_from_db()
        self.assertEqual(charges.status, LineStatus.RESOLVED)

        # Unknown UPI credit -> suspense -> reclassify to the customer's ledger as an advance.
        upi = lines["UPI-UNKNOWN SE"]
        upi_item = move_to_suspense(upi, reason="Sender not identified")
        reclassify_suspense(upi_item, target=party_account(self.entity, self.customer, payable=False),
                            note="Customer confirmed by phone")

        # 30,000 receipt not in books yet -> stays unmatched and visible in the BRS.
        brs = bank_reconciliation(self.bank, date(2026, 5, 31))
        self.assertEqual(brs["statement_balance"], D("102764.00"))
        self.assertEqual(brs["unrecorded_credits"], D("30000.00"))
        self.assertEqual(brs["difference"], D("0.00"))
        self.assertEqual(brs["book_balance"], D("72764.00"))
        self.assertEqual(account_balance(self.bank.account), D("72764.00"))

    def test_split_and_partial_manual_match(self):
        r1 = record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                            payment_date=date(2026, 5, 11), amount=D("10000.00"))
        r2 = record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                            payment_date=date(2026, 5, 11), amount=D("15000.00"))
        self._import()
        line = StatementLine.objects.get(bank_account=self.bank, credit=D("30000.00"))
        manual_match(line, [(r1.voucher, D("10000.00")), (r2.voucher, D("15000.00"))])
        line.refresh_from_db()
        self.assertEqual((line.status, line.matched_amount), (LineStatus.PARTIAL, D("25000.00")))
        with self.assertRaises(AccountingError):  # over-match of the line
            manual_match(line, [(self.receipt.voucher, D("5000.01"))])
        # History is preserved on unmatch.
        m = line.matches.filter(voucher=r2.voucher).get()
        unmatch(m, reason="wrong receipt")
        m.refresh_from_db()
        line.refresh_from_db()
        self.assertFalse(m.is_active)
        self.assertEqual(line.matched_amount, D("10000.00"))
        self.assertEqual(BankMatch.objects.filter(statement_line=line).count(), 2)

    def test_wrong_side_cannot_match(self):
        self._import()
        deposit = StatementLine.objects.get(bank_account=self.bank, credit=D("30000.00"))
        with self.assertRaises(AccountingError):
            manual_match(deposit, [(self.payment.voucher, D("30000.00"))])

    def test_suspense_resolved_by_matching_existing_payment_is_not_double_counted(self):
        self._import()
        line = StatementLine.objects.get(bank_account=self.bank, credit=D("30000.00"))
        item = move_to_suspense(line, reason="unknown")
        late = record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                              payment_date=date(2026, 5, 12), amount=D("30000.00"))
        resolve_suspense_by_match(item, late.voucher, note="receipt entered later")
        # Bank ledger counts the 30,000 exactly once (suspense entry reversed).
        balance = account_balance(self.bank.account)
        self.assertEqual(balance, D("118000.00") - D("50000.00") + D("30000.00"))
        self.assertEqual(account_balance(system_account(self.entity, "SUSPENSE")), D("0.00"))

    def test_candidates_rank_utr_first(self):
        self._import()
        line = StatementLine.objects.get(reference="HDFCN52026050212")
        cands = candidates_for(line)
        self.assertEqual(cands[0].voucher.pk, self.receipt.voucher_id)
        self.assertIn("utr", cands[0].signals)

    def test_ambiguous_amounts_stay_unmatched(self):
        for _ in range(2):
            record_payment(entity=self.entity, direction="RECEIPT", party=self.customer, bank_account=self.bank,
                           payment_date=date(2026, 5, 12), amount=D("30000.00"))
        self._import()
        auto_match(self.bank)
        line = StatementLine.objects.get(bank_account=self.bank, credit=D("30000.00"))
        self.assertEqual(line.status, LineStatus.UNMATCHED)

    def test_excel_import(self):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["Transaction Date", "Description", "Debit", "Credit", "Balance"])
        ws.append([date(2026, 6, 1), "NEFT CR-ABC", None, 1500, 1500])
        buf = io.BytesIO()
        wb.save(buf)
        res = import_statement(self.bank, file_name="s.xlsx", content=buf.getvalue())
        self.assertEqual(res.statement_import.rows_new, 1)
        self.assertEqual(res.new_lines[0].credit, D("1500.00"))

    def test_pdf_rejected_with_guidance(self):
        with self.assertRaises(AccountingError) as ctx:
            import_statement(self.bank, file_name="s.pdf", content=b"%PDF-1.4")
        self.assertEqual(ctx.exception.code, "pdf_unsupported")

    def test_outstanding_unchanged_by_matching(self):
        self._import()
        auto_match(self.bank)
        self.assertEqual(outstanding(self.sale_inv), D("0.00"))
