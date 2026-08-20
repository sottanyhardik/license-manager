from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel,
    LicenseItemPlan, LicenseReplanRequest, SionPlanningAction,
    SionPlanningProfile, SionPlanningRule,
)
from apps.license.services.canonical_planning_service import CanonicalPlanningService
from apps.license.services.sion_planning_execution import SionPlanningExecutionService
from apps.license.services.sion_rule_engine import (
    SionRulePlanningService, evaluate_expression, validate_expression,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def rule_world():
    head = HeadSIONNormsModel.objects.create(name="Rule engine")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="R77", is_active=True)
    company = CompanyModel.objects.create(iec="9200000001", name="Rule Company")
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company, license_number="RULE-LIC-1", license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30),
    )
    LicenseExportItemModel.objects.create(
        # Execution tests below exercise bucket selection and priority with
        # thousands of kilograms.  Give their shared fixture a real live
        # export-CIF entitlement large enough that the financial cap does
        # not mask the behaviour under test; cap-specific tests pass their
        # own operational ceiling explicitly.
        license=license_obj, norm_class=sion, cif_fc=Decimal("10000000.00"),
    )
    hs = HSCodeModel.objects.create(
        hs_code="001701", product_description="Refined   Sugar",
        unit_price=Decimal("2.25"), unit="kg",
    )
    item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs,
        description=" Refined   Sugar ", unit="kg", quantity=Decimal("10.000"),
        available_quantity=Decimal("8.000"),
    )
    rule = SionPlanningRule.objects.create(
        sion=sion, name="Sugar", unit="kg", max_unit_price=Decimal("2.50"),
        priority=1,
        expression={"operator": "AND", "conditions": [
            {"field": "HSN", "comparator": "CONTAINS", "value": "1701"},
            {"operator": "NOT", "conditions": [{
                "field": "PRODUCT_DESCRIPTION", "comparator": "NOT_CONTAINS", "value": "sugar",
            }]},
        ]},
    )
    return company, sion, license_obj, item, rule


def _client(company):
    user = get_user_model().objects.create_user(username="rule-manager", company=company)
    role, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(role)
    client = APIClient()
    client.force_authenticate(user)
    return client, user


def _split_action(sion, rule):
    rule.execution_output = "MILK PRODUCTS"
    rule.save(update_fields=("execution_output",))
    profile = SionPlanningProfile.objects.create(
        sion=sion, stable_key=f"{sion.norm_class}:PROFILE", is_active=True,
    )
    return SionPlanningAction.objects.create(
        profile=profile, stable_key=f"{sion.norm_class}:SPLIT", action_type="SPLIT",
        priority=1, config={
            "algorithm": "SPLIT_BY_UNIT_VALUE",
            "basis": "BALANCE_CIF_PER_QUANTITY",
            "category": "MILK PRODUCTS",
            "granularity": "ITEM_SEQUENTIAL",
            "buckets": [
                {"code": "SWP", "min_price": "0.00", "max_price": "1.50", "reference_price": "1.50"},
                {"code": "DWP", "min_price": "1.50", "max_price": "6.50", "reference_price": "6.50"},
            ],
        },
    )


def _unit_value_rule_payload(rule, dwp, swp):
    return {
        "sion": rule.sion_id,
        "name": "003 MILK PRODUCTS",
        "expression": rule.expression,
        "max_unit_price": "6.50",
        "unit": "KG",
        "is_active": True,
        "strategy": "SPLIT_BY_UNIT_VALUE",
        "import_item": None,
        # Deliberately reverse the price ordering: save validation must sort a
        # copy rather than requiring the React editor's visible order.
        "unit_value_rows": [
            {"import_item": dwp.pk, "min_unit_price": "1.5", "max_unit_price": "6.50", "preferred_unit_price": "0"},
            {"import_item": swp.pk, "min_unit_price": "0", "max_unit_price": "1.5", "preferred_unit_price": "0"},
        ],
        "percentage_rows": [],
    }


def test_unit_value_rule_saves_zero_preferred_price_and_touching_boundary(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    dwp = ItemNameModel.objects.create(name="DWP - E1", sion_norm_class=sion)
    swp = ItemNameModel.objects.create(name="SWP - E1", sion_norm_class=sion)
    client, _user = _client(company)

    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/", _unit_value_rule_payload(rule, dwp, swp), format="json",
    )

    assert response.status_code == 200, response.data
    saved = SionPlanningRule.objects.get(pk=response.data["id"])
    assert saved.strategy == "SPLIT_BY_UNIT_VALUE"
    assert saved.max_unit_price == Decimal("6.50")
    rows = {row.import_item.name: row for row in saved.unit_value_rows.all()}
    assert rows["DWP - E1"].min_unit_price == Decimal("1.50")
    assert rows["DWP - E1"].max_unit_price == Decimal("6.50")
    assert rows["DWP - E1"].preferred_unit_price == Decimal("0.00")
    assert rows["SWP - E1"].min_unit_price == Decimal("0.00")
    assert rows["SWP - E1"].max_unit_price == Decimal("1.50")
    assert rows["SWP - E1"].preferred_unit_price == Decimal("0.00")

    # API reload uses the persisted canonical response, not stale draft rows.
    reloaded = client.get(f"/api/sion-planning-rules/{saved.pk}/")
    assert reloaded.status_code == 200
    assert {row["import_item"] for row in reloaded.data["unit_value_rows"]} == {dwp.pk, swp.pk}


