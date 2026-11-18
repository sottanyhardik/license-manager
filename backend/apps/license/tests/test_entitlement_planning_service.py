"""Entitlement planning — DB adapter + API (real records, read-only)."""
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
    SionPlanningPercentageRow,
    SionPlanningRule,
)
from apps.license.services.entitlement_planning import AMBIGUOUS, MAPPED, UNMAPPED
from apps.license.services.entitlement_planning_service import (
    EntitlementPlanningService,
    resolve_entitlement,
    split_action_targets,
)
from apps.license.services.sion_planner_config.entitlement_profiles import ENTITLEMENT_PROFILES, entitlement_profile

E126_PRODUCTS = ENTITLEMENT_PROFILES["E126"]["groups"][1]["products"]
VEG_KEYS = ["PALM KERNEL OIL", "OLIVE OIL"]


def _sion(code):
    head, _ = HeadSIONNormsModel.objects.get_or_create(name="Test SION Head")
    return SionNormClassModel.objects.get_or_create(norm_class=code, defaults={"head_norm": head, "is_active": True})[0]


def _cond(field, comparator, value):
    return {"field": field, "comparator": comparator, "value": value}


@pytest.fixture
def e126_rules(db):
    sion = _sion("E126")
    names = {n: ItemNameModel.objects.get_or_create(name=n)[0] for n in ("FOOD FLAVOUR", "OLIVE OIL", "PALM KERNEL OIL")}
    SionPlanningRule.objects.create(
        sion=sion, name="FOOD FLAVOUR", priority=1, max_unit_price=D("2.70"), import_item=names["FOOD FLAVOUR"],
        expression={"operator": "OR", "conditions": [_cond("HSN", "STARTS_WITH", "0802"),
                                                      _cond("PRODUCT_DESCRIPTION", "CONTAINS", "flavour")]})
    veg = SionPlanningRule.objects.create(
        sion=sion, name="VEG OIL", priority=2, max_unit_price=D("5.00"), strategy="SPLIT_BY_PERCENT",
        expression={"operator": "AND", "conditions": [_cond("PRODUCT_DESCRIPTION", "CONTAINS", "1509"),
                                                       _cond("PRODUCT_DESCRIPTION", "CONTAINS", "1513")]})
    SionPlanningPercentageRow.objects.create(rule=veg, import_item=names["OLIVE OIL"], percentage=D("50"), unit_price=D("5.50"))
    SionPlanningPercentageRow.objects.create(rule=veg, import_item=names["PALM KERNEL OIL"], percentage=D("50"), unit_price=D("1.80"))
    return sion, names, veg


class World:
    """One E126 licence shaped like the spreadsheet's licence (as of the sheet)."""

    def __init__(self, sion, number, ff_qty=D("299770.32"), veg_qty=D("851620.26"), cif=D("3724889.95")):
        self.company = CompanyModel.objects.create(iec=number[-10:], name=f"Co {number}")
        self.licence = LicenseDetailsModel.objects.create(
            license_number=number, license_date=date.today(), license_expiry_date=date.today() + timedelta(days=365),
            exporter=self.company)
        LicenseExportItemModel.objects.create(license=self.licence, norm_class=sion, cif_fc=cif)
        hs, _ = HSCodeModel.objects.get_or_create(hs_code="15119020")
        self.ff = self._item(1, "Food Flavour - Fruit & Nut Products (HS 0802)", ff_qty)
        self.veg = self._item(2, "FATS AND OILS OLIVE OIL (HS Code 1509 / 1510) PALM BASED OIL (HS 15132110) SUNFLOWER OIL",
                              veg_qty, hs)
        self.alu = self._item(3, "PACKING MATERIAL Aluminium Foil", D("1000"))

    def _item(self, serial, desc, qty, hs=None):
        return LicenseImportItemsModel.objects.create(license=self.licence, serial_number=serial, description=desc,
                                                      quantity=qty, available_quantity=qty, hs_code=hs)

    def boe(self, number, item, qty, cif, product, allotment=None, frozen=False):
        boe = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number=number,
                                              bill_of_entry_date=date.today(), product_name=product)
        if allotment:
            boe.allotment.add(allotment)
        return RowDetails.objects.create(bill_of_entry=boe, sr_number=item, transaction_type="D",
                                         qty=D(qty), cif_fc=D(cif), is_frozen=frozen)

    def allot(self, item, qty, cif, name):
        allotment = AllotmentModel.objects.create(company=self.company, item_name=name, type="AT")
        AllotmentItems.objects.create(allotment=allotment, item=item, qty=D(qty), cif_fc=D(cif))
        return allotment

    def spreadsheet_records(self):
        pko_allot = self.allot(self.veg, "211771", "381187.80", "PKO")  # BOE-linked → excluded
        self.boe("3631938", self.veg, "211771", "378141.62", "PALM KERNEL OIL", allotment=pko_allot, frozen=True)
        self.boe("4132530", self.veg, "12654", "32200.69", "SUNFLOWER SEED OIL")
        self.boe("4000001", self.veg, "231767.64", "1181177.86", "OLIVE OIL")
        self.allot(self.veg, "200000", "360000.00", "PKO")
        self.allot(self.veg, "12311", "59092.80", "OLIVE OIL")


