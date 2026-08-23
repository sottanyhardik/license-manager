"""Regression matrix for canonical ledger reconciliation.

The original tests queried historical production licence numbers and asserted
known bugs. These deterministic fixtures retain the coverage while asserting
the current canonical contract: raw trade lines, the ledger dataset, and the
summary/export-facing values reconcile exactly.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.core.models import CompanyModel, HeadSIONNormsModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.trade.models import LicenseTrade


class TestLedgerReconciliationMatrixSmokingGun(TestCase):
    """Exercise the ledger against known raw values without production fixtures."""

    def setUp(self):
        self.exporter = CompanyModel.objects.create(iec="8310001111", name="Ledger Exporter")
        self.supplier = CompanyModel.objects.create(iec="8310002222", name="Ledger Supplier")
        self.buyer = CompanyModel.objects.create(iec="8310003333", name="Ledger Buyer")
        head = HeadSIONNormsModel.objects.create(name="Ledger reconciliation norm")
        self.norm = SionNormClassModel.objects.create(head_norm=head, norm_class="LREC", is_active=True)
        self.license = LicenseDetailsModel.objects.create(
            license_number="LEDGER-RECON-001",
            exporter=self.exporter,
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2026, 12, 31),
        )
        LicenseExportItemModel.objects.create(
            license=self.license, description="Opening CIF", norm_class=self.norm,
            cif_fc=Decimal("1000.00"),
        )
        self._trade(
            LicenseTrade.DIR_PURCHASE, Decimal("200.00"), Decimal("10000.00"),
            date(2026, 1, 10), self.supplier, self.exporter,
        )
        self._trade(
            LicenseTrade.DIR_SALE, Decimal("200.00"), Decimal("15000.00"),
            date(2026, 2, 10), self.exporter, self.buyer,
        )

    def _trade(self, direction, cif_fc, amount_inr, invoice_date, from_company, to_company):
        serial = self.license.import_license.count() + 1
        trade = LicenseTrade.objects.create(
            direction=direction,
            license_type=LicenseTrade.LICENSE_TYPE_DFIA,
            from_company=from_company,
            to_company=to_company,
            invoice_number=f"LEDGER-RECON-{direction}-{serial}",
            invoice_date=invoice_date,
        )
        import_item = LicenseImportItemsModel.objects.create(
            license=self.license,
            serial_number=serial,
            description=f"Ledger line {serial}",
        )
        trade.lines.create(
            sr_number=import_item,
            cif_fc=cif_fc,
            amount_inr=amount_inr,
            mode="CIF_INR",
            pct=Decimal("100.000"),
        )
        return trade

    def _dataset(self):
        return CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id, "DFIA")

    def test_summary_balance_uses_display_rule_without_double_counting_opening(self):
        dataset = self._dataset()
        self.assertEqual(dataset["opening_balance"], Decimal("1000.00"))
        self.assertEqual(dataset["license_running_balance"], Decimal("0.00"))
        # A purchase records the acquisition already represented by the export
        # item's opening CIF. The display summary deliberately suppresses the
        # synthetic opening row whenever a purchase exists, so it reports the
        # net position of displayed transactions instead of double counting
        # that acquisition.
        self.assertEqual(dataset["summary"]["total_purchase"], Decimal("200.00"))
        self.assertEqual(dataset["summary"]["total_sale"], Decimal("200.00"))
        self.assertEqual(dataset["summary"]["current_balance"], Decimal("0.00"))
        # With the acquisition represented once by PURCHASE, display and
        # running balances reconcile exactly.
        self.assertEqual(dataset["summary"]["current_balance"], dataset["closing_balance"])

    def test_opening_purchase_and_sale_are_all_accounted_for_once(self):
        dataset = self._dataset()
        transactions = dataset["transactions"]
        self.assertEqual([row["type"] for row in transactions], ["PURCHASE", "SALE"])
        self.assertEqual(len(dataset["display_transactions"]), 2)
        self.assertIsNone(dataset["opening_display"])
        self.assertEqual(
            sum((row["purchase_amount"] or Decimal("0.00")) for row in dataset["display_transactions"])
            - sum((row["sale_amount"] or Decimal("0.00")) for row in dataset["display_transactions"]),
            dataset["license_running_balance"],
        )

    def test_raw_trade_count_and_canonical_display_selection_reconcile(self):
        dataset = self._dataset()
        raw_count = LicenseTrade.objects.filter(
            license_type="DFIA", lines__sr_number__license_id=self.license.id,
        ).distinct().count()
        opening_rows = [row for row in dataset["transactions"] if row["type"] == "OPENING"]
        non_opening_rows = [row for row in dataset["transactions"] if row["type"] != "OPENING"]

        self.assertEqual(raw_count, 2)
        self.assertEqual(len(opening_rows), 0)
        self.assertEqual(len(non_opening_rows), raw_count)
        self.assertEqual(len(dataset["display_transactions"]), raw_count)
        self.assertTrue(all(row["type"] != "OPENING" for row in dataset["display_transactions"]))

    def test_raw_inr_bills_match_canonical_summary_and_profit(self):
        raw_by_direction = {
            direction: sum(
                (line.amount_inr for trade in LicenseTrade.objects.filter(
                    license_type="DFIA", direction=direction,
                    lines__sr_number__license_id=self.license.id,
                ).distinct().prefetch_related("lines")
                 for line in trade.lines.filter(sr_number__license_id=self.license.id)),
                Decimal("0.00"),
            )
            for direction in (LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_SALE)
        }
        summary = self._dataset()["summary"]

        self.assertEqual(raw_by_direction[LicenseTrade.DIR_PURCHASE], Decimal("10000.00"))
        self.assertEqual(raw_by_direction[LicenseTrade.DIR_SALE], Decimal("15000.00"))
        self.assertEqual(summary["total_purchase_bill_inr"], raw_by_direction[LicenseTrade.DIR_PURCHASE])
        self.assertEqual(summary["total_sale_bill_inr"], raw_by_direction[LicenseTrade.DIR_SALE])
        self.assertEqual(summary["total_profit_loss"], Decimal("5000.00"))
        self.assertEqual(summary["profit_state"], "PROFIT")

    def test_purchase_bill_and_company_utilization_are_canonical(self):
        dataset = self._dataset()
        self.assertTrue(dataset["has_purchase_bill"])
        self.assertEqual(dataset["purchase_bill_status"], "WITH_PURCHASE_BILL")
        self.assertIsNone(dataset["opening_display"])
        self.assertEqual(
            dataset["company_utilizations"][self.exporter.id]["utilization_balance"],
            Decimal("0.00"),
        )
        self.assertEqual(dataset["company_utilizations"][self.exporter.id]["company_name"], self.exporter.name)
