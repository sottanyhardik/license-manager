"""
Canonical CIF balance scenarios (V1 brief §4.4) run against the existing
`LicenseBalanceCalculator`.

The brief names nine balance concepts. The calculator exposes three public
figures per licence:

- `calculate_debit`     → utilised CIF (BOE rows, excluding BOEs that are
                          linked to a trade).
- `calculate_allotment` → reserved CIF held by allotments that have NO linked
                          BOE. An allotment with a linked BOE contributes 0 here.
- `calculate_balance`   → remaining licence balance = credit − (debit + allotment),
                          floored at 0.

Scenarios that need a concept the calculator does not expose (remaining
reservation on a partly-used allotment, available = remaining − reservation)
are marked `xfail(strict=True)` and point at the issue register. A strict
xfail turns into a failure as soon as the gap is closed, so the marker must
be removed at that point.

Quantity balances are NOT covered here; they are a separate calculation path
and are tracked as their own gap.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.test import TestCase

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator

D = Decimal
REMAINING_RESERVATION_GAP = (
    "Engine has no remaining-reservation output, and _annotate_allotment_contribution "
    "zeroes every allotment row whose parent has any linked BOE (When(has_linked_boe, 0)), "
    "which discards the unused remainder even when a BOEAllotmentAllocation exists. See ISS-008."
)


class CanonicalCifScenarioFixture(TestCase):
    def setUp(self):
        self.company = CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name="Scenario Co")
        self.license = LicenseDetailsModel.objects.create(
            license_number="03" + str(uuid.uuid4().int)[:8],
            license_date=datetime.now().date(),
            license_expiry_date=datetime.now().date() + timedelta(days=365),
            exporter=self.company,
        )
        self.import_item = LicenseImportItemsModel.objects.create(
            license=self.license,
            serial_number=1,
            description="Scenario import item",
            quantity=D("1000.000"),
            available_quantity=D("1000.000"),
        )

    # -- builders -----------------------------------------------------------

    def set_original_cif(self, cif_fc):
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=D(cif_fc))

    def make_allotment(self, cif_fc):
        allotment = AllotmentModel.objects.create(company=self.company)
        AllotmentItems.objects.create(
            allotment=allotment,
            item=self.import_item,
            cif_fc=D(cif_fc),
            cif_inr=D(cif_fc) * D("84.5"),
            qty=D("10.000"),
        )
        return allotment

    def make_boe(self, cif_fc, *, allotment=None):
        boe = BillOfEntryModel.objects.create(
            company=self.company,
            bill_of_entry_number=str(uuid.uuid4().int)[:9],
            bill_of_entry_date=datetime.now().date(),
            exchange_rate=D("84.50"),
        )
        if allotment is not None:
            boe.allotment.add(allotment)
        RowDetails.objects.create(
            bill_of_entry=boe,
            sr_number=self.import_item,
            transaction_type=DEBIT,
            cif_fc=D(cif_fc),
            cif_inr=D(cif_fc) * D("84.5"),
            qty=D("10.000"),
        )
        return boe

    # -- readings -----------------------------------------------------------

    def utilised(self):
        return LicenseBalanceCalculator.calculate_debit(self.license)

    def reserved(self):
        return LicenseBalanceCalculator.calculate_allotment(self.license)

    def remaining(self):
        return LicenseBalanceCalculator.calculate_balance(self.license)


class CanonicalCifBalanceScenarioTests(CanonicalCifScenarioFixture):

    def test_scenario_a_full_utilisation_leaves_zero_remaining(self):
        # A: original 100, allotment 100, BOE 100 → remaining 0.
        self.set_original_cif("100.00")
        allotment = self.make_allotment("100.00")
        self.make_boe("100.00", allotment=allotment)

        self.assertEqual(self.utilised(), D("100.00"))
        self.assertEqual(self.reserved(), D("0.00"))
        self.assertEqual(self.remaining(), D("0.00"))

    def test_scenario_b_partial_utilisation_remaining_licence_balance(self):
        # B: original 100, allotment 40, BOE 25 → utilised 25, remaining 75.
        self.set_original_cif("100.00")
        allotment = self.make_allotment("40.00")
        self.make_boe("25.00", allotment=allotment)

        self.assertEqual(self.utilised(), D("25.00"))
        self.assertEqual(self.remaining(), D("75.00"))

    @pytest.mark.xfail(strict=True, reason=REMAINING_RESERVATION_GAP)
    def test_scenario_b_partial_utilisation_reserved_and_available(self):
        # B continued: reserved 15, available 60 (= 100 − 25 − 15).
        self.set_original_cif("100.00")
        allotment = self.make_allotment("40.00")
        self.make_boe("25.00", allotment=allotment)

        remaining_reservation = getattr(LicenseBalanceCalculator, "calculate_remaining_reservation", None)
        self.assertIsNotNone(remaining_reservation, "no remaining-reservation calculation exists")
        self.assertEqual(remaining_reservation(self.license), D("15.00"))
        self.assertEqual(self.remaining() - remaining_reservation(self.license), D("60.00"))

    def test_scenario_c_multiple_boes_against_one_allotment(self):
        # C: original 100, allotment 60, BOE 20 + BOE 15 → utilised 35, remaining 65.
        self.set_original_cif("100.00")
        allotment = self.make_allotment("60.00")
        self.make_boe("20.00", allotment=allotment)
        self.make_boe("15.00", allotment=allotment)

        self.assertEqual(self.utilised(), D("35.00"))
        self.assertEqual(self.remaining(), D("65.00"))

    @pytest.mark.xfail(strict=True, reason=REMAINING_RESERVATION_GAP)
    def test_scenario_c_multiple_boes_reserved_and_available(self):
        # C continued: reserved 25, available 40 (= 100 − 35 − 25).
        self.set_original_cif("100.00")
        allotment = self.make_allotment("60.00")
        self.make_boe("20.00", allotment=allotment)
        self.make_boe("15.00", allotment=allotment)

        remaining_reservation = getattr(LicenseBalanceCalculator, "calculate_remaining_reservation", None)
        self.assertIsNotNone(remaining_reservation, "no remaining-reservation calculation exists")
        self.assertEqual(remaining_reservation(self.license), D("25.00"))
        self.assertEqual(self.remaining() - remaining_reservation(self.license), D("40.00"))

    def test_scenario_d_direct_boe_without_allotment(self):
        # D: original 100, direct BOE 30 → utilised 30, reserved 0, remaining 70.
        self.set_original_cif("100.00")
        self.make_boe("30.00")

        self.assertEqual(self.utilised(), D("30.00"))
        self.assertEqual(self.reserved(), D("0.00"))
        self.assertEqual(self.remaining(), D("70.00"))

    def test_scenario_e_cancelled_allotment_releases_full_reservation(self):
        # E: original 100, allotment 40 cancelled before any BOE → remaining 100.
        # Cancellation is a hard delete (`destroy_allotment` → `allotment.delete()`),
        # which cascades to the items. The audit gap is tracked as ISS-010.
        self.set_original_cif("100.00")
        allotment = self.make_allotment("40.00")
        self.assertEqual(self.reserved(), D("40.00"))

        allotment.delete()

        self.assertEqual(self.reserved(), D("0.00"))
        self.assertEqual(self.remaining(), D("100.00"))

    @pytest.mark.skip(reason=(
        "No partial-cancellation operation exists in the calculator or the "
        "allotment model: allotments are cancelled whole. See ISS-008."
    ))
    def test_scenario_f_partial_cancellation_of_unused_reservation(self):
        # F: original 100, allotment 40, BOE 25, cancel only the unused 15 → remaining 75.
        pass

    def test_scenario_g_over_utilisation_is_floored_and_not_signalled(self):
        # G: original 100, existing BOE 90, new BOE 20 → debit 110, remaining floored at 0.
        # The calculator floors the balance, so the over-utilisation is invisible to any
        # reader of calculate_balance alone. Rejection must happen at save time (ISS-009).
        self.set_original_cif("100.00")
        self.make_boe("90.00")
        self.make_boe("20.00")

        self.assertEqual(self.utilised(), D("110.00"))
        self.assertEqual(self.remaining(), D("0.00"))

    def test_scenario_h_multiple_customers_and_direct_boe(self):
        # H: original 100, customer A 30, customer B 40, direct BOE 10
        #    → reserved 70, utilised 10, remaining 20.
        self.set_original_cif("100.00")
        self.make_allotment("30.00")
        self.make_allotment("40.00")
        self.make_boe("10.00")

        self.assertEqual(self.reserved(), D("70.00"))
        self.assertEqual(self.utilised(), D("10.00"))
        self.assertEqual(self.remaining(), D("20.00"))
