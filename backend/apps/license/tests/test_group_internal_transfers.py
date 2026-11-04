"""Group-company internal transfers: classification, matching, utilisation and the accounting ledger.

The group is identified by registered company ID (see apps.trade.services.internal_transfers). Fixtures create
the companies with those IDs. A sale is matched to its purchase only from persisted records: a COPIED pair, or
the same invoice, parties, date and identical lines.
"""

import uuid
from datetime import date
from decimal import Decimal

from apps.core.models import CompanyModel
from apps.license.services.invoice_ledger import load_invoice_ledger
from apps.license.services.licence_balance_report import build_licence_balance_reports
from apps.license.tests.test_licence_balance_report import ReportFixture
from apps.trade.models import LicenseTrade, LicenseTradeLine, TradePairAudit, TradeUtilisationClassification
from apps.trade.services.internal_transfers import (
    EXTERNAL_PURCHASE,
    EXTERNAL_SALE,
    INTERNAL_TRANSFER,
    INTERNAL_TRANSFER_PURCHASE,
    REVIEW_REQUIRED,
    UNMATCHED_INTERNAL_TRANSACTION,
    match_counterpart_purchase,
    match_counterpart_sale,
    transaction_class,
)

D = Decimal


def _company(pk, name, iec):
    return CompanyModel.objects.create(id=pk, name=name, iec=iec)


