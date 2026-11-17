"""A-2 option (i): the stored quantity writer is hidden-BOE aware.

BUSINESS-RULE CHANGE, A-2 option (i): APPROVED by the owner 2026-11-17 (landed in 9a4dcf94;
doc 11 §9 A-2), QUANTITY ONLY:
``apps.core.scripts.calculate_balance`` now excludes genuinely hidden BOE debit
rows from the stored ``debited_quantity`` / ``available_quantity`` exactly as
``ItemBalanceCalculator`` does.  Unchanged by design: the integer floor of the
stored ``available_quantity`` (Q-10), the CIF fields ``debited_value`` /
``available_value`` (hidden CIF still counted there), and no bulk refresh.

Before this change (pinned in doc 11 §6 L8) the L8 shape stored
``available_quantity=0`` and ``debited_quantity=12335``.
"""
import uuid
from decimal import Decimal



from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, OTH_INVOICE_MARKER
from apps.core.scripts import calculate_balance as writer
from apps.license.models import LicenseImportItemsModel
from apps.license.tests.test_quantity_parity import QuantityFixtureMixin

D = Decimal


def floor0(value):
    """The stored writer's existing rule: integer floor, never below 0."""
    return max(value.to_integral_value(rounding="ROUND_FLOOR"), D("0"))


