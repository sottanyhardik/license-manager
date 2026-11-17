"""
Workstream B3: BOE create/update orchestration lives in
`boe_service.save_boe_with_rows` (ADR-003).  The API-level characterization
tests below were written against the serializer implementation and must pass
unchanged against the service; the service-level tests pin the new entry point.
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework import serializers

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.bill_of_entry.services import boe_service
from apps.bill_of_entry.tests.test_boe_api_contract import (
    BOE_URL, LOCMEM_CACHES, BoeApiFixtureMixin, boe_detail_url,
)


@override_settings(CACHES=LOCMEM_CACHES)
class BoeSaveCreateCharacterizationTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.user = self.make_role_user("BOE_MANAGER")
        self.client = self.client_for(self.user)
        self.company = self.make_company()
        self.port = self.make_port()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)
        self.item_2 = self.make_item(self.license, 2)

    def _post(self, **extra):
        payload = {
            "bill_of_entry_number": "SAVE001",
            "bill_of_entry_date": "2026-02-01",
            "port": self.port.id,
            "company": self.company.id,
        }
        payload.update(extra)
        return self.client.post(BOE_URL, payload, format="json")

    def test_create_with_rows_writes_header_rows_and_audit_user(self):
        response = self._post(item_details=[
            self.row_payload(self.item, Decimal("100.00"), Decimal("10.000")),
            self.row_payload(self.item_2, Decimal("50.00"), Decimal("5.000")),
        ])
        self.assertEqual(response.status_code, 201, response.data)
        boe = BillOfEntryModel.objects.get(pk=response.data["id"])
        self.assertEqual(boe.created_by_id, self.user.id)
        self.assertEqual(boe.port_id, self.port.id)
        rows = RowDetails.objects.filter(bill_of_entry=boe)
        self.assertEqual(sorted(r.cif_fc for r in rows), [Decimal("50.00"), Decimal("100.00")])

    def test_create_sets_allotments_and_is_boe_flag(self):
        allotment = self.make_allotment(self.company)
        other = self.make_allotment(self.company, item_name="Other")
        response = self._post(allotment=[allotment.id])
        self.assertEqual(response.status_code, 201, response.data)
        boe = BillOfEntryModel.objects.get(pk=response.data["id"])
        self.assertEqual(list(boe.allotment.values_list("id", flat=True)), [allotment.id])
        allotment.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(allotment.is_boe)
        self.assertFalse(other.is_boe)

    def test_create_without_rows_or_allotments(self):
        response = self._post()
        self.assertEqual(response.status_code, 201, response.data)
        boe = BillOfEntryModel.objects.get(pk=response.data["id"])
        self.assertFalse(RowDetails.objects.filter(bill_of_entry=boe).exists())
        self.assertFalse(boe.allotment.exists())

    def test_null_date_collision_is_400_with_existing_id(self):
        first = self._post(bill_of_entry_date=None)
        self.assertEqual(first.status_code, 201, first.data)
        second = self._post(bill_of_entry_date=None)
        self.assertEqual(second.status_code, 400, second.data)
        self.assertEqual(second.data["existing_boe_id"], first.data["id"])
        self.assertEqual(BillOfEntryModel.objects.filter(bill_of_entry_number="SAVE001").count(), 1)


@override_settings(CACHES=LOCMEM_CACHES)
class BoeSaveUpdateCharacterizationTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.user = self.make_role_user("BOE_MANAGER")
        self.client = self.client_for(self.user)
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)
        self.item_2 = self.make_item(self.license, 2)
        self.item_3 = self.make_item(self.license, 3)
        self.boe = self.make_boe(self.company)
        self.row = self.make_debit_row(self.boe, self.item, cif_fc=Decimal("100.00"), qty=Decimal("10.000"))
        self.row_2 = self.make_debit_row(self.boe, self.item_2, cif_fc=Decimal("200.00"), qty=Decimal("20.000"))

    def _patch(self, payload):
        return self.client.patch(boe_detail_url(self.boe.id), payload, format="json")

    def test_nested_add_update_delete(self):
        response = self._patch({"comments": "c", "item_details": [
            self.row_payload(self.item, Decimal("111.00"), Decimal("11.000"), row_id=self.row.id),
            self.row_payload(self.item_3, Decimal("30.00"), Decimal("3.000")),
        ]})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(RowDetails.objects.filter(pk=self.row_2.pk).exists())
        self.row.refresh_from_db()
        self.assertEqual(self.row.cif_fc, Decimal("111.00"))
        self.assertTrue(RowDetails.objects.filter(bill_of_entry=self.boe, sr_number=self.item_3).exists())
        self.assertEqual(RowDetails.objects.filter(bill_of_entry=self.boe).count(), 2)
        self.boe.refresh_from_db()
        self.assertEqual(self.boe.comments, "c")
        self.assertEqual(self.boe.modified_by_id, self.user.id)

    def test_upsert_by_key_without_id_updates_in_place(self):
        response = self._patch({"item_details": [
            self.row_payload(self.item, Decimal("123.00"), Decimal("12.000")),
            self.row_payload(self.item_2, Decimal("200.00"), Decimal("20.000"), row_id=self.row_2.id),
        ]})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(RowDetails.objects.filter(bill_of_entry=self.boe).count(), 2)
        self.row.refresh_from_db()
        self.assertEqual(self.row.cif_fc, Decimal("123.00"))

    def test_patch_without_item_details_keeps_rows(self):
        self.assertEqual(self._patch({"comments": "x"}).status_code, 200)
        self.assertEqual(RowDetails.objects.filter(bill_of_entry=self.boe).count(), 2)

    def test_frozen_row_survives_omission(self):
        RowDetails.objects.filter(pk=self.row_2.pk).update(is_frozen=True)
        response = self._patch({"item_details": [
            self.row_payload(self.item, Decimal("100.00"), Decimal("10.000"), row_id=self.row.id),
        ]})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(RowDetails.objects.filter(pk=self.row_2.pk, is_frozen=True).exists())

    def test_allotment_set_flags_and_unflags(self):
        a1 = self.make_allotment(self.company, item_name="A1")
        a2 = self.make_allotment(self.company, item_name="A2")
        self.assertEqual(self._patch({"allotment": [a1.id]}).status_code, 200)
        a1.refresh_from_db()
        self.assertTrue(a1.is_boe)

        self.assertEqual(self._patch({"allotment": [a2.id]}).status_code, 200)
        a1.refresh_from_db()
        a2.refresh_from_db()
        self.assertFalse(a1.is_boe)
        self.assertTrue(a2.is_boe)
        self.assertEqual(list(self.boe.allotment.values_list("id", flat=True)), [a2.id])

    def test_removed_allotment_shared_with_other_boe_keeps_flag(self):
        a1 = self.make_allotment(self.company, item_name="A1")
        a2 = self.make_allotment(self.company, item_name="A2")
        other = self.make_boe(self.company)
        other.allotment.set([a1])
        self.assertEqual(self._patch({"allotment": [a1.id]}).status_code, 200)
        self.assertEqual(self._patch({"allotment": [a2.id]}).status_code, 200)
        a1.refresh_from_db()
        self.assertTrue(a1.is_boe)

    def test_planning_target_persisted(self):
        from apps.core.models import ItemNameModel
        target = ItemNameModel.objects.create(name="Plan Target")
        response = self._patch({"planning_target_item": target.id})
        self.assertEqual(response.status_code, 200, response.data)
        self.boe.refresh_from_db()
        self.assertEqual(self.boe.planning_target_item_id, target.id)
        self.assertEqual(self.boe.planning_mapping_status, "MAPPED_EXPLICIT")
        self.assertEqual(self.boe.planning_mapping_source, "USER_SELECTED")

    def test_ceiling_violation_is_400_and_rolls_back(self):
        self.license.individual_item_cif_override = True
        self.license.save()
        self.item.cif_fc = Decimal("150.00")
        self.item.save()
        response = self._patch({"comments": "should-not-stick", "item_details": [
            self.row_payload(self.item, Decimal("999.00"), Decimal("10.000"), row_id=self.row.id),
        ]})
        self.assertEqual(response.status_code, 400, response.data)
        self.boe.refresh_from_db()
        self.row.refresh_from_db()
        self.assertNotEqual(self.boe.comments, "should-not-stick")
        self.assertEqual(self.row.cif_fc, Decimal("100.00"))
        self.assertTrue(RowDetails.objects.filter(pk=self.row_2.pk).exists())


@override_settings(CACHES=LOCMEM_CACHES)
class SaveBoeWithRowsServiceTests(BoeApiFixtureMixin, TestCase):
    """Direct service entry point (no HTTP)."""

    def setUp(self):
        self.user = self.make_role_user("BOE_MANAGER")
        self.company = self.make_company()
        self.port = self.make_port()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)

    def _header(self, **extra):
        data = {
            "bill_of_entry_number": "SVC001",
            "bill_of_entry_date": "2026-04-01",
            "port": self.port,
            "company": self.company,
        }
        data.update(extra)
        return data

    def test_create_returns_boe_with_rows(self):
        boe = boe_service.save_boe_with_rows(
            validated_data=self._header(),
            item_rows=[{"sr_number": self.item, "cif_fc": Decimal("10.00"),
                        "cif_inr": Decimal("845.00"), "qty": Decimal("1.000")}],
            allotments=None,
            user=self.user,
        )
        self.assertIsInstance(boe, BillOfEntryModel)
        self.assertEqual(RowDetails.objects.filter(bill_of_entry=boe).count(), 1)

    def test_update_requires_instance_and_applies_header(self):
        boe = self.make_boe(self.company)
        out = boe_service.save_boe_with_rows(
            instance=boe, validated_data={"comments": "svc"}, item_rows=None, allotments=None,
        )
        self.assertEqual(out.pk, boe.pk)
        boe.refresh_from_db()
        self.assertEqual(boe.comments, "svc")

    def test_create_null_date_collision_raises_validation_error(self):
        self.make_boe(self.company, number="SVC002")
        with self.assertRaises(serializers.ValidationError) as ctx:
            boe_service.save_boe_with_rows(
                validated_data=self._header(bill_of_entry_number="SVC002", bill_of_entry_date=None),
                item_rows=[], allotments=None,
            )
        self.assertIn("existing_boe_id", ctx.exception.detail)
