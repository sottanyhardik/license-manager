"""
Owner decision 2026-11-17: an allotment linked to a BOE through the
`BillOfEntryModel.allotment` M2M is FULLY CONSUMED (no partial consumption is
derived for that relationship). Amended 2026-11-20 (DEC-03 C / DEC-14 B): the
linked BOE must carry a DEBIT row, and a formal `BOEAllotmentAllocation`
covering part of an item releases the whole item.

Pins the rule across layers that expose allotment CIF: engine
(`calculate_allotment`, `calculate_balance`), item level
(`get_outstanding_allotment_totals`), overview summary card
(`total_allotted_cif`) and overview Allotments tab (`outstanding_cif_fc`).
BOE debit CIF is counted exactly once whatever the number of links.
Original CIF is 100.00 throughout; expected values are hand-computed.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin

D = Decimal


class M2MFullConsumptionTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())
        self.company = self.make_company()
        self.lic = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=self.lic, cif_fc=D("100.00"))
        self.item = self.make_item(self.lic, 1)

    # helpers -------------------------------------------------------------
    def _allot(self, cif):
        a = AllotmentModel.objects.create(company=self.company, item_name="M2M")
        AllotmentItems.objects.create(item=self.item, allotment=a, cif_fc=cif, cif_inr=cif * D("84.5"), qty=D("10.000"))
        return a

    def _boe(self, cif, *allotments):
        boe = self.make_boe(self.company)
        row = self.make_debit_row(boe, self.item, cif)
        for a in allotments:
            boe.allotment.add(a)
        return boe, row

    def _layers(self):
        summary = self.client.get(f"/api/licenses/{self.lic.id}/overview-summary/")
        tab = self.client.get(f"/api/licenses/{self.lic.id}/overview-allotments/")
        assert summary.status_code == 200 and tab.status_code == 200
        return {
            "engine": LBC.calculate_allotment(self.lic),
            "item": LBC.get_outstanding_allotment_totals(self.item)[1],
            "card": D(str(summary.data["summary"]["total_allotted_cif"])),
            "tab": sum((D(str(r["outstanding_cif_fc"])) for r in tab.data), D("0")),
        }

    def _assert_allotment_everywhere(self, expected):
        layers = self._layers()
        for name, value in layers.items():
            self.assertEqual(value, expected, f"{name} layer: {layers}")

    # full consumption -----------------------------------------------------
    def test_fully_billed_m2m_link_consumes_allotment(self):
        a = self._allot(D("40.00"))
        self._boe(D("40.00"), a)
        self._assert_allotment_everywhere(D("0.00"))
        self.assertEqual(LBC.calculate_boe_debit_total(self.lic), D("40.00"))
        self.assertEqual(LBC.calculate_balance(self.lic), D("60.00"))  # 100 − 40, once

    def test_partially_billed_m2m_link_is_full_consumption(self):
        a = self._allot(D("40.00"))
        self._boe(D("15.00"), a)
        # Decision: no remainder (25) is derived for an M2M link.
        self._assert_allotment_everywhere(D("0.00"))
        self.assertEqual(LBC.calculate_balance(self.lic), D("85.00"))  # 100 − BOE 15

    # duplicate prevention -------------------------------------------------
    def test_one_boe_linked_to_two_allotments_counts_boe_once(self):
        a1, a2 = self._allot(D("30.00")), self._allot(D("20.00"))
        self._boe(D("45.00"), a1, a2)
        self._assert_allotment_everywhere(D("0.00"))
        self.assertEqual(LBC.calculate_boe_debit_total(self.lic), D("45.00"))
        self.assertEqual(LBC.calculate_balance(self.lic), D("55.00"))

    def test_relinking_the_same_boe_is_idempotent(self):
        a = self._allot(D("40.00"))
        boe, _ = self._boe(D("40.00"), a)
        boe.allotment.add(a)  # duplicate add: M2M keeps a single link
        self.assertEqual(boe.allotment.filter(pk=a.pk).count(), 1)
        self._assert_allotment_everywhere(D("0.00"))
        self.assertEqual(LBC.calculate_balance(self.lic), D("60.00"))

    # multiple linked records -----------------------------------------------
    def test_allotment_linked_to_two_boes_is_consumed_once(self):
        a = self._allot(D("60.00"))
        self._boe(D("20.00"), a)
        self._boe(D("15.00"), a)
        self._assert_allotment_everywhere(D("0.00"))
        self.assertEqual(LBC.calculate_boe_debit_total(self.lic), D("35.00"))
        self.assertEqual(LBC.calculate_balance(self.lic), D("65.00"))

    def test_mixed_linked_and_unlinked_allotments(self):
        linked = self._allot(D("30.00"))
        self._allot(D("25.00"))  # outstanding
        self._boe(D("30.00"), linked)
        self._assert_allotment_everywhere(D("25.00"))
        self.assertEqual(LBC.calculate_balance(self.lic), D("45.00"))  # 100 − (30 BOE + 25 allotment)

    # distinction preserved ----------------------------------------------
    def test_independently_consumed_short_allocation_releases_remainder(self):
        # Owner DEC-14 B (2026-11-20) supersedes the 2026-11-17 "formal
        # allocation keeps partial netting": a short BOE releases the
        # remainder (25) at once.
        from apps.reconciliation.services.allocation_service import create_boe_allotment_allocation

        a = self._allot(D("40.00"))
        allotment_item = AllotmentItems.objects.get(allotment=a)
        boe = self.make_boe(self.company)
        row = self.make_debit_row(boe, self.item, D("15.00"))  # no M2M link
        create_boe_allotment_allocation(row, allotment_item, qty=D("3.000"), cif_fc=D("15.00"),
                                        cif_inr=D("1267.50"), user=None)
        self._assert_allotment_everywhere(D("0.00"))
        self.assertEqual(LBC.calculate_balance(self.lic), D("85.00"))  # 100 − BOE 15

    def test_over_utilisation_stays_negative(self):
        self._allot(D("70.00"))
        self._boe(D("50.00"))  # unrelated BOE, no link
        self.assertEqual(LBC.calculate_balance(self.lic), D("-20.00"))  # signed, not clamped