def test_unit_value_rule_rejects_true_overlap_but_not_touching_boundary(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    dwp = ItemNameModel.objects.create(name="DWP - E1", sion_norm_class=sion)
    swp = ItemNameModel.objects.create(name="SWP - E1", sion_norm_class=sion)
    payload = _unit_value_rule_payload(rule, dwp, swp)
    payload["unit_value_rows"][1]["max_unit_price"] = "2.00"
    client, _user = _client(company)

    response = client.patch(f"/api/sion-planning-rules/{rule.pk}/", payload, format="json")

    assert response.status_code == 400
    assert response.data["unit_value_rows"] == ["Price ranges overlap."]


def test_unit_value_execution_assigns_each_source_item_to_one_decimal_bucket(rule_world):
    """Touching bands are deterministic and never duplicate source quantity."""
    _company, sion, license_obj, _item, rule = rule_world
    swp = ItemNameModel.objects.create(name="SWP output", sion_norm_class=sion)
    dwp = ItemNameModel.objects.create(name="DWP output", sion_norm_class=sion)
    rule.strategy = "SPLIT_BY_UNIT_VALUE"
    rule.expression = {"field": "HSN", "comparator": "CONTAINS", "value": "1701"}
    rule.save(update_fields=("strategy", "expression"))
    rule.unit_value_rows.create(
        import_item=dwp, min_unit_price=Decimal("1.50"),
        max_unit_price=Decimal("6.50"), preferred_unit_price=Decimal("0"), priority=2,
    )
    rule.unit_value_rows.create(
        import_item=swp, min_unit_price=Decimal("0"),
        max_unit_price=Decimal("1.50"), preferred_unit_price=Decimal("0"), priority=1,
    )

    # Existing fixture source: 10 units / CIF 22.50 => 2.25 (DWP).
    _item.cif_fc = Decimal("22.50")
    _item.save(update_fields=("cif_fc",))
    hs = HSCodeModel.objects.create(hs_code="170199", product_description="Low sugar", unit="kg")
    LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=2, hs_code=hs, description="Low sugar",
        unit="kg", quantity=Decimal("1000"), available_quantity=Decimal("1000"),
        cif_fc=Decimal("1500"),  # 1.50 belongs to the lower/SWP band.
    )
    hs_high = HSCodeModel.objects.create(hs_code="170198", product_description="High sugar", unit="kg")
    LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=3, hs_code=hs_high, description="High sugar",
        unit="kg", quantity=Decimal("700"), available_quantity=Decimal("700"),
        cif_fc=Decimal("1260"),  # 1.80 belongs to DWP.
    )

    lines, _remaining, metadata = SionPlanningExecutionService._compute_license_new_architecture(
        license_obj, sion, [rule], preview=True,
        # The unit-value splitter consumes the authoritative operational CIF
        # ceiling.  Source-row cached CIF is not its input.
        operational_balance_cif=Decimal("2782.50"),
    )
    by_output = {}
    for line in lines:
        by_output[line["item_name"]] = by_output.get(line["item_name"], Decimal("0")) + line["planned_quantity"]

    # The canonical bounded solver consumes the live operational ceiling, not
    # source-row CIF.  Its Decimal mix is fully reconciled to that ceiling.
    assert by_output == {dwp.pk: Decimal("253.500"), swp.pk: Decimal("756.500")}
    assert sum(by_output.values()) == Decimal("1010")
    assert sum((line["planned_cif"] for line in lines), Decimal("0")) == Decimal("2782.50")
    assert all(line["unit_price"] > 0 and line["planned_cif"] > 0 for line in lines)
    assert metadata["architecture"] == "strategy"


@pytest.mark.parametrize(("source_cif", "expected_mix"), [
    ("0", []),
    ("1200", [("SWP", "800.000")]),
    ("1500", [("SWP", "1000.000")]),
    ("1500.10", [("SWP", "999.980"), ("DWP", "0.020")]),
    ("1800", [("SWP", "940.000"), ("DWP", "60.000")]),
    ("6500", [("DWP", "1000.000")]),
    ("6501", [("DWP", "1000.000")]),
])
def test_unit_value_execution_decimal_boundaries(rule_world, source_cif, expected_mix):
    _company, sion, license_obj, item, rule = rule_world
    swp = ItemNameModel.objects.create(name="SWP boundary", sion_norm_class=sion)
    dwp = ItemNameModel.objects.create(name="DWP boundary", sion_norm_class=sion)
    rule.strategy = "SPLIT_BY_UNIT_VALUE"
    rule.expression = {"field": "HSN", "comparator": "CONTAINS", "value": "1701"}
    rule.save(update_fields=("strategy", "expression"))
    rule.unit_value_rows.create(import_item=swp, min_unit_price=Decimal("0"), max_unit_price=Decimal("1.50"), preferred_unit_price=Decimal("0"))
    rule.unit_value_rows.create(import_item=dwp, min_unit_price=Decimal("1.50"), max_unit_price=Decimal("6.50"), preferred_unit_price=Decimal("0"))
    item.quantity = Decimal("1000")
    item.cif_fc = Decimal(source_cif)
    item.save(update_fields=("quantity", "cif_fc"))

    lines, _remaining, _metadata = SionPlanningExecutionService._compute_license_new_architecture(
        license_obj, sion, [rule], preview=True,
        operational_balance_cif=Decimal(source_cif),
    )
    by_name = {swp.pk: "SWP", dwp.pk: "DWP"}
    assert [(by_name[line["item_name"]], str(line["planned_quantity"])) for line in lines] == expected_mix
    assert sum((line["planned_cif"] for line in lines), Decimal("0")) <= Decimal(source_cif)
    assert all(line["unit_price"] in (Decimal("1.50"), Decimal("6.50")) for line in lines)


def test_unit_value_auto_plan_is_idempotent_and_persists_one_bucket(rule_world):
    _company, sion, license_obj, item, rule = rule_world
    swp = ItemNameModel.objects.create(name="SWP idempotent", sion_norm_class=sion)
    dwp = ItemNameModel.objects.create(name="DWP idempotent", sion_norm_class=sion)
    rule.strategy = "SPLIT_BY_UNIT_VALUE"
    rule.expression = {"field": "HSN", "comparator": "CONTAINS", "value": "1701"}
    rule.save(update_fields=("strategy", "expression"))
    rule.unit_value_rows.create(import_item=swp, min_unit_price=Decimal("0"), max_unit_price=Decimal("1.50"), preferred_unit_price=Decimal("0"))
    rule.unit_value_rows.create(import_item=dwp, min_unit_price=Decimal("1.50"), max_unit_price=Decimal("6.50"), preferred_unit_price=Decimal("0"))
    item.quantity = Decimal("1000")
    item.cif_fc = Decimal("1200")
    item.available_quantity = Decimal("1000")
    item.save(update_fields=("quantity", "cif_fc", "available_quantity"))
    LicenseExportItemModel.objects.filter(license=license_obj, norm_class=sion).update(cif_fc=Decimal("1200"))

    first = SionPlanningExecutionService.plan_sion(sion, license_ids=[license_obj.pk], mode="ALL")
    first_rows = list(LicenseItemPlan.objects.filter(license=license_obj).values_list(
        "item_name_id", "planned_quantity", "unit_price", "planned_cif_fc",
    ))
    second = SionPlanningExecutionService.plan_sion(sion, license_ids=[license_obj.pk], mode="ALL")
    second_rows = list(LicenseItemPlan.objects.filter(license=license_obj).values_list(
        "item_name_id", "planned_quantity", "unit_price", "planned_cif_fc",
    ))

    assert first["write_results"][0]["status"] == "PLANNED"
    assert second["write_results"][0]["status"] == "PLANNED"
    assert first_rows == second_rows == [(swp.pk, Decimal("800.000"), Decimal("1.50"), Decimal("1200.00"))]
    persisted = LicenseItemPlan.objects.get(license=license_obj, item_name=swp)
    assert persisted.allocation_provenance["theoretical_cif"] == "1200.00"
    assert persisted.allocation_provenance["operational_planned_cif"] == "1200.00"
    assert persisted.allocation_provenance["cif_status"] == "FULLY_FUNDED"


