"""
View-level tests for the Licence Balance & Financial Reconciliation
Workspace actions attached to `LicenseDetailsViewSet`
(`apps/license/views/license_balance_ledger.py`).

Covers: the GET dataset endpoint, permission enforcement
(`LicenseBalanceLedgerPermission`), and the write actions' happy paths +
validation error surfacing, using the real HTTP layer (APIClient) rather
than calling the view functions directly, so routing/permission wiring is
exercised too.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.test import APIClient

from apps.core.constants import DEBIT
from apps.core.models import CompanyModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.reconciliation.models import ExternalInvoiceLink, ReconciliationLog

User = get_user_model()


class LicenseBalanceLedgerFixtureMixin:
    def make_company(self, name="Test Co"):
        return CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name=name)

    def make_port(self):
        return PortModel.objects.create(code=str(uuid.uuid4().int)[:6], name="Test Port")

    def make_license(self, company):
        return LicenseDetailsModel.objects.create(
            license_number="03" + str(uuid.uuid4().int)[:8],
            license_date=datetime.now().date(),
            license_expiry_date=datetime.now().date() + timedelta(days=365),
            exporter=company,
        )

    def make_item(self, license_obj, serial_number):
        return LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=serial_number,
            description=f"Test Import Item {serial_number}",
            quantity=Decimal("1000.000"),
            available_quantity=Decimal("1000.000"),
        )

    def make_boe(self, company, number=None, invoice_no=""):
        return BillOfEntryModel.objects.create(
            company=company,
            bill_of_entry_number=number or str(uuid.uuid4().int)[:9],
            bill_of_entry_date=datetime.now().date(),
            exchange_rate=Decimal("84.50"),
            invoice_no=invoice_no,
        )

    def make_debit_row(self, boe, item, cif_fc, qty=Decimal("100.000")):
        return RowDetails.objects.create(
            bill_of_entry=boe,
            sr_number=item,
            transaction_type=DEBIT,
            cif_inr=cif_fc * Decimal("84.5"),
            cif_fc=cif_fc,
            qty=qty,
        )

    def make_superuser(self):
        return User.objects.create_user(
            username=f"balance-ledger-{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123!",
            is_superuser=True,
        )

    def make_plain_user(self):
        """An authenticated user with no roles at all."""
        return User.objects.create_user(
            username=f"no-role-{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123!",
        )


class BalanceLedgerGetTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def test_returns_full_dataset(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"))

        resp = self.client.get(f"/api/licenses/{license_obj.id}/balance-ledger/")

        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(set(data.keys()), {
            "license", "financial_ledger", "invoice_boe", "boe_allotment", "reconciliation", "warnings",
        })
        self.assertEqual(data["license"]["license_number"], license_obj.license_number)
        self.assertGreaterEqual(len(data["financial_ledger"]["rows"]), 2)  # opening + final at minimum

    def test_denies_authenticated_user_with_no_roles(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        resp = client.get(f"/api/licenses/{license_obj.id}/balance-ledger/")

        self.assertEqual(resp.status_code, 403)

    def test_denies_anonymous_user(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        client = APIClient()
        resp = client.get(f"/api/licenses/{license_obj.id}/balance-ledger/")

        self.assertEqual(resp.status_code, 403)


class MarkExternalInvoiceViewTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.user = self.make_superuser()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_mark_creates_link_and_audit_log(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("500.00"))

        resp = self.client.post(
            f"/api/licenses/{license_obj.id}/mark-external-invoice/",
            {"row_details_id": row.id, "invoice_number": "OTH-001245", "qty": 0, "cif_fc": "500.00", "cif_inr": "42250.00"},
            format="json",
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        link = ExternalInvoiceLink.objects.get(pk=resp.data["link_id"])
        self.assertEqual(link.invoice_number, "OTH-001245")
        self.assertEqual(link.status, ExternalInvoiceLink.STATUS_ACTIVE)
        self.assertEqual(link.created_by_id, self.user.id)

        log = ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_MARK_EXTERNAL_INVOICE).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, self.user.id)

    def test_over_allocation_returns_400(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("500.00"))

        resp = self.client.post(
            f"/api/licenses/{license_obj.id}/mark-external-invoice/",
            {"row_details_id": row.id, "invoice_number": "OTH-001245", "qty": 0, "cif_fc": "999999.00", "cif_inr": "1.00"},
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.data)

    def test_blank_invoice_number_returns_400(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("500.00"))

        resp = self.client.post(
            f"/api/licenses/{license_obj.id}/mark-external-invoice/",
            {"row_details_id": row.id, "invoice_number": "   ", "qty": 0, "cif_fc": "10.00", "cif_inr": "1.00"},
            format="json",
        )

        self.assertEqual(resp.status_code, 400)

    def test_row_details_from_another_license_rejected(self):
        company = self.make_company()
        license_a = self.make_license(company)
        license_b = self.make_license(company)
        item_b = self.make_item(license_b, 1)
        boe = self.make_boe(company)
        row_b = self.make_debit_row(boe, item_b, cif_fc=Decimal("500.00"))

        resp = self.client.post(
            f"/api/licenses/{license_a.id}/mark-external-invoice/",
            {"row_details_id": row_b.id, "invoice_number": "OTH-001245", "qty": 0, "cif_fc": "10.00", "cif_inr": "1.00"},
            format="json",
        )

        self.assertEqual(resp.status_code, 400)

    def test_denied_without_boe_manager_role(self):
        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("500.00"))

        resp = client.post(
            f"/api/licenses/{license_obj.id}/mark-external-invoice/",
            {"row_details_id": row.id, "invoice_number": "OTH-001245", "qty": 0, "cif_fc": "10.00", "cif_inr": "1.00"},
            format="json",
        )

        self.assertEqual(resp.status_code, 403)


class ReverseExternalInvoiceViewTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.user = self.make_superuser()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_reverse_requires_reason(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("500.00"))
        link = ExternalInvoiceLink.objects.create(
            row_details=row, invoice_number="OTH-001245",
            qty=Decimal("0"), cif_fc=Decimal("500.00"), cif_inr=Decimal("42250.00"),
            created_by=self.user,
        )

        resp = self.client.post(
            f"/api/licenses/{license_obj.id}/reverse-external-invoice/",
            {"link_id": link.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_reverse_succeeds_with_reason(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("500.00"))
        link = ExternalInvoiceLink.objects.create(
            row_details=row, invoice_number="OTH-001245",
            qty=Decimal("0"), cif_fc=Decimal("500.00"), cif_inr=Decimal("42250.00"),
            created_by=self.user,
        )

        resp = self.client.post(
            f"/api/licenses/{license_obj.id}/reverse-external-invoice/",
            {"link_id": link.id, "reason": "wrong BOE"},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        link.refresh_from_db()
        self.assertEqual(link.status, ExternalInvoiceLink.STATUS_REVERSED)
        self.assertFalse(link.is_current)


class RecalculateViewTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.user = self.make_superuser()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_recalculate_refreshes_balance_cif_and_logs(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        self.make_item(license_obj, 1)

        resp = self.client.post(f"/api/licenses/{license_obj.id}/recalculate/", {}, format="json")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn("balance_cif", resp.data)
        log = ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_RECALCULATE).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, self.user.id)

    def test_denied_without_license_manager_role(self):
        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        company = self.make_company()
        license_obj = self.make_license(company)

        resp = client.post(f"/api/licenses/{license_obj.id}/recalculate/", {}, format="json")

        self.assertEqual(resp.status_code, 403)
