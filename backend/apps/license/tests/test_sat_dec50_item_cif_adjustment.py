"""
SAT DEC-50 D / C-3 A / G1 (owner 2026-11-20): an item's realised CIF over-use is
covered by unused CIF of any other attributed item on the same licence. Total
licence CIF preserved, no entitlement created, CIF only, deterministic order,
remaining over-use flagged. Hand-computed Decimal expectations.
"""
from decimal import Decimal

from django.test import TestCase

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import (
    ItemBalanceCalculator as IBC,
    LicenseBalanceCalculator as LBC,
)
from apps.license.services.item_cif_adjustment import CifTransfer, compute_item_cif_adjustments
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin

D = Decimal


class Dec50AdjustmentTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.lic = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=self.lic, cif_fc=D("150.00"))

    def _item(self, serial, cif):
        item = self.make_item(self.lic, serial)
        item.cif_fc = cif
        item.save(update_fields=["cif_fc"])
        return item

    def _debit(self, item, cif):
        self.make_debit_row(self.make_boe(self.company), item, cif)

    def _allot(self, item, cif):
        a = AllotmentModel.objects.create(company=self.company, item_name="x")
        AllotmentItems.objects.create(item=item, allotment=a, cif_fc=cif, cif_inr=cif, qty=D("1.000"))

    def _attributed(self, *items):
        bulk = IBC.calculate_item_attributed_balances_for_items(list(items))
        single = {i.id: IBC.calculate_item_attributed_balance(i) for i in items}
        self.assertEqual(bulk, single)
        return single

    def test_over_use_covered_by_sibling_surplus(self):
        a, b = self._item(1, D("50.00")), self._item(2, D("50.00"))
        self._debit(a, D("70.00"))
        res = compute_item_cif_adjustments([self.lic.id])
        self.assertEqual(res.transfers, [CifTransfer(self.lic.id, b.id, a.id, D("20.00"))])
        self.assertEqual(res.for_item(a.id).uncovered, D("0"))
        bal = self._attributed(a, b)
        self.assertEqual((bal[a.id], bal[b.id]), (D("0.00"), D("30.00")))
        # total preserved: licence balance (150 − 70) unchanged by the adjustment
        self.assertEqual(LBC.calculate_balance(self.lic), D("80.00"))

    def test_insufficient_surplus_leaves_uncovered_over_use(self):
        a, b = self._item(1, D("50.00")), self._item(2, D("50.00"))
        self._debit(a, D("90.00"))
        self._debit(b, D("30.00"))
        self._allot(b, D("10.00"))  # donor's own reservation is not given away
        res = compute_item_cif_adjustments([self.lic.id])
        self.assertEqual(res.transfers, [CifTransfer(self.lic.id, b.id, a.id, D("10.00"))])
        self.assertEqual(res.for_item(a.id).uncovered, D("30.00"))
        bal = self._attributed(a, b)
        self.assertEqual((bal[a.id], bal[b.id]), (D("0"), D("0.00")))

    def test_outstanding_allotment_over_use_is_not_covered(self):
        a, b = self._item(1, D("50.00")), self._item(2, D("50.00"))
        self._debit(a, D("50.00"))
        self._allot(a, D("20.00"))
        self.assertEqual(compute_item_cif_adjustments([self.lic.id]).transfers, [])

    def test_largest_donor_first_then_next(self):
        a, b, c = self._item(1, D("50.00")), self._item(2, D("30.00")), self._item(3, D("40.00"))
        self._debit(a, D("110.00"))  # over-use 60
        res = compute_item_cif_adjustments([self.lic.id])
        self.assertEqual(res.transfers, [
            CifTransfer(self.lic.id, c.id, a.id, D("40.00")),
            CifTransfer(self.lic.id, b.id, a.id, D("20.00")),
        ])
        self.assertEqual(sum(t.amount for t in res.transfers), D("60.00"))

    def test_shared_ceiling_items_and_other_licences_do_not_take_part(self):
        a = self._item(1, D("50.00"))
        self.make_item(self.lic, 2)  # cif_fc 0 → not attributed
        other_lic = self.make_license(self.company)
        other = self.make_item(other_lic, 1)
        other.cif_fc = D("500.00")
        other.save(update_fields=["cif_fc"])
        self._debit(a, D("60.00"))
        res = compute_item_cif_adjustments([self.lic.id, other_lic.id])
        self.assertEqual(res.transfers, [])
        self.assertEqual(res.for_item(a.id).uncovered, D("10.00"))


