"""
Characterization tests (WS4): BOE write-path edge cases, pinned as they
behave TODAY. Gaps awaiting an owner decision are marked
"# CURRENT BEHAVIOUR — owner decision pending: <escalation>".
"""
from decimal import Decimal

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.allotment.models import AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, OTH_INVOICE_MARKER, RowDetails
from apps.bill_of_entry.services.boe_service import hide_boes_bulk
from apps.bill_of_entry.tests.test_boe_api_contract import (
    BOE_URL, LOCMEM_CACHES, BoeApiFixtureMixin, boe_detail_url,
)
from apps.core.constants import DEC_0
from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.signals import update_license_flags
from apps.reconciliation.models import InvoiceBOEAllocation, ReconciliationLog


@override_settings(CACHES=LOCMEM_CACHES)
class NestedRowOmissionTests(BoeApiFixtureMixin, TestCase):
    """PATCH with `item_details` deletes every existing row the client
    leaves out of the payload (serializers.py nested update)."""

    def setUp(self):
        self.user = self.make_role_user("BOE_MANAGER")
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item_keep = self.make_item(self.license, 1)
        self.item_omit = self.make_item(self.license, 2)
        self.boe = self.make_boe(self.company)
        self.kept = self.make_debit_row(self.boe, self.item_keep, cif_fc=Decimal("100.00"), qty=Decimal("10.000"))
        self.omitted = self.make_debit_row(self.boe, self.item_omit, cif_fc=Decimal("200.00"), qty=Decimal("20.000"))

    def _patch_keep_only(self, client):
        return client.patch(boe_detail_url(self.boe.id), {
            "comments": "edited",
            "item_details": [self.row_payload(self.item_keep, Decimal("100.00"), Decimal("10.000"), row_id=self.kept.id)],
        }, format="json")

    def test_omitting_row_with_protect_allocation_is_400_and_rolls_back(self):
        from apps.reconciliation.services.allocation_service import create_invoice_boe_allocation
        from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin

        helper = ReconciliationFixtureMixin()
        trade = helper.make_sale_trade(self.company)
        line = helper.make_trade_line(trade, self.item_omit, cif_fc=Decimal("200.00"))
        allocation = create_invoice_boe_allocation(
            line, self.omitted, qty=DEC_0, cif_fc=Decimal("200.00"), cif_inr=Decimal("16900.00"), user=None,
        )

        response = self._patch_keep_only(self.client_for(self.user, raise_request_exception=False))

        # WS5 (flipped from 500): the PROTECT FK's ProtectedError inside the
        # nested delete is mapped to a DRF 400 naming the protected row.
        self.assertEqual(response.status_code, 400)
        self.assertIn("item_details", response.data)
        self.assertIn(str(self.omitted.id), str(response.data["item_details"]))
        # perform_update's transaction.atomic() rolls the whole write back.
        self.assertTrue(RowDetails.objects.filter(id=self.omitted.id).exists())
        self.assertEqual(InvoiceBOEAllocation.objects.get(id=allocation.id).row_details_id, self.omitted.id)
        self.boe.refresh_from_db()
        self.assertNotEqual(self.boe.comments, "edited")

    def test_omitting_frozen_row_keeps_it(self):
        RowDetails.objects.filter(id=self.omitted.id).update(is_frozen=True)

        response = self._patch_keep_only(self.client_for(self.user))

        self.assertEqual(response.status_code, 200, response.data)
        # FLIPPED by owner decision D3 (was: the omitted frozen row was deleted).
        self.assertTrue(RowDetails.objects.filter(id=self.omitted.id).exists())
        self.assertTrue(RowDetails.objects.filter(id=self.kept.id).exists())

    def test_frozen_row_sent_with_new_values_is_rejected_400(self):
        """A frozen row that IS in the payload with changed values is rejected."""
        RowDetails.objects.filter(id=self.omitted.id).update(is_frozen=True)

        response = self.client_for(self.user).patch(boe_detail_url(self.boe.id), {
            "comments": "edited",
            "item_details": [
                self.row_payload(self.item_keep, Decimal("100.00"), Decimal("10.000"), row_id=self.kept.id),
                self.row_payload(self.item_omit, Decimal("999.00"), Decimal("99.000"), row_id=self.omitted.id),
            ],
        }, format="json")

        # FLIPPED by owner decision D3 (was: 200 with the change silently dropped).
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn(str(self.omitted.id), str(response.data["item_details"][1]))
        self.assertEqual(response.data["item_details"][0], {})
        self.assertEqual(RowDetails.objects.get(id=self.omitted.id).cif_fc, Decimal("200.000"))
        self.boe.refresh_from_db()
        self.assertNotEqual(self.boe.comments, "edited")


