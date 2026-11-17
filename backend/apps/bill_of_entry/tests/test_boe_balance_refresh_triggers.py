"""
Iteration 2 / A4 — stored-balance refresh TRIGGERS for BOE writes.

Owner decisions:
  * D5  — moving a RowDetails row between licence items / licences must refresh
          the OLD and NEW item and the OLD and NEW licence (captured before
          the save), with no duplicate refresh when the relationship is
          unchanged, and item refreshes deferred to transaction.on_commit.
  * D12 — linking/unlinking/clearing BillOfEntryModel.allotment (M2M) must
          refresh the stored balances that depend on the BOE-allotment link
          (allotment items' stored allotted/available fields and their
          licences' stored balance_cif).

Only refresh TRIGGERS are under test: the balance math itself
(calculate_balance.update_balance_values, LicenseBalanceCalculator,
update_license_flags) is frozen and is used here as the oracle — after every
trigger the STORED figure must equal the LIVE figure.
"""
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.db.models.signals import post_delete, post_save, pre_save
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import (
    RowDetails, capture_previous_row_relationship, delete_stock, update_stock,
)
from apps.bill_of_entry.tests.test_boe_api_contract import (
    LOCMEM_CACHES, BoeApiFixtureMixin, boe_detail_url,
)
from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator


def _stored_balance(license_obj):
    license_obj.refresh_from_db()
    if getattr(license_obj, "balance", None) is not None:
        license_obj.balance.refresh_from_db()
    return license_obj.balance_cif


def _live_balance(license_obj):
    return LicenseBalanceCalculator.calculate_financial_balance(license_obj)


