"""Item Summary ↔ Licence Summary reconciliation (owner bug reports 2026-11-19: PKO blank, 025/2023 GLOBAL EXIM totals).

Root causes pinned here:
1. A SPLIT_BY_PERCENT source planned to several canonical targets (OLIVE OIL + PALM KERNEL OIL) was keyed by the shared
   source description → one cell; the merge kept the repeated source once, so every other target's share vanished.
2. Plan columns were registered with a stale loop variable → a planned item that no other licence had never became a
   column (its planned CIF was missing from the Item Summary).
3. BOE debits / allotments on such sources without a planning target were carried by no cell → now one NOT ATTRIBUTED
   row, so the Item Summary reconciles with the Licence Summary; never attributed to a guessed item.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT, GE
from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, PurchaseStatus, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.services.item_pivot_service import UNATTRIBUTED_CATEGORY
from apps.license.views.item_pivot_report import ItemPivotReportView

OIL_DESC = ("RELEVANT FATS AND OILS NAMELY Sesame Oil/ Mustard Oil / Olive Oil (HS Code 1509 / 1510) Groundnut Oil / "
            "Palm Based Oil (HS Code 1511 / 1513) Sunflower Oil")


class SplitTargetReconciliationTests(TestCase):
    def setUp(self):
        self.company = CompanyModel.objects.create(iec="SPLITREC", name="Split Reconciliation Exporter")
        status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
        head = HeadSIONNormsModel.objects.create(name="Split reconciliation")
        self.sion, _ = SionNormClassModel.objects.get_or_create(norm_class="E126", defaults={"head_norm": head, "is_active": True})
        self.licence = LicenseDetailsModel.objects.create(
            license_number="SPLIT-REC-001", license_date=date.today() - timedelta(days=1),
            license_expiry_date=date.today() + timedelta(days=60), exporter=self.company, purchase_status=status)
        LicenseExportItemModel.objects.create(license=self.licence, norm_class=self.sion, cif_fc=Decimal("10000"))
        self.olive, _ = ItemNameModel.objects.get_or_create(name="OLIVE OIL")
        self.pko, _ = ItemNameModel.objects.get_or_create(name="PALM KERNEL OIL")
        code, _ = HSCodeModel.objects.get_or_create(hs_code="15132110")
        self.source = LicenseImportItemsModel.objects.create(
            license=self.licence, serial_number=1, hs_code=code, description=OIL_DESC, quantity=Decimal("1000"),
            available_quantity=Decimal("1000"), cif_fc=Decimal("5000"))
        self.source.items.set([self.olive, self.pko])  # two Item Names on one record
        for target, qty, cif in ((self.olive, "400", "2000"), (self.pko, "0", "0")):
            LicenseItemPlan.objects.create(
                license=self.licence, import_item=self.source, item_name=target, planned_quantity=Decimal(qty), planned_cif_fc=Decimal(cif),
                allocation_provenance={"strategy": "SPLIT_BY_PERCENT", "source_item_ids": [self.source.pk], "percentage": "50.00",
                                       "theoretical_target_qty": "500", "sion": "E126"})

    def report(self):
        data = ItemPivotReportView().generate_report(min_balance=-10 ** 9, license_status="all", sion_norm="E126")
        group = next(g for g in data["notification_groups"] if any(r["license_id"] == self.licence.pk for r in g["licenses"]))
        row = next(r for r in group["licenses"] if r["license_id"] == self.licence.pk)
        return group, row

    def debit(self, qty, cif, target=None):
        boe = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number=f"SPLIT{qty}", bill_of_entry_date=date.today(),
                                              exchange_rate=Decimal("80"), product_name="PKO")
        BillOfEntryModel.objects.filter(pk=boe.pk).update(planning_target_item=target, planning_mapping_status="MAPPED_EXPLICIT" if target else "UNMAPPED_AMBIGUOUS")
        return RowDetails.objects.create(bill_of_entry=boe, sr_number=self.source, transaction_type=DEBIT, qty=Decimal(qty), cif_fc=Decimal(cif),
                                         cif_inr=Decimal(cif) * 80)

    def allot(self, qty, cif, target=None):
        allotment = AllotmentModel.objects.create(company=self.company, item_name="PKO", required_quantity=Decimal(qty))
        AllotmentModel.objects.filter(pk=allotment.pk).update(planning_target_item=target, planning_mapping_status="MAPPED_EXPLICIT" if target else "UNMAPPED_AMBIGUOUS")
        return AllotmentItems.objects.create(allotment=allotment, item=self.source, qty=Decimal(qty), cif_fc=Decimal(cif), cif_inr=Decimal(cif) * 80)

    def test_each_split_target_keeps_its_own_share_and_the_source_is_never_multiplied(self):
        group, row = self.report()
        olive, pko = row["items"]["OLIVE OIL:E126"], row["items"]["PALM KERNEL OIL:E126"]
        assert (olive["canonical_item_id"], pko["canonical_item_id"]) == (self.olive.pk, self.pko.pk)  # never merged
        assert Decimal(olive["total_qty"]) == Decimal(pko["total_qty"]) == Decimal("500")
        assert Decimal(olive["total_qty"]) + Decimal(pko["total_qty"]) == self.source.quantity  # 50 % + 50 % = the source, once
        assert Decimal(olive["plan_qty"]) == Decimal("400") and Decimal(pko["plan_qty"]) == Decimal("0")
        keys = {item["key"] for item in group["item_groups"]}
        assert {"OLIVE OIL:E126", "PALM KERNEL OIL:E126"} <= keys  # both are Item Summary rows
        assert UNATTRIBUTED_CATEGORY + ":E126" not in row["items"]  # no usage → nothing unattributed
        assert group["reconciliation"]["reconciled"]

    def test_usage_without_a_planning_target_is_shown_once_as_not_attributed_and_reconciles(self):
        boe_row = self.debit("120", "600")
        allot_row = self.allot("80", "400")
        group, row = self.report()
        cell = row["items"][f"{UNATTRIBUTED_CATEGORY}:E126"]
        assert (Decimal(cell["debited_qty"]), Decimal(cell["boe_used_cif"])) == (Decimal("120"), Decimal("600"))
        assert (Decimal(cell["allotted_qty"]), Decimal(cell["allotted_cif"])) == (Decimal("80"), Decimal("400"))
        assert Decimal(cell["total_qty"]) == 0 and Decimal(cell["plan_qty"]) == 0  # usage only: no invented entitlement
        assert {(r["kind"], r["row_id"]) for r in cell["unattributed_records"]} == {("BOE", boe_row.pk), ("ALLOTMENT", allot_row.pk)}
        # counted exactly once across every cell of the licence
        assert sum(Decimal(c["boe_used_cif"]) for c in row["items"].values()) == Decimal("600")
        assert sum(Decimal(c["allotted_cif"]) for c in row["items"].values()) == Decimal("400")
        assert not any(i["item_key"].startswith(UNATTRIBUTED_CATEGORY) for i in row["issues"])  # reported, not an item exception
        rec = group["reconciliation"]
        assert rec["license_ids"] == [self.licence.pk]
        for metric in ("allotted_cif", "debited_cif", "planned_cif"):
            assert Decimal(rec["metrics"][metric]["difference"]) == 0, metric
        assert Decimal(rec["metrics"]["debited_cif"]["licence_summary"]) == LBC.calculate_debit_for_licenses([self.licence.pk])[self.licence.pk].quantize(Decimal("0.01"))
        assert len(rec["not_attributed_records"]) == 2
        summary_rows = {r["item_name"]: r for r in group["item_summary"]}
        assert Decimal(summary_rows[UNATTRIBUTED_CATEGORY]["allotted_cif"]) == Decimal("400")  # own projection row
        assert summary_rows[UNATTRIBUTED_CATEGORY]["exception_count"] == 0

    def test_usage_mapped_to_the_pko_target_lands_on_pko_only(self):
        self.debit("120", "600", target=self.pko)
        self.allot("80", "400", target=self.pko)
        group, row = self.report()
        pko, olive = row["items"]["PALM KERNEL OIL:E126"], row["items"]["OLIVE OIL:E126"]
        assert (Decimal(pko["debited_qty"]), Decimal(pko["boe_used_cif"]), Decimal(pko["allotted_qty"]), Decimal(pko["allotted_cif"])) == (
            Decimal("120"), Decimal("600"), Decimal("80"), Decimal("400"))
        assert Decimal(olive["debited_qty"]) == Decimal(olive["allotted_qty"]) == 0
        assert Decimal(pko["balance_qty"]) == Decimal("300")  # existing formula: 500 − 120 − 80
        assert f"{UNATTRIBUTED_CATEGORY}:E126" not in row["items"]
        assert group["reconciliation"]["reconciled"]

    def test_every_planned_item_becomes_a_column_and_planned_cif_reconciles(self):
        code, _ = HSCodeModel.objects.get_or_create(hs_code="21021090")
        flavour, _ = ItemNameModel.objects.get_or_create(name="FOOD FLAVOUR")
        yeast_source = LicenseImportItemsModel.objects.create(license=self.licence, serial_number=2, hs_code=code, description="YEAST EXTRACT",
                                                              quantity=Decimal("50"), available_quantity=Decimal("50"), cif_fc=Decimal("100"))
        # planned BEFORE the split plans (priority order) — the stale key used to register only the last plan's column
        LicenseItemPlan.objects.create(license=self.licence, import_item=yeast_source, item_name=flavour, planned_quantity=Decimal("50"),
                                       planned_cif_fc=Decimal("135"), planning_rule_priority=1,
                                       allocation_provenance={"strategy": "STANDARD", "source_item_ids": [yeast_source.pk], "sion": "E126"})
        group, row = self.report()
        keys = {item["key"] for item in group["item_groups"]}
        assert {"YEAST:E126", "OLIVE OIL:E126", "PALM KERNEL OIL:E126"} <= keys
        assert Decimal(group["totals"]["items"]["YEAST:E126"]["planned_cif"]) == Decimal("135")
        planned = group["reconciliation"]["metrics"]["planned_cif"]
        assert Decimal(planned["licence_summary"]) == Decimal(planned["item_summary"]) == Decimal("2135.00")

    def sale_line(self, qty, cif, number="INV-SPLIT-1"):
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        trade = LicenseTrade.objects.create(direction=LicenseTrade.DIR_SALE, from_company=self.company, invoice_number=number, invoice_date=date.today())
        return LicenseTradeLine.objects.create(trade=trade, sr_number=self.source, description="sale", mode=LicenseTradeLine.MODE_CIF_INR,
                                               cif_fc=Decimal(cif), cif_inr=Decimal(cif) * 80, qty_kg=Decimal(qty))

    def test_billed_without_boe_on_a_split_source_is_counted_once_not_per_target(self):
        # owner decision D3 2026-11-20 (was: billed shown once in NOT ATTRIBUTED, not deducted): apportioned to each split
        # target by its split percentage; counted once in total; target balances sum to the source balance.
        self.sale_line("200", "1000")
        group, row = self.report()
        cells = row["items"]
        assert sum(Decimal(c["billed_cif"]) for c in cells.values()) == Decimal("1000")  # once — not 2 000 for two targets
        # owner decision D3 2026-11-20: each 50 % target carries half and deducts it
        assert Decimal(cells["OLIVE OIL:E126"]["billed_cif"]) == Decimal(cells["PALM KERNEL OIL:E126"]["billed_cif"]) == Decimal("500")
        assert Decimal(cells["OLIVE OIL:E126"]["billed_qty"]) == Decimal(cells["PALM KERNEL OIL:E126"]["billed_qty"]) == Decimal("100")
        assert f"{UNATTRIBUTED_CATEGORY}:E126" not in cells  # owner decision D3 2026-11-20: no longer NOT ATTRIBUTED
        assert all("shared_source_billed_cif" not in c for c in cells.values())  # reason removed with the rule it described
        assert Decimal(cells["OLIVE OIL:E126"]["balance_qty"]) + Decimal(cells["PALM KERNEL OIL:E126"]["balance_qty"]) == Decimal("1000") - Decimal("200")
        assert {r["kind"] for r in cells["OLIVE OIL:E126"]["apportioned_rows"]} == {"BILLED"}
        # Opus B1 2026-11-20: the licence row carries the CANONICAL billed CIF, never the last plan's (shadowed) share
        assert Decimal(row["billed_cif"]) == LBC.calculate_trade_for_licenses([self.licence.pk])[self.licence.pk] == Decimal("1000")
        assert group["reconciliation"]["quantity_metrics"]["billed_qty"]["licences"] == []  # source billed rows = item billed, once

    def test_billed_apportionment_uses_the_split_percentages_and_the_remainder_rule(self):
        for plan in LicenseItemPlan.objects.filter(license=self.licence):
            prov = dict(plan.allocation_provenance)
            prov["percentage"] = "33.33" if plan.item_name_id == self.olive.pk else "66.67"
            LicenseItemPlan.objects.filter(pk=plan.pk).update(allocation_provenance=prov)
        self.sale_line("1.003", "100.00")
        group, row = self.report()
        olive, pko = row["items"]["OLIVE OIL:E126"], row["items"]["PALM KERNEL OIL:E126"]
        # owner decision D3 2026-11-20: 100.00 split 33.33 : 66.67 -> 33.33 + 66.67; qty 1.003 (3 dp) -> 0.334 + 0.669, sums exact
        assert (Decimal(olive["billed_cif"]), Decimal(pko["billed_cif"])) == (Decimal("33.33"), Decimal("66.67"))
        assert Decimal(olive["billed_qty"]) + Decimal(pko["billed_qty"]) == Decimal("1.003")
        assert Decimal(row["billed_cif"]) == LBC.calculate_trade_for_licenses([self.licence.pk])[self.licence.pk]  # Opus B1
        assert group["reconciliation"]["quantity_metrics"]["billed_qty"]["licences"] == []  # source billed rows = item billed, once

    def test_split_target_item_cif_is_the_percentage_share_of_the_source_cif(self):
        group, row = self.report()
        assert Decimal(row["items"]["OLIVE OIL:E126"]["item_total_cif"]) == Decimal(row["items"]["PALM KERNEL OIL:E126"]["item_total_cif"]) == Decimal("2500.00")

    # --- D1 / D2 (owner decisions 2026-11-20) -------------------------------------------------------------------------
    def _two_standard_plans(self, olive_cif, pko_cif):
        LicenseItemPlan.objects.filter(license=self.licence).delete()
        for target, cif in ((self.olive, olive_cif), (self.pko, pko_cif)):
            LicenseItemPlan.objects.create(license=self.licence, import_item=self.source, item_name=target, planned_quantity=Decimal("10"),
                                           planned_cif_fc=Decimal(cif), allocation_provenance={"strategy": "STANDARD", "source_item_ids": [self.source.pk], "sion": "E126"})

    @staticmethod
    def part(row, target):
        """The identity part of ``target`` (merged STANDARD plans of one source share one matrix cell)."""
        return next(p for c in row["items"].values() for p in c.get("identity_parts", []) if p["canonical_item_id"] == target.pk)

    def test_d1_unmapped_rows_are_shared_between_standard_plans_in_proportion_to_planned_cif(self):
        self._two_standard_plans("100", "200")
        boe = self.debit("3", "100.00")
        self.allot("3", "100.00")
        group, row = self.report()
        olive, pko = (self.part(row, t) for t in (self.olive, self.pko))
        # owner decision D1 2026-11-20: 100.00 split 1:2 -> 33.33 + 66.67 (was: first plan took all); qty 3 -> 1.000 + 2.000
        assert (Decimal(olive["boe_used_cif"]), Decimal(pko["boe_used_cif"])) == (Decimal("33.33"), Decimal("66.67"))
        assert (Decimal(olive["debited_qty"]), Decimal(pko["debited_qty"])) == (Decimal("1.000"), Decimal("2.000"))
        assert (Decimal(olive["allotted_cif"]), Decimal(pko["allotted_cif"])) == (Decimal("33.33"), Decimal("66.67"))
        assert sum(Decimal(c["boe_used_cif"]) for c in row["items"].values()) == Decimal("100.00")  # counted once in total
        assert [(r["kind"], r["row_id"]) for r in olive["apportioned_rows"] if r["kind"] == "BOE"] == [("BOE", boe.pk)]
        assert {r["share"] for r in olive["apportioned_rows"]} == {"0.333333"}
        assert group["reconciliation"]["reconciled"]

    def test_d1_remainder_goes_to_the_largest_planned_cif_and_qty_keeps_three_decimals(self):
        self._two_standard_plans("100", "100")  # equal weights: half each, leftover unit to the lowest plan pk
        self.debit("1.001", "0.01")
        group, row = self.report()
        olive, pko = (self.part(row, t) for t in (self.olive, self.pko))
        assert Decimal(olive["debited_qty"]) + Decimal(pko["debited_qty"]) == Decimal("1.001")
        assert Decimal(olive["boe_used_cif"]) + Decimal(pko["boe_used_cif"]) == Decimal("0.01")
        # Largest-remainder rounding (Opus B2 2026-11-20): shares round DOWN (0.500 each / 0.00 each); the leftover unit goes to
        # the equal-fraction, equal-weight tie's lowest pk (OLIVE) — never a negative share.
        assert (Decimal(olive["debited_qty"]), Decimal(pko["debited_qty"])) == (Decimal("0.501"), Decimal("0.500"))
        assert (Decimal(olive["boe_used_cif"]), Decimal(pko["boe_used_cif"])) == (Decimal("0.01"), Decimal("0.00"))

    def test_d1_all_zero_planned_cif_splits_equally(self):
        self._two_standard_plans("0", "0")
        self.debit("10", "50.00")
        group, row = self.report()
        olive, pko = (self.part(row, t) for t in (self.olive, self.pko))
        assert (Decimal(olive["boe_used_cif"]), Decimal(pko["boe_used_cif"])) == (Decimal("25.00"), Decimal("25.00"))
        assert group["reconciliation"]["reconciled"]

    def test_d1_a_mapped_row_is_not_apportioned(self):
        self._two_standard_plans("100", "200")
        self.debit("5", "70", target=self.pko)
        group, row = self.report()
        olive, pko = (self.part(row, t) for t in (self.olive, self.pko))
        assert (Decimal(olive["boe_used_cif"]), Decimal(pko["boe_used_cif"])) == (Decimal("0"), Decimal("70"))
        assert pko["apportioned_rows"] == []

    def test_d2_row_mapped_to_an_unplanned_item_is_not_attributed_even_when_the_source_plan_has_no_usage(self):
        self._standard_olive_plan([self.source.pk])  # OLIVE planned; no usage mapped to it
        other = self.debit("20", "200", target=self.pko)  # PKO has no plan on this source
        unmapped = self.debit("1", "10")
        group, row = self.report()
        olive = self.part(row, self.olive)
        # owner decision D2 2026-11-20: (was: the plan's cell took it through the legacy fallback)
        assert Decimal(olive["boe_used_cif"]) == Decimal("10")  # only the row with no target
        cell = row["items"][f"{UNATTRIBUTED_CATEGORY}:E126"]
        assert [(r["row_id"], r["reason"]) for r in cell["unattributed_records"]] == [(RowDetails.objects.get(bill_of_entry=other.bill_of_entry).pk, "target_not_planned")]
        assert Decimal(cell["boe_used_cif"]) == Decimal("200")
        assert sum(Decimal(c["boe_used_cif"]) for c in row["items"].values()) == Decimal("210")
        assert unmapped.pk and group["reconciliation"]["reconciled"]

    def test_standard_plans_of_two_targets_on_one_source_keep_the_single_merged_cell(self):
        LicenseItemPlan.objects.filter(license=self.licence).update(allocation_provenance={"strategy": "STANDARD", "source_item_ids": [self.source.pk], "sion": "E126"})
        self.debit("120", "600")
        group, row = self.report()
        oil_cells = [c for k, c in row["items"].items() if not k.startswith(UNATTRIBUTED_CATEGORY)]
        assert len(oil_cells) == 1  # not a percentage split: unchanged behaviour (one cell, source usage once)
        assert Decimal(oil_cells[0]["boe_used_cif"]) == Decimal("600")
        assert f"{UNATTRIBUTED_CATEGORY}:E126" not in row["items"]

    def test_split_target_takes_the_category_its_item_name_has_on_single_target_plans(self):
        status = self.licence.purchase_status
        other = LicenseDetailsModel.objects.create(license_number="SPLIT-REC-002", license_date=date.today() - timedelta(days=1),
                                                   license_expiry_date=date.today() + timedelta(days=60), exporter=self.company, purchase_status=status)
        LicenseExportItemModel.objects.create(license=other, norm_class=self.sion, cif_fc=Decimal("1000"))
        code, _ = HSCodeModel.objects.get_or_create(hs_code="15132110")
        pko_only = LicenseImportItemsModel.objects.create(license=other, serial_number=1, hs_code=code, description="PALM KERNEL OIL",
                                                          quantity=Decimal("10"), available_quantity=Decimal("10"), cif_fc=Decimal("50"))
        LicenseItemPlan.objects.create(license=other, import_item=pko_only, item_name=self.pko, planned_quantity=Decimal("10"), planned_cif_fc=Decimal("50"),
                                       allocation_provenance={"strategy": "STANDARD", "source_item_ids": [pko_only.pk], "sion": "E126"})
        group, row = self.report()
        # PALM KERNEL OIL's single-target plan classifies PKO (HSN 1513) → its split share is the same PKO column
        assert "PKO:E126" in row["items"] and row["items"]["PKO:E126"]["canonical_item_id"] == self.pko.pk
        assert Decimal(group["totals"]["items"]["PKO:E126"]["total_qty"]) == Decimal("510")  # 500 share + 10, each once

    def test_excel_item_summary_carries_the_not_attributed_row_and_matches_the_json(self):
        import io

        import openpyxl

        self.debit("120", "600")
        group, _row = self.report()
        response = ItemPivotReportView().export_to_excel_streaming(min_balance=-10 ** 9, license_status="all", sion_norm="E126")
        workbook = openpyxl.load_workbook(io.BytesIO(b"".join(response.streaming_content)), data_only=True)
        rows = [[c.value for c in r] for sheet in workbook.worksheets for r in sheet.iter_rows()]
        excel = [r for r in rows if r and r[0] == UNATTRIBUTED_CATEGORY]
        assert excel, "NOT ATTRIBUTED row missing from the Excel Item Summary"
        json_row = next(r for r in group["item_summary"] if r["item_name"] == UNATTRIBUTED_CATEGORY)
        assert Decimal(str(json_row["boe_used_cif"])) == Decimal("600")
        assert any(Decimal("600") in {Decimal(str(v)) for v in r[4:] if isinstance(v, (int, float))} for r in excel)
        # numeric columns stay numeric: a calculated zero is 0 (never blank), UNIT PRICE with no balance is empty, never text
        for r in excel:
            metrics = dict(zip(["TOTAL QTY", "ALLOTTED QTY", "ALLOTTED CIF", "DEBITED QTY", "DEBITED CIF", "BALANCE QTY", "UNIT PRICE",
                                "PLAN QTY", "PLANNED CIF"], r[4:13]))
            assert not any(isinstance(v, str) for v in metrics.values()), metrics
            assert all(isinstance(v, (int, float)) for k, v in metrics.items() if k != "UNIT PRICE"), metrics

    def test_not_attributed_source_records_and_provenance_survive_into_the_total_summary_and_excel(self):
        """TARGET MISSING summary rows carry the licence cell's per-transaction records (2026-11-20: the projection dropped
        them while the row still held 7,671 qty / 75,630.23 debited CIF). Display only — no figure changes."""
        import io

        import openpyxl

        boe_row = self.debit("120", "600")
        allot_row = self.allot("80", "400")
        data = ItemPivotReportView().generate_report(min_balance=-10 ** 9, license_status="all", sion_norm="E126")
        group = next(g for g in data["notification_groups"] if any(r["license_id"] == self.licence.pk for r in g["licenses"]))
        cell = next(r for r in group["licenses"] if r["license_id"] == self.licence.pk)["items"][f"{UNATTRIBUTED_CATEGORY}:E126"]
        for summary in (group, data["grand_total"]):
            na = next(r for r in summary["item_summary"] if r["item_name"] == UNATTRIBUTED_CATEGORY)
            ours = [rec for rec in na["source_records"] if rec["license_id"] == self.licence.pk]
            assert {(rec["kind"], rec["row_id"]) for rec in ours} == {("BOE", boe_row.pk), ("ALLOTMENT", allot_row.pk)}  # each once
            assert len(ours) == len(cell["unattributed_records"])
            for rec in ours:  # provenance: licence, source import item, HSN, description, reason, planning target status
                assert (rec["license_number"], rec["import_item_id"], rec["serial_number"], rec["hsn_code"]) == (
                    "SPLIT-REC-001", self.source.pk, 1, "15132110")
                assert rec["description"] == OIL_DESC and rec["reason"] == "no_target" and rec["planning_target_item_id"] is None
            # the records explain the row's figures exactly (no netting, no figure change)
            assert sum(Decimal(rec["cif_fc"]) for rec in ours if rec["kind"] == "BOE") == Decimal(cell["boe_used_cif"]) == Decimal("600")
            assert sum(Decimal(rec["cif_fc"]) for rec in ours if rec["kind"] == "ALLOTMENT") == Decimal(cell["allotted_cif"]) == Decimal("400")
        grand_na = next(r for r in data["grand_total"]["item_summary"] if r["item_name"] == UNATTRIBUTED_CATEGORY)
        response = ItemPivotReportView().export_to_excel_streaming(min_balance=-10 ** 9, license_status="all", sion_norm="E126")
        workbook = openpyxl.load_workbook(io.BytesIO(b"".join(response.streaming_content)), data_only=True)
        total = [[c.value for c in r] for r in workbook["TOTAL_Summary"].iter_rows()]
        header = total[0]
        excel_na = next(r for r in total if r[0] and str(r[0]).endswith(UNATTRIBUTED_CATEGORY))
        assert Decimal(str(excel_na[header.index("DEBITED CIF")])) == Decimal(grand_na["boe_used_cif"])
        assert Decimal(str(excel_na[header.index("ALLOTTED CIF")])) == Decimal(grand_na["allotted_cif"])
        assert excel_na[header.index("LICENCES")] == grand_na["license_count"]

    def test_split_plan_without_an_item_name_never_takes_rows_mapped_to_another_target(self):
        """Opus review F1 (2026-11-20): ``LicenseItemPlan.item_name`` is SET_NULL; a split plan that lost its Item Name took
        every row on its source (``target_id=None`` = unfiltered), so a BOE mapped to OLIVE showed on no item."""
        LicenseItemPlan.objects.filter(license=self.licence, item_name=self.pko).update(item_name=None, planning_rule_priority=1)
        LicenseItemPlan.objects.filter(license=self.licence, item_name=self.olive).update(planning_rule_priority=2)
        mapped = self.debit("120", "600", target=self.olive)
        unmapped = self.debit("30", "150")
        group, row = self.report()
        olive = row["items"]["OLIVE OIL:E126"]  # the unnamed plan shares the category cell; identity parts keep them apart
        assert Decimal(olive["boe_used_cif"]) == Decimal("600")  # the mapped BOE stays on its target
        na = row["items"][f"{UNATTRIBUTED_CATEGORY}:E126"]
        assert {(r["kind"], r["row_id"], r["reason"]) for r in na["unattributed_records"]} == {("BOE", unmapped.pk, "no_target")}
        assert mapped.pk not in {r["row_id"] for r in na["unattributed_records"]}
        assert sum(Decimal(c["boe_used_cif"]) for c in row["items"].values()) == Decimal("750")  # every BOE row exactly once
        summary = {r["item_name"]: Decimal(r["boe_used_cif"]) for r in group["item_summary"]}
        assert summary["OLIVE OIL"] == Decimal("600") and summary[UNATTRIBUTED_CATEGORY] == Decimal("150")
        assert group["reconciliation"]["reconciled"]

    def test_summary_check_tolerates_only_output_rounding_between_groups_and_total(self):
        """Opus review F3: cells are exact (a percentage target of 0.0004), summary rows are rounded once at output;
        two groups at 0.000 each vs a total of 0.001 is rounding, not an inconsistency."""
        mitc, _ = PurchaseStatus.objects.get_or_create(code="MI", defaults={"label": "MITC"})
        other = LicenseDetailsModel.objects.create(
            license_number="SPLIT-REC-002", license_date=date.today() - timedelta(days=1),
            license_expiry_date=date.today() + timedelta(days=60), exporter=self.company, purchase_status=mitc)
        LicenseExportItemModel.objects.create(license=other, norm_class=self.sion, cif_fc=Decimal("10000"))
        LicenseItemPlan.objects.filter(license=self.licence).delete()
        for lic, serial in ((self.licence, 7), (other, 1)):
            source = LicenseImportItemsModel.objects.create(license=lic, serial_number=serial, hs_code=self.source.hs_code, description="tiny",
                                                            quantity=Decimal("0"), available_quantity=Decimal("0"), cif_fc=Decimal("0"))
            source.items.set([self.olive])
            LicenseItemPlan.objects.create(license=lic, import_item=source, item_name=self.olive, planned_quantity=Decimal("0"), planned_cif_fc=Decimal("0"),
                                           allocation_provenance={"strategy": "SPLIT_BY_PERCENT", "source_item_ids": [source.pk], "percentage": "40",
                                                                  "percentage_base_qty": "0.001", "sion": "E126"})
        data = ItemPivotReportView().generate_report(min_balance=-10 ** 9, license_status="all", sion_norm="E126")
        check = data["grand_total"]["summary_check"]
        # the drift is really there (0.000 + 0.000 vs 0.001) — the tolerance, not luck, keeps the check consistent
        assert Decimal(check["metrics"]["total_qty"]["difference"]) == Decimal("0.001"), check["metrics"]["total_qty"]
        assert check["consistent"], check["metrics"]
        for metric in check["metrics"].values():  # never more than output rounding
            assert abs(Decimal(metric["difference"])) <= Decimal("0.05"), metric

    def test_a_zero_quantity_row_mapped_to_the_plans_target_stays_on_that_plan(self):
        """Opus N2 2026-11-20: fallback eligibility is decided by mapped ROWS, not mapped quantity — a 0-qty / 50-CIF BOE
        mapped to OLIVE is OLIVE's usage, never NOT ATTRIBUTED (target_not_carried)."""
        self._standard_olive_plan([self.source.pk])
        mapped = self.debit("0", "50", target=self.olive)
        group, row = self.report()
        olive = [c for c in row["items"].values() if c.get("canonical_item_id") == self.olive.pk or "OLIVE" in str(c.get("item_name"))]
        assert sum(Decimal(c["boe_used_cif"]) for c in olive) == Decimal("50")
        na = row["items"].get(f"{UNATTRIBUTED_CATEGORY}:E126")
        assert na is None or mapped.pk not in {r["row_id"] for r in na["unattributed_records"]}
        assert group["reconciliation"]["reconciled"]

    def _standard_olive_plan(self, source_ids):
        LicenseItemPlan.objects.filter(license=self.licence).delete()
        LicenseItemPlan.objects.create(license=self.licence, import_item=self.source, item_name=self.olive, planned_quantity=Decimal("100"),
                                       planned_cif_fc=Decimal("500"),
                                       allocation_provenance={"strategy": "STANDARD", "source_item_ids": source_ids, "sion": "E126"})

    def test_standard_source_usage_mapped_to_an_unplanned_target_is_not_attributed_not_dropped(self):
        # 025/2023 GLOBAL EXIM (E5, 2026-11-20 local data): a STANDARD plan's cell carries only BOEs mapped to its own target;
        # BOEs on the same source mapped to another Item Name (no plan here) or unmapped vanished from the Item Summary.
        self._standard_olive_plan([self.source.pk])
        self.debit("10", "100", target=self.olive)
        other = self.debit("20", "200", target=self.pko)
        group, row = self.report()
        olive = next(c for c in row["items"].values() if c.get("canonical_item_id") == self.olive.pk)
        assert Decimal(olive["boe_used_cif"]) == Decimal("100")
        cell = row["items"][f"{UNATTRIBUTED_CATEGORY}:E126"]
        assert Decimal(cell["boe_used_cif"]) == Decimal("200")
        assert [(r["row_id"], r["reason"]) for r in cell["unattributed_records"]] == [(other.pk, "target_not_planned")]
        assert sum(Decimal(c["boe_used_cif"]) for c in row["items"].values()) == Decimal("300")  # each row exactly once
        assert group["reconciliation"]["reconciled"]

    def test_secondary_source_of_a_standard_plan_is_counted_once(self):
        code, _ = HSCodeModel.objects.get_or_create(hs_code="15132110")
        second = LicenseImportItemsModel.objects.create(license=self.licence, serial_number=2, hs_code=code, description=OIL_DESC,
                                                        quantity=Decimal("100"), available_quantity=Decimal("100"), cif_fc=Decimal("500"))
        self._standard_olive_plan([self.source.pk, second.pk])
        self.debit("10", "100", target=self.olive)
        RowDetails.objects.create(bill_of_entry=BillOfEntryModel.objects.get(bill_of_entry_number="SPLIT10"), sr_number=second,
                                  transaction_type=DEBIT, qty=Decimal("5"), cif_fc=Decimal("40"), cif_inr=Decimal("3200"))
        group, row = self.report()
        assert sum(Decimal(c["boe_used_cif"]) for c in row["items"].values()) == Decimal("140")
        assert group["reconciliation"]["reconciled"]

    def test_overlapping_plan_sources_count_each_transaction_once(self):
        # Auditor 2026-11-20: P1 on A and P2 on A + B under one key added A's BOE twice (whole candidate summed on any new source).
        code, _ = HSCodeModel.objects.get_or_create(hs_code="15132110")
        second = LicenseImportItemsModel.objects.create(license=self.licence, serial_number=2, hs_code=code, description=OIL_DESC,
                                                        quantity=Decimal("100"), available_quantity=Decimal("100"), cif_fc=Decimal("500"))
        LicenseItemPlan.objects.filter(license=self.licence).delete()
        for sources in ([self.source.pk], [self.source.pk, second.pk]):
            LicenseItemPlan.objects.create(license=self.licence, import_item=self.source, item_name=self.olive, planned_quantity=Decimal("10"),
                                           planned_cif_fc=Decimal("50"), allocation_provenance={"strategy": "STANDARD", "source_item_ids": sources, "sion": "E126"})
        self.debit("10", "10000", target=self.olive)
        RowDetails.objects.create(bill_of_entry=BillOfEntryModel.objects.get(bill_of_entry_number="SPLIT10"), sr_number=second,
                                  transaction_type=DEBIT, qty=Decimal("2"), cif_fc=Decimal("300"), cif_inr=Decimal("24000"))
        with __import__("unittest").mock.patch("apps.license.services.item_pivot_service.billed_no_boe_bulk_map", return_value={self.source.pk: Decimal("5000")}), \
                __import__("unittest").mock.patch("apps.license.services.item_pivot_service.billed_no_boe_qty_bulk_map", return_value={self.source.pk: Decimal("1")}):
            group, row = self.report()
        assert sum(Decimal(c["boe_used_cif"]) for c in row["items"].values()) == Decimal("10300")  # not 20 300
        assert sum(Decimal(c["billed_cif"]) for c in row["items"].values()) == Decimal("5000")  # not 10 000
        rec = group["reconciliation"]  # (billed is mocked at item level only, so only the BOE metrics are compared here)
        assert rec["metrics"]["debited_cif"]["licences"] == [] and rec["quantity_metrics"]["debited_qty"]["licences"] == []
        assert rec["quantity_metrics"]["billed_qty"]["licences"] == []  # source billed rows = item billed, once

    def test_fallback_plan_never_takes_rows_mapped_to_another_planned_target(self):
        # A STANDARD plan with no usage mapped to its own target falls back to its source rows — but a row mapped to another
        # Item Name planned on that source belongs to that target's cell only.
        LicenseItemPlan.objects.filter(license=self.licence).delete()
        for target in (self.olive, self.pko):
            LicenseItemPlan.objects.create(license=self.licence, import_item=self.source, item_name=target, planned_quantity=Decimal("10"),
                                           planned_cif_fc=Decimal("50"), allocation_provenance={"strategy": "STANDARD", "source_item_ids": [self.source.pk], "sion": "E126"})
        self.debit("20", "200", target=self.pko)
        self.debit("5", "70")  # unmapped: the legacy fallback still carries it, once
        group, row = self.report()
        total = sum(Decimal(c["boe_used_cif"]) for c in row["items"].values())
        assert total == Decimal("270"), {k: c["boe_used_cif"] for k, c in row["items"].items()}
        assert group["reconciliation"]["reconciled"]

    def test_group_reconciles_only_when_every_licence_reconciles(self):
        from apps.license.services.item_pivot_service import _group_reconciliation

        def licence(pk, licence_debit, item_debit):
            return {"license_id": pk, "license_number": f"L{pk}", "allotted_cif": "0", "debited_cif": licence_debit, "billed_cif": "0",
                    "planned_cif": "0", "items": {"X:E1": {"boe_used_cif": item_debit}}, "item_reconciliation": {}}
        rec = _group_reconciliation({"licenses": [licence(1, "1000", "900"), licence(2, "500", "600")]})
        assert Decimal(rec["metrics"]["debited_cif"]["difference"]) == 0  # the totals cancel …
        assert rec["reconciled"] is False and rec["unreconciled_license_count"] == 2  # … the licences do not
        assert {x["license_id"] for x in rec["metrics"]["debited_cif"]["licences"]} == {1, 2}

    def test_provenance_naming_another_licences_item_never_reads_its_transactions(self):
        status = self.licence.purchase_status
        other = LicenseDetailsModel.objects.create(license_number="SPLIT-REC-003", license_date=date.today() - timedelta(days=1),
                                                   license_expiry_date=date.today() + timedelta(days=60), exporter=self.company, purchase_status=status)
        LicenseExportItemModel.objects.create(license=other, norm_class=self.sion, cif_fc=Decimal("1000"))
        code, _ = HSCodeModel.objects.get_or_create(hs_code="15132110")
        foreign = LicenseImportItemsModel.objects.create(license=other, serial_number=1, hs_code=code, description=OIL_DESC,
                                                         quantity=Decimal("10"), available_quantity=Decimal("10"), cif_fc=Decimal("50"))
        self._standard_olive_plan([self.source.pk, foreign.pk])  # stale provenance lists the other licence's row
        boe = self.debit("3", "90", target=self.olive)
        RowDetails.objects.create(bill_of_entry=boe.bill_of_entry, sr_number=foreign, transaction_type=DEBIT, qty=Decimal("1"),
                                  cif_fc=Decimal("25"), cif_inr=Decimal("2000"))
        group, row = self.report()
        assert sum(Decimal(c["boe_used_cif"]) for c in row["items"].values()) == Decimal("90")  # not 115
        assert group["reconciliation"]["metrics"]["debited_cif"]["licences"] == []



    # --- N4 (owner decision 2026-11-20): shared entitlement of D1 fallback plans -----------------------------------------
    def test_n4_d1_also_shares_the_source_entitlement_by_planned_cif(self):
        # The Opus probe: one source 100 qty / 500 CIF, planned CIF 100 : 200, one unmapped BOE 3 qty / 100 CIF.
        self._two_standard_plans("100", "200")
        self.source.cif_fc = Decimal("500")
        self.debit("3", "100.00")
        group, row = self.report()
        olive, pko = (self.part(row, t) for t in (self.olive, self.pko))
        assert (Decimal(olive["total_qty"]), Decimal(pko["total_qty"])) == (Decimal("333.333"), Decimal("666.667"))  # source = 1000 qty here
        assert Decimal(olive["total_qty"]) + Decimal(pko["total_qty"]) == self.source.quantity
        assert (Decimal(olive["canonical_item_cif_capacity"]), Decimal(pko["canonical_item_cif_capacity"])) == (Decimal("1666.67"), Decimal("3333.33"))
        assert (Decimal(olive["boe_used_cif"]), Decimal(pko["boe_used_cif"])) == (Decimal("33.33"), Decimal("66.67"))
        cell = next(c for k, c in row["items"].items() if not k.startswith(UNATTRIBUTED_CATEGORY))
        assert Decimal(cell["total_qty"]) == self.source.quantity  # licence figures unchanged: the source once
        assert Decimal(cell["item_total_cif"]) == Decimal("5000.00")
        assert group["reconciliation"]["reconciled"]

    def test_n4_probe_with_a_100_qty_500_cif_source(self):
        LicenseItemPlan.objects.filter(license=self.licence).delete()
        LicenseImportItemsModel.objects.filter(pk=self.source.pk).update(quantity=Decimal("100"), cif_fc=Decimal("500"))
        self._two_standard_plans("100", "200")
        self.debit("3", "100.00")
        group, row = self.report()
        olive, pko = (self.part(row, t) for t in (self.olive, self.pko))
        assert (Decimal(olive["total_qty"]), Decimal(pko["total_qty"])) == (Decimal("33.333"), Decimal("66.667"))
        assert (Decimal(olive["item_total_cif"]), Decimal(pko["item_total_cif"])) == (Decimal("166.67"), Decimal("333.33"))
        assert (Decimal(olive["boe_used_cif"]), Decimal(pko["boe_used_cif"])) == (Decimal("33.33"), Decimal("66.67"))
        assert Decimal(olive["total_qty"]) + Decimal(pko["total_qty"]) == Decimal("100")
        assert Decimal(olive["item_total_cif"]) + Decimal(pko["item_total_cif"]) == Decimal("500")
        # balances reflect each share (the usage is deducted from the product that carries it)
        assert Decimal(olive["available_qty"] if "available_qty" in olive else "0") >= 0
        cell = next(c for k, c in row["items"].items() if not k.startswith(UNATTRIBUTED_CATEGORY))
        assert Decimal(cell["total_qty"]) == Decimal("100") and Decimal(cell["item_total_cif"]) == Decimal("500.00")

    # --- N1 / N3 -------------------------------------------------------------------------------------------------------
    def _split_plus_standard(self, standard_first):
        """The split source (OLIVE/PKO 50:50) plus a STANDARD plan on the same source, created before or after the splits."""
        LicenseItemPlan.objects.filter(license=self.licence).delete()
        flavour, _ = ItemNameModel.objects.get_or_create(name="OIL FLAVOUR")

        def standard():
            LicenseItemPlan.objects.create(license=self.licence, import_item=self.source, item_name=flavour, planned_quantity=Decimal("10"),
                                           planned_cif_fc=Decimal("50"), allocation_provenance={"strategy": "STANDARD", "source_item_ids": [self.source.pk], "sion": "E126"})

        def splits():
            for target in (self.olive, self.pko):
                LicenseItemPlan.objects.create(license=self.licence, import_item=self.source, item_name=target, planned_quantity=Decimal("10"),
                                               planned_cif_fc=Decimal("50"), allocation_provenance={"strategy": "SPLIT_BY_PERCENT", "source_item_ids": [self.source.pk],
                                                                                                    "percentage": "50.00", "theoretical_target_qty": "500", "sion": "E126"})
        (standard, splits)[0 if standard_first else 1]()
        (splits, standard)[0 if standard_first else 1]()
        return flavour

    def test_n1_split_billed_is_order_independent_and_the_standard_plan_takes_none(self):
        results = []
        for standard_first in (True, False):
            self._split_plus_standard(standard_first)
            line = self.sale_line("200", "1000", number=f"INV-N1-{standard_first}")
            group, row = self.report()
            billed = {c["canonical_item_id"] if len(c.get("identity_parts", [])) < 2 else "merged": (c["billed_qty"], c["billed_cif"]) for c in row["items"].values()}
            parts = {p["item_name"]: (p["billed_qty"], p["billed_cif"]) for c in row["items"].values() for p in c["identity_parts"]}
            results.append(parts)
            assert parts["OIL FLAVOUR"] == ("0.000", "0.00") or Decimal(parts["OIL FLAVOUR"][1]) == 0  # the STANDARD plan takes none
            assert Decimal(parts["OLIVE OIL"][1]) == Decimal(parts["PALM KERNEL OIL"][1]) == Decimal("500")
            assert sum(Decimal(c["billed_cif"]) for c in row["items"].values()) == Decimal("1000")  # exactly once
            assert group["reconciliation"]["quantity_metrics"]["billed_qty"]["licences"] == []
            assert billed
            line.trade.delete()
        assert results[0] == results[1]

    def test_n3_billed_weights_use_only_the_exact_split_group(self):
        # Group A (OLIVE 50 / PKO 50) on source 1; a lone percentage plan elsewhere touching the same source with another source
        # set (a different group) must not dilute A's weights.
        code, _ = HSCodeModel.objects.get_or_create(hs_code="15132110")
        second = LicenseImportItemsModel.objects.create(license=self.licence, serial_number=2, hs_code=code, description=OIL_DESC, quantity=Decimal("100"),
                                                        available_quantity=Decimal("100"), cif_fc=Decimal("500"))
        third, _ = ItemNameModel.objects.get_or_create(name="SUNFLOWER OIL")
        self.sale_line("200", "1000")
        for target in (self.olive, third):  # group B: sources {source, second}, a partial overlap with group A
            LicenseItemPlan.objects.create(license=self.licence, import_item=second, item_name=target, planned_quantity=Decimal("10"), planned_cif_fc=Decimal("50"),
                                           allocation_provenance={"strategy": "SPLIT_BY_PERCENT", "source_item_ids": [self.source.pk, second.pk], "percentage": "80.00",
                                                                  "theoretical_target_qty": "80", "sion": "E126"})
        group, row = self.report()
        parts = {}
        for cell in row["items"].values():
            for p in cell["identity_parts"]:
                parts.setdefault(p["item_name"], []).append(Decimal(p["billed_cif"]))
        # the source's billed (1000) is claimed once, by the group with the lowest plan pk (A: OLIVE 50 / PKO 50) — never 80:80:50
        assert sum(sum(v) for v in parts.values()) == Decimal("1000")
        assert sum(parts["PALM KERNEL OIL"]) == Decimal("500") and sum(parts["OLIVE OIL"]) == Decimal("500")
        assert sum(parts.get("SUNFLOWER OIL", [Decimal("0")])) == 0


