"""
Tests for `apps.bill_of_entry.services.boe_service.hide_boe` / `restore_boe`
(and their bulk siblings `hide_boes_bulk` / `restore_boes_bulk`) -- the
"Hidden BOEs" (previous-owner utilisation) write path.

REWRITTEN: this file previously tested a first-generation, license-scoped
`hide_boe_for_license`/`restore_boe_for_license` API built around a
`RowDetails.is_hidden` column. Both are gone. The CURRENT mechanism (see
`apps.bill_of_entry.models.OTH_INVOICE_MARKER` and `boe_service`'s module
docstring) is:

  - BOE-LEVEL, not row-level: hiding sets `BillOfEntryModel.invoice_no =
    "OTH"` on the whole physical document. There is no per-row flag.
  - NOT scoped to a single licence: hiding/restoring applies uniformly to
    EVERY licence a BOE's `RowDetails` rows touch (explicitly, by product
    decision -- the old "must not affect the other licence" behaviour this
    file used to pin is now SUPERSEDED; seethe module docstring for
    `boe_service.py`). Every touched licence is recomputed.
  - The single most important property under test now is the OPPOSITE of
    the old one: a BOE spanning two licences must have BOTH of them
    recomputed on hide/restore, never just one.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.bill_of_entry.models import BillOfEntryModel, OTH_INVOICE_MARKER, RowDetails
from apps.bill_of_entry.serializers import BillOfEntrySerializer
from apps.bill_of_entry.services.boe_service import (
    hide_boe, hide_boes_bulk, restore_boe, restore_boes_bulk,
)
from apps.core.constants import DEBIT, DEC_0
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.signals import update_license_flags
from apps.reconciliation.models import ReconciliationLog

User = get_user_model()


class BoeHideServiceFixtureMixin:
    def make_company(self, name="Test Co"):
        return CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name=name)

    def make_license(self, company):
        return LicenseDetailsModel.objects.create(
            license_number="03" + str(uuid.uuid4().int)[:8],
            license_date=datetime.now().date(),
            license_expiry_date=datetime.now().date() + timedelta(days=365),
            exporter=company,
        )

    def make_item(self, license_obj, serial_number=1):
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

    def make_purchase_trade(self, company, item, cif_fc):
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

    def make_user(self, name="hide-boe-actor"):
        return User.objects.create_user(
            username=f"{name}-{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123!",
        )


class BillOfEntryNestedRowUpdateTests(BoeHideServiceFixtureMixin, TestCase):
    def test_update_ignores_header_planning_metadata_when_creating_row(self):
        """Annotated planning metadata belongs to the BOE, not RowDetails.

        A nested update without a row id uses ``update_or_create``.  The
        metadata may be present in the validated nested payload after planning
        mapping, but is not a RowDetails field and must never be passed as a
        model default.
        """
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj)
        boe = self.make_boe(company)

        serializer = BillOfEntrySerializer()
        result = serializer.update(boe, {
            "item_details": [{
                "sr_number": item,
                "cif_inr": Decimal("409649.00"),
                "cif_fc": Decimal("4264.96"),
                "qty": Decimal("3000.000"),
                "planning_mapping_status": "MAPPED_EXPLICIT",
                "planning_mapping_source": "USER_SELECTED",
            }],
        })

        row = result.item_details.get(sr_number=item)
        self.assertEqual(row.cif_inr, Decimal("409649.000"))
        self.assertEqual(row.cif_fc, Decimal("4264.960"))
        self.assertEqual(row.qty, Decimal("3000.000"))


class HideBoeSpansMultipleLicensesTests(BoeHideServiceFixtureMixin, TestCase):
    """The CURRENT regression to pin (opposite of the old, removed
    behaviour): a single physical BOE with DEBIT rows against TWO different
    licences -- hiding it must mark the WHOLE BOE hidden and recompute BOTH
    licences; restoring it must put both back exactly as they were. There is
    deliberately NO cross-licence refusal/scoping any more (see
    `boe_service`'s module docstring)."""

    def test_hide_and_restore_both_recompute_every_touched_license(self):
        company = self.make_company()
        license_a = self.make_license(company)
        license_b = self.make_license(company)
        item_a = self.make_item(license_a, 1)
        item_b = self.make_item(license_b, 1)
        LicenseExportItemModel.objects.create(license=license_a, cif_fc=Decimal("10000.00"))
        LicenseExportItemModel.objects.create(license=license_b, cif_fc=Decimal("20000.00"))

        # ONE physical BOE, debiting BOTH licences (via two different items).
        boe = self.make_boe(company)
        self.make_debit_row(boe, item_a, cif_fc=Decimal("1000.00"), qty=Decimal("10.000"))
        self.make_debit_row(boe, item_b, cif_fc=Decimal("2000.00"), qty=Decimal("20.000"))

        update_license_flags(license_a)
        update_license_flags(license_b)
        license_a.refresh_from_db()
        license_b.refresh_from_db()
        balance_a_before = license_a.balance_cif
        balance_b_before = license_b.balance_cif
        self.assertEqual(balance_a_before, Decimal("9000.00"))  # 10000 - 1000
        self.assertEqual(balance_b_before, Decimal("18000.00"))  # 20000 - 2000

        result = hide_boe(boe, user=None, reason="Previous owner (spans two licences)")

        self.assertTrue(result["is_hidden"])
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, OTH_INVOICE_MARKER)

        # BOTH licences recomputed immediately -- no separate recalc call.
        # The raw (hidden-excluded) BOE debit total drops to zero for both,
        # proving the exclusion was actually applied to both licences --
        # but with NO Purchase trade on either licence, the Financial
        # Available Balance itself is UNCHANGED by hiding (Previous Owner
        # Utilisation simply relabels the same amount as no-longer-ours
        # instead of ours -- see `HideBoeBalanceImmediacyTests.test_hide_
        # with_no_purchase_leaves_balance_unchanged` for the same invariant
        # pinned in isolation).
        license_a.refresh_from_db()
        license_b.refresh_from_db()
        self.assertEqual(LicenseBalanceCalculator.calculate_boe_debit_total(license_a), DEC_0)
        self.assertEqual(LicenseBalanceCalculator.calculate_boe_debit_total(license_b), DEC_0)
        self.assertEqual(license_a.balance_cif, balance_a_before)
        self.assertEqual(license_b.balance_cif, balance_b_before)

        restore_boe(boe, user=None, reason="Restored in error")

        boe.refresh_from_db()
        self.assertNotEqual(boe.invoice_no, OTH_INVOICE_MARKER)
        license_a.refresh_from_db()
        license_b.refresh_from_db()
        self.assertEqual(license_a.balance_cif, balance_a_before)
        self.assertEqual(license_b.balance_cif, balance_b_before)


