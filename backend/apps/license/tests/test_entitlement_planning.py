"""Generic entitlement planning engine — pure tests + E126 spreadsheet fixture.

Reference: the owner's E126 planning spreadsheet for licence 3411008089.
All inputs below are the licence's recorded figures (import item quantities,
export CIF, BOE debit rows and outstanding allotments as of the spreadsheet);
the expected outputs are the spreadsheet's printed values.

Spreadsheet note: it prints Olive "BOE Debited" quantity as 2,44,214.64 but
its own balance (1,69,077.49) and the recorded BOE rows give 2,44,421.64
(digit transposition in the sheet).  The test pins the recorded figure.
"""
from decimal import Decimal as D

import pytest

from apps.license.services.entitlement_planning import (
    ALLOTMENT,
    AMBIGUOUS,
    BOE,
    OUTSIDE,
    RATE,
    RESIDUAL,
    Debit,
    EntitlementSpec,
    GroupSpec,
    compute_entitlement_plan,
)

FF = EntitlementSpec("FOOD FLAVOUR", "Food Flavour", D("100"), D("2.70"))
PKO = EntitlementSpec("PALM KERNEL OIL", "PKO", D("50"), D("1.80"), RATE, ("PKO",))
OLIVE = EntitlementSpec("OLIVE OIL", "Olive Oil + Sunflower Oil", D("50"), D("5.50"), RESIDUAL,
                        ("Olive Oil", "Sunflower Oil"))

# Import item quantities (serials 2/6/10/18 and 1/5/9/17 of the licence).
FF_QTY = D("37.400") + D("1037.700") + D("3714.760") + D("294980.460")
VEG_QTY = D("106.300") + D("2948.000") + D("10553.290") + D("838012.670")
OPENING_CIF = D("3724889.95")


def e126_groups(pko=PKO, olive=OLIVE):
    return [
        GroupSpec("FOOD_FLAVOUR", "Food Flavour", FF_QTY, (FF,), 4),
        GroupSpec("VEGETABLE_OIL", "Vegetable Oil", VEG_QTY, (pko, olive), 4),
    ]


# Olive Oil + Sunflower Oil BOE rows (qty, cif) as recorded for the licence.
OLIVE_BOES = [
    ("13224", "50644.74"), ("2948", "17432.04"), ("10553", "63547.04"), ("10525", "56539.67"),
    ("13740", "73495.46"), ("10217", "51790.86"), ("10435", "63510.40"), ("12654", "32200.69"),
    ("11432", "61267.16"), ("5894", "35161.49"), ("13850", "39758.97"), ("20120", "49968.03"),
    ("11432", "68128.85"), ("12457.6", "83737.15"), ("11432", "68128.85"), ("10223", "67248.65"),
    ("10480", "52594.88"), ("11432", "66778.38"), ("11432", "66778.38"), ("12311", "57850.90"),
    ("4000", "19080.68"), ("12311", "58050.59"), ("1319.04", "9684.69"),
]


def spreadsheet_debits():
    debits = [Debit(BOE, "3631938", D("211771"), D("378141.62"), entitlement_key="PALM KERNEL OIL")]
    debits += [Debit(BOE, f"OL{i}", D(q), D(c), entitlement_key="OLIVE OIL")
               for i, (q, c) in enumerate(OLIVE_BOES)]
    debits += [
        Debit(ALLOTMENT, "10432", D("200000"), D("360000.00"), entitlement_key="PALM KERNEL OIL"),
        Debit(ALLOTMENT, "10106", D("12311"), D("59092.80"), entitlement_key="OLIVE OIL"),
    ]
    return debits


def money(value):
    return D(value).quantize(D("0.01"))


@pytest.fixture
def plan():
    return compute_entitlement_plan(opening_cif=OPENING_CIF, groups=e126_groups(), debits=spreadsheet_debits())


def rows_by_key(rows):
    return {r["entitlement"]: r for r in rows}


