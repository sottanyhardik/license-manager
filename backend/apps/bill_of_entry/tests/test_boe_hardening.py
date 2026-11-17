"""
WS5 hardening tests: no business-semantics or success-shape change.

  * nested update: a ProtectedError on the orphan-row delete is a DRF 400;
  * merge: both endpoints write exactly one MERGE_BOE log, from the service;
  * export: per-BOE totals come from the prefetched rows (same Decimals,
    no per-BOE SUM queries);
  * retrieve: allotment metadata unchanged, BOE loaded once;
  * bulk hide/restore: ids normalised to int, de-duplicated in order,
    unparseable values reported in `failed`.
"""
from decimal import Decimal

from django.db import connection
from django.db.models import Prefetch
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.bill_of_entry.api.views import BillOfEntryViewSet
from apps.bill_of_entry.models import BillOfEntryModel, OTH_INVOICE_MARKER, RowDetails
from apps.bill_of_entry.services import boe_service
from apps.bill_of_entry.services.boe_service import hide_boe, hide_boes_bulk, restore_boes_bulk
from apps.bill_of_entry.tests.test_boe_api_contract import (
    LOCMEM_CACHES, BoeApiFixtureMixin, boe_detail_url,
)
from apps.core.constants import DEC_0
from apps.reconciliation.models import ReconciliationLog


