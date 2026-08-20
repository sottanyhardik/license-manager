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
from django.contrib.auth.models import Group
from django.test import TestCase

from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.constants import DEBIT, DEC_0
from apps.core.models import CompanyModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.bill_of_entry.models import BillOfEntryModel, OTH_INVOICE_MARKER, RowDetails
from apps.license.services.balance_calculator import LicenseBalanceCalculator
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
        boe = BillOfEntryModel.objects.create(
            company=company,
            bill_of_entry_number=number or str(uuid.uuid4().int)[:9],
            bill_of_entry_date=datetime.now().date(),
            exchange_rate=Decimal("84.50"),
            invoice_no=invoice_no,
        )
        if invoice_no == OTH_INVOICE_MARKER:
            # A BOE only counts as GENUINELY hidden if its audit trail
            # confirms a real hide (see `annotate_and_exclude_hidden`'s
            # docstring) — raw `invoice_no == "OTH"` alone collides with
            # ~35-40% of real BOEs carrying it as unrelated legacy
            # free-text data. Every caller passing this marker means a
            # REAL hide, so create the same `ReconciliationLog` entry
            # `hide_boe`/`_apply_hide` would.
            ReconciliationLog.objects.create(
                action=ReconciliationLog.ACTION_HIDE_BOE,
                bill_of_entry=boe,
                before={"is_hidden": False, "invoice_no": ""},
                after={"is_hidden": True, "bill_of_entry_number": boe.bill_of_entry_number},
            )
        return boe

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
            "pending_invoice_groups",
        })
        self.assertEqual(data["license"]["license_number"], license_obj.license_number)
        self.assertGreaterEqual(len(data["financial_ledger"]["rows"]), 2)  # opening + final at minimum

    def test_api_returns_matching_purchase_once_balance_without_mismatch(self):
        from apps.license.models import LicenseExportItemModel
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("89283.10"))
        purchase = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE,
            to_company=company,
            invoice_number="PUR-API-ONCE",
            invoice_date=datetime.now().date(),
        )
        LicenseTradeLine.objects.create(
            trade=purchase, sr_number=item, description=item.description,
            mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=Decimal("89283.10"),
            cif_inr=Decimal("7544426.95"),
        )
        sale = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE,
            from_company=company,
            invoice_number="SALE-API-ONCE",
            invoice_date=datetime.now().date(),
        )
        LicenseTradeLine.objects.create(
            trade=sale, sr_number=item, description=item.description,
            mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=Decimal("80359.10"),
            cif_inr=Decimal("6790343.95"),
        )

        response = self.client.get(f"/api/licenses/{license_obj.id}/balance-ledger/")

        self.assertEqual(response.status_code, 200, response.data)
        financial = response.data["financial_ledger"]
        self.assertEqual(Decimal(str(financial["summary"]["computed_balance"])), Decimal("8924.00"))
        self.assertEqual(Decimal(str(financial["summary"]["engine_balance"])), Decimal("8924.00"))
        self.assertEqual(Decimal(str(response.data["reconciliation"]["difference"])), DEC_0)
        self.assertFalse(financial["summary"]["mismatched"])
        self.assertNotIn("MISMATCH vs Balance Engine", financial["rows"][-1]["remarks"])
        self.assertFalse(any(warning["warning_type"] == "FINANCIAL_MISMATCH" for warning in response.data["warnings"]))

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
        # allocations as its children. No Purchase trade exists here, so an
        # Opening Balance row leads the ledger (see `has_purchase` in
        # `build_financial_ledger`'s docstring). ---
        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertEqual([r["row_kind"] for r in rows], ["opening", "trade", "final"])
        trade_row = rows[1]
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
        # debit now carried by the "trade" row with singular remarks. No
        # Purchase trade exists, so an Opening Balance row leads the ledger.
        rows, _ = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertEqual([r["row_kind"] for r in rows], ["opening", "trade", "final"])
        self.assertEqual(rows[1]["remarks"], "Matched Invoice(s)")
        self.assertEqual(rows[1]["debit"], Decimal("50000.00"))

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
        # No Purchase trade exists, so an Opening Balance row leads.
        self.assertEqual([r["row_kind"] for r in rows], ["opening", "boe", "trade", "final"])
        _opening_row, boe_row, trade_row, _ = rows
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

        Balance CIF (`calculate_balance`) now uses that SAME raw, invoice-
        allocation-blind BOE debit — so here it agrees with the Customs
        Ledger's own running total exactly (100000 - 40000 = 60000), even
        though the Financial Ledger's OWN row display nets the BOE to 0 and
        carries the debit via the "trade" row instead. Two different
        internal bookkeeping paths landing on the same final number for
        this licence is exactly the point: Balance CIF no longer depends on
        which path a licence happens to take."""
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

        # Financial Ledger: no Purchase -> Opening Balance row leads;
        # fully invoice-matched -> BOE row skipped, its 40,000 debit now
        # carried by the "trade" row (with the allocation as an
        # informational child).
        self.assertEqual([r["row_kind"] for r in financial_rows], ["opening", "trade", "final"])
        self.assertEqual(financial_rows[0]["credit"], Decimal("100000.00"))
        self.assertEqual(financial_rows[1]["debit"], Decimal("40000.00"))
        self.assertEqual(financial_summary["total_invoice_allocation_debit"], Decimal("40000.00"))

        # Financial Ledger's own running total, the Customs Ledger's own
        # running total, and the Balance Engine all land on 60,000 here.
        self.assertEqual(financial_summary["computed_balance"], Decimal("60000.00"))
        self.assertEqual(financial_summary["engine_balance"], Decimal("60000.00"))
        self.assertFalse(financial_summary["mismatched"])

        self.assertEqual(customs_summary["computed_balance"], Decimal("60000.00"))
        self.assertEqual(customs_summary["engine_balance"], Decimal("60000.00"))

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
        # This licence has no Purchase, so an Opening Balance row leads the
        # ledger too (see `has_purchase` in `build_financial_ledger`'s
        # docstring) — running: 200000 - 40000 (BOE) - 25000 (trade) = 135000.
        self.assertEqual([r["row_kind"] for r in financial_rows], ["opening", "boe", "trade", "final"])
        self.assertEqual(financial_summary["computed_balance"], Decimal("135000.00"))

        # The two ledgers legitimately disagree — the Customs Ledger has no
        # concept of the unmatched trade line at all, while the Financial
        # Ledger debits it — a gap of exactly that trade's own CIF.
        self.assertEqual(
            customs_summary["computed_balance"] - financial_summary["computed_balance"],
            Decimal("25000.00"),
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


class FinancialLedgerOpeningBalanceGateTests(LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase):
    """`build_financial_ledger()`'s Opening Balance row is keyed on
    `has_purchase` alone (not `has_trading_activity`) — see that method's
    docstring. The Financial Ledger section is also no longer hidden for a
    never-traded licence (PDF/Excel/frontend `has_trading_activity` gates
    removed): an Opening-Balance-only statement is a real thing to show."""

    def _make_purchase_trade(self, company, item, cif_fc):
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE,
            to_company=company,
            invoice_number=f"PUR-{uuid.uuid4().int % 999999:06d}",
            invoice_date=datetime.now().date(),
        )
        LicenseTradeLine.objects.create(
            trade=trade, sr_number=item, description=item.description or "Test Item",
            mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"),
        )
        return trade

    def test_no_purchase_no_sale_shows_opening_balance_row(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("50000.00"))
        self.make_item(license_obj, 1)

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual([r["row_kind"] for r in rows], ["opening", "final"])
        self.assertFalse(summary["has_purchase"])
        self.assertFalse(summary["has_sale"])
        opening_row = rows[0]
        self.assertEqual(opening_row["credit"], Decimal("50000.00"))
        self.assertEqual(opening_row["debit"], DEC_0)
        self.assertEqual(opening_row["running_balance"], Decimal("50000.00"))
        self.assertEqual(summary["computed_balance"], Decimal("50000.00"))
        self.assertEqual(summary["computed_balance"], summary["engine_balance"])
        self.assertFalse(summary["mismatched"])

    def test_purchase_exists_no_opening_balance_row(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("60000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual([r["row_kind"] for r in rows], ["trade_purchase", "final"])
        self.assertTrue(summary["has_purchase"])
        self.assertNotIn("opening", [r["row_kind"] for r in rows])
        self.assertEqual(summary["computed_balance"], Decimal("60000.00"))

    def test_purchased_license_uses_one_acquisition_across_ledger_and_engine(self):
        """The opening metadata and purchase are one acquisition, never two."""
        from apps.license.models import LicenseExportItemModel

        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("89283.10"))
        self._make_purchase_trade(company, item, cif_fc=Decimal("89283.10"))
        sale = self.make_sale_trade(company, invoice_number="SALE-ONCE-ACQUISITION")
        self.make_trade_line(sale, item, cif_fc=Decimal("80359.10"))

        dataset = LicenseBalanceLedgerBuilder.build(license_obj)
        financial = dataset["financial_ledger"]
        final_row = financial["rows"][-1]

        self.assertEqual(final_row["running_balance"], Decimal("8924.00"))
        self.assertEqual(financial["summary"]["computed_balance"], Decimal("8924.00"))
        self.assertEqual(financial["summary"]["engine_balance"], Decimal("8924.00"))
        self.assertEqual(dataset["reconciliation"]["difference"], DEC_0)
        self.assertFalse(financial["summary"]["mismatched"])
        self.assertNotIn("MISMATCH vs Balance Engine", final_row["remarks"])
        self.assertFalse(any(warning["warning_type"] == "FINANCIAL_MISMATCH" for warning in dataset["warnings"]))


class HiddenBoeOpeningBalanceGateTests(LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase):
    """
    New 3-way Opening Balance gate: `hidden_total > 0` -> ALWAYS show the
    Opening Balance row (even when `has_purchase` is True), with
    `credit=opening_balance, debit=hidden_total,
    running_balance=opening_balance-hidden_total` -- see
    `build_financial_ledger`'s docstring / the design doc's "Remaining
    Tradable Licence" rule. Checked BEFORE the has_purchase/no-purchase
    branches exercised by `FinancialLedgerOpeningBalanceGateTests` above
    (which have zero hidden BOEs and must stay byte-identical).
    """

    def _make_purchase_trade(self, company, item, cif_fc):
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE,
            to_company=company,
            invoice_number=f"PUR-{uuid.uuid4().int % 999999:06d}",
            invoice_date=datetime.now().date(),
        )
        LicenseTradeLine.objects.create(
            trade=trade, sr_number=item, description=item.description or "Test Item",
            mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"),
        )
        return trade

    def _make_hidden_and_visible_rows(self, company, item, hidden_cif, visible_cif=None):
        hidden_boe = self.make_boe(
            company, number=f"HID-{uuid.uuid4().int % 999999:06d}", invoice_no=OTH_INVOICE_MARKER,
        )
        hidden_row = RowDetails.objects.create(
            bill_of_entry=hidden_boe, sr_number=item, transaction_type=DEBIT,
            cif_fc=hidden_cif, cif_inr=hidden_cif * Decimal("84.5"), qty=Decimal("100.000"),
        )
        visible_row = None
        if visible_cif is not None:
            visible_boe = self.make_boe(company, number=f"VIS-{uuid.uuid4().int % 999999:06d}")
            visible_row = RowDetails.objects.create(
                bill_of_entry=visible_boe, sr_number=item, transaction_type=DEBIT,
                cif_fc=visible_cif, cif_inr=visible_cif * Decimal("84.5"), qty=Decimal("50.000"),
            )
        return hidden_row, visible_row

    def test_hidden_total_shows_opening_row_without_purchase(self):
        """UPDATED: the Opening Balance row is NEVER reduced any more (it
        stays the full Original Licence CIF) -- the hidden total is instead
        debited on its OWN "Previous Owner Utilisation" row immediately
        after it (see `build_financial_ledger`'s 3-way Opening Balance gate
        docstring). The previous version of this test pinned a
        single-combined-row shape that no longer exists."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        self._make_hidden_and_visible_rows(company, item, hidden_cif=Decimal("40000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertFalse(summary["has_purchase"])
        self.assertEqual(summary["hidden_boe_total"], Decimal("40000.00"))
        self.assertEqual([r["row_kind"] for r in rows], ["opening", "previous_owner_utilisation", "final"])

        opening_row = rows[0]
        self.assertEqual(opening_row["credit"], Decimal("100000.00"))
        self.assertEqual(opening_row["debit"], DEC_0)  # never reduced
        self.assertEqual(opening_row["running_balance"], Decimal("100000.00"))

        utilisation_row = rows[1]
        self.assertEqual(utilisation_row["debit"], Decimal("40000.00"))  # hidden(40000) + purchase(0)
        self.assertEqual(utilisation_row["running_balance"], Decimal("60000.00"))
        self.assertEqual(summary["previous_owner_utilisation"], Decimal("40000.00"))
        self.assertEqual(summary["computed_balance"], Decimal("60000.00"))
        self.assertEqual(summary["engine_balance"], summary["computed_balance"])
        self.assertFalse(summary["mismatched"])

    def test_hidden_total_shows_opening_row_even_with_purchase(self):
        """The hidden_total>0 branch takes priority over has_purchase --
        the Opening Balance row must still appear (unlike the plain
        has_purchase case in `FinancialLedgerOpeningBalanceGateTests.
        test_purchase_exists_no_opening_balance_row`, which has zero
        hidden BOEs and correctly shows NO opening row). UPDATED: Opening
        Balance itself is never reduced -- Previous Owner Utilisation now
        carries hidden + purchase CIF as its OWN row, and Purchase still
        re-enters as its own unconditional "Licence Trade (Purchased)"
        credit row further down (net-zero effect on the final balance,
        see that row-kind's docstring)."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        self._make_hidden_and_visible_rows(company, item, hidden_cif=Decimal("40000.00"))
        self._make_purchase_trade(company, item, cif_fc=Decimal("10000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertTrue(summary["has_purchase"])
        self.assertEqual(
            [r["row_kind"] for r in rows],
            ["opening", "previous_owner_utilisation", "trade_purchase", "final"],
        )
        self.assertEqual(rows[0]["credit"], Decimal("100000.00"))
        self.assertEqual(rows[0]["debit"], DEC_0)
        self.assertEqual(rows[0]["running_balance"], Decimal("100000.00"))

        self.assertEqual(rows[1]["debit"], Decimal("50000.00"))  # 40000 hidden + 10000 purchase
        self.assertEqual(rows[1]["running_balance"], Decimal("50000.00"))

        self.assertEqual(rows[2]["credit"], Decimal("10000.00"))  # Purchase re-enters, unconditionally
        self.assertEqual(rows[2]["running_balance"], Decimal("60000.00"))

        self.assertEqual(summary["computed_balance"], Decimal("60000.00"))
        self.assertEqual(summary["engine_balance"], summary["computed_balance"])
        self.assertFalse(summary["mismatched"])

    def test_no_hidden_boes_regression_unaffected(self):
        """`hidden_boe_total` is exposed on the summary for every licence,
        but is exactly zero (and the existing has_purchase/no-purchase
        branches fire unchanged) when there are no hidden rows at all --
        the additive/backward-compatible guarantee this feature relies on."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("50000.00"))
        self.make_item(license_obj, 1)

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual(summary["hidden_boe_total"], DEC_0)
        self.assertEqual([r["row_kind"] for r in rows], ["opening", "final"])

    def test_financial_ledger_self_check_never_mismatches_on_hidden_boes(self):
        """
        UPDATED (previous version of this test pinned SUPERSEDED behaviour):
        `build_financial_ledger`'s own `engine_balance` is now
        `calculate_financial_balance()` -- a pure-function formalization of
        this SAME ledger's row-by-row `running`, not the older, unrelated
        `calculate_balance()`. So `computed_balance == engine_balance`
        (`mismatched is False`) is a FINANCIAL-vs-FINANCIAL self-check that
        must ALWAYS hold for a hidden-BOE licence -- it is no longer a
        "known gap." See `calculate_financial_balance`'s docstring.
        """
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("5000.00"))
        item = self.make_item(license_obj, 1)
        self._make_hidden_and_visible_rows(company, item, hidden_cif=Decimal("1000.00"), visible_cif=Decimal("800.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual(summary["computed_balance"], Decimal("3200.00"))  # (5000-1000) - 800
        self.assertEqual(summary["engine_balance"], summary["computed_balance"])
        self.assertFalse(summary["mismatched"])

    def test_financial_vs_customs_balance_expected_divergence_by_sale_debit(self):
        """
        Financial and Customs ARE still expected to genuinely diverge for a
        hidden-BOE licence -- just via `calculate_financial_balance()` vs
        `calculate_customs_balance()` (compared explicitly here), never via
        `build_financial_ledger`'s own internal `mismatched` flag (that one
        is a same-formula self-check, see the test above). Adding a SALE
        trade line with no BOE/invoice link demonstrates a real, non-hidden
        source of divergence: Financial subtracts the Sale debit (its own
        transactional narrative); Customs has no Sale term at all (it is
        the literal "what physically came through customs" figure) -- so
        the two differ by EXACTLY the Sale debit amount.
        """
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("5000.00"))
        item = self.make_item(license_obj, 1)
        self._make_hidden_and_visible_rows(company, item, hidden_cif=Decimal("1000.00"), visible_cif=Decimal("800.00"))

        sale_trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE, from_company=company,
            invoice_number="SALE-DIVERGE-1", invoice_date=datetime.now().date(),
        )
        LicenseTradeLine.objects.create(
            trade=sale_trade, sr_number=item, description=item.description or "Test Item",
            mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=Decimal("500.00"), cif_inr=Decimal("500.00") * Decimal("84.5"),
        )

        financial_balance = LicenseBalanceCalculator.calculate_financial_balance(license_obj)
        customs_balance = LicenseBalanceCalculator.calculate_customs_balance(license_obj)

        self.assertEqual(financial_balance, Decimal("2700.00"))  # (5000-1000) - 500 (sale) - 800 (boe)
        self.assertEqual(customs_balance, Decimal("3200.00"))  # 5000 - (800 + 1000 hidden), no sale term
        self.assertEqual(customs_balance - financial_balance, Decimal("500.00"))  # exactly the Sale debit