@override_settings(CACHES=LOCMEM_CACHES)
class RowMoveRefreshTests(BoeApiFixtureMixin, TestCase):
    """D5 — RowDetails.sr_number change refreshes old AND new item/licence."""

    def setUp(self):
        self.company = self.make_company()
        self.license_1 = self.make_license(self.company)
        self.license_2 = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=self.license_1, cif_fc=Decimal("10000.00"))
        LicenseExportItemModel.objects.create(license=self.license_2, cif_fc=Decimal("10000.00"))
        self.item_a = self.make_item(self.license_1, 1)
        self.item_b = self.make_item(self.license_1, 2)
        self.item_c = self.make_item(self.license_2, 1)
        self.boe = self.make_boe(self.company)
        with self.captureOnCommitCallbacks(execute=True):
            self.row = self.make_debit_row(self.boe, self.item_a, cif_fc=Decimal("500.00"), qty=Decimal("50.000"))

    def _move_row(self, new_item):
        row = RowDetails.objects.get(pk=self.row.pk)
        row.sr_number = new_item
        with self.captureOnCommitCallbacks(execute=True):
            row.save()
        return row

    def test_baseline_debit_is_stored_on_the_original_item_and_licence(self):
        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.debited_value, Decimal("500.00"))
        self.assertEqual(_stored_balance(self.license_1), Decimal("9500.00"))
        self.assertEqual(_stored_balance(self.license_1), _live_balance(self.license_1))

    def test_move_within_licence_refreshes_old_and_new_item(self):
        self._move_row(self.item_b)

        self.item_a.refresh_from_db()
        self.item_b.refresh_from_db()
        self.assertEqual(self.item_b.debited_value, Decimal("500.00"))
        self.assertEqual(self.item_b.debited_quantity, Decimal("50.000"))
        # D5: the OLD item no longer carries the moved debit.
        self.assertEqual(self.item_a.debited_value, Decimal("0.00"))
        self.assertEqual(self.item_a.debited_quantity, Decimal("0.000"))
        # Same licence: balance unchanged and consistent with the live figure.
        self.assertEqual(_stored_balance(self.license_1), Decimal("9500.00"))
        self.assertEqual(_stored_balance(self.license_1), _live_balance(self.license_1))

    def test_move_across_licences_refreshes_old_and_new_licence(self):
        self._move_row(self.item_c)

        self.item_a.refresh_from_db()
        self.item_c.refresh_from_db()
        self.assertEqual(self.item_c.debited_value, Decimal("500.00"))
        self.assertEqual(self.item_a.debited_value, Decimal("0.00"))
        self.assertEqual(_live_balance(self.license_1), Decimal("10000.00"))
        self.assertEqual(_live_balance(self.license_2), Decimal("9500.00"))
        self.assertEqual(_stored_balance(self.license_2), Decimal("9500.00"))
        # D5: the OLD licence's stored balance gets its debit back.
        self.assertEqual(_stored_balance(self.license_1), Decimal("10000.00"))

    def test_move_via_bulk_patch_api_refreshes_old_licence(self):
        user = self.make_role_user("BOE_MANAGER")
        client = self.client_for(user)
        with self.captureOnCommitCallbacks(execute=True):
            response = client.patch(boe_detail_url(self.boe.id), {
                "item_details": [self.row_payload(self.item_c, Decimal("500.00"), Decimal("50.000"), row_id=self.row.id)],
            }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(RowDetails.objects.get(pk=self.row.pk).sr_number_id, self.item_c.id)

        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.debited_value, Decimal("0.00"))
        self.assertEqual(_stored_balance(self.license_1), _live_balance(self.license_1))
        self.assertEqual(_stored_balance(self.license_2), _live_balance(self.license_2))

    def test_unchanged_relationship_refreshes_item_and_licence_once(self):
        row = RowDetails.objects.get(pk=self.row.pk)
        row.cif_fc = Decimal("600.00")
        with mock.patch("apps.bill_of_entry.models._update_balance_sync") as item_refresh, \
                mock.patch("apps.license.signals.update_license_flags") as licence_refresh:
            with self.captureOnCommitCallbacks(execute=True):
                row.save()
        self.assertEqual([c.args for c in item_refresh.call_args_list], [(self.item_a.id,)])
        self.assertEqual(licence_refresh.call_count, 1)
        self.assertEqual(licence_refresh.call_args.args[0].pk, self.license_1.pk)

    def test_move_within_licence_refreshes_licence_once_and_both_items(self):
        row = RowDetails.objects.get(pk=self.row.pk)
        row.sr_number = self.item_b
        with mock.patch("apps.bill_of_entry.models._update_balance_sync") as item_refresh, \
                mock.patch("apps.license.signals.update_license_flags") as licence_refresh:
            with self.captureOnCommitCallbacks(execute=True):
                row.save()
        self.assertEqual(sorted(c.args[0] for c in item_refresh.call_args_list), sorted([self.item_a.id, self.item_b.id]))
        self.assertEqual([c.args[0].pk for c in licence_refresh.call_args_list], [self.license_1.pk])

    def test_move_across_licences_refreshes_each_licence_once(self):
        row = RowDetails.objects.get(pk=self.row.pk)
        row.sr_number = self.item_c
        with mock.patch("apps.bill_of_entry.models._update_balance_sync") as item_refresh, \
                mock.patch("apps.license.signals.update_license_flags") as licence_refresh:
            with self.captureOnCommitCallbacks(execute=True):
                row.save()
        self.assertEqual(sorted(c.args[0] for c in item_refresh.call_args_list), sorted([self.item_a.id, self.item_c.id]))
        self.assertEqual(
            sorted(c.args[0].pk for c in licence_refresh.call_args_list),
            sorted([self.license_1.pk, self.license_2.pk]),
        )

    def test_item_refresh_waits_for_commit(self):
        row = RowDetails.objects.get(pk=self.row.pk)
        row.sr_number = self.item_b
        with mock.patch("apps.bill_of_entry.models._update_balance_sync") as item_refresh:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                row.save()
            self.assertEqual(item_refresh.call_count, 0)
            for callback in callbacks:
                callback()
        self.assertEqual(sorted(c.args[0] for c in item_refresh.call_args_list), sorted([self.item_a.id, self.item_b.id]))

    def test_update_fields_without_sr_number_skips_old_relationship_lookup(self):
        def _count_queries(save):
            row = RowDetails.objects.get(pk=self.row.pk)
            row.cif_fc = Decimal("600.00")
            with CaptureQueriesContext(connection) as ctx:
                save(row)
            return len(ctx.captured_queries)

        _count_queries(lambda r: r.save(update_fields=["cif_fc"]))  # warm caches
        partial = _count_queries(lambda r: r.save(update_fields=["cif_fc"]))
        self.assertTrue(pre_save.disconnect(sender=RowDetails, dispatch_uid="capture_previous_row_relationship"))
        try:
            partial_without_capture = _count_queries(lambda r: r.save(update_fields=["cif_fc"]))
        finally:
            pre_save.connect(capture_previous_row_relationship, sender=RowDetails,
                             dispatch_uid="capture_previous_row_relationship")
        self.assertEqual(partial, partial_without_capture)
        # A full save does pay exactly one extra lookup for the old relationship.
        full = _count_queries(lambda r: r.save())
        self.assertEqual(full, partial + 1)

    def test_parse_ledger_disconnect_convention_still_suppresses_item_refresh(self):
        # backend/scripts/parse_ledger.py disconnects exactly like this.
        self.assertTrue(post_save.disconnect(update_stock, sender=RowDetails, dispatch_uid="update_stock_on_save"))
        self.assertTrue(post_delete.disconnect(delete_stock, sender=RowDetails))
        try:
            row = RowDetails.objects.get(pk=self.row.pk)
            row.sr_number = self.item_b
            with mock.patch("apps.bill_of_entry.models._update_balance_sync") as item_refresh:
                with self.captureOnCommitCallbacks(execute=True):
                    row.save()
                    row.delete()
            self.assertEqual(item_refresh.call_count, 0)
        finally:
            post_save.connect(update_stock, sender=RowDetails, dispatch_uid="update_stock_on_save")
            post_delete.connect(delete_stock, sender=RowDetails)

    def test_delete_still_refreshes_item_and_licence(self):
        row = RowDetails.objects.get(pk=self.row.pk)
        with self.captureOnCommitCallbacks(execute=True):
            row.delete()
        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.debited_value, Decimal("0.00"))
        self.assertEqual(_stored_balance(self.license_1), Decimal("10000.00"))