class GroupInternalTransferTests(ReportFixture):
    def setUp(self):
        super().setUp()
        # Registered group companies, by their company master IDs.
        self.labdhi_mercantile = _company(766, "LABDHI MERCANTILE LLP", "AAMFL0999F")
        self.labdhi_global = _company(881, "LABDHI GLOBAL LLP", "AAMFL9142N")
        self.neelkanth = _company(866, "NEELKANTH IMPEX", "AAWFN4258P")
        # Not in the group, although the name resembles a group company.
        self.sambhav_papers = _company(223, "SAMBHAV PAPERS", "0415021332")

    def _trade(self, direction, invoice, frm, to, cif, qty, item=None, when=None):
        item = item or self.item
        trade = LicenseTrade.objects.create(
            direction=direction, invoice_number=invoice, invoice_date=when or date(2026, 8, 3),
            from_company=frm, to_company=to,
        )
        LicenseTradeLine.objects.create(trade=trade, sr_number=item, cif_fc=D(cif), cif_inr=D(cif) * D("84.5"), qty_kg=D(qty))
        return trade

    def _classify(self, trade, classification=TradeUtilisationClassification.CLASS_INTERNAL, reason="Test."):
        TradeUtilisationClassification.objects.create(trade=trade, classification=classification, reason=reason)

    def _balance(self):
        return build_licence_balance_reports([self.licence.id], include_legacy=False)[self.licence.id]

    def _balance_item(self):
        return self.item_report(self._balance())

    # 1. Verified internal sale and corresponding purchase ---------------------------------------

    def test_verified_internal_sale_and_its_purchase_are_recognised_as_one_transfer(self):
        sale = self._trade("SALE", "LML/2026-27/0023", self.labdhi_mercantile, self.labdhi_global, "48120", "124970.150")
        purchase = self._trade("PURCHASE", "LML/2026-27/0023", self.labdhi_mercantile, self.labdhi_global, "48120", "124970.150")
        self._classify(sale)
        self._classify(purchase)

        self.assertEqual(match_counterpart_purchase(sale).counterpart_trade_id, purchase.pk)
        self.assertEqual(match_counterpart_sale(purchase).counterpart_trade_id, sale.pk)
        self.assertEqual(transaction_class(sale, TradeUtilisationClassification.CLASS_INTERNAL)[0], INTERNAL_TRANSFER)
        self.assertEqual(transaction_class(purchase, TradeUtilisationClassification.CLASS_INTERNAL)[0], INTERNAL_TRANSFER_PURCHASE)

    # 2. Internal transfer excluded from external utilisation -------------------------------------

    def test_internal_transfer_is_excluded_from_external_utilisation(self):
        sale = self._trade("SALE", "LML/2026-27/0023", self.labdhi_mercantile, self.labdhi_global, "400", "400")
        self._classify(sale)

        item = self._balance_item()

        self.assertEqual(item.cif["invoiced"], "0.00")
        self.assertEqual(item.cif["available"], "1000.00")

    # 3. Same transfer not counted twice ------------------------------------------------------------

    def test_the_same_transfer_is_not_counted_as_a_sale_and_again_as_a_purchase(self):
        sale = self._trade("SALE", "T-SAME", self.labdhi_mercantile, self.labdhi_global, "300", "300")
        purchase = self._trade("PURCHASE", "T-SAME", self.labdhi_mercantile, self.labdhi_global, "300", "300")
        self._classify(sale)
        self._classify(purchase)

        item = self._balance_item()

        self.assertEqual(item.cif["invoiced"], "0.00")
        self.assertEqual(item.cif["available"], "1000.00")

    # 4. Subsequent external sale counted once ---------------------------------------------------------

    def test_subsequent_external_sale_by_the_receiving_company_is_counted_once(self):
        internal = self._trade("SALE", "LML-IN", self.labdhi_mercantile, self.labdhi_global, "500", "500")
        self._classify(internal)
        external = self._trade("SALE", "LGL-EXT", self.labdhi_global, self.customer, "200", "200")
        self._classify(external, TradeUtilisationClassification.CLASS_EXTERNAL)

        item = self._balance_item()

        self.assertEqual(item.cif["invoiced"], "200.00")
        self.assertEqual(item.cif["available"], "800.00")
        self.assertEqual(item.qty["available"], "800.000")

    # 5. Multiple internal transfers across group entities ---------------------------------------------

    def test_a_chain_of_internal_transfers_across_group_companies_is_fully_excluded(self):
        for frm, to, invoice in (
            (self.labdhi_mercantile, self.labdhi_global, "CH-1"),
            (self.labdhi_global, self.neelkanth, "CH-2"),
        ):
            sale = self._trade("SALE", invoice, frm, to, "100", "100")
            purchase = self._trade("PURCHASE", invoice, frm, to, "100", "100")
            self._classify(sale)
            self._classify(purchase)

        item = self._balance_item()

        self.assertEqual(item.cif["invoiced"], "0.00")
        self.assertEqual(item.cif["available"], "1000.00")

    # 6. Internal transfer with different invoice numbers ----------------------------------------------

    def test_a_copied_pair_with_different_invoice_numbers_is_matched_by_the_persisted_pair(self):
        sale = self._trade("SALE", "LGL/2026-27/0101", self.labdhi_global, self.neelkanth, "100", "100")
        purchase = self._trade("PURCHASE", "P-NI/2026-27/0001", self.labdhi_global, self.neelkanth, "100", "100")
        TradePairAudit.objects.create(pair_uuid=uuid.uuid4(), source=sale, counterpart=purchase, action="COPIED")

        match = match_counterpart_purchase(sale)

        self.assertEqual(match.counterpart_trade_id, purchase.pk)
        self.assertEqual(match.basis, "COPIED_PAIR")

    # 7. Unmatched internal sale flagged for review --------------------------------------------------------

    def test_a_group_sale_with_no_counterpart_is_flagged_unmatched_and_stays_visible(self):
        self._trade("SALE", "LML/2025-26/0088", self.labdhi_mercantile, self.neelkanth, "250", "250")

        item = self._balance_item()

        self.assertIn("UNMATCHED_INTERNAL_TRANSACTION", item.flags)
        self.assertEqual(item.status, "REVIEW REQUIRED")
        # Not silently external, and not silently discarded: it is still counted until it is classified.
        self.assertEqual(item.cif["invoiced"], "250.00")
        self.assertEqual(transaction_class(
            LicenseTrade.objects.get(invoice_number="LML/2025-26/0088"), None)[0], UNMATCHED_INTERNAL_TRANSACTION)

    def test_a_group_sale_whose_purchase_has_different_lines_is_unmatched(self):
        sale = self._trade("SALE", "DIFF-LINES", self.labdhi_mercantile, self.labdhi_global, "100", "100")
        self._trade("PURCHASE", "DIFF-LINES", self.labdhi_mercantile, self.labdhi_global, "90", "100")

        self.assertIsNone(match_counterpart_purchase(sale))

    # 8. External customer sale remains external ----------------------------------------------------------

    def test_an_external_customer_sale_remains_an_external_sale_and_is_not_flagged(self):
        customer_sale = self._trade("SALE", "CUST-1", self.labdhi_global, self.customer, "150", "150")

        item = self._balance_item()

        self.assertEqual(item.cif["invoiced"], "150.00")
        self.assertNotIn("UNMATCHED_INTERNAL_TRANSACTION", item.flags)
        self.assertEqual(transaction_class(customer_sale, None)[0], EXTERNAL_SALE)

    def test_a_name_resembling_a_group_company_is_not_internal(self):
        # SAMBHAV PAPERS is not the registered Sambhav Corporation (ID 1037), so this is external.
        lookalike = self._trade("SALE", "LOOK-1", self.labdhi_global, self.sambhav_papers, "120", "120")

        item = self._balance_item()

        self.assertEqual(item.cif["invoiced"], "120.00")
        self.assertNotIn("UNMATCHED_INTERNAL_TRANSACTION", item.flags)
        self.assertEqual(transaction_class(lookalike, None)[0], EXTERNAL_SALE)

    # 9. Duplicate and superseded relationships excluded ------------------------------------------------------

    def test_a_superseded_copy_relationship_is_not_used_for_matching(self):
        sale = self._trade("SALE", "SUP-1", self.labdhi_mercantile, self.labdhi_global, "100", "100")
        purchase = self._trade("PURCHASE", "SUP-1-P", self.labdhi_mercantile, self.labdhi_global, "100", "100")
        # The pair was later unpaired. Only a COPIED row counts.
        TradePairAudit.objects.create(pair_uuid=uuid.uuid4(), source=sale, counterpart=purchase, action="UNPAIRED_DELETED")

        self.assertIsNone(match_counterpart_purchase(sale))

    def test_a_second_purchase_for_the_same_supplier_invoice_cannot_exist_so_the_match_is_unambiguous(self):
        from django.db import IntegrityError, transaction

        sale = self._trade("SALE", "DUP-1", self.labdhi_mercantile, self.labdhi_global, "100", "100")
        purchase = self._trade("PURCHASE", "DUP-1", self.labdhi_mercantile, self.labdhi_global, "100", "100")

        with self.assertRaises(IntegrityError), transaction.atomic():
            self._trade("PURCHASE", "DUP-1", self.labdhi_mercantile, self.labdhi_global, "100", "100")
        self.assertEqual(match_counterpart_purchase(sale).counterpart_trade_id, purchase.pk)

    # 10. BOE-linked internal transfer not double-counted ------------------------------------------------------

    def test_a_boe_linked_internal_transfer_is_not_counted_twice(self):
        sale = self._trade("SALE", "BOE-INT", self.labdhi_mercantile, self.labdhi_global, "700", "700")
        self._classify(sale)
        self._boe("BOE-INT-1", cif="700", qty="700")

        item = self._balance_item()

        # The BOE debit is the only utilisation for these goods. The internal sale adds nothing.
        self.assertEqual(item.cif["debited"], "700.00")
        self.assertEqual(item.cif["invoiced"], "0.00")
        self.assertEqual(item.cif["available"], "300.00")

    # 11. Credit and debit notes keep their own classification ---------------------------------------------------

    def test_a_credit_note_on_an_internal_sale_is_its_own_trade_and_is_not_reclassified(self):
        sale = self._trade("SALE", "CN-BASE", self.labdhi_mercantile, self.labdhi_global, "200", "200")
        self._classify(sale)
        note = self._trade("SALE", "CREDIT NOTE CN-BASE", self.labdhi_mercantile, self.labdhi_global, "50", "50")

        # The note has no record of its own. It is not silently treated as internal, and it is not an external
        # purchase: its class comes from its own record, and without one it is treated as a group transfer to review.
        self.assertEqual(transaction_class(note, None)[0], UNMATCHED_INTERNAL_TRANSACTION)

    # 12. Quantity and CIF calculated independently ----------------------------------------------------------------

    def test_quantity_and_cif_of_an_internal_transfer_are_excluded_together_and_independently_reconciled(self):
        sale = self._trade("SALE", "QC-1", self.labdhi_mercantile, self.labdhi_global, "300", "450")
        self._classify(sale)
        self._trade("SALE", "QC-2", self.labdhi_global, self.customer, "0", "50")

        item = self._balance_item()

        self.assertEqual(item.cif["invoiced"], "0.00")
        self.assertEqual(item.qty["invoiced"], "50.000")
        self.assertEqual(item.qty["available"], "950.000")
        self.assertEqual(item.cif["available"], "1000.00")

    # 13. Drawer, item balance and licence balance agree -------------------------------------------------------

    def test_item_balance_and_licence_balance_agree_on_the_internal_exclusion(self):
        sale = self._trade("SALE", "AGREE-1", self.labdhi_mercantile, self.labdhi_global, "400", "400")
        self._classify(sale)

        report = self._balance()
        item = self.item_report(report)

        self.assertEqual(report.summary_cif["invoiced"], item.cif["invoiced"])
        self.assertEqual(report.summary_cif["available"], item.cif["available"])

    # 14. Accounting company-wise totals unchanged; internal rows still visible --------------------------------------

    def test_internal_rows_stay_visible_in_the_ledger_and_leave_external_totals(self):
        sale = self._trade("SALE", "LEDGER-INT", self.labdhi_mercantile, self.labdhi_global, "400", "400")
        purchase = self._trade("PURCHASE", "LEDGER-INT", self.labdhi_mercantile, self.labdhi_global, "400", "400")
        self._classify(sale)
        self._classify(purchase)

        rows = load_invoice_ledger(self.licence.id)
        all_rows = [row for company in rows["companies"] for row in company["rows"]]

        internal = [row for row in all_rows if row["invoice"] == "LEDGER-INT"]
        self.assertEqual({row["transaction_class"] for row in internal}, {INTERNAL_TRANSFER, INTERNAL_TRANSFER_PURCHASE})
        self.assertTrue(all(row["classification"] == "INTERNAL" for row in internal))
        self.assertEqual(rows["summary"]["gross_sale_cif"], "0.00")
