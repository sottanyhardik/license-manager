"""Auto Plan split-child reconciliation after explicit BOE/allotment targets.

The SPLIT_BY_PERCENT planner persists ``planned_quantity`` = FUTURE quantity
(target − actual already mapped) and records the actual in provenance
(``actual_target_quantity``).  The reconciliation must therefore use
planned + actual-at-plan as the child's theoretical target; otherwise every
child with real usage looks over-utilised (MANUAL_PLANNING_REQUIRED).

Plans without recorded actual usage (legacy / zero-usage / STANDARD) keep the
previous behaviour exactly.
"""
from decimal import Decimal as D

import pytest

from apps.license.models import LicenseItemPlan
from apps.license.services.planning_usage_reconciliation import reconcile_license_plans
from apps.license.tests.test_entitlement_planning_service import World, e126_rules  # noqa: F401  (fixture)


def _plan(world, rule, item_name, planned, rate, actual=None, strategy="SPLIT_BY_PERCENT"):
    provenance = {"strategy": strategy, "percentage": "50", "theoretical_target_qty": "425810.130"}
    if actual is not None:
        provenance["actual_target_quantity"] = str(actual)
    return LicenseItemPlan.objects.create(
        license=world.licence, import_item=world.veg, item_name=item_name, planning_rule=rule,
        planned_quantity=D(planned), unit_price=D(rate), planned_cif_fc=(D(planned) * D(rate)).quantize(D("0.01")),
        allocation_provenance=provenance)


def _mapped_world(sion, names, number):
    world = World(sion, number)
    pko, olive = names["PALM KERNEL OIL"], names["OLIVE OIL"]
    for boe_no, qty, cif, target in (("B-PKO", "211771", "378141.62", pko), ("B-OL1", "244421.64", "1213378.55", olive)):
        row = world.boe(boe_no, world.veg, qty, cif, target.name)
        boe = row.bill_of_entry
        boe.planning_target_item = target
        boe.planning_mapping_status = "MAPPED_EXPLICIT"
        boe.save(update_fields=["planning_target_item", "planning_mapping_status"])
    for qty, cif, target in (("200000", "360000.00", pko), ("12311", "59092.80", olive)):
        allotment = world.allot(world.veg, qty, cif, target.name)
        allotment.planning_target_item = target
        allotment.planning_mapping_status = "MAPPED_EXPLICIT"
        allotment.save(update_fields=["planning_target_item", "planning_mapping_status"])
    return world


