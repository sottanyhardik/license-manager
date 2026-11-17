"""
Characterization tests (WS4): editing `invoice_no` on a GENUINELY hidden
BOE (hidden via `hide_boe`, i.e. invoice_no == "OTH" with a latest HIDE_BOE
log) through the two plain write paths:

  * POST /bill-of-entries/{id}/update-invoice-no/   (boe_service.update_invoice_no)
  * PATCH /bill-of-entries/{id}/ {"invoice_no": ...} (BillOfEntrySerializer.update)

Iteration 1 pinned that both silently un-hid the BOE (no RESTORE_BOE log,
no licence recompute).  Owner decision D1 (2026-11-17): a change on a
genuinely hidden BOE is HTTP 400 on both paths (use restore/hide); the
unchanged value is a no-op success; a legacy free-text 'OTH' on a
never-hidden BOE stays editable.  Flipped assertions are marked "D1".

Owner decision D6: restore decides "hidden" from the audit history
(`genuinely_hidden_boe_ids`), never from invoice_no == 'OTH', and never
erases a legitimate 'OTH' invoice (see RestoreUsesGenuineHiddenStateTests).
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.bill_of_entry.models import BillOfEntryModel, OTH_INVOICE_MARKER, genuinely_hidden_boe_ids
from apps.bill_of_entry.services.boe_service import hide_boe
from apps.bill_of_entry.tests.test_boe_api_contract import (
    LOCMEM_CACHES, BoeApiFixtureMixin, boe_detail_url,
)
from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.signals import update_license_flags
from apps.reconciliation.models import ReconciliationLog


@override_settings(CACHES=LOCMEM_CACHES)
class InvoiceNoEditOnHiddenBoeTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("10000.00"))
        # A Purchase trade makes hiding actually move the balance (see
        # HideBoeBalanceImmediacyTests.test_hide_and_restore_round_trip_with_purchase).
        self.make_purchase_trade(self.company, self.item, cif_fc=Decimal("4000.00"))
        self.boe = self.make_boe(self.company)
        self.make_debit_row(self.boe, self.item, cif_fc=Decimal("3000.00"), qty=Decimal("30.000"))
        update_license_flags(self.license)
        self.license.refresh_from_db()
        self.assertEqual(self.license.balance_cif, Decimal("1000.00"))

        hide_boe(self.boe, user=None, reason="Previous owner")
        self.license.refresh_from_db()
        self.hidden_balance = self.license.balance_cif
        self.assertEqual(self.hidden_balance, Decimal("7000.00"))
        self.assertIn(self.boe.id, genuinely_hidden_boe_ids(boe_ids=[self.boe.id]))

        self.manager = self.make_role_user("BOE_MANAGER")
        self.client = self.client_for(self.manager)

    def _restore_log_count(self):
        return ReconciliationLog.objects.filter(
            action=ReconciliationLog.ACTION_RESTORE_BOE, bill_of_entry=self.boe,
        ).count()

    def _assert_still_hidden_and_unchanged(self):
        """D1: the rejected edit left the BOE hidden, wrote no audit row and
        did not touch the stored balance (which is still correct)."""
        self.boe.refresh_from_db()
        self.assertEqual(self.boe.invoice_no, OTH_INVOICE_MARKER)
        self.assertIn(self.boe.id, genuinely_hidden_boe_ids(boe_ids=[self.boe.id]))
        self.assertEqual(self._restore_log_count(), 0)
        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(self.license), self.hidden_balance)
        self.license.refresh_from_db()
        self.assertEqual(self.license.balance_cif, self.hidden_balance)

    def test_update_invoice_no_blank_on_hidden_boe_is_400(self):
        response = self.client.post(
            boe_detail_url(self.boe.id, "update-invoice-no/"), {"invoice_no": ""}, format="json",
        )

        # D1 (flipped from 200 + silent un-hide): rejected, pointing to restore.
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(response.data.keys()), ["error"])
        self.assertIn("restore", response.data["error"].lower())
        self._assert_still_hidden_and_unchanged()

    def test_patch_invoice_no_on_hidden_boe_is_400(self):
        # PATCH reaches the invoiced/hidden BOE without ?is_invoice=all
        # (partial_update skips the is_invoice queryset filter).
        response = self.client.patch(boe_detail_url(self.boe.id), {"invoice_no": "INV-9"}, format="json")

        # D1 (flipped from 200 + silent un-hide; implemented by A1 in the serializer).
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("invoice_no", response.data)
        self.assertIn("restore", str(response.data["invoice_no"]).lower())
        self._assert_still_hidden_and_unchanged()

    def test_resending_oth_on_hidden_boe_is_noop_success(self):
        rejected = self.client.post(
            boe_detail_url(self.boe.id, "update-invoice-no/"), {"invoice_no": ""}, format="json",
        )
        self.assertEqual(rejected.status_code, 400)
        hide_logs_before = ReconciliationLog.objects.filter(
            action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=self.boe,
        ).count()

        response = self.client.post(
            boe_detail_url(self.boe.id, "update-invoice-no/"), {"invoice_no": OTH_INVOICE_MARKER}, format="json",
        )

        # D1 (flipped from "silently re-hides"): the unchanged value is a
        # no-op success; the BOE never left the hidden state.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["invoice_no"], OTH_INVOICE_MARKER)
        self.assertIn(self.boe.id, genuinely_hidden_boe_ids(boe_ids=[self.boe.id]))
        self.assertEqual(
            ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=self.boe).count(),
            hide_logs_before,
        )
        self._assert_still_hidden_and_unchanged()

    def test_viewer_cannot_unhide_via_update_invoice_no(self):
        """D2 keeps BOE_VIEWER's update-invoice-no exception; D1 still blocks
        the change on a hidden BOE."""
        viewer_client = self.client_for(self.make_role_user("BOE_VIEWER"))
        response = viewer_client.post(
            boe_detail_url(self.boe.id, "update-invoice-no/"), {"invoice_no": "INV-V"}, format="json",
        )

        # D1 (flipped from 200 + silent un-hide).
        self.assertEqual(response.status_code, 400)
        self._assert_still_hidden_and_unchanged()

    def test_service_raises_value_error_with_restore_hint(self):
        from apps.bill_of_entry.services.boe_service import update_invoice_no

        with self.assertRaisesMessage(ValueError, "Restore the bill of entry"):
            update_invoice_no(self.boe, "INV-S")
        self._assert_still_hidden_and_unchanged()

    def test_restore_boe_is_the_audited_path_for_comparison(self):
        """Baseline: the sanctioned path writes a RESTORE_BOE log and refreshes."""
        from apps.bill_of_entry.services.boe_service import restore_boe

        restore_boe(self.boe, user=None, reason="restore")

        self.assertEqual(self._restore_log_count(), 1)
        self.license.refresh_from_db()
        self.assertEqual(self.license.balance_cif, Decimal("1000.00"))


@override_settings(CACHES=LOCMEM_CACHES)
class LegacyOthInvoiceStaysEditableTests(BoeApiFixtureMixin, TestCase):
    """A never-hidden BOE whose real invoice text is 'OTH' (legacy free text)
    is NOT hidden and must stay editable -- pinned so a future guard does
    not over-reach."""

    def test_legacy_oth_is_not_hidden_and_is_editable(self):
        company = self.make_company()
        boe = self.make_boe(company, invoice_no=OTH_INVOICE_MARKER)
        self.assertEqual(genuinely_hidden_boe_ids(boe_ids=[boe.id]), set())

        client = self.client_for(self.make_role_user("ACCOUNT_ACCESS"))
        response = client.post(boe_detail_url(boe.id, "update-invoice-no/"), {"invoice_no": "INV-L"}, format="json")

        self.assertEqual(response.status_code, 200)
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "INV-L")
        self.assertFalse(ReconciliationLog.objects.filter(bill_of_entry=boe).exists())


@override_settings(CACHES=LOCMEM_CACHES)
class RestoreUsesGenuineHiddenStateTests(BoeApiFixtureMixin, TestCase):
    """D6: restore acts only on genuinely hidden BOEs and gives back the
    exact pre-hide invoice number, including a legitimate 'OTH'."""

    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)

    def _boe(self, invoice_no=""):
        boe = self.make_boe(self.company, invoice_no=invoice_no)
        self.make_debit_row(boe, self.item, cif_fc=Decimal("100.00"))
        return boe

    def _restore_logs(self, boe):
        return ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_RESTORE_BOE, bill_of_entry=boe)

    def test_restore_never_hidden_legacy_oth_is_noop(self):
        from apps.bill_of_entry.services.boe_service import restore_boe

        boe = self._boe(invoice_no=OTH_INVOICE_MARKER)

        result = restore_boe(boe, user=None, reason="r")

        self.assertIsNone(result["restored_at"])
        self.assertEqual(result["invoice_no"], OTH_INVOICE_MARKER)
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, OTH_INVOICE_MARKER)
        self.assertFalse(self._restore_logs(boe).exists())

    def test_bulk_restore_skips_never_hidden_legacy_oth(self):
        from apps.bill_of_entry.services.boe_service import restore_boes_bulk

        legacy = self._boe(invoice_no=OTH_INVOICE_MARKER)
        hidden = self._boe(invoice_no="INV-H")
        hide_boe(hidden, user=None, reason="h")

        result = restore_boes_bulk([str(legacy.id), hidden.id], user=None)

        self.assertEqual(result["skipped"], [legacy.id])
        self.assertEqual([r["id"] for r in result["restored"]], [hidden.id])
        legacy.refresh_from_db()
        hidden.refresh_from_db()
        self.assertEqual(legacy.invoice_no, OTH_INVOICE_MARKER)
        self.assertEqual(hidden.invoice_no, "INV-H")

    def test_hide_then_restore_gives_back_legacy_oth(self):
        from apps.bill_of_entry.services.boe_service import restore_boe

        boe = self._boe(invoice_no=OTH_INVOICE_MARKER)
        hide_boe(boe, user=None, reason="h")
        hide_log = ReconciliationLog.objects.get(action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe)
        self.assertEqual(hide_log.before, {"is_hidden": False, "invoice_no": OTH_INVOICE_MARKER})
        self.assertIn(boe.id, genuinely_hidden_boe_ids(boe_ids=[boe.id]))

        result = restore_boe(boe, user=None, reason="r")

        self.assertEqual(result["invoice_no"], OTH_INVOICE_MARKER)
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, OTH_INVOICE_MARKER)
        self.assertEqual(genuinely_hidden_boe_ids(boe_ids=[boe.id]), set())

    def test_repeated_hide_then_restore_gives_back_original_invoice(self):
        from apps.bill_of_entry.services.boe_service import restore_boe

        boe = self._boe(invoice_no="INV-1")
        hide_boe(boe, user=None, reason="first")
        hide_boe(boe, user=None, reason="again")

        result = restore_boe(boe, user=None, reason="r")

        self.assertEqual(result["invoice_no"], "INV-1")
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "INV-1")

    def test_oth_retyped_after_restore_is_not_restorable(self):
        from apps.bill_of_entry.services.boe_service import restore_boe, update_invoice_no

        boe = self._boe(invoice_no="INV-2")
        hide_boe(boe, user=None, reason="h")
        restore_boe(boe, user=None, reason="r")
        update_invoice_no(boe, OTH_INVOICE_MARKER)   # legacy free text again
        self.assertEqual(genuinely_hidden_boe_ids(boe_ids=[boe.id]), set())

        result = restore_boe(boe, user=None, reason="r2")

        self.assertIsNone(result["restored_at"])
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, OTH_INVOICE_MARKER)
        self.assertEqual(self._restore_logs(boe).count(), 1)


@override_settings(CACHES=LOCMEM_CACHES)
class LegacyOthRestoreAndTypeTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)

    def test_first_ever_hide_log_with_oth_restores_oth(self):
        from apps.bill_of_entry.services.boe_service import restore_boe

        boe = self.make_boe(self.company, invoice_no=OTH_INVOICE_MARKER)
        self.make_debit_row(boe, self.item, cif_fc=Decimal("100.00"))
        # Legacy audit row: hide recorded without is_hidden=False.
        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe,
            before={"is_hidden": True, "invoice_no": OTH_INVOICE_MARKER},
            after={"is_hidden": True},
        )
        self.assertIn(boe.id, genuinely_hidden_boe_ids(boe_ids=[boe.id]))

        result = restore_boe(boe, user=None, reason="r")

        self.assertEqual(result["invoice_no"], OTH_INVOICE_MARKER)
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, OTH_INVOICE_MARKER)

    def test_oth_after_a_prior_restore_still_restores_none(self):
        from apps.bill_of_entry.services.boe_service import restore_boe

        boe = self.make_boe(self.company, invoice_no="INV-1")
        self.make_debit_row(boe, self.item, cif_fc=Decimal("100.00"))
        hide_boe(boe, user=None, reason="h")
        restore_boe(boe, user=None, reason="r")
        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe,
            before={"is_hidden": True, "invoice_no": OTH_INVOICE_MARKER}, after={"is_hidden": True},
        )
        BillOfEntryModel.objects.filter(pk=boe.pk).update(invoice_no=OTH_INVOICE_MARKER)
        boe.refresh_from_db()

        result = restore_boe(boe, user=None, reason="r2")

        self.assertIsNone(result["invoice_no"])

    def test_non_string_invoice_no_is_value_error(self):
        from apps.bill_of_entry.services.boe_service import update_invoice_no

        boe = self.make_boe(self.company, invoice_no="INV-1")
        for bad in (123, ["x"], {"a": 1}):
            with self.assertRaisesMessage(ValueError, "string"):
                update_invoice_no(boe, bad)
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "INV-1")

    def test_non_string_invoice_no_endpoint_is_400(self):
        client = self.client_for(self.make_role_user("BOE_MANAGER"))
        boe = self.make_boe(self.company, invoice_no="INV-1")
        response = client.post(boe_detail_url(boe.id, "update-invoice-no/"), {"invoice_no": 123}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