def rows(result, section="after"):
    data = result["after"]["entitlements"] if section == "after" else result["opening"]["rows"]
    return {r["entitlement"]: r for r in data}


def q2(value):
    return D(value).quantize(D("0.01"))


@pytest.mark.django_db
class TestE126LicenceFromRecords:
    def test_reproduces_spreadsheet_opening_and_after(self, e126_rules):
        sion, *_ = e126_rules
        world = World(sion, "3411000001")
        world.spreadsheet_records()
        result = EntitlementPlanningService.build("3411000001", "E126")

        opening = rows(result, "opening")
        assert [r["label"] for r in result["opening"]["rows"]] == ["Food Flavour", "PKO", "Olive Oil + Sunflower Oil"]
        assert opening["FOOD FLAVOUR"]["planned_cif"] == "809379.86"
        assert opening["PALM KERNEL OIL"]["planned_cif"] == "766458.23"
        assert opening["OLIVE OIL"]["planned_cif"] == "2149051.85"
        assert q2(opening["OLIVE OIL"]["unit_price"]) == D("5.05")
        assert q2(result["opening"]["total_quantity"]) == D("1151390.58")

        after = rows(result)
        pko, olive = after["PALM KERNEL OIL"], after["OLIVE OIL"]
        assert (pko["boe_debited"]["cif"], pko["allotted"]["cif"], pko["balance"]["cif"]) == (
            "378141.62", "360000.00", "25270.43")
        assert q2(pko["balance"]["quantity"]) == D("14039.13")
        assert q2(olive["boe_debited"]["quantity"]) == D("244421.64")
        assert olive["boe_debited"]["cif"] == "1213378.55"
        assert olive["allotted"]["cif"] == "59092.80"
        assert q2(olive["balance"]["quantity"]) == D("169077.49")
        assert olive["balance"]["cif"] == "879626.68"
        assert result["reconciliation"]["authority_difference"] == "0.00"
        assert result["after"]["total_balance_cif"] == result["after"]["remaining_licence_cif"]
        assert result["can_confirm"] is True

    def test_sunflower_and_olive_aggregate_pko_separate(self, e126_rules):
        sion, *_ = e126_rules
        world = World(sion, "3411000002")
        world.boe("B1", world.veg, "100", "500", "SUNFLOWER OIL")
        world.boe("B2", world.veg, "50", "250", "OLIVE POMACE OIL")
        world.boe("B3", world.veg, "10", "18", "PALM KERNEL OIL")
        after = rows(EntitlementPlanningService.build("3411000002", "E126"))
        assert after["OLIVE OIL"]["boe_debited"]["quantity"] == "150.000"
        assert after["PALM KERNEL OIL"]["boe_debited"]["quantity"] == "10.000"

    def test_boe_linked_allotment_is_not_counted_twice(self, e126_rules):
        sion, *_ = e126_rules
        world = World(sion, "3411000003")
        world.spreadsheet_records()
        pko = rows(EntitlementPlanningService.build("3411000003", "E126"))["PALM KERNEL OIL"]
        assert [r["reference"] for r in pko["allotted"]["rows"]] != []
        assert pko["allotted"]["quantity"] == "200000.000"  # the BOE-linked 211,771 allotment is excluded

    def test_frozen_ledger_rows_counted_once_and_rerun_is_identical(self, e126_rules):
        sion, *_ = e126_rules
        world = World(sion, "3411000004")
        world.spreadsheet_records()
        first = EntitlementPlanningService.build("3411000004", "E126")
        second = EntitlementPlanningService.build("3411000004", "E126")
        assert first == second
        assert len(rows(first)["PALM KERNEL OIL"]["boe_debited"]["rows"]) == 1

    def test_unlinked_boe_and_outstanding_allotment_of_same_qty_is_flagged(self, e126_rules):
        sion, *_ = e126_rules
        world = World(sion, "3411000005")
        world.spreadsheet_records()
        world.boe("5051922", world.veg, "12311", "58050.59", "OLIVE OIL")
        result = EntitlementPlanningService.build("3411000005", "E126")
        dup = [i for i in result["issues"] if i["code"] == "POSSIBLE_DUPLICATE_UTILISATION"]
        assert len(dup) == 1 and dup[0]["reference"] == "5051922"
        assert result["can_confirm"] is False
        # Authoritative figures are kept: the BOE is still debited.
        assert rows(result)["OLIVE OIL"]["boe_debited"]["cif"] == "1271429.14"

    def test_debits_outside_groups_are_adjustments(self, e126_rules):
        sion, *_ = e126_rules
        world = World(sion, "3411000006")
        world.boe("ALU1", world.alu, "10", "100", "ALUMINIUM FOIL")
        result = EntitlementPlanningService.build("3411000006", "E126")
        assert result["reconciliation"]["adjustments"][0]["code"] == "BOE_DEBITS_OUTSIDE_PLANNED_GROUPS"
        assert result["after"]["total_balance_cif"] == result["after"]["remaining_licence_cif"]

    def test_unresolvable_boe_blocks_confirmation(self, e126_rules):
        sion, *_ = e126_rules
        world = World(sion, "3411000007")
        world.boe("X1", world.veg, "10", "30", "VEGETABLE OIL")
        result = EntitlementPlanningService.build("3411000007", "E126")
        assert result["can_confirm"] is False
        assert any(i["code"] == "UNATTRIBUTED_DEBIT" for i in result["issues"])

    def test_multiple_licences_are_independent(self, e126_rules):
        sion, *_ = e126_rules
        a = World(sion, "3411000010")
        a.spreadsheet_records()
        World(sion, "3411000011", ff_qty=D("1000"), veg_qty=D("2000"), cif=D("10000"))
        ra = EntitlementPlanningService.build("3411000010", "E126")
        rb = EntitlementPlanningService.build("3411000011", "E126")
        assert rows(rb)["OLIVE OIL"]["boe_debited"]["cif"] == "0.00"
        assert rb["opening"]["total_cif"] == "10000.00"
        assert rows(ra)["OLIVE OIL"]["balance"]["cif"] == "879626.68"

    def test_preview_never_writes(self, e126_rules):
        sion, *_ = e126_rules
        world = World(sion, "3411000012")
        world.spreadsheet_records()
        before = (RowDetails.objects.count(), AllotmentItems.objects.count(), LicenseItemPlan.objects.count())
        with CaptureQueriesContext(connection) as ctx:
            EntitlementPlanningService.build("3411000012", "E126")
        writes = [q["sql"] for q in ctx.captured_queries
                  if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
        assert writes == []
        assert before == (RowDetails.objects.count(), AllotmentItems.objects.count(), LicenseItemPlan.objects.count())

    def test_split_matches_registry_action(self, e126_rules):
        sion, *_ = e126_rules
        World(sion, "3411000013")
        result = EntitlementPlanningService.build("3411000013", "E126")
        assert not any(i["code"] == "SPLIT_ACTION_MISMATCH" for i in result["issues"])
        veg = next(g for g in result["group_config"] if g["group"] == "VEGETABLE_OIL")
        assert veg["split_action"] == "E126:ACTION:002:SPLIT"
        assert veg["source_rule"] == "E126:RULE:002:PKO_OLIVE_SPLIT"

    def test_split_mismatch_with_registry_is_warned(self, e126_rules):
        sion, _names, veg = e126_rules
        SionPlanningPercentageRow.objects.filter(rule=veg, import_item__name="OLIVE OIL").update(percentage=D("60"))
        SionPlanningPercentageRow.objects.filter(rule=veg, import_item__name="PALM KERNEL OIL").update(percentage=D("40"))
        World(sion, "3411000014")
        result = EntitlementPlanningService.build("3411000014", "E126")
        assert any(i["code"] == "SPLIT_ACTION_MISMATCH" for i in result["issues"])
        assert rows(result, "opening")["OLIVE OIL"]["quantity"] == "510972.156"

    def test_unknown_licence_or_norm_is_a_clear_error(self, e126_rules):
        from apps.license.services.scoped_sion_planning import ScopedPlanningError
        with pytest.raises(ScopedPlanningError):
            EntitlementPlanningService.build("NOPE", "E126")
        with pytest.raises(ScopedPlanningError):
            EntitlementPlanningService.build("", "E126")


class TestPureMapping:
    @pytest.mark.parametrize("text,expected", [
        ("SUNFLOWER SEED OIL", (MAPPED, "OLIVE OIL")),
        ("OLIVE POMACE OIL", (MAPPED, "OLIVE OIL")),
        ("PALM KERNEL OIL", (MAPPED, "PALM KERNEL OIL")),
        ("PKO", (MAPPED, "PALM KERNEL OIL")),
        ("PKO / OLIVE OIL", (AMBIGUOUS, None)),
        ("VEGETABLE OIL", (UNMAPPED, None)),
    ])
    def test_e126_product_mapping(self, text, expected):
        assert resolve_entitlement([text], E126_PRODUCTS, VEG_KEYS) == expected

    def test_first_authoritative_text_wins(self):
        assert resolve_entitlement([None, "PALM KERNEL OIL", "OLIVE OIL"], E126_PRODUCTS, VEG_KEYS) == (MAPPED, "PALM KERNEL OIL")

    def test_generic_mapping_without_profile_uses_item_names(self):
        assert resolve_entitlement(["CHEESE BLOCKS"], [], ["CHEESE", "PKO"]) == (MAPPED, "CHEESE")

    def test_e126_profile_maps_sunflower_and_olive_together_pko_apart(self):
        mapping = {p["name"]: p["entitlement"] for p in E126_PRODUCTS}
        assert mapping["Sunflower Oil"] == mapping["Olive Oil"] == "OLIVE OIL"
        assert mapping["PKO"] == "PALM KERNEL OIL"

    def test_e132_has_no_profile_and_its_registry_split_is_unchanged(self):
        assert entitlement_profile("E132") == {"groups": [], "entitlements": {}}
        assert split_action_targets("E132", "E132:ACTION:002:SPLIT") == {"PKO": D("0.4"), "CHEESE": D("0.6")}
        assert split_action_targets("E126", "E126:ACTION:002:SPLIT") == {"PKO": D("0.5"), "OLIVE": D("0.5")}


@pytest.mark.django_db
class TestApi:
    def _client(self, group):
        user = get_user_model().objects.create_user(username=f"u-{group}")
        user.groups.add(Group.objects.get_or_create(name=group)[0])
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_json_and_xlsx(self, e126_rules):
        sion, *_ = e126_rules
        World(sion, "3411000020").spreadsheet_records()
        client = self._client("LICENSE_MANAGER")
        resp = client.get("/api/entitlement-plan/", {"license_number": "3411000020", "sion": "E126"})
        assert resp.status_code == 200
        assert resp.json()["read_only"] is True
        xlsx = client.get("/api/entitlement-plan/", {"license_number": "3411000020", "sion": "E126", "export": "xlsx"})
        assert xlsx.status_code == 200
        assert xlsx["Content-Type"].startswith("application/vnd.openxmlformats")
        assert xlsx.content[:2] == b"PK"

    def test_bad_scope_is_400(self, e126_rules):
        client = self._client("LICENSE_MANAGER")
        resp = client.get("/api/entitlement-plan/", {"license_number": "missing", "sion": "E126"})
        assert resp.status_code == 400 and "not found" in resp.json()["error"]

    def test_anonymous_is_rejected(self, e126_rules):
        resp = APIClient().get("/api/entitlement-plan/", {"license_number": "x", "sion": "E126"})
        assert resp.status_code in (401, 403)
