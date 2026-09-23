"""Regression coverage for the protected balance-PDF endpoint."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.license.models import LicenseExportItemModel
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class BalancePdfEndpointTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.license.license_number = "0310713518"
        self.license.license_expiry_date = date(2014, 3, 31)
        self.license.save(update_fields=["license_number", "license_expiry_date"])
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("0.40"))
        self.item = self.make_item(self.license, 1)
        self.item.cif_fc = Decimal("0.40")
        self.item.save(update_fields=["cif_fc"])
        self.make_debit_row(
            self.make_boe(self.company, number="BOE-BALANCE-PDF-001"),
            self.item,
            cif_fc=Decimal("0.00"),
            qty=Decimal("0.000"),
        )
        self.make_item(self.license, 2)  # A valid zero-allocation second item.

    def test_expired_regression_license_returns_a_valid_pdf(self):
        response = self.client.get(f"/api/licenses/{self.license.id}/balance-pdf/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="Balance_0310713518.pdf"',
        )
        self.assertTrue(response.content.startswith(b"%PDF"))
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages)
        self.assertIn("0310713518", text)
        self.assertIn("0.40", text)
        self.assertIn("BOE-BALANCE-PDF-001", text)

    def test_active_license_returns_a_valid_pdf(self):
        self.license.license_expiry_date = date(2030, 3, 31)
        self.license.save(update_fields=["license_expiry_date"])

        response = self.client.get(f"/api/licenses/{self.license.id}/balance-pdf/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_unauthenticated_request_is_rejected(self):
        response = APIClient().get(f"/api/licenses/{self.license.id}/balance-pdf/")

        self.assertIn(response.status_code, {401, 403})

    @patch("apps.license.services.exporters.license_balance_pdf.build_balance_pdf_response")
    def test_generation_error_is_logged_and_safely_returned(self, generate_pdf):
        generate_pdf.side_effect = RuntimeError("renderer details must not reach clients")

        with self.assertLogs("apps.license.views.license", level="ERROR") as logs:
            response = self.client.get(f"/api/licenses/{self.license.id}/balance-pdf/")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {
            "code": "balance_pdf_generation_failed",
            "detail": "Unable to generate Balance PDF. Please try again.",
        })
        self.assertNotIn("renderer details", response.content.decode())
        self.assertTrue(any("Balance PDF generation failed" in message for message in logs.output))
