"""
Owner decision D4 (2026-11-17): BOE merge integrity.

  A. exactly one BOE has frozen (ledger) rows -> it survives regardless of the
     argument order; frozen rows are never deleted/modified;
  B. both frozen -> both frozen sets preserved when no frozen row would be
     dropped as a duplicate, else rejected with a clear error;
  C. neither frozen -> existing rules (requested target survives).

Plus, for every case: hidden-state compatibility, duplicate-merge prevention
(idempotent re-run), exchange-rate persistence, audit payload, and refresh of
every affected licence/item via the existing helpers on commit.  Each case is
exercised in BOTH input orders.
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails, genuinely_hidden_boe_ids
from apps.bill_of_entry.services import boe_service
from apps.bill_of_entry.services.boe_service import hide_boe
from apps.bill_of_entry.tests.test_boe_api_contract import (
    LOCMEM_CACHES, BoeApiFixtureMixin, boe_detail_url,
)
from apps.core.constants import DEBIT
from apps.license.models import LicenseBalance, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.reconciliation.models import ReconciliationLog

ROW_FIELDS = ("id", "bill_of_entry_id", "sr_number_id", "transaction_type", "cif_fc", "cif_inr", "qty", "is_frozen")


def _row_state(row_ids):
    return {
        row["id"]: row
        for row in RowDetails.objects.filter(id__in=row_ids).values(*ROW_FIELDS)
    }


@override_settings(CACHES=LOCMEM_CACHES)
class MergeFrozenPriorityTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.license_2 = self.make_license(self.company)
        self.items = [self.make_item(self.license, n) for n in (1, 2, 3)]
        self.other_item = self.make_item(self.license_2, 1)
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("10000.00"))
        LicenseExportItemModel.objects.create(license=self.license_2, cif_fc=Decimal("5000.00"))
        self.user = self.make_role_user("BOE_MANAGER", "TRADE_MANAGER")

    # -- helpers -----------------------------------------------------------
    def _frozen_row(self, boe, item, cif_fc):
        row = self.make_debit_row(boe, item, cif_fc=cif_fc)
        RowDetails.objects.filter(pk=row.pk).update(is_frozen=True)
        return row

    def _merge(self, target, source_id):
        with self.captureOnCommitCallbacks(execute=True):
            return boe_service.merge_boe(target, source_id, user=self.user)

    def _logs(self):
        return ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_MERGE_BOE)

    def _frozen_and_plain(self):
        frozen_boe = self.make_boe(self.company)
        plain_boe = self.make_boe(self.company)
        frozen_rows = [
            self._frozen_row(frozen_boe, self.items[0], Decimal("100.00")),
            self._frozen_row(frozen_boe, self.items[1], Decimal("200.00")),
        ]
        duplicate = self.make_debit_row(plain_boe, self.items[0], cif_fc=Decimal("999.00"))
        movable = self.make_debit_row(plain_boe, self.items[2], cif_fc=Decimal("300.00"))
        return frozen_boe, plain_boe, frozen_rows, duplicate, movable

    # -- A: exactly one frozen ----------------------------------------------
    def _assert_case_a(self, result, frozen_boe, plain_boe, frozen_rows, frozen_before, duplicate, movable):
        self.assertEqual(result["target_boe_id"], frozen_boe.id)
        self.assertEqual(result["boe"]["id"], frozen_boe.id)
        self.assertTrue(BillOfEntryModel.objects.filter(id=frozen_boe.id).exists())
        self.assertFalse(BillOfEntryModel.objects.filter(id=plain_boe.id).exists())
        # Frozen rows: same ids, same values, same BOE.
        self.assertEqual(_row_state([r.id for r in frozen_rows]), frozen_before)
        # Eligible row moved in; the plain duplicate of a frozen item is dropped.
        self.assertEqual(RowDetails.objects.get(id=movable.id).bill_of_entry_id, frozen_boe.id)
        self.assertFalse(RowDetails.objects.filter(id=duplicate.id).exists())
        self.assertEqual(self._logs().count(), 1)
        log = self._logs().get()
        self.assertEqual(log.bill_of_entry_id, frozen_boe.id)
        self.assertEqual(log.after["moved_row_ids"], [movable.id])
        self.assertEqual(log.after["skipped_row_ids"], [duplicate.id])
        self.assertEqual(log.before["surviving_boe_id"], frozen_boe.id)
        self.assertEqual(log.before["removed_boe_id"], plain_boe.id)

    def test_a_frozen_target_survives_without_swap(self):
        frozen_boe, plain_boe, frozen_rows, duplicate, movable = self._frozen_and_plain()
        frozen_before = _row_state([r.id for r in frozen_rows])

        result = self._merge(frozen_boe, plain_boe.id)

        self.assertFalse(result["swapped"])
        self._assert_case_a(result, frozen_boe, plain_boe, frozen_rows, frozen_before, duplicate, movable)
        log = self._logs().get()
        self.assertFalse(log.before["swapped"])
        self.assertEqual(log.before["target_boe_id"], frozen_boe.id)
        self.assertEqual(log.before["source_boe_id"], plain_boe.id)

    def test_a_frozen_source_becomes_survivor_with_swap(self):
        frozen_boe, plain_boe, frozen_rows, duplicate, movable = self._frozen_and_plain()
        frozen_before = _row_state([r.id for r in frozen_rows])

        result = self._merge(plain_boe, frozen_boe.id)

        self.assertTrue(result["swapped"])
        self._assert_case_a(result, frozen_boe, plain_boe, frozen_rows, frozen_before, duplicate, movable)
        log = self._logs().get()
        self.assertTrue(log.before["swapped"])
        self.assertTrue(log.after["swapped"])
        # The requested ids are kept verbatim in the audit.
        self.assertEqual(log.before["target_boe_id"], plain_boe.id)
        self.assertEqual(log.before["source_boe_id"], frozen_boe.id)
        self.assertEqual(log.before["removed_boe"]["id"], plain_boe.id)
        self.assertEqual(log.before["removed_boe"]["bill_of_entry_number"], plain_boe.bill_of_entry_number)

    def test_a_swap_keeps_requested_source_port_rule(self):
        """The survivor takes the requested source's port (unchanged rule);
        on a swap the survivor IS the requested source, so its port stays."""
        frozen_boe, plain_boe, *_ = self._frozen_and_plain()
        BillOfEntryModel.objects.filter(pk=frozen_boe.pk).update(port=self.make_port())
        frozen_port = BillOfEntryModel.objects.get(pk=frozen_boe.pk).port_id
        BillOfEntryModel.objects.filter(pk=plain_boe.pk).update(port=self.make_port())

        self._merge(plain_boe, frozen_boe.id)

        self.assertEqual(BillOfEntryModel.objects.get(pk=frozen_boe.pk).port_id, frozen_port)

    def test_a_swap_via_boe_endpoint(self):
        frozen_boe, plain_boe, frozen_rows, *_ = self._frozen_and_plain()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client_for(self.user).post(
                boe_detail_url(plain_boe.id, "merge/"), {"source_boe_id": frozen_boe.id}, format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["swapped"])
        self.assertEqual(response.data["target_boe_id"], frozen_boe.id)
        self.assertEqual(response.data["boe"]["id"], frozen_boe.id)

    def test_a_swap_via_reconciliation_endpoint(self):
        frozen_boe, plain_boe, *_ = self._frozen_and_plain()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client_for(self.user).post(
                reverse("reconciliation:reconciliation-merge-boe"),
                {"target_boe_id": plain_boe.id, "source_boe_id": frozen_boe.id}, format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["swapped"])
        self.assertEqual(response.data["target_boe_id"], frozen_boe.id)

    def test_a_swap_rejected_when_removed_target_has_trade_links(self):
        frozen_boe, plain_boe, frozen_rows, duplicate, movable = self._frozen_and_plain()
        trade = self.make_purchase_trade(self.company, self.items[2], cif_fc=Decimal("10.00"))
        trade.boes.add(plain_boe)
        before = _row_state([duplicate.id, movable.id] + [r.id for r in frozen_rows])

        with self.assertRaisesMessage(ValueError, "trades/invoices"):
            self._merge(plain_boe, frozen_boe.id)

        self.assertEqual(_row_state(list(before)), before)
        self.assertTrue(BillOfEntryModel.objects.filter(id=plain_boe.id).exists())
        self.assertFalse(self._logs().exists())

    # -- B: both frozen -----------------------------------------------------
    def _both_frozen(self, overlapping):
        first = self.make_boe(self.company)
        second = self.make_boe(self.company)
        rows = [
            self._frozen_row(first, self.items[0], Decimal("100.00")),
            self._frozen_row(second, self.items[0] if overlapping else self.items[1], Decimal("200.00")),
            self.make_debit_row(second, self.items[2], cif_fc=Decimal("50.00")),
        ]
        return first, second, rows

    def _assert_case_b_preserved(self, target, source, rows):
        before = _row_state([r.id for r in rows])

        result = self._merge(target, source.id)

        self.assertFalse(result["swapped"])
        self.assertEqual(result["target_boe_id"], target.id)
        self.assertFalse(BillOfEntryModel.objects.filter(id=source.id).exists())
        after = _row_state([r.id for r in rows])
        self.assertEqual(set(after), set(before))  # nothing deleted
        for row_id, state in before.items():
            moved = dict(state, bill_of_entry_id=target.id)
            self.assertEqual(after[row_id], moved)  # only the BOE FK changed
        self.assertEqual(RowDetails.objects.filter(bill_of_entry=target, is_frozen=True).count(), 2)

    def test_b_both_frozen_disjoint_preserved_first_into_second(self):
        first, second, rows = self._both_frozen(overlapping=False)
        self._assert_case_b_preserved(second, first, rows)

    def test_b_both_frozen_disjoint_preserved_second_into_first(self):
        first, second, rows = self._both_frozen(overlapping=False)
        self._assert_case_b_preserved(first, second, rows)

    def _assert_case_b_rejected(self, target, source, rows):
        before = _row_state([r.id for r in rows])

        with self.assertRaisesMessage(ValueError, "frozen"):
            self._merge(target, source.id)

        self.assertEqual(_row_state([r.id for r in rows]), before)
        self.assertTrue(BillOfEntryModel.objects.filter(id=source.id).exists())
        self.assertTrue(BillOfEntryModel.objects.filter(id=target.id).exists())
        self.assertFalse(self._logs().exists())

    def test_b_both_frozen_overlapping_rejected_first_into_second(self):
        first, second, rows = self._both_frozen(overlapping=True)
        self._assert_case_b_rejected(second, first, rows)

    def test_b_both_frozen_overlapping_rejected_second_into_first(self):
        first, second, rows = self._both_frozen(overlapping=True)
        self._assert_case_b_rejected(first, second, rows)

    def test_b_rejection_is_400_on_boe_endpoint(self):
        first, second, rows = self._both_frozen(overlapping=True)

        response = self.client_for(self.user).post(
            boe_detail_url(first.id, "merge/"), {"source_boe_id": second.id}, format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(list(response.data.keys()), ["error"])
        self.assertIn(str(rows[1].id), response.data["error"])

    # -- C: neither frozen --------------------------------------------------
    def _plain_pair(self):
        first = self.make_boe(self.company)
        second = self.make_boe(self.company)
        first_row = self.make_debit_row(first, self.items[0], cif_fc=Decimal("100.00"))
        second_row = self.make_debit_row(second, self.items[1], cif_fc=Decimal("200.00"))
        return first, second, first_row, second_row

    def test_c_neither_frozen_requested_target_survives_first_into_second(self):
        first, second, first_row, second_row = self._plain_pair()

        result = self._merge(second, first.id)

        self.assertFalse(result["swapped"])
        self.assertEqual(result["target_boe_id"], second.id)
        self.assertFalse(BillOfEntryModel.objects.filter(id=first.id).exists())
        self.assertEqual(RowDetails.objects.get(id=first_row.id).bill_of_entry_id, second.id)

    def test_c_neither_frozen_requested_target_survives_second_into_first(self):
        first, second, first_row, second_row = self._plain_pair()

        result = self._merge(first, second.id)

        self.assertFalse(result["swapped"])
        self.assertEqual(result["target_boe_id"], first.id)
        self.assertFalse(BillOfEntryModel.objects.filter(id=second.id).exists())
        self.assertEqual(RowDetails.objects.get(id=second_row.id).bill_of_entry_id, first.id)

    # -- hidden-state compatibility ------------------------------------------
    def test_exactly_one_hidden_rejected_in_both_orders(self):
        hidden = self.make_boe(self.company)
        visible = self.make_boe(self.company)
        self.make_debit_row(hidden, self.items[0], cif_fc=Decimal("100.00"))
        self.make_debit_row(visible, self.items[1], cif_fc=Decimal("100.00"))
        hide_boe(hidden, user=None, reason="previous owner")

        for target, source in ((hidden, visible), (visible, hidden)):
            with self.assertRaisesMessage(ValueError, "exactly one of the two bills of entry is hidden"):
                self._merge(target, source.id)
        self.assertTrue(BillOfEntryModel.objects.filter(id__in=[hidden.id, visible.id]).count() == 2)
        self.assertFalse(self._logs().exists())

    def test_both_hidden_merge_allowed_and_survivor_stays_hidden(self):
        first = self.make_boe(self.company)
        second = self.make_boe(self.company)
        self.make_debit_row(first, self.items[0], cif_fc=Decimal("100.00"))
        self.make_debit_row(second, self.items[1], cif_fc=Decimal("100.00"))
        hide_boe(first, user=None, reason="h")
        hide_boe(second, user=None, reason="h")

        result = self._merge(first, second.id)

        self.assertEqual(result["target_boe_id"], first.id)
        self.assertIn(first.id, genuinely_hidden_boe_ids(boe_ids=[first.id]))

    # -- duplicate-merge prevention ------------------------------------------
    def test_rerun_after_merge_is_clean_error_and_does_not_move_twice(self):
        first, second, first_row, second_row = self._plain_pair()
        self._merge(first, second.id)
        rows_after = _row_state([first_row.id, second_row.id])

        with self.assertRaisesMessage(ValueError, "not found"):
            self._merge(first, second.id)

        self.assertEqual(_row_state([first_row.id, second_row.id]), rows_after)
        self.assertEqual(self._logs().count(), 1)

    def test_rerun_after_swapped_merge_is_clean_error(self):
        frozen_boe, plain_boe, *_ = self._frozen_and_plain()
        self._merge(plain_boe, frozen_boe.id)  # plain_boe (requested target) is removed

        with self.assertRaisesMessage(ValueError, "not found"):
            self._merge(plain_boe, frozen_boe.id)
        response = self.client_for(self.user).post(
            boe_detail_url(plain_boe.id, "merge/"), {"source_boe_id": frozen_boe.id}, format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self._logs().count(), 1)

    def test_same_id_and_invalid_ids_rejected(self):
        boe = self.make_boe(self.company)
        for bad in (boe.id, str(boe.id)):
            with self.assertRaisesMessage(ValueError, "itself"):
                self._merge(boe, bad)
        for bad in (None, "", "abc"):
            with self.assertRaises(ValueError):
                self._merge(boe, bad)
        self.assertFalse(self._logs().exists())

    # -- exchange rate + balances --------------------------------------------
    def test_swap_persists_exchange_rate_on_survivor(self):
        frozen_boe = self.make_boe(self.company)          # rows at 84.5
        plain_boe = self.make_boe(self.company)
        self._frozen_row(frozen_boe, self.items[0], Decimal("1000.00"))
        RowDetails.objects.create(                        # INR at 100.0
            bill_of_entry=plain_boe, sr_number=self.items[1], transaction_type=DEBIT,
            cif_fc=Decimal("1000.00"), cif_inr=Decimal("100000.00"), qty=Decimal("10.000"),
        )

        result = self._merge(plain_boe, frozen_boe.id)

        frozen_boe.refresh_from_db()
        self.assertEqual(frozen_boe.exchange_rate, Decimal("92.2500"))
        self.assertEqual(Decimal(str(result["boe"]["exchange_rate"])), Decimal("92.2500"))
        self.assertEqual(self._logs().get().after["exchange_rate"], "92.2500")

    def test_affected_licences_and_items_refreshed_after_swap(self):
        from apps.core.scripts.calculate_balance import update_balance_values
        from apps.license.signals import update_license_flags

        frozen_boe = self.make_boe(self.company)
        plain_boe = self.make_boe(self.company)
        self._frozen_row(frozen_boe, self.items[0], Decimal("100.00"))
        duplicate = self.make_debit_row(plain_boe, self.items[0], cif_fc=Decimal("400.00"))
        self.make_debit_row(plain_boe, self.other_item, cif_fc=Decimal("250.00"))
        for licence in (self.license, self.license_2):
            update_license_flags(licence)
        for item in (self.items[0], self.other_item):
            update_balance_values(LicenseImportItemsModel.objects.get(pk=item.pk))
        stale = Decimal("1.00")
        LicenseBalance.objects.filter(license_id__in=[self.license.pk, self.license_2.pk]).update(balance_cif=stale)
        LicenseImportItemsModel.objects.filter(pk__in=[self.items[0].pk, self.other_item.pk]).update(
            debited_value=Decimal("0"),
        )

        self._merge(plain_boe, frozen_boe.id)

        self.assertFalse(RowDetails.objects.filter(id=duplicate.id).exists())
        log = self._logs().get()
        self.assertEqual(log.after["refreshed_license_ids"], sorted([self.license.pk, self.license_2.pk]))
        for licence in (self.license, self.license_2):
            licence.refresh_from_db()
            self.assertNotEqual(licence.balance_cif, stale)
            self.assertEqual(licence.balance_cif, LicenseBalanceCalculator.calculate_financial_balance(licence))
        # licence 1 keeps only the frozen 100.00 debit (the 400.00 duplicate went
        # with the removed BOE); licence 2 keeps the moved 250.00 debit.
        self.assertEqual(self.license.balance_cif, Decimal("9900.00"))
        self.assertEqual(self.license_2.balance_cif, Decimal("4750.00"))
        for item in (self.items[0], self.other_item):
            refreshed = LicenseImportItemsModel.objects.get(pk=item.pk)
            self.assertGreater(refreshed.debited_value, Decimal("0"))
