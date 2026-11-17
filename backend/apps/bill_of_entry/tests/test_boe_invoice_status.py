"""BOE invoice_status field + filter (additive); balance resolver is called read-only."""
from decimal import Decimal

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.bill_of_entry.services.boe_invoice_status import invoice_status_for_boes
from apps.bill_of_entry.services.boe_service import hide_boe
from apps.bill_of_entry.tests.test_boe_api_contract import BOE_URL, LOCMEM_CACHES, BoeApiFixtureMixin
from apps.reconciliation.models import InvoiceBOEAllocation
from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin


@override_settings(CACHES=LOCMEM_CACHES)
class BoeInvoiceStatusTests(BoeApiFixtureMixin, ReconciliationFixtureMixin, TestCase):
    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER", superuser=True))
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)
        self.item2 = self.make_item(self.license, 2)

    # -- helpers ---------------------------------------------------------
    def _boe(self, invoice_no="", item=None):
        boe = self.make_boe(self.company, invoice_no=invoice_no)
        row = self.make_debit_row(boe, item or self.item, Decimal("100.00"))
        return boe, row

    def _allocate(self, row, status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=True):
        trade = self.make_sale_trade(self.company)
        line = self.make_trade_line(trade, row.sr_number, Decimal("100.00"))
        return InvoiceBOEAllocation.objects.create(
            trade_line=line, row_details=row, allocated_qty=Decimal("100"),
            allocated_cif_fc=Decimal("100"), allocated_cif_inr=Decimal("8450"),
            status=status, is_current=is_current,
        )

    def _status(self, boe):
        return invoice_status_for_boes([boe])[boe.id]

    def _ids(self, **params):
        resp = self.client.get(BOE_URL, {"page_size": 50, **params})
        self.assertEqual(resp.status_code, 200, resp.content)
        return {r["id"] for r in resp.json()["results"]}

    # -- statuses --------------------------------------------------------
    def test_not_invoiced(self):
        boe, _ = self._boe()
        self.assertEqual(self._status(boe), "not_invoiced")

    def test_invoice_no_recorded(self):
        boe, _ = self._boe(invoice_no="INV-1")
        self.assertEqual(self._status(boe), "invoice_no_recorded")

    def test_invoiced_by_active_allocation_beats_invoice_no(self):
        boe, row = self._boe(invoice_no="INV-1")
        self._allocate(row)
        self.assertEqual(self._status(boe), "invoiced")

    def test_reversed_allocation_is_not_invoiced(self):
        boe, row = self._boe()
        self._allocate(row, status=InvoiceBOEAllocation.STATUS_REVERSED)
        self.assertEqual(self._status(boe), "not_invoiced")

    def test_oth_without_hide_log_is_invoice_no_recorded(self):
        # Legacy free-text 'OTH' is not hidden unless the audit history says so.
        boe, _ = self._boe(invoice_no="OTH")
        self.assertEqual(self._status(boe), "invoice_no_recorded")

    def test_non_current_active_allocation_is_not_invoiced(self):
        boe, row = self._boe()
        self._allocate(row, is_current=False)
        self.assertEqual(self._status(boe), "not_invoiced")

    def test_unknown_status_value_is_400(self):
        resp = self.client.get(BOE_URL, {"invoice_status": "invoiced,bogus"})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("invoice_status", resp.json())

    def test_legacy_sale_trade_link_is_invoiced(self):
        boe, row = self._boe()
        trade = self.make_sale_trade(self.company, boes=[boe])
        self.make_trade_line(trade, self.item, Decimal("100.00"))
        self.assertEqual(self._status(boe), "invoiced")

    def test_multi_licence_boe_invoiced_via_one_licence(self):
        other_license = self.make_license(self.company)
        other_item = self.make_item(other_license, 1)
        boe, row = self._boe()
        self.make_debit_row(boe, other_item, Decimal("50.00"))
        self._allocate(row)  # represented only through self.license
        self.assertEqual(self._status(boe), "invoiced")

    def test_hidden_beats_invoiced(self):
        boe, row = self._boe()
        self._allocate(row)
        hide_boe(boe, user=None, reason="prev owner")
        boe.refresh_from_db()
        self.assertEqual(self._status(boe), "hidden")

    def test_serializer_exposes_status_and_label(self):
        boe, _ = self._boe(invoice_no="X1")
        data = self.client.get(f"{BOE_URL}{boe.id}/").json()
        self.assertEqual(data["invoice_status"], "invoice_no_recorded")
        self.assertEqual(data["invoice_status_label"], "Invoice no. recorded")

    # -- filter ----------------------------------------------------------
    def _mixed(self):
        not_inv, _ = self._boe()
        no_rec, _ = self._boe(invoice_no="INV-9")
        invd, row = self._boe()
        self._allocate(row)
        hid, _ = self._boe()
        hide_boe(hid, user=None, reason="prev owner")
        return not_inv, no_rec, invd, hid

    def test_filter_each_status_and_combinations(self):
        not_inv, no_rec, invd, hid = self._mixed()
        self.assertEqual(self._ids(invoice_status="not_invoiced"), {not_inv.id})
        self.assertEqual(self._ids(invoice_status="invoice_no_recorded"), {no_rec.id})
        self.assertEqual(self._ids(invoice_status="invoiced"), {invd.id})
        self.assertEqual(self._ids(invoice_status="hidden"), {hid.id})
        self.assertEqual(self._ids(invoice_status="invoiced,hidden"), {invd.id, hid.id})
        self.assertEqual(
            self._ids(invoice_status="not_invoiced,invoice_no_recorded"), {not_inv.id, no_rec.id}
        )

    def test_is_invoice_legacy_semantics_unchanged(self):
        not_inv, no_rec, invd, hid = self._mixed()
        # default: invoice_no empty (hidden BOEs carry 'OTH', so excluded)
        self.assertEqual(self._ids(), {not_inv.id, invd.id})
        self.assertEqual(self._ids(is_invoice="true"), {no_rec.id, hid.id})
        self.assertEqual(self._ids(is_invoice="all"), {not_inv.id, no_rec.id, invd.id, hid.id})

    def test_filter_config_labels(self):
        self._boe()
        fc = self.client.get(BOE_URL).json()["filter_config"]
        self.assertEqual(fc["is_invoice"]["label"], "Has Invoice No.")
        self.assertEqual(fc["invoice_status"]["label"], "Invoice Status")
        self.assertEqual(
            [c[0] for c in fc["invoice_status"]["choices"]],
            ["hidden", "invoiced", "invoice_no_recorded", "not_invoiced"],
        )

    def test_export_honours_invoice_status(self):
        not_inv, no_rec, invd, hid = self._mixed()
        captured = {}
        from apps.bill_of_entry.api import views_export as ve

        original = ve.build_export_queryset

        def spy(qs):
            captured["ids"] = set(qs.values_list("id", flat=True))
            return original(qs)

        ve.build_export_queryset = spy
        try:
            resp = self.client.get(BOE_URL + "export/", {"_export": "xlsx", "invoice_status": "invoiced"})
        finally:
            ve.build_export_queryset = original
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(captured["ids"], {invd.id})

    # -- query count -----------------------------------------------------
    # NOTE: the list endpoint has a PRE-EXISTING per-row cost from
    # RowDetailsSerializer.authoritative_available_cif (frozen balance math),
    # so the whole-request count is not constant.  What this feature must
    # guarantee is that invoice status itself is O(1): one bulk call per
    # page, never a per-instance fallback.
    def test_status_service_query_count_constant(self):
        def count(boes):
            with CaptureQueriesContext(connection) as ctx:
                invoice_status_for_boes(boes)
            return len(ctx.captured_queries)

        boe, _ = self._boe()
        n1 = count([boe])
        boes = [boe]
        for _ in range(9):
            b, row = self._boe()
            self._allocate(row)
            boes.append(b)
        self.assertEqual(count(boes) - n1, 0)

    def test_list_resolves_status_once_per_page(self):
        from unittest import mock

        for _ in range(10):
            self._boe()
        real = invoice_status_for_boes
        with mock.patch("apps.bill_of_entry.api.views.invoice_status_for_boes", side_effect=real) as view_call, \
                mock.patch("apps.bill_of_entry.api.serializers.invoice_status_for_boes",
                           side_effect=AssertionError("per-instance fallback")):
            resp = self.client.get(BOE_URL, {"page_size": 50})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["results"]), 10)
        self.assertEqual(view_call.call_count, 1)