def test_unit_value_rule_priority_prevents_overlapping_fruit_juice_target(rule_world):
    """A Milk source matching an old fruit HSN must retain its Milk target."""
    _company, sion, license_obj, source, milk_rule = rule_world
    swp = ItemNameModel.objects.create(name="SWP mapping", sion_norm_class=sion)
    dwp = ItemNameModel.objects.create(name="DWP mapping", sion_norm_class=sion)
    fruit_juice = ItemNameModel.objects.create(name="FRUIT JUICE mapping", sion_norm_class=sion)
    milk_rule.strategy = "SPLIT_BY_UNIT_VALUE"
    milk_rule.priority = 1
    milk_rule.expression = {"field": "PRODUCT_DESCRIPTION", "comparator": "CONTAINS", "value": "milk"}
    milk_rule.save(update_fields=("strategy", "priority", "expression"))
    milk_rule.unit_value_rows.create(import_item=swp, min_unit_price=Decimal("0"), max_unit_price=Decimal("1.50"), preferred_unit_price=Decimal("0"))
    milk_rule.unit_value_rows.create(import_item=dwp, min_unit_price=Decimal("1.50"), max_unit_price=Decimal("6.50"), preferred_unit_price=Decimal("0"))
    SionPlanningRule.objects.create(
        sion=sion, name="Fruit Juice fallback", import_item=fruit_juice,
        max_unit_price=Decimal("2.50"), unit="kg", priority=2, strategy="STANDARD",
        expression={"field": "HSN", "comparator": "STARTS_WITH", "value": "2009"},
    )
    source.hs_code = HSCodeModel.objects.create(hs_code="20091100", product_description="Fruit HSN", unit="kg")
    source.description = "Milk and Milk Products / Milk solids (04041020)"
    source.quantity = Decimal("31513")
    source.cif_fc = Decimal("39391.25")  # unit value 1.25 -> SWP
    source.save(update_fields=("hs_code", "description", "quantity", "cif_fc"))

    lines, _remaining, _metadata = SionPlanningExecutionService._compute_license_new_architecture(
        license_obj, sion,
        list(SionPlanningRule.objects.filter(sion=sion, is_active=True).order_by("priority", "pk")),
        preview=True, operational_balance_cif=Decimal("39391.25"),
    )

    assert [(line["item_name"], line["planned_quantity"], line["planned_cif"] ) for line in lines] == [
        (swp.pk, Decimal("26260.833"), Decimal("39391.25")),
    ]
    assert all(line["item_name"] != fruit_juice.pk for line in lines)


def test_strategy_rules_use_persisted_priority_waterfall_capacity(rule_world):
    """Later rules see only quantity and CIF left by earlier rules."""
    _company, sion, license_obj, first_source, first_rule = rule_world
    first_output = ItemNameModel.objects.create(name="Waterfall first", sion_norm_class=sion)
    second_output = ItemNameModel.objects.create(name="Waterfall second", sion_norm_class=sion)
    third_output = ItemNameModel.objects.create(name="Waterfall third", sion_norm_class=sion)
    first_rule.import_item = first_output
    first_rule.strategy = "STANDARD"
    first_rule.priority = 1
    first_rule.max_unit_price = Decimal("3")
    first_rule.expression = {"field": "HSN", "comparator": "STARTS_WITH", "value": "1001"}
    first_rule.save(update_fields=("import_item", "strategy", "priority", "max_unit_price", "expression"))
    first_source.hs_code = HSCodeModel.objects.create(hs_code="10010000", product_description="First", unit="kg")
    first_source.quantity = first_source.available_quantity = Decimal("24830")
    first_source.save(update_fields=("hs_code", "quantity", "available_quantity"))
    def source(serial, hsn, quantity):
        return LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=serial,
            hs_code=HSCodeModel.objects.create(hs_code=hsn, product_description=hsn, unit="kg"),
            description=hsn, unit="kg", quantity=Decimal(quantity), available_quantity=Decimal(quantity),
        )
    source(2, "10020000", "31513")
    source(3, "10030000", "43657")
    second_rule = SionPlanningRule.objects.create(
        sion=sion, name="Waterfall second", import_item=second_output, strategy="STANDARD",
        priority=2, max_unit_price=Decimal("6.50"), unit="kg",
        expression={"field": "HSN", "comparator": "STARTS_WITH", "value": "1002"},
    )
    third_rule = SionPlanningRule.objects.create(
        sion=sion, name="Waterfall third", import_item=third_output, strategy="STANDARD",
        priority=3, max_unit_price=Decimal("1"), unit="kg",
        expression={"field": "HSN", "comparator": "STARTS_WITH", "value": "1003"},
    )

    lines, _remaining, metadata = SionPlanningExecutionService._compute_license_new_architecture(
        license_obj, sion, [third_rule, second_rule, first_rule], preview=True,
        operational_balance_cif=Decimal("500000"),
    )
    assert [(line["item_name"], line["planned_quantity"], line["planned_cif"]) for line in lines] == [
        (first_output.pk, Decimal("24830.000"), Decimal("74490.000")),
        (second_output.pk, Decimal("31513.000"), Decimal("204834.500")),
        (third_output.pk, Decimal("43657.000"), Decimal("43657.000")),
    ]
    assert metadata["waterfall"][0]["priority"] == 1
    assert Decimal(metadata["waterfall"][1]["remaining_cif"]) == Decimal("220675.500")


