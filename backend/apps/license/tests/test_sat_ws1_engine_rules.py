"""
SAT WS1 — owner decisions of 2026-11-20 applied to the Balance Engine
(`docs/qa/SAT_USER_DECISION_REGISTER.md`, decision-closure section):

- DEC-01 A   an ARO (`AR`) allotment is consumption at item level, like AT.
- DEC-03 C   an M2M link to a BOE with no DEBIT rows does NOT release the
             allotment; the link is listed as a reconciliation exception.
- DEC-06 A   COMMISSION_PURCHASE is neither a purchase credit nor an
             opening-balance gate in the CIF engine.
- DEC-07b A  an allotment item with status RELEASED (or COMPLETED) stops
             reserving CIF/qty.
- DEC-14 B   a BOE that formally covers only part of an allotment item
             releases the uncovered remainder immediately.
- SAT-DEF-005 / D-A, D-B: the shared-ceiling item cap (`cif_fc == 0` items)
             never exceeds max(licence balance, 0).

Original CIF is 100.00 throughout; expected values are hand-computed.
"""
from decimal import Decimal
from datetime import datetime
import uuid

from django.test import TestCase

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import (
    ItemBalanceCalculator as IBC,
    LicenseBalanceCalculator as LBC,
)
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin

D = Decimal


class WS1EngineRuleTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.lic = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=self.lic, cif_fc=D("100.00"))
        self.item = self.make_item(self.lic, 1)

    # helpers -------------------------------------------------------------
    def _allot(self, cif, qty=D("10.000"), type_="AT", status="CREATED", item=None):
        a = AllotmentModel.objects.create(company=self.company, item_name="WS1", type=type_)
        ai = AllotmentItems.objects.create(
            item=item or self.item, allotment=a, cif_fc=cif, cif_inr=cif * D("84.5"), qty=qty, status=status,
        )
        return a, ai

    def _assert_allotment(self, expected):
        self.assertEqual(LBC.calculate_allotment(self.lic), expected)
        self.assertEqual(LBC.calculate_allotment_for_licenses([self.lic.id]).get(self.lic.id, D("0")), expected)

    # DEC-03 --------------------------------------------------------------
    def test_link_to_rowless_boe_keeps_allotment_outstanding(self):
        a, _ = self._allot(D("40.00"))
        rowless = self.make_boe(self.company, number="1234567")
        rowless.allotment.add(a)
        self._assert_allotment(D("40.00"))
        self.assertEqual(LBC.get_outstanding_allotment_totals(self.item), (D("10.000"), D("40.00")))
        self.assertEqual(LBC.calculate_balance(self.lic), D("60.00"))

    def test_link_to_boe_with_rows_still_full_consumption(self):
        a, _ = self._allot(D("40.00"))
        boe = self.make_boe(self.company)
        self.make_debit_row(boe, self.item, D("15.00"))
        boe.allotment.add(a)
        self._assert_allotment(D("0.00"))
        self.assertEqual(LBC.calculate_balance(self.lic), D("85.00"))

    def test_rowless_link_exception_list(self):
        from apps.license.services.allotment_exceptions import rowless_boe_link_exceptions

        a, ai = self._allot(D("40.00"))
        rowless = self.make_boe(self.company, number="1234567")
        rowless.allotment.add(a)
        ok_a, _ = self._allot(D("5.00"))
        good = self.make_boe(self.company)
        self.make_debit_row(good, self.item, D("5.00"))
        good.allotment.add(ok_a)
        rows = rowless_boe_link_exceptions([self.lic.id])
        self.assertEqual([(r["allotment_id"], r["bill_of_entry_number"]) for r in rows], [(a.id, "1234567")])
        self.assertEqual(rows[0]["outstanding_cif_fc"], D("40.00"))

    # DEC-14 --------------------------------------------------------------
    def test_short_formal_allocation_releases_remainder(self):
        from apps.reconciliation.services.allocation_service import create_boe_allotment_allocation

        _, ai = self._allot(D("40.00"))
        boe = self.make_boe(self.company)
        row = self.make_debit_row(boe, self.item, D("15.00"), qty=D("3.000"))
        create_boe_allotment_allocation(row, ai, qty=D("3.000"), cif_fc=D("15.00"), cif_inr=D("1267.50"), user=None)
        self._assert_allotment(D("0.00"))
        self.assertEqual(LBC.get_outstanding_allotment_totals(self.item), (D("0"), D("0")))
        self.assertEqual(LBC.calculate_balance(self.lic), D("85.00"))  # 100 − BOE 15; remainder 25 released

    # DEC-07b -------------------------------------------------------------
    def test_released_and_completed_items_do_not_reserve(self):
        self._allot(D("20.00"), status="RELEASED")
        self._allot(D("10.00"), status="COMPLETED")
        self._allot(D("5.00"), status="REACTIVATED")
        self._allot(D("7.00"))
        self._assert_allotment(D("12.00"))
        self.assertEqual(LBC.calculate_balance(self.lic), D("88.00"))

    # DEC-01 --------------------------------------------------------------
    def test_aro_allotment_consumes_item_qty_and_cif(self):
        self._allot(D("30.00"), qty=D("200.000"), type_="AR")
        self.assertEqual(LBC.get_outstanding_allotment_totals(self.item), (D("200.000"), D("30.00")))
        bulk = LBC.get_outstanding_allotment_totals_for_items([self.lic.id])
        self.assertEqual(bulk[self.item.id], (D("200.000"), D("30.00")))
        self.assertEqual(IBC.calculate_available_quantity(self.item), D("800.000"))  # 1000 − 200 AR
        self._assert_allotment(D("30.00"))  # licence level already counted it

    def test_stored_writer_counts_aro_once(self):
        from apps.core.scripts.calculate_balance import calculate_available_quantity

        self._allot(D("30.00"), qty=D("200.000"), type_="AR")
        self._allot(D("10.00"), qty=D("100.000"))
        self.assertEqual(D(str(calculate_available_quantity(self.item))), D("700.000"))

    # DEC-06 --------------------------------------------------------------
    def test_commission_purchase_is_not_a_purchase_credit(self):
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_COMMISSION_PURCHASE, to_company=self.company,
            invoice_number=f"CP-{uuid.uuid4().int % 999999:06d}", invoice_date=datetime.now().date(),
        )
        LicenseTradeLine.objects.create(
            trade=trade, sr_number=self.item, description="x", mode=LicenseTradeLine.MODE_CIF_INR,
            cif_fc=D("50.00"), cif_inr=D("4225.00"),
        )
        self.assertFalse(LBC.get_purchase_trade_rows(self.lic).exists())
        self.assertEqual(LBC.calculate_purchase_credit(self.lic), D("0"))
        self.assertEqual(LBC.calculate_purchase_credit_for_licenses([self.lic.id]).get(self.lic.id, D("0")), D("0"))
        self.assertFalse(LBC.has_purchase_for_licenses([self.lic.id]).get(self.lic.id, False))

    # SAT-DEF-005 ----------------------------------------------------------
    def test_shared_ceiling_item_cap_never_exceeds_licence_balance(self):
        sibling = self.make_item(self.lic, 2)
        self._allot(D("70.00"), item=sibling)
        self.assertEqual(LBC.calculate_balance(self.lic), D("30.00"))
        self.assertEqual(IBC.calculate_item_balance(self.item), D("30.00"))

    def test_shared_ceiling_item_cap_floors_at_zero_when_over_utilised(self):
        sibling = self.make_item(self.lic, 2)
        self._allot(D("130.00"), item=sibling)
        self.assertEqual(IBC.calculate_item_balance(self.item), D("0"))
