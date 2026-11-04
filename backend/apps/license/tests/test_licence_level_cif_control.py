"""Licence-level CIF control (Individual Item CIF OFF) against Individual Item CIF ON.

Persisted override None/False: the licence's pooled CIF decides CIF over-utilisation, and an item's
negative CIF is attribution only. Persisted True: each item's CIF is enforced on its own (unchanged).
Quantity status is the same in both modes.
"""

from decimal import Decimal

from apps.license.models import LicenseDetailsModel
from apps.license.services.licence_balance_report import (
    LICENCE_CIF_UNVERIFIED_FLAG,
    LICENCE_CONTROL_STATUS,
    build_licence_balance_reports,
    serialise_licence_detail,
    serialise_licence_summary,
)
from apps.license.tests.test_licence_balance_report import ReportFixture
from apps.trade.models import TradeUtilisationClassification

D = Decimal


class LicenceLevelCifControlTests(ReportFixture):
    def _mode(self, value):
        LicenseDetailsModel.objects.filter(pk=self.licence.pk).update(individual_item_cif_override=value)

    def _verified_external(self, trade):
        TradeUtilisationClassification.objects.create(
            trade=trade, classification=TradeUtilisationClassification.CLASS_EXTERNAL, reason="Test: verified external.",
        )

    def _second_item_over_on_cif_and_qty(self):
        """Item 1 has 1000 CIF / 1000 kg and is positive. Item 2 has 100 CIF / 100 kg and a 300 kg sale."""
        second = self._item(self.licence, serial=2, qty="100.000", cif="100.00")
        trade, _line = self._sale(invoice="INV-2", cif="300", qty="300", item=second)
        return second, trade

    def _report(self):
        return build_licence_balance_reports([self.licence.id], include_legacy=False)[self.licence.id]

    # OFF: licence-level control --------------------------------------------

    def test_off_negative_item_cif_is_attribution_not_over_utilised(self):
        second, _trade = self._second_item_over_on_cif_and_qty()
        self._mode(None)

        report = self._report()
        item = self.item_report(report, item=second)

        self.assertEqual(report.cif_control, "LICENCE")
        self.assertEqual(item.cif["available"], "-200.00")
        self.assertEqual(item.cif["status"], LICENCE_CONTROL_STATUS)
        self.assertEqual(item.cif["raw_status"], "OVER-UTILISED")
        self.assertFalse(item.cif["is_over_utilised"])

    def test_off_licence_cif_uses_the_pooled_figure_and_is_not_over(self):
        self._second_item_over_on_cif_and_qty()
        self._mode(None)

        report = self._report()

        # 1000 + 100 - 300 pooled, with the 300 kg sale unverified and counted external.
        self.assertEqual(report.summary_cif["available"], "800.00")
        self.assertEqual(report.summary_cif["status"], "RECONCILED")
        self.assertFalse(report.summary_cif["is_over_utilised"])

    def test_off_quantity_status_is_independent_of_cif_control(self):
        second, _trade = self._second_item_over_on_cif_and_qty()
        self._mode(None)

        item = self.item_report(self._report(), item=second)

        self.assertEqual(item.qty["available"], "-200.000")
        self.assertEqual(item.qty["status"], "OVER-UTILISED")
        self.assertEqual(item.status, "OVER-UTILISED")

    def test_off_negative_verified_pool_is_over_utilised(self):
        trade, _line = self._sale(invoice="LGL-BIG", cif="1200", qty="1200")
        self._verified_external(trade)
        self._mode(None)

        report = self._report()

        self.assertEqual(report.summary_cif["available"], "-200.00")
        self.assertTrue(report.summary_cif["is_over_utilised"])
        self.assertEqual(report.summary_cif["status"], "OVER-UTILISED")
        self.assertEqual(report.status, "OVER-UTILISED")

    def test_off_negative_pool_resting_on_unverified_sale_is_review(self):
        # Base: the unverified 1200 sale is external, so the pool is -200.
        # Alternative: that sale is internal, so the pool is +1000. The outcome depends on the classification.
        trade, _line = self._sale(invoice="LGL-UNVERIFIED", cif="1200", qty="1200")
        self._mode(None)

        report = self._report()

        self.assertEqual(report.summary_cif["available"], "-200.00")
        self.assertFalse(report.summary_cif["is_over_utilised"])
        self.assertEqual(report.summary_cif["status"], "REVIEW REQUIRED")
        self.assertIn(LICENCE_CIF_UNVERIFIED_FLAG, report.flags)
        self.assertEqual(report.status, "REVIEW REQUIRED")
        self.assertEqual(report.cif_scenarios["base_available"], D("-200.00"))
        self.assertEqual(report.cif_scenarios["alternative_available"], "1000.00")
        self.assertEqual(report.cif_scenarios["unverified_trade_ids"], [trade.id])

    def test_off_negative_under_both_scenarios_is_over_utilised(self):
        # Verified external 1100 leaves -100 even when the unverified 200 sale is internal, so OVER-UTILISED.
        verified, _line = self._sale(invoice="LGL-VERIFIED", cif="1100", qty="1100")
        self._verified_external(verified)
        self._sale(invoice="LGL-UNVERIFIED", cif="200", qty="200")
        self._mode(None)

        report = self._report()

        self.assertEqual(report.summary_cif["available"], "-300.00")
        self.assertEqual(report.cif_scenarios["alternative_available"], "-100.00")
        self.assertTrue(report.summary_cif["is_over_utilised"])
        self.assertEqual(report.status, "OVER-UTILISED")
        self.assertIn(LICENCE_CIF_UNVERIFIED_FLAG, report.flags)

    def test_off_item_cif_with_unverified_attribution_is_review_required(self):
        # A sale and an allotment on the same item are flagged as unverified overlap.
        self._sale(invoice="LGL-OVERLAP", cif="100", qty="100")
        self._allotment(self.item, cif="100", qty="100")
        self._mode(None)

        item = self.item_report(self._report())

        self.assertIn("ALLOT_AND_SALE_OVERLAP_UNVERIFIED", item.flags)
        self.assertEqual(item.cif["status"], "REVIEW REQUIRED")
        self.assertEqual(item.cif["cif_control"], "LICENCE")

    # ON: item-level enforcement is unchanged -------------------------------

    def test_on_negative_item_cif_stays_over_utilised_with_no_netting(self):
        second, _trade = self._second_item_over_on_cif_and_qty()
        self._mode(True)

        report = self._report()
        item = self.item_report(report, item=second)

        self.assertEqual(report.cif_control, "ITEM")
        self.assertEqual(item.cif["status"], "OVER-UTILISED")
        self.assertTrue(item.cif["is_over_utilised"])
        self.assertNotIn("raw_status", item.cif)
        # The licence total is still the pooled sum, and the item over-utilisation keeps the licence in review.
        self.assertEqual(report.summary_cif["available"], "800.00")
        self.assertFalse(report.summary_cif["is_over_utilised"])
        self.assertEqual(report.status, "REVIEW REQUIRED")
        self.assertIsNone(report.cif_scenarios.get("base_available"))

    def test_on_and_off_give_the_same_quantity_and_the_same_licence_pool(self):
        second, _trade = self._second_item_over_on_cif_and_qty()
        self._mode(None)
        off = self._report()
        self._mode(True)
        on = self._report()

        self.assertEqual(off.summary_cif["available"], on.summary_cif["available"])
        for report in (off, on):
            item = self.item_report(report, item=second)
            self.assertEqual(item.qty["available"], "-200.000")
            self.assertEqual(item.qty["status"], "OVER-UTILISED")

    # Serialised contract ----------------------------------------------------

    def test_serialised_summary_names_the_control_mode_and_scenarios(self):
        trade, _line = self._sale(invoice="LGL-UNVERIFIED", cif="1200", qty="1200")
        self._mode(None)
        off = serialise_licence_summary(self._report())
        self.assertEqual(off["cif_control"], "LICENCE")
        self.assertEqual(off["cif_scenarios"]["unverified_trade_ids"], [trade.id])
        self.assertEqual(off["cif_scenarios"]["base_available"], "-200.00")

        self._mode(True)
        on = serialise_licence_summary(self._report())
        self.assertEqual(on["cif_control"], "ITEM")
        self.assertIsNone(on["cif_scenarios"])

    # Row display: the Available CIF each Items & Balance row shows ---------

    def test_off_every_row_displays_the_same_licence_available_cif(self):
        second, _trade = self._second_item_over_on_cif_and_qty()
        self._mode(None)

        rows = serialise_licence_detail(self._report())["items"]

        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["cif_control"], "LICENCE")
            self.assertEqual(row["available_cif_display"], "800.00")
        # The display is one licence balance, so it is not a per-item amount.
        by_item = {row["item_id"]: row for row in rows}
        self.assertEqual(by_item[second.id]["cif"]["available"], "-200.00")
        self.assertEqual(by_item[second.id]["qty"]["available"], "-200.000")

    def test_on_each_row_displays_its_own_available_cif(self):
        second, _trade = self._second_item_over_on_cif_and_qty()
        self._mode(True)

        rows = {row["item_id"]: row for row in serialise_licence_detail(self._report())["items"]}

        self.assertEqual(rows[self.item.id]["cif_control"], "ITEM")
        self.assertEqual(rows[self.item.id]["available_cif_display"], "1000.00")
        self.assertEqual(rows[second.id]["cif_control"], "ITEM")
        self.assertEqual(rows[second.id]["available_cif_display"], "-200.00")