def test_mixed_legacy_and_strategy_rules_share_one_available_quantity_waterfall(rule_world):
    """A blank legacy strategy is a STANDARD stage, never a skipped rule.

    This guards SIONs such as E5 where persisted rules were created before
    strategy was mandatory but later rules use the strategy editor.
    """
    _company, sion, license_obj, dietary_source, dietary_rule = rule_world
    dietary_output = ItemNameModel.objects.create(name="Dietary target", sion_norm_class=sion)
    wpc_output = ItemNameModel.objects.create(name="WPC target", sion_norm_class=sion)
    dietary_rule.import_item = dietary_output
    dietary_rule.priority = 1
    dietary_rule.strategy = None
    dietary_rule.max_unit_price = Decimal("2.70")
    dietary_rule.save(update_fields=("import_item", "priority", "strategy", "max_unit_price"))
    dietary_source.available_quantity = Decimal("8.000")
    dietary_source.save(update_fields=("available_quantity",))
    wpc_source = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=2,
        hs_code=HSCodeModel.objects.create(hs_code="35020000", product_description="WPC", unit="kg"),
        description="WPC", unit="kg", quantity=Decimal("10.000"), available_quantity=Decimal("10.000"),
    )
    wpc_rule = SionPlanningRule.objects.create(
        sion=sion, name="WPC", import_item=wpc_output, strategy="STANDARD",
        priority=2, max_unit_price=Decimal("25.00"), unit="kg",
        expression={"field": "HSN", "comparator": "STARTS_WITH", "value": "3502"},
    )

    lines, _remaining, metadata = SionPlanningExecutionService._compute_license(
        license_obj, sion, preview=True, operational_balance_cif=Decimal("1000.00"),
    )

    assert [(line["item_name"], line["planned_quantity"], line["planned_cif"])
            for line in lines] == [
        (dietary_output.pk, Decimal("8.000"), Decimal("21.60")),
        (wpc_output.pk, Decimal("10.000"), Decimal("250.00")),
    ]
    assert [stage["priority"] for stage in metadata["waterfall"]] == [1, 2]
    assert all(line["import_item"] != dietary_source.pk or line["planned_quantity"] <= Decimal("8") for line in lines)


def test_standard_waterfall_keeps_full_quantity_when_operational_cif_is_capped(rule_world):
    _company, sion, license_obj, source, rule = rule_world
    target = ItemNameModel.objects.create(name="Capped standard", sion_norm_class=sion)
    rule.import_item = target
    rule.strategy = "STANDARD"
    rule.max_unit_price = Decimal("25.00")
    rule.expression = {"field": "HSN", "comparator": "STARTS_WITH", "value": "3502"}
    rule.save(update_fields=("import_item", "strategy", "max_unit_price", "expression"))
    source.hs_code = HSCodeModel.objects.create(hs_code="35022000", product_description="Milk", unit="kg")
    source.quantity = source.available_quantity = Decimal("35843.000")
    source.save(update_fields=("hs_code", "quantity", "available_quantity"))

    lines, _remaining, metadata = SionPlanningExecutionService._compute_license_new_architecture(
        license_obj, sion, [rule], preview=True, operational_balance_cif=Decimal("264107.07"),
    )

    assert [(line["planned_quantity"], line["unit_price"], line["planned_cif"]) for line in lines] == [
        (Decimal("10564.282"), Decimal("25.00"), Decimal("264107.05")),
    ]
    assert lines[0]["allocation_provenance"]["theoretical_cif"] == "264107.05"
    assert lines[0]["allocation_provenance"]["cif_status"] == "FULLY_FUNDED"
    # Quantisation to the persisted quantity/CIF precision leaves a harmless
    # unspendable residue; it must never turn into an over-cap allocation.
    assert metadata["remaining_waterfall_cif"] == Decimal("0.02")


def test_generic_waterfall_allocates_e5_style_pko_dietary_and_wpc_by_priority(rule_world):
    """The shared engine needs no SION-specific branch for E5-style rules."""
    _company, sion, license_obj, dietary_source, dietary_rule = rule_world
    dietary_output = ItemNameModel.objects.create(name="DIETARY FIBRE - test", sion_norm_class=sion)
    pko_output = ItemNameModel.objects.create(name="PALM KERNEL OIL - test", sion_norm_class=sion)
    wpc_output = ItemNameModel.objects.create(name="WPC - test", sion_norm_class=sion)
    dietary_rule.import_item = dietary_output
    dietary_rule.priority = 1
    dietary_rule.strategy = None
    dietary_rule.max_unit_price = Decimal("2.70")
    dietary_rule.expression = {"field": "PRODUCT_DESCRIPTION", "comparator": "CONTAINS", "value": "dietary"}
    dietary_rule.save(update_fields=("import_item", "priority", "strategy", "max_unit_price", "expression"))
    dietary_source.description = "Dietary Fibre"
    dietary_source.quantity = dietary_source.available_quantity = Decimal("3819.000")
    dietary_source.save(update_fields=("description", "quantity", "available_quantity"))
    pko_source = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=2,
        hs_code=HSCodeModel.objects.create(hs_code="15132110", product_description="PKO", unit="kg"),
        description="Vegetable oil", unit="kg", quantity=Decimal("48759.000"), available_quantity=Decimal("48759.000"),
    )
    wpc_source = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=3,
        hs_code=HSCodeModel.objects.create(hs_code="35022000", product_description="WPC", unit="kg"),
        description="Milk solids", unit="kg", quantity=Decimal("35843.000"), available_quantity=Decimal("35843.000"),
    )
    pko_rule = SionPlanningRule.objects.create(
        sion=sion, name="PKO", import_item=pko_output, priority=2,
        max_unit_price=Decimal("1.80"), unit="kg",
        expression={"field": "HSN", "comparator": "STARTS_WITH", "value": "1513"},
    )
    wpc_rule = SionPlanningRule.objects.create(
        sion=sion, name="WPC", import_item=wpc_output, strategy="STANDARD", priority=3,
        max_unit_price=Decimal("25.00"), unit="kg",
        expression={"operator": "AND", "conditions": [
            {"field": "PRODUCT_DESCRIPTION", "comparator": "CONTAINS", "value": "milk"},
            {"field": "HSN", "comparator": "STARTS_WITH", "value": "3502"},
            {"field": "HSN", "comparator": "NOT_STARTS_WITH", "value": "0404"},
        ]},
    )

    assert evaluate_expression(wpc_rule.expression, {
        "hs_code": "35022000", "description": "Milk & Milk Products - Milk Solids",
    })
    assert evaluate_expression(wpc_rule.expression, {
        "hs_code": "35021000", "description": "Milk protein concentrate",
    })
    assert not evaluate_expression(wpc_rule.expression, {
        "hs_code": "04041020", "description": "Milk solids",
    })

    lines, _remaining, metadata = SionPlanningExecutionService._compute_license(
        license_obj, sion, preview=True, operational_balance_cif=Decimal("1000000.00"),
    )

    assert [(line["planning_rule_id"], line["item_name"], line["planned_quantity"], line["unit_price"], line["planned_cif"])
            for line in lines] == [
        (dietary_rule.pk, dietary_output.pk, Decimal("3819.000"), Decimal("2.70"), Decimal("10311.30")),
        (pko_rule.pk, pko_output.pk, Decimal("48759.000"), Decimal("1.80"), Decimal("87766.20")),
        (wpc_rule.pk, wpc_output.pk, Decimal("35843.000"), Decimal("25.00"), Decimal("896075.00")),
    ]
    assert sum(line["planned_quantity"] for line in lines) == Decimal("88421.000")
    assert sum(line["planned_cif"] for line in lines) == Decimal("994152.50")
    assert [stage["priority"] for stage in metadata["waterfall"]] == [1, 2, 3]
    assert {line["import_item"] for line in lines} == {dietary_source.pk, pko_source.pk, wpc_source.pk}

    # A matched later rule is explicitly explained when an earlier priority
    # consumes the operational CIF ceiling; it must not look like a matcher
    # failure or a silently stale plan.
    _capped_lines, _remaining, capped_metadata = SionPlanningExecutionService._compute_license(
        license_obj, sion, preview=True, operational_balance_cif=Decimal("70923.47"),
    )
    wpc_trace = next(stage for stage in capped_metadata["waterfall"] if stage["rule_id"] == wpc_rule.pk)
    assert wpc_trace["matched_source_item_ids"] == [wpc_source.pk]
    assert Decimal(wpc_trace["requested_qty"]) == Decimal("35843.000")
    assert wpc_trace["allocated_qty"] == "0"
    assert wpc_trace["skip_reason"] == "WATERFALL_CIF_EXHAUSTED"