class HideBoeBalanceImmediacyTests(BoeHideServiceFixtureMixin, TestCase):
    """`hide_boe`/`restore_boe` must call `update_license_flags` themselves
    so `LicenseBalance.balance_cif` (== `calculate_financial_balance`, the
    Balance Engine's business figure -- see `LicenseDetailsModel.
    get_balance_cif`) reflects the change immediately, with NO separate
    recalculate call needed."""

    def test_hide_with_no_purchase_leaves_balance_unchanged(self):
        """With no Purchase trade, hiding a BOE just relabels its debit as
        'Previous Owner Utilisation' instead of 'our BOE debit' -- the CIF
        was already unavailable either way, so the Financial Available
        Balance is IDENTICAL before and after (a deliberate, non-obvious
        invariant of the Opening Balance / Previous Owner Utilisation gate
        -- see `LicenseBalanceCalculator.calculate_opening_balance`'s
        docstring). This is NOT the old (removed) mechanism's behaviour,
        where hiding would have freed up the full CIF again."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("10000.00"))
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("3000.00"), qty=Decimal("30.000"))

        update_license_flags(license_obj)
        license_obj.refresh_from_db()
        self.assertEqual(license_obj.balance_cif, Decimal("7000.00"))  # 10000 - 3000

        hide_boe(boe, user=None, reason="Previous owner")

        license_obj.refresh_from_db()
        self.assertEqual(license_obj.balance_cif, Decimal("7000.00"))
        self.assertEqual(license_obj.balance_cif, LicenseBalanceCalculator.calculate_financial_balance(license_obj))

    def test_hide_and_restore_round_trip_with_purchase(self):
        """With a Purchase trade in play, hiding a BOE DOES shift the
        balance -- Previous Owner Utilisation now nets against the Purchase
        credit too (see `calculate_opening_balance`'s docstring: "Hidden
        BOEs (never ours) AND Purchased CIF ... both left that original
        pool"). Restoring must put the balance back to its pre-hide figure
        exactly."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("10000.00"))
        self.make_purchase_trade(company, item, cif_fc=Decimal("4000.00"))
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("3000.00"), qty=Decimal("30.000"))

        update_license_flags(license_obj)
        license_obj.refresh_from_db()
        balance_before = license_obj.balance_cif
        self.assertEqual(balance_before, Decimal("1000.00"))  # 0 (opening) + 4000 (purchase) - 3000 (boe)

        hide_boe(boe, user=None, reason="Previous owner")

        license_obj.refresh_from_db()
        self.assertEqual(license_obj.balance_cif, Decimal("7000.00"))  # (10000-3000-4000) + 4000 - 0
        self.assertEqual(license_obj.balance_cif, LicenseBalanceCalculator.calculate_financial_balance(license_obj))

        restore_boe(boe, user=None, reason="Restored in error")

        license_obj.refresh_from_db()
        self.assertEqual(license_obj.balance_cif, balance_before)