@pytest.mark.django_db
class TestSplitChildren:
    def test_children_show_actual_usage_and_reference_balances(self, e126_rules):  # noqa: F811
        sion, names, veg = e126_rules
        world = _mapped_world(sion, names, "3411000101")
        pko = _plan(world, veg, names["PALM KERNEL OIL"], "14039.130", "1.80", actual="411771.000")
        olive = _plan(world, veg, names["OLIVE OIL"], "169077.490", "5.20", actual="256732.640")
        result = reconcile_license_plans(world.licence.pk)["plans"]

        p, o = result[pko.pk], result[olive.pk]
        assert p["effective_used_quantity"] == D("411771.000")
        assert p["boe_used_quantity"] == D("211771.000")
        assert p["unlinked_allotment_quantity"] == D("200000.000")
        assert p["percentage_theoretical_quantity"] == D("425810.130")
        assert p["raw_remaining_quantity"] == D("14039.130")
        assert p["reconciliation_status"] == "PARTIALLY_UTILIZED"
        assert o["effective_used_quantity"] == D("256732.640")
        assert o["percentage_theoretical_quantity"] == D("425810.130")
        assert o["raw_remaining_quantity"] == D("169077.490")
        assert o["reconciliation_status"] == "PARTIALLY_UTILIZED"
        assert "NOT_USED" not in {p["reconciliation_status"], o["reconciliation_status"]}

    def test_reconciliation_is_read_only_and_repeatable(self, e126_rules):  # noqa: F811
        sion, names, veg = e126_rules
        world = _mapped_world(sion, names, "3411000102")
        _plan(world, veg, names["PALM KERNEL OIL"], "14039.130", "1.80", actual="411771.000")
        before = list(LicenseItemPlan.objects.values_list("pk", "planned_quantity", "planned_cif_fc"))
        first = reconcile_license_plans(world.licence.pk)["plans"]
        second = reconcile_license_plans(world.licence.pk)["plans"]
        assert first == second
        assert before == list(LicenseItemPlan.objects.values_list("pk", "planned_quantity", "planned_cif_fc"))

    def test_new_usage_after_planning_reduces_remaining(self, e126_rules):  # noqa: F811
        sion, names, veg = e126_rules
        world = _mapped_world(sion, names, "3411000103")
        pko = _plan(world, veg, names["PALM KERNEL OIL"], "14039.130", "1.80", actual="411771.000")
        extra = world.allot(world.veg, "4000", "7200", "PKO")
        extra.planning_target_item = names["PALM KERNEL OIL"]
        extra.planning_mapping_status = "MAPPED_EXPLICIT"
        extra.save(update_fields=["planning_target_item", "planning_mapping_status"])
        row = reconcile_license_plans(world.licence.pk)["plans"][pko.pk]
        assert row["raw_remaining_quantity"] == D("10039.130")


    def test_usage_removed_after_planning_restores_full_target(self, e126_rules):  # noqa: F811
        sion, names, veg = e126_rules
        world = World(sion, "3411000104")  # no mapped usage any more
        pko = _plan(world, veg, names["PALM KERNEL OIL"], "14039.130", "1.80", actual="411771.000")
        pko.allocation_provenance["actual_target_cif"] = "738141.62"
        pko.save(update_fields=["allocation_provenance"])
        row = reconcile_license_plans(world.licence.pk)["plans"][pko.pk]
        assert row["raw_remaining_quantity"] == D("425810.130")
        assert row["remaining_cif"] == D("763412.05")  # persisted future CIF + actual CIF at plan
        assert row["reconciliation_status"] == "NOT_USED"

    def test_missing_actual_cif_is_treated_as_zero(self, e126_rules):  # noqa: F811
        sion, names, veg = e126_rules
        world = _mapped_world(sion, names, "3411000105")
        pko = _plan(world, veg, names["PALM KERNEL OIL"], "14039.130", "1.80", actual="411771.000")
        row = reconcile_license_plans(world.licence.pk)["plans"][pko.pk]
        assert row["percentage_theoretical_cif"] == D("25270.43")
        assert row["raw_remaining_quantity"] == D("14039.130")


@pytest.mark.django_db
class TestUnchangedBehaviour:
    """Characterisation: plans without recorded actual usage are untouched."""

    def test_zero_usage_split_keeps_planned_as_theoretical(self, e126_rules):  # noqa: F811
        sion, names, veg = e126_rules
        world = World(sion, "3411000110")
        olive = _plan(world, veg, names["OLIVE OIL"], "300000.000", "5.00")  # CIF-capped, no actual key
        row = reconcile_license_plans(world.licence.pk)["plans"][olive.pk]
        assert row["percentage_theoretical_quantity"] == D("300000.000")
        assert row["reconciliation_status"] == "NOT_USED"
        assert row["remaining_cif"] == D("1500000.00")

    def test_standard_plan_unchanged(self, e126_rules):  # noqa: F811
        sion, names, _veg = e126_rules
        world = World(sion, "3411000111")
        ff = LicenseItemPlan.objects.create(
            license=world.licence, import_item=world.ff, item_name=names["FOOD FLAVOUR"],
            planned_quantity=D("1000"), unit_price=D("2.70"), planned_cif_fc=D("2700.00"),
            allocation_provenance={"strategy": "STANDARD", "actual_target_quantity": "50"})
        row = reconcile_license_plans(world.licence.pk)["plans"][ff.pk]
        assert row["percentage_theoretical_quantity"] == D("1000")
