"""E1 Total Summary ↔ licence detail (owner report 2026-11-20: Total Summary inconsistent with the notification detail).

Root causes pinned here:
1. Each notification's Item Summary was built from the matrix (product-category columns, several Item Names merged), the
   Total Summary from the canonical projection — two row identities. Both now read the one projection.
2. The projection keyed by the merged cell's single ``canonical_item_id``: every source in a category cell was credited to
   the first Item Name, and every cell with no Item Name merged into one row named after whichever came first
   ("Packing Material :- PP film grade" holding nuts / starch HSNs). Cells now carry identity parts (Item Name × SION, or an
   explicit no-Item-Name / ambiguous identity with its source rows) and the projection aggregates the parts.
"""
import io
from datetime import date, timedelta
from decimal import Decimal

import openpyxl
from django.test import TestCase

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT, GE
from apps.core.models import (CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, NotificationNumber, PurchaseStatus,
                              SionNormClassModel)
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.item_pivot_item_summary import NO_ITEM_NAME_CATEGORY, project_item_summary
from apps.license.views.item_pivot_report import ItemPivotReportView

METRICS = (("total_qty", "adjusted_total_qty"), ("allotted_qty", "allotted_qty"), ("allotted_cif", "allotted_cif"),
           ("boe_used_qty", "debited_qty"), ("boe_used_cif", "boe_used_cif"), ("planned_qty", "effective_planned_qty"),
           ("planned_cif", "effective_planned_cif"))