class StoredAvailableQuantityHiddenBoeTests(QuantityFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.lic = self.make_license(self.company)

    def test_hidden_boe_excluded_from_stored_quantity_cif_unchanged(self):
        item = self.make_item(self.lic, "12335.890")
        self.debit(self.make_boe(self.company, hidden=True), item, "12335.000", cif="500.00")
        stored = self.stored(item)
        self.assertEqual(stored.available_quantity, D("12335"))  # was 0
        self.assertEqual(stored.debited_quantity, D("0"))  # was 12335
        self.assertEqual(stored.debited_value, D("500.00"))  # CIF out of scope: hidden CIF still counted
        self.assertEqual(stored.available_quantity, floor0(self.engine(item)))

    def test_restored_boe_counts_again(self):
        item = self.make_item(self.lic, "12335.890")
        boe = self.make_boe(self.company, hidden=True)
        self.debit(boe, item, "12335.000")
        self.restore_log(boe)
        stored = self.stored(item)
        self.assertEqual(stored.available_quantity, D("0"))  # floor(0.890)
        self.assertEqual(stored.debited_quantity, D("12335.00"))

    def test_oth_without_hide_log_is_not_hidden(self):
        item = self.make_item(self.lic, "100.000")
        boe = BillOfEntryModel.objects.create(
            company=self.company, bill_of_entry_number=str(uuid.uuid4().int)[:9],
            exchange_rate=D("84.50"), invoice_no=OTH_INVOICE_MARKER,
        )
        self.debit(boe, item, "40.000")
        stored = self.stored(item)
        self.assertEqual(stored.available_quantity, D("60"))
        self.assertEqual(stored.debited_quantity, D("40.00"))

    def test_mixed_visible_hidden_and_direct_sale_l7(self):
        item = self.make_item(self.lic, "58965.610")
        self.debit(self.make_boe(self.company), item, "19233.000", cif="100.00")
        self.debit(self.make_boe(self.company, hidden=True), item, "37767.000", cif="200.00")
        self.sale(self.company, item, "21314.000")
        stored = self.stored(item)
        self.assertEqual(self.engine(item), D("18418.610"))
        self.assertEqual(stored.available_quantity, D("18418"))  # was 0
        self.assertEqual(stored.debited_quantity, D("40547.00"))  # visible D + direct sale; was 78314
        self.assertEqual(stored.debited_value, D("300.00"))  # CIF unchanged

    def test_prefetch_path_equals_sql_path(self):
        item = self.make_item(self.lic, "1000.000")
        self.debit(self.make_boe(self.company), item, "100.000", cif="10.00")
        self.debit(self.make_boe(self.company, hidden=True), item, "250.000", cif="20.00")
        restored = self.make_boe(self.company, hidden=True)
        self.debit(restored, item, "5.500", cif="1.00")
        self.restore_log(restored)
        self.sale(self.company, item, "30.000")
        self.allot(self.company, item, "12.000")

        sql_item = LicenseImportItemsModel.objects.get(pk=item.pk)
        pre_item = LicenseImportItemsModel.objects.prefetch_related("item_details").get(pk=item.pk)
        self.assertIn("item_details", pre_item._prefetched_objects_cache)
        sql = writer._get_aggregated_values(sql_item)
        pre = writer._get_aggregated_values(pre_item)
        self.assertEqual(sql, pre)
        self.assertEqual(sql["debited_qty"], D("105.500"))
        self.assertIsInstance(sql["debited_qty"], Decimal)
        for fn in (writer.calculate_available_quantity, writer.calculate_debited_quantity,
                   writer.calculate_allotted_quantity, writer.calculate_debited_value):
            self.assertEqual(fn(sql_item, sql), fn(pre_item, pre), fn.__name__)
        self.assertEqual(writer.calculate_available_quantity(sql_item, sql), D("852"))
        self.assertEqual(writer.calculate_available_quantity(sql_item, sql), floor0(self.engine(item)))

    def test_api_db_consistency_with_and_without_hidden(self):
        plain = self.make_item(self.lic, "1253.620", serial=1)
        self.debit(self.make_boe(self.company), plain, "1014.000")
        hidden = self.make_item(self.lic, "500.500", serial=2)
        self.debit(self.make_boe(self.company, hidden=True), hidden, "500.000")
        for item in (plain, hidden):
            stored = self.stored(item)
            canonical = D(self.payload(stored)["available_quantity_canonical"])
            self.assertEqual(canonical, self.engine(item))
            self.assertEqual(stored.available_quantity, floor0(canonical))


class AllotmentGatingAfterHiddenBoeTests(QuantityFixtureMixin, TestCase):
    """An item whose only debit is on a hidden BOE becomes an allotment
    candidate (``available_quantity__gt=0``) after a normal signal recompute."""

    def setUp(self):
        self.company = self.make_company()
        self.lic = self.make_license(self.company)
        self.user = get_user_model().objects.create_superuser(
            username=f"qty_{uuid.uuid4().hex[:8]}", password="x", email=f"{uuid.uuid4().hex[:6]}@example.com")

    def candidates(self):
        return set(LicenseImportItemsModel.objects.filter(available_quantity__gt=0).values_list("id", flat=True))

    def test_hidden_only_debit_item_becomes_candidate_after_recompute(self):
        from apps.bill_of_entry.services.boe_service import hide_boe

        item = self.make_item(self.lic, "1000.000")
        boe = self.make_boe(self.company)
        with self.captureOnCommitCallbacks(execute=True):
            self.debit(boe, item, "1000.000")
        item.refresh_from_db()
        self.assertEqual(item.available_quantity, D("0"))
        self.assertNotIn(item.id, self.candidates())

        hide_boe(boe, self.user, reason="previous owner")
        item.refresh_from_db()
        # Hiding does not itself recompute stored item quantity (unchanged; A-10 not approved).
        self.assertEqual(item.available_quantity, D("0"))

        with self.captureOnCommitCallbacks(execute=True):
            item.save(update_fields=["description"])  # existing item post_save recompute path
        item.refresh_from_db()
        self.assertEqual(item.available_quantity, D("1000"))
        self.assertEqual(item.debited_quantity, D("0"))
        self.assertIn(item.id, self.candidates())

        client = APIClient()
        client.force_authenticate(self.user)
        allotment = AllotmentModel.objects.create(company=self.company, item_name="Gate", required_quantity=D("10"))
        resp = client.get(f"/api/allotment-actions/{allotment.id}/available-licenses/", {"debit_based_on": "ACTUAL"})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn(item.id, [row["id"] for row in resp.data["available_items"]])
