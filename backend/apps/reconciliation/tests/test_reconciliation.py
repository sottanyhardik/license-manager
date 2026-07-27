# reconciliation/tests/test_reconciliation.py
"""
Tests for the BOE / Invoice Reconciliation panel (Phase 1):
- Detection queries (`services/queries.py`) against fixtures that
  reproduce the exact scenario each one is meant to catch.
- The `link` / `note` / `merge-boe` write actions (`views.py`), asserting
  both the underlying model state change AND that a `ReconciliationLog`
  row is created with the correct before/after.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from apps.core.constants import DEBIT, DEC_0
from apps.core.models import CompanyModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.trade.models import LicenseTrade, LicenseTradeLine

from apps.reconciliation.models import ReconciliationLog, ReconciliationNote
from apps.reconciliation.services import queries as reconciliation_queries
from apps.reconciliation.services.allocation_service import create_invoice_boe_allocation

User = get_user_model()


class ReconciliationFixtureMixin:
    """Shared model-creation helpers, mirroring
    apps/license/tests/test_balance_calculator.py's DB-backed fixtures."""

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

    def make_boe(self, company, port=None, number=None, boe_date=None, invoice_no=""):
        return BillOfEntryModel.objects.create(
            company=company,
            port=port,
            bill_of_entry_number=number or str(uuid.uuid4().int)[:9],
            bill_of_entry_date=boe_date or datetime.now().date(),
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

    def make_sale_trade(self, company, boes=None, invoice_number=None):
        trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE,
            from_company=company,
            invoice_number=invoice_number or f"INV-TEST-{uuid.uuid4().int % 999999:06d}",
            invoice_date=datetime.now().date(),
        )
        if boes:
            trade.boes.set(boes)
        return trade

    def make_trade_line(self, trade, item, cif_fc, qty_kg=Decimal("100.0000")):
        return LicenseTradeLine.objects.create(
            trade=trade,
            sr_number=item,
            description=item.description or "Test Item",
            mode=LicenseTradeLine.MODE_CIF_INR,
            cif_fc=cif_fc,
            cif_inr=cif_fc * Decimal("84.5"),
            qty_kg=qty_kg,
        )


# ---------------------------------------------------------------------------
# Detection queries
# ---------------------------------------------------------------------------