@override_settings(CACHES=LOCMEM_CACHES)
class NullDateDuplicatePostTests(BoeApiFixtureMixin, TestCase):
    """BOE POST is an `update_or_create` upsert on (number, date, port) while
    the DB constraint is (number, date).

    FLIPPED by owner decision D7 (was: null-date BOEs silently overwritten or
    duplicated): a create without a date whose number already exists is a 400
    carrying `existing_boe_id`.
    """

    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.port_a = self.make_port()
        self.port_b = self.make_port()

    def _post(self, port, comments, date=None, client=None):
        return (client or self.client).post(BOE_URL, {
            "bill_of_entry_number": "NULLDATE01",
            "bill_of_entry_date": date,
            "port": port.id,
            "company": self.company.id,
            "comments": comments,
        }, format="json")

    def test_same_port_null_date_second_post_is_rejected_400(self):
        first = self._post(self.port_a, "first")
        second = self._post(self.port_a, "second")

        self.assertEqual(first.status_code, 201, first.data)
        # FLIPPED by owner decision D7 (was: 201 overwriting the first BOE).
        self.assertEqual(second.status_code, 400, second.data)
        self.assertIn("bill_of_entry_date", second.data)
        self.assertEqual(second.data["existing_boe_id"], first.data["id"])
        self.assertEqual(BillOfEntryModel.objects.filter(bill_of_entry_number="NULLDATE01").count(), 1)
        self.assertEqual(BillOfEntryModel.objects.get(id=first.data["id"]).comments, "first")

    def test_different_port_null_date_second_post_is_rejected_400(self):
        first = self._post(self.port_a, "first")
        second = self._post(self.port_b, "second")

        self.assertEqual(first.status_code, 201, first.data)
        # FLIPPED by owner decision D7 (was: 201 creating a duplicate BOE).
        self.assertEqual(second.status_code, 400, second.data)
        self.assertEqual(second.data["existing_boe_id"], first.data["id"])
        self.assertEqual(BillOfEntryModel.objects.filter(bill_of_entry_number="NULLDATE01").count(), 1)

    def test_dated_duplicate_post_is_rejected_400(self):
        first = self._post(self.port_a, "first", date="2026-03-01")
        second = self._post(self.port_a, "second", date="2026-03-01")

        self.assertEqual(first.status_code, 201, first.data)
        # The serializer's UniqueTogetherValidator rejects a dated duplicate
        # before the upsert runs (it skips the check when date is null).
        self.assertEqual(second.status_code, 400)
        self.assertEqual(BillOfEntryModel.objects.get(id=first.data["id"]).comments, "first")


class HideBoesBulkStringIdTests(BoeApiFixtureMixin, TestCase):
    def test_string_id_is_normalised_and_boe_is_hidden(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("100.00"))

        result = hide_boes_bulk([str(boe.id)], user=None, reason="string id")

        # WS5 (flipped from "failed"): ids are normalised to int, so a
        # numeric string id now resolves to the existing BOE.
        self.assertEqual([h["id"] for h in result["hidden"]], [boe.id])
        self.assertEqual(result["failed"], [])
        self.assertEqual(result["licenses_refreshed"], [license_obj.id])
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, OTH_INVOICE_MARKER)
        self.assertEqual(
            ReconciliationLog.objects.filter(
                bill_of_entry=boe, action=ReconciliationLog.ACTION_HIDE_BOE,
            ).count(),
            1,
        )