@override_settings(CACHES=LOCMEM_CACHES)
class BoeAllotmentLinkRefreshTests(BoeApiFixtureMixin, TestCase):
    """D12 — BillOfEntryModel.allotment M2M changes refresh dependent stored balances."""

    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("10000.00"))
        self.item = self.make_item(self.license, 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.allotment = self.make_allotment(self.company, item=self.item, cif_fc=Decimal("2000.00"))
        self.allotment_item = AllotmentItems.objects.get(allotment=self.allotment)
        self.boe = self.make_boe(self.company)

    def _assert_consistent(self, expected_balance, expected_allotted_value):
        self.item.refresh_from_db()
        self.assertEqual(_live_balance(self.license), expected_balance)
        self.assertEqual(_stored_balance(self.license), expected_balance)
        self.assertEqual(self.item.allotted_value, expected_allotted_value)

    def test_baseline_unlinked_allotment_reserves_balance(self):
        self._assert_consistent(Decimal("8000.00"), Decimal("2000.00"))

    def test_link_refreshes_stored_balances(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.boe.allotment.add(self.allotment)
        # A BOE-linked allotment no longer reserves CIF (Balance Engine rule).
        self._assert_consistent(Decimal("10000.00"), Decimal("0.00"))

    def test_unlink_refreshes_stored_balances(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.boe.allotment.add(self.allotment)
        with self.captureOnCommitCallbacks(execute=True):
            self.boe.allotment.remove(self.allotment)
        self._assert_consistent(Decimal("8000.00"), Decimal("2000.00"))

    def test_clear_refreshes_previously_linked_allotments(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.boe.allotment.add(self.allotment)
        with self.captureOnCommitCallbacks(execute=True):
            self.boe.allotment.clear()
        self._assert_consistent(Decimal("8000.00"), Decimal("2000.00"))

    def test_reverse_side_link_refreshes_stored_balances(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.allotment.bill_of_entry.add(self.boe)
        self._assert_consistent(Decimal("10000.00"), Decimal("0.00"))

    def test_reverse_side_clear_refreshes_stored_balances(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.allotment.bill_of_entry.add(self.boe)
        with self.captureOnCommitCallbacks(execute=True):
            self.allotment.bill_of_entry.clear()
        self._assert_consistent(Decimal("8000.00"), Decimal("2000.00"))

    def test_link_via_patch_api_refreshes_stored_balances(self):
        client = self.client_for(self.make_role_user("BOE_MANAGER"))
        with self.captureOnCommitCallbacks(execute=True):
            response = client.patch(boe_detail_url(self.boe.id), {"allotment": [self.allotment.id]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self._assert_consistent(Decimal("10000.00"), Decimal("0.00"))

    def test_link_refresh_waits_for_commit_and_dedupes(self):
        with mock.patch("apps.license.signals.update_license_flags") as licence_refresh, \
                mock.patch("apps.core.scripts.calculate_balance.update_balance_values") as item_refresh:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                self.boe.allotment.add(self.allotment)
            self.assertEqual(licence_refresh.call_count, 0)
            self.assertEqual(item_refresh.call_count, 0)
            for callback in callbacks:
                callback()
        self.assertEqual([c.args[0].pk for c in licence_refresh.call_args_list], [self.license.pk])
        self.assertEqual([c.args[0].pk for c in item_refresh.call_args_list], [self.item.pk])

    def test_noop_m2m_actions_do_not_refresh(self):
        with mock.patch("apps.license.signals.update_license_flags") as licence_refresh:
            with self.captureOnCommitCallbacks(execute=True):
                self.boe.allotment.clear()        # nothing linked
                self.boe.allotment.add()          # empty add
        self.assertEqual(licence_refresh.call_count, 0)


    def test_deleting_linked_boe_refreshes_allotment_balances(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.boe.allotment.add(self.allotment)
        with mock.patch("apps.license.signals._refresh_balances_for_allotments") as refresh:
            with self.captureOnCommitCallbacks(execute=True):
                self.boe.delete()
        refresh.assert_called_once_with({self.allotment.pk})

    def test_deleting_linked_boe_restores_stored_balance(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.boe.allotment.add(self.allotment)
        linked_balance = _stored_balance(self.license)
        with self.captureOnCommitCallbacks(execute=True):
            self.boe.delete()
        self.assertEqual(_stored_balance(self.license), _live_balance(self.license))
        self.assertLess(_stored_balance(self.license), linked_balance)

    def test_deleting_unlinked_boe_schedules_nothing(self):
        with mock.patch("apps.license.signals._refresh_balances_for_allotments") as refresh:
            with self.captureOnCommitCallbacks(execute=True):
                self.boe.delete()
        refresh.assert_not_called()
