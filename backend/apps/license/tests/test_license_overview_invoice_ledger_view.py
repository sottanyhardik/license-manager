"""
View-level tests for `GET .../overview-invoice-ledger/`
(`apps/license/services/license_overview_invoices.py` /
`apps/license/views/license_overview.py`).

Covers all 4 purchase/sale presence combinations for
`missing_purchase_invoice_warning` (only SALE / PURCHASE+SALE / only
PURCHASE / no trades at all), plus status derivation via the existing
`LicenseTrade.paid_or_received`/`due_amount` properties (never
reimplemented) and the `gst: None` ("not tracked") contract.
"""
import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin
from apps.trade.models import LicenseTrade, LicenseTradeLine, LicenseTradePayment


class LicenseOverviewInvoiceLedgerViewTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def make_trade(self, direction, from_company=None, to_company=None, invoice_number=None):
        return LicenseTrade.objects.create(
            direction=direction,
            from_company=from_company,
            to_company=to_company,
            invoice_number=invoice_number or f"INV-{uuid.uuid4().hex[:8]}",
        )

    def make_line(self, trade, item, cif_fc=Decimal("100.00")):
        return LicenseTradeLine.objects.create(
            trade=trade,
            sr_number=item,
            description=item.description or "Test Item",
            mode=LicenseTradeLine.MODE_CIF_INR,
            cif_fc=cif_fc,
            cif_inr=cif_fc * Decimal("84.5"),
            pct=Decimal("100"),
        )

    def test_only_sale_trades_shows_warning(self):
        company = self.make_company()
        customer = self.make_company("Customer Co")
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        sale = self.make_trade(LicenseTrade.DIR_SALE, from_company=company, to_company=customer)
        self.make_line(sale, item, cif_fc=Decimal("1000.00"))

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-invoice-ledger/")

        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(len(data["purchase"]), 0)
        self.assertEqual(len(data["sale"]), 1)
        self.assertEqual(data["warning"], {
            "show_warning": True,
            "message": "Purchase invoice has not been created for this licence.",
        })
        sale_row = data["sale"][0]
        self.assertEqual(sale_row["company_name"], "Customer Co")
        self.assertIsNone(sale_row["gst"])
        self.assertEqual(sale_row["status"], "Unpaid")

    def test_purchase_and_sale_no_warning(self):
        company = self.make_company()
        supplier = self.make_company("Supplier Co")
        customer = self.make_company("Customer Co")
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)

        purchase = self.make_trade(LicenseTrade.DIR_PURCHASE, from_company=supplier, to_company=company)
        self.make_line(purchase, item, cif_fc=Decimal("500.00"))

        sale = self.make_trade(LicenseTrade.DIR_SALE, from_company=company, to_company=customer)
        self.make_line(sale, item, cif_fc=Decimal("1000.00"))
        sale.refresh_from_db()
        LicenseTradePayment.objects.create(trade=sale, amount=sale.total_amount)

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-invoice-ledger/")

        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(len(data["purchase"]), 1)
        self.assertEqual(len(data["sale"]), 1)
        self.assertEqual(data["warning"], {
            "show_warning": False,
            "message": "Purchase invoice has not been created for this licence.",
        })
        self.assertEqual(data["purchase"][0]["company_name"], "Supplier Co")
        self.assertEqual(data["sale"][0]["status"], "Paid")

    def test_only_purchase_no_warning(self):
        company = self.make_company()
        supplier = self.make_company("Supplier Co")
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)

        purchase = self.make_trade(LicenseTrade.DIR_PURCHASE, from_company=supplier, to_company=company)
        self.make_line(purchase, item, cif_fc=Decimal("500.00"))

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-invoice-ledger/")

        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(len(data["purchase"]), 1)
        self.assertEqual(len(data["sale"]), 0)
        self.assertFalse(data["warning"]["show_warning"])

    def test_no_trades_at_all_no_warning(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-invoice-ledger/")

        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(data["purchase"], [])
        self.assertEqual(data["sale"], [])
        self.assertEqual(data["warning"], {
            "show_warning": False,
            "message": "Purchase invoice has not been created for this licence.",
        })

    def test_partial_payment_status(self):
        company = self.make_company()
        customer = self.make_company("Customer Co")
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        sale = self.make_trade(LicenseTrade.DIR_SALE, from_company=company, to_company=customer)
        self.make_line(sale, item, cif_fc=Decimal("1000.00"))
        sale.refresh_from_db()
        LicenseTradePayment.objects.create(trade=sale, amount=Decimal("100.00"))

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-invoice-ledger/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["sale"][0]["status"], "Partial")

    def test_denies_authenticated_user_with_no_roles(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        resp = client.get(f"/api/licenses/{license_obj.id}/overview-invoice-ledger/")

        self.assertEqual(resp.status_code, 403)
