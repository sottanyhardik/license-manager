"""Item Pivot — canonical licence figures + intelligence views (2026-11-18).

Owner decisions: the report's licence CIF comes from ``LicenseBalanceCalculator``
(signed, billed term, allocation netting); products are one row per master item
(``ItemNameModel``) × SION, with Unmapped / Ambiguous import items kept separate.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.constants import GE
from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, PurchaseStatus, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan, SionPlanningRule
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.services.item_pivot_intelligence import build_intelligence, recommend_for_licenses
from apps.license.services.item_pivot_selection import select_pivot_licenses
from apps.license.views.item_pivot_report import ItemPivotReportView


class IntelligenceFixture(TestCase):
    def setUp(self):
        self.company = CompanyModel.objects.create(iec="PIVOTINT", name="Pivot Intel Exporter")
        status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
        head = HeadSIONNormsModel.objects.create(name="Intel")
        self.sion = SionNormClassModel.objects.create(head_norm=head, norm_class="PI1", is_active=True)
        self.licences = []
        for n in range(2):
            lic = LicenseDetailsModel.objects.create(
                license_number=f"PIVOT-INT-00{n}", license_date=date.today() - timedelta(days=1),
                license_expiry_date=date.today() + timedelta(days=30 + n), exporter=self.company, purchase_status=status,
            )
            LicenseExportItemModel.objects.create(license=lic, norm_class=self.sion, cif_fc=Decimal("1000"))
            self.licences.append(lic)
        self.sugar = ItemNameModel.objects.create(name="PIVOT SUGAR", sion_norm_class=self.sion)
        self.milk = ItemNameModel.objects.create(name="PIVOT MILK", sion_norm_class=self.sion)

    def item(self, lic, serial, hsn, desc, qty, names=()):
        code, _ = HSCodeModel.objects.get_or_create(hs_code=hsn)
        row = LicenseImportItemsModel.objects.create(
            license=lic, serial_number=serial, hs_code=code, description=desc,
            quantity=Decimal(qty), available_quantity=Decimal(qty), cif_fc=Decimal("100"),
        )
        for name in names:
            row.items.add(name)
        return row

    def rule_for(self, name, price="2.00"):
        return SionPlanningRule.objects.create(
            sion=self.sion, name=name.name, unit="kg", max_unit_price=Decimal(price), priority=1, import_item=name,
            expression={"operator": "AND", "conditions": [{"field": "HSN", "comparator": "STARTS_WITH", "value": "17"}]},
        )

    def report(self):
        return build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))


class ClassicPivotCanonicalTests(IntelligenceFixture):
    def test_licence_balance_is_the_signed_canonical_financial_balance(self):
        lic = self.licences[0]
        sugar = self.item(lic, 1, "17019990", "Sugar", "100", names=[self.sugar])
        allotment = AllotmentModel.objects.create(company=self.company, item_name="x", required_quantity=Decimal("10"))
        AllotmentItems.objects.create(allotment=allotment, item=sugar, qty=Decimal("10"), cif_fc=Decimal("1500"), cif_inr=Decimal("1"))
        report = ItemPivotReportView().generate_report(min_balance=-10**9, license_status="all", sion_norm="PI1")
        row = next(r for g in report["groups"] for r in g["licenses"] if r["license_id"] == lic.id)
        canonical = LicenseBalanceCalculator.calculate_financial_balance_for_licenses([lic.id])[lic.id]
        assert Decimal(row["balance_cif"]) == canonical == Decimal("-500.00")  # signed, never floored
        assert row["is_over_utilised"] is True
        assert Decimal(row["allotted_cif"]) == LicenseBalanceCalculator.calculate_allotment_for_licenses([lic.id])[lic.id]
        assert Decimal(report["summary"]["final_balance_cif"]) <= Decimal(report["summary"]["actual_balance_cif"])
        assert Decimal(report["summary"]["overdrawn_cif"]) == Decimal("500.00")  # from the signed balance


class IntelligenceTests(IntelligenceFixture):
    def test_master_item_consolidation_keeps_unmapped_and_ambiguous_separate(self):
        a, b = self.licences
        self.item(a, 1, "17019990", "Sugar (refined)", "100", names=[self.sugar])
        self.item(b, 1, "17011490", "SUGAR - refined grade", "50", names=[self.sugar])
        self.item(a, 2, "04021010", "Milk powder / sugar blend", "10", names=[self.sugar, self.milk])
        self.item(a, 3, "21069099", "Misc ingredient", "5")
        self.item(b, 3, "21069099", "misc  ingredient!", "7")
        data = self.report()
        by_kind = {}
        for row in data["products"]:
            by_kind.setdefault(row["kind"], []).append(row)
        sugar = next(r for r in by_kind["MAPPED"] if r["product"] == "PIVOT SUGAR")
        assert Decimal(sugar["entitlement_qty"]) == Decimal("150")
        assert sugar["eligible_licences"] == 2
        assert sugar["hsn_codes"] == ["17011490", "17019990"] and len(sugar["aliases"]) == 2
        assert len(by_kind["AMBIGUOUS"]) == 1 and "not merged" in by_kind["AMBIGUOUS"][0]["mapping_basis"]
        # Unmapped rows merge only on identical normalised description + HSN (punctuation/spacing).
        assert len(by_kind["UNMAPPED"]) == 1 and Decimal(by_kind["UNMAPPED"][0]["entitlement_qty"]) == Decimal("12")
        assert data["overview"]["consolidation"] == {"mapped": 1, "ambiguous": 1, "unmapped": 1, "merged_source_records": 2, "mapping_review": 0, "multi_product": 0}

    def test_licence_figures_are_canonical_and_statuses_follow_entitlement(self):
        a, b = self.licences
        self.rule_for(self.sugar)
        sugar_a = self.item(a, 1, "17019990", "Sugar", "500", names=[self.sugar])
        self.item(b, 1, "17019990", "Sugar", "500", names=[self.sugar])
        LicenseItemPlan.objects.create(license=a, import_item=sugar_a, item_name=self.sugar, planned_quantity=Decimal("650"), planned_cif_fc=Decimal("300"))
        data = self.report()
        lic_a = next(r for r in data["licences"] if r["license_id"] == a.id)
        assert Decimal(lic_a["available_cif"]) == LicenseBalanceCalculator.calculate_financial_balance_for_licenses([a.id])[a.id]
        assert Decimal(lic_a["final_balance_cif"]) == Decimal(lic_a["available_cif"]) - Decimal("300")
        status = {c["license_id"]: c["status"] for c in data["eligibility"] if c["product"] == "PIVOT SUGAR"}
        assert status[a.id] == "OVERPLANNED"  # 650 planned > 500 entitlement
        assert status[b.id] == "UNDERUTILIZED"
        cell_b = next(c for c in data["eligibility"] if c["license_id"] == b.id)
        assert cell_b["planning_eligible"] is True and cell_b["reasons"]

    def test_products_without_an_active_rule_or_with_tiny_residuals_are_not_underutilized(self):
        a, b = self.licences
        self.item(a, 1, "17019990", "Sugar", "500", names=[self.sugar])  # no rule for sugar yet
        self.item(b, 1, "04021010", "Milk", "500", names=[self.milk])
        self.rule_for(self.milk)
        milk_b = LicenseImportItemsModel.objects.get(license=b, serial_number=1)
        LicenseItemPlan.objects.create(license=b, import_item=milk_b, item_name=self.milk, planned_quantity=Decimal("450"), planned_cif_fc=Decimal("10"))
        cells = {c["product"]: c for c in self.report()["eligibility"]}
        assert cells["PIVOT SUGAR"]["status"] == "WARNING" and "No active planning rule" in cells["PIVOT SUGAR"]["reasons"][0]
        assert cells["PIVOT MILK"]["status"] == "CORRECT"  # 50 qty residual < 100 tolerance

    def test_mixed_hsn_chapters_are_flagged_not_split(self):
        a, b = self.licences
        self.item(a, 1, "17019990", "Sugar", "10", names=[self.sugar])
        self.item(b, 1, "39011090", "Sugar?", "10", names=[self.sugar])
        sugar = next(r for r in self.report()["products"] if r["product"] == "PIVOT SUGAR")
        assert sugar["hsn_chapters"] == ["17", "39"] and "review" in sugar["mapping_review"]

    def test_query_count_is_constant(self):
        for lic in self.licences:
            for serial in range(1, 4):
                self.item(lic, serial, "17019990", f"Sugar {serial}", "10", names=[self.sugar])
        licences = select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1")
        with CaptureQueriesContext(connection) as small:
            build_intelligence(licences[:1])
        with CaptureQueriesContext(connection) as large:
            build_intelligence(licences)
        assert len(large.captured_queries) == len(small.captured_queries)

    def test_recommendations_are_read_only_and_within_available_cif(self):
        from django.apps import apps as django_apps
        lic = self.licences[0]
        self.item(lic, 1, "17019990", "Sugar", "100", names=[self.sugar])
        counted = [m for m in django_apps.get_models() if m._meta.app_label in {"license", "allotment", "bill_of_entry", "trade", "core"} and m._meta.managed]
        before = {m: m.objects.count() for m in counted}
        data = recommend_for_licenses([lic.id])
        assert data["read_only"] is True
        assert {m: m.objects.count() for m in counted} == before
        available = LicenseBalanceCalculator.calculate_financial_balance_for_licenses([lic.id])[lic.id]
        assert sum((Decimal(r["recommended_cif"]) for r in data["recommendations"]), Decimal("0")) <= max(available, Decimal("0"))

    def test_licence_components_reconcile_with_the_engine(self):
        self.item(self.licences[0], 1, "17019990", "Sugar", "100", names=[self.sugar])
        for row in self.report()["licences"]:
            assert row["components_reconcile"] is True
            total = Decimal(row["original_cif"]) + Decimal(row["other_adjustments_cif"]) - Decimal(row["boe_cif"]) - Decimal(row["allotment_cif"]) - Decimal(row["billed_cif"])
            assert abs(total - Decimal(row["available_cif"])) <= Decimal("0.01")


class IntelligenceApiTests(IntelligenceFixture):
    def client_with(self, role):
        user = get_user_model().objects.create_user(username=f"intel-{role or 'none'}")
        if role:
            user.groups.add(Group.objects.get_or_create(name=role)[0])
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_endpoints_respect_report_permission_and_export_excel(self):
        self.item(self.licences[0], 1, "17019990", "Sugar", "100", names=[self.sugar])
        params = {"sion_norm": "PI1", "min_balance": -1000000000, "license_status": "all"}
        assert self.client_with(None).get("/api/item-pivot/intelligence/", params).status_code == 403
        client = self.client_with("REPORT_VIEWER")
        response = client.get("/api/item-pivot/intelligence/", params)
        assert response.status_code == 200
        assert response.data["report_version"] == "item-pivot-intelligence-v1"
        excel = client.get("/api/item-pivot/intelligence/", {**params, "format": "excel"})
        assert excel.status_code == 200 and excel["Content-Type"].startswith("application/vnd.openxmlformats")
        assert client.get("/api/item-pivot/recommendations/", {"license_ids": "x"}).status_code == 400
