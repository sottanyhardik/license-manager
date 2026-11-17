"""
Tests for `GET licenses/<id>/overview-transactions/`
(`apps/license/services/license_overview_transactions.py`).

Pins the approved grouping rules (OD-BA-a/b/c, D4) and the counting
invariants of doc 06 §7.4 / backend audit 07 (F1, F4, F5, F7, F8, F9, F14,
F21): no double counting, partitioned summaries, no cross-unit qty sums,
hidden-BOE parity with `overview-boes/`, and constant query counts.
"""
import uuid
from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import OTH_INVOICE_MARKER, BillOfEntryModel, RowDetails
from apps.core.constants import CREDIT
from apps.core.models import ItemNameModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


def _url(license_obj, **params):
    from urllib.parse import urlencode
    base = f"/api/licenses/{license_obj.id}/overview-transactions/"
    return f"{base}?{urlencode(params)}" if params else base


class OverviewTransactionsTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    # -- fixtures ---------------------------------------------------------
    def make_allotment(self, company, **kwargs):
        kwargs.setdefault("item_name", "Free text item")
        return AllotmentModel.objects.create(company=company, **kwargs)

    def make_allotment_item(self, allotment, item, cif_fc, qty=Decimal("10.000"), basis="ACTUAL"):
        return AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"), qty=qty,
            allocation_basis=basis,
        )

    def name(self, label):
        return ItemNameModel.objects.create(name=f"{label}-{uuid.uuid4().hex[:6]}")

    def get(self, license_obj, **params):
        resp = self.client.get(_url(license_obj, **params))
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        return resp.data

    @staticmethod
    def group(data, supplier_id):
        return next(g for g in data["results"] if g["supplier_id"] == supplier_id)

    @staticmethod
    def product(group, product_key):
        return next(p for p in group["products"] if p["product_key"] == product_key)

    # -- shape / basic grouping -------------------------------------------
    def test_groups_shape_and_supplier_source(self):
        exporter = self.make_company("Exporter")
        supplier = self.make_company("Supplier A")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        item.items.add(self.name("Paper"))
        boe = self.make_boe(supplier, number="BOE-1")
        self.make_debit_row(boe, item, cif_fc=Decimal("100.00"), qty=Decimal("5.000"))

        data = self.get(lic)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["current_page"], 1)
        group = data["results"][0]
        self.assertEqual(group["supplier_id"], supplier.id)
        self.assertEqual(group["supplier_name"], "Supplier A")
        self.assertEqual(group["supplier_source"], "company")
        self.assertFalse(group["is_missing_supplier"])
        prod = group["products"][0]
        self.assertEqual(prod["product_key"], item.id)
        self.assertEqual(prod["serial_number"], 1)
        self.assertFalse(prod["is_unmapped"])
        self.assertEqual(prod["summary"]["boe_debit_cif"], 100.0)
        bucket = prod["summary"]["boe_buckets"][0]
        self.assertEqual(bucket["transaction_type"], "D")
        self.assertEqual(bucket["record_count"], 1)
        self.assertEqual(bucket["line_count"], 1)
        self.assertEqual(bucket["qty_by_unit"], [{"unit": "kg", "qty": 5.0, "line_count": 1}])
        self.assertNotIn("available_qty", prod["summary"])
        self.assertEqual(data["totals"]["boe_debit_cif"], 100.0)

    def test_allotment_supplier_is_company_not_related_company(self):
        exporter = self.make_company("Exporter")
        company = self.make_company("Allot Co")
        related = self.make_company("Related Co")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        allot = self.make_allotment(company, related_company=related)
        self.make_allotment_item(allot, item, Decimal("50.00"))

        data = self.get(lic)
        self.assertEqual([g["supplier_id"] for g in data["results"]], [company.id])

    def test_suppliers_with_same_name_are_not_merged(self):
        exporter = self.make_company("Exporter")
        a = self.make_company("Same Name")
        b = self.make_company("Same Name")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        self.make_debit_row(self.make_boe(a), item, cif_fc=Decimal("10.00"))
        self.make_debit_row(self.make_boe(b), item, cif_fc=Decimal("20.00"))

        data = self.get(lic)
        self.assertEqual(data["count"], 2)
        self.assertEqual(sorted(g["supplier_id"] for g in data["results"]), sorted([a.id, b.id]))
        self.assertEqual(data["totals"]["boe_debit_cif"], 30.0)

    # -- double counting ----------------------------------------------------
    def test_boe_across_two_srs_not_double_counted(self):
        exporter = self.make_company("Exporter")
        supplier = self.make_company("Supplier")
        lic = self.make_license(exporter)
        sr1, sr2 = self.make_item(lic, 1), self.make_item(lic, 2)
        boe = self.make_boe(supplier, number="BOE-SPAN")
        self.make_debit_row(boe, sr1, cif_fc=Decimal("125.00"))
        self.make_debit_row(boe, sr2, cif_fc=Decimal("40.00"))

        group = self.group(self.get(lic), supplier.id)
        p1, p2 = self.product(group, sr1.id), self.product(group, sr2.id)
        self.assertEqual(p1["summary"]["boe_debit_cif"], 125.0)
        self.assertEqual(p2["summary"]["boe_debit_cif"], 40.0)
        self.assertEqual(p1["summary"]["boe_buckets"][0]["line_count"], 1)
        sup = group["summary"]
        self.assertEqual(sup["boe_debit_cif"], 165.0)
        self.assertEqual(sup["record_count_by_type"]["BOE"], 1)
        self.assertEqual(sup["line_count_by_type"]["BOE"], 2)
        self.assertEqual(sup["boe_buckets"][0]["record_count"], 1)

        recs = self.get(lic, supplier_id=supplier.id, product_key=sr1.id)
        self.assertEqual(recs["count"], 1)
        self.assertEqual(recs["results"][0]["cif_fc"], 125.0)
        self.assertEqual(recs["results"][0]["source_row_count"], 1)

    def test_credit_rows_are_a_separate_bucket_and_not_in_boe_debit_cif(self):
        exporter = self.make_company("Exporter")
        supplier = self.make_company("Supplier")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        boe = self.make_boe(supplier)
        self.make_debit_row(boe, item, cif_fc=Decimal("100.00"))
        RowDetails.objects.create(bill_of_entry=boe, sr_number=item, transaction_type=CREDIT,
                                  cif_fc=Decimal("30.00"), cif_inr=Decimal("0"), qty=Decimal("1.000"))

        summary = self.group(self.get(lic), supplier.id)["summary"]
        by_tt = {b["transaction_type"]: b for b in summary["boe_buckets"]}
        self.assertEqual(by_tt["D"]["cif_fc"], 100.0)
        self.assertEqual(by_tt["C"]["cif_fc"], 30.0)
        self.assertEqual(summary["boe_debit_cif"], 100.0)

    def test_linked_allotment_in_linked_bucket_and_excluded_from_unlinked(self):
        exporter = self.make_company("Exporter")
        supplier = self.make_company("Supplier")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        linked = self.make_allotment(supplier)
        self.make_allotment_item(linked, item, Decimal("70.00"))
        boe = self.make_boe(supplier, number="BOE-LINK")
        boe.allotment.add(linked)
        open_allot = self.make_allotment(supplier)
        self.make_allotment_item(open_allot, item, Decimal("30.00"))

        summary = self.group(self.get(lic), supplier.id)["summary"]
        self.assertEqual(summary["unlinked_allotment_cif"], 30.0)
        self.assertEqual(summary["linked_allotment_cif"], 70.0)
        buckets = {b["is_linked_to_boe"]: b for b in summary["allotment_buckets"]}
        self.assertEqual(buckets[True]["cif_fc"], 70.0)
        self.assertEqual(buckets[False]["cif_fc"], 30.0)
        self.assertEqual(buckets[True]["allotment_type"], "AT")
        self.assertEqual(buckets[True]["allocation_basis"], "ACTUAL")

        recs = self.get(lic, supplier_id=supplier.id, product_key=item.id, record_type="ALLOTMENT")
        linked_row = next(r for r in recs["results"] if r["record_id"] == linked.id)
        self.assertTrue(linked_row["is_linked_to_boe"])
        self.assertEqual(linked_row["linked_boe_numbers"], ["BOE-LINK"])
        self.assertEqual(linked_row["status"], "Linked to BOE")
        self.assertEqual(linked_row["record_number"], f"ALT-{linked.id}")

    def test_plan_and_actual_rows_of_one_allotment_stay_separate(self):
        exporter = self.make_company("Exporter")
        supplier = self.make_company("Supplier")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        allot = self.make_allotment(supplier)
        self.make_allotment_item(allot, item, Decimal("10.00"), basis="ACTUAL")
        self.make_allotment_item(allot, item, Decimal("15.00"), basis="PLAN")

        summary = self.group(self.get(lic), supplier.id)["summary"]
        self.assertEqual(summary["record_count_by_type"]["ALLOTMENT"], 1)
        self.assertEqual(summary["line_count_by_type"]["ALLOTMENT"], 2)
        bases = {b["allocation_basis"]: b["cif_fc"] for b in summary["allotment_buckets"]}
        self.assertEqual(bases, {"ACTUAL": 10.0, "PLAN": 15.0})

    # -- parity -----------------------------------------------------------
    def test_boe_debit_cif_matches_engine_boe_debit_total(self):
        exporter = self.make_company("Exporter")
        s1, s2 = self.make_company("S1"), self.make_company("S2")
        lic = self.make_license(exporter)
        sr1, sr2 = self.make_item(lic, 1), self.make_item(lic, 2)
        b1 = self.make_boe(s1)
        self.make_debit_row(b1, sr1, cif_fc=Decimal("111.11"))
        self.make_debit_row(b1, sr2, cif_fc=Decimal("22.22"))
        self.make_debit_row(self.make_boe(s2), sr2, cif_fc=Decimal("33.33"))
        self.make_debit_row(self.make_boe(None), sr1, cif_fc=Decimal("4.44"))
        hidden = self.make_boe(s1, invoice_no=OTH_INVOICE_MARKER)
        self.make_debit_row(hidden, sr1, cif_fc=Decimal("999.00"))

        engine = LicenseBalanceCalculator.calculate_boe_debit_total(lic)
        data = self.get(lic)
        self.assertEqual(Decimal(str(data["totals"]["boe_debit_cif"])), engine)
        self.assertEqual(engine, Decimal("171.10"))

    def test_hidden_boe_exclusion_parity_with_overview_boes(self):
        exporter = self.make_company("Exporter")
        supplier = self.make_company("Supplier")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        self.make_debit_row(self.make_boe(supplier, number="VISIBLE"), item, cif_fc=Decimal("10.00"))
        # "OTH" without a hide log is ordinary legacy data and stays visible.
        legacy = BillOfEntryModel.objects.create(company=supplier, bill_of_entry_number="LEGACY-OTH",
                                                 invoice_no=OTH_INVOICE_MARKER)
        self.make_debit_row(legacy, item, cif_fc=Decimal("20.00"))
        hidden = self.make_boe(supplier, number="HIDDEN", invoice_no=OTH_INVOICE_MARKER)
        self.make_debit_row(hidden, item, cif_fc=Decimal("40.00"))

        boes = self.client.get(f"/api/licenses/{lic.id}/overview-boes/").data
        recs = self.get(lic, supplier_id=supplier.id, product_key=item.id)
        self.assertEqual(
            sorted(r["bill_of_entry_number"] for r in boes),
            sorted(r["record_number"] for r in recs["results"]),
        )
        self.assertNotIn("HIDDEN", [r["record_number"] for r in recs["results"]])
        self.assertEqual(self.get(lic)["totals"]["boe_debit_cif"], 30.0)

    # -- missing values / units / names -----------------------------------
    def test_null_company_is_explicit_group_sorted_last(self):
        exporter = self.make_company("Exporter")
        supplier = self.make_company("Zeta")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        self.make_debit_row(self.make_boe(None, number="NOCO"), item, cif_fc=Decimal("5.00"))
        self.make_debit_row(self.make_boe(supplier), item, cif_fc=Decimal("6.00"))

        data = self.get(lic)
        self.assertEqual([g["supplier_id"] for g in data["results"]], [supplier.id, None])
        none_group = data["results"][-1]
        self.assertTrue(none_group["is_missing_supplier"])
        self.assertIsNone(none_group["supplier_name"])
        self.assertEqual(none_group["supplier_label"], "No supplier recorded")
        self.assertEqual(none_group["summary"]["boe_debit_cif"], 5.0)

        recs = self.get(lic, supplier_id="null", product_key=item.id)
        self.assertEqual([r["record_number"] for r in recs["results"]], ["NOCO"])
        self.assertIsNone(recs["supplier_id"])

    def test_unmapped_sr_and_sr_with_two_names_counted_once(self):
        exporter = self.make_company("Exporter")
        supplier = self.make_company("Supplier")
        lic = self.make_license(exporter)
        unmapped = self.make_item(lic, 1)
        multi = self.make_item(lic, 2)
        multi.items.add(self.name("Alpha"), self.name("Beta"))
        boe = self.make_boe(supplier)
        self.make_debit_row(boe, unmapped, cif_fc=Decimal("10.00"))
        self.make_debit_row(boe, multi, cif_fc=Decimal("20.00"), qty=Decimal("2.000"))

        group = self.group(self.get(lic, search=""), supplier.id)
        u = self.product(group, unmapped.id)
        self.assertTrue(u["is_unmapped"])
        self.assertEqual(u["product_label"], "Unmapped product")
        m = self.product(group, multi.id)
        self.assertEqual(len(m["product_names"]), 2)
        self.assertEqual(m["summary"]["boe_debit_cif"], 20.0)
        self.assertEqual(m["summary"]["boe_buckets"][0]["qty_by_unit"][0]["qty"], 2.0)
        self.assertEqual(group["summary"]["boe_debit_cif"], 30.0)
        # Searching on a canonical name must not fan out either.
        searched = self.get(lic, search="Alpha")
        self.assertEqual(searched["totals"]["boe_debit_cif"], 20.0)

    def test_mixed_units_are_never_summed_together(self):
        exporter = self.make_company("Exporter")
        supplier = self.make_company("Supplier")
        lic = self.make_license(exporter)
        kg_item = self.make_item(lic, 1)
        pcs_item = self.make_item(lic, 2)
        pcs_item.unit = "pcs"
        pcs_item.save(update_fields=["unit"])
        boe = self.make_boe(supplier)
        self.make_debit_row(boe, kg_item, cif_fc=Decimal("1.00"), qty=Decimal("7.000"))
        self.make_debit_row(boe, pcs_item, cif_fc=Decimal("1.00"), qty=Decimal("3.000"))

        bucket = self.group(self.get(lic), supplier.id)["summary"]["boe_buckets"][0]
        self.assertEqual(
            bucket["qty_by_unit"],
            [{"unit": "kg", "qty": 7.0, "line_count": 1}, {"unit": "pcs", "qty": 3.0, "line_count": 1}],
        )
        self.assertNotIn("qty", bucket)

    # -- filters / pagination -----------------------------------------------
    def test_record_type_filter_and_pagination(self):
        exporter = self.make_company("Exporter")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        companies = [self.make_company(f"C{i:02d}") for i in range(3)]
        for c in companies:
            self.make_debit_row(self.make_boe(c), item, cif_fc=Decimal("1.00"))
        allot_only = self.make_company("Allot Only")
        self.make_allotment_item(self.make_allotment(allot_only), item, Decimal("2.00"))

        page1 = self.get(lic, page_size=2)
        self.assertEqual(page1["count"], 4)
        self.assertEqual(page1["total_pages"], 2)
        self.assertEqual([g["supplier_name"] for g in page1["results"]], ["Allot Only", "C00"])
        page2 = self.get(lic, page_size=2, page=2)
        self.assertEqual([g["supplier_name"] for g in page2["results"]], ["C01", "C02"])

        only_boe = self.get(lic, record_type="BOE")
        self.assertEqual(only_boe["count"], 3)
        self.assertEqual(only_boe["totals"]["unlinked_allotment_cif"], 0.0)

    def test_invalid_params_return_400(self):
        lic = self.make_license(self.make_company("Exporter"))
        for params in ({"record_type": "X"}, {"ordering": "bogus"}, {"date_from": "nope"},
                       {"supplier_id": "1"}, {"page": "0"}):
            resp = self.client.get(_url(lic, **params))
            self.assertEqual(resp.status_code, 400, params)

    def test_page_size_capped_at_200(self):
        lic = self.make_license(self.make_company("Exporter"))
        self.assertEqual(self.get(lic, page_size=1000)["page_size"], 200)

    # -- query budget -------------------------------------------------------
    def _populate(self, lic, n_suppliers, n_lines):
        items = [self.make_item(lic, i + 1) for i in range(2)]
        for item in items:
            item.items.add(self.name("N"))
        for s in range(n_suppliers):
            company = self.make_company(f"S{s}")
            for i in range(n_lines):
                boe = self.make_boe(company)
                for item in items:
                    self.make_debit_row(boe, item, cif_fc=Decimal("1.00"))
                allot = self.make_allotment(company)
                self.make_allotment_item(allot, items[i % 2], Decimal("1.00"))
                if i % 2:
                    boe.allotment.add(allot)
        return items

    def test_query_count_constant_in_suppliers_and_lines(self):
        small = self.make_license(self.make_company("E1"))
        small_items = self._populate(small, 1, 1)
        large = self.make_license(self.make_company("E2"))
        large_items = self._populate(large, 4, 5)

        # licence + BOE summary + allotment summary + companies + SRs + names
        with self.assertNumQueries(6):
            self.get(small)
        with self.assertNumQueries(6):
            data = self.get(large)
        self.assertEqual(data["count"], 4)

        sid_small = self.get(small)["results"][0]["supplier_id"]
        sid_large = data["results"][0]["supplier_id"]
        # licence + count + page + SR + names
        with self.assertNumQueries(5):
            self.get(small, supplier_id=sid_small, product_key=small_items[0].id)
        with self.assertNumQueries(5):
            self.get(large, supplier_id=sid_large, product_key=large_items[0].id)

    # -- permissions ----------------------------------------------------------
    def test_permissions_match_overview_boes(self):
        lic = self.make_license(self.make_company("Exporter"))
        anon = APIClient()
        self.assertIn(anon.get(_url(lic)).status_code, (401, 403))

        no_role = APIClient()
        no_role.force_authenticate(user=self.make_plain_user())
        self.assertEqual(no_role.get(_url(lic)).status_code, 403)
        self.assertEqual(no_role.get(f"/api/licenses/{lic.id}/overview-boes/").status_code, 403)

        viewer = self.make_plain_user()
        viewer.groups.add(Group.objects.get_or_create(name="BOE_VIEWER")[0])
        client = APIClient()
        client.force_authenticate(user=viewer)
        self.assertEqual(client.get(_url(lic)).status_code, 200)
        self.assertEqual(client.get(f"/api/licenses/{lic.id}/overview-boes/").status_code, 200)

    def test_lookup_by_license_number_and_404(self):
        lic = self.make_license(self.make_company("Exporter"))
        resp = self.client.get(f"/api/licenses/{lic.license_number}/overview-transactions/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["license_id"], lic.id)
        self.assertEqual(self.client.get("/api/licenses/NOPE/overview-transactions/").status_code, 404)

    # -- documented divergences from the balance engine (cif-balance-auditor F3) --
    def test_unlinked_allotment_cif_is_not_allocation_netted(self):
        """Pins `cif_basis`: an active BOEAllotmentAllocation without a BOE M2M link
        is not subtracted here, while the engine's calculate_allotment nets it."""
        from apps.reconciliation.models import BOEAllotmentAllocation

        exporter = self.make_company("Exporter")
        supplier = self.make_company("Supplier")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        allot = self.make_allotment(supplier)
        allot_item = self.make_allotment_item(allot, item, Decimal("100.00"))
        row = self.make_debit_row(self.make_boe(supplier), item, cif_fc=Decimal("60.00"))
        BOEAllotmentAllocation.objects.create(
            row_details=row, allotment_item=allot_item,
            allocated_qty=Decimal("1.0000"), allocated_cif_fc=Decimal("60.000"),
        )

        data = self.get(lic)
        self.assertEqual(data["totals"]["unlinked_allotment_cif"], 100.0)
        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(lic), Decimal("40.00"))
        self.assertIn("NOT allocation-netted", data["cif_basis"]["unlinked_allotment_cif"])

    def test_allotment_item_without_allotment_is_excluded_but_engine_counts_it(self):
        exporter = self.make_company("Exporter")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        AllotmentItems.objects.create(
            item=item, allotment=None, cif_fc=Decimal("50.00"), cif_inr=Decimal("0"),
            qty=Decimal("1.000"), allocation_basis="ACTUAL",
        )

        data = self.get(lic)
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["totals"]["unlinked_allotment_cif"], 0.0)
        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(lic), Decimal("50.00"))
        self.assertTrue(any("null allotment" in e for e in data["cif_basis"]["exclusions"]))

    def test_request_filters_scope_the_totals(self):
        exporter = self.make_company("Exporter")
        supplier = self.make_company("Supplier")
        lic = self.make_license(exporter)
        item = self.make_item(lic, 1)
        self.make_debit_row(self.make_boe(supplier), item, cif_fc=Decimal("100.00"))
        self.make_allotment_item(self.make_allotment(supplier), item, Decimal("30.00"))

        unfiltered = self.get(lic)["totals"]
        self.assertEqual((unfiltered["boe_debit_cif"], unfiltered["unlinked_allotment_cif"]), (100.0, 30.0))
        boe_only = self.get(lic, record_type="BOE")["totals"]
        self.assertEqual((boe_only["boe_debit_cif"], boe_only["unlinked_allotment_cif"]), (100.0, 0.0))

    def test_totals_equal_sum_of_buckets_and_suppliers_equal_sum_of_products(self):
        exporter = self.make_company("Exporter")
        s1, s2 = self.make_company("S1"), self.make_company("S2")
        lic = self.make_license(exporter)
        sr1, sr2 = self.make_item(lic, 1), self.make_item(lic, 2)
        b1 = self.make_boe(s1)
        self.make_debit_row(b1, sr1, cif_fc=Decimal("10.10"))
        self.make_debit_row(b1, sr2, cif_fc=Decimal("20.20"))
        RowDetails.objects.create(bill_of_entry=b1, sr_number=sr1, transaction_type=CREDIT,
                                  cif_fc=Decimal("3.30"), cif_inr=Decimal("0"), qty=Decimal("1.000"))
        self.make_debit_row(self.make_boe(s2), sr2, cif_fc=Decimal("40.40"))
        linked = self.make_allotment(s1)
        self.make_allotment_item(linked, sr1, Decimal("5.50"))
        self.make_boe(s1).allotment.add(linked)
        open_allot = self.make_allotment(s2)
        self.make_allotment_item(open_allot, sr1, Decimal("6.60"))
        self.make_allotment_item(open_allot, sr2, Decimal("7.70"), basis="PLAN")

        def from_buckets(summary):
            return {
                "boe_debit_cif": sum(b["cif_fc"] for b in summary["boe_buckets"] if b["transaction_type"] == "D"),
                "unlinked_allotment_cif": sum(
                    b["cif_fc"] for b in summary["allotment_buckets"] if not b["is_linked_to_boe"]),
                "linked_allotment_cif": sum(
                    b["cif_fc"] for b in summary["allotment_buckets"] if b["is_linked_to_boe"]),
            }

        keys = ("boe_debit_cif", "unlinked_allotment_cif", "linked_allotment_cif")
        data = self.get(lic)
        grand = {k: 0.0 for k in keys}
        for group in data["results"]:
            sup = group["summary"]
            expected = from_buckets(sup)
            for k in keys:
                self.assertAlmostEqual(sup[k], expected[k], places=2)
                self.assertAlmostEqual(sup[k], sum(p["summary"][k] for p in group["products"]), places=2)
                grand[k] += sup[k]
            for prod in group["products"]:
                for k, v in from_buckets(prod["summary"]).items():
                    self.assertAlmostEqual(prod["summary"][k], v, places=2)
        for k in keys:
            self.assertAlmostEqual(data["totals"][k], grand[k], places=2)
        self.assertAlmostEqual(data["totals"]["boe_debit_cif"], 70.70, places=2)
        self.assertAlmostEqual(data["totals"]["unlinked_allotment_cif"], 14.30, places=2)
        self.assertAlmostEqual(data["totals"]["linked_allotment_cif"], 5.50, places=2)
