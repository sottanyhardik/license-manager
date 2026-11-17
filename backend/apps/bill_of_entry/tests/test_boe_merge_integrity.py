"""
Characterization tests (WS4): integrity side-effects of merging BOEs.

Two entry points call the same `boe_service.merge_boe`:
  * POST /api/bill-of-entries/{target}/merge/        (BOE workspace)
  * POST reconciliation:reconciliation-merge-boe     (Reconciliation panel)

Pinned:
  * audit: both entry points write exactly one MERGE_BOE log (WS5 moved the
    write into `merge_boe`; the BOE-side endpoint previously wrote none);
  * exchange_rate: D4 (flipped) — the survivor's rate is recomputed with the
    RowDetails-signal helper and persisted;
  * stored balances: D4 (flipped) — every affected licence/item is refreshed
    on commit by the existing helpers;
  * hidden source -> visible target: D4 (flipped) — rejected with 400.

Frozen priority / both-frozen / idempotency: test_boe_merge_frozen_priority.py.
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails, genuinely_hidden_boe_ids
from apps.bill_of_entry.services.boe_service import hide_boe
from apps.bill_of_entry.tests.test_boe_api_contract import (
    LOCMEM_CACHES, BoeApiFixtureMixin, boe_detail_url,
)
from apps.core.constants import DEBIT
from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.signals import update_license_flags
from apps.reconciliation.models import ReconciliationLog


@override_settings(CACHES=LOCMEM_CACHES)
class BoeMergeIntegrityTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item_a = self.make_item(self.license, 1)
        self.item_b = self.make_item(self.license, 2)
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("10000.00"))
        self.user = self.make_role_user("BOE_MANAGER", "TRADE_MANAGER")
        self.client = self.client_for(self.user)

    def _merge_logs(self):
        return ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_MERGE_BOE)

    def test_boe_side_merge_writes_exactly_one_merge_log(self):
        target = self.make_boe(self.company)
        source = self.make_boe(self.company)
        self.make_debit_row(source, self.item_a, cif_fc=Decimal("100.00"))
        source_id = source.id

        response = self.client.post(boe_detail_url(target.id, "merge/"), {"source_boe_id": source_id}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        # WS5 (flipped from 0): the BOE-side merge is now audited too.
        self.assertEqual(self._merge_logs().count(), 1)
        log = self._merge_logs().get()
        self.assertEqual(log.bill_of_entry_id, target.id)
        self.assertEqual(log.before["source_boe_id"], source_id)
        self.assertEqual(log.user_id, self.user.id)

    def test_reconciliation_merge_writes_exactly_one_merge_log(self):
        target = self.make_boe(self.company)
        source = self.make_boe(self.company)
        self.make_debit_row(source, self.item_a, cif_fc=Decimal("100.00"))
        source_id = source.id

        response = self.client.post(
            reverse("reconciliation:reconciliation-merge-boe"),
            {"target_boe_id": target.id, "source_boe_id": source_id}, format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._merge_logs().count(), 1)
        log = self._merge_logs().get()
        self.assertEqual(log.bill_of_entry_id, target.id)
        self.assertEqual(log.before["source_boe_id"], source_id)

    def test_exchange_rate_is_stale_after_merge_that_changes_totals(self):
        target = self.make_boe(self.company)   # stored exchange_rate 84.50
        source = self.make_boe(self.company)
        self.make_debit_row(target, self.item_a, cif_fc=Decimal("1000.00"))  # INR at 84.5
        RowDetails.objects.create(                                           # INR at 100.0
            bill_of_entry=source, sr_number=self.item_b, transaction_type=DEBIT,
            cif_fc=Decimal("1000.00"), cif_inr=Decimal("100000.00"), qty=Decimal("10.000"),
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                boe_detail_url(target.id, "merge/"), {"source_boe_id": source.id}, format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        target.refresh_from_db()
        self.assertEqual(target.get_total_fc, Decimal("2000"))
        self.assertEqual(target.get_total_inr, Decimal("184500"))
        recomputed = (target.get_total_inr / target.get_total_fc).quantize(Decimal("0.0001"))
        self.assertEqual(recomputed, Decimal("92.2500"))
        # D4 (flipped from the stale 84.5000): the recomputed rate is persisted
        # and returned.
        self.assertEqual(target.exchange_rate, Decimal("92.2500"))
        self.assertEqual(Decimal(str(response.data["boe"]["exchange_rate"])), Decimal("92.2500"))

    def test_stored_balances_refreshed_by_merge(self):
        from apps.core.scripts.calculate_balance import update_balance_values
        from apps.license.models import LicenseBalance, LicenseImportItemsModel

        target = self.make_boe(self.company)
        source = self.make_boe(self.company)
        self.make_debit_row(source, self.item_a, cif_fc=Decimal("500.00"))
        update_license_flags(self.license)
        update_balance_values(LicenseImportItemsModel.objects.get(pk=self.item_a.pk))
        self.license.refresh_from_db()
        self.assertEqual(self.license.balance_cif, Decimal("9500.00"))
        item_debited = LicenseImportItemsModel.objects.get(pk=self.item_a.pk).debited_value
        # Make both stored caches stale so the refresh is observable.
        LicenseBalance.objects.filter(license_id=self.license.pk).update(balance_cif=Decimal("1.00"))
        LicenseImportItemsModel.objects.filter(pk=self.item_a.pk).update(debited_value=Decimal("0"))

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                boe_detail_url(target.id, "merge/"), {"source_boe_id": source.id}, format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        # Same licence, same debit: the live figure is unchanged by a pure move.
        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(self.license), Decimal("9500.00"))
        self.license.refresh_from_db()
        # D4 (flipped from "not refreshed"): recomputed by update_license_flags /
        # update_balance_values on commit.
        self.assertEqual(self.license.balance_cif, Decimal("9500.00"))
        self.assertEqual(LicenseImportItemsModel.objects.get(pk=self.item_a.pk).debited_value, item_debited)

    def test_merging_hidden_source_into_visible_target_is_rejected(self):
        # A Purchase trade makes the hidden/visible split move the balance.
        self.make_purchase_trade(self.company, self.item_a, cif_fc=Decimal("4000.00"))
        target = self.make_boe(self.company)
        source = self.make_boe(self.company)
        self.make_debit_row(target, self.item_a, cif_fc=Decimal("1000.00"))
        moved_row = self.make_debit_row(source, self.item_b, cif_fc=Decimal("2000.00"))
        hide_boe(source, user=None, reason="Previous owner")
        self.assertIn(source.id, genuinely_hidden_boe_ids(boe_ids=[source.id]))
        self.license.refresh_from_db()
        stored_before = self.license.balance_cif
        self.assertEqual(stored_before, Decimal("7000.00"))

        response = self.client.post(boe_detail_url(target.id, "merge/"), {"source_boe_id": source.id}, format="json")

        # D4 (flipped from 200): exactly one side genuinely hidden -> 400.
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(list(response.data.keys()), ["error"])
        self.assertIn("hidden", response.data["error"])
        self.assertTrue(BillOfEntryModel.objects.filter(id=source.id).exists())
        self.assertEqual(RowDetails.objects.get(id=moved_row.id).bill_of_entry_id, source.id)
        self.assertIn(source.id, genuinely_hidden_boe_ids(boe_ids=[source.id]))
        self.assertEqual(LicenseBalanceCalculator.calculate_boe_debit_total(self.license), Decimal("1000.00"))
        self.assertFalse(self._merge_logs().exists())
        self.license.refresh_from_db()
        self.assertEqual(self.license.balance_cif, stored_before)

    def test_merging_visible_source_into_hidden_target_is_rejected(self):
        target = self.make_boe(self.company)
        source = self.make_boe(self.company)
        self.make_debit_row(target, self.item_a, cif_fc=Decimal("1000.00"))
        self.make_debit_row(source, self.item_b, cif_fc=Decimal("2000.00"))
        hide_boe(target, user=None, reason="Previous owner")

        response = self.client.post(
            reverse("reconciliation:reconciliation-merge-boe"),
            {"target_boe_id": target.id, "source_boe_id": source.id}, format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(list(response.data.keys()), ["detail"])
        self.assertTrue(BillOfEntryModel.objects.filter(id=source.id).exists())
        self.assertFalse(self._merge_logs().exists())


@override_settings(CACHES=LOCMEM_CACHES)
class MergeReviewFixTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item_a = self.make_item(self.license, 1)
        self.item_b = self.make_item(self.license, 2)
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("10000.00"))
        self.user = self.make_role_user("BOE_MANAGER", "TRADE_MANAGER")

    def _merge(self, target, source_id):
        from apps.bill_of_entry.services import boe_service

        with self.captureOnCommitCallbacks(execute=True):
            return boe_service.merge_boe(target, source_id, user=self.user)

    def test_exchange_rate_is_forced_even_for_sub_one_movement(self):
        target = self.make_boe(self.company)
        source = self.make_boe(self.company)
        # row rate 84.5 vs stored 84.50 -> |diff| < 1: only force=True writes it.
        RowDetails.objects.create(
            bill_of_entry=target, sr_number=self.item_a, transaction_type=DEBIT,
            cif_fc=Decimal("100.00"), cif_inr=Decimal("8400.00"), qty=Decimal("1.000"),
        )
        self.make_debit_row(source, self.item_b, cif_fc=Decimal("100.00"))
        BillOfEntryModel.objects.filter(pk=target.pk).update(exchange_rate=Decimal("84.5000"))

        result = self._merge(target, source.id)

        survivor = BillOfEntryModel.objects.get(pk=result["target_boe_id"])
        self.assertEqual(survivor.exchange_rate, Decimal("84.2500"))  # (8400+8450)/200

    def _linked(self, with_invoice=False):
        plain = self.make_boe(self.company)
        other = self.make_boe(self.company)
        self.make_debit_row(plain, self.item_a, cif_fc=Decimal("100.00"))
        self.make_debit_row(other, self.item_b, cif_fc=Decimal("100.00"))
        return plain, other

    def test_merge_rejected_when_removed_boe_has_trade_links_both_orders(self):
        from apps.bill_of_entry.services import boe_service

        for linked_is_target in (False, True):
            plain, other = self._linked()
            linked, free = (plain, other) if linked_is_target else (other, plain)
            trade = self.make_purchase_trade(self.company, self.item_a, cif_fc=Decimal("10.00"))
            trade.boes.add(linked)
            # Unswapped: removed == requested source.  Swapped: frozen priority
            # makes the linked BOE the removed one although it was the target.
            if linked_is_target:
                RowDetails.objects.filter(bill_of_entry=free).update(is_frozen=True)
                target, source = linked, free
            else:
                target, source = free, linked
            with self.assertRaisesMessage(ValueError, "trades/invoices"):
                with self.captureOnCommitCallbacks(execute=True):
                    boe_service.merge_boe(target, source.id, user=self.user)
            self.assertTrue(BillOfEntryModel.objects.filter(pk=linked.pk).exists())
            self.assertTrue(trade.boes.filter(pk=linked.pk).exists())

    def test_merge_refreshes_allotment_targets_exactly_once(self):
        from unittest import mock

        target = self.make_boe(self.company)
        source = self.make_boe(self.company)
        allotment = self.make_allotment(self.company, item=self.item_a, cif_fc=Decimal("500.00"))
        source.allotment.add(allotment)
        with mock.patch("apps.license.signals._refresh_balances_for_allotments") as signal_refresh, \
                mock.patch("apps.bill_of_entry.services.boe_service._refresh_licenses") as merge_refresh:
            self._merge(target, source.id)

        signal_refresh.assert_not_called()
        self.assertEqual(merge_refresh.call_count, 1)