class MissingBoeQueryTests(ReconciliationFixtureMixin, TestCase):
    def test_detects_sale_line_with_no_boe_linked(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        trade = self.make_sale_trade(company, boes=None)
        self.make_trade_line(trade, item, cif_fc=Decimal("500.00"))

        rows = reconciliation_queries.missing_boe()

        matching = [r for r in rows if r["trade_id"] == trade.id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["cif_fc"], Decimal("500.00"))
        self.assertEqual(matching[0]["license_number"], license_obj.license_number)

    def test_excludes_sale_line_when_boe_is_linked(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        trade = self.make_sale_trade(company, boes=[boe])
        self.make_trade_line(trade, item, cif_fc=Decimal("500.00"))

        rows = reconciliation_queries.missing_boe()

        self.assertFalse(any(r["trade_id"] == trade.id for r in rows))

    def test_excludes_purchase_direction(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE,
            to_company=company,
            invoice_number=f"P-TEST-{uuid.uuid4().int % 999999:06d}",
        )
        self.make_trade_line(trade, item, cif_fc=Decimal("500.00"))

        rows = reconciliation_queries.missing_boe()

        self.assertFalse(any(r["trade_id"] == trade.id for r in rows))


class MissingInvoiceQueryTests(ReconciliationFixtureMixin, TestCase):
    def test_detects_boe_with_blank_invoice_no(self):
        company = self.make_company()
        boe = self.make_boe(company, invoice_no="")

        rows = reconciliation_queries.missing_invoice()

        self.assertTrue(any(r["boe_id"] == boe.id for r in rows))

    def test_excludes_boe_with_invoice_no_set(self):
        company = self.make_company()
        boe = self.make_boe(company, invoice_no="SOME/INV/0001")

        rows = reconciliation_queries.missing_invoice()

        self.assertFalse(any(r["boe_id"] == boe.id for r in rows))


class DuplicateDebitsQueryTests(ReconciliationFixtureMixin, TestCase):
    def test_detects_the_double_debit_bug_scenario(self):
        """SALE line debits sr_number, a RowDetails debit row ALSO debits
        the same sr_number on a BOE NOT in that trade's boes -> flagged."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company, boes=None)  # NOT linked
        self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        rows = reconciliation_queries.duplicate_debits()

        matching = [r for r in rows if r["trade_id"] == trade.id and r["boe_id"] == boe.id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["invoice_debit"], Decimal("1000.00"))
        self.assertEqual(matching[0]["boe_debit"], Decimal("1000.00"))
        self.assertEqual(matching[0]["difference"], Decimal("0.00"))

    def test_line_level_fix_excludes_matched_boe(self):
        """When an ACTIVE InvoiceBOEAllocation ties the trade line to the
        BOE debit row, it's excluded by calculate_debit()'s allocation-
        driven exclusion -- must NOT show up as a duplicate here either.

        Phase A: merely linking the BOE to the trade's `boes` M2M is no
        longer sufficient on its own for calculate_debit() to exclude a
        row -- an explicit, ACTIVE InvoiceBOEAllocation is required, and
        duplicate_debits()'s "already excluded" check mirrors that same
        condition (see queries.duplicate_debits()'s docstring).
        """
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        debit_row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company, boes=[boe])  # linked
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))
        create_invoice_boe_allocation(
            trade_line=trade_line,
            row_details=debit_row,
            qty=DEC_0,
            cif_fc=Decimal("1000.00"),
            cif_inr=Decimal("1000.00") * Decimal("84.5"),
            user=None,
        )

        rows = reconciliation_queries.duplicate_debits()

        self.assertFalse(any(r["trade_id"] == trade.id for r in rows))


class CifComparisonQueryTests(ReconciliationFixtureMixin, TestCase):
    def test_flags_mismatch_beyond_tolerance(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company, boes=[boe])
        # Invoice line total (1200) vs BOE debit total (1000) -- 200 diff,
        # comfortably beyond the default 1.00 tolerance.
        self.make_trade_line(trade, item, cif_fc=Decimal("1200.00"))

        rows = reconciliation_queries.cif_comparison()

        matching = [r for r in rows if r["trade_id"] == trade.id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["invoice_total"], Decimal("1200.00"))
        self.assertEqual(matching[0]["boe_total"], Decimal("1000.00"))
        self.assertEqual(matching[0]["difference"], Decimal("200.00"))

    def test_no_flag_when_within_tolerance(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company, boes=[boe])
        self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        rows = reconciliation_queries.cif_comparison()

        self.assertFalse(any(r["trade_id"] == trade.id for r in rows))


class MultiBoeMultiInvoiceQueryTests(ReconciliationFixtureMixin, TestCase):
    def test_multi_boe_per_invoice_detects_trade_with_two_boes(self):
        company = self.make_company()
        boe_a = self.make_boe(company)
        boe_b = self.make_boe(company)
        trade = self.make_sale_trade(company, boes=[boe_a, boe_b])

        rows = reconciliation_queries.multi_boe_per_invoice()

        matching = [r for r in rows if r["trade_id"] == trade.id]
        self.assertEqual(len(matching), 1)
        self.assertCountEqual(
            matching[0]["boe_numbers"],
            [boe_a.bill_of_entry_number, boe_b.bill_of_entry_number],
        )

    def test_multi_invoice_per_boe_detects_boe_with_two_trades(self):
        company = self.make_company()
        boe = self.make_boe(company)
        trade_a = self.make_sale_trade(company, boes=[boe])
        trade_b = self.make_sale_trade(company, boes=[boe])

        rows = reconciliation_queries.multi_invoice_per_boe()

        matching = [r for r in rows if r["boe_id"] == boe.id]
        self.assertEqual(len(matching), 1)
        self.assertCountEqual(
            matching[0]["invoice_numbers"],
            [trade_a.invoice_number, trade_b.invoice_number],
        )


class DuplicateBoesQueryTests(ReconciliationFixtureMixin, TestCase):
    def test_detects_near_duplicate_boes(self):
        company = self.make_company()
        port = self.make_port()
        same_date = datetime.now().date()
        boe_a = self.make_boe(company, port=port, boe_date=same_date)
        boe_b = self.make_boe(company, port=port, boe_date=same_date)
        item_license = self.make_license(company)
        item_a = self.make_item(item_license, 1)
        item_b = self.make_item(item_license, 2)
        # Near-identical CIF (within default 1.00 tolerance).
        self.make_debit_row(boe_a, item_a, cif_fc=Decimal("1000.00"))
        self.make_debit_row(boe_b, item_b, cif_fc=Decimal("1000.50"))

        rows = reconciliation_queries.duplicate_boes()

        pair_ids = {(r["boe_id_a"], r["boe_id_b"]) for r in rows} | {
            (r["boe_id_b"], r["boe_id_a"]) for r in rows
        }
        self.assertIn((boe_a.id, boe_b.id), pair_ids)

    def test_no_flag_when_cif_far_apart(self):
        company = self.make_company()
        port = self.make_port()
        same_date = datetime.now().date()
        boe_a = self.make_boe(company, port=port, boe_date=same_date)
        boe_b = self.make_boe(company, port=port, boe_date=same_date)
        item_license = self.make_license(company)
        item_a = self.make_item(item_license, 1)
        item_b = self.make_item(item_license, 2)
        self.make_debit_row(boe_a, item_a, cif_fc=Decimal("1000.00"))
        self.make_debit_row(boe_b, item_b, cif_fc=Decimal("5000.00"))

        rows = reconciliation_queries.duplicate_boes()

        pair_ids = {(r["boe_id_a"], r["boe_id_b"]) for r in rows} | {
            (r["boe_id_b"], r["boe_id_a"]) for r in rows
        }
        self.assertNotIn((boe_a.id, boe_b.id), pair_ids)


class SummaryQueryTests(ReconciliationFixtureMixin, TestCase):
    def test_summary_returns_expected_keys(self):
        result = reconciliation_queries.summary()
        expected_keys = {
            "total_boe", "total_import_invoices", "matched", "unmatched_boe",
            "unmatched_invoice", "duplicate_debits", "cif_difference",
        }
        self.assertEqual(set(result.keys()), expected_keys)


# ---------------------------------------------------------------------------
# Write actions
# ---------------------------------------------------------------------------

class ReconciliationWriteActionTests(ReconciliationFixtureMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=f"reconciler-{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123!",
            is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_link_adds_boe_to_trade_and_logs(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, invoice_no="")
        trade = self.make_sale_trade(company, boes=None, invoice_number="LM/2025-26/0001")
        self.make_trade_line(trade, item, cif_fc=Decimal("500.00"))

        url = reverse("reconciliation:reconciliation-link")
        response = self.client.post(url, {"trade_id": trade.id, "boe_id": boe.id}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        trade.refresh_from_db()
        boe.refresh_from_db()
        self.assertIn(boe.id, trade.boes.values_list("id", flat=True))
        # Shared stamping helper should have copied the trade's invoice onto the BOE.
        self.assertEqual(boe.invoice_no, "LM/2025-26/0001")

        log = ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_LINK, trade=trade).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.bill_of_entry_id, boe.id)
        self.assertEqual(log.before["boe_ids"], [])
        self.assertEqual(log.after["boe_ids"], [boe.id])
        self.assertEqual(log.user_id, self.user.id)

    def test_note_creates_reconciliation_note_and_log(self):
        company = self.make_company()
        trade = self.make_sale_trade(company, boes=None)

        url = reverse("reconciliation:reconciliation-note")
        response = self.client.post(
            url,
            {"status": "IGNORED", "reason": "Known bulk-import artifact", "trade_id": trade.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        note = ReconciliationNote.objects.get(trade=trade)
        self.assertEqual(note.status, ReconciliationNote.STATUS_IGNORED)
        self.assertEqual(note.reason, "Known bulk-import artifact")

        log = ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_IGNORE, trade=trade).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.after["status"], "IGNORED")

    def test_note_rejects_multiple_targets(self):
        company = self.make_company()
        trade = self.make_sale_trade(company, boes=None)
        boe = self.make_boe(company)

        url = reverse("reconciliation:reconciliation-note")
        response = self.client.post(
            url,
            {"status": "IGNORED", "trade_id": trade.id, "bill_of_entry_id": boe.id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_merge_boe_delegates_to_boe_service_and_logs(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        target_boe = self.make_boe(company)
        source_boe = self.make_boe(company)
        self.make_debit_row(source_boe, item, cif_fc=Decimal("750.00"))
        source_boe_id = source_boe.id

        url = reverse("reconciliation:reconciliation-merge-boe")
        response = self.client.post(
            url,
            {"target_boe_id": target_boe.id, "source_boe_id": source_boe_id},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(BillOfEntryModel.objects.filter(id=source_boe_id).exists())
        self.assertTrue(
            RowDetails.objects.filter(bill_of_entry=target_boe, sr_number=item).exists()
        )

        log = ReconciliationLog.objects.filter(
            action=ReconciliationLog.ACTION_MERGE_BOE, bill_of_entry=target_boe
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.before["source_boe_id"], source_boe_id)