class TestOpeningPlanning:
    def test_header_totals(self, plan):
        assert plan["opening"]["total_cif"] == "3724889.95"
        assert money(plan["opening"]["total_quantity"]) == D("1151390.58")
        assert plan["opening"]["total_planned_cif"] == "3724889.95"

    def test_food_flavour_row(self, plan):
        ff = rows_by_key(plan["opening"]["rows"])["FOOD FLAVOUR"]
        assert money(ff["quantity"]) == D("299770.32")
        assert money(ff["unit_price"]) == D("2.70")
        assert ff["planned_cif"] == "809379.86"
        assert ff["cif_available"] == "2915510.09"

    def test_pko_row(self, plan):
        pko = rows_by_key(plan["opening"]["rows"])["PALM KERNEL OIL"]
        assert money(pko["quantity"]) == D("425810.13")
        assert money(pko["unit_price"]) == D("1.80")
        assert pko["planned_cif"] == "766458.23"
        assert pko["cif_available"] == "2149051.85"

    def test_olive_absorbs_remaining_cif_below_max_price(self, plan):
        olive = rows_by_key(plan["opening"]["rows"])["OLIVE OIL"]
        assert money(olive["quantity"]) == D("425810.13")
        assert money(olive["unit_price"]) == D("5.05")
        assert olive["max_unit_price"] == "5.50"
        assert olive["planned_cif"] == "2149051.85"
        assert olive["cif_available"] == "0.00"

    def test_vegetable_oil_split_reconciles_50_50(self, plan):
        veg = next(g for g in plan["opening"]["groups"] if g["group"] == "VEGETABLE_OIL")
        assert money(veg["quantity"]) == D("851620.26")
        assert veg["reconciles"] is True
        assert [s["percentage"] for s in veg["split"]] == ["50", "50"]


class TestAfterBoeAndAllotted:
    def test_pko(self, plan):
        pko = rows_by_key(plan["after"]["entitlements"])["PALM KERNEL OIL"]
        assert money(pko["boe_debited"]["quantity"]) == D("211771.00")
        assert money(pko["boe_debited"]["rate"]) == D("1.79")
        assert pko["boe_debited"]["cif"] == "378141.62"
        assert pko["allotted"]["cif"] == "360000.00"
        assert money(pko["allotted"]["rate"]) == D("1.80")
        assert money(pko["balance"]["quantity"]) == D("14039.13")
        assert money(pko["balance"]["rate"]) == D("1.80")
        assert pko["balance"]["cif"] == "25270.43"
        # 3,046.18 CIF saved by the cheaper actual BOE rate flows to the residual.
        assert pko["components"] == [{"code": "RELEASED_TO_RESIDUAL", "cif": "-3046.18"}]

    def test_olive_plus_sunflower(self, plan):
        olive = rows_by_key(plan["after"]["entitlements"])["OLIVE OIL"]
        assert money(olive["boe_debited"]["quantity"]) == D("244421.64")
        assert olive["boe_debited"]["cif"] == "1213378.55"
        assert money(olive["boe_debited"]["rate"]) == D("4.96")
        assert money(olive["allotted"]["quantity"]) == D("12311.00")
        assert money(olive["allotted"]["rate"]) == D("4.80")
        assert olive["allotted"]["cif"] == "59092.80"
        assert money(olive["balance"]["quantity"]) == D("169077.49")
        assert olive["balance"]["cif"] == "879626.68"
        assert olive["components"] == [{"code": "RECEIVED_FROM_OTHER_ENTITLEMENTS", "cif": "3046.18"}]

    def test_food_flavour_unchanged(self, plan):
        ff = rows_by_key(plan["after"]["entitlements"])["FOOD FLAVOUR"]
        assert ff["balance"]["cif"] == "809379.86"
        assert ff["boe_debited"]["cif"] == "0.00"

    def test_totals_reconcile_to_remaining_licence_cif(self, plan):
        assert plan["after"]["remaining_licence_cif"] == "1714276.98"
        assert plan["after"]["total_balance_cif"] == "1714276.98"
        assert plan["reconciliation"]["status"] == "RECONCILED"
        assert plan["can_confirm"] is True
        assert plan["totals"]["boe_debit_cif"] == "1591520.17"
        assert plan["totals"]["allotment_cif"] == "419092.80"


