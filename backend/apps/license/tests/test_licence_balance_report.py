"""Database-backed tests for the canonical licence item balance report.

Builds real records (licence, SR items, sales with membership, BOE debits, allocations,
allotments) and checks the report that the API serves. Pure calculation rules are covered in
test_sale_boe_allocation.py and test_licence_item_balance.py.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.licence_balance_report import build_licence_balance_reports
from apps.reconciliation.models import InvoiceBOEAllocation
from apps.trade.models import LicenseTrade, LicenseTradeLine, TradeUtilisationClassification

D = Decimal


class ReportFixture(TestCase):
    def setUp(self):
        self.seller = CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name="Seller Co")
        self.customer = CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name="Customer One")
        self.customer_two = CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name="Customer Two")
        self.licence = self._licence("03" + str(uuid.uuid4().int)[:8])
        self.item = self._item(self.licence, serial=1, qty="1000.000", cif="1000.00", unit="kg")

    # builders -----------------------------------------------------------

    def _licence(self, number):
        return LicenseDetailsModel.objects.create(
            license_number=number,
            license_date=date.today(),
            license_expiry_date=date.today() + timedelta(days=365),
            exporter=self.seller,
        )

    def _item(self, licence, *, serial, qty, cif, unit="kg"):
        return LicenseImportItemsModel.objects.create(
            license=licence, serial_number=serial, description=f"Item {serial}",
            quantity=D(qty), cif_fc=D(cif), cif_inr=D(cif) * D("84.5"), unit=unit,
        )

    def _sale(self, *, invoice, cif, qty, item=None, to=None):
        item = item or self.item
        trade = LicenseTrade.objects.create(
            direction="SALE", invoice_number=invoice, invoice_date=date.today(),
            from_company=self.seller, to_company=to or self.customer,
        )
        line = LicenseTradeLine.objects.create(
            trade=trade, sr_number=item, cif_fc=D(cif), cif_inr=D(cif) * D("84.5"), qty_kg=D(qty),
        )
        return trade, line

    def _boe(self, number, *, item=None, cif, qty, trades=()):
        item = item or self.item
        boe = BillOfEntryModel.objects.create(
            company=self.customer, bill_of_entry_number=number,
            bill_of_entry_date=date.today(), exchange_rate=D("84.50"),
        )
        row = RowDetails.objects.create(
            bill_of_entry=boe, sr_number=item, transaction_type=DEBIT,
            cif_fc=D(cif), cif_inr=D(cif) * D("84.5"), qty=D(qty),
        )
        for trade in trades:
            trade.boes.add(boe)
        return boe, row

    def _allocate(self, row, line, cif, qty):
        return InvoiceBOEAllocation.objects.create(
            row_details=row, trade_line=line, allocated_cif_fc=D(cif),
            allocated_cif_inr=D(cif) * D("84.5"), allocated_qty=D(qty),
            status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=True,
        )

    def _allotment(self, item, *, cif, qty, boes=()):
        allotment = AllotmentModel.objects.create(company=self.customer)
        AllotmentItems.objects.create(
            allotment=allotment, item=item, cif_fc=D(cif), cif_inr=D(cif) * D("84.5"), qty=D(qty),
        )
        for boe in boes:
            boe.allotment.add(allotment)
        return allotment

    def report(self, licence=None):
        return build_licence_balance_reports([(licence or self.licence).id])[(licence or self.licence).id]

    def item_report(self, report, item=None):
        item = item or self.item
        return next(i for i in report.items if i.item_id == item.id)


class BriefExampleTests(ReportFixture):
    def test_quantity_and_cif_example_balances_to_200(self):
        # Original 1,000. Debited 540 (BOEs 200 + 340, uncovered). Allotted 160. Invoiced 100.
        self._boe("B-001", cif="200", qty="200")
        self._boe("B-002", cif="340", qty="340")
        self._allotment(self.item, cif="160", qty="160")
        self._sale(invoice="INV-001", cif="100", qty="100")

        item = self.item_report(self.report())
        self.assertEqual(item.cif["debited"], "540.00")
        self.assertEqual(item.cif["allotted"], "160.00")
        self.assertEqual(item.cif["invoiced"], "100.00")
        self.assertEqual(item.cif["available"], "200.00")
        self.assertEqual(item.qty["available"], "200.000")
        self.assertEqual(item.qty["debited"], "540.000")

    def test_running_balance_ends_at_available(self):
        self._boe("B-001", cif="200", qty="200")
        self._sale(invoice="INV-001", cif="100", qty="100")
        item = self.item_report(self.report())
        cif_rows = [r for r in item.cif_ledger if not r.memo]
        self.assertEqual(cif_rows[0].running_balance, D("1000.00"))
        self.assertEqual(cif_rows[-1].running_balance, D("700.00"))
        self.assertEqual(item.cif["available"], "700.00")


class SaleCoverageTests(ReportFixture):
    def test_sale_500_with_linked_boes_190_keeps_seller_at_500(self):
        trade, line = self._sale(invoice="LGL-1", cif="500", qty="500")
        b1, _ = self._boe("S-1", cif="40", qty="40", trades=[trade])
        b2, _ = self._boe("S-2", cif="50", qty="50", trades=[trade])
        b3, _ = self._boe("S-3", cif="100", qty="100", trades=[trade])
        item = self.item_report(self.report())
        self.assertEqual(item.cif["invoiced"], "500.00")
        self.assertEqual(item.cif["invoiced_boe_covered"], "190.00")
        self.assertEqual(item.cif["debited"], "0.00")
        self.assertEqual(item.cif["available"], "500.00")
        self.assertEqual(item.customers[0]["remaining_entitlement"], "310.00")
        covered = [r for r in item.cif_ledger if r.kind == "SALE_COVERED_BOE"]
        self.assertTrue(all(r.memo for r in covered))

    def test_additional_uncovered_boe_reduces_available_to_470(self):
        trade, _ = self._sale(invoice="LGL-1", cif="500", qty="500")
        self._boe("S-1", cif="190", qty="190", trades=[trade])
        self._boe("U-1", cif="30", qty="30")
        item = self.item_report(self.report())
        self.assertEqual(item.cif["debited"], "30.00")
        self.assertEqual(item.cif["available"], "470.00")

    def test_over_linked_excess_is_debited_and_flagged(self):
        trade, line = self._sale(invoice="LGL-1", cif="500", qty="500")
        self._boe("O-1", cif="300", qty="300", trades=[trade])
        self._boe("O-2", cif="300", qty="300", trades=[trade])
        item = self.item_report(self.report())
        self.assertEqual(item.cif["debited"], "100.00")
        self.assertEqual(item.cif["available"], "400.00")
        self.assertIn("OVER_LINKED", item.flags)
        self.assertEqual(item.status, "REVIEW REQUIRED")

    def test_partial_allocation_row_leaves_remainder_as_debit(self):
        trade, line = self._sale(invoice="LGL-1", cif="100", qty="100")
        _, row = self._boe("P-1", cif="150", qty="150", trades=[trade])
        self._allocate(row, line, cif="100", qty="100")
        item = self.item_report(self.report())
        self.assertEqual(item.cif["debited"], "50.00")
        self.assertEqual(item.cif["available"], "850.00")


class ItemAndUnitTests(ReportFixture):
    def test_cross_item_boe_is_uncovered_on_its_own_item_and_flagged(self):
        other = self._item(self.licence, serial=2, qty="500.000", cif="500.00")
        trade, _ = self._sale(invoice="LGL-X", cif="200", qty="200", item=other)
        self._boe("X-1", item=self.item, cif="80", qty="80", trades=[trade])
        report = self.report()
        item = self.item_report(report)
        self.assertEqual(item.cif["debited"], "80.00")
        self.assertIn("CROSS_ITEM", item.flags)
        self.assertEqual(item.status, "REVIEW REQUIRED")

    def test_two_sales_over_allocating_one_boe_is_refused(self):
        t1, _ = self._sale(invoice="A", cif="80", qty="80")
        t2, _ = self._sale(invoice="B", cif="80", qty="80")
        self._boe("DUP-1", cif="100", qty="100", trades=[t1, t2])
        item = self.item_report(self.report())
        self.assertEqual(item.status, "OVER-ALLOCATED")
        self.assertIsNone(item.cif.get("available"))

    def test_mts_unit_withholds_quantity_totals(self):
        mts = self._item(self.licence, serial=3, qty="50.000", cif="10.00", unit="mts")
        report = self.report()
        mts_item = self.item_report(report, mts)
        self.assertEqual(mts_item.unit_status, "UNIT_UNVERIFIED")
        self.assertEqual(mts_item.status, "REVIEW REQUIRED")
        self.assertEqual(report.summary_qty["status"], "UNIT_UNVERIFIED")
        self.assertIn("available", report.summary_cif)

    def test_kg_case_variants_are_one_unit(self):
        upper = self._item(self.licence, serial=4, qty="10.000", cif="1.00", unit="KG")
        item = self.item_report(self.report(), upper)
        self.assertEqual(item.unit, "kg")
        self.assertEqual(item.unit_status, "VERIFIED")


class AllotmentTests(ReportFixture):
    def test_multiple_customer_allotments_are_summed(self):
        self._allotment(self.item, cif="100", qty="100")
        self._allotment(self.item, cif="50", qty="50")
        item = self.item_report(self.report())
        self.assertEqual(item.cif["allotted"], "150.00")
        self.assertEqual(item.cif["available"], "850.00")

    def test_allotment_partly_converted_to_boe_keeps_residue(self):
        trade, line = self._sale(invoice="LGL-1", cif="10", qty="10")
        boe, _ = self._boe("AB-1", cif="60", qty="60")
        self._allotment(self.item, cif="100", qty="100", boes=[boe])
        item = self.item_report(self.report())
        # BOE 60 is on this item and linked to the allotment → residue 40.
        self.assertEqual(item.cif["allotted"], "40.00")

    def test_allotment_linked_to_boe_on_another_licence_is_flagged(self):
        other_licence = self._licence("03" + str(uuid.uuid4().int)[:8])
        other_item = self._item(other_licence, serial=1, qty="10.000", cif="10.00")
        foreign_boe, _ = self._boe("FOREIGN-1", item=other_item, cif="30", qty="30")
        self._allotment(self.item, cif="100", qty="100", boes=[foreign_boe])
        item = self.item_report(self.report())
        self.assertEqual(item.cif["allotted"], "100.00")
        self.assertIn("ALLOTMENT_LINKED_BOE_NOT_ON_ITEM", item.flags)
        self.assertEqual(item.status, "REVIEW REQUIRED")

    def test_allotment_and_sale_on_same_item_is_flagged_unverified(self):
        self._sale(invoice="LGL-1", cif="100", qty="100")
        self._allotment(self.item, cif="100", qty="100")
        item = self.item_report(self.report())
        self.assertIn("ALLOT_AND_SALE_OVERLAP_UNVERIFIED", item.flags)


class LicenceAggregationTests(ReportFixture):
    def test_licence_summary_equals_sum_of_items(self):
        second = self._item(self.licence, serial=2, qty="500.000", cif="500.00")
        self._boe("L-1", cif="100", qty="100")
        self._boe("L-2", item=second, cif="50", qty="50")
        report = self.report()
        self.assertEqual(report.summary_cif["original"], "1500.00")
        self.assertEqual(report.summary_cif["debited"], "150.00")
        self.assertEqual(report.summary_cif["available"], "1350.00")

    def test_negative_licence_balance_is_reported_not_floored(self):
        # The sale is verified EXTERNAL, so the negative balance does not depend on an unclassified sale.
        trade, _line = self._sale(invoice="LGL-BIG", cif="1200", qty="1200")
        TradeUtilisationClassification.objects.create(
            trade=trade, classification=TradeUtilisationClassification.CLASS_EXTERNAL,
            reason="Test: verified external sale.",
        )
        report = self.report()
        self.assertEqual(report.summary_cif["available"], "-200.00")
        self.assertTrue(report.summary_cif["is_over_utilised"])
        self.assertEqual(report.status, "OVER-UTILISED")

    def test_customers_are_listed_separately(self):
        self._sale(invoice="C1", cif="100", qty="100", to=self.customer)
        self._sale(invoice="C2", cif="200", qty="200", to=self.customer_two)
        item = self.item_report(self.report())
        names = {c["customer"]: c["sold"] for c in item.customers}
        self.assertEqual(names, {"Customer One": "100.00", "Customer Two": "200.00"})

    def test_legacy_figure_is_reported_for_comparison(self):
        report = self.report()
        self.assertIsNotNone(report.legacy_balance_cif)
        self.assertIn(report.legacy_status, ("RECONCILED", "MISMATCH"))


class ApiTests(ReportFixture):
    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        self.user = get_user_model().objects.create_user(username="lm-" + uuid.uuid4().hex[:6], password="x")
        # Roles are Django groups named by role code (see accounts.models.User.has_role).
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def test_list_returns_summary_rows_and_pagination(self):
        self._sale(invoice="API-1", cif="100", qty="100")
        response = self.client_api.get("/api/licence-balances/", {"search": self.licence.license_number})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        row = body["results"][0]
        self.assertEqual(row["licence_number"], self.licence.license_number)
        self.assertEqual(row["cif"]["invoiced"], "100.00")
        self.assertIn("legacy_balance_cif", row)

    def test_detail_returns_items_with_components(self):
        response = self.client_api.get(f"/api/licence-balances/{self.licence.id}/")
        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["cif"]["original"], "1000.00")
        self.assertIn("status", item)

    def test_item_movements_return_both_ledgers(self):
        self._boe("M-1", cif="200", qty="200")
        response = self.client_api.get(f"/api/licence-balances/{self.licence.id}/items/{self.item.id}/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["cif_movements"][0]["kind"], "ORIGINAL")
        self.assertEqual(body["qty_movements"][-1]["running_balance"], "800.000")

    def test_unknown_licence_is_404(self):
        response = self.client_api.get("/api/licence-balances/999999999/")
        self.assertEqual(response.status_code, 404)

    def test_unknown_item_is_404(self):
        response = self.client_api.get(f"/api/licence-balances/{self.licence.id}/items/999999999/")
        self.assertEqual(response.status_code, 404)

    def test_authenticated_user_without_licence_role_is_refused(self):
        from django.contrib.auth import get_user_model
        outsider = get_user_model().objects.create_user(username="out-" + uuid.uuid4().hex[:6], password="x")
        client = APIClient()
        client.force_authenticate(outsider)
        self.assertEqual(client.get("/api/licence-balances/").status_code, 403)

    def test_anonymous_request_is_refused(self):
        response = APIClient().get("/api/licence-balances/")
        self.assertIn(response.status_code, (401, 403))


class TransactionsTests(ReportFixture):
    """The workspace tabs read these rows; they must agree with the balance."""

    def _transactions(self):
        from apps.license.services.licence_balance_report import build_licence_transactions
        return build_licence_transactions(self.licence.id)

    def test_over_linked_sale_is_reported_not_hidden(self):
        trade, _ = self._sale(invoice="OVER-1", cif="500", qty="500")
        self._boe("OV-1", cif="300", qty="300", trades=[trade])
        self._boe("OV-2", cif="300", qty="300", trades=[trade])
        inv = self._transactions()["invoices"][0]
        self.assertEqual(inv["status"], "OVER-LINKED: excess counted as utilisation")
        self.assertEqual(inv["over_linked"], "100.00")
        self.assertEqual(inv["covered_by_boe"], "500.00")

    def test_transactions_tie_back_to_the_item_balance(self):
        trade, _ = self._sale(invoice="TIE-1", cif="500", qty="500")
        self._boe("TB-1", cif="190", qty="190", trades=[trade])
        self._boe("TB-2", cif="30", qty="30")
        self._allotment(self.item, cif="100", qty="100")
        item = self.item_report(self.report())
        tx = self._transactions()
        uncovered = sum((Decimal(b["uncovered_cif"]) for b in tx["boes"]), D("0"))
        over = sum((Decimal(i["over_linked"]) for i in tx["invoices"]), D("0"))
        allotted = sum((Decimal(a["outstanding_cif"]) for a in tx["allotments"]), D("0"))
        self.assertEqual(uncovered + over, Decimal(item.cif["debited"]))
        self.assertEqual(allotted, Decimal(item.cif["allotted"]))

    def test_covered_boe_has_covered_status_and_linked_sale(self):
        trade, _ = self._sale(invoice="COV-1", cif="500", qty="500")
        self._boe("CV-1", cif="40", qty="40", trades=[trade])
        self._boe("CV-2", cif="50", qty="50", trades=[trade])
        self._boe("CV-3", cif="100", qty="100", trades=[trade])
        boes = self._transactions()["boes"]
        self.assertTrue(all(b["status"] == "COVERED BY SALE" for b in boes))
        self.assertTrue(all(b["linked_sale_trade_ids"] == [trade.id] for b in boes))

    def test_transactions_endpoint_requires_a_licence_role(self):
        from django.contrib.auth import get_user_model
        outsider = get_user_model().objects.create_user(username="tx-" + uuid.uuid4().hex[:6], password="x")
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(outsider)
        self.assertEqual(client.get(f"/api/licence-balances/{self.licence.id}/transactions/").status_code, 403)

    def test_transactions_endpoint_returns_three_groups(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        user = get_user_model().objects.create_user(username="tx2-" + uuid.uuid4().hex[:6], password="x")
        user.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(user)
        response = client.get(f"/api/licence-balances/{self.licence.id}/transactions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"license_id", "boes", "allotments", "invoices"})


class OverLinkedBoeStatusTests(ReportFixture):
    def test_boe_linked_only_to_an_over_linked_sale_is_not_labelled_covered(self):
        # Sale 500 with 600 of BOEs: the excess is counted on the invoice, so no BOE is "covered" silently.
        trade, _ = self._sale(invoice="OVL-1", cif="500", qty="500")
        self._boe("OVL-A", cif="300", qty="300", trades=[trade])
        self._boe("OVL-B", cif="300", qty="300", trades=[trade])
        from apps.license.services.licence_balance_report import build_licence_transactions
        tx = build_licence_transactions(self.licence.id)
        self.assertTrue(all(b["status"].startswith("LINKED TO AN OVER-LINKED SALE") for b in tx["boes"]))


class LegacyOptInTests(ReportFixture):
    def test_list_omits_legacy_comparison_unless_requested(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        user = get_user_model().objects.create_user(username="leg-" + uuid.uuid4().hex[:6], password="x")
        user.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(user)
        default = client.get("/api/licence-balances/", {"search": self.licence.license_number}).json()["results"][0]
        self.assertIsNone(default["legacy_balance_cif"])
        opted = client.get("/api/licence-balances/", {"search": self.licence.license_number, "legacy": "1"}).json()["results"][0]
        self.assertIsNotNone(opted["legacy_balance_cif"])