@override_settings(CACHES=LOCMEM_CACHES)
class NestedUpdateProtectedRowTests(BoeApiFixtureMixin, TestCase):
    def test_protected_orphan_row_is_400_with_row_id_and_rolls_back(self):
        from apps.reconciliation.services.allocation_service import create_invoice_boe_allocation
        from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin

        company = self.make_company()
        license_obj = self.make_license(company)
        keep_item = self.make_item(license_obj, 1)
        omit_item = self.make_item(license_obj, 2)
        boe = self.make_boe(company)
        kept = self.make_debit_row(boe, keep_item, cif_fc=Decimal("100.00"), qty=Decimal("10.000"))
        omitted = self.make_debit_row(boe, omit_item, cif_fc=Decimal("200.00"), qty=Decimal("20.000"))
        helper = ReconciliationFixtureMixin()
        line = helper.make_trade_line(helper.make_sale_trade(company), omit_item, cif_fc=Decimal("200.00"))
        create_invoice_boe_allocation(
            line, omitted, qty=DEC_0, cif_fc=Decimal("200.00"), cif_inr=Decimal("16900.00"), user=None,
        )

        response = self.client_for(self.make_role_user("BOE_MANAGER")).patch(boe_detail_url(boe.id), {
            "comments": "edited",
            "item_details": [self.row_payload(keep_item, Decimal("100.00"), Decimal("10.000"), row_id=kept.id)],
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(response.data.keys()), ["item_details"])
        message = str(response.data["item_details"])
        self.assertIn(str(omitted.id), message)
        self.assertNotIn(str(kept.id) + ",", message)
        self.assertTrue(RowDetails.objects.filter(id=omitted.id).exists())
        boe.refresh_from_db()
        self.assertNotEqual(boe.comments, "edited")

    def test_unprotected_orphan_row_is_still_deleted(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        keep_item = self.make_item(license_obj, 1)
        omit_item = self.make_item(license_obj, 2)
        boe = self.make_boe(company)
        kept = self.make_debit_row(boe, keep_item, cif_fc=Decimal("100.00"), qty=Decimal("10.000"))
        omitted = self.make_debit_row(boe, omit_item, cif_fc=Decimal("200.00"), qty=Decimal("20.000"))

        response = self.client_for(self.make_role_user("BOE_MANAGER")).patch(boe_detail_url(boe.id), {
            "item_details": [self.row_payload(keep_item, Decimal("100.00"), Decimal("10.000"), row_id=kept.id)],
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(RowDetails.objects.filter(id=omitted.id).exists())


@override_settings(CACHES=LOCMEM_CACHES)
class MergeAuditTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)
        self.user = self.make_role_user("BOE_MANAGER", "TRADE_MANAGER")

    def _logs(self):
        return ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_MERGE_BOE)

    def test_service_writes_one_log_with_user_and_message(self):
        target = self.make_boe(self.company)
        source = self.make_boe(self.company)
        self.make_debit_row(source, self.item, cif_fc=Decimal("100.00"))
        source_id = source.id

        result = boe_service.merge_boe(target, source_id, user=self.user)

        log = self._logs().get()
        self.assertEqual(log.bill_of_entry_id, target.id)
        # D4 (flipped from exact {target_boe_id, source_boe_id} / {message}):
        # the payload is extended additively (swapped flag, moved row ids, ...).
        self.assertEqual(log.before["target_boe_id"], target.id)
        self.assertEqual(log.before["source_boe_id"], source_id)
        self.assertEqual(log.before["swapped"], False)
        self.assertEqual(log.after["message"], result["message"])
        self.assertEqual(log.after["swapped"], False)
        self.assertEqual(len(log.after["moved_row_ids"]), 1)
        self.assertEqual(log.user_id, self.user.id)
        # D4 (flipped from {success, message, boe}): additive keys.
        self.assertEqual(set(result.keys()), {"success", "message", "boe", "target_boe_id", "swapped"})
        self.assertEqual(result["target_boe_id"], target.id)
        self.assertFalse(result["swapped"])

    def test_service_without_user_logs_null_user(self):
        target = self.make_boe(self.company)
        source = self.make_boe(self.company)

        boe_service.merge_boe(target, source.id)

        self.assertIsNone(self._logs().get().user_id)

    def test_failed_merge_writes_no_log(self):
        target = self.make_boe(self.company)
        with self.assertRaises(ValueError):
            boe_service.merge_boe(target, target.id, user=self.user)
        with self.assertRaises(ValueError):
            boe_service.merge_boe(target, 999999999, user=self.user)
        self.assertFalse(self._logs().exists())

    def test_reconciliation_endpoint_still_writes_exactly_one_log(self):
        target = self.make_boe(self.company)
        source = self.make_boe(self.company)

        response = self.client_for(self.user).post(
            reverse("reconciliation:reconciliation-merge-boe"),
            {"target_boe_id": target.id, "source_boe_id": source.id}, format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._logs().count(), 1)
        self.assertEqual(self._logs().get().user_id, self.user.id)

    def test_reconciliation_endpoint_error_shape_unchanged(self):
        target = self.make_boe(self.company)

        response = self.client_for(self.user).post(
            reverse("reconciliation:reconciliation-merge-boe"),
            {"target_boe_id": target.id, "source_boe_id": target.id}, format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(response.data.keys()), ["detail"])
        self.assertFalse(self._logs().exists())

    def test_merge_locks_both_boes(self):
        target = self.make_boe(self.company)
        source = self.make_boe(self.company)

        with CaptureQueriesContext(connection) as ctx:
            boe_service.merge_boe(target, source.id)

        self.assertTrue(any("FOR UPDATE" in q["sql"] for q in ctx.captured_queries))


class ExportTotalsTests(BoeApiFixtureMixin, TestCase):
    def _queryset(self):
        return BillOfEntryModel.objects.select_related("company", "port").prefetch_related(
            Prefetch(
                "item_details",
                queryset=RowDetails.objects.select_related(
                    "sr_number", "sr_number__license", "sr_number__license__exporter",
                    "sr_number__license__port", "sr_number__hs_code",
                ),
            ),
        ).order_by("id")

    def _grouped_totals(self):
        grouped = BillOfEntryViewSet._group_boe(None, self._queryset())
        totals = {}
        for by_licence in grouped.values():
            for by_product in by_licence.values():
                for by_port in by_product.values():
                    for boes in by_port.values():
                        for data in boes:
                            totals[data["boe_number"]] = (
                                data["total_fc"], data["total_inr"], data["total_quantity"],
                            )
        return totals

    def test_group_boe_totals_match_model_and_do_not_scale_queries(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        item_2 = self.make_item(license_obj, 2)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("100.50"), qty=Decimal("1.250"))
        self.make_debit_row(boe, item_2, cif_fc=Decimal("200.25"), qty=Decimal("2.500"))

        with CaptureQueriesContext(connection) as one_boe:
            totals = self._grouped_totals()
        fresh = BillOfEntryModel.objects.get(id=boe.id)
        self.assertEqual(
            totals[boe.bill_of_entry_number],
            (fresh.get_total_fc, fresh.get_total_inr, fresh.get_total_quantity),
        )

        for _ in range(3):
            extra = self.make_boe(company)
            self.make_debit_row(extra, item, cif_fc=Decimal("10.00"), qty=Decimal("1.000"))
        with CaptureQueriesContext(connection) as four_boes:
            totals = self._grouped_totals()

        self.assertEqual(len(totals), 4)
        self.assertEqual(len(four_boes.captured_queries), len(one_boe.captured_queries))

    def test_empty_boe_totals_default_like_sql(self):
        company = self.make_company()
        boe = self.make_boe(company)

        totals = self._grouped_totals()

        fresh = BillOfEntryModel.objects.get(id=boe.id)
        self.assertEqual(
            totals[boe.bill_of_entry_number],
            (fresh.get_total_fc, fresh.get_total_inr, fresh.get_total_quantity),
        )


@override_settings(CACHES=LOCMEM_CACHES)
class RetrieveAllotmentMetadataTests(BoeApiFixtureMixin, TestCase):
    def test_retrieve_metadata_lists_current_allotments(self):
        company = self.make_company()
        boe = self.make_boe(company)
        first = self.make_allotment(company)
        second = self.make_allotment(company)
        boe.allotment.add(first, second)
        client = self.client_for(self.make_role_user("BOE_MANAGER"))

        response = client.get(boe_detail_url(boe.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(response.data["allotment"]), sorted([first.id, second.id]))
        metadata = response.data.get("metadata")
        if metadata and "allotment" in metadata.get("fields", {}):
            endpoint = metadata["fields"]["allotment"]["fk_endpoint"]
            ids = ",".join(map(str, response.data["allotment"]))
            self.assertEqual(
                endpoint, f"/allotments/?is_boe=false_or_current&current_boe_allotments={ids}",
            )

    def test_retrieve_loads_the_boe_row_once(self):
        company = self.make_company()
        boe = self.make_boe(company)
        boe.allotment.add(self.make_allotment(company))
        client = self.client_for(self.make_role_user("BOE_MANAGER"))
        table = BillOfEntryModel._meta.db_table

        with CaptureQueriesContext(connection) as ctx:
            response = client.get(boe_detail_url(boe.id))

        self.assertEqual(response.status_code, 200)
        boe_selects = [
            q["sql"] for q in ctx.captured_queries
            if q["sql"].startswith("SELECT") and f'FROM "{table}"' in q["sql"]
        ]
        self.assertEqual(len(boe_selects), 1, boe_selects)


class BulkIdNormalisationTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)

    def _boe(self):
        boe = self.make_boe(self.company)
        self.make_debit_row(boe, self.item, cif_fc=Decimal("100.00"))
        return boe

    def test_normalise_helper(self):
        ids, bad = boe_service._normalise_boe_ids([3, "3", " 4 ", "x", None, True, 1.5, 2, 4])
        self.assertEqual(ids, [3, 4, 2])
        self.assertEqual(bad, ["x", None, True, 1.5])

    def test_hide_dedupes_and_reports_unparseable(self):
        boe = self._boe()

        result = hide_boes_bulk([boe.id, str(boe.id), "abc"], user=None, reason="r")

        self.assertEqual([h["id"] for h in result["hidden"]], [boe.id])
        self.assertEqual(result["failed"], [{"id": "abc", "error": "No BOE matches that id."}])
        self.assertEqual(
            ReconciliationLog.objects.filter(action=ReconciliationLog.ACTION_HIDE_BOE, bill_of_entry=boe).count(), 1,
        )

    def test_hide_unknown_int_still_failed(self):
        result = hide_boes_bulk([999999999], user=None)
        self.assertEqual(result["failed"], [{"id": 999999999, "error": "No BOE matches that id."}])
        self.assertEqual(result["hidden"], [])

    def test_restore_accepts_string_ids(self):
        boe = self._boe()
        hide_boe(boe, user=None, reason="r")

        result = restore_boes_bulk([str(boe.id), "nope"], user=None)

        self.assertEqual([r["id"] for r in result["restored"]], [boe.id])
        self.assertEqual(result["failed"], [{"id": "nope", "error": "No BOE matches that id."}])
        boe.refresh_from_db()
        self.assertNotEqual(boe.invoice_no, OTH_INVOICE_MARKER)

    def test_restore_skipped_uses_int_ids(self):
        boe = self._boe()
        result = restore_boes_bulk([str(boe.id)], user=None)
        self.assertEqual(result["skipped"], [boe.id])