def test_allocation_strategy_api_reads_and_updates_canonical_action(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    action = _split_action(sion, rule)
    client, _user = _client(company)

    response = client.get(f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/")
    assert response.status_code == 200
    assert response.data["strategy"] == "SPLIT_BY_UNIT_VALUE"
    assert response.data["config"]["buckets"][1]["max_price"] == "6.50"

    changed = response.data["config"]
    changed["buckets"][1]["max_price"] = "6.75"
    response = client.patch(f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", {
        "strategy": "SPLIT_BY_UNIT_VALUE", "config": changed,
    }, format="json")
    assert response.status_code == 200
    action.refresh_from_db()
    assert action.config["buckets"][1]["max_price"] == "6.75"
    assert action.config["category"] == "MILK PRODUCTS"
    assert action.config["granularity"] == "ITEM_SEQUENTIAL"
    assert action.version == 2


def test_allocation_strategy_api_rejects_invalid_band(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    _split_action(sion, rule)
    client, _user = _client(company)
    response = client.patch(f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", {
        "strategy": "SPLIT_BY_UNIT_VALUE",
        "config": {
            "algorithm": "SPLIT_BY_UNIT_VALUE", "basis": "BALANCE_CIF_PER_QUANTITY",
            "buckets": [
                {"code": "SWP", "min_price": "1.50", "max_price": "1.50", "reference_price": "1.50"},
                {"code": "DWP", "min_price": "1.50", "max_price": "6.50", "reference_price": "6.50"},
            ],
        },
    }, format="json")
    assert response.status_code == 400


def test_allocation_strategy_api_creates_db_action_for_new_rule_and_reloads(rule_world):
    company, _sion, _license_obj, _item, rule = rule_world
    client, _user = _client(company)
    payload = {
        "strategy": "SPLIT_BY_UNIT_VALUE",
        "config": {
            "algorithm": "SPLIT_BY_UNIT_VALUE", "basis": "BALANCE_CIF_PER_QUANTITY",
            "buckets": [
                {"code": "LOW", "min_price": "0.00", "max_price": "1.50", "reference_price": "1.50"},
                {"code": "HIGH", "min_price": "1.50", "max_price": "6.50", "reference_price": "6.50"},
            ],
        },
    }
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", payload, format="json",
    )
    assert response.status_code == 200
    action = SionPlanningAction.objects.get(pk=response.data["action_id"])
    assert action.config["source_rule_id"] == rule.pk
    assert action.config["category"] == rule.name

    reloaded = client.get(f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/")
    assert reloaded.status_code == 200
    assert reloaded.data["config"]["buckets"] == payload["config"]["buckets"]


def test_split_by_percentage_accepts_editable_rows(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    from apps.core.models import ItemNameModel
    output_item = ItemNameModel.objects.create(name="PKO")
    olive_item = ItemNameModel.objects.create(name="OLIVE_OIL")
    rule.import_item = output_item
    rule.save(update_fields=("import_item",))

    client, _user = _client(company)
    payload = {
        "strategy": "SPLIT_BY_PERCENTAGE",
        "config": {
            "algorithm": "SPLIT_BY_PERCENTAGE",
            "rows": [
                {"id": "row-1", "input_item_id": output_item.pk, "percentage": "50.00", "unit_price": "1.80"},
                {"id": "row-2", "input_item_id": olive_item.pk, "percentage": "50.00", "unit_price": "5.00"},
            ],
        },
    }
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", payload, format="json",
    )
    assert response.status_code == 200
    action = SionPlanningAction.objects.get(pk=response.data["action_id"])
    assert action.config["algorithm"] == "SPLIT_BY_PERCENTAGE"
    assert [(row["input_item_id"], row["percentage"], row["unit_price"]) for row in action.config["rows"]] == [
        (output_item.pk, "50.00", "1.80"), (olive_item.pk, "50.00", "5.00"),
    ]
    assert action.is_active is True


def test_split_by_percentage_rejects_percentages_not_summing_to_100(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    from apps.core.models import ItemNameModel
    output_item = ItemNameModel.objects.create(name="PKO")
    olive_item = ItemNameModel.objects.create(name="OLIVE_OIL")
    rule.import_item = output_item
    rule.save(update_fields=("import_item",))

    client, _user = _client(company)
    payload = {
        "strategy": "SPLIT_BY_PERCENTAGE",
        "config": {
            "algorithm": "SPLIT_BY_PERCENTAGE",
            "rows": [
                {"id": "row-1", "input_item_id": output_item.pk, "percentage": "40.00", "unit_price": "1.80"},
                {"id": "row-2", "input_item_id": olive_item.pk, "percentage": "40.00", "unit_price": "5.00"},
            ],
        },
    }
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", payload, format="json",
    )
    assert response.status_code == 400
    assert "100" in str(response.data.get("config", ""))


def test_split_by_percentage_rejects_duplicate_input_codes(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    from apps.core.models import ItemNameModel
    output_item = ItemNameModel.objects.create(name="PKO")
    rule.import_item = output_item
    rule.save(update_fields=("import_item",))

    client, _user = _client(company)
    payload = {
        "strategy": "SPLIT_BY_PERCENTAGE",
        "config": {
            "algorithm": "SPLIT_BY_PERCENTAGE",
            "rows": [
                {"id": "row-1", "input_item_id": output_item.pk, "percentage": "60.00", "unit_price": "1.80"},
                {"id": "row-2", "input_item_id": output_item.pk, "percentage": "40.00", "unit_price": "1.80"},
            ],
        },
    }
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", payload, format="json",
    )
    assert response.status_code == 400
    assert "Duplicate" in str(response.data.get("config", ""))


def test_split_by_percentage_loads_from_master_rules_as_defaults(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    from apps.core.models import ItemNameModel
    from apps.license.services.sion_rule_engine import SionRulePriorityService

    output_item = ItemNameModel.objects.create(name="PKO")
    rule.import_item = output_item
    rule.save(update_fields=("import_item",))

    # Create master percentage rules for this output item
    next_prio = SionRulePriorityService.next_priority(sion.pk)
    master_rule_1 = SionPlanningRule.objects.create(
        sion=sion, name="PKO Percentage Cap", unit="kg", max_unit_price=Decimal("2.50"),
        priority=next_prio, import_item=output_item, percentage_constraint=Decimal("50.00"),
        expression={},
    )
    next_prio = SionRulePriorityService.next_priority(sion.pk)
    master_rule_2 = SionPlanningRule.objects.create(
        sion=sion, name="PKO Alternative", unit="kg", max_unit_price=Decimal("3.00"),
        priority=next_prio, import_item=output_item, percentage_constraint=Decimal("50.00"),
        expression={},
    )

    client, _user = _client(company)

    payload = {
        "strategy": "SPLIT_BY_PERCENTAGE",
        "config": {"algorithm": "SPLIT_BY_PERCENTAGE", "rows": []},
    }
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", payload, format="json",
    )
    assert response.status_code == 200
    action = SionPlanningAction.objects.get(pk=response.data["action_id"])
    assert action.config["algorithm"] == "SPLIT_BY_PERCENTAGE"
    assert len(action.config.get("rows", [])) == 2
    percentages = {row["output_code"]: row["percentage"] for row in action.config.get("rows", [])}
    assert percentages.get("PKO") == "50.00"


def test_safe_nested_expression_normalizes_case_space_and_hsn_zeroes():
    expression = {"operator": "AND", "conditions": [
        {"field": "HSN", "comparator": "CONTAINS", "value": " 1701 "},
        {"operator": "NOT", "condition": {
            "field": "PRODUCT_DESCRIPTION", "comparator": "NOT_CONTAINS", "value": "sugar",
        }},
    ]}
    assert evaluate_expression(expression, {"hs_code": "001701", "description": "Refined   SUGAR"})


def test_unknown_expression_field_is_rejected():
    with pytest.raises(Exception, match="Unsupported rule field"):
        validate_expression({"field": "__class__", "comparator": "EQ", "value": "x"})


def test_preview_uses_current_price_and_ceiling_is_not_a_replacement(rule_world):
    company, _sion, license_obj, _item, rule = rule_world
    preview = SionRulePlanningService.preview(rule, [], company_id=company.pk)
    line = preview["results"][0]["matched_lines"][0]
    assert line["current_unit_price"] == Decimal("2.25")
    assert line["max_unit_price"] == Decimal("2.50")
    assert line["price_status"] == "WITHIN_MAX"
    assert preview["conflicts"] == []
    assert preview["results"][0]["license_id"] == license_obj.pk


def test_above_ceiling_blocks_plan(rule_world):
    company, _sion, license_obj, _item, rule = rule_world
    rule.max_unit_price = Decimal("2.00")
    rule.save()
    preview = SionRulePlanningService.preview(rule, [license_obj.pk], company_id=company.pk)
    assert preview["can_plan"] is False
    assert preview["conflicts"][0]["price_status"] == "ABOVE_MAX"


def test_plan_passes_current_price_to_canonical_writer(rule_world, monkeypatch):
    company, _sion, license_obj, _item, rule = rule_world
    captured = []
    def fake_build(**kwargs):
        captured.append(kwargs)
        return {"license_id": kwargs["license_id"]}
    monkeypatch.setattr(CanonicalPlanningService, "build_canonical_plan", staticmethod(fake_build))
    result = SionRulePlanningService.plan(rule, [license_obj.pk], company_id=company.pk)
    assert result["planned_licenses"] == 1
    assert captured[0]["items"][0]["unit_price"] == Decimal("2.25")


def test_preview_never_writes_and_duplicate_ids_are_rejected(rule_world):
    company, _sion, license_obj, _item, rule = rule_world
    before = LicenseItemPlan.objects.count()
    SionRulePlanningService.preview(rule, [license_obj.pk], company_id=company.pk)
    assert LicenseItemPlan.objects.count() == before
    with pytest.raises(Exception, match="duplicate"):
        SionRulePlanningService.preview(
            rule, [license_obj.pk, license_obj.pk], company_id=company.pk,
        )


def test_database_rejects_duplicate_active_priority(rule_world):
    _company, sion, _license_obj, _item, rule = rule_world
    with pytest.raises(IntegrityError):
        SionPlanningRule.objects.create(
            sion=sion, name="Sugar duplicate", unit="kg",
            max_unit_price=Decimal("2.50"), priority=rule.priority,
            expression=rule.expression,
        )


def test_inactive_rule_cannot_plan(rule_world):
    company, _sion, license_obj, _item, rule = rule_world
    rule.is_active = False
    rule.save(update_fields=["is_active"])
    with pytest.raises(Exception, match="active rule"):
        SionRulePlanningService.plan(rule, [license_obj.pk], company_id=company.pk)


def test_repeated_plan_is_idempotent(rule_world):
    company, _sion, license_obj, _item, rule = rule_world
    first = SionRulePlanningService.plan(rule, [license_obj.pk], company_id=company.pk)
    plan_ids = list(LicenseItemPlan.objects.values_list("pk", flat=True))
    second = SionRulePlanningService.plan(rule, [license_obj.pk], company_id=company.pk)
    assert first["planned_licenses"] == second["planned_licenses"] == 1
    assert list(LicenseItemPlan.objects.values_list("pk", flat=True)) == plan_ids


@pytest.mark.parametrize("endpoint", ("plan-sion", "preview-sion"))
@pytest.mark.parametrize("include_empty_license_ids", (False, True))
def test_sion_first_api_uses_eligible_company_licenses_when_filter_is_omitted_or_empty(
    rule_world, endpoint, include_empty_license_ids,
):
    """An empty license filter is the SION-first contract, not invalid input."""
    company, sion, license_obj, _item, _rule = rule_world
    client, _user = _client(company)
    payload = {"sion_id": sion.pk}
    if include_empty_license_ids:
        payload["license_ids"] = []

    response = client.post(
        f"/api/sion-planning-rules/{endpoint}/", payload, format="json",
    )

    if endpoint == "plan-sion":
        # HTTP only persists/coalesces a durable request.  The Celery worker
        # has separate execution coverage; no plan may be written inline.
        assert response.status_code == 202, response.data
        assert response.data["planning_state"] == "REPLAN_PENDING"
        assert len(response.data["replan_request_ids"]) == 1
        request = LicenseReplanRequest.objects.get(pk=response.data["replan_request_ids"][0])
        assert request.license_id == license_obj.pk
        assert LicenseItemPlan.objects.filter(license=license_obj).count() == 0
        return

    assert response.status_code == 200, response.data
    assert response.data["sion_id"] == sion.pk
    assert len(response.data["licenses"]) == 1
    assert response.data["licenses"][0]["license_id"] == license_obj.pk
    assert response.data["licenses"][0]["license_number"] == license_obj.license_number


@pytest.mark.django_db(transaction=True)
def test_concurrent_identical_plan_creates_one_stable_row(rule_world):
    import threading
    from django.db import connections

    company, _sion, license_obj, _item, rule = rule_world
    barrier = threading.Barrier(2)
    results, errors = [], []

    def worker():
        try:
            barrier.wait(timeout=5)
            result = SionRulePlanningService.plan(
                SionPlanningRule.objects.get(pk=rule.pk),
                [license_obj.pk], company_id=company.pk,
            )
            results.append(result)
        except Exception as exc:  # surfaced below with the original exception
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert not errors, errors
    assert len(results) == 2
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 1
    assert any(
        row["write_results"][0].get("mutation_status") == "UNCHANGED"
        for row in results
    )


def test_rule_api_permissions_and_company_isolation(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    viewer = get_user_model().objects.create_user(username="rule-viewer", company=company)
    viewer_group, _ = Group.objects.get_or_create(name="LICENSE_VIEWER")
    viewer.groups.add(viewer_group)
    viewer_client = APIClient()
    viewer_client.force_authenticate(viewer)
    assert viewer_client.get("/api/sion-planning-rules/").status_code == 200
    assert viewer_client.post(
        f"/api/sion-planning-rules/{rule.pk}/test/", {}, format="json",
    ).status_code == 403
    assert viewer_client.post(
        "/api/sion-planning-rules/plan-sion/", {"sion_id": sion.pk}, format="json",
    ).status_code == 403
    assert viewer_client.post(
        "/api/sion-planning-rules/preview-sion/", {"sion_id": sion.pk}, format="json",
    ).status_code == 403

    foreign_company = CompanyModel.objects.create(iec="9200000002", name="Foreign Rule")
    foreign_license = LicenseDetailsModel.objects.create(
        exporter=foreign_company, license_number="RULE-FOREIGN",
        license_date=date.today(), license_expiry_date=date.today() + timedelta(days=30),
    )
    LicenseExportItemModel.objects.create(license=foreign_license, norm_class=sion)
    manager_client, _user = _client(company)
    response = manager_client.post(
        f"/api/sion-planning-rules/{rule.pk}/test/",
        {"license_ids": [foreign_license.pk]}, format="json",
    )
    assert response.status_code == 403


def test_plan_sion_rejects_an_inactive_sion_with_structured_error(rule_world):
    company, sion, _license_obj, _item, _rule = rule_world
    client, _user = _client(company)
    sion.is_active = False
    sion.save(update_fields=["is_active"])

    response = client.post(
        "/api/sion-planning-rules/plan-sion/",
        {"sion_id": sion.pk, "mode": "ALL"},
        format="json",
    )

    assert response.status_code == 404
    assert response.data == {
        "code": "SION_NOT_FOUND_OR_INACTIVE",
        "detail": "sion_id must reference an active SION norm.",
    }


def test_crud_versions_and_delete_retires_history(rule_world):
    company, sion, _license_obj, _item, _rule = rule_world
    client, user = _client(company)
    payload = {
        "sion": sion.pk, "name": "API Rule", "unit": "KG",
        "max_unit_price": "3.00", "priority": 5, "is_active": True,
        "expression": {"operator": "AND", "conditions": [
            {"field": "HSN", "comparator": "CONTAINS", "value": "17"},
        ]},
    }
    created = client.post("/api/sion-planning-rules/", payload, format="json")
    assert created.status_code == 201, created.data
    first_id = created.data["id"]
    assert created.data["version"] == 1
    assert SionPlanningRule.objects.get(pk=first_id).created_by == user
    updated = client.patch(f"/api/sion-planning-rules/{first_id}/", {"max_unit_price": "3.10"}, format="json")
    assert updated.status_code == 200, updated.data
    assert updated.data["id"] != first_id and updated.data["version"] == 2
    assert SionPlanningRule.objects.get(pk=first_id).is_active is False
    retired = client.delete(f"/api/sion-planning-rules/{updated.data['id']}/")
    assert retired.status_code == 204
    assert SionPlanningRule.objects.filter(pk=updated.data["id"], is_active=False).exists()
    assert SionPlanningRule.objects.filter(name="API Rule").count() == 2


def test_versioned_edit_preserves_execution_mapping_identity(rule_world):
    company, _sion, _license_obj, _item, rule = rule_world
    rule.stable_key = "TEST:RULE:001"
    rule.save(update_fields=("stable_key",))
    client, _user = _client(company)
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/",
        {"max_unit_price": "3.10"}, format="json",
    )
    assert response.status_code == 200, response.data
    assert SionPlanningRule.objects.get(pk=response.data["id"]).stable_key == rule.stable_key


def test_versioned_clear_expression_is_match_none_and_preserves_execution_output(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    rule.stable_key = "TEST:RULE:CLEAR"
    rule.execution_output = "OTHER CONFECTIONERY INGREDIENTS"
    rule.save(update_fields=("stable_key", "execution_output"))
    untouched = SionPlanningRule.objects.create(
        sion=sion, stable_key="TEST:RULE:OTHER", name="Other", version=1,
        unit="kg", max_unit_price=Decimal("9.00"), priority=2,
        execution_output="EGG ALBUMIN",
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "3502"},
    )
    client, _user = _client(company)

    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/",
        {"expression": {"operator": "AND", "conditions": [
            {"operator": "OR", "conditions": []},
        ]}},
        format="json",
    )

    assert response.status_code == 200, response.data
    replacement = SionPlanningRule.objects.get(pk=response.data["id"])
    assert replacement.version == rule.version + 1
    assert replacement.expression == {"operator": "AND", "conditions": []}
    assert replacement.execution_output == "OTHER CONFECTIONERY INGREDIENTS"
    assert evaluate_expression(replacement.expression, {
        "hs_code": "08029900", "description": "Other Confectionery",
    }) is False
    preview = client.post(
        "/api/sion-planning-rules/preview-sion/",
        {"sion_id": sion.pk, "mode": "NEW"}, format="json",
    )
    assert preview.status_code == 200, preview.data
    assert preview.data["licenses"] == []
    for mode in ("NEW", "ALL"):
        queued = client.post(
            "/api/sion-planning-rules/plan-sion/",
            {"sion_id": sion.pk, "mode": mode}, format="json",
        )
        assert queued.status_code == 202, queued.data
        assert queued.data["planning_state"] == "REPLAN_PENDING"
        assert queued.data["replan_request_ids"]
    assert not LicenseItemPlan.objects.filter(license=_license_obj).exists()
    rule.refresh_from_db()
    untouched.refresh_from_db()
    assert rule.is_active is False
    assert untouched.is_active is True
    assert untouched.expression == {
        "field": "HSN", "comparator": "CONTAINS", "value": "3502",
    }