@override_settings(CACHES=LOCMEM_CACHES)
class IndividualItemCeilingTests(BoeApiFixtureMixin, TestCase):
    """Nested INDIVIDUAL_ITEM CIF ceiling (`check_individual_item_cif_ceiling`).

    FLIPPED by owner decisions D12/D13 (was: the row's own debit was not added
    back, so an unchanged re-save failed).
    """

    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.license.individual_item_cif_override = True
        self.license.save()
        self.item = self.make_item(self.license, 1)
        self.item.cif_fc = Decimal("1000.00")
        self.item.save()
        self.boe = self.make_boe(self.company)
        self.row = self.make_debit_row(self.boe, self.item, cif_fc=Decimal("600.00"), qty=Decimal("6.000"))

    def _resave(self, cif_fc, with_id=True):
        return self.client.patch(boe_detail_url(self.boe.id), {
            "item_details": [self.row_payload(
                self.item, cif_fc, Decimal("6.000"), row_id=self.row.id if with_id else None,
            )],
        }, format="json")

    def test_unchanged_resave_adds_back_own_debit(self):
        # Live item balance is 1000 - 600 = 400; the row's own 600 is now
        # added back, so the ceiling for this row is 1000.
        response = self._resave(Decimal("600.00"))

        # FLIPPED by owner decision D13 (was: 400 on cif_fc).
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(RowDetails.objects.get(id=self.row.id).cif_fc, Decimal("600.000"))

    def test_resave_above_ceiling_with_own_debit_is_rejected(self):
        response = self._resave(Decimal("1000.01"))

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("cif_fc", response.data["item_details"][0])
        self.assertEqual(RowDetails.objects.get(id=self.row.id).cif_fc, Decimal("600.000"))

    def test_resave_within_remaining_balance_is_accepted(self):
        response = self._resave(Decimal("400.00"))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(RowDetails.objects.get(id=self.row.id).cif_fc, Decimal("400.000"))

    def test_legacy_mode_has_no_ceiling(self):
        self.license.individual_item_cif_override = None
        self.license.save()

        response = self._resave(Decimal("5000.00"))

        self.assertEqual(response.status_code, 200, response.data)


@override_settings(CACHES=LOCMEM_CACHES)
class BoeAllotmentM2MStoredBalanceTests(BoeApiFixtureMixin, TestCase):
    """Linking/unlinking an allotment through the BOE form changes the live
    allotment term (`has_linked_boe` exclusion) but nothing recomputes the
    stored `LicenseBalance` (no m2m_changed receiver on BOE.allotment).

    CURRENT BEHAVIOUR — owner decision pending: "the BOE-allotment M2M
    link/unlink has no m2m_changed recompute".
    """

    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("10000.00"))
        self.allotment = self.make_allotment(self.company, item=self.item, cif_fc=Decimal("2000.00"))
        self.other_allotment = self.make_allotment(self.company, item_name="Other")
        self.boe = self.make_boe(self.company)
        update_license_flags(self.license)
        self.license.refresh_from_db()
        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(self.license), Decimal("2000.00"))
        self.stored_unlinked = self.license.balance_cif
        self.assertEqual(self.stored_unlinked, Decimal("8000.00"))

    def _patch_allotments(self, ids):
        return self.client.patch(boe_detail_url(self.boe.id), {"allotment": ids}, format="json")

    def test_link_changes_live_term_but_not_stored_balance(self):
        response = self._patch_allotments([self.allotment.id])

        self.assertEqual(response.status_code, 200, response.data)
        self.allotment.refresh_from_db()
        self.assertTrue(self.allotment.is_boe)
        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(self.license), DEC_0)
        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(self.license), Decimal("10000.00"))
        self.license.refresh_from_db()
        # CURRENT BEHAVIOUR — owner decision pending: no m2m_changed recompute
        self.assertEqual(self.license.balance_cif, self.stored_unlinked)

    def test_unlink_by_replacement_changes_live_term_but_not_stored_balance(self):
        self._patch_allotments([self.allotment.id])
        update_license_flags(self.license)
        self.license.refresh_from_db()
        stored_linked = self.license.balance_cif
        self.assertEqual(stored_linked, Decimal("10000.00"))

        response = self._patch_allotments([self.other_allotment.id])

        self.assertEqual(response.status_code, 200, response.data)
        self.allotment.refresh_from_db()
        self.assertFalse(self.allotment.is_boe)
        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(self.license), Decimal("2000.00"))
        self.license.refresh_from_db()
        # CURRENT BEHAVIOUR — owner decision pending: no m2m_changed recompute
        self.assertEqual(self.license.balance_cif, stored_linked)

    def test_empty_allotment_list_does_not_unlink(self):
        self._patch_allotments([self.allotment.id])

        response = self._patch_allotments([])

        self.assertEqual(response.status_code, 200, response.data)
        # CURRENT BEHAVIOUR: `allotment: []` is ignored ("only if explicitly
        # provided with values"), so the client cannot clear the last link.
        self.assertEqual(list(self.boe.allotment.values_list("id", flat=True)), [self.allotment.id])
        self.assertTrue(AllotmentModel.objects.get(id=self.allotment.id).is_boe)