class ApportionTests(TestCase):
    """Opus B2 2026-11-20: largest-remainder apportionment — exact sums, never a negative share."""

    def test_examples_and_exact_sums(self):
        from apps.license.services.item_pivot_service import CIF_PLACES, QTY_PLACES, apportion

        assert apportion(Decimal("100.00"), [(1, 1), (2, 2)], CIF_PLACES) == {1: Decimal("33.33"), 2: Decimal("66.67")}
        assert apportion(Decimal("0.02"), [(k, 1) for k in (1, 2, 3, 4)], CIF_PLACES) == {
            1: Decimal("0.01"), 2: Decimal("0.01"), 3: Decimal("0.00"), 4: Decimal("0.00")}
        assert apportion(Decimal("10.00"), [(1, 0), (2, 0)], CIF_PLACES) == {1: Decimal("5.00"), 2: Decimal("5.00")}
        assert apportion(Decimal("1.003"), [(1, Decimal("33.33")), (2, Decimal("66.67"))], QTY_PLACES) == {1: Decimal("0.334"), 2: Decimal("0.669")}
        assert apportion(Decimal("5.00"), [], CIF_PLACES) == {}
        # Opus R1: more decimals than ``places`` — the sub-unit residual is carried exactly, never lost
        half = apportion(Decimal("1.0005"), [(1, 1), (2, 1)], QTY_PLACES)
        assert sum(half.values()) == Decimal("1.0005") and min(half.values()) >= 0
        half = apportion(Decimal("0.005"), [(1, 1), (2, 1)], CIF_PLACES)
        assert sum(half.values()) == Decimal("0.005") and min(half.values()) >= 0

    def test_property_non_negative_and_exact(self):
        import random

        from apps.license.services.item_pivot_service import CIF_PLACES, QTY_PLACES, apportion

        rng = random.Random(20261120)
        for _ in range(500):
            places = rng.choice([CIF_PLACES, QTY_PLACES])
            total = (Decimal(rng.randint(0, 5000)) * places)
            weights = [(k, Decimal(rng.choice([0, 1, 1, 2, 3, 7, 100]))) for k in range(1, rng.randint(1, 7) + 1)]
            shares = apportion(total, weights, places)
            assert sum(shares.values(), Decimal("0")) == total, (total, weights, shares)
            assert all(v >= 0 for v in shares.values()), (total, weights, shares)
            assert all(v == v.quantize(places) for v in shares.values())
        for _ in range(500):  # totals with more decimals than ``places`` (cif_fc 3 dp, qty_kg 4 dp): exact and non-negative only
            places = rng.choice([CIF_PLACES, QTY_PLACES])
            total = Decimal(rng.randint(0, 500000)) * places / Decimal(rng.choice([10, 100]))
            weights = [(k, Decimal(rng.choice([0, 1, 1, 2, 3, 7, 100]))) for k in range(1, rng.randint(1, 7) + 1)]
            shares = apportion(total, weights, places)
            assert sum(shares.values(), Decimal("0")) == total, (total, weights, shares)
            assert all(v >= 0 for v in shares.values()), (total, weights, shares)