class TestAuthoritativeAdjustments:
    def test_authoritative_balance_difference_lands_on_residual(self):
        # e.g. billed-without-BOE CIF the financial engine deducts.
        result = compute_entitlement_plan(opening_cif=OPENING_CIF, groups=e126_groups(),
                                          debits=spreadsheet_debits(), authoritative_balance=D("1700000.00"))
        olive = rows_by_key(result["after"]["entitlements"])["OLIVE OIL"]
        assert result["reconciliation"]["authority_difference"] == "-14276.98"
        assert {"code": "OTHER_AUTHORITATIVE_ADJUSTMENTS", "cif": "-14276.98"} in olive["components"]
        assert olive["balance"]["cif"] == "865349.70"
        assert result["after"]["total_balance_cif"] == "1700000.00"

    def test_debits_outside_groups_reduce_residual_and_are_listed(self):
        debits = spreadsheet_debits() + [Debit(BOE, "ALU-1", D("10"), D("100"), status=OUTSIDE)]
        result = compute_entitlement_plan(opening_cif=OPENING_CIF, groups=e126_groups(), debits=debits)
        adj = result["reconciliation"]["adjustments"]
        assert adj == [{"code": "BOE_DEBITS_OUTSIDE_PLANNED_GROUPS", "cif": "-100.00", "references": ["ALU-1"]}]
        olive = rows_by_key(result["after"]["entitlements"])["OLIVE OIL"]
        assert olive["balance"]["cif"] == "879526.68"
        assert result["can_confirm"] is True

    def test_ambiguous_debit_blocks_confirmation_and_is_not_guessed(self):
        debits = spreadsheet_debits() + [Debit(BOE, "X1", D("5"), D("20"), status=AMBIGUOUS, group_key="VEGETABLE_OIL")]
        result = compute_entitlement_plan(opening_cif=OPENING_CIF, groups=e126_groups(), debits=debits)
        assert result["can_confirm"] is False
        assert any(i["code"] == "UNATTRIBUTED_DEBIT" and i["reference"] == "X1" for i in result["issues"])
        pko = rows_by_key(result["after"]["entitlements"])["PALM KERNEL OIL"]
        assert pko["boe_debited"]["cif"] == "378141.62"  # never silently assigned


class TestValidation:
    def test_split_must_total_100(self):
        bad = EntitlementSpec("OLIVE OIL", "Olive", D("40"), D("5.50"), RESIDUAL)
        result = compute_entitlement_plan(opening_cif=OPENING_CIF, groups=e126_groups(olive=bad))
        assert result["can_confirm"] is False
        assert any(i["code"] == "SPLIT_NOT_100" for i in result["issues"])

    def test_over_utilisation_is_visible_and_blocking(self):
        debits = [Debit(BOE, "B", D("500000"), D("900000"), entitlement_key="PALM KERNEL OIL")]
        result = compute_entitlement_plan(opening_cif=OPENING_CIF, groups=e126_groups(), debits=debits)
        pko = rows_by_key(result["after"]["entitlements"])["PALM KERNEL OIL"]
        assert D(pko["balance"]["quantity"]) < 0
        assert D(pko["balance"]["cif"]) < 0  # signed, never floored
        assert {"OVER_UTILISED_QUANTITY", "OVER_UTILISED_CIF"} <= {i["code"] for i in result["issues"]}
        assert result["can_confirm"] is False

    def test_missing_unit_price_blocks(self):
        bad = EntitlementSpec("PALM KERNEL OIL", "PKO", D("50"), D("0"))
        result = compute_entitlement_plan(opening_cif=OPENING_CIF, groups=e126_groups(pko=bad))
        assert any(i["code"] == "MISSING_UNIT_PRICE" for i in result["issues"])

    def test_two_residuals_block(self):
        other = EntitlementSpec("PALM KERNEL OIL", "PKO", D("50"), D("1.80"), RESIDUAL)
        result = compute_entitlement_plan(opening_cif=OPENING_CIF, groups=e126_groups(pko=other))
        assert any(i["code"] == "MULTIPLE_RESIDUAL" for i in result["issues"])


