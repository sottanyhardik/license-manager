"""Regression coverage for the native Customs Ledger download."""
from decimal import Decimal
from io import BytesIO

from django.test import TestCase
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.license.models import LicenseExportItemModel
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class CustomLedgerPdfTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())
        self.company = self.make_company()
        self.licence = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=self.licence, cif_fc=Decimal("1000.00"))
        self.item = self.make_item(self.licence, 1)
        self.item.description = "A deliberately long import-item description which must wrap in native table cells"
        self.item.save(update_fields=["description"])
        boe = self.make_boe(self.company, number="BOE-NATIVE-PDF-001")
        self.make_debit_row(boe, self.item, cif_fc=Decimal("100.00"), qty=Decimal("100.000"))

    def test_endpoint_is_native_searchable_pdf_with_expected_data(self):
        response = self.client.get(f"/api/license-ledger/{self.licence.id}/custom-ledger-pdf/?license_type=DFIA")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(f'{self.licence.license_number}.pdf', response["Content-Disposition"])
        raw = b"".join(response.streaming_content)
        self.assertTrue(raw.startswith(b"%PDF"))
        reader = PdfReader(BytesIO(raw))
        self.assertGreaterEqual(len(reader.pages), 1)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        compact = text.replace("\n", "")
        for expected in ("Customs Ledger", self.licence.license_number, "BOE-NATIVE-PDF-001"):
            self.assertIn(expected, compact)
        # Native ReportLab content streams expose extractable text; they are
        # not a single raster page image masquerading as a PDF.
        self.assertGreater(len(text.strip()), 100)
        self.assertNotIn("/Subtype /Image", raw.decode("latin1", errors="ignore"))

    def test_pdf_excludes_genuinely_hidden_boe_rows(self):
        hidden = self.make_boe(self.company, number="HIDDEN-BOE", invoice_no="OTH")
        self.make_debit_row(hidden, self.item, cif_fc=Decimal("50.00"))
        response = self.client.get(f"/api/license-ledger/{self.licence.id}/custom-ledger-pdf/?license_type=DFIA")
        raw = b"".join(response.streaming_content)
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages)
        self.assertNotIn("HIDDEN-BOE", text)
