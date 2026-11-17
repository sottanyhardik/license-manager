"""
View-level tests for `GET .../overview-allotments/`
(`apps/license/services/license_overview_allotments.py` /
`apps/license/views/license_overview.py`).

Proves the endpoint is O(1) queries regardless of allotment count by
asserting the SAME query count at 10 and 50 allotments.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class LicenseOverviewAllotmentsViewTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def make_allotment(self, company, **kwargs):
        return AllotmentModel.objects.create(company=company, item_name="Test Allotment Item", **kwargs)

    def make_allotment_item(self, allotment, item, cif_fc, qty=Decimal("100.000")):
        return AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"), qty=qty,
        )

    def _make_n_allotments(self, license_obj, company, item, n):
        for i in range(n):
            allotment = self.make_allotment(company)
            self.make_allotment_item(allotment, item, cif_fc=Decimal("100.00"), qty=Decimal("10.000"))

    def test_returns_allotment_rows_with_expected_shape_and_values(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        allotment = self.make_allotment(company)
        self.make_allotment_item(allotment, item, cif_fc=Decimal("500.00"), qty=Decimal("50.000"))

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-allotments/")

        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(set(row.keys()), {
            "allotment_number", "date", "customer", "product", "quantity", "cif_fc",
            "outstanding_cif_fc", "status",
        })
        self.assertEqual(row["outstanding_cif_fc"], 500.0)
        self.assertEqual(row["allotment_number"], f"ALT-{allotment.id}")
        self.assertEqual(row["customer"], company.name)
        self.assertEqual(row["product"], "Test Allotment Item")
        self.assertEqual(row["cif_fc"], 500.0)
        self.assertEqual(row["quantity"], 50.0)
        # `is_allotted` auto-flips True via `update_is_allotted_on_save` the
        # moment an AllotmentItems row is attached (a precondition for
        # appearing in this list at all) — see `_allotment_status`'s
        # docstring.
        self.assertEqual(row["status"], "Allotted")

    def test_status_derived_from_boolean_flags(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)

        # Deliberately does NOT set `is_boe=True` — status is now derived
        # from the REAL `BillOfEntryModel.allotment` M2M link, not that
        # hand-maintained cache boolean (found stale at real-world scale).
        boe_allotment = self.make_allotment(company)
        self.make_allotment_item(boe_allotment, item, cif_fc=Decimal("100.00"))
        boe = self.make_boe(company)
        boe.allotment.add(boe_allotment)

        allotted_allotment = self.make_allotment(company, is_allotted=True)
        self.make_allotment_item(allotted_allotment, item, cif_fc=Decimal("100.00"))

        approved_allotment = self.make_allotment(company, is_approved=True)
        self.make_allotment_item(approved_allotment, item, cif_fc=Decimal("100.00"))

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-allotments/")
        self.assertEqual(resp.status_code, 200, resp.data)
        by_number = {r["allotment_number"]: r for r in resp.data}
        self.assertEqual(by_number[f"ALT-{boe_allotment.id}"]["status"], "Linked to BOE")
        self.assertEqual(by_number[f"ALT-{allotted_allotment.id}"]["status"], "Allotted")
        self.assertEqual(by_number[f"ALT-{approved_allotment.id}"]["status"], "Approved")

    def test_query_count_is_constant_regardless_of_allotment_count(self):
        company_small = self.make_company()
        license_small = self.make_license(company_small)
        item_small = self.make_item(license_small, 1)
        self._make_n_allotments(license_small, company_small, item_small, 10)

        # 6 = previous 5 + one batched Balance Engine `get_allotment_rows`
        # query for `outstanding_cif_fc` (constant, not per allotment).
        with self.assertNumQueries(6):
            resp_small = self.client.get(f"/api/licenses/{license_small.id}/overview-allotments/")
        self.assertEqual(resp_small.status_code, 200, resp_small.data)
        self.assertEqual(len(resp_small.data), 10)

        company_large = self.make_company()
        license_large = self.make_license(company_large)
        item_large = self.make_item(license_large, 1)
        self._make_n_allotments(license_large, company_large, item_large, 50)

        with self.assertNumQueries(6):
            resp_large = self.client.get(f"/api/licenses/{license_large.id}/overview-allotments/")
        self.assertEqual(resp_large.status_code, 200, resp_large.data)
        self.assertEqual(len(resp_large.data), 50)

    def test_denies_authenticated_user_with_no_roles(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        resp = client.get(f"/api/licenses/{license_obj.id}/overview-allotments/")

        self.assertEqual(resp.status_code, 403)


class OverviewAllotmentsOutstandingCifScenarioTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """
    Regression for the Allotments-tab "Total Allotted" double count
    (docs/audits/LICENCE_OVERVIEW_DOUBLE_COUNTING_AUDIT.md): the gross
    `cif_fc` of a BOE-linked allotment is already inside BOE CIF, so the
    tab footer must sum `outstanding_cif_fc`, which must equal the Balance
    Engine's ALLOTMENT CIF (`LicenseBalanceCalculator.calculate_allotment`)
    in every representable scenario. Original CIF is 100 throughout
    (scenario letters match the audit doc). An M2M BOE link zeroes the
    whole allotment (scenarios C/D) — owner decision 2026-11-17 "M2M link =
    full consumption" (docs/decisions/2026-11-17-trade-line-pricing-and-m2m-consumption.md).
    """

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())
        self.company = self.make_company()
        self.license_obj = self.make_license(self.company)
        self.item = self.make_item(self.license_obj, 1)

    def _allot(self, cif_fc):
        allotment = AllotmentModel.objects.create(company=self.company, item_name="Scenario Allotment")
        allotment_item = AllotmentItems.objects.create(
            item=self.item, allotment=allotment, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"),
            qty=Decimal("10.000"),
        )
        return allotment, allotment_item

    def _linked_boe(self, allotment, cif_fc):
        boe = self.make_boe(self.company)
        row = self.make_debit_row(boe, self.item, cif_fc)
        boe.allotment.add(allotment)
        return boe, row

    def _rows_and_engine(self):
        from apps.license.services.balance_calculator import LicenseBalanceCalculator

        resp = self.client.get(f"/api/licenses/{self.license_obj.id}/overview-allotments/")
        self.assertEqual(resp.status_code, 200, resp.data)
        engine = LicenseBalanceCalculator.calculate_allotment(self.license_obj)
        return resp.data, engine

    def _assert_footer_equals_engine(self, rows, engine, expected):
        footer = sum(Decimal(str(r["outstanding_cif_fc"])) for r in rows)
        self.assertEqual(engine, expected)
        self.assertEqual(footer, engine)

    def test_a_unlinked_allotment_is_fully_outstanding(self):
        self._allot(Decimal("40.00"))
        rows, engine = self._rows_and_engine()
        self.assertEqual(rows[0]["cif_fc"], 40.0)
        self._assert_footer_equals_engine(rows, engine, Decimal("40.00"))

    def test_b_fully_billed_linked_allotment_is_not_outstanding(self):
        allotment, _ = self._allot(Decimal("40.00"))
        self._linked_boe(allotment, Decimal("40.00"))
        rows, engine = self._rows_and_engine()
        self.assertEqual(rows[0]["cif_fc"], 40.0)  # gross kept for display
        self.assertEqual(rows[0]["status"], "Linked to BOE")
        self._assert_footer_equals_engine(rows, engine, Decimal("0.00"))

    def test_c_partial_boe_via_m2m_link_pins_current_engine_zeroing(self):
        allotment, _ = self._allot(Decimal("40.00"))
        self._linked_boe(allotment, Decimal("15.00"))
        rows, engine = self._rows_and_engine()
        # Decided 2026-11-17: ANY M2M link is full consumption (no remainder 25).
        self._assert_footer_equals_engine(rows, engine, Decimal("0.00"))

    def test_c_prime_partial_formal_allocation_leaves_remainder(self):
        from apps.reconciliation.services.allocation_service import create_boe_allotment_allocation

        _, allotment_item = self._allot(Decimal("40.00"))
        boe = self.make_boe(self.company)
        row = self.make_debit_row(boe, self.item, Decimal("15.00"))
        create_boe_allotment_allocation(
            row, allotment_item, qty=Decimal("3.000"), cif_fc=Decimal("15.00"),
            cif_inr=Decimal("1267.50"), user=None,
        )
        rows, engine = self._rows_and_engine()
        self.assertEqual(rows[0]["cif_fc"], 40.0)
        self._assert_footer_equals_engine(rows, engine, Decimal("25.00"))

    def test_d_mixed_allotments_footer_excludes_only_linked(self):
        self._allot(Decimal("30.00"))  # outstanding
        linked, _ = self._allot(Decimal("60.00"))
        self._linked_boe(linked, Decimal("20.00"))
        rows, engine = self._rows_and_engine()
        gross = sum(Decimal(str(r["cif_fc"])) for r in rows)
        self.assertEqual(gross, Decimal("90.00"))  # old footer value (double counts 60)
        self._assert_footer_equals_engine(rows, engine, Decimal("30.00"))
