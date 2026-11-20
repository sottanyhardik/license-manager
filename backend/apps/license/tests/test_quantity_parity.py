"""A-1 parity: the canonical per-item available quantity is the engine as-is.

Owner decision (docs/modernization/backend-audit/11_QUANTITY_DISCREPANCY_REPORT.md
§9, A-1): ``available_quantity_canonical`` is exactly
``ItemBalanceCalculator.calculate_available_quantity_for_items`` (S7 direct-sale
netting, floored at 0, Decimal, 3dp).  ``over_utilised_quantity`` is
``max(-unfloored, 0)`` and ``is_quantity_over_utilised`` flags it.  These are
ADDITIVE fields on ``LicenseImportItemSerializer`` (the licence-detail
``import_license`` rows read by CustomsLedgerSection C1 and LicenseBalanceModal
C2); every existing field keeps its value.

Fixture shapes follow §6 L1..L10 and §7.1.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, OTH_INVOICE_MARKER, RowDetails
from apps.core.constants import ARO, DEBIT
from apps.core.models import CompanyModel
from apps.core.scripts.calculate_balance import update_balance_values
from apps.license.api.serializers.license import LicenseImportItemSerializer
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.balance_calculator import ItemBalanceCalculator
from apps.reconciliation.models import ReconciliationLog
from apps.trade.models import LicenseTrade, LicenseTradeLine

D = Decimal
OPT_IN = {"include_canonical_quantity": True}
NEW_FIELDS = ("available_quantity_canonical", "over_utilised_quantity", "is_quantity_over_utilised")


class QuantityFixtureMixin:
    """Small builders shared by the A-1/A-2 quantity tests."""

    def make_company(self, name="Qty Co"):
        return CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name=name)

    def make_license(self, company):
        lic = LicenseDetailsModel.objects.create(
            license_number="03" + str(uuid.uuid4().int)[:8],
            license_date=date.today(),
            license_expiry_date=date.today() + timedelta(days=365),
            exporter=company,
        )
        LicenseExportItemModel.objects.create(license=lic, description="exp", cif_fc=D("100000"))
        return lic

    def make_item(self, lic, quantity, serial=1, unit="kg"):
        return LicenseImportItemsModel.objects.create(
            license=lic, serial_number=serial, description=f"Item {serial}",
            quantity=D(quantity), available_quantity=D(quantity), unit=unit, cif_fc=D("1000"),
        )

    def make_boe(self, company, hidden=False):
        boe = BillOfEntryModel.objects.create(
            company=company, bill_of_entry_number=str(uuid.uuid4().int)[:9],
            bill_of_entry_date=date.today(), exchange_rate=D("84.50"),
            invoice_no=OTH_INVOICE_MARKER if hidden else "",
        )
        if hidden:
            # Same audit entry `hide_boe` writes; "OTH" alone is not a hide.
            ReconciliationLog.objects.create(
                action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe,
                before={"is_hidden": False, "invoice_no": ""}, after={"is_hidden": True},
            )
        return boe

    def restore_log(self, boe):
        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_RESTORE_BOE, bill_of_entry=boe,
            before={"is_hidden": True}, after={"is_hidden": False},
        )

    def debit(self, boe, item, qty, cif="10.00"):
        return RowDetails.objects.create(
            bill_of_entry=boe, sr_number=item, transaction_type=DEBIT,
            qty=D(qty), cif_fc=D(cif), cif_inr=D(cif) * D("84.5"),
        )

    def sale(self, company, item, qty, *, paired=False, invoice_number=""):
        sale = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE, from_company=company, invoice_number=invoice_number,
        )
        if paired:
            purchase = LicenseTrade.objects.create(direction=LicenseTrade.DIR_PURCHASE, from_company=company)
            sale.counterpart = purchase
            sale.save(update_fields=["counterpart"])
            purchase.counterpart = sale
            purchase.save(update_fields=["counterpart"])
        LicenseTradeLine.objects.create(trade=sale, sr_number=item, mode=LicenseTradeLine.MODE_QTY, qty_kg=D(qty))
        return sale

    def allot(self, company, item, qty, cif="10.00", atype="AT"):
        allotment = AllotmentModel.objects.create(company=company, item_name="Qty allotment", type=atype)
        AllotmentItems.objects.create(allotment=allotment, item=item, qty=D(qty), cif_fc=D(cif), cif_inr=D(cif))
        return allotment

    # ---- readers ------------------------------------------------------- #
    @staticmethod
    def engine(item):
        return ItemBalanceCalculator.calculate_available_quantity_for_items([item])[item.id]

    @staticmethod
    def unfloored(item):
        return ItemBalanceCalculator.calculate_unfloored_available_quantity_for_items([item])[item.id]

    @staticmethod
    def payload(item):
        item = LicenseImportItemsModel.objects.get(pk=item.pk)
        return LicenseImportItemSerializer(item, context=OPT_IN).data

    @staticmethod
    def stored(item):
        item = LicenseImportItemsModel.objects.get(pk=item.pk)
        update_balance_values(item)
        item.refresh_from_db()
        return item


class CanonicalQuantityParityTests(QuantityFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.lic = self.make_license(self.company)

    def assert_canonical(self, item, available, over, flag):
        data = self.payload(item)
        self.assertEqual(data["available_quantity_canonical"], available)
        self.assertEqual(data["over_utilised_quantity"], over)
        self.assertIs(data["is_quantity_over_utilised"], flag)
        self.assertEqual(D(data["available_quantity_canonical"]), self.engine(item))
        return data

    # ---- §7.1 cases ------------------------------------------------------ #
    def test_hidden_boe_debit_excluded_by_engine_and_canonical(self):
        item = self.make_item(self.lic, "12335.890")
        self.debit(self.make_boe(self.company, hidden=True), item, "12335.000")
        data = self.assert_canonical(item, "12335.890", "0.000", False)
        self.assertEqual(data["boe_debited_quantity"], 0.0)

    def test_hidden_boe_restore_log_keeps_boe_visible(self):
        item = self.make_item(self.lic, "12335.890")
        boe = self.make_boe(self.company, hidden=True)
        self.debit(boe, item, "12335.000")
        self.restore_log(boe)
        data = self.assert_canonical(item, "0.890", "0.000", False)
        self.assertEqual(data["boe_debited_quantity"], 12335.0)

    def test_paired_sale_whole_quantity_c1_inputs(self):
        item = self.make_item(self.lic, "163077.020", unit="mts")
        self.sale(self.company, item, "163077.020", paired=True)
        data = self.assert_canonical(item, "163077.020", "0.000", False)
        self.assertEqual(ItemBalanceCalculator.calculate_direct_sale_quantity(item), D("0"))
        # Existing S8 field is unchanged (still header-level, pairing-blind).
        self.assertEqual(data["billed_no_boe_qty"], 163077.02)
        self.assertEqual(data["unit"], "mts")

    def test_paired_sale_plus_boe_debit_c1_negative_inputs(self):
        item = self.make_item(self.lic, "33850.820")
        self.debit(self.make_boe(self.company), item, "31142.000")
        self.sale(self.company, item, "33850.820", paired=True)
        data = self.assert_canonical(item, "2708.820", "0.000", False)
        self.assertGreater(D(str(data["boe_debited_quantity"])) + D(str(data["billed_no_boe_qty"])), D("33850.820"))

    def test_unpaired_sale_with_equal_debit_on_same_sr_subtracts_both(self):
        item = self.make_item(self.lic, "20000.000")
        self.debit(self.make_boe(self.company), item, "15898.000")
        self.sale(self.company, item, "15898.000")
        self.assertEqual(self.unfloored(item), D("-11796.000"))
        self.assert_canonical(item, "0.000", "11796.000", True)

    def test_stored_available_integer_floor_fractional_qty(self):
        item = self.make_item(self.lic, "66859.780")
        self.assert_canonical(item, "66859.780", "0.000", False)
        self.assertEqual(self.stored(item).available_quantity, D("66859"))

    def test_over_utilised_floor_and_over_use_value(self):
        item = self.make_item(self.lic, "321000.000")
        self.debit(self.make_boe(self.company), item, "434670.000")
        self.assertEqual(self.unfloored(item), D("-113670.000"))
        self.assert_canonical(item, "0.000", "113670.000", True)
        self.assertEqual(self.stored(item).available_quantity, D("0"))

    def test_bulk_equals_per_item_available_quantity(self):
        items = [self.make_item(self.lic, q, serial=i + 1) for i, q in enumerate(
            ["66859.780", "1253.620", "321000.000", "12335.890", "33850.820"])]
        self.debit(self.make_boe(self.company), items[1], "1014.000")
        self.debit(self.make_boe(self.company), items[2], "434670.000")
        self.debit(self.make_boe(self.company, hidden=True), items[3], "12335.000")
        self.debit(self.make_boe(self.company), items[4], "31142.000")
        self.sale(self.company, items[4], "33850.820", paired=True)
        self.allot(self.company, items[0], "100.000")
        bulk = ItemBalanceCalculator.calculate_available_quantity_for_items(items)
        unfloored = ItemBalanceCalculator.calculate_unfloored_available_quantity_for_items(items)
        for item in items:
            self.assertEqual(bulk[item.id], ItemBalanceCalculator.calculate_available_quantity(item))
            self.assertEqual(bulk[item.id], max(unfloored[item.id], D("0")))

    # ---- owner list ------------------------------------------------------ #
    def test_multiple_allotments_on_one_licence(self):
        a = self.make_item(self.lic, "1000.000", serial=1)
        b = self.make_item(self.lic, "500.000", serial=2)
        self.allot(self.company, a, "30.000")
        self.allot(self.company, a, "20.000")
        self.allot(self.company, b, "100.000")
        # Owner DEC-01 A (2026-11-20, SAT-DEF-001): an ARO allotment consumes
        # item qty like AT (was: never "outstanding allotted").
        self.allot(self.company, a, "7.000", atype=ARO)
        self.assert_canonical(a, "943.000", "0.000", False)
        self.assert_canonical(b, "400.000", "0.000", False)

    def test_allotment_represented_by_boe_is_not_outstanding(self):
        item = self.make_item(self.lic, "17625.860")
        allotment = self.allot(self.company, item, "3774.000")
        boe = self.make_boe(self.company)
        boe.allotment.add(allotment)
        self.debit(boe, item, "10185.680")
        self.assert_canonical(item, "7440.180", "0.000", False)

    def test_partial_boe_utilisation(self):
        item = self.make_item(self.lic, "1253.620")
        self.debit(self.make_boe(self.company), item, "1014.000")
        self.assert_canonical(item, "239.620", "0.000", False)
        self.assertEqual(self.stored(item).available_quantity, D("239"))

    def test_multiple_boes_against_one_allotment(self):
        item = self.make_item(self.lic, "1000.000")
        allotment = self.allot(self.company, item, "100.000")
        for _ in range(2):
            boe = self.make_boe(self.company)
            boe.allotment.add(allotment)
            self.debit(boe, item, "40.000")
        self.assert_canonical(item, "920.000", "0.000", False)

    def test_invoice_without_boe_is_direct_sale(self):
        item = self.make_item(self.lic, "100.000")
        self.sale(self.company, item, "30.000")
        self.assertEqual(ItemBalanceCalculator.calculate_direct_sale_quantity(item), D("30.0000"))
        self.assert_canonical(item, "70.000", "0.000", False)
        stored = self.stored(item)
        self.assertEqual(stored.available_quantity, D("70"))
        self.assertEqual(stored.debited_quantity, D("30.00"))  # direct sale stays in stored "debited"

    def test_duplicate_sale_invoice_rejected_by_existing_constraint(self):
        buyer = self.make_company("Buyer")
        LicenseTrade.objects.create(direction=LicenseTrade.DIR_SALE, from_company=self.company,
                                    to_company=buyer, invoice_number="INV-1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            LicenseTrade.objects.create(direction=LicenseTrade.DIR_SALE, from_company=self.company,
                                        to_company=buyer, invoice_number="INV-1")

    def test_mixed_unit_strings_are_per_item_and_never_summed(self):
        kg = self.make_item(self.lic, "100.000", serial=1, unit="kg")
        upper = self.make_item(self.lic, "16530.490", serial=2, unit="KG")
        boe = self.make_boe(self.company)
        self.debit(boe, kg, "40.000")
        self.debit(boe, upper, "7220.000")
        a = self.assert_canonical(kg, "60.000", "0.000", False)
        b = self.assert_canonical(upper, "9310.490", "0.000", False)
        self.assertEqual((a["unit"], b["unit"]), ("kg", "KG"))
        self.assertFalse(any("total" in key for key in a if key in NEW_FIELDS))

    def test_decimal_precision_three_dp_string_no_float_drift(self):
        item = self.make_item(self.lic, "0.300")
        boe = self.make_boe(self.company)
        self.debit(boe, item, "0.100")
        self.debit(self.make_boe(self.company), item, "0.200")
        data = self.assert_canonical(item, "0.000", "0.000", False)  # float would be -5.55e-17
        self.assertIsInstance(data["available_quantity_canonical"], str)
        self.assertIsInstance(data["over_utilised_quantity"], str)
        fractional = self.make_item(self.lic, "1000.001", serial=2)
        self.debit(boe, fractional, "0.001")
        self.assert_canonical(fractional, "1000.000", "0.000", False)

    def test_zero_quantity(self):
        item = self.make_item(self.lic, "0.000")
        self.assert_canonical(item, "0.000", "0.000", False)
        self.assertEqual(self.stored(item).available_quantity, D("0"))

    def test_negative_or_invalid_quantity(self):
        item = self.make_item(self.lic, "100.000")
        # Existing model validation rejects a negative debit quantity.
        bad = RowDetails(bill_of_entry=self.make_boe(self.company), sr_number=item, transaction_type=DEBIT,
                         qty=D("-1.000"), cif_fc=D("1"), cif_inr=D("84.5"))
        with self.assertRaises(DjangoValidationError):
            bad.full_clean()
        # An item quantity has no such validator: a negative value floors with the flag.
        negative = self.make_item(self.lic, "-5.000", serial=2)
        self.assert_canonical(negative, "0.000", "5.000", True)

    def test_existing_fields_unchanged_and_new_fields_additive(self):
        item = self.make_item(self.lic, "1253.620")
        self.debit(self.make_boe(self.company), item, "1014.000")
        stored = self.stored(item)
        data = self.payload(stored)
        for name in NEW_FIELDS:
            self.assertIn(name, data)
        self.assertEqual(data["available_quantity"], 239.0)
        self.assertEqual(data["debited_quantity"], 1014.0)
        self.assertEqual(data["boe_debited_quantity"], 1014.0)
        self.assertEqual(data["quantity"], "1253.620")

    def test_list_serializer_is_batched_not_per_item(self):
        items = [self.make_item(self.lic, "100.000", serial=i + 1) for i in range(5)]
        for item in items:
            self.debit(self.make_boe(self.company), item, "10.000")
        fetched = list(LicenseImportItemsModel.objects.filter(pk__in=[i.pk for i in items]))
        target = "apps.license.services.balance_calculator.ItemBalanceCalculator." \
                 "calculate_unfloored_available_quantity_for_items"
        real = ItemBalanceCalculator.calculate_unfloored_available_quantity_for_items
        with mock.patch(target, side_effect=real) as spy:
            rows = LicenseImportItemSerializer(fetched, many=True, context=dict(OPT_IN)).data
        self.assertEqual(spy.call_count, 1, "one bulk engine call per page, not one per item")
        self.assertEqual(len(spy.call_args.args[0]), 5)
        self.assertTrue(all(row["available_quantity_canonical"] == "90.000" for row in rows))


class PayloadConsistencyTests(QuantityFixtureMixin, TestCase):
    """Overview vs ledger: the licence-detail import rows (C1/C2 source) and the
    allotment candidate rows carry the same engine value for the same item."""

    def setUp(self):
        self.company = self.make_company()
        self.lic = self.make_license(self.company)
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create_superuser(
            username=f"qty_{uuid.uuid4().hex[:8]}", password="x", email=f"{uuid.uuid4().hex[:6]}@example.com"))

    def test_licence_detail_and_allotment_candidates_match_engine(self):
        item = self.make_item(self.lic, "58965.610")
        self.debit(self.make_boe(self.company), item, "19233.000")
        # Hidden qty kept small enough that the item is an allotment candidate
        # under either stored-writer rule (A-2 paused); the engine ignores it.
        self.debit(self.make_boe(self.company, hidden=True), item, "10000.000")
        self.sale(self.company, item, "21314.000")
        engine = self.engine(item)
        self.assertEqual(engine, D("18418.610"))

        detail = self.client.get(f"/api/licenses/{self.lic.id}/")
        self.assertEqual(detail.status_code, 200)
        rows = detail.data.get("import_license") or detail.data.get("import_license_read")
        row = next(r for r in rows if r["id"] == item.id)
        self.assertEqual(row["available_quantity_canonical"], "18418.610")
        self.assertIs(row["is_quantity_over_utilised"], False)

        # The same item serialised on a batched list page carries the same value.
        page = LicenseImportItemSerializer(
            list(LicenseImportItemsModel.objects.filter(license=self.lic)), many=True, context=dict(OPT_IN)).data
        listed = next(r for r in page if r["id"] == item.id)
        self.assertEqual(listed["available_quantity_canonical"], row["available_quantity_canonical"])
        self.assertEqual(listed["over_utilised_quantity"], row["over_utilised_quantity"])
        self.assertEqual(D(row["available_quantity_canonical"]), ItemBalanceCalculator.calculate_available_quantity(item))

    def test_other_payloads_unchanged_without_opt_in(self):
        item = self.make_item(self.lic, "100.000")
        self.assertFalse(set(NEW_FIELDS) & set(LicenseImportItemSerializer(item).data))
        allotment = AllotmentModel.objects.create(company=self.company, item_name="X", required_quantity=D("10"))
        resp = self.client.get(f"/api/allotment-actions/{allotment.id}/available-licenses/",
                               {"debit_based_on": "ACTUAL"})
        self.assertEqual(resp.status_code, 200, resp.data)
        candidate = next(r for r in resp.data["available_items"] if r["id"] == item.id)
        self.assertFalse(set(NEW_FIELDS) & set(candidate))