class Dec50AuditTrailTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.lic = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=self.lic, cif_fc=D("100.00"))
        self.a = self.make_item(self.lic, 1)
        self.b = self.make_item(self.lic, 2)
        for item in (self.a, self.b):
            item.cif_fc = D("50.00")
            item.save(update_fields=["cif_fc"])

    def test_dry_run_writes_nothing_then_apply_records_and_is_idempotent(self):
        from apps.reconciliation.models import ItemCifAdjustmentRecord
        from apps.reconciliation.services.item_cif_adjustment_log import refresh_item_cif_adjustment_log

        self.make_debit_row(self.make_boe(self.company), self.a, D("70.00"))
        dry = refresh_item_cif_adjustment_log([self.lic.id])
        self.assertEqual((dry["transfers"], ItemCifAdjustmentRecord.objects.count()), (1, 0))
        applied = refresh_item_cif_adjustment_log([self.lic.id], dry_run=False)
        rec = ItemCifAdjustmentRecord.objects.get()
        self.assertEqual(
            (rec.batch_id, rec.source_item_id, rec.destination_item_id, rec.amount_cif_fc),
            (applied["batch_id"], self.b.id, self.a.id, D("20.00")),
        )
        again = refresh_item_cif_adjustment_log([self.lic.id], dry_run=False)
        self.assertEqual((again["transfers"], ItemCifAdjustmentRecord.objects.count()), (0, 1))

    def test_change_back_to_none_appends_marker_and_keeps_history(self):
        from apps.bill_of_entry.models import RowDetails
        from apps.reconciliation.models import ItemCifAdjustmentRecord
        from apps.reconciliation.services.item_cif_adjustment_log import refresh_item_cif_adjustment_log

        row = self.make_debit_row(self.make_boe(self.company), self.a, D("70.00"))
        refresh_item_cif_adjustment_log([self.lic.id], dry_run=False)
        RowDetails.objects.filter(pk=row.pk).update(cif_fc=D("40.00"))
        refresh_item_cif_adjustment_log([self.lic.id], dry_run=False)
        self.assertEqual(ItemCifAdjustmentRecord.objects.count(), 2)
        marker = ItemCifAdjustmentRecord.objects.order_by("-id").first()
        self.assertIsNone(marker.source_item_id)

    def test_no_adjustment_no_history_writes_nothing(self):
        from apps.reconciliation.models import ItemCifAdjustmentRecord
        from apps.reconciliation.services.item_cif_adjustment_log import refresh_item_cif_adjustment_log

        refresh_item_cif_adjustment_log([self.lic.id], dry_run=False)
        self.assertEqual(ItemCifAdjustmentRecord.objects.count(), 0)


class Dec50AutomaticAuditTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """Owner F3 (2026-11-20): audit rows are written automatically, once per
    transaction, when DEC-50 inputs change."""

    def setUp(self):
        # Flush the fixture's own audit callbacks (one flush per transaction).
        with self.captureOnCommitCallbacks(execute=True):
            self.company = self.make_company()
            self.lic = self.make_license(self.company)
            LicenseExportItemModel.objects.create(license=self.lic, cif_fc=D("100.00"))
            self.a = self.make_item(self.lic, 1)
            self.b = self.make_item(self.lic, 2)
            for item in (self.a, self.b):
                item.cif_fc = D("50.00")
                item.save(update_fields=["cif_fc"])

    def _records(self):
        from apps.reconciliation.models import ItemCifAdjustmentRecord
        return list(ItemCifAdjustmentRecord.objects.order_by("id").values_list(
            "source_item_id", "destination_item_id", "amount_cif_fc"))

    def test_new_boe_row_records_transfer_once_per_transaction(self):
        from apps.reconciliation.models import ItemCifAdjustmentRecord

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.make_debit_row(self.make_boe(self.company), self.a, D("60.00"))
            self.make_debit_row(self.make_boe(self.company), self.a, D("10.00"))  # 2nd change, same txn
        flushes = [c for c in callbacks if getattr(c, "__name__", "") == "_flush"]
        self.assertEqual(len(flushes), 1)
        self.assertEqual(self._records(), [(self.b.id, self.a.id, D("20.00"))])
        self.assertEqual(ItemCifAdjustmentRecord.objects.values("batch_id").distinct().count(), 1)

    def test_allotment_on_donor_changes_recorded_set(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.make_debit_row(self.make_boe(self.company), self.a, D("70.00"))
        with self.captureOnCommitCallbacks(execute=True):
            al = AllotmentModel.objects.create(company=self.company, item_name="x")
            AllotmentItems.objects.create(item=self.b, allotment=al, cif_fc=D("40.00"), cif_inr=D("1"), qty=D("1.000"))
        # donor b now has 50 − 40 = 10 unused → transfer 10, uncovered 10
        recs = self._records()
        self.assertEqual(recs[-1], (self.b.id, self.a.id, D("10.00")))
        self.assertEqual(len(recs), 2)  # history kept, append-only

    def test_rolled_back_change_does_not_block_later_audit(self):
        from django.db import transaction

        try:
            with transaction.atomic():
                self.make_debit_row(self.make_boe(self.company), self.a, D("70.00"))
                raise RuntimeError("rollback")
        except RuntimeError:
            pass
        with self.captureOnCommitCallbacks(execute=True):
            self.make_debit_row(self.make_boe(self.company), self.a, D("65.00"))
        self.assertEqual(self._records(), [(self.b.id, self.a.id, D("15.00"))])

    def test_setting_disables_automatic_audit(self):
        from django.test import override_settings

        with override_settings(ITEM_CIF_ADJUSTMENT_AUDIT_ON_CHANGE=False), self.captureOnCommitCallbacks(execute=True):
            self.make_debit_row(self.make_boe(self.company), self.a, D("70.00"))
        self.assertEqual(self._records(), [])