class HideBoeIdempotencyTests(BoeHideServiceFixtureMixin, TestCase):
    def test_hide_is_idempotent(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"), qty=Decimal("5.000"))
        user1 = self.make_user("first-actor")
        user2 = self.make_user("second-actor")

        result1 = hide_boe(boe, user=user1, reason="first reason")
        result2 = hide_boe(boe, user=user2, reason="second reason")

        self.assertTrue(result1["is_hidden"])
        self.assertTrue(result2["is_hidden"])  # still hidden -- idempotent no-op on the BOE state

        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, OTH_INVOICE_MARKER)

        # Each call still writes its OWN audit-log entry (append-only ledger,
        # never mutated in place) -- the LATEST one reflects who/why most
        # recently, which `restore_boe` also relies on to find the value to
        # restore.
        logs = list(
            ReconciliationLog.objects.filter(
                action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe,
            ).order_by("created_on")
        )
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0].user_id, user1.id)
        self.assertEqual(logs[0].reason, "first reason")
        self.assertEqual(logs[1].user_id, user2.id)
        self.assertEqual(logs[1].reason, "second reason")

    def test_restore_is_idempotent_reports_none_restored_at_on_second_call(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"), qty=Decimal("5.000"))
        hide_boe(boe, user=None, reason="hide")

        result1 = restore_boe(boe, user=None, reason="restore")
        result2 = restore_boe(boe, user=None, reason="restore again")

        self.assertFalse(result1["is_hidden"])
        self.assertIsNotNone(result1["restored_at"])
        # Second restore is a no-op -- the BOE is already visible, and
        # `_apply_restore` only acts when `invoice_no == OTH_INVOICE_MARKER`.
        self.assertFalse(result2["is_hidden"])
        self.assertIsNone(result2["restored_at"])

        boe.refresh_from_db()
        self.assertNotEqual(boe.invoice_no, OTH_INVOICE_MARKER)

        # No second RESTORE_BOE log written for the no-op call.
        self.assertEqual(
            ReconciliationLog.objects.filter(
                action=ReconciliationLog.ACTION_RESTORE_BOE, bill_of_entry=boe,
            ).count(),
            1,
        )


class HideBoeReconciliationLogTests(BoeHideServiceFixtureMixin, TestCase):
    def test_hide_and_restore_each_write_a_reconciliation_log_entry(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"), qty=Decimal("5.000"))
        user = self.make_user()

        hide_boe(boe, user=user, reason="Previous owner")

        hide_log = ReconciliationLog.objects.get(action=ReconciliationLog.ACTION_HIDE_BOE)
        self.assertEqual(hide_log.bill_of_entry_id, boe.id)
        self.assertEqual(hide_log.user_id, user.id)
        self.assertEqual(hide_log.reason, "Previous owner")
        self.assertEqual(hide_log.after["is_hidden"], True)
        self.assertIsNone(hide_log.license_item)  # BOE-level action, not scoped to one item/licence

        restore_boe(boe, user=user, reason="Restored")

        restore_log = ReconciliationLog.objects.get(action=ReconciliationLog.ACTION_RESTORE_BOE)
        self.assertEqual(restore_log.bill_of_entry_id, boe.id)
        self.assertEqual(restore_log.after["is_hidden"], False)

    def test_restore_preserves_real_invoice_no_round_trip(self):
        """Hide preserves the BOE's prior `invoice_no` in the HIDE_BOE log's
        `before['invoice_no']` (no dedicated column); restore reads it back
        from the most recent such log row. Verify round-trip for a REAL
        invoice number, not just a blank one."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj)
        boe = self.make_boe(company, invoice_no="GE")
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"), qty=Decimal("5.000"))

        hide_result = hide_boe(boe, user=None, reason="Previous owner")
        self.assertEqual(hide_result["previous_invoice_no"], "GE")
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, OTH_INVOICE_MARKER)

        hide_log = ReconciliationLog.objects.get(action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe)
        self.assertEqual(hide_log.before["invoice_no"], "GE")

        restore_result = restore_boe(boe, user=None, reason="Restored")
        self.assertEqual(restore_result["invoice_no"], "GE")
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "GE")


class HideBoesBulkTests(BoeHideServiceFixtureMixin, TestCase):
    """`hide_boes_bulk`/`restore_boes_bulk` process every BOE independently
    but recompute each affected licence exactly ONCE, regardless of how many
    selected BOEs touch it -- and never refuse/skip a BOE for spanning
    multiple licences."""

    def test_bulk_hide_recomputes_each_affected_license_once(self):
        company = self.make_company()
        license_a = self.make_license(company)
        license_b = self.make_license(company)
        item_a1 = self.make_item(license_a, 1)
        item_a2 = self.make_item(license_a, 2)
        item_b = self.make_item(license_b, 1)
        LicenseExportItemModel.objects.create(license=license_a, cif_fc=Decimal("10000.00"))
        LicenseExportItemModel.objects.create(license=license_b, cif_fc=Decimal("20000.00"))

        # boe_1 debits license_a twice, via two DIFFERENT items on it (a
        # physical BOE can only carry one debit row per item -- see the
        # (bill_of_entry, sr_number, transaction_type) unique constraint on
        # `RowDetails`); boe_2 debits license_b once.
        boe_1 = self.make_boe(company)
        self.make_debit_row(boe_1, item_a1, cif_fc=Decimal("1000.00"), qty=Decimal("10.000"))
        self.make_debit_row(boe_1, item_a2, cif_fc=Decimal("500.00"), qty=Decimal("5.000"))
        boe_2 = self.make_boe(company)
        self.make_debit_row(boe_2, item_b, cif_fc=Decimal("2000.00"), qty=Decimal("20.000"))

        update_license_flags(license_a)
        update_license_flags(license_b)

        result = hide_boes_bulk([boe_1.id, boe_2.id, 999999999], user=None, reason="Bulk hide")

        self.assertEqual(len(result["hidden"]), 2)
        self.assertEqual(len(result["failed"]), 1)
        self.assertEqual(result["failed"][0]["id"], 999999999)
        self.assertCountEqual(result["licenses_refreshed"], [license_a.id, license_b.id])

        boe_1.refresh_from_db()
        boe_2.refresh_from_db()
        self.assertEqual(boe_1.invoice_no, OTH_INVOICE_MARKER)
        self.assertEqual(boe_2.invoice_no, OTH_INVOICE_MARKER)

        # Raw (hidden-excluded) debit totals drop to zero for both licences,
        # proving the exclusion applied everywhere it should -- but with no
        # Purchase trade on either licence, Financial Available Balance
        # itself is unchanged by hiding (same invariant as
        # `HideBoeSpansMultipleLicensesTests`/`HideBoeBalanceImmediacyTests`
        # above).
        self.assertEqual(LicenseBalanceCalculator.calculate_boe_debit_total(license_a), DEC_0)
        self.assertEqual(LicenseBalanceCalculator.calculate_boe_debit_total(license_b), DEC_0)
        license_a.refresh_from_db()
        license_b.refresh_from_db()
        self.assertEqual(license_a.balance_cif, Decimal("8500.00"))  # 10000 - 1000 - 500, unchanged
        self.assertEqual(license_b.balance_cif, Decimal("18000.00"))  # 20000 - 2000, unchanged

        restore_result = restore_boes_bulk([boe_1.id, boe_2.id], user=None, reason="Bulk restore")
        self.assertEqual(len(restore_result["restored"]), 2)
        self.assertEqual(restore_result["skipped"], [])

        license_a.refresh_from_db()
        license_b.refresh_from_db()
        self.assertEqual(license_a.balance_cif, Decimal("8500.00"))  # 10000 - 1000 - 500
        self.assertEqual(license_b.balance_cif, Decimal("18000.00"))  # 20000 - 2000

    def test_bulk_restore_skips_boe_that_is_not_hidden(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"), qty=Decimal("5.000"))

        result = restore_boes_bulk([boe.id], user=None, reason="no-op restore")

        self.assertEqual(result["restored"], [])
        self.assertEqual(result["skipped"], [boe.id])
        self.assertEqual(result["licenses_refreshed"], [])
