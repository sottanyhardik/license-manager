"""Internal transfer pairs are not external utilisation, and each underlying utilisation counts once.

A sale and its copied purchase (TradePairAudit COPIED, same pair_uuid) describe one transfer between two
group companies. When both sides carry an explicit INTERNAL classification, the sale contributes nothing to
the canonical balance, the purchase never contributes, and the item's final external sale decides utilisation.
Classification comes only from persisted records, never from company names or equal amounts.
"""

import uuid
from datetime import date
from decimal import Decimal

from apps.license.services.licence_balance_report import build_licence_balance_reports
from apps.license.tests.test_licence_balance_report import ReportFixture
from apps.trade.models import LicenseTrade, LicenseTradeLine, TradePairAudit, TradeUtilisationClassification

D = Decimal


class InternalTransferPairTests(ReportFixture):
    def setUp(self):
        super().setUp()
        self.vision = self.seller
        self.labdhi = self.customer

    def _purchase(self, *, invoice, cif, qty, item=None, frm=None, to=None):
        item = item or self.item
        trade = LicenseTrade.objects.create(
            direction="PURCHASE", invoice_number=invoice, invoice_date=date.today(),
            from_company=frm or self.vision, to_company=to or self.labdhi,
        )
        LicenseTradeLine.objects.create(trade=trade, sr_number=item, cif_fc=D(cif), cif_inr=D(cif) * D("84.5"), qty_kg=D(qty))
        return trade

    def _copied_pair(self, sale, purchase):
        TradePairAudit.objects.create(pair_uuid=uuid.uuid4(), source=sale, counterpart=purchase, action="COPIED")

    def _classify(self, trade, classification, reason="Test: persisted classification."):
        TradeUtilisationClassification.objects.create(trade=trade, classification=classification, reason=reason)

    def _balance(self, report=None, item=None):
        report = report or build_licence_balance_reports([self.licence.id], include_legacy=False)[self.licence.id]
        return self.item_report(report, item=item)

    # 1. A purchase and linked sale representing the same internal transfer -------------------------

    def test_internal_sale_and_its_copied_purchase_do_not_consume_entitlement(self):
        sale, _line = self._sale(invoice="GST/26-27/017", cif="1000", qty="1000")
        purchase = self._purchase(invoice="GST/26-27/017", cif="1000", qty="1000")
        self._copied_pair(sale, purchase)
        self._classify(sale, TradeUtilisationClassification.CLASS_INTERNAL)
        self._classify(purchase, TradeUtilisationClassification.CLASS_INTERNAL)

        item = self._balance()

        self.assertEqual(item.cif["invoiced"], "0.00")
        self.assertEqual(item.cif["available"], "1000.00")
        self.assertEqual(item.qty["invoiced"], "0.000")
        self.assertEqual(item.qty["available"], "1000.000")
        self.assertIn("INTERNAL_TRANSFER_NO_EXTERNAL_SALE", item.flags)
        self.assertEqual(item.status, "REVIEW REQUIRED")

    def test_the_same_pair_without_classification_is_counted_as_external_until_classified(self):
        # Before classification the sale is external utilisation. The purchase still contributes nothing.
        sale, _line = self._sale(invoice="GST/26-27/017", cif="1000", qty="1000")
        purchase = self._purchase(invoice="GST/26-27/017", cif="1000", qty="1000")
        self._copied_pair(sale, purchase)

        item = self._balance()

        self.assertEqual(item.cif["invoiced"], "1000.00")
        self.assertEqual(item.cif["available"], "0.00")

    # 2. Internal transfer excluded from duplicate external utilisation ----------------------------

    def test_purchase_side_never_adds_utilisation_even_when_unclassified(self):
        self._purchase(invoice="P-ONLY", cif="500", qty="500")

        item = self._balance()

        self.assertEqual(item.cif["invoiced"], "0.00")
        self.assertEqual(item.cif["available"], "1000.00")

    # 3. Multi-company chain: internal legs carry nothing, the final external sale counts once ----

    def test_chain_of_internal_transfers_counts_only_the_final_external_sale_once(self):
        first, _ = self._sale(invoice="LEG-1", cif="400", qty="400")  # VISION -> LABDHI (internal)
        self._classify(first, TradeUtilisationClassification.CLASS_INTERNAL)
        leg_two, _ = self._sale(invoice="LEG-2", cif="400", qty="400")  # LABDHI -> NEELKANTH (internal)
        self._classify(leg_two, TradeUtilisationClassification.CLASS_INTERNAL)
        final_external, _ = self._sale(invoice="FINAL-EXT", cif="250", qty="250")  # NEELKANTH -> external buyer
        self._classify(final_external, TradeUtilisationClassification.CLASS_EXTERNAL)

        item = self._balance()

        self.assertEqual(item.cif["invoiced"], "250.00")
        self.assertEqual(item.cif["available"], "750.00")
        self.assertEqual(item.qty["available"], "750.000")
        # The item has an external sale, so the no-final-sale exception does not apply.
        self.assertNotIn("INTERNAL_TRANSFER_NO_EXTERNAL_SALE", item.flags)

    # 4. Final external sale counted correctly ----------------------------------------------------

    def test_external_sale_with_no_internal_leg_is_counted_once(self):
        self._sale(invoice="EXT-ONLY", cif="300", qty="300")

        item = self._balance()

        self.assertEqual(item.cif["invoiced"], "300.00")
        self.assertEqual(item.cif["available"], "700.00")
        self.assertNotIn("INTERNAL_TRANSFER_NO_EXTERNAL_SALE", item.flags)

    # 5. Linked sale and purchase with different invoice numbers and different amounts -----------

    def test_pair_linked_by_record_not_by_invoice_number_or_amount(self):
        sale, _ = self._sale(invoice="SALE-NO", cif="600", qty="600")
        purchase = self._purchase(invoice="PURCHASE-NO-DIFFERENT", cif="580", qty="590")
        self._copied_pair(sale, purchase)
        self._classify(sale, TradeUtilisationClassification.CLASS_INTERNAL)
        self._classify(purchase, TradeUtilisationClassification.CLASS_INTERNAL)

        item = self._balance()

        # Classification is per record, so the different numbers and amounts change nothing about the exclusion.
        self.assertEqual(item.cif["invoiced"], "0.00")
        self.assertEqual(item.qty["invoiced"], "0.000")

    # 6. BOE-linked invoice not double-counted, and internal sale beside a BOE debit ---------------

    def test_internal_sale_beside_a_boe_debit_counts_the_boe_once(self):
        # The goods were debited by a BOE (uncovered) and separately appear on an internal sale.
        sale, _ = self._sale(invoice="INT-BOE", cif="700", qty="700")
        self._classify(sale, TradeUtilisationClassification.CLASS_INTERNAL)
        self._boe("BOE-ONE", cif="700", qty="700")

        item = self._balance()

        self.assertEqual(item.cif["debited"], "700.00")
        self.assertEqual(item.cif["invoiced"], "0.00")
        self.assertEqual(item.cif["available"], "300.00")

    # 7. Unclassified transaction and REVIEW records ------------------------------------------------

    def test_review_classification_changes_no_arithmetic(self):
        sale, _ = self._sale(invoice="UNDECIDED", cif="200", qty="200")
        self._classify(sale, TradeUtilisationClassification.CLASS_REVIEW)

        item = self._balance()

        self.assertEqual(item.cif["invoiced"], "200.00")
        self.assertEqual(item.cif["available"], "800.00")

    # 8. No false classification from names or amounts -----------------------------------------------

    def test_same_company_names_and_equal_amounts_without_a_record_are_not_internal(self):
        sale, _ = self._sale(invoice="LOOKALIKE", cif="500", qty="500")
        self._purchase(invoice="LOOKALIKE", cif="500", qty="500")  # no COPIED pair, no classification

        item = self._balance()

        self.assertEqual(item.cif["invoiced"], "500.00")
        self.assertEqual(item.cif["available"], "500.00")

    # 9. Quantity and CIF remain independent --------------------------------------------------------

    def test_quantity_and_cif_of_an_internal_sale_are_excluded_together_and_independently_reconciled(self):
        sale, _ = self._sale(invoice="QTY-CIF", cif="300", qty="450")
        self._classify(sale, TradeUtilisationClassification.CLASS_INTERNAL)

        item = self._balance()

        self.assertEqual(item.cif["available"], "1000.00")
        self.assertEqual(item.qty["available"], "1000.000")
