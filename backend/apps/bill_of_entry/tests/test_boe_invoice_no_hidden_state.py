"""
Characterization tests (WS4): editing `invoice_no` on a GENUINELY hidden
BOE (hidden via `hide_boe`, i.e. invoice_no == "OTH" with a latest HIDE_BOE
log) through the two plain write paths:

  * POST /bill-of-entries/{id}/update-invoice-no/   (boe_service.update_invoice_no)
  * PATCH /bill-of-entries/{id}/ {"invoice_no": ...} (BillOfEntrySerializer.update)

Today both silently un-hide the BOE: no RESTORE_BOE log, no licence
recompute, so the stored `LicenseBalance.balance_cif` is left stale while
the live calculator already counts the BOE again.

CURRENT BEHAVIOUR — owner decision pending: BUSINESS-RULE / API CONTRACT
("changing invoice_no on a genuinely hidden BOE ... un-hides it with no
RESTORE_BOE log and no `_refresh_licenses`. Setting it back to 'OTH'
silently re-hides it."). Every assertion below that encodes the gap carries
that marker so WS5 can flip exactly those.
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.bill_of_entry.models import OTH_INVOICE_MARKER, genuinely_hidden_boe_ids
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

    def _assert_unhidden_without_audit_and_stale(self):
        self.boe.refresh_from_db()
        # CURRENT BEHAVIOUR — owner decision pending: BUSINESS-RULE / API CONTRACT
        # (BOE becomes visible again with no RESTORE_BOE log written).
        self.assertNotIn(self.boe.id, genuinely_hidden_boe_ids(boe_ids=[self.boe.id]))
        self.assertEqual(self._restore_log_count(), 0)

        # The live calculator already counts the BOE again ...
        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(self.license), Decimal("1000.00"))
        # ... but the stored cache was never refreshed.
        self.license.refresh_from_db()
        # CURRENT BEHAVIOUR — owner decision pending: BUSINESS-RULE / API CONTRACT
        # (no `_refresh_licenses`; stored LicenseBalance.balance_cif is stale).
        self.assertEqual(self.license.balance_cif, self.hidden_balance)

    def test_update_invoice_no_blank_unhides_without_restore_log(self):
        response = self.client.post(
            boe_detail_url(self.boe.id, "update-invoice-no/"), {"invoice_no": ""}, format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["invoice_no"], "")
        self._assert_unhidden_without_audit_and_stale()

    def test_patch_invoice_no_unhides_without_restore_log(self):
        # PATCH reaches the invoiced/hidden BOE without ?is_invoice=all
        # (partial_update skips the is_invoice queryset filter).
        response = self.client.patch(boe_detail_url(self.boe.id), {"invoice_no": "INV-9"}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["invoice_no"], "INV-9")
        self._assert_unhidden_without_audit_and_stale()

    def test_setting_oth_again_silently_rehides(self):
        self.client.post(boe_detail_url(self.boe.id, "update-invoice-no/"), {"invoice_no": ""}, format="json")
        self.assertNotIn(self.boe.id, genuinely_hidden_boe_ids(boe_ids=[self.boe.id]))
        hide_logs_before = ReconciliationLog.objects.filter(
            action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=self.boe,
        ).count()

        response = self.client.post(
            boe_detail_url(self.boe.id, "update-invoice-no/"), {"invoice_no": OTH_INVOICE_MARKER}, format="json",
        )

        self.assertEqual(response.status_code, 200)
        # CURRENT BEHAVIOUR — owner decision pending: BUSINESS-RULE / API CONTRACT
        # (the stale latest HIDE_BOE log makes plain 'OTH' count as hidden again;
        # no new HIDE_BOE log is written for this re-hide).
        self.assertIn(self.boe.id, genuinely_hidden_boe_ids(boe_ids=[self.boe.id]))
        self.assertEqual(
            ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=self.boe).count(),
            hide_logs_before,
        )

    def test_viewer_can_unhide_via_update_invoice_no(self):
        """Combination of the two gaps: the read-only BOE_VIEWER can un-hide."""
        viewer_client = self.client_for(self.make_role_user("BOE_VIEWER"))
        response = viewer_client.post(
            boe_detail_url(self.boe.id, "update-invoice-no/"), {"invoice_no": "INV-V"}, format="json",
        )

        # CURRENT BEHAVIOUR — owner decision pending: PERMISSION / API CONTRACT
        # (BOE_VIEWER in AccountAccessPermission._roles).
        self.assertEqual(response.status_code, 200)
        self._assert_unhidden_without_audit_and_stale()

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