class TestGenericConfigurations:
    def test_different_sion_split_60_40_all_rate(self):
        a = EntitlementSpec("A", "A", D("60"), D("2.00"))
        b = EntitlementSpec("B", "B", D("40"), D("3.00"))
        result = compute_entitlement_plan(opening_cif=D("1000"),
                                          groups=[GroupSpec("G", "G", D("100"), (a, b))])
        rows = rows_by_key(result["opening"]["rows"])
        assert (rows["A"]["quantity"], rows["A"]["planned_cif"]) == ("60.000", "120.00")
        assert (rows["B"]["quantity"], rows["B"]["planned_cif"]) == ("40.000", "120.00")
        assert result["opening"]["unplanned_cif"] == "760.00"

    def test_waterfall_reduces_rate_when_cif_runs_out(self):
        a = EntitlementSpec("A", "A", D("100"), D("10"))
        result = compute_entitlement_plan(opening_cif=D("500"), groups=[GroupSpec("G", "G", D("100"), (a,))])
        row = result["opening"]["rows"][0]
        assert row["planned_cif"] == "500.00" and row["unit_price"] == "5.0000"

    def test_residual_capped_at_max_price_reports_unplanned(self):
        a = EntitlementSpec("A", "A", D("100"), D("1.00"), RESIDUAL)
        result = compute_entitlement_plan(opening_cif=D("500"), groups=[GroupSpec("G", "G", D("100"), (a,))])
        after = result["after"]["entitlements"][0]
        assert after["balance"]["cif"] == "100.00"
        assert any(i["code"] == "RESIDUAL_ABOVE_MAX_PRICE" for i in result["issues"])

    def test_decimal_precision_no_float_drift(self):
        a = EntitlementSpec("A", "A", D("33.33"), D("0.10"))
        b = EntitlementSpec("B", "B", D("66.67"), D("0.10"))
        result = compute_entitlement_plan(opening_cif=D("1000000"),
                                          groups=[GroupSpec("G", "G", D("0.003"), (a, b))])
        group = result["opening"]["groups"][0]
        assert group["reconciles"] is True

    def test_recomputing_is_idempotent(self):
        first = compute_entitlement_plan(opening_cif=OPENING_CIF, groups=e126_groups(), debits=spreadsheet_debits())
        second = compute_entitlement_plan(opening_cif=OPENING_CIF, groups=e126_groups(), debits=spreadsheet_debits())
        assert first == second


class TestReviewFindings:
    def test_unplanned_opening_cif_is_labelled_not_as_max_price_cap(self):
        a = EntitlementSpec("A", "A", D("50"), D("2.00"))
        b = EntitlementSpec("B", "B", D("50"), D("8.00"), RESIDUAL)
        # opening 1000; A plans 100, B plans min(400, 900) = 400 -> 500 unplanned at opening
        result = compute_entitlement_plan(opening_cif=D("1000"), groups=[GroupSpec("G", "G", D("100"), (a, b))])
        residual = rows_by_key(result["after"]["entitlements"])["B"]
        codes = {c["code"]: c["cif"] for c in residual["components"]}
        # The 500 left at opening is labelled as such; B's balance cap (50 qty × 8.00 = 400)
        # then leaves exactly that 500 outside B, labelled as the max-price cap.
        assert codes == {"UNPLANNED_OPENING_CIF": "500.00", "UNPLANNED_ABOVE_MAX_PRICE": "-500.00"}
        assert residual["balance"]["cif"] == "400.00"
        assert result["reconciliation"]["unreconciled_cif"] == "500.00"

    def test_no_residual_entitlement_is_not_reported_reconciled(self):
        a = EntitlementSpec("A", "A", D("100"), D("1.00"))
        result = compute_entitlement_plan(opening_cif=D("500"), groups=[GroupSpec("G", "G", D("100"), (a,))])
        assert result["reconciliation"]["unreconciled_cif"] == "400.00"
        assert result["reconciliation"]["status"] == "ATTENTION"
        assert any(i["code"] == "BALANCE_NOT_FULLY_PLANNED" for i in result["issues"])

    def test_spreadsheet_fixture_has_zero_unreconciled(self, plan):
        assert plan["reconciliation"]["unreconciled_cif"] == "0.00"
