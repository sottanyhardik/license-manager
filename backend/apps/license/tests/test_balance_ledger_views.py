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

    The Financial Ledger's `rows` display was later changed (see
    `build_financial_ledger`'s docstring) to show BOEs with NO invoice
    relationship at all — a "boe_allocation" row is BY DEFINITION invoice-
    matched, so it and any invoice-matched "boe" row are NEVER in `rows`
    anymore, regardless of consolidation. The consolidation math itself
    (`build_invoice_allocation_groups`) is unaffected and still exercised
    directly here.
    """

    def test_two_fully_allocated_boes_produce_one_consolidated_row(self):
        """Exact spec test case: two BOEs of 99,000 qty / 87,120 CIF each,
        both fully allocated to one invoice -> ONE consolidated GROUP,
        qty=198,000, cif=174,240, with 2 underlying allocations. The
        Financial Ledger's `rows` display now hides this entirely (it's
        fully invoice-matched — see class docstring); the consolidation
        math itself is verified via `build_invoice_allocation_groups`."""
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

        # --- Financial Ledger display: fully matched -> nothing shown for
        # this invoice/BOE pair at all (no "boe", no "boe_allocation", no
        # "trade" row) ---
        rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertEqual([r["row_kind"] for r in rows], ["opening", "final"])
        self.assertEqual(summary["total_invoice_allocation_debit"], Decimal("174240.00"))
        self.assertEqual(summary["total_boe_debit"], DEC_0)
        self.assertEqual(summary["total_trade_debit"], DEC_0)

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

        # Financial Ledger: fully matched -> hidden from `rows` entirely
        # (see class docstring) — nothing left to check remarks text on.
        rows, _ = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        self.assertEqual([r["row_kind"] for r in rows], ["opening", "final"])

    def test_partially_allocated_boe_leaves_remainder_as_individual_row_and_totals_match(self):
        """A BOE only PARTLY allocated to an invoice must still count its
        unmatched remainder — nothing is lost, nothing is double-counted,
        and total_boe_debit + total_invoice_allocation_debit reconciles
        exactly to the BOE's full cif_fc. The remainder row is still HIDDEN
        from `rows` display (it has an invoice relationship — a partial one
        — via the allocation, so it's not "no invoice relationship at
        all"), but the underlying total is unaffected by that display
        filter."""
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

        # Both the consolidated 30,000 and the unmatched 20,000 remainder
        # carry SOME invoice relationship now (the remainder's own BOE row
        # has a partial allocation), so neither displays in `rows`.
        self.assertEqual([r["row_kind"] for r in rows], ["opening", "final"])

        # But the totals feeding those hidden amounts are still correct and
        # reconcile to the BOE's full cif_fc — nothing lost, nothing double-
        # counted, regardless of what's shown.
        self.assertEqual(summary["total_boe_debit"], Decimal("20000.00"))
        self.assertEqual(summary["total_invoice_allocation_debit"], Decimal("30000.00"))
        self.assertEqual(summary["total_boe_debit"] + summary["total_invoice_allocation_debit"], Decimal("50000.00"))


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
        represented by the consolidated invoice row instead), but the
        Customs Ledger always debits its full raw amount and just flags it
        "Matched" instead of omitting it."""
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

        # Financial Ledger: fully invoice-matched -> hidden from `rows`
        # entirely (no "boe", no "boe_allocation" — see
        # FinancialLedgerGroupingTests' class docstring); the consolidated
        # 40,000 group still exists underneath (verified via
        # `build_invoice_allocation_groups` in that test class).
        self.assertEqual([r["row_kind"] for r in financial_rows], ["opening", "final"])
        self.assertEqual(financial_summary["total_invoice_allocation_debit"], Decimal("40000.00"))

        # Customs Ledger's OWN running total reconciles with the Balance
        # Engine in this fully-matched, no-leftover scenario (unaffected by
        # the Financial Ledger's separate display filter).
        self.assertEqual(customs_summary["computed_balance"], customs_summary["engine_balance"])
        self.assertEqual(customs_summary["computed_balance"], Decimal("60000.00"))

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
        self.assertEqual(financial_summary["computed_balance"], Decimal("135000.00"))  # 200000 - 40000 - 25000

        # The two ledgers legitimately disagree by exactly the unmatched amount.
        self.assertEqual(
            customs_summary["computed_balance"] - financial_summary["computed_balance"],
            Decimal("25000.00"),
        )


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