def test_database_priority_assignment_is_sion_scoped_and_reorder_persists(rule_world):
    company, sion, _license_obj, _item, existing = rule_world
    client, _user = _client(company)
    head = sion.head_norm
    other_sion = SionNormClassModel.objects.create(
        head_norm=head, norm_class="R78", is_active=True,
    )
    payload = {
        "name": "Second", "unit": "kg", "max_unit_price": "4.20",
        "expression": {"field": "HSN", "comparator": "CONTAINS", "value": "99"},
    }
    second = client.post(
        "/api/sion-planning-rules/", {**payload, "sion": sion.pk, "priority": 88}, format="json",
    )
    first_other = client.post(
        "/api/sion-planning-rules/", {**payload, "sion": other_sion.pk}, format="json",
    )
    assert second.status_code == first_other.status_code == 201
    assert second.data["priority"] == 2
    assert first_other.data["priority"] == 1
    reordered = client.post("/api/sion-planning-rules/reorder/", {
        "sion_id": sion.pk, "rule_order": [second.data["id"], existing.pk],
    }, format="json")
    assert reordered.status_code == 200, reordered.data
    assert list(SionPlanningRule.objects.filter(
        sion=sion, is_active=True,
    ).order_by("priority").values_list("pk", "priority")) == [
        (second.data["id"], 1), (existing.pk, 2),
    ]
    retired = client.delete(f"/api/sion-planning-rules/{second.data['id']}/")
    assert retired.status_code == 204
    existing.refresh_from_db()
    assert existing.priority == 1


