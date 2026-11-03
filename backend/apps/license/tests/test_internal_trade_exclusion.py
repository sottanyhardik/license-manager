"""Internal trades are listed for audit and never count as external licence utilisation.

Built on the report fixture, so every figure comes from real trade, BOE and item rows. Only an
explicit INTERNAL record changes the arithmetic. A trade with no record, or a REVIEW record, does not.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.license.services.invoice_ledger import load_invoice_ledger
from apps.license.services.licence_balance_report import build_licence_balance_reports, build_licence_transactions
from apps.license.services.licence_item_drilldown import build_item_drilldown
from apps.license.tests import test_licence_balance_report as base
from apps.trade.models import LicenseTrade, TradeUtilisationClassification

INTERNAL = TradeUtilisationClassification.CLASS_INTERNAL
REVIEW = TradeUtilisationClassification.CLASS_REVIEW


class InternalTradeFixture(base.ReportFixture):
    def classify(self, trade, classification=INTERNAL):
        return TradeUtilisationClassification.objects.create(trade=trade, classification=classification, reason="test")

    def item_figures(self, item=None):
        report = build_licence_balance_reports([self.licence.id], include_legacy=False)[self.licence.id]
        by_sr = {i.sr: i for i in report.items}
        sr = str((item or self.item).serial_number)
        return by_sr[sr]

    def drill(self, item=None):
        return build_item_drilldown(self.licence.id, (item or self.item).id)


class InternalSaleUtilisationTests(InternalTradeFixture):
    def test_an_internal_sale_is_not_external_utilisation(self):
        trade, _ = self._sale(invoice="INT-1", cif="300", qty="0")
        self.classify(trade)
        figures = self.item_figures()
        self.assertEqual(figures.cif["invoiced"], "0.00")
        self.assertEqual(figures.cif["available"], "1000.00")

    def test_an_external_sale_is_still_counted(self):
        self._sale(invoice="EXT-1", cif="300", qty="0")
        figures = self.item_figures()
        self.assertEqual(figures.cif["invoiced"], "300.00")
        self.assertEqual(figures.cif["available"], "700.00")

    def test_a_genuine_boe_debit_on_an_internal_sale_is_still_counted_once(self):
        trade, _ = self._sale(invoice="INT-B", cif="300", qty="0")
        self.classify(trade)
        self._boe("INT-BOE", cif="120", qty="0", trades=[trade])
        figures = self.item_figures()
        self.assertEqual(figures.cif["debited"], "120.00")
        self.assertEqual(figures.cif["invoiced"], "0.00")
        self.assertEqual(figures.cif["available"], "880.00")

    def test_a_review_classification_changes_no_arithmetic(self):
        trade, _ = self._sale(invoice="REV-1", cif="300", qty="0")
        self.classify(trade, classification=REVIEW)
        self.assertEqual(self.item_figures().cif["invoiced"], "300.00")

    def test_an_internal_sale_on_one_item_does_not_touch_another(self):
        other = self._item(self.licence, serial=2, qty="500.000", cif="500.00")
        trade, _ = self._sale(invoice="ISO-1", cif="300", qty="0", item=other)
        self.classify(trade)
        self.assertEqual(self.item_figures(other).cif["available"], "500.00")
        self.assertEqual(self.item_figures().cif["available"], "1000.00")

    def test_an_internal_purchase_does_not_add_entitlement(self):
        purchase = LicenseTrade.objects.create(
            direction="PURCHASE", invoice_number="INT-P", invoice_date=base.date.today(),
            from_company=self.customer, to_company=self.seller,
        )
        base.LicenseTradeLine.objects.create(trade=purchase, sr_number=self.item, cif_fc=base.D("400"), cif_inr=base.D("400") * base.D("84.5"), qty_kg=base.D("0"))
        self.classify(purchase)
        self.assertEqual(self.item_figures().cif["available"], "1000.00")


class InternalTradeDrillDownTests(InternalTradeFixture):
    def test_the_internal_sale_is_listed_with_its_reason_and_kept_out_of_external_totals(self):
        trade, _ = self._sale(invoice="INT-D", cif="300", qty="0")
        self.classify(trade)
        drill = self.drill()
        totals = drill["invoices"]["totals"]
        self.assertEqual(totals["internal_sold_cif"], "300.00")
        self.assertEqual(totals["gross_sold_cif"], "300.00")
        self.assertEqual(totals["sold_cif"], "0.00")
        self.assertEqual(totals["uncovered_cif"], "0.00")
        self.assertEqual(totals["current_balance_cif"], "0.00")
        row = next(r for r in drill["invoices"]["rows"] if r["trade_id"] == trade.id)
        self.assertEqual(row["classification"], "INTERNAL")
        self.assertFalse(row["counts_in_current_balance"])
        self.assertEqual(row["classification_reason"], "test")

    def test_the_drill_down_reconciles_with_the_item_table(self):
        trade, _ = self._sale(invoice="INT-R", cif="300", qty="0")
        self.classify(trade)
        drill = self.drill()
        self.assertEqual(drill["canonical"]["cif"]["invoiced"], "0.00")
        self.assertEqual(drill["invoices"]["totals"]["sold_cif"], drill["canonical"]["cif"]["invoiced"])

    def test_workspace_transactions_list_the_internal_invoice_as_internal(self):
        trade, _ = self._sale(invoice="INT-T", cif="300", qty="0")
        self.classify(trade)
        invoices = build_licence_transactions(self.licence.id)["invoices"]
        row = next(i for i in invoices if i["invoice_number"] == "INT-T")
        self.assertEqual(row["classification"], "INTERNAL")
        self.assertEqual(row["covered_by_boe"], "0.00")
        self.assertEqual(row["uncovered"], "0.00")


class InvoiceLedgerInternalTests(InternalTradeFixture):
    def test_the_ledger_lists_the_internal_sale_and_keeps_external_totals_clean(self):
        internal, _ = self._sale(invoice="LED-I", cif="300", qty="0")
        self.classify(internal)
        self._sale(invoice="LED-E", cif="50", qty="0")
        ledger = load_invoice_ledger(self.licence.id)
        summary = ledger["summary"]
        self.assertEqual(summary["gross_internal_sale_cif"], "300.00")
        self.assertEqual(summary["gross_sale_cif"], "50.00")
        self.assertEqual(summary["gross_sale_all_cif"], "350.00")
        self.assertEqual(summary["internal_row_count"], 1)
        rows = [r for c in ledger["companies"] for r in c["rows"]]
        internal_rows = [r for r in rows if r["invoice"] == "LED-I"]
        self.assertEqual(len(internal_rows), 1)
        self.assertEqual(internal_rows[0]["classification"], "INTERNAL")

    def test_the_company_balance_excludes_the_internal_sale(self):
        trade, _ = self._sale(invoice="LED-B", cif="300", qty="0")
        self.classify(trade)
        ledger = load_invoice_ledger(self.licence.id)
        customer = next(c for c in ledger["companies"] if c["company"] == self.seller.name)
        self.assertEqual(customer["internal_cif"], "300.00")
        self.assertEqual(customer["balance_cif"], "0.00")


class InternalClassificationCommandTests(InternalTradeFixture):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username="cls-" + uuid.uuid4().hex[:6], password="x")

    def test_a_dry_run_writes_nothing(self):
        trade, _ = self._sale(invoice="CMD-1", cif="300", qty="0")
        call_command("set_trade_utilisation_classification", "--trade", str(trade.id), "--classification", INTERNAL,
                     "--reason", "why", "--by", self.user.username)
        self.assertFalse(TradeUtilisationClassification.objects.filter(trade=trade).exists())

    def test_apply_records_the_classification_and_the_authoriser(self):
        trade, _ = self._sale(invoice="CMD-2", cif="300", qty="0")
        call_command("set_trade_utilisation_classification", "--trade", str(trade.id), "--classification", INTERNAL,
                     "--reason", "why", "--evidence", "doc", "--by", self.user.username, "--apply")
        record = TradeUtilisationClassification.objects.get(trade=trade)
        self.assertEqual(record.classification, INTERNAL)
        self.assertEqual(record.authorised_by, self.user)
        self.assertEqual(record.evidence, "doc")

    def test_a_reason_is_required(self):
        trade, _ = self._sale(invoice="CMD-3", cif="300", qty="0")
        with self.assertRaises(CommandError):
            call_command("set_trade_utilisation_classification", "--trade", str(trade.id), "--classification", INTERNAL,
                         "--reason", "  ", "--by", self.user.username, "--apply")

    def test_an_unknown_trade_or_user_is_refused(self):
        with self.assertRaises(CommandError):
            call_command("set_trade_utilisation_classification", "--trade", "999999", "--classification", INTERNAL,
                         "--reason", "why", "--by", self.user.username, "--apply")
        trade, _ = self._sale(invoice="CMD-4", cif="300", qty="0")
        with self.assertRaises(CommandError):
            call_command("set_trade_utilisation_classification", "--trade", str(trade.id), "--classification", INTERNAL,
                         "--reason", "why", "--by", "nobody-here", "--apply")

    def test_a_classified_trade_cannot_be_deleted(self):
        from django.db.models import ProtectedError
        trade, _ = self._sale(invoice="CMD-5", cif="300", qty="0")
        self.classify(trade)
        with self.assertRaises(ProtectedError):
            trade.delete()