class TotalSummaryIdentityTests(TestCase):
    def setUp(self):
        self.company = CompanyModel.objects.create(iec="E1TOTAL", name="E1 Total Summary Exporter")
        self.status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
        head = HeadSIONNormsModel.objects.create(name="E1 total summary")
        self.sion, _ = SionNormClassModel.objects.get_or_create(norm_class="E1", defaults={"head_norm": head, "is_active": True})
        self.hsn, _ = HSCodeModel.objects.get_or_create(hs_code="39021000")
        self.nut_hsn, _ = HSCodeModel.objects.get_or_create(hs_code="08029900")
        other_norm, _ = SionNormClassModel.objects.get_or_create(norm_class="A3627", defaults={"head_norm": head, "is_active": True})
        # PP is valid for E1 through the authoritative multi-norm link only (legacy FK another norm); FOIL through the FK.
        self.pp, _ = ItemNameModel.objects.get_or_create(name="PP TOTALTEST", defaults={"sion_norm_class": other_norm})
        self.pp.norms.add(self.sion)
        self.foil, _ = ItemNameModel.objects.get_or_create(name="ALUMINIUM FOIL TOTALTEST", defaults={"sion_norm_class": self.sion})
        self.e5_only, _ = ItemNameModel.objects.get_or_create(name="E5 ONLY TOTALTEST", defaults={"sion_norm_class": other_norm})
        self.l1 = self.licence("E1TOT-001", "N1/TEST")
        self.l2 = self.licence("E1TOT-002", "N2/TEST")
        self.mitc, _ = PurchaseStatus.objects.get_or_create(code="MI", defaults={"label": "MITC"})
        self.l3 = self.licence("E1TOT-003", "N2/TEST", status=self.mitc)  # same notification, other company
        # l1: PP planned; FOIL unplanned with the same HSN and the same packing description (same matrix category column)
        self.pp_src = self.item(self.l1, 1, "Packing Material - PP", "1000", "5000", names=[self.pp])
        self.foil_src = self.item(self.l1, 2, "Packing Material - PP", "400", "2000", names=[self.foil])
        LicenseItemPlan.objects.create(license=self.l1, import_item=self.pp_src, item_name=self.pp, planned_quantity=Decimal("100"),
                                       planned_cif_fc=Decimal("500"), allocation_provenance={"strategy": "STANDARD", "source_item_ids": [self.pp_src.pk], "sion": "E1"})
        # l1: a source with no Item Name and a source with two Item Names — neither is guessed onto an item
        self.unmapped = self.item(self.l1, 3, "Packing Material :- PP film grade", "70", "300", names=[], hsn=self.nut_hsn)
        self.ambiguous = self.item(self.l1, 4, "Packing Material - PP / Foil", "30", "100", names=[self.pp, self.foil])
        self.wrong_norm = self.item(self.l1, 5, "Packing film", "20", "60", names=[self.e5_only])
        # l2 (other notification): PP unplanned, with a BOE
        self.pp_src2 = self.item(self.l2, 1, "PP granules", "500", "2500", names=[self.pp])
        boe = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="E1TOT-BOE", bill_of_entry_date=date.today(),
                                              exchange_rate=Decimal("80"), product_name="PP")
        RowDetails.objects.create(bill_of_entry=boe, sr_number=self.pp_src2, transaction_type=DEBIT, qty=Decimal("50"), cif_fc=Decimal("250"),
                                  cif_inr=Decimal("20000"))
        self.pp_src3 = self.item(self.l3, 1, "PP granules", "200", "900", names=[self.pp])

    def licence(self, number, notification, status=None):
        code, _ = NotificationNumber.objects.get_or_create(code=notification, defaults={"label": notification})
        lic = LicenseDetailsModel.objects.create(license_number=number, license_date=date.today() - timedelta(days=1),
                                                 license_expiry_date=date.today() + timedelta(days=60), exporter=self.company,
                                                 purchase_status=status or self.status, notification_number=code)
        LicenseExportItemModel.objects.create(license=lic, norm_class=self.sion, cif_fc=Decimal("10000"))
        return lic

    def item(self, lic, serial, description, qty, cif, *, names, hsn=None):
        row = LicenseImportItemsModel.objects.create(license=lic, serial_number=serial, hs_code=hsn or self.hsn, description=description,
                                                     quantity=Decimal(qty), available_quantity=Decimal(qty), cif_fc=Decimal(cif))
        row.items.set(names)
        return row

    def report(self, **filters):
        data = ItemPivotReportView().generate_report(min_balance=-10 ** 9, license_status="all", sion_norm="E1", **filters)
        ours = {self.l1.pk, self.l2.pk, self.l3.pk}
        groups = [g for g in data["notification_groups"] if {r["license_id"] for r in g["licenses"]} & ours]
        return data, groups

    def rows(self, projection):
        return {(r["canonical_item_id"], r["item_name"]): r for r in projection["item_summary"]}

    def test_total_summary_is_the_aggregation_of_every_licence_detail_cell_and_of_the_notification_summaries(self):
        data, groups = self.report()
        assert len(groups) == 3  # N1 · GLOBAL EXIM, N2 · GLOBAL EXIM, N2 · MITC
        grand = data["grand_total"]
        cells = [c for g in data["notification_groups"] for r in g["licenses"] for c in r["items"].values()]
        for summary_field, cell_field in METRICS:
            detail = sum((max(Decimal(str(c.get(cell_field) or 0)), 0) for c in cells), Decimal("0"))
            total = sum((Decimal(r[summary_field]) for r in grand["item_summary"]), Decimal("0"))
            notifications = sum((Decimal(r[summary_field]) for g in data["notification_groups"] for r in g["item_summary"]), Decimal("0"))
            assert total == detail == notifications, (summary_field, total, detail, notifications)
        check = grand["summary_check"]
        assert check["consistent"] and check["notifications_reconciled"]
        assert all(g["reconciliation"]["reconciled"] for g in groups)  # per licence

    def test_licence_count_is_distinct_and_states_its_notification_population(self):
        data, groups = self.report()
        check = data["grand_total"]["summary_check"]
        assert check["distinct_license_count"] == data["grand_total"]["license_count"] == sum(p["license_count"] for p in check["license_population"])
        pp = self.rows(data["grand_total"])[(self.pp.pk, "PP TOTALTEST")]
        assert pp["license_count"] == 3  # distinct licences (l1 plan, l2 and l3 unplanned), not cells

    def test_sources_without_a_single_item_name_are_not_attributed_with_their_source_rows(self):
        _data, groups = self.report()
        g1 = next(g for g in groups if any(r["license_id"] == self.l1.pk for r in g["licenses"]))
        rows = self.rows(g1)
        na = rows[(None, NO_ITEM_NAME_CATEGORY)]
        assert Decimal(na["total_qty"]) == Decimal("120")  # 70 unmapped + 30 ambiguous + 20 other-norm name, never PP / FOIL
        reasons = {(rec["import_item_id"], rec["reason"]) for rec in na["source_records"]}
        assert reasons == {(self.unmapped.pk, "no_item_name"), (self.ambiguous.pk, "ambiguous_item_name"),
                           (self.wrong_norm.pk, "item_name_not_valid_for_norm")}
        rec = next(rec for rec in na["source_records"] if rec["import_item_id"] == self.unmapped.pk)
        assert (rec["license_number"], rec["serial_number"], rec["hsn_code"]) == ("E1TOT-001", 3, "08029900")  # provenance kept
        assert "08029900" not in rows[(self.pp.pk, "PP TOTALTEST")]["hsn_codes"]  # nut HSN never on PP

    def test_different_item_names_sharing_hsn_and_category_stay_separate_rows(self):
        _data, groups = self.report()
        g1 = next(g for g in groups if any(r["license_id"] == self.l1.pk for r in g["licenses"]))
        rows = self.rows(g1)
        assert Decimal(rows[(self.pp.pk, "PP TOTALTEST")]["total_qty"]) == Decimal("1000")
        assert Decimal(rows[(self.foil.pk, "ALUMINIUM FOIL TOTALTEST")]["total_qty"]) == Decimal("400")
        assert rows[(self.foil.pk, "ALUMINIUM FOIL TOTALTEST")]["hsn_codes"] == ["39021000"]

    def test_same_item_under_two_norms_stays_two_rows(self):
        def cell(sion, qty):
            return {"canonical_item_id": 7, "item_name": "SUGAR", "sion": sion, "total_qty": qty, "adjusted_total_qty": qty,
                    "debited_qty": "0", "allotted_qty": "0", "boe_used_cif": "0", "allotted_cif": "0"}
        projection = project_item_summary([{"license_id": 1, "items": {"SUGAR:E1": cell("E1", "10"), "SUGAR:E5": cell("E5", "4")}}])
        assert sorted((r["sion"], r["total_qty"]) for r in projection["item_summary"]) == [("E1", "10.000"), ("E5", "4.000")]

    def test_boe_counted_once_and_excel_matches_the_screen(self):
        data, groups = self.report()
        pp = self.rows(data["grand_total"])[(self.pp.pk, "PP TOTALTEST")]
        assert Decimal(pp["boe_used_cif"]) == Decimal("250")  # the one BOE row, once
        response = ItemPivotReportView().export_to_excel_streaming(min_balance=-10 ** 9, license_status="all", sion_norm="E1")
        workbook = openpyxl.load_workbook(io.BytesIO(b"".join(response.streaming_content)), data_only=True)
        total = [[c.value for c in r] for r in workbook["TOTAL_Summary"].iter_rows()]
        names = [r[0] for r in total]
        assert "PP TOTALTEST" in names and "ALUMINIUM FOIL TOTALTEST" in names and NO_ITEM_NAME_CATEGORY in names
        excel_pp = next(r for r in total if r[0] == "PP TOTALTEST")
        assert Decimal(str(excel_pp[3])) == pp["license_count"] and Decimal(str(excel_pp[4])) == Decimal(pp["total_qty"])
        subtotal = next(r for r in total if r[0] == "SUBTOTAL")
        assert Decimal(str(subtotal[4])) == sum((Decimal(r["total_qty"]) for r in data["grand_total"]["item_summary"]), Decimal("0"))
        # each notification sheet's Item Summary lists the same canonical rows as its JSON projection
        for g in groups:
            sheet_rows = [[c.value for c in r] for sheet in workbook.worksheets if sheet.title != "TOTAL_Summary" for r in sheet.iter_rows()]
            for row in g["item_summary"]:
                assert any(r[0] and str(r[0]).endswith(row["item_name"]) for r in sheet_rows), row["item_name"]


    def test_default_population_includes_mitc_and_keeps_each_group_scoped(self):
        # The legacy MI constant is "NP"; MITC's code is "MI" — the API default dropped every MITC licence.
        data, groups = self.report()
        scopes = {(g["notification_number"], g["purchase_status"]["name"]): {r["license_number"] for r in g["licenses"]} for g in groups}
        assert scopes == {("N1/TEST", "Global Exim"): {"E1TOT-001"}, ("N2/TEST", "Global Exim"): {"E1TOT-002"}, ("N2/TEST", "MITC"): {"E1TOT-003"}}
        population = data["grand_total"]["summary_check"]["license_population"]
        assert any(p["purchase_status"] == "MITC" and p["license_count"] >= 1 for p in population)
        # an explicit purchase-status filter still scopes the report
        _data, only_ge = self.report(purchase_status="GE")
        assert all(g["purchase_status"]["name"] != "MITC" for g in only_ge)

    def test_item_name_valid_through_the_norms_link_is_a_mapping_not_unmapped(self):
        _data, groups = self.report()
        g2 = next(g for g in groups if any(r["license_id"] == self.l2.pk for r in g["licenses"]))
        assert (self.pp.pk, "PP TOTALTEST") in self.rows(g2)  # PP: legacy FK another norm, E1 via ItemNameModel.norms

    def test_mapped_item_without_target_is_distinct_from_a_missing_mapping(self):
        own = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="E1TOT-PP", bill_of_entry_date=date.today(),
                                              exchange_rate=Decimal("80"), product_name="PP")
        BillOfEntryModel.objects.filter(pk=own.pk).update(planning_target_item=self.pp, planning_mapping_status="MAPPED_EXPLICIT")
        RowDetails.objects.create(bill_of_entry=own, sr_number=self.pp_src, transaction_type=DEBIT, qty=Decimal("2"), cif_fc=Decimal("10"),
                                  cif_inr=Decimal("800"))
        boe = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="E1TOT-NOTARGET", bill_of_entry_date=date.today(),
                                              exchange_rate=Decimal("80"), product_name="FOIL")
        BillOfEntryModel.objects.filter(pk=boe.pk).update(planning_target_item=self.foil, planning_mapping_status="MAPPED_EXPLICIT")
        RowDetails.objects.create(bill_of_entry=boe, sr_number=self.pp_src, transaction_type=DEBIT, qty=Decimal("5"), cif_fc=Decimal("40"),
                                  cif_inr=Decimal("3200"))
        _data, groups = self.report()
        g1 = next(g for g in groups if any(r["license_id"] == self.l1.pk for r in g["licenses"]))
        rows = self.rows(g1)
        missing_target = next(r for r in g1["item_summary"] if r["item_name"].startswith("NOT ATTRIBUTED (TARGET"))
        assert Decimal(missing_target["boe_used_cif"]) == Decimal("40")  # mapped to FOIL, FOIL not planned on this source
        rec = g1["reconciliation"]["not_attributed_records"][0]
        assert (rec["reason"], rec["planning_target_item_id"]) == ("target_not_planned", self.foil.pk)
        assert Decimal(rows[(None, NO_ITEM_NAME_CATEGORY)]["boe_used_cif"]) == 0  # never relabelled as a missing mapping
        assert g1["reconciliation"]["reconciled"]

    def test_units_are_reported_and_never_silently_mixed(self):
        LicenseImportItemsModel.objects.filter(pk=self.pp_src3.pk).update(unit="mt")
        data, _groups = self.report()
        pp = self.rows(data["grand_total"])[(self.pp.pk, "PP TOTALTEST")]
        assert pp["mixed_units"] is True and set(pp["units"]) == {"KG", "MT"}
        foil = self.rows(data["grand_total"])[(self.foil.pk, "ALUMINIUM FOIL TOTALTEST")]
        assert foil["mixed_units"] is False

    def test_zero_entitlement_part_pools_its_usage_into_the_shared_balance(self):
        # Opus round 4 (M1): cell entitlement 100, part A debit 20, part B (same source, entitlement 0) debit 30 → the
        # cell's available 50 must be the parts' available too, and B is not an over-use of an entitlement it lacks.
        src = [{"import_item_id": 1}]
        part = lambda cid, total, debit: {"canonical_item_id": cid, "item_name": f"I{cid}", "sion": "E1", "total_qty": total,
                                           "adjusted_total_qty": total, "debited_qty": debit, "allotted_qty": "0", "boe_used_cif": "0",
                                           "allotted_cif": "0", "source_items": src}
        cell = {"canonical_item_id": 1, "item_name": "I1", "sion": "E1", "adjusted_total_qty": "100", "debited_qty": "50",
                "identity_parts": [part(1, "100", "20"), part(2, "0", "30")]}
        rows = {r["canonical_item_id"]: r for r in project_item_summary([{"license_id": 1, "items": {"K:E1": cell}}])["item_summary"]}
        assert Decimal(rows[1]["available_qty"]) + Decimal(rows[2]["available_qty"]) == Decimal("50")
        assert Decimal(rows[2]["over_utilized_qty"]) == 0 and Decimal(rows[1]["over_utilized_qty"]) == 0

    def test_summary_check_compares_the_projection_with_the_licence_cells(self):
        data, _groups = self.report()
        metrics = data["grand_total"]["summary_check"]["metrics"]
        assert all(Decimal(m["difference_to_cells"]) == 0 for k, m in metrics.items() if "difference_to_cells" in m)
        assert {"total_qty", "boe_used_cif", "planned_cif"} <= {k for k, m in metrics.items() if "licence_detail_cells" in m}
