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

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.constants import DEBIT, DEC_0
from apps.core.models import CompanyModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.license.services.license_balance_ledger_builder import (
    LicenseBalanceLedgerBuilder,
    build_invoice_allocation_groups,
)
from apps.reconciliation.models import BOEAllotmentAllocation, ReconciliationLog
from apps.reconciliation.services.allocation_service import (
    create_boe_allotment_allocation,
    create_invoice_boe_allocation,
    remaining_for_row_details_allotment_side,
    remaining_for_row_details_invoice_side,
)
from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin

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
            "license", "financial_ledger", "customs_ledger", "reconciliation", "warnings", "timeline",
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


class BoeCandidateDimensionRegressionTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """
    Regression test for a reported production bug: the "Find BOE" drawer
    (Invoice<->BOE allocation) was sourcing candidate remaining-capacity
    from the ALLOTMENT-side track instead of the INVOICE-side track, which
    caused a false "over allocation" error whenever a BOE's allotment-side
    and invoice-side remaining diverged. Proves
    `remaining_for_row_details_invoice_side` reports the INVOICE-side
    remaining (full, untouched) independently of
    `remaining_for_row_details_allotment_side` being partially consumed on
    the very same row.
    """

    def make_allotment(self, company):
        return AllotmentModel.objects.create(company=company, item_name="Test Allotment Item")

    def make_allotment_item(self, allotment, item, cif_fc, qty=Decimal("100.000")):
        return AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"), qty=qty,
        )

    def test_invoice_side_remaining_unaffected_by_allotment_side_allocation(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("56020.35"), qty=Decimal("46493.000"))

        allotment = self.make_allotment(company)
        allotment_item = self.make_allotment_item(allotment, item, cif_fc=Decimal("56020.35"), qty=Decimal("46493.000"))

        # Consume HALF of this row's ALLOTMENT-side capacity only — the
        # invoice side has zero allocations and must remain fully available.
        create_boe_allotment_allocation(
            row, allotment_item,
            qty=Decimal("23246.500"), cif_fc=Decimal("28010.18"), cif_inr=Decimal("2366860.21"),
            user=None,
        )

        _, invoice_remaining_cif_fc, _ = remaining_for_row_details_invoice_side(row)
        _, allotment_remaining_cif_fc, _ = remaining_for_row_details_allotment_side(row)

        # The bug: these two numbers were being conflated. They must now
        # correctly diverge -- invoice side untouched, allotment side halved.
        self.assertEqual(invoice_remaining_cif_fc, Decimal("56020.35"))
        self.assertEqual(allotment_remaining_cif_fc, Decimal("28010.17"))
        self.assertNotEqual(invoice_remaining_cif_fc, allotment_remaining_cif_fc)

    def test_denies_anonymous_user(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        client = APIClient()
        resp = client.get(f"/api/licenses/{license_obj.id}/balance-ledger/")

        self.assertEqual(resp.status_code, 403)


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


class FinancialLedgerGroupingTests(LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase):
    """
    Regression tests for consolidating multiple BOEs allocated to the same
    invoice into ONE Financial Ledger row instead of one row per BOE (the
    Customs Ledger — untested here — is unaffected and keeps one row per
    BOE always).

    Once a BOE is fully allocated to an invoice, it is skipped entirely from
    `rows` (its `contributed` is 0 — see `get_debit_rows`/`calculate_debit`'s
    docstring) because its full amount is now represented by the matching
    SALE trade line's own row, with the underlying allocation(s) attached as
    informational `children` — see `build_financial_ledger`'s docstring. The
    consolidation math itself (`build_invoice_allocation_groups`) is
    unaffected and still exercised directly here.
    """

    def test_two_fully_allocated_boes_produce_one_consolidated_row(self):
        """Exact spec test case: two BOEs of 99,000 qty / 87,120 CIF each,
        both fully allocated to one invoice -> ONE consolidated GROUP,
        qty=198,000, cif=174,240, with 2 underlying allocations, attached as
        children of the SALE trade row, which debits its full 174,240."""
        company = self.make_company()
        license_obj = self.make_license(company)
        # opening_balance == calculate_credit() == sum of export item cif_fc.
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("222360.00"))

        item = self.make_item(license_obj, 1)
        boe1 = self.make_boe(company, number="7650222")
        boe2 = self.make_boe(company, number="7650224")
        row1 = self.make_debit_row(boe1, item, cif_fc=Decimal("87120.00"), qty=Decimal("99000.000"))
        row2 = self.make_debit_row(boe2, item, cif_fc=Decimal("87120.00"), qty=Decimal("99000.000"))

        trade = self.make_sale_trade(company, invoice_number="LML/2025-26/0125")
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("174240.00"), qty_kg=Decimal("198000.0000"))

        create_invoice_boe_allocation(
            trade_line, row1, qty=row1.qty, cif_fc=row1.cif_fc, cif_inr=row1.cif_inr, user=None,
        )
        create_invoice_boe_allocation(
            trade_line, row2, qty=row2.qty, cif_fc=row2.cif_fc, cif_inr=row2.cif_inr, user=None,
        )

        # --- Consolidation math itself, unaffected by display filtering ---
        groups = build_invoice_allocation_groups(license_obj)
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group["trade_line"].id, trade_line.id)
        self.assertIn("7650222", group["boe_numbers"])
        self.assertIn("7650224", group["boe_numbers"])
        self.assertEqual(group["total_qty"], Decimal("198000.000"))
        self.assertEqual(group["total_cif_fc"], Decimal("174240.00"))
        self.assertEqual(group["total_cif_inr"], row1.cif_inr + row2.cif_inr)
        self.assertEqual(len(group["allocations"]), 2)
        allocated_boe_numbers = {a.row_details.bill_of_entry.bill_of_entry_number for a in group["allocations"]}
        self.assertEqual(allocated_boe_numbers, {"7650222", "7650224"})

        # --- Financial Ledger display: both BOEs fully matched -> no "boe"
        # rows; ONE "trade" row carries the full 174,240 debit, with both
        # allocations as its children ---
        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertEqual([r["row_kind"] for r in rows], ["trade", "final"])
        trade_row = rows[0]
        self.assertEqual(trade_row["debit"], Decimal("174240.00"))
        self.assertEqual(len(trade_row["children"]), 2)
        self.assertEqual(summary["total_invoice_allocation_debit"], Decimal("174240.00"))
        self.assertEqual(summary["total_boe_debit"], DEC_0)
        self.assertEqual(summary["total_trade_debit"], Decimal("174240.00"))

    def test_single_boe_allocation_uses_singular_remarks(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))

        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="7650300")
        row = self.make_debit_row(boe, item, cif_fc=Decimal("50000.00"), qty=Decimal("1000.000"))
        trade = self.make_sale_trade(company, invoice_number="LML/2025-26/0200")
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("50000.00"), qty_kg=Decimal("1000.0000"))
        create_invoice_boe_allocation(
            trade_line, row, qty=row.qty, cif_fc=row.cif_fc, cif_inr=row.cif_inr, user=None,
        )

        # Consolidation math: a single-BOE group uses singular remarks in
        # `build_financial_ledger` (verified below); `build_invoice_
        # allocation_groups` itself doesn't compute remarks text, so assert
        # the underlying boe_numbers count that drives it.
        groups = build_invoice_allocation_groups(license_obj)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["boe_numbers"], ["7650300"])

        # Financial Ledger: fully matched -> BOE row skipped, its 50,000
        # debit now carried by the "trade" row with singular remarks.
        rows, _ = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertEqual([r["row_kind"] for r in rows], ["trade", "final"])
        self.assertEqual(rows[0]["remarks"], "Matched Invoice(s)")
        self.assertEqual(rows[0]["debit"], Decimal("50000.00"))

    def test_partially_allocated_boe_leaves_remainder_as_individual_row_and_totals_match(self):
        """A BOE only PARTLY allocated to an invoice must still count its
        unmatched remainder — nothing is lost, nothing is double-counted,
        and total_boe_debit + total_invoice_allocation_debit reconciles
        exactly to the BOE's full cif_fc. The remainder now shows as its own
        "BOE Utilisation (Pending Invoice)" row (it still has an unallocated
        remainder — see `build_financial_ledger`'s docstring), alongside the
        "trade" row carrying the allocated portion's full debit."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))

        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="7650400")
        row = self.make_debit_row(boe, item, cif_fc=Decimal("50000.00"), qty=Decimal("1000.000"))
        trade = self.make_sale_trade(company, invoice_number="LML/2025-26/0300")
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("30000.00"), qty_kg=Decimal("600.0000"))
        # Only 30,000 of this BOE's 50,000 CIF (and 600 of its 1000 qty) is
        # allocated to the invoice — the rest of the BOE remains unmatched.
        allocated_cif_inr = (row.cif_inr * Decimal("30000.00") / Decimal("50000.00"))
        create_invoice_boe_allocation(
            trade_line, row, qty=Decimal("600.000"), cif_fc=Decimal("30000.00"), cif_inr=allocated_cif_inr, user=None,
        )

        # Consolidation math: one group for the 30,000 that IS allocated.
        groups = build_invoice_allocation_groups(license_obj)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["total_cif_fc"], Decimal("30000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        # BOE's unallocated 20,000 remainder shows as its own Pending
        # Invoice row; the trade line's own 30,000 (fully allocated) shows
        # via the "trade" row — both real, neither lost, neither doubled.
        self.assertEqual([r["row_kind"] for r in rows], ["boe", "trade", "final"])
        boe_row, trade_row, _ = rows
        self.assertEqual(boe_row["debit"], Decimal("20000.00"))
        self.assertEqual(boe_row["status"], "Pending Invoice")
        self.assertEqual(trade_row["debit"], Decimal("30000.00"))
        self.assertEqual(len(trade_row["children"]), 1)

        # And the totals reconcile exactly to the BOE's full cif_fc —
        # nothing lost, nothing double-counted, regardless of how it's split
        # across the two rows.
        self.assertEqual(summary["total_boe_debit"], Decimal("20000.00"))
        self.assertEqual(summary["total_invoice_allocation_debit"], Decimal("30000.00"))
        self.assertEqual(summary["total_boe_debit"] + summary["total_invoice_allocation_debit"], Decimal("50000.00"))
        self.assertEqual(summary["total_trade_debit"], Decimal("30000.00"))


class CustomsLedgerTests(LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase):
    """
    Tests for `LicenseBalanceLedgerBuilder.build_customs_ledger` — a
    SEPARATE running-balance statement from the Financial Ledger. Every BOE
    debits at its FULL raw cif_fc unconditionally (never allocation-
    adjusted), which is intentional: see the builder method's docstring.
    """

    def test_opening_boe_and_final_rows(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))

        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="9000001")
        self.make_debit_row(boe, item, cif_fc=Decimal("40000.00"), qty=Decimal("500.000"))

        rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj)

        self.assertEqual(rows[0]["row_kind"], "customs_opening")
        self.assertEqual(rows[0]["credit"], Decimal("100000.00"))
        self.assertEqual(rows[0]["running_balance"], Decimal("100000.00"))

        boe_row = rows[1]
        self.assertEqual(boe_row["row_kind"], "customs_boe")
        self.assertEqual(boe_row["debit"], Decimal("40000.00"))  # FULL raw amount
        self.assertEqual(boe_row["status"], "Unmatched")
        self.assertEqual(boe_row["running_balance"], Decimal("60000.00"))

        final_row = rows[-1]
        self.assertEqual(final_row["status"], "Balance Engine")
        self.assertEqual(final_row["running_balance"], summary["engine_balance"])
        self.assertEqual(summary["total_boe_cif"], Decimal("40000.00"))

    def test_matched_boe_still_debits_full_amount_unlike_financial_ledger(self):
        """The whole point of a separate Customs Ledger: a fully-matched
        BOE contributes 0 to the Financial Ledger's BOE debit (it's
        represented by the matching "trade" row's full debit instead), but
        the Customs Ledger always debits its full raw amount and just flags
        it "Matched" instead of omitting it.

        This licence has a Sale but no Purchase, so the Balance Engine
        anchors on purchase credit (0), not the original export-item CIF —
        see `LicenseBalanceCalculator.calculate_balance`'s docstring. The
        Financial Ledger's own running total uses the same anchor, so it
        reconciles with the Balance Engine exactly (both 0, floored). The
        Customs Ledger, however, is untouched and still anchors on the
        original opening balance — so its own running total (60,000)
        legitimately diverges from the Balance Engine here; that gap is the
        actionable "create a Purchase invoice" signal, not a bug."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))

        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="9000002")
        row = self.make_debit_row(boe, item, cif_fc=Decimal("40000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, invoice_number="INV-9000002")
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("40000.00"), qty_kg=Decimal("500.0000"))
        create_invoice_boe_allocation(trade_line, row, qty=row.qty, cif_fc=row.cif_fc, cif_inr=row.cif_inr, user=None)

        customs_rows, customs_summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj)
        financial_rows, financial_summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        customs_boe_row = next(r for r in customs_rows if r["row_kind"] == "customs_boe")
        self.assertEqual(customs_boe_row["debit"], Decimal("40000.00"))
        self.assertEqual(customs_boe_row["status"], "Matched")

        # Financial Ledger: fully invoice-matched -> BOE row skipped, its
        # 40,000 debit now carried by the "trade" row (with the allocation
        # as an informational child).
        self.assertEqual([r["row_kind"] for r in financial_rows], ["trade", "final"])
        self.assertEqual(financial_rows[0]["debit"], Decimal("40000.00"))
        self.assertEqual(financial_summary["total_invoice_allocation_debit"], Decimal("40000.00"))

        # Financial Ledger's own running total reconciles EXACTLY with the
        # Balance Engine — the actual acceptance criterion this feature
        # exists to guarantee.
        self.assertEqual(financial_summary["computed_balance"], financial_summary["engine_balance"])
        self.assertEqual(financial_summary["computed_balance"], DEC_0)

        # Customs Ledger's OWN running total (opening-balance-anchored,
        # untouched) legitimately diverges from the Balance Engine here —
        # this licence has no Purchase trade, so the engine has no credit
        # anchor beyond the (zero) purchase credit.
        self.assertEqual(customs_summary["computed_balance"], Decimal("60000.00"))
        self.assertEqual(customs_summary["engine_balance"], DEC_0)

    def test_pending_allotment_row(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))

        item = self.make_item(license_obj, 1)
        allotment = AllotmentModel.objects.create(company=company, item_name="Test Allotment")
        AllotmentItems.objects.create(item=item, allotment=allotment, cif_fc=Decimal("15000.00"), cif_inr=Decimal("1267500.00"), qty=Decimal("200.000"))

        rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj)
        pending_rows = [r for r in rows if r["row_kind"] == "customs_pending_allotment"]
        self.assertEqual(len(pending_rows), 1)
        self.assertEqual(pending_rows[0]["debit"], Decimal("15000.00"))
        self.assertEqual(pending_rows[0]["status"], "Pending")
        self.assertEqual(pending_rows[0]["remarks"], "Awaiting BOE")
        self.assertEqual(summary["total_pending_allotment_cif"], Decimal("15000.00"))

    def test_unmatched_trade_remainder_causes_legitimate_divergence_from_financial_ledger(self):
        """When a SALE trade line has NO BOE allocation at all, the
        Financial Ledger debits it (via the "trade" row) but the Customs
        Ledger has no concept of it at all (it only reflects physical BOE
        activity) — the two ledgers legitimately land on DIFFERENT totals,
        and that gap is exactly the reconciliation signal this workspace
        exists to surface, not a bug to hide."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("200000.00"))

        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="9000003")
        self.make_debit_row(boe, item, cif_fc=Decimal("40000.00"), qty=Decimal("500.000"))

        # A SALE trade line with NO BOE allocation at all.
        trade = self.make_sale_trade(company, invoice_number="INV-UNMATCHED")
        self.make_trade_line(trade, item, cif_fc=Decimal("25000.00"))

        customs_rows, customs_summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj)
        financial_rows, financial_summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        # Customs Ledger has no row at all for the unmatched trade line.
        self.assertEqual([r for r in customs_rows if r["row_kind"] == "trade"], [])
        self.assertEqual(customs_summary["computed_balance"], Decimal("160000.00"))  # 200000 - 40000

        # Financial Ledger DOES carry the unmatched trade line's full debit.
        trade_rows = [r for r in financial_rows if r["row_kind"] == "trade"]
        self.assertEqual(len(trade_rows), 1)
        self.assertEqual(trade_rows[0]["debit"], Decimal("25000.00"))
        # This licence has a Sale but no Purchase, so no opening balance is
        # fabricated — the running balance starts at 0 (see
        # `has_trading_activity` in `build_financial_ledger`'s docstring) and
        # the 40000 BOE debit + 25000 trade debit drive it negative, which is
        # then floored at 0 (pre-existing clamp, unrelated to this feature).
        self.assertEqual(financial_summary["computed_balance"], Decimal("0.00"))

        # The two ledgers legitimately disagree — the Customs Ledger still
        # reflects the licence's real opening balance while the Financial
        # Ledger (correctly) has no basis to assume one without a Purchase.
        self.assertEqual(
            customs_summary["computed_balance"] - financial_summary["computed_balance"],
            Decimal("160000.00"),
        )

    def test_boe_tagged_allotment_never_shown_as_pending_and_never_double_deducted(self):
        """
        An allotment already tagged to a BOE via the REAL `BillOfEntryModel.
        allotment` M2M relationship (set by the BOE form's allotment picker,
        `apps/bill_of_entry/serializers.py`) must NOT appear as a "Pending
        Allotment" in the Customs Ledger, and its CIF must not reduce
        `running` a second time — the BOE's own debit (via its `RowDetails`
        row) is the sole, authoritative customs movement for that
        utilisation. Reuses `get_allotment_rows()`'s existing `Exists()`
        linked-BOE exclusion (`balance_calculator.py`) — no new matching
        logic.

        Deliberately does NOT set `AllotmentModel.is_boe=True` — that hand-
        maintained cache boolean has been found stale at real-world scale
        (allotments linked via the real M2M with `is_boe` still `False`),
        which is exactly the bug this test guards against; the exclusion
        must work from the real relationship alone.
        """
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))

        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="9000010")
        self.make_debit_row(boe, item, cif_fc=Decimal("30000.00"), qty=Decimal("300.000"))

        allotment = AllotmentModel.objects.create(company=company, item_name="Test Allotment", is_boe=False)
        boe.allotment.add(allotment)
        AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=Decimal("20000.00"), cif_inr=Decimal("1690000.00"),
            qty=Decimal("200.000"),
        )

        rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj)

        self.assertEqual([r for r in rows if r["row_kind"] == "customs_pending_allotment"], [])
        self.assertEqual(summary["total_pending_allotment_cif"], DEC_0)
        # Only the BOE's own 30,000 debit reduces the balance — the tagged
        # allotment's 20,000 is never deducted a second time.
        self.assertEqual(summary["computed_balance"], Decimal("70000.00"))  # 100000 - 30000

    def test_unlinked_allotment_still_shown_as_pending_in_customs_ledger(self):
        """Sanity check for the above: an allotment with NO BOE association
        at all must still appear as a real outstanding commitment — the
        exclusion must be specific to linked allotments, not blanket."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))

        item = self.make_item(license_obj, 1)
        allotment = AllotmentModel.objects.create(company=company, item_name="Test Allotment", is_boe=False)
        AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=Decimal("20000.00"), cif_inr=Decimal("1690000.00"),
            qty=Decimal("200.000"),
        )

        rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj)

        pending_rows = [r for r in rows if r["row_kind"] == "customs_pending_allotment"]
        self.assertEqual(len(pending_rows), 1)
        self.assertEqual(pending_rows[0]["debit"], Decimal("20000.00"))
        self.assertEqual(summary["total_pending_allotment_cif"], Decimal("20000.00"))
        self.assertEqual(summary["computed_balance"], Decimal("80000.00"))  # 100000 - 20000

    def test_partially_boe_allocated_allotment_only_deducts_remainder_once(self):
        """An allotment PARTLY consumed by a formal `BOEAllotmentAllocation`
        (not `is_boe`-tagged) must show only its unallocated remainder as
        Pending — the allocated portion is never double-deducted, and
        nothing is silently lost either."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))

        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="9000011")
        row = self.make_debit_row(boe, item, cif_fc=Decimal("10000.00"), qty=Decimal("100.000"))
        allotment = AllotmentModel.objects.create(company=company, item_name="Test Allotment", is_boe=False)
        allotment_item = AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=Decimal("20000.00"), cif_inr=Decimal("1690000.00"),
            qty=Decimal("200.000"),
        )
        create_boe_allotment_allocation(
            row, allotment_item, qty=Decimal("100.000"), cif_fc=Decimal("10000.00"), cif_inr=Decimal("845000.00"),
            user=None,
        )

        rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj)

        pending_rows = [r for r in rows if r["row_kind"] == "customs_pending_allotment"]
        self.assertEqual(len(pending_rows), 1)
        self.assertEqual(pending_rows[0]["debit"], Decimal("10000.00"))  # 20000 - 10000 allocated
        self.assertEqual(summary["total_pending_allotment_cif"], Decimal("10000.00"))
        # 100000 - 10000 (BOE) - 10000 (allotment remainder) = 80000
        self.assertEqual(summary["computed_balance"], Decimal("80000.00"))


class TimelineTests(LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase):
    """`build_timeline` must reflect ONLY real persisted records — never a
    fabricated/inferred event — and must present them in chronological
    order with hierarchical children for reconciliation actions."""

    def test_empty_license_has_empty_timeline(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        events = LicenseBalanceLedgerBuilder.build_timeline(license_obj)
        self.assertEqual(events, [])

    def test_boe_filed_event_reflects_real_row(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="8000001")
        self.make_debit_row(boe, item, cif_fc=Decimal("12000.00"), qty=Decimal("300.000"))

        events = LicenseBalanceLedgerBuilder.build_timeline(license_obj)
        boe_events = [e for e in events if e["event_type"] == "boe_filed"]
        self.assertEqual(len(boe_events), 1)
        self.assertEqual(boe_events[0]["document_number"], "8000001")
        self.assertEqual(boe_events[0]["cif"], Decimal("12000.00"))
        self.assertIsNotNone(boe_events[0]["date"])

    def test_invoice_boe_reconciliation_is_hierarchical(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe1 = self.make_boe(company, number="8000002")
        boe2 = self.make_boe(company, number="8000003")
        row1 = self.make_debit_row(boe1, item, cif_fc=Decimal("30000.00"), qty=Decimal("400.000"))
        row2 = self.make_debit_row(boe2, item, cif_fc=Decimal("30000.00"), qty=Decimal("400.000"))
        trade = self.make_sale_trade(company, invoice_number="INV-TIMELINE-1")
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("60000.00"), qty_kg=Decimal("800.0000"))
        create_invoice_boe_allocation(trade_line, row1, qty=row1.qty, cif_fc=row1.cif_fc, cif_inr=row1.cif_inr, user=None)
        create_invoice_boe_allocation(trade_line, row2, qty=row2.qty, cif_fc=row2.cif_fc, cif_inr=row2.cif_inr, user=None)

        events = LicenseBalanceLedgerBuilder.build_timeline(license_obj)
        recon_events = [e for e in events if e["event_type"] == "invoice_boe_reconciled" and e["document_number"] == "INV-TIMELINE-1"]
        self.assertEqual(len(recon_events), 1)
        parent = recon_events[0]
        self.assertTrue(parent["expandable"])
        self.assertEqual(len(parent["children"]), 2)
        child_docs = {c["document_number"] for c in parent["children"]}
        self.assertEqual(child_docs, {"8000002", "8000003"})

    def test_recalculate_action_appears_as_manual_adjustment(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        self.make_item(license_obj, 1)

        client = APIClient()
        client.force_authenticate(user=User.objects.create_user(
            username=f"timeline-user-{uuid.uuid4().hex[:8]}", is_superuser=True,
        ))
        resp = client.post(f"/api/licenses/{license_obj.id}/recalculate/", {"reason": "month-end close"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)

        events = LicenseBalanceLedgerBuilder.build_timeline(license_obj)
        adjustments = [e for e in events if e["event_type"] == "manual_adjustment"]
        self.assertEqual(len(adjustments), 1)
        self.assertEqual(adjustments[0]["remarks"], "month-end close")
        self.assertIsNotNone(adjustments[0]["user"])

    def test_events_are_chronologically_sorted(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe1 = self.make_boe(company, number="8000010")
        self.make_debit_row(boe1, item, cif_fc=Decimal("1000.00"), qty=Decimal("10.000"))
        boe2 = self.make_boe(company, number="8000011")
        self.make_debit_row(boe2, item, cif_fc=Decimal("1000.00"), qty=Decimal("10.000"))

        events = LicenseBalanceLedgerBuilder.build_timeline(license_obj)
        dates = [e["date"] for e in events]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual([e["sr"] for e in events], list(range(1, len(events) + 1)))


class WarningManagementTests(LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase):
    """Warning ignore/restore is pure workflow bookkeeping — must never
    change any financial number, must be audit-logged, and must be
    permission-gated."""

    def _make_unmatched_invoice_license(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        trade = self.make_sale_trade(company, invoice_number="INV-WARN-1")
        self.make_trade_line(trade, item, cif_fc=Decimal("20000.00"))
        return license_obj

    def test_build_warnings_has_stable_identity(self):
        license_obj = self._make_unmatched_invoice_license()
        data = LicenseBalanceLedgerBuilder.build(license_obj)
        unmatched = [w for w in data["warnings"] if w["warning_type"] == "UNMATCHED_INVOICE"]
        self.assertEqual(len(unmatched), 1)
        self.assertEqual(unmatched[0]["entity_type"], "TRADE_LINE")
        self.assertFalse(unmatched[0]["ignored"])

    def test_ignore_then_restore_via_endpoint_never_changes_financials(self):
        license_obj = self._make_unmatched_invoice_license()
        user = self.make_superuser()
        client = APIClient()
        client.force_authenticate(user=user)

        before = LicenseBalanceLedgerBuilder.build(license_obj)
        warning = next(w for w in before["warnings"] if w["warning_type"] == "UNMATCHED_INVOICE")

        resp = client.post(
            f"/api/licenses/{license_obj.id}/ignore-warning/",
            {
                "warning_type": warning["warning_type"], "entity_type": warning["entity_type"],
                "entity_id": warning["entity_id"], "reason": "known issue, fixing next week",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)

        after_ignore = LicenseBalanceLedgerBuilder.build(license_obj)
        ignored_warning = next(w for w in after_ignore["warnings"] if w["warning_type"] == "UNMATCHED_INVOICE")
        self.assertTrue(ignored_warning["ignored"])
        self.assertEqual(ignored_warning["reason"], "known issue, fixing next week")
        self.assertIsNotNone(ignored_warning["ignored_by"])

        # Financial data must be byte-identical to before ignoring.
        self.assertEqual(before["financial_ledger"]["summary"], after_ignore["financial_ledger"]["summary"])
        self.assertEqual(before["customs_ledger"]["summary"], after_ignore["customs_ledger"]["summary"])
        self.assertEqual(before["reconciliation"], after_ignore["reconciliation"])

        log = ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_WARNING_IGNORED).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, user.id)
        self.assertEqual(log.reason, "known issue, fixing next week")

        # Restore.
        resp = client.post(
            f"/api/licenses/{license_obj.id}/restore-warning/",
            {"warning_type": warning["warning_type"], "entity_type": warning["entity_type"], "entity_id": warning["entity_id"]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        after_restore = LicenseBalanceLedgerBuilder.build(license_obj)
        restored_warning = next(w for w in after_restore["warnings"] if w["warning_type"] == "UNMATCHED_INVOICE")
        self.assertFalse(restored_warning["ignored"])
        self.assertEqual(after_restore["financial_ledger"]["summary"], before["financial_ledger"]["summary"])

        restore_log = ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_WARNING_RESTORED).first()
        self.assertIsNotNone(restore_log)
        self.assertEqual(restore_log.user_id, user.id)

    def test_ignore_unknown_warning_identity_returns_404(self):
        license_obj = self._make_unmatched_invoice_license()
        client = APIClient()
        client.force_authenticate(user=self.make_superuser())

        resp = client.post(
            f"/api/licenses/{license_obj.id}/ignore-warning/",
            {"warning_type": "UNMATCHED_INVOICE", "entity_type": "TRADE_LINE", "entity_id": "999999"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_restore_never_ignored_warning_returns_404(self):
        license_obj = self._make_unmatched_invoice_license()
        client = APIClient()
        client.force_authenticate(user=self.make_superuser())

        resp = client.post(
            f"/api/licenses/{license_obj.id}/restore-warning/",
            {"warning_type": "UNMATCHED_INVOICE", "entity_type": "TRADE_LINE", "entity_id": "1"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_ignore_denied_without_manager_role(self):
        license_obj = self._make_unmatched_invoice_license()
        data = LicenseBalanceLedgerBuilder.build(license_obj)
        warning = next(w for w in data["warnings"] if w["warning_type"] == "UNMATCHED_INVOICE")

        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        resp = client.post(
            f"/api/licenses/{license_obj.id}/ignore-warning/",
            {"warning_type": warning["warning_type"], "entity_type": warning["entity_type"], "entity_id": warning["entity_id"]},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_reignoring_is_idempotent_single_row(self):
        from apps.reconciliation.models import IgnoredWarning

        license_obj = self._make_unmatched_invoice_license()
        client = APIClient()
        client.force_authenticate(user=self.make_superuser())
        data = LicenseBalanceLedgerBuilder.build(license_obj)
        warning = next(w for w in data["warnings"] if w["warning_type"] == "UNMATCHED_INVOICE")
        payload = {"warning_type": warning["warning_type"], "entity_type": warning["entity_type"], "entity_id": warning["entity_id"]}

        client.post(f"/api/licenses/{license_obj.id}/ignore-warning/", payload, format="json")
        client.post(f"/api/licenses/{license_obj.id}/restore-warning/", payload, format="json")
        client.post(f"/api/licenses/{license_obj.id}/ignore-warning/", payload, format="json")

        self.assertEqual(
            IgnoredWarning.objects.filter(
                license=license_obj, warning_type=warning["warning_type"],
                entity_type=warning["entity_type"], entity_id=warning["entity_id"],
            ).count(),
            1,
        )


class BalanceEngineFinancialLedgerReconciliationTests(
    LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase
):
    """
    The actual acceptance criterion behind "unify the Balance Engine with
    the Financial Ledger": `LicenseBalanceCalculator.calculate_balance()`
    and `build_financial_ledger()`'s own `computed_balance` must land on
    the EXACT same number (not merely within tolerance) for every shape of
    trading activity a licence can have.
    """

    def _make_purchase_trade(self, company, item, cif_fc, invoice_number=None):
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE,
            to_company=company,
            invoice_number=invoice_number or f"PUR-{uuid.uuid4().int % 999999:06d}",
            invoice_date=datetime.now().date(),
        )
        LicenseTradeLine.objects.create(
            trade=trade, sr_number=item, description=item.description or "Test Item",
            mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"),
        )
        return trade

    def _assert_engine_matches_ledger(self, license_obj):
        from apps.license.services.balance_calculator import LicenseBalanceCalculator

        _, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        engine_balance = LicenseBalanceCalculator.calculate_balance(license_obj)
        self.assertEqual(summary["computed_balance"], engine_balance)
        self.assertEqual(summary["computed_balance"], summary["engine_balance"])
        return summary

    def test_purchase_only(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("50000.00"))

        summary = self._assert_engine_matches_ledger(license_obj)
        self.assertEqual(summary["computed_balance"], Decimal("50000.00"))

    def test_sale_only_unmatched(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        trade = self.make_sale_trade(company, invoice_number="INV-UNMATCHED-2")
        self.make_trade_line(trade, item, cif_fc=Decimal("15000.00"))

        summary = self._assert_engine_matches_ledger(license_obj)
        # No Purchase credit at all -> floored at 0, not negative.
        self.assertEqual(summary["computed_balance"], DEC_0)

    def test_sale_fully_allocated(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("80000.00"))
        boe = self.make_boe(company, number="8000001")
        row = self.make_debit_row(boe, item, cif_fc=Decimal("30000.00"), qty=Decimal("300.000"))
        trade = self.make_sale_trade(company, invoice_number="INV-FULL")
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("30000.00"), qty_kg=Decimal("300.0000"))
        create_invoice_boe_allocation(trade_line, row, qty=row.qty, cif_fc=row.cif_fc, cif_inr=row.cif_inr, user=None)

        summary = self._assert_engine_matches_ledger(license_obj)
        self.assertEqual(summary["computed_balance"], Decimal("50000.00"))  # 80000 - 30000

    def test_sale_partially_allocated(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("80000.00"))
        boe = self.make_boe(company, number="8000002")
        row = self.make_debit_row(boe, item, cif_fc=Decimal("50000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, invoice_number="INV-PARTIAL")
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("30000.00"), qty_kg=Decimal("300.0000"))
        allocated_cif_inr = row.cif_inr * Decimal("30000.00") / Decimal("50000.00")
        create_invoice_boe_allocation(
            trade_line, row, qty=Decimal("300.000"), cif_fc=Decimal("30000.00"), cif_inr=allocated_cif_inr, user=None,
        )

        summary = self._assert_engine_matches_ledger(license_obj)
        # 80000 credit - 20000 (BOE unallocated remainder) - 30000 (full sale debit)
        self.assertEqual(summary["computed_balance"], Decimal("30000.00"))

    def test_mixed_boe_allotment_and_trade(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("200000.00"))

        boe = self.make_boe(company, number="8000003")
        self.make_debit_row(boe, item, cif_fc=Decimal("40000.00"), qty=Decimal("400.000"))

        allotment = AllotmentModel.objects.create(company=company, item_name="Test Allotment")
        AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=Decimal("15000.00"), cif_inr=Decimal("1267500.00"),
            qty=Decimal("150.000"),
        )

        trade = self.make_sale_trade(company, invoice_number="INV-MIXED")
        self.make_trade_line(trade, item, cif_fc=Decimal("25000.00"))

        summary = self._assert_engine_matches_ledger(license_obj)
        # 200000 - 40000 (BOE) - 15000 (allotment) - 25000 (sale)
        self.assertEqual(summary["computed_balance"], Decimal("120000.00"))

    def test_sale_linked_to_mismatched_boe_no_duplicate_row_and_engine_matches(self):
        """
        Real-bug regression (BOE 2557728 / invoice LGL/2026-27/0044): a BOE
        tagged to a sale trade via `.boes` but whose CIF mismatches the
        trade line beyond tolerance must show up ONCE -- as the "Licence
        Trade (Sold)" row, carrying the linked BOE number and a
        `mismatch_warning` -- never as a separate "BOE Utilisation
        (Pending Invoice)" row, and the Balance Engine must still
        reconcile exactly with the Financial Ledger's own running total.
        """
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("80000.00"))
        boe = self.make_boe(company, number="2557728")
        self.make_debit_row(boe, item, cif_fc=Decimal("5036.36"), qty=Decimal("50.000"))
        trade = self.make_sale_trade(company, invoice_number="LGL/2026-27/0044", boes=[boe])
        self.make_trade_line(trade, item, cif_fc=Decimal("5031.07"), qty_kg=Decimal("50.0000"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual([r["row_kind"] for r in rows], ["trade_purchase", "trade", "final"])
        trade_row = rows[1]
        self.assertEqual(trade_row["boe_number"], "2557728")
        self.assertEqual(trade_row["debit"], Decimal("5031.07"))
        warning = trade_row["mismatch_warning"]
        self.assertIsNotNone(warning)
        self.assertEqual(warning["status"], "mismatch")
        self.assertEqual(warning["boe_cif"], Decimal("5036.36"))
        self.assertEqual(warning["invoice_cif"], Decimal("5031.07"))
        self.assertEqual(warning["difference"], Decimal("5.29"))

        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        self.assertEqual(summary["computed_balance"], LicenseBalanceCalculator.calculate_balance(license_obj))
        self.assertEqual(summary["computed_balance"], Decimal("74968.93"))  # 80000 - 5031.07