@override_settings(CACHES=LOCMEM_CACHES)
class BoeExportQueryCountTests(BoeApiFixtureMixin, TestCase):
    """Grouped BOE export (`/bill-of-entries/export/`) query count for N=1
    vs N=5 BOEs, pinned as measured today.

    WS5 (flipped from 3 per BOE): `_group_boe` / `_export_port_xlsx` now seed
    `get_total_fc/inr/quantity` from the prefetched rows via
    `BillOfEntrySerializer._seed_totals_from_prefetch` (same Decimals), so
    no per-BOE SUM() query is issued and the export is constant in N.
    """

    PER_BOE_TOTAL_QUERIES = 0

    def setUp(self):
        self.user = self.make_role_user("BOE_MANAGER")
        self.company = self.make_company()
        self.port = self.make_port()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)

    def _make_boes(self, n):
        for _ in range(n):
            boe = self.make_boe(self.company)
            BillOfEntryModel.objects.filter(id=boe.id).update(port=self.port)
            self.make_debit_row(boe, self.item, cif_fc=Decimal("10.00"))

    def _count(self, export_format):
        client = self.client_for(self.user)
        # Warm-up request so one-off lookups (e.g. cached master data) do
        # not skew the N=1 measurement.
        client.get(BOE_URL + "export/", {"_export": export_format})
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(BOE_URL + "export/", {"_export": export_format})
        self.assertEqual(response.status_code, 200)
        sqls = [q["sql"] for q in ctx.captured_queries]
        per_boe_sums = [s for s in sqls if "SUM(" in s and '"bill_of_entry_rowdetails"."bill_of_entry_id" =' in s]
        return len(sqls), len(per_boe_sums)

    def _assert_linear_in_boes(self, export_format):
        self._make_boes(1)
        total_one, sums_one = self._count(export_format)
        self._make_boes(4)
        total_five, sums_five = self._count(export_format)

        self.assertEqual(sums_one, 1 * self.PER_BOE_TOTAL_QUERIES)
        self.assertEqual(sums_five, 5 * self.PER_BOE_TOTAL_QUERIES)
        # Everything else is constant: the whole delta is the per-BOE SUMs.
        self.assertEqual(total_five - total_one, 4 * self.PER_BOE_TOTAL_QUERIES)

    def test_xlsx_export_query_count(self):
        self._assert_linear_in_boes("xlsx")

    def test_pdf_export_query_count(self):
        self._assert_linear_in_boes("pdf")

    def test_port_xlsx_export_query_count(self):
        self._make_boes(1)
        total_one, _ = self._count("port_xlsx")
        self._make_boes(4)
        total_five, _ = self._count("port_xlsx")
        # WS5 (flipped from 2 extra queries per BOE): constant in N.
        self.assertEqual(total_five - total_one, 0)
