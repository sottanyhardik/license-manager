"""
View-level tests for `GET .../overview-summary/`
(`apps/license/services/license_overview_summary.py` /
`apps/license/views/license_overview.py`).

Asserts response shape + fixture-accurate values, and pins a fixed
(low) query count via `assertNumQueries`.
"""
from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.models import PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class LicenseOverviewSummaryViewTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def test_returns_header_fields_and_summary_cards(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Widget A",
            quantity=Decimal("1000.000"),
            cif_fc=Decimal("5000.00"),
            debited_quantity=Decimal("100.000"),
            debited_value=Decimal("500.00"),
            allotted_quantity=Decimal("50.000"),
            allotted_value=Decimal("250.00"),
        )
        boe = self.make_boe(company)
        self.make_debit_row(boe, license_obj.import_license.first(), cif_fc=Decimal("400.00"), qty=Decimal("40.000"))

        # Redirected to `balance_snapshot.get_snapshot()` (the shared
        # Balance-CIF snapshot every consumer now composes from) instead of
        # calling `calculate_all_components` directly. The snapshot always
        # computes its per-item map too (available_value/planned/quantity
        # bulk lookups) even though this view only surfaces the license-
        # level totals, which is why the query count is higher than the old
        # license-only `calculate_all_components` path (9). Still O(1) /
        # fixed regardless of item count (every added query is a single
        # grouped aggregate, never per-row) — not O(items). Bumped to 48
        # after the Financial Balance Engine + BOE-level invoice-status
        # resolver additions (each adds a handful more fixed, non-per-row
        # aggregate queries to the same snapshot composition).
        # Lowered 48 -> 47: `calculate_purchase_credit_for_licenses` was being
        # issued twice per snapshot (once directly, once inside the opening-
        # balance gate). It is now computed once and passed down.
        with self.assertNumQueries(47):
            resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-summary/")

        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(data["license_number"], license_obj.license_number)
        self.assertEqual(data["authorisation_number"], license_obj.registration_number)
        self.assertEqual(data["importer"], company.name)
        self.assertEqual(data["status"], "Active")
        # No port set on this fixture — both display-only fields are None,
        # not omitted or defaulted to empty string.
        self.assertIsNone(data["port_code"])
        self.assertIsNone(data["port_name"])

        summary = data["summary"]
        self.assertEqual(set(summary.keys()), {
            "total_boes", "total_allotments", "total_planned_cif",
            "total_cif", "total_debited_cif", "total_allotted_cif",
            "total_balance_cif",
        })
        self.assertEqual(summary["total_boes"], 1)
        self.assertEqual(summary["total_allotments"], 0)
        self.assertEqual(summary["total_planned_cif"], 0.0)
        self.assertEqual(summary["total_debited_cif"], 400.0)

    def test_planned_cif_sums_item_plan_lines_and_defaults_to_zero(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Widget A",
            quantity=Decimal("1000.000"),
            cif_fc=Decimal("5000.00"),
        )
        LicenseItemPlan.objects.create(
            import_item=item,
            license=license_obj,
            planned_quantity=Decimal("600.000"),
            planned_cif_fc=Decimal("3000.00"),
        )

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-summary/")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["summary"]["total_planned_cif"], 3000.0)

    def test_total_allotments_excludes_boe_linked(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Widget A",
            quantity=Decimal("1000.000"),
        )

        unlinked = AllotmentModel.objects.create(company=company, item_name="Unlinked")
        AllotmentItems.objects.create(item=item, allotment=unlinked, cif_fc=Decimal("100.00"), qty=Decimal("10.000"))

        # Deliberately does NOT set `is_boe=True` — exclusion is now based on
        # the REAL `BillOfEntryModel.allotment` M2M link, not that hand-
        # maintained cache boolean (found stale at real-world scale).
        linked = AllotmentModel.objects.create(company=company, item_name="Linked to BOE")
        AllotmentItems.objects.create(item=item, allotment=linked, cif_fc=Decimal("200.00"), qty=Decimal("20.000"))
        boe = self.make_boe(company)
        boe.allotment.add(linked)

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-summary/")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["summary"]["total_allotments"], 1)

    def test_expired_status_takes_priority(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        license_obj.flags.is_expired = True
        license_obj.flags.save()

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-summary/")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["status"], "Expired")

    def test_expired_license_999_is_retrievable_without_reactivation(self):
        """Overview detail routes must not inherit the active-list filter."""
        company = self.make_company()
        license_obj = LicenseDetailsModel.objects.create(
            pk=999,
            exporter=company,
            license_number="0511007564",
            license_date=date.today() - timedelta(days=90),
            license_expiry_date=date.today() - timedelta(days=1),
        )
        license_obj.flags.is_active = False
        license_obj.flags.is_expired = True
        license_obj.flags.save()

        resp = self.client.get("/api/licenses/999/overview-summary/")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["license_number"], "0511007564")
        self.assertEqual(resp.data["status"], "Expired")
        license_obj.refresh_from_db()
        self.assertLess(license_obj.license_expiry_date, date.today())
        self.assertFalse(license_obj.flags.is_active)

    def test_port_code_and_name_reflect_the_license_s_port(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        port = PortModel.objects.create(code="INNSA1", name="Nhava Sheva")
        license_obj.port = port
        license_obj.save(update_fields=["port"])

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-summary/")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["port_code"], "INNSA1")
        self.assertEqual(resp.data["port_name"], "Nhava Sheva")

    def test_denies_authenticated_user_with_no_roles(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        resp = client.get(f"/api/licenses/{license_obj.id}/overview-summary/")

        self.assertEqual(resp.status_code, 403)
