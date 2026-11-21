"""
SAT WS1 financial invariants (owner WS1-finalization brief, 2026-11-20):
no double counting, no excess reservation, no incorrect release, AR/AT parity,
no commission purchase as a purchase, DEC-50 transfers net to zero and never
exceed donor surplus, and every transfer is auditable. Hand-computed Decimals.
"""
from datetime import datetime
from decimal import Decimal
import uuid

from django.test import TestCase

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import (
    ItemBalanceCalculator as IBC,
    LicenseBalanceCalculator as LBC,
)
from apps.license.services.item_cif_adjustment import compute_item_cif_adjustments
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin

D = Decimal


class WS1InvariantTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        with self.captureOnCommitCallbacks(execute=True):  # flush fixture audit callbacks
            self.company = self.make_company()
            self.lic = self.make_license(self.company)
            LicenseExportItemModel.objects.create(license=self.lic, cif_fc=D("1000.00"))
            self.item = self.make_item(self.lic, 1)

    def _allot(self, cif, type_="AT", status="CREATED", item=None):
        a = AllotmentModel.objects.create(company=self.company, item_name="inv", type=type_)
        ai = AllotmentItems.objects.create(item=item or self.item, allotment=a, cif_fc=cif, cif_inr=cif,
                                           qty=D("10.000"), status=status)
        return a, ai

    def _boe_row(self, cif):
        boe = self.make_boe(self.company)
        return boe, self.make_debit_row(boe, self.item, cif)

    def _components_bulk_equal_single(self):
        lid = self.lic.id
        self.assertEqual(LBC.calculate_allotment_for_licenses([lid]).get(lid, D("0")), LBC.calculate_allotment(self.lic))
        self.assertEqual(LBC.calculate_balance_for_licenses([lid])[lid], LBC.calculate_balance(self.lic))

    def test_each_cif_amount_in_exactly_one_bucket(self):
        from apps.reconciliation.services.allocation_service import create_boe_allotment_allocation

        linked, _ = self._allot(D("100.00"))
        boe1, _ = self._boe_row(D("90.00"))
        boe1.allotment.add(linked)                       # M2M with rows → BOE only (90)
        _, formal = self._allot(D("80.00"))
        _, row2 = self._boe_row(D("30.00"))
        create_boe_allotment_allocation(row2, formal, qty=D("1.000"), cif_fc=D("30.00"), cif_inr=D("30.00"), user=None)
        self._allot(D("50.00"))                          # unlinked → allotment (50)
        self._allot(D("40.00"), type_="AR")              # AR unlinked → allotment (40)
        self._allot(D("70.00"), status="RELEASED")       # released → nothing
        self.assertEqual(LBC.calculate_boe_debit_total(self.lic), D("120.00"))
        self.assertEqual(LBC.calculate_allotment(self.lic), D("90.00"))
        # 1000 − (120 BOE + 90 allotment) — each amount counted once
        self.assertEqual(LBC.calculate_balance(self.lic), D("790.00"))
        self._components_bulk_equal_single()

    def test_no_excess_reservation(self):
        self._allot(D("60.00"))
        self._allot(D("25.00"), type_="AR")
        rows = LBC.get_allotment_rows(self.lic)
        for r in rows:
            self.assertLessEqual(r.contributed, r.cif_fc)
            self.assertLessEqual(r.contributed_qty, r.qty)
        self.assertEqual(LBC.calculate_allotment(self.lic), D("85.00"))

    def test_no_incorrect_release(self):
        from apps.reconciliation.services.allocation_service import (
            create_boe_allotment_allocation,
            reverse_boe_allotment_allocation,
        )

        a, _ = self._allot(D("40.00"))
        other, _ = self._allot(D("10.00"))
        boe, _ = self._boe_row(D("10.00"))
        boe.allotment.add(other)                         # a BOE linked to ANOTHER allotment
        self.assertEqual(LBC.calculate_allotment(self.lic), D("40.00"))  # a still reserves
        rowless = self.make_boe(self.company)
        rowless.allotment.add(a)                         # rowless link never releases
        self.assertEqual(LBC.calculate_allotment(self.lic), D("40.00"))
        _, ai = self._allot(D("30.00"))
        _, row = self._boe_row(D("5.00"))
        alloc = create_boe_allotment_allocation(row, ai, qty=D("1.000"), cif_fc=D("5.00"), cif_inr=D("5.00"), user=None)
        self.assertEqual(LBC.calculate_allotment(self.lic), D("40.00"))  # short allocation releases ai
        reverse_boe_allotment_allocation(alloc, user=None, reason="test")
        self.assertEqual(LBC.calculate_allotment(self.lic), D("70.00"))  # reversal restores the reservation

    def test_ar_and_at_treated_identically(self):
        at_item, ar_item = self.make_item(self.lic, 2), self.make_item(self.lic, 3)
        self._allot(D("33.00"), item=at_item)
        self._allot(D("33.00"), type_="AR", item=ar_item)
        self.assertEqual(LBC.get_outstanding_allotment_totals(at_item), LBC.get_outstanding_allotment_totals(ar_item))
        self.assertEqual(IBC.calculate_available_quantity(at_item), IBC.calculate_available_quantity(ar_item))

    def test_commission_purchase_never_a_purchase(self):
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        hidden_boe = self.make_boe(self.company, invoice_no="OTH")
        self.make_debit_row(hidden_boe, self.item, D("200.00"))
        opening_before = LBC.calculate_opening_balance(self.lic)
        trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_COMMISSION_PURCHASE, to_company=self.company,
            invoice_number=f"CP-{uuid.uuid4().int % 999999:06d}", invoice_date=datetime.now().date(),
        )
        LicenseTradeLine.objects.create(trade=trade, sr_number=self.item, description="x",
                                        mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=D("500.00"), cif_inr=D("500.00"))
        self.assertEqual(LBC.calculate_opening_balance(self.lic), opening_before)
        self.assertEqual(LBC.calculate_purchase_credit(self.lic), D("0"))
        self.assertEqual(LBC.calculate_opening_balance_for_licenses([self.lic.id])[self.lic.id], opening_before)

    def test_dec50_transfers_net_zero_within_surplus_and_licence_unchanged(self):
        items = [self.make_item(self.lic, n) for n in (2, 3, 4)]
        for it, cif in zip(items, (D("100.00"), D("100.00"), D("100.00"))):
            it.cif_fc = cif
            it.save(update_fields=["cif_fc"])
        self.make_debit_row(self.make_boe(self.company), items[0], D("180.00"))   # over 80
        self.make_debit_row(self.make_boe(self.company), items[1], D("70.00"))    # unused 30
        self._allot(D("50.00"), item=items[2])                                     # unused 50
        balance_before = LBC.calculate_balance(self.lic)
        res = compute_item_cif_adjustments([self.lic.id])
        given = sum((a.given for a in res.by_item.values()), D("0"))
        received = sum((a.received for a in res.by_item.values()), D("0"))
        self.assertEqual(given, received)
        self.assertEqual(received, D("80.00"))
        self.assertLessEqual(res.for_item(items[1].id).given, D("30.00"))
        self.assertLessEqual(res.for_item(items[2].id).given, D("50.00"))
        self.assertEqual(LBC.calculate_balance(self.lic), balance_before)      # licence CIF untouched
        attributed = IBC.calculate_item_attributed_balances_for_items(items)
        self.assertTrue(all(v >= D("0") for v in attributed.values()))

    def test_every_transfer_is_recorded(self):
        from apps.reconciliation.services.item_cif_adjustment_log import refresh_item_cif_adjustment_log

        with self.captureOnCommitCallbacks(execute=True):
            a, b = self.make_item(self.lic, 2), self.make_item(self.lic, 3)
            for it in (a, b):
                it.cif_fc = D("50.00")
                it.save(update_fields=["cif_fc"])
        with self.captureOnCommitCallbacks(execute=True):
            self.make_debit_row(self.make_boe(self.company), a, D("75.00"))
        # dry run = audit-gap check: nothing left to record
        from apps.reconciliation.models import ItemCifAdjustmentRecord
        self.assertEqual(list(ItemCifAdjustmentRecord.objects.values_list("source_item_id", "destination_item_id", "amount_cif_fc")),
                         [(b.id, a.id, D("25.00"))])
        self.assertEqual(refresh_item_cif_adjustment_log([self.lic.id])["licences_changed"], [])
