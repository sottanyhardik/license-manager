"""
Iteration 2 (workstream A1): BOE write-path owner decisions implemented in
`apps.bill_of_entry.api.serializers.BillOfEntrySerializer`.

* D1  - invoice_no change on a genuinely hidden BOE is a 400 on PUT/PATCH.
* D3  - frozen (ledger) rows are never deleted or modified by the form.
* D7  - a date-less create whose number already exists is a 400 + existing id.
* D12/D13 - INDIVIDUAL_ITEM CIF ceiling adds back the BOE's own debit.
* D14 - planning_target_item is persisted (and validated) on PATCH.
"""
from decimal import Decimal

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework import serializers

from apps.bill_of_entry.api.serializers import BillOfEntrySerializer
from apps.bill_of_entry.models import BillOfEntryModel, OTH_INVOICE_MARKER, RowDetails, genuinely_hidden_boe_ids
from apps.bill_of_entry.services.boe_service import hide_boe
from apps.bill_of_entry.tests.test_boe_api_contract import (
    BOE_URL, LOCMEM_CACHES, BoeApiFixtureMixin, boe_detail_url,
)
from apps.reconciliation.models import ReconciliationLog


def _boe_put_payload(boe, **overrides):
    payload = {
        "bill_of_entry_number": boe.bill_of_entry_number,
        "bill_of_entry_date": boe.bill_of_entry_date.isoformat(),
        "company": boe.company_id,
        "invoice_no": boe.invoice_no,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# D1 — hidden BOE invoice number
# --------------------------------------------------------------------------- #
@override_settings(CACHES=LOCMEM_CACHES)
class HiddenBoeInvoiceNoTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)
        self.boe = self.make_boe(self.company)
        self.make_debit_row(self.boe, self.item, cif_fc=Decimal("300.00"))
        hide_boe(self.boe, user=None, reason="Previous owner")
        self.boe.refresh_from_db()
        self.assertIn(self.boe.id, genuinely_hidden_boe_ids(boe_ids=[self.boe.id]))
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))

    def _logs(self):
        return list(
            ReconciliationLog.objects.filter(bill_of_entry=self.boe).values_list("action", flat=True)
        )

    def _assert_still_hidden(self, logs_before):
        self.boe.refresh_from_db()
        self.assertEqual(self.boe.invoice_no, OTH_INVOICE_MARKER)
        self.assertIn(self.boe.id, genuinely_hidden_boe_ids(boe_ids=[self.boe.id]))
        self.assertEqual(self._logs(), logs_before)

    def test_patch_changing_invoice_no_is_400(self):
        logs_before = self._logs()
        response = self.client.patch(boe_detail_url(self.boe.id), {"invoice_no": "INV-9"}, format="json")

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("invoice_no", response.data)
        self.assertIn("restore", str(response.data["invoice_no"]).lower())
        self._assert_still_hidden(logs_before)

    def test_patch_blanking_invoice_no_is_400(self):
        logs_before = self._logs()
        response = self.client.patch(boe_detail_url(self.boe.id), {"invoice_no": ""}, format="json")

        self.assertEqual(response.status_code, 400, response.data)
        self._assert_still_hidden(logs_before)

    def test_put_changing_invoice_no_is_400(self):
        logs_before = self._logs()
        response = self.client.put(
            boe_detail_url(self.boe.id) + "?is_invoice=all",
            _boe_put_payload(self.boe, invoice_no="INV-PUT"), format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("invoice_no", response.data)
        self._assert_still_hidden(logs_before)

    def test_unchanged_invoice_no_on_hidden_boe_is_accepted(self):
        logs_before = self._logs()
        response = self.client.patch(
            boe_detail_url(self.boe.id), {"invoice_no": OTH_INVOICE_MARKER, "comments": "note"}, format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self._assert_still_hidden(logs_before)
        self.assertEqual(self.boe.comments, "note")

    def test_other_field_edit_on_hidden_boe_is_accepted(self):
        response = self.client.patch(boe_detail_url(self.boe.id), {"comments": "x"}, format="json")

        self.assertEqual(response.status_code, 200, response.data)

    def test_serializer_save_rechecks_hidden_state_under_lock(self):
        """A BOE hidden between validation and save is still protected."""
        visible = self.make_boe(self.company)
        serializer = BillOfEntrySerializer(visible, data={"invoice_no": "INV-RACE"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        hide_boe(visible, user=None, reason="concurrent hide")

        with self.assertRaises(serializers.ValidationError):
            serializer.save()
        visible.refresh_from_db()
        self.assertEqual(visible.invoice_no, OTH_INVOICE_MARKER)

    def test_legacy_oth_never_hidden_stays_editable_via_patch(self):
        legacy = self.make_boe(self.company, invoice_no=OTH_INVOICE_MARKER)
        self.assertEqual(genuinely_hidden_boe_ids(boe_ids=[legacy.id]), set())

        response = self.client.patch(boe_detail_url(legacy.id), {"invoice_no": "INV-L"}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        legacy.refresh_from_db()
        self.assertEqual(legacy.invoice_no, "INV-L")
        self.assertFalse(ReconciliationLog.objects.filter(bill_of_entry=legacy).exists())

    def test_restored_boe_invoice_no_is_editable(self):
        from apps.bill_of_entry.services.boe_service import restore_boe

        restore_boe(self.boe, user=None, reason="back")
        response = self.client.patch(boe_detail_url(self.boe.id), {"invoice_no": "INV-R"}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self._logs().count(ReconciliationLog.ACTION_RESTORE_BOE), 1,
        )


# --------------------------------------------------------------------------- #
# D3 — frozen rows
# --------------------------------------------------------------------------- #
@override_settings(CACHES=LOCMEM_CACHES)
class FrozenRowTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item_a = self.make_item(self.license, 1)
        self.item_b = self.make_item(self.license, 2)
        self.item_c = self.make_item(self.license, 3)
        self.boe = self.make_boe(self.company)
        self.editable = self.make_debit_row(self.boe, self.item_a, cif_fc=Decimal("100.00"), qty=Decimal("10.000"))
        self.frozen = self.make_debit_row(self.boe, self.item_b, cif_fc=Decimal("200.00"), qty=Decimal("20.000"))
        RowDetails.objects.filter(id=self.frozen.id).update(is_frozen=True)
        self.frozen.refresh_from_db()

    def _frozen_snapshot(self):
        row = RowDetails.objects.get(id=self.frozen.id)
        return (row.sr_number_id, row.cif_fc, row.cif_inr, row.qty, row.is_frozen, row.bill_of_entry_id)

    def test_empty_item_details_keeps_frozen_row_and_deletes_editable_row(self):
        before = self._frozen_snapshot()
        response = self.client.patch(boe_detail_url(self.boe.id), {"item_details": []}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(RowDetails.objects.filter(id=self.editable.id).exists())
        self.assertEqual(self._frozen_snapshot(), before)

    def test_replacing_rows_keeps_omitted_frozen_row(self):
        before = self._frozen_snapshot()
        response = self.client.patch(boe_detail_url(self.boe.id), {
            "item_details": [self.row_payload(self.item_c, Decimal("50.00"), Decimal("5.000"))],
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._frozen_snapshot(), before)
        self.assertEqual(
            set(RowDetails.objects.filter(bill_of_entry=self.boe).values_list("sr_number_id", flat=True)),
            {self.item_b.id, self.item_c.id},
        )

    def test_frozen_row_echoed_unchanged_is_accepted(self):
        before = self._frozen_snapshot()
        response = self.client.patch(boe_detail_url(self.boe.id), {
            "item_details": [
                self.row_payload(self.item_a, Decimal("120.00"), Decimal("12.000"), row_id=self.editable.id),
                self.row_payload(self.item_b, Decimal("200.00"), Decimal("20.000"), row_id=self.frozen.id),
            ],
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._frozen_snapshot(), before)
        self.assertEqual(RowDetails.objects.get(id=self.editable.id).cif_fc, Decimal("120.000"))

    def test_frozen_row_with_three_decimal_stored_value_echoed_at_2dp_is_accepted(self):
        # The read path serializes with DRF's default ROUND_HALF_EVEN, so the
        # client sees 1234.565 as 1234.56 and echoes that back.
        RowDetails.objects.filter(id=self.frozen.id).update(cif_fc=Decimal("1234.565"))
        echoed = self.row_payload(self.item_b, Decimal("1234.56"), Decimal("20.000"), row_id=self.frozen.id) | {
            "cif_inr": str(self.frozen.cif_inr.quantize(Decimal("0.01")))
        }
        response = self.client.patch(boe_detail_url(self.boe.id), {"item_details": [echoed]}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(RowDetails.objects.get(id=self.frozen.id).cif_fc, Decimal("1234.565"))

        # The HALF_UP neighbour is NOT what the client was shown: a real change.
        changed = dict(echoed, cif_fc="1234.57")
        response = self.client.patch(boe_detail_url(self.boe.id), {"item_details": [changed]}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(RowDetails.objects.get(id=self.frozen.id).cif_fc, Decimal("1234.565"))

    def test_changing_frozen_row_by_id_is_400_naming_the_row(self):
        before = self._frozen_snapshot()
        for change in ({"cif_fc": "201.00"}, {"qty": "21.000"}, {"cif_inr": "1.00"}, {"sr_number": self.item_c.id}):
            row = self.row_payload(self.item_b, Decimal("200.00"), Decimal("20.000"), row_id=self.frozen.id)
            row.update(change)
            response = self.client.patch(boe_detail_url(self.boe.id), {"item_details": [row]}, format="json")

            self.assertEqual(response.status_code, 400, (change, response.data))
            self.assertIn(f"Row {self.frozen.id}", str(response.data["item_details"][0]))
            self.assertEqual(self._frozen_snapshot(), before)
        self.assertTrue(RowDetails.objects.filter(id=self.editable.id).exists())

    def test_changing_frozen_row_by_upsert_key_is_400(self):
        before = self._frozen_snapshot()
        response = self.client.patch(boe_detail_url(self.boe.id), {
            "item_details": [self.row_payload(self.item_b, Decimal("999.00"), Decimal("20.000"))],
        }, format="json")

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn(f"Row {self.frozen.id}", str(response.data["item_details"][0]))
        self.assertEqual(self._frozen_snapshot(), before)


# --------------------------------------------------------------------------- #
# D7 — upsert contract
# --------------------------------------------------------------------------- #
@override_settings(CACHES=LOCMEM_CACHES)
class NullDateCreateContractTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.port = self.make_port()

    def _post(self, number, date=None, **extra):
        payload = {
            "bill_of_entry_number": number,
            "bill_of_entry_date": date,
            "port": self.port.id,
            "company": self.company.id,
        }
        payload.update(extra)
        return self.client.post(BOE_URL, payload, format="json")

    def test_null_date_with_new_number_is_created(self):
        response = self._post("NEWNUM01")
        self.assertEqual(response.status_code, 201, response.data)

    def test_null_date_colliding_with_dated_boe_is_400_with_int_existing_id(self):
        dated = self._post("DATED01", date="2026-03-01")
        self.assertEqual(dated.status_code, 201, dated.data)

        response = self._post("DATED01", comments="overwrite?")

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data["existing_boe_id"], dated.data["id"])
        self.assertIsInstance(response.data["existing_boe_id"], int)
        self.assertIsInstance(response.data["bill_of_entry_date"], list)
        self.assertEqual(BillOfEntryModel.objects.filter(bill_of_entry_number="DATED01").count(), 1)

    def test_rejected_create_writes_no_rows(self):
        license_obj = self.make_license(self.company)
        item = self.make_item(license_obj, 1)
        first = self._post("ROWS01")
        self.assertEqual(first.status_code, 201, first.data)

        response = self._post("ROWS01", item_details=[self.row_payload(item, Decimal("10.00"))])

        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(RowDetails.objects.filter(sr_number=item).exists())

    def test_dated_duplicate_keeps_unique_together_400(self):
        self._post("DUP01", date="2026-03-01")
        response = self._post("DUP01", date="2026-03-01")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("existing_boe_id", response.data)

    def test_dated_create_with_existing_null_date_number_is_allowed(self):
        self.assertEqual(self._post("MIX01").status_code, 201)
        response = self._post("MIX01", date="2026-03-01")
        self.assertEqual(response.status_code, 201, response.data)


# --------------------------------------------------------------------------- #
# D12 / D13 — INDIVIDUAL_ITEM CIF ceiling with own-debit add-back
# --------------------------------------------------------------------------- #
@override_settings(CACHES=LOCMEM_CACHES)
class IndividualItemOwnDebitTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.license = self._individual_licence()
        self.item = self._item(self.license, 1, Decimal("1000.00"))
        self.item_2 = self._item(self.license, 2, Decimal("500.00"))
        self.boe = self.make_boe(self.company)
        self.row = self.make_debit_row(self.boe, self.item, cif_fc=Decimal("600.00"), qty=Decimal("6.000"))

    def _individual_licence(self):
        licence = self.make_license(self.company)
        licence.individual_item_cif_override = True
        licence.save()
        return licence

    def _item(self, licence, serial, cif_fc):
        item = self.make_item(licence, serial)
        item.cif_fc = cif_fc
        item.save()
        return item

    def _patch(self, rows, boe=None):
        return self.client.patch(boe_detail_url((boe or self.boe).id), {"item_details": rows}, format="json")

    def _row(self, item, cif_fc, row_id=None):
        return self.row_payload(item, cif_fc, Decimal("6.000"), row_id=row_id)

    def _stored(self, row=None):
        return RowDetails.objects.get(id=(row or self.row).id).cif_fc

    def test_unchanged_row_passes(self):
        response = self._patch([self._row(self.item, Decimal("600.00"), self.row.id)])
        self.assertEqual(response.status_code, 200, response.data)

    def test_unchanged_row_without_id_passes(self):
        response = self._patch([self._row(self.item, Decimal("600.00"))])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(RowDetails.objects.filter(bill_of_entry=self.boe).count(), 1)

    def test_increase_within_ceiling_passes(self):
        response = self._patch([self._row(self.item, Decimal("1000.00"), self.row.id)])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._stored(), Decimal("1000.000"))

    def test_increase_above_ceiling_is_400(self):
        response = self._patch([self._row(self.item, Decimal("1000.01"), self.row.id)])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("1000.00", str(response.data["item_details"][0]["cif_fc"]))
        self.assertEqual(self._stored(), Decimal("600.000"))

    def test_other_boe_debit_is_not_added_back(self):
        other_boe = self.make_boe(self.company)
        self.make_debit_row(other_boe, self.item, cif_fc=Decimal("300.00"))
        # Ceiling for self.row = 1000 - 300 (other BOE) = 700.
        self.assertEqual(self._patch([self._row(self.item, Decimal("700.00"), self.row.id)]).status_code, 200)
        self.assertEqual(self._patch([self._row(self.item, Decimal("700.01"), self.row.id)]).status_code, 400)

    def test_decrease_passes_even_when_item_over_utilised(self):
        other_boe = self.make_boe(self.company)
        self.make_debit_row(other_boe, self.item, cif_fc=Decimal("900.00"))  # 1500 used of 1000

        self.assertEqual(self._patch([self._row(self.item, Decimal("600.00"), self.row.id)]).status_code, 200)
        response = self._patch([self._row(self.item, Decimal("500.00"), self.row.id)])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._stored(), Decimal("500.000"))
        self.assertEqual(self._patch([self._row(self.item, Decimal("500.01"), self.row.id)]).status_code, 400)

    def test_item_change_gets_no_own_debit_credit(self):
        # item_2 has 500 available; moving the 600 row there must fail ...
        response = self._patch([self._row(self.item_2, Decimal("600.00"), self.row.id)])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(RowDetails.objects.get(id=self.row.id).sr_number_id, self.item.id)
        # ... and 500 fits.
        response = self._patch([self._row(self.item_2, Decimal("500.00"), self.row.id)])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(RowDetails.objects.get(id=self.row.id).sr_number_id, self.item_2.id)

    def test_licence_change_gets_no_own_debit_credit(self):
        other_licence = self._individual_licence()
        other_item = self._item(other_licence, 1, Decimal("400.00"))

        self.assertEqual(self._patch([self._row(other_item, Decimal("600.00"), self.row.id)]).status_code, 400)
        self.assertEqual(self._patch([self._row(other_item, Decimal("400.00"), self.row.id)]).status_code, 200)

    def test_multiple_rows_each_checked_against_own_item(self):
        boe = self.make_boe(self.company)
        # unique (bill_of_entry, sr_number, transaction_type) allows one DEBIT
        # row per item per BOE, so summation is exercised on a licence-wide
        # scope (items with no own CIF) in the next test; here each row is
        # checked against its own item and only the offending row is flagged.
        response = self._patch([self._row(self.item, Decimal("400.00")), self._row(self.item_2, Decimal("500.01"))], boe=boe)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data["item_details"][0], {})
        self.assertIn("cif_fc", response.data["item_details"][1])
        self.assertFalse(RowDetails.objects.filter(bill_of_entry=boe).exists())

    def test_licence_wide_scope_sums_rows_across_items(self):
        licence = self._individual_licence()
        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal("1000.00"))
        zero_a = self._item(licence, 1, Decimal("0"))
        zero_b = self._item(licence, 2, Decimal("0"))
        boe = self.make_boe(self.company)

        over = self._patch([self._row(zero_a, Decimal("600.00")), self._row(zero_b, Decimal("400.01"))], boe=boe)
        self.assertEqual(over.status_code, 400, over.data)
        self.assertIn("Combined", str(over.data["item_details"][0]["cif_fc"]))
        self.assertFalse(RowDetails.objects.filter(bill_of_entry=boe).exists())

        ok = self._patch([self._row(zero_a, Decimal("600.00")), self._row(zero_b, Decimal("400.00"))], boe=boe)
        self.assertEqual(ok.status_code, 200, ok.data)
        rows = list(RowDetails.objects.filter(bill_of_entry=boe).order_by("sr_number__serial_number"))
        # Re-saving both unchanged rows must pass (own debit added back for the scope).
        again = self._patch([
            self._row(zero_a, Decimal("600.00"), rows[0].id), self._row(zero_b, Decimal("400.00"), rows[1].id),
        ], boe=boe)
        self.assertEqual(again.status_code, 200, again.data)

    def test_create_applies_ceiling(self):
        response = self.client.post(BOE_URL, {
            "bill_of_entry_number": "CEIL01", "bill_of_entry_date": "2026-03-01",
            "company": self.company.id, "item_details": [self._row(self.item, Decimal("400.01"))],
        }, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(BillOfEntryModel.objects.filter(bill_of_entry_number="CEIL01").exists())

    def test_hidden_boe_unchanged_resave_passes(self):
        hide_boe(self.boe, user=None, reason="hidden")
        response = self._patch([self._row(self.item, Decimal("600.00"), self.row.id)])
        self.assertEqual(response.status_code, 200, response.data)

    def test_legacy_licence_has_no_ceiling(self):
        legacy = self.make_license(self.company)
        legacy_item = self._item(legacy, 1, Decimal("10.00"))
        response = self._patch([self._row(legacy_item, Decimal("5000.00"))])
        self.assertEqual(response.status_code, 200, response.data)

    def test_concurrent_debit_between_validation_and_save_is_rejected(self):
        serializer = BillOfEntrySerializer(
            self.boe, data={"item_details": [self._row(self.item, Decimal("900.00"), self.row.id)]}, partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        # Another BOE consumes 200 after validation (would have been blocked
        # on the item row lock if it had been concurrent with the save).
        self.make_debit_row(self.make_boe(self.company), self.item, cif_fc=Decimal("200.00"))

        with self.assertRaises(serializers.ValidationError) as ctx:
            serializer.save()
        self.assertIn("cif_fc", ctx.exception.detail["item_details"][0])
        self.assertEqual(self._stored(), Decimal("600.000"))

    def test_save_locks_the_item_row(self):
        serializer = BillOfEntrySerializer(
            self.boe, data={"item_details": [self._row(self.item, Decimal("650.00"), self.row.id)]}, partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with CaptureQueriesContext(connection) as ctx:
            serializer.save()
        locks = [
            q["sql"] for q in ctx.captured_queries
            if "FOR UPDATE" in q["sql"] and "license_licenseimportitemsmodel" in q["sql"]
        ]
        self.assertTrue(locks, "expected SELECT ... FOR UPDATE on the import item")


# --------------------------------------------------------------------------- #
# D14 — planning_target_item on PATCH
# --------------------------------------------------------------------------- #
@override_settings(CACHES=LOCMEM_CACHES)
class PlanningTargetItemPatchTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        import uuid

        from apps.core.models import ItemNameModel

        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.boe = self.make_boe(self.company)
        self.target = ItemNameModel.objects.create(name=f"Plan A {uuid.uuid4().hex[:6]}")
        self.inactive = ItemNameModel.objects.create(name=f"Plan X {uuid.uuid4().hex[:6]}", is_active=False)

    def _patch(self, value, **extra):
        return self.client.patch(
            boe_detail_url(self.boe.id), {"planning_target_item": value, **extra}, format="json",
        )

    def test_patch_persists_target_and_mapping(self):
        response = self._patch(self.target.id)

        self.assertEqual(response.status_code, 200, response.data)
        self.boe.refresh_from_db()
        self.assertEqual(self.boe.planning_target_item_id, self.target.id)
        self.assertEqual(self.boe.planning_mapping_status, "MAPPED_EXPLICIT")
        self.assertEqual(self.boe.planning_mapping_source, "USER_SELECTED")
        self.assertEqual(response.data["planning_target_item"], self.target.id)
        self.assertEqual(response.data["planning_target_item_name"], self.target.name)

    def test_patch_null_clears_target(self):
        self._patch(self.target.id)
        response = self._patch(None)

        self.assertEqual(response.status_code, 200, response.data)
        self.boe.refresh_from_db()
        self.assertIsNone(self.boe.planning_target_item_id)
        self.assertEqual(self.boe.planning_mapping_status, "UNMAPPED_AMBIGUOUS")
        self.assertEqual(self.boe.planning_mapping_source, "")

    def test_patch_without_field_leaves_target(self):
        self._patch(self.target.id)
        response = self.client.patch(boe_detail_url(self.boe.id), {"comments": "x"}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.boe.refresh_from_db()
        self.assertEqual(self.boe.planning_target_item_id, self.target.id)

    def test_patch_with_rows_keeps_target(self):
        licence = self.make_license(self.company)
        item = self.make_item(licence, 1)
        response = self._patch(self.target.id, item_details=[self.row_payload(item, Decimal("10.00"))])

        self.assertEqual(response.status_code, 200, response.data)
        self.boe.refresh_from_db()
        self.assertEqual(self.boe.planning_target_item_id, self.target.id)

    def test_unknown_target_is_400(self):
        response = self._patch(999999999)
        self.assertEqual(response.status_code, 400)
        self.assertIn("planning_target_item", response.data)

    def test_inactive_target_is_400(self):
        response = self._patch(self.inactive.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("planning_target_item", response.data)
        self.boe.refresh_from_db()
        self.assertIsNone(self.boe.planning_target_item_id)

    def test_currently_stored_inactive_target_can_be_resent(self):
        BillOfEntryModel.objects.filter(id=self.boe.id).update(planning_target_item=self.inactive)
        response = self._patch(self.inactive.id)
        self.assertEqual(response.status_code, 200, response.data)


# --------------------------------------------------------------------------- #
# D10 — boe_pdf_copy upload validation on PUT/PATCH
# --------------------------------------------------------------------------- #
@override_settings(CACHES=LOCMEM_CACHES)
class BoePdfCopyUploadValidationTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.boe = self.make_boe(self.company)

    @staticmethod
    def _pdf():
        import io
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    def _patch(self, data):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return self.client.patch(
            boe_detail_url(self.boe.id),
            {"boe_pdf_copy": SimpleUploadedFile("boe.pdf", data, content_type="application/pdf")},
            format="multipart",
        )

    def test_html_disguised_as_pdf_is_400_and_not_stored(self):
        response = self._patch(b"<html><script>alert(1)</script></html>")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("boe_pdf_copy", response.data)
        self.boe.refresh_from_db()
        self.assertFalse(self.boe.boe_pdf_copy)

    def test_oversize_pdf_is_400(self):
        with override_settings(BOE_PDF_MAX_UPLOAD_MB=1):
            response = self._patch(self._pdf() + b"%" + b"x" * (1024 * 1024))
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("boe_pdf_copy", response.data)

    def test_valid_pdf_is_accepted(self):
        import tempfile

        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self._patch(self._pdf())
        self.assertEqual(response.status_code, 200, response.data)

    def test_none_and_unchanged_pass_validator(self):
        serializer = BillOfEntrySerializer()
        self.assertIsNone(serializer.validate_boe_pdf_copy(None))
        self.assertEqual(serializer.validate_boe_pdf_copy("boe/existing.pdf"), "boe/existing.pdf")


# --------------------------------------------------------------------------- #
# D7 on update — null-date collision
# --------------------------------------------------------------------------- #
@override_settings(CACHES=LOCMEM_CACHES)
class NullDateUpdateCollisionTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.other = self.make_boe(self.company, number="7770001")
        self.boe = self.make_boe(self.company, number="7770002")

    def test_patch_clearing_date_onto_existing_number_is_400(self):
        response = self.client.patch(
            boe_detail_url(self.boe.id),
            {"bill_of_entry_number": "7770001", "bill_of_entry_date": None}, format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("bill_of_entry_date", response.data)
        self.assertEqual(response.data["existing_boe_id"], self.other.id)

    def test_patch_clearing_date_on_unique_number_is_ok_and_excludes_self(self):
        response = self.client.patch(boe_detail_url(self.boe.id), {"bill_of_entry_date": None}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        # Re-saving the already undated BOE does not collide with itself.
        response = self.client.patch(boe_detail_url(self.boe.id), {"comments": "x"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)


# --------------------------------------------------------------------------- #
# D12/D13 — non-DEBIT payload rows are outside the ceiling
# --------------------------------------------------------------------------- #
@override_settings(CACHES=LOCMEM_CACHES)
class CeilingTransactionTypeTests(IndividualItemOwnDebitTests):
    def test_non_debit_payload_row_is_skipped(self):
        from apps.bill_of_entry.api.serializers import check_individual_item_cif_ceiling
        from apps.core.constants import CREDIT

        huge = {"sr_number": self.item, "cif_fc": Decimal("5000.00"), "qty": Decimal("1.000")}
        with self.assertRaises(serializers.ValidationError):
            check_individual_item_cif_ceiling(self.boe, [huge], lock=False)
        check_individual_item_cif_ceiling(self.boe, [dict(huge, transaction_type=CREDIT)], lock=False)

    def test_echoed_row_without_cif_counts_at_stored_value(self):
        """Review fix: a payload row targeting an existing row without cif_fc keeps
        its stored 600. Moving it to item_2 (CIF 500) must therefore fail
        (600 > 500). Previously the row was skipped because cif_fc was absent."""
        from apps.bill_of_entry.api.serializers import check_individual_item_cif_ceiling

        moved = {"id": self.row.id, "sr_number": self.item_2}
        with self.assertRaises(serializers.ValidationError):
            check_individual_item_cif_ceiling(self.boe, [moved], lock=False)
        # Echoed unchanged (same item, no cif_fc) still passes.
        check_individual_item_cif_ceiling(self.boe, [{"id": self.row.id}], lock=False)

    def test_target_resolved_by_payload_transaction_type(self):
        from apps.bill_of_entry.api.serializers import _resolve_payload_target
        from apps.core.constants import CREDIT

        by_key = {(self.item.pk, "D"): self.row}
        payload = {"sr_number": self.item}
        self.assertIs(_resolve_payload_target(payload, {}, by_key), self.row)
        self.assertIsNone(_resolve_payload_target(dict(payload, transaction_type=CREDIT), {}, by_key))