def test_plan_sion_uses_only_saved_active_rules_and_queues_a_durable_request(rule_world):
    company, sion, license_obj, _item, rule = rule_world
    client, _user = _client(company)
    response = client.post("/api/sion-planning-rules/plan-sion/", {
        "sion_id": sion.pk,
        "license_ids": [license_obj.pk],
        "rules": [{"expression": {"field": "HSN", "operator": "CONTAINS", "value": "fake"}}],
    }, format="json")
    assert response.status_code == 400
    assert not LicenseItemPlan.objects.exists()

    response = client.post("/api/sion-planning-rules/plan-sion/", {
        "sion_id": sion.pk, "license_ids": [license_obj.pk],
    }, format="json")
    assert response.status_code == 202, response.data
    assert response.data["planning_state"] == "REPLAN_PENDING"
    request = LicenseReplanRequest.objects.get(pk=response.data["replan_request_ids"][0])
    assert request.license_id == license_obj.pk
    assert request.reason == "manual_plan_sion"
    assert request.source_model == "sion_planning_rule.plan_sion"
    assert request.source_pk == str(sion.pk)
    # The HTTP handler must never persist a generated plan. Canonical rule
    # provenance is asserted by the worker/replan integration tests.
    assert not LicenseItemPlan.objects.exists()


