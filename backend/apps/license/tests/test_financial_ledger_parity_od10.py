"""OD-10 follow-up parity tests (verification 2026-11-15).

Pins, against the approved rules:
* trade_running_balance counts a licence's acquisition ONCE (canonical
  summary.current_balance), not opening + purchase (raw
  license_running_balance double count), and excludes COMMISSION trades;
* OD-01: the financial Available CIF is SIGNED end-to-end (engine, bulk
  engine, ledger summary + final row) and flagged with is_over_utilised;
* the balance Excel and PDF show the same Current Available Balance as the
  screen and the separately labelled Trade Running Balance.
"""
import io
import uuid
from datetime import datetime
from decimal import Decimal

import openpyxl
from django.test import RequestFactory, TestCase
from pypdf import PdfReader

from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.exporters.license_balance_excel import build_balance_excel
from apps.license.services.exporters.license_balance_pdf import build_balance_pdf_response
from apps.license.services.license_balance_ledger_builder import LicenseBalanceLedgerBuilder
from apps.license.tests import test_balance_ledger_views as _ledger_view_tests
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin
from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin

TRADE_LABEL = "Trade Running Balance (purchases − sales)"


class Od10ParityTests(LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase):
    _make_purchase_trade = _ledger_view_tests.FinancialLedgerOpeningBalanceGateTests._make_purchase_trade

    def _make_trade(self, direction, company, item, cif_fc):
        from apps.trade.models import LicenseTrade, LicenseTradeLine
        other = self.make_company(name="Counterparty")
        trade = LicenseTrade.objects.create(
            direction=direction, from_company=other, to_company=company,
            invoice_number=f"{direction[:3]}-{uuid.uuid4().int % 999999:06d}",
            invoice_date=datetime.now().date(),
        )
        LicenseTradeLine.objects.create(
            trade=trade, sr_number=item, description=item.description or "Item",
            mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"),
        )
        return trade

    def _purchased_and_partly_sold(self):
        """Face value 50,000 acquired by a 50,000 PURCHASE, 20,000 sold."""
        company = self.make_company()
        licence = self.make_license(company)
        LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal("50000.00"))
        item = self.make_item(licence, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("50000.00"))
        sale = self.make_sale_trade(company, invoice_number=f"SALE-{uuid.uuid4().hex[:6]}")
        self.make_trade_line(sale, item, cif_fc=Decimal("20000.00"))
        return licence, company, item

    # ---- trade_running_balance --------------------------------------------
    def test_trade_running_balance_counts_acquisition_once(self):
        licence, _company, _item = self._purchased_and_partly_sold()
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(license_id=licence.id, license_type="DFIA")
        summary = LicenseBalanceLedgerBuilder.build(licence)["financial_ledger"]["summary"]

        # 30,000 = 50,000 purchase - 20,000 sale; a double count of the
        # acquisition (opening + purchase) would give 80,000. Raw running
        # total and the de-duplicated summary figure the trade-ledger page
        # shows must agree (opening seed is suppressed when a PURCHASE exists).
        self.assertEqual(summary["trade_running_balance"], Decimal("30000.00"))
        self.assertEqual(canonical["license_running_balance"], canonical["summary"]["current_balance"])

    def test_trade_running_balance_excludes_commission(self):
        from apps.trade.models import LicenseTrade
        licence, company, item = self._purchased_and_partly_sold()
        self._make_trade(LicenseTrade.DIR_COMMISSION_SALE, company, item, Decimal("5000.00"))
        self._make_trade(LicenseTrade.DIR_COMMISSION_PURCHASE, company, item, Decimal("7000.00"))

        summary = LicenseBalanceLedgerBuilder.build(licence)["financial_ledger"]["summary"]
        self.assertEqual(summary["trade_running_balance"], Decimal("30000.00"))

    # ---- negative / over-utilisation (additive) ---------------------------
    def test_over_utilisation_is_flagged_with_signed_balance(self):
        company = self.make_company()
        licence = self.make_license(company)
        LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal("10000.00"))
        item = self.make_item(licence, 1)
        self.make_debit_row(self.make_boe(company), item, cif_fc=Decimal("15000.00"))

        dataset = LicenseBalanceLedgerBuilder.build(licence)
        summary = dataset["financial_ledger"]["summary"]
        expected = Decimal("-5000.00")  # 10,000 original - 15,000 BOE

        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(licence), expected)
        self.assertEqual(
            LicenseBalanceCalculator.calculate_financial_balance_for_licenses([licence.id])[licence.id], expected
        )
        self.assertEqual(summary["computed_balance"], expected)
        self.assertEqual(dataset["financial_ledger"]["rows"][-1]["running_balance"], expected)
        self.assertEqual(summary["engine_balance"], expected)
        self.assertFalse(summary["mismatched"])
        self.assertTrue(summary["is_over_utilised"])

    def test_not_over_utilised_when_balance_positive(self):
        licence, _c, _i = self._purchased_and_partly_sold()
        summary = LicenseBalanceLedgerBuilder.build(licence)["financial_ledger"]["summary"]
        self.assertFalse(summary["is_over_utilised"])
        self.assertGreater(summary["computed_balance"], Decimal("0"))

    # ---- Excel / PDF numerical parity -------------------------------------
    def _excel_summary(self, licence):
        wb = openpyxl.load_workbook(io.BytesIO(build_balance_excel(licence).content))
        found = {}
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [c for c in row if c is not None]
                if len(cells) >= 2 and isinstance(cells[0], str):
                    found.setdefault(cells[0], cells[1])
        return found

    def _pdf_text(self, licence):
        request = RequestFactory().get("/")
        request.user = self.make_superuser()
        response = build_balance_pdf_response(licence, request)
        body = b"".join(response.streaming_content) if getattr(response, "streaming", False) else response.content
        return " ".join(page.extract_text() for page in PdfReader(io.BytesIO(body)).pages)

    def test_excel_and_pdf_match_screen(self):
        licence, _c, _i = self._purchased_and_partly_sold()
        summary = LicenseBalanceLedgerBuilder.build(licence)["financial_ledger"]["summary"]
        self.assertEqual(summary["computed_balance"], LicenseBalanceCalculator.calculate_financial_balance(licence))

        excel = self._excel_summary(licence)
        self.assertEqual(Decimal(str(excel["Current Available Balance"])), summary["computed_balance"])
        self.assertEqual(Decimal(str(excel[TRADE_LABEL])), summary["trade_running_balance"])

        text = " ".join(self._pdf_text(licence).split())
        self.assertIn(f"Current Available Balance ${summary['computed_balance']:,.2f}", text)
        self.assertIn(f"{TRADE_LABEL} ${summary['trade_running_balance']:,.2f}", text)