class CustomsLedgerShowHiddenTests(LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase):
    """`build_customs_ledger(..., show_hidden=...)` -- the ONE deliberate
    place hidden rows can be rendered again, for the audit-view toggle.

    UPDATED: hidden is now BOE-level (`BillOfEntryModel.invoice_no ==
    OTH_INVOICE_MARKER`), not a `RowDetails.is_hidden` column. Also
    UPDATED: `show_hidden` affects ONLY which rows are returned -- every
    total (`total_boe_cif`, `computed_balance`) ALWAYS includes hidden BOEs
    regardless of the toggle (`get_debit_rows(..., include_hidden=True)` is
    called unconditionally -- see `build_customs_ledger`'s docstring). The
    previous version of this test wrongly expected `computed_balance` to
    shrink when hidden rows were excluded from display; that was never how
    this ledger works -- it is deliberately the LITERAL customs figure, and
    the toggle is display-only."""

    def _make_hidden_and_visible_rows(self, company, item, hidden_cif, visible_cif):
        hidden_boe = self.make_boe(
            company, number=f"HID-{uuid.uuid4().int % 999999:06d}", invoice_no=OTH_INVOICE_MARKER,
        )
        hidden_row = RowDetails.objects.create(
            bill_of_entry=hidden_boe, sr_number=item, transaction_type=DEBIT,
            cif_fc=hidden_cif, cif_inr=hidden_cif * Decimal("84.5"), qty=Decimal("100.000"),
        )
        visible_boe = self.make_boe(company, number=f"VIS-{uuid.uuid4().int % 999999:06d}")
        visible_row = RowDetails.objects.create(
            bill_of_entry=visible_boe, sr_number=item, transaction_type=DEBIT,
            cif_fc=visible_cif, cif_inr=visible_cif * Decimal("84.5"), qty=Decimal("50.000"),
        )
        return hidden_row, visible_row

    def test_show_hidden_false_hides_row_but_totals_still_include_it(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        self._make_hidden_and_visible_rows(company, item, hidden_cif=Decimal("40000.00"), visible_cif=Decimal("15000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj, show_hidden=False)

        boe_rows = [r for r in rows if r["row_kind"] == "customs_boe"]
        self.assertEqual(len(boe_rows), 1)  # hidden row dropped from the returned list only
        self.assertEqual(boe_rows[0]["debit"], Decimal("15000.00"))
        # Totals ALWAYS include the hidden BOE, regardless of show_hidden.
        self.assertEqual(summary["total_boe_cif"], Decimal("55000.00"))
        self.assertEqual(summary["computed_balance"], Decimal("45000.00"))  # 100000 - 55000
        self.assertEqual(summary["engine_balance"], summary["computed_balance"])
        self.assertFalse(summary["mismatched"])

    def test_show_hidden_true_includes_hidden_row_and_flags_it(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        self._make_hidden_and_visible_rows(company, item, hidden_cif=Decimal("40000.00"), visible_cif=Decimal("15000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj, show_hidden=True)

        boe_rows = [r for r in rows if r["row_kind"] == "customs_boe"]
        self.assertEqual(len(boe_rows), 2)
        self.assertEqual(summary["total_boe_cif"], Decimal("55000.00"))
        # Totals are IDENTICAL to the show_hidden=False case above -- only
        # which rows are returned changed, never any number in `summary`.
        self.assertEqual(summary["computed_balance"], Decimal("45000.00"))

        hidden_boe_row = next(r for r in boe_rows if r["debit"] == Decimal("40000.00"))
        visible_boe_row = next(r for r in boe_rows if r["debit"] == Decimal("15000.00"))
        self.assertTrue(hidden_boe_row["is_hidden"])
        self.assertEqual(hidden_boe_row["hidden_reason"], "Previous Owner (invoice_no=OTH)")
        self.assertFalse(visible_boe_row["is_hidden"])
        self.assertEqual(visible_boe_row["hidden_reason"], "")
        self.assertEqual(hidden_boe_row["status"], "Unmatched")  # never invoice-matched in this fixture

    def test_show_hidden_default_is_false(self):
        """`build_customs_ledger(license_obj)` with no explicit `show_hidden`
        kwarg must behave exactly like `show_hidden=False` -- the default
        stays backward compatible for every existing caller."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        self._make_hidden_and_visible_rows(company, item, hidden_cif=Decimal("40000.00"), visible_cif=Decimal("15000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj)

        boe_rows = [r for r in rows if r["row_kind"] == "customs_boe"]
        self.assertEqual(len(boe_rows), 1)
        self.assertEqual(summary["total_boe_cif"], Decimal("55000.00"))


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


class BalanceEngineCustomsLedgerReconciliationTests(
    LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase
):
    """
    The acceptance criterion behind "Customs Ledger is the single source of
    truth for Balance CIF" (real-bug regression: licence 5211016017 showed
    $0.00 via the Balance Engine but $243,034.85 via the Customs Ledger --
    see `LicenseBalanceCalculator.calculate_balance`'s docstring for the
    root cause): `calculate_balance()` and `build_customs_ledger()`'s own
    `computed_balance` must land on the EXACT same number for every shape
    of trading activity a licence can have. Purchase/Sale trades never
    participate in this number at all, however large.

    `build_financial_ledger()`'s OWN `computed_balance` (its Purchase/Sale
    transactional walk) is a separate, still-valid statement that may now
    legitimately diverge from the Balance Engine for a traded licence --
    checked explicitly below via its own `mismatched` flag, never asserted
    equal to the engine (that was the PREVIOUS, now-superseded acceptance
    criterion).
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

    def _assert_engine_matches_customs_ledger(self, license_obj):
        from apps.license.services.balance_calculator import LicenseBalanceCalculator

        _, customs_summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj)
        engine_balance = LicenseBalanceCalculator.calculate_balance(license_obj)
        self.assertEqual(customs_summary["computed_balance"], engine_balance)
        self.assertEqual(customs_summary["computed_balance"], customs_summary["engine_balance"])
        return engine_balance

    def test_no_transactions(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("10000.00"))
        self.make_item(license_obj, 1)

        engine_balance = self._assert_engine_matches_customs_ledger(license_obj)
        self.assertEqual(engine_balance, Decimal("10000.00"))

    def test_purchase_only(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("50000.00"))
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("999999.00"))

        engine_balance = self._assert_engine_matches_customs_ledger(license_obj)
        self.assertEqual(engine_balance, Decimal("50000.00"))  # unaffected by the purchase

        # Financial Ledger's own total tracks the purchase instead -- a
        # different, expected divergence from the CUSTOMS engine_balance
        # above, not a bug. `fin_summary["mismatched"]` is a SEPARATE,
        # Financial-vs-Financial self-check (its own `computed_balance`
        # vs. the standalone `calculate_financial_balance()` -- see
        # `build_financial_ledger`'s docstring) and must be False: the two
        # Financial figures always agree, only Financial vs. Customs is
        # expected to diverge.
        _, fin_summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertNotEqual(fin_summary["computed_balance"], engine_balance)
        self.assertFalse(fin_summary["mismatched"])

    def test_sale_only(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("40000.00"))
        item = self.make_item(license_obj, 1)
        trade = self.make_sale_trade(company, invoice_number="INV-SALE-ONLY")
        self.make_trade_line(trade, item, cif_fc=Decimal("15000.00"))

        engine_balance = self._assert_engine_matches_customs_ledger(license_obj)
        self.assertEqual(engine_balance, Decimal("40000.00"))  # the sale never deducts

    def test_purchase_and_sale(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("60000.00"))
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("30000.00"))
        trade = self.make_sale_trade(company, invoice_number="INV-PURCHASE-AND-SALE")
        self.make_trade_line(trade, item, cif_fc=Decimal("20000.00"))

        engine_balance = self._assert_engine_matches_customs_ledger(license_obj)
        self.assertEqual(engine_balance, Decimal("60000.00"))  # neither purchase nor sale deduct

    def test_boes_only(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="9100001")
        self.make_debit_row(boe, item, cif_fc=Decimal("40000.00"), qty=Decimal("400.000"))

        engine_balance = self._assert_engine_matches_customs_ledger(license_obj)
        self.assertEqual(engine_balance, Decimal("60000.00"))  # 100000 - 40000

    def test_outstanding_allotments(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("80000.00"))
        item = self.make_item(license_obj, 1)
        allotment = AllotmentModel.objects.create(company=company, item_name="Test Allotment")
        AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=Decimal("15000.00"), cif_inr=Decimal("1267500.00"),
            qty=Decimal("150.000"),
        )

        engine_balance = self._assert_engine_matches_customs_ledger(license_obj)
        self.assertEqual(engine_balance, Decimal("65000.00"))  # 80000 - 15000

    def test_linked_allotments_never_double_deducted(self):
        """An allotment already linked to a BOE must be excluded entirely --
        only the BOE's own debit counts, never both."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("90000.00"))
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="9100002")
        self.make_debit_row(boe, item, cif_fc=Decimal("20000.00"), qty=Decimal("200.000"))
        allotment = AllotmentModel.objects.create(company=company, item_name="Linked Allotment")
        AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=Decimal("20000.00"), cif_inr=Decimal("1690000.00"),
            qty=Decimal("200.000"),
        )
        boe.allotment.add(allotment)

        engine_balance = self._assert_engine_matches_customs_ledger(license_obj)
        self.assertEqual(engine_balance, Decimal("70000.00"))  # 90000 - 20000 (BOE only)

    def test_mixed_boe_allotment_and_trade_engine_ignores_trade(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("200000.00"))
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("999999.00"))

        boe = self.make_boe(company, number="8000003")
        self.make_debit_row(boe, item, cif_fc=Decimal("40000.00"), qty=Decimal("400.000"))

        allotment = AllotmentModel.objects.create(company=company, item_name="Test Allotment")
        AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=Decimal("15000.00"), cif_inr=Decimal("1267500.00"),
            qty=Decimal("150.000"),
        )

        trade = self.make_sale_trade(company, invoice_number="INV-MIXED")
        self.make_trade_line(trade, item, cif_fc=Decimal("25000.00"))

        engine_balance = self._assert_engine_matches_customs_ledger(license_obj)
        # 200000 - 40000 (BOE) - 15000 (allotment); the Sale's 25000 and
        # Purchase's 999999 never participate.
        self.assertEqual(engine_balance, Decimal("145000.00"))

    def test_sale_linked_to_mismatched_boe_still_counts_boe_debit_in_full(self):
        """
        Real-bug regression (BOE 2557728 / invoice LGL/2026-27/0044): even
        though this BOE is tagged to a Sale trade via the legacy `.boes`
        M2M, Balance CIF debits it at its full raw cif_fc unconditionally --
        Purchase/Sale trades never adjust the BOE side of Balance CIF. The
        Financial Ledger's OWN row display still folds this BOE into the
        "trade" row (no duplicate row) with a `mismatch_warning` -- that
        display behavior is unchanged, it just no longer feeds Balance CIF.
        """
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("80000.00"))
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("80000.00"))
        boe = self.make_boe(company, number="2557728")
        self.make_debit_row(boe, item, cif_fc=Decimal("5036.36"), qty=Decimal("50.000"))
        trade = self.make_sale_trade(company, invoice_number="LGL/2026-27/0044", boes=[boe])
        self.make_trade_line(trade, item, cif_fc=Decimal("5031.07"), qty_kg=Decimal("50.0000"))

        engine_balance = self._assert_engine_matches_customs_ledger(license_obj)
        self.assertEqual(engine_balance, Decimal("74963.64"))  # 80000 - 5036.36 (full, raw BOE debit)

        rows, fin_summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertEqual([r["row_kind"] for r in rows], ["trade_purchase", "trade", "final"])
        trade_row = rows[1]
        self.assertEqual(trade_row["boe_number"], "2557728")
        warning = trade_row["mismatch_warning"]
        self.assertIsNotNone(warning)
        self.assertEqual(warning["status"], "mismatch")


class HideBoeRestoreBoeViewTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """View-level tests for `POST licenses/{id}/hide-boe/` and
    `.../restore-boe/` -- the write actions built on top of
    `apps.bill_of_entry.services.boe_service.hide_boe` / `restore_boe`
    (BOE-level, not licence-scoped -- see that module's docstring),
    exercised through the real HTTP/permission
    layer (`LicenseBalanceLedgerPermission`'s `hide_boe`/`restore_boe`
    AND-of-two role gate)."""

    def make_user_with_roles(self, *roles, company=None):
        user = User.objects.create_user(
            username=f"hide-boe-{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123!",
            company=company,
        )
        for role in roles:
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.add(group)
        return user

    def setUp(self):
        self.user = self.make_superuser()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_hide_boe_happy_path(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("10000.00"))
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="9500001")
        self.make_debit_row(boe, item, cif_fc=Decimal("4000.00"), qty=Decimal("40.000"))

        resp = self.client.post(
            f"/api/licenses/{license_obj.id}/hide-boe/",
            {"boe_id": boe.id, "reason": "Previous owner utilisation"},
            format="json",
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["is_hidden"], True)
        self.assertEqual(resp.data["invoice_no"], OTH_INVOICE_MARKER)
        self.assertEqual(resp.data["previous_invoice_no"], "")  # BOE had a blank invoice_no beforehand
        self.assertEqual(resp.data["hidden_by"], self.user.username)
        self.assertIsNotNone(resp.data["hidden_at"])

        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, OTH_INVOICE_MARKER)

        log = ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_HIDE_BOE).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.bill_of_entry_id, boe.id)
        self.assertEqual(log.user_id, self.user.id)
        self.assertEqual(log.reason, "Previous owner utilisation")

        # No Purchase trade on this licence -- hiding relabels the debit as
        # Previous Owner Utilisation but does not change the Balance CIF
        # (see `HideBoeBalanceImmediacyTests.test_hide_with_no_purchase_
        # leaves_balance_unchanged` in `apps.bill_of_entry.tests.
        # test_boe_hide_service` for the same invariant, pinned there).
        license_obj.refresh_from_db()
        self.assertEqual(license_obj.balance_cif, Decimal("6000.00"))  # 10000 - 4000, unchanged by hiding

    def test_restore_boe_happy_path(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="9500002", invoice_no="GE")
        self.make_debit_row(boe, item, cif_fc=Decimal("4000.00"), qty=Decimal("40.000"))

        hide_resp = self.client.post(
            f"/api/licenses/{license_obj.id}/hide-boe/",
            {"boe_id": boe.id, "reason": "Previous owner"},
            format="json",
        )
        self.assertEqual(hide_resp.status_code, 201, hide_resp.data)
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, OTH_INVOICE_MARKER)

        resp = self.client.post(
            f"/api/licenses/{license_obj.id}/restore-boe/",
            {"boe_id": boe.id, "reason": "Restored in error"},
            format="json",
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["is_hidden"], False)
        # Restored back to the REAL invoice_no it had before hiding, read
        # back from the HIDE_BOE log's preserved `before['invoice_no']`.
        self.assertEqual(resp.data["invoice_no"], "GE")
        self.assertIsNotNone(resp.data["restored_at"])

        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "GE")

        log = ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_RESTORE_BOE).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.bill_of_entry_id, boe.id)
        self.assertEqual(log.user_id, self.user.id)

    def test_hide_boe_missing_boe_id_returns_400(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        resp = self.client.post(f"/api/licenses/{license_obj.id}/hide-boe/", {}, format="json")

        self.assertEqual(resp.status_code, 400)

    def test_hide_boe_nonexistent_boe_returns_404(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        resp = self.client.post(
            f"/api/licenses/{license_obj.id}/hide-boe/", {"boe_id": 999999999}, format="json",
        )

        self.assertEqual(resp.status_code, 404)

    def test_hide_boe_denied_without_any_role(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        boe = self.make_boe(company)

        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        resp = client.post(f"/api/licenses/{license_obj.id}/hide-boe/", {"boe_id": boe.id}, format="json")

        self.assertEqual(resp.status_code, 403)

    def test_hide_boe_denied_with_boe_manager_only(self):
        """The AND-of-two gate (`BOE_MANAGER` *and* `LICENSE_MANAGER`) means
        holding only ONE of the two required roles must still be denied --
        this is the real financial-mutation gate, stricter than the
        any-of-four `ignore_warning`/`restore_warning` actions."""
        company = self.make_company()
        license_obj = self.make_license(company)
        boe = self.make_boe(company)

        client = APIClient()
        client.force_authenticate(user=self.make_user_with_roles("BOE_MANAGER", company=company))
        resp = client.post(f"/api/licenses/{license_obj.id}/hide-boe/", {"boe_id": boe.id}, format="json")

        self.assertEqual(resp.status_code, 403)

    def test_hide_boe_denied_with_license_manager_only(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        boe = self.make_boe(company)

        client = APIClient()
        client.force_authenticate(user=self.make_user_with_roles("LICENSE_MANAGER", company=company))
        resp = client.post(f"/api/licenses/{license_obj.id}/hide-boe/", {"boe_id": boe.id}, format="json")

        self.assertEqual(resp.status_code, 403)

    def test_hide_boe_allowed_with_both_roles(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="9500003")
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("10.000"))

        client = APIClient()
        client.force_authenticate(user=self.make_user_with_roles(
            "BOE_MANAGER", "LICENSE_MANAGER", company=company,
        ))
        resp = client.post(f"/api/licenses/{license_obj.id}/hide-boe/", {"boe_id": boe.id}, format="json")

        self.assertEqual(resp.status_code, 201, resp.data)

    def test_hide_boe_rejects_a_boe_not_linked_to_url_license(self):
        """The licence URL cannot be used as a capability to mutate a
        different company's BOE by guessing its primary key."""
        company = self.make_company()
        license_obj = self.make_license(company)
        self.make_item(license_obj, 1)

        other_company = self.make_company()
        other_license = self.make_license(other_company)
        other_item = self.make_item(other_license, 1)
        foreign_boe = self.make_boe(other_company, number="9500004")
        self.make_debit_row(foreign_boe, other_item, cif_fc=Decimal("1000.00"), qty=Decimal("10.000"))

        client = APIClient()
        client.force_authenticate(user=self.make_user_with_roles(
            "BOE_MANAGER", "LICENSE_MANAGER", company=company,
        ))
        response = client.post(
            f"/api/licenses/{license_obj.id}/hide-boe/", {"boe_id": foreign_boe.id}, format="json",
        )

        self.assertEqual(response.status_code, 404, response.data)
        foreign_boe.refresh_from_db()
        self.assertNotEqual(foreign_boe.invoice_no, OTH_INVOICE_MARKER)

    def test_restore_boe_denied_with_boe_manager_only(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        boe = self.make_boe(company)

        client = APIClient()
        client.force_authenticate(user=self.make_user_with_roles("BOE_MANAGER", company=company))
        resp = client.post(f"/api/licenses/{license_obj.id}/restore-boe/", {"boe_id": boe.id}, format="json")

        self.assertEqual(resp.status_code, 403)


class LicenseLifecycleScenarioTests(LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase):
    """Broad characterization coverage across the common real-world licence
    lifecycles the Balance Engine/Financial Ledger must handle correctly:
    Purchase/Sale combinations, multiple invoices, BOEs, allotments, and the
    hidden-BOE round trip -- each cross-checked against `calculate_
    financial_balance` (the same identity `build_financial_ledger`'s own
    `mismatched` flag polices) rather than trusting the ledger's own numbers
    in isolation."""

    def _make_purchase_trade(self, company, item, cif_fc, invoice_number=None):
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE, to_company=company,
            invoice_number=invoice_number or f"PUR-{uuid.uuid4().int % 999999:06d}",
            invoice_date=datetime.now().date(),
        )
        LicenseTradeLine.objects.create(
            trade=trade, sr_number=item, description=item.description or "Test Item",
            mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"),
        )
        return trade

    # -- Purchase / Sale combinations -----------------------------------

    def test_full_purchase_full_sale(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("100000.00"))
        trade = self.make_sale_trade(company, invoice_number="INV-FULL-FULL")
        self.make_trade_line(trade, item, cif_fc=Decimal("100000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual(summary["total_purchase_credit"], Decimal("100000.00"))
        self.assertEqual(summary["total_trade_debit"], Decimal("100000.00"))
        self.assertEqual(summary["computed_balance"], DEC_0)
        self.assertEqual(summary["engine_balance"], DEC_0)
        self.assertFalse(summary["mismatched"])
        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(license_obj), DEC_0)

    def test_full_purchase_partial_sale(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("100000.00"))
        trade = self.make_sale_trade(company, invoice_number="INV-FULL-PARTIAL")
        self.make_trade_line(trade, item, cif_fc=Decimal("40000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        expected = Decimal("60000.00")
        self.assertEqual(summary["computed_balance"], expected)
        self.assertEqual(summary["engine_balance"], expected)
        self.assertFalse(summary["mismatched"])

    def test_partial_purchase_partial_sale(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("60000.00"))
        trade = self.make_sale_trade(company, invoice_number="INV-PARTIAL-PARTIAL")
        self.make_trade_line(trade, item, cif_fc=Decimal("30000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        expected = Decimal("30000.00")
        self.assertEqual(summary["computed_balance"], expected)
        self.assertEqual(summary["engine_balance"], expected)
        self.assertFalse(summary["mismatched"])

    def test_partial_purchase_full_sale(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("60000.00"))
        trade = self.make_sale_trade(company, invoice_number="INV-PARTIAL-FULL")
        self.make_trade_line(trade, item, cif_fc=Decimal("60000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual(summary["computed_balance"], DEC_0)
        self.assertEqual(summary["engine_balance"], DEC_0)
        self.assertFalse(summary["mismatched"])

    def test_multiple_purchase_invoices_sum_correctly(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("30000.00"), invoice_number="PUR-A")
        self._make_purchase_trade(company, item, cif_fc=Decimal("20000.00"), invoice_number="PUR-B")

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual(summary["total_purchase_credit"], Decimal("50000.00"))
        self.assertEqual(
            [r["row_kind"] for r in rows if r["row_kind"] == "trade_purchase"], ["trade_purchase", "trade_purchase"],
        )
        self.assertEqual(summary["computed_balance"], Decimal("50000.00"))
        self.assertEqual(summary["engine_balance"], Decimal("50000.00"))

    def test_multiple_sale_invoices_sum_correctly(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("100000.00"))
        trade_a = self.make_sale_trade(company, invoice_number="SALE-A")
        self.make_trade_line(trade_a, item, cif_fc=Decimal("20000.00"))
        trade_b = self.make_sale_trade(company, invoice_number="SALE-B")
        self.make_trade_line(trade_b, item, cif_fc=Decimal("15000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual(summary["total_trade_debit"], Decimal("35000.00"))
        expected = Decimal("65000.00")  # 100000 - 35000
        self.assertEqual(summary["computed_balance"], expected)
        self.assertEqual(summary["engine_balance"], expected)

    def test_purchased_license_with_no_sale_at_all(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("70000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertTrue(summary["has_purchase"])
        self.assertFalse(summary["has_sale"])
        self.assertFalse(summary["missing_purchase_warning"]["show_warning"])
        self.assertEqual([r["row_kind"] for r in rows], ["trade_purchase", "final"])
        self.assertEqual(summary["computed_balance"], Decimal("70000.00"))
        self.assertEqual(summary["engine_balance"], Decimal("70000.00"))

    # -- Allotments -------------------------------------------------------

    def test_sale_with_no_allotments(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("100000.00"))
        trade = self.make_sale_trade(company, invoice_number="INV-NO-ALLOT")
        self.make_trade_line(trade, item, cif_fc=Decimal("40000.00"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual(summary["total_allotment_debit"], DEC_0)
        self.assertEqual(summary["computed_balance"], Decimal("60000.00"))

    def test_sale_with_allotments(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("100000.00"))
        trade = self.make_sale_trade(company, invoice_number="INV-WITH-ALLOT")
        self.make_trade_line(trade, item, cif_fc=Decimal("40000.00"))

        allotment = AllotmentModel.objects.create(company=company, item_name="Outstanding Allotment")
        AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=Decimal("10000.00"),
            cif_inr=Decimal("10000.00") * Decimal("84.5"), qty=Decimal("100.000"),
        )

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual(summary["total_allotment_debit"], Decimal("10000.00"))
        expected = Decimal("50000.00")  # 100000 - 40000 - 10000
        self.assertEqual(summary["computed_balance"], expected)
        self.assertEqual(summary["engine_balance"], expected)

    def test_multiple_allotments_net_final_balance(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)

        allotment_1 = AllotmentModel.objects.create(company=company, item_name="Allotment 1")
        AllotmentItems.objects.create(
            item=item, allotment=allotment_1, cif_fc=Decimal("5000.00"),
            cif_inr=Decimal("5000.00") * Decimal("84.5"), qty=Decimal("50.000"),
        )
        allotment_2 = AllotmentModel.objects.create(company=company, item_name="Allotment 2")
        AllotmentItems.objects.create(
            item=item, allotment=allotment_2, cif_fc=Decimal("3000.00"),
            cif_inr=Decimal("3000.00") * Decimal("84.5"), qty=Decimal("30.000"),
        )

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual(summary["total_allotment_debit"], Decimal("8000.00"))
        expected = Decimal("92000.00")  # 100000 - 5000 - 3000
        self.assertEqual(summary["computed_balance"], expected)
        self.assertEqual(summary["engine_balance"], expected)
        self.assertFalse(summary["mismatched"])

    # -- BOEs ---------------------------------------------------------------

    def test_single_boe(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="SINGLE-BOE-1")
        self.make_debit_row(boe, item, cif_fc=Decimal("4000.00"), qty=Decimal("40.000"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        self.assertEqual([r["row_kind"] for r in rows], ["opening", "boe", "final"])
        self.assertEqual(summary["total_boe_debit"], Decimal("4000.00"))
        expected = Decimal("96000.00")
        self.assertEqual(summary["computed_balance"], expected)
        self.assertEqual(summary["engine_balance"], expected)

    def test_multiple_boes(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        boe_1 = self.make_boe(company, number="MULTI-BOE-1")
        boe_2 = self.make_boe(company, number="MULTI-BOE-2")
        boe_3 = self.make_boe(company, number="MULTI-BOE-3")
        self.make_debit_row(boe_1, item, cif_fc=Decimal("4000.00"), qty=Decimal("40.000"))
        self.make_debit_row(boe_2, item, cif_fc=Decimal("3000.00"), qty=Decimal("30.000"))
        self.make_debit_row(boe_3, item, cif_fc=Decimal("2000.00"), qty=Decimal("20.000"))

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)

        boe_rows = [r for r in rows if r["row_kind"] == "boe"]
        self.assertEqual(len(boe_rows), 3)
        self.assertEqual(summary["total_boe_debit"], Decimal("9000.00"))
        expected = Decimal("91000.00")
        self.assertEqual(summary["computed_balance"], expected)
        self.assertEqual(summary["engine_balance"], expected)

    # -- Hidden BOE round trip at the ledger level ---------------------------

    def test_hidden_boe_then_restored_boe_round_trip(self):
        """Complements the service-level round-trip pinned in
        `apps.bill_of_entry.tests.test_boe_hide_service` -- here checked
        against the full `build_financial_ledger` row set/summary, with a
        Purchase in play so hiding actually shifts the balance (see that
        module's docstring for why a no-purchase licence would not)."""
        from apps.bill_of_entry.services.boe_service import hide_boe, restore_boe
        from apps.license.signals import update_license_flags

        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        self._make_purchase_trade(company, item, cif_fc=Decimal("20000.00"))
        boe = self.make_boe(company, number="HIDE-ROUNDTRIP-1")
        self.make_debit_row(boe, item, cif_fc=Decimal("5000.00"), qty=Decimal("50.000"))

        rows_before, summary_before = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        balance_before = summary_before["computed_balance"]
        self.assertEqual(balance_before, Decimal("15000.00"))  # 0 (opening) + 20000 - 5000

        hide_boe(boe, user=None, reason="Previous owner")
        update_license_flags(license_obj)

        rows_hidden, summary_hidden = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertEqual([r["row_kind"] for r in rows_hidden], ["opening", "previous_owner_utilisation", "trade_purchase", "final"])
        self.assertEqual(summary_hidden["hidden_boe_total"], Decimal("5000.00"))
        expected_hidden = Decimal("95000.00")  # (100000-5000-20000) + 20000
        self.assertEqual(summary_hidden["computed_balance"], expected_hidden)
        self.assertEqual(summary_hidden["engine_balance"], expected_hidden)
        self.assertFalse(summary_hidden["mismatched"])

        restore_boe(boe, user=None, reason="Restored in error")
        update_license_flags(license_obj)

        rows_after, summary_after = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertEqual(summary_after["hidden_boe_total"], DEC_0)
        self.assertEqual(summary_after["computed_balance"], balance_before)
        self.assertEqual(
            [r["row_kind"] for r in rows_after], [r["row_kind"] for r in rows_before],
        )

    # -- BOE-level invoice matching spanning multiple items ------------------

    def test_boe_spanning_two_items_only_one_invoice_matched_excludes_both(self):
        """The BOE Invoice Status Consistency rule: once ANY row of a
        physical BOE is invoice-matched, the WHOLE BOE is "represented" --
        every debit row on it is excluded from `calculate_debit()`/
        `get_debit_rows()`'s `contributed`, regardless of which licence item
        it belongs to. Here item_2's row has NO allocation of its own, yet
        must still be excluded because it shares a physical BOE with
        item_1's now-matched row."""
        company = self.make_company()
        license_obj = self.make_license(company)
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item_1 = self.make_item(license_obj, 1)
        item_2 = self.make_item(license_obj, 2)
        boe = self.make_boe(company, number="SPAN-ITEMS-1")
        row_1 = self.make_debit_row(boe, item_1, cif_fc=Decimal("3000.00"), qty=Decimal("30.000"))
        row_2 = self.make_debit_row(boe, item_2, cif_fc=Decimal("2000.00"), qty=Decimal("20.000"))

        trade = self.make_sale_trade(company, invoice_number="INV-SPAN-ITEMS")
        trade_line = self.make_trade_line(trade, item_1, cif_fc=Decimal("3000.00"), qty_kg=Decimal("30.0000"))
        create_invoice_boe_allocation(
            trade_line, row_1, qty=row_1.qty, cif_fc=row_1.cif_fc, cif_inr=row_1.cif_inr, user=None,
        )

        represented = LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license_obj)
        self.assertIn(boe.id, represented)

        debit_rows = {
            row.id: row.contributed
            for row in LicenseBalanceCalculator.get_debit_rows(license_obj)
        }
        self.assertEqual(debit_rows[row_1.id], DEC_0)  # netted by its own allocation
        self.assertEqual(debit_rows[row_2.id], DEC_0)  # excluded too -- same represented BOE, no allocation of its own

        self.assertEqual(LicenseBalanceCalculator.calculate_debit(license_obj), DEC_0)

        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertEqual(summary["total_boe_debit"], DEC_0)  # neither row shown as "BOE Utilisation (Pending Invoice)"
        self.assertNotIn("boe", [r["row_kind"] for r in rows])