def test_sion_preview_is_read_only_database_driven_and_isolated(rule_world):
    company, sion, license_obj, _item, rule = rule_world
    client, _user = _client(company)
    before = LicenseItemPlan.objects.count()
    rejected = client.post("/api/sion-planning-rules/preview-sion/", {
        "sion_id": sion.pk, "license_ids": [license_obj.pk],
        "rules": [{"expression": {"operator": "OR", "conditions": []}}],
    }, format="json")
    assert rejected.status_code == 400

    response = client.post("/api/sion-planning-rules/preview-sion/", {
        "sion_id": sion.pk, "license_ids": [license_obj.pk],
    }, format="json")
    assert response.status_code == 200, response.data
    assert response.data["rules_processed"] == [{
        "id": rule.pk, "version": rule.version, "priority": rule.priority,
    }]
    # The canonical preview distinguishes a saved rule that matched no live
    # source from a generic unplanned licence.
    assert response.data["licenses"][0]["status"] == "SKIPPED_NO_MATCH"
    assert LicenseItemPlan.objects.count() == before

    other_sion = SionNormClassModel.objects.create(
        head_norm=sion.head_norm, norm_class="R79", is_active=True,
    )
    SionPlanningRule.objects.create(
        sion=other_sion, name="Other norm only", unit="kg",
        max_unit_price=Decimal("9.00"), priority=1,
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "1701"},
    )
    response = client.post("/api/sion-planning-rules/preview-sion/", {
        "sion_id": sion.pk, "license_ids": [license_obj.pk],
    }, format="json")
    assert [row["id"] for row in response.data["rules_processed"]] == [rule.pk]


def test_norm_preview_runs_canonical_waterfall_in_saved_priority_order(rule_world):
    company, sion, license_obj, _item, first = rule_world
    hs = HSCodeModel.objects.create(
        hs_code="009999", product_description="Second", unit_price=Decimal("2.00"), unit="kg",
    )
    LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=2, hs_code=hs, description="Second",
        unit="kg", quantity=Decimal("10.000"), available_quantity=Decimal("10.000"),
    )
    second = SionPlanningRule.objects.create(
        sion=sion, name="Second", unit="kg", max_unit_price=Decimal("2.00"), priority=2,
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "9999"},
    )
    result = SionRulePlanningService.preview_sion(
        sion.pk, [license_obj.pk], company_id=company.pk,
    )
    assert [row["id"] for row in result["rules_processed"]] == [first.pk, second.pk]
    items = result["licenses"][0]["items"]
    assert [row["rule_id"] for row in items] == [first.pk, second.pk]
    assert [row["rule_priority"] for row in items] == [1, 2]
    quantities = [row["proposed_planned_quantity"] for row in items]
    # Neither source has an authoritative financial entitlement in this
    # preview fixture.  Priority is still represented by rule order and the
    # exact shortage state; cached available quantities must not create CIF.
    assert quantities == [Decimal("0"), Decimal("0")]
    assert result["licenses"][0]["change_status"] == "SHORTAGE"
    assert not LicenseItemPlan.objects.exists()
