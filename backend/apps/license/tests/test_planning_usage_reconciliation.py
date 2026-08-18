from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import ANY
from types import SimpleNamespace

import pytest

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.core.models import CompanyModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.serializers import LicenseItemPlanSerializer
from apps.license.services.planning_usage_reconciliation import (
    aggregate_license_usage,
    normalize_planning_family,
    reconcile_split_allocation,
    reconcile_license_plans,
    apply_operational_cif_ceiling,
)
from apps.license.services.planning_tolerances import apply_remaining_plan_tolerance
from apps.license.services.planning_operational_snapshot import planning_operational_snapshots


@pytest.mark.parametrize(("name", "family"), [
    ("PKO", "PKO"),
    (" palm   kernel oil ", "PKO"),
    ("PALM KERNEL", "PKO"),
    ("PALM KERNEL OIL - E126", "PKO"),
    ("OLIVE OIL", "OLIVE_OIL"),
    ("OLIVE", "OLIVE_OIL"),
    ("Olive Oil - E126", "OLIVE_OIL"),
    ("CHEESE", "CHEESE"),
    ("CREAM", "CHEESE"),
    ("BUTTER", "CHEESE"),
    ("FOOD FLAVOR", "FOOD_FLAVOUR"),
    ("UNKNOWN PRODUCT", None),
])
def test_family_mapping(name, family):
    assert normalize_planning_family(name) == family


@pytest.mark.parametrize(("source", "theoretical", "used", "expected", "excess"), [
    ("58337", ("35003", "23334"), ("58337", "0"), ("58337", "0"), "0"),
    ("100000", ("60000", "40000"), ("70000", "10000"), ("70000", "30000"), "0"),
    ("100000", ("60000", "40000"), ("75000", "25000"), ("75000", "25000"), "0"),
    ("58337", ("35003", "23334"), ("60000", "0"), ("58337", "0"), "1663"),
    ("100000", ("60000", "40000"), ("60000", "15000"), ("60000", "40000"), "0"),
])
def test_split_reallocation_respects_actual_commitments(source, theoretical, used, expected, excess):
    result = reconcile_split_allocation(
        Decimal(source),
        [{"key": "OLIVE", "theoretical_qty": Decimal(theoretical[0])},
         {"key": "PKO", "theoretical_qty": Decimal(theoretical[1])}],
        {"OLIVE": Decimal(used[0]), "PKO": Decimal(used[1])},
    )
    assert tuple(row["reconciled_qty"] for row in result["rows"]) == tuple(map(Decimal, expected))
    assert result["group_excess_quantity"] == Decimal(excess)
    assert result["manual_review_required"] is (Decimal(excess) > 0)


@pytest.mark.parametrize(("quantity", "cif", "expected_quantity", "expected_cif"), [
    ("99.999", "123.45", "0.000", "0.00"),
    ("100.000", "123.45", "100.000", "123.45"),
    ("100.001", "123.45", "100.001", "123.45"),
    ("-0.001", "-1.00", "-0.001", "-1.00"),
])
def test_remaining_plan_tolerance_boundaries(quantity, cif, expected_quantity, expected_cif):
    result = apply_remaining_plan_tolerance(Decimal(quantity), Decimal(cif))
    assert result == (Decimal(expected_quantity), Decimal(expected_cif))


def _ceiling_plan(plan_id, price, priority=1):
    return SimpleNamespace(
        id=plan_id, unit_price=Decimal(price), planning_rule_id=plan_id,
        planning_rule=SimpleNamespace(priority=priority),
    )


def _ceiling_row(quantity, cif):
    return {
        "remaining_quantity": Decimal(quantity), "remaining_cif": Decimal(cif),
        "reconciliation_status": "PARTIALLY_UTILIZED",
    }


def test_operational_cif_ceiling_caps_single_future_row():
    row = _ceiling_row("120000", "120000")
    effective = apply_operational_cif_ceiling([(_ceiling_plan(1, "1"), row)], Decimal("100000"))
    assert effective == Decimal("100000")
    assert row["remaining_cif"] == Decimal("100000.00")
    assert row["remaining_quantity"] == Decimal("100000.000")


def test_operational_cif_ceiling_uses_deterministic_rule_priority():
    first = _ceiling_row("60000", "60000")
    second = _ceiling_row("50000", "50000")
    apply_operational_cif_ceiling(
        [(_ceiling_plan(2, "1", priority=2), second), (_ceiling_plan(1, "1", priority=1), first)],
        Decimal("100000"),
    )
    assert first["remaining_cif"] == Decimal("60000")
    assert second["remaining_cif"] == Decimal("40000.00")


def test_operational_cif_ceiling_honours_balance_tolerance():
    row = _ceiling_row("1000", "1000")
    effective = apply_operational_cif_ceiling([(_ceiling_plan(1, "1"), row)], Decimal("499.99"))
    assert effective == Decimal("0.00")
    assert row["remaining_quantity"] == Decimal("0.000")
    assert row["remaining_cif"] == Decimal("0.00")


def test_operational_cif_ceiling_matches_the_notification_regression_aggregate():
    """The report aggregate must be the sum of capped license rows."""
    balance = Decimal("8292469.31")
    raw_plan = Decimal("8838777.54")
    row = _ceiling_row(raw_plan, raw_plan)

    apply_operational_cif_ceiling([(_ceiling_plan(1, "1"), row)], balance)

    assert row["pre_balance_remaining_cif"] == raw_plan
    assert row["remaining_cif"] == balance
    assert row["remaining_cif"] <= balance


def test_operational_cif_ceiling_never_creates_negative_future_plan_for_negative_balance():
    row = _ceiling_row("1000", "1000")

    apply_operational_cif_ceiling([(_ceiling_plan(1, "1"), row)], Decimal("-1.00"))

    assert row["remaining_quantity"] == Decimal("0.000")
    assert row["remaining_cif"] == Decimal("0.00")


@pytest.mark.django_db
def test_operational_cif_ceiling_is_idempotent(reconciliation_setup):
    _company, license_obj, _import_item, _plan = reconciliation_setup

    first = reconcile_license_plans(license_obj.id)
    second = reconcile_license_plans(license_obj.id)

    assert first == second


@pytest.fixture
def reconciliation_setup(db):
    company = CompanyModel.objects.create(iec="LEVEL2REC", name="Level 2 Reconciliation")
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company,
        license_number="LEVEL2-PLAN",
        license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30),
    )
    LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("2000000"))
    pko = ItemNameModel.objects.create(name="PALM KERNEL OIL - E126", is_active=True)
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="Vegetable oil", unit="KG",
        quantity=Decimal("321138"), available_quantity=Decimal("321138"),
    )
    import_item.items.add(pko)
    plan = LicenseItemPlan.objects.create(
        license=license_obj, import_item=import_item, item_name=pko,
        planned_quantity=Decimal("321138"), unit_price=Decimal("1.80"),
        planned_cif_fc=Decimal("578048.40"),
    )
    return company, license_obj, import_item, plan


@pytest.mark.django_db
def test_reconciliation_subtracts_boe_and_only_unlinked_allotment(reconciliation_setup):
    company, license_obj, import_item, plan = reconciliation_setup
    boe = BillOfEntryModel.objects.create(company=company, bill_of_entry_number="BOE-L2-1", product_name="PKO")
    RowDetails.objects.create(
        bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
        qty=Decimal("20000"), cif_fc=Decimal("40000"),
    )

    open_allotment = AllotmentModel.objects.create(
        company=company, item_name="PALM KERNEL", required_quantity=Decimal("5000"),
        unit_value_per_unit=Decimal("2"),
    )
    AllotmentItems.objects.create(
        allotment=open_allotment, item=import_item, qty=Decimal("5000"), cif_fc=Decimal("10000"),
    )

    linked_allotment = AllotmentModel.objects.create(
        company=company, item_name="PKO", required_quantity=Decimal("10000"),
        unit_value_per_unit=Decimal("5"), is_boe=True,
    )
    AllotmentItems.objects.create(
        allotment=linked_allotment, item=import_item, qty=Decimal("10000"), cif_fc=Decimal("50000"), is_boe=True,
    )
    boe.allotment.add(linked_allotment)

    result = reconcile_license_plans(license_obj.id)["plans"][plan.id]
    assert result["boe_used_quantity"] == Decimal("20000")
    assert result["boe_used_cif"] == Decimal("40000")
    assert result["unlinked_allotment_quantity"] == Decimal("5000")
    assert result["unlinked_allotment_cif"] == Decimal("10000")
    assert result["effective_used_quantity"] == Decimal("25000")
    assert result["effective_used_cif"] == Decimal("50000")
    assert result["remaining_quantity"] == Decimal("296138")
    assert result["remaining_cif"] == Decimal("533048.40")
    assert result["reconciliation_status"] == "PARTIALLY_UTILIZED"

    payload = LicenseItemPlanSerializer(plan).data
    assert payload["planned_quantity"] == "321138.000"
    assert payload["planned_cif_fc"] == "578048.40"
    assert payload["remaining_quantity"] == "296138.000"
    assert payload["remaining_cif"] == "533048.40"
    assert payload["status"] == "PARTIALLY_UTILIZED"


@pytest.mark.django_db
def test_actual_debit_overrides_license_split_and_small_sibling_residual(reconciliation_setup):
    company, license_obj, import_item, pko_plan = reconciliation_setup
    import_item.quantity = Decimal("58337.000")
    import_item.save(update_fields=["quantity"])
    pko_plan.planned_quantity = Decimal("23334.800")
    pko_plan.planned_cif_fc = Decimal("42002.64")
    pko_plan.save(update_fields=["planned_quantity", "planned_cif_fc"])
    olive = ItemNameModel.objects.create(name="OLIVE OIL - E126", is_active=True)
    olive_plan = LicenseItemPlan.objects.create(
        license=license_obj, import_item=import_item, item_name=olive,
        planned_quantity=Decimal("35002.200"), unit_price=Decimal("5.00"),
        planned_cif_fc=Decimal("175011.00"),
    )
    boe = BillOfEntryModel.objects.create(
        company=company, bill_of_entry_number="BOE-ACTUAL-FIRST", product_name="OLIVE OIL",
    )
    RowDetails.objects.create(
        bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
        qty=Decimal("58336.900"), cif_fc=Decimal("287877.13"),
    )

    result = reconcile_license_plans(license_obj.id)
    olive_result = result["plans"][olive_plan.id]
    pko_result = result["plans"][pko_plan.id]
    assert olive_result["percentage_theoretical_quantity"] == Decimal("35002.200")
    assert olive_result["theoretical_quantity"] == Decimal("58336.900")
    assert olive_result["theoretical_cif"] == Decimal("287877.13")
    assert olive_result["remaining_quantity"] == Decimal("0.000")
    assert olive_result["remaining_cif"] == Decimal("0.00")
    assert pko_result["percentage_theoretical_quantity"] == Decimal("23334.800")
    assert pko_result["theoretical_quantity"] == Decimal("0.100")
    assert pko_result["raw_remaining_quantity"] == Decimal("0.100")
    assert pko_result["remaining_quantity"] == Decimal("0.000")
    assert pko_result["remaining_cif"] == Decimal("0.00")
    assert result["groups"][import_item.id]["manual_review_required"] is False


@pytest.mark.django_db
def test_pivot_snapshot_uses_complete_original_source_group(reconciliation_setup):
    company, license_obj, import_item, pko_plan = reconciliation_setup
    import_item.quantity = Decimal("637466.100")
    import_item.save(update_fields=["quantity"])
    olive = ItemNameModel.objects.create(name="OLIVE OIL - E126", is_active=True)
    import_item.items.add(olive)
    for serial, quantity in ((2, "972.000"), (3, "3839.870")):
        extra = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=serial, description="Vegetable oil",
            unit="KG", quantity=Decimal(quantity), available_quantity=Decimal(quantity),
        )
        extra.items.add(olive, pko_plan.item_name)
    olive_plan = LicenseItemPlan.objects.create(
        license=license_obj, import_item=import_item, item_name=olive,
        planned_quantity=Decimal("385366.200"), unit_price=Decimal("5.00"),
        planned_cif_fc=Decimal("1926831.00"),
    )
    pko_plan.planned_quantity = Decimal("256910.800")
    pko_plan.save(update_fields=["planned_quantity"])
    boe = BillOfEntryModel.objects.create(
        company=company, bill_of_entry_number="BOE-GROUP-SNAPSHOT", product_name="OLIVE OIL",
    )
    RowDetails.objects.create(
        bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
        qty=Decimal("51286.840"), cif_fc=Decimal("284982.98"),
    )
    allotment = AllotmentModel.objects.create(
        company=company, item_name="OLIVE OIL", required_quantity=Decimal("26711.000"),
        unit_value_per_unit=Decimal("4.87"),
    )
    AllotmentItems.objects.create(
        allotment=allotment, item=import_item, qty=Decimal("26711.000"), cif_fc=Decimal("130033.87"),
    )

    snapshot = planning_operational_snapshots(license_obj.id)[olive_plan.id]
    assert snapshot["original_total_qty"] == Decimal("642277")
    assert snapshot["original_total_qty"] != Decimal("637466.100")
    assert snapshot["boe_debited_qty"] == Decimal("51286.840")
    assert snapshot["unlinked_allotment_qty"] == Decimal("26711.000")
    assert snapshot["balance_qty"] == Decimal("564279.160")

    olive_plan.planned_quantity = Decimal("1.000")
    olive_plan.save(update_fields=["planned_quantity"])
    rebuilt = planning_operational_snapshots(license_obj.id)[olive_plan.id]
    assert rebuilt["original_total_qty"] == Decimal("642277")
    assert rebuilt["balance_qty"] == Decimal("564279.160")


@pytest.mark.django_db
def test_linked_allotment_and_boe_are_not_double_counted(reconciliation_setup):
    company, license_obj, import_item, _plan = reconciliation_setup
    allotment = AllotmentModel.objects.create(
        company=company, item_name="PKO", required_quantity=Decimal("10000"),
        unit_value_per_unit=Decimal("5"),
    )
    AllotmentItems.objects.create(
        allotment=allotment, item=import_item, qty=Decimal("10000"), cif_fc=Decimal("50000"),
    )
    boe = BillOfEntryModel.objects.create(company=company, bill_of_entry_number="BOE-L2-DEDUPE", product_name="PKO")
    boe.allotment.add(allotment)
    RowDetails.objects.create(
        bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
        qty=Decimal("10000"), cif_fc=Decimal("50000"),
    )

    pko = aggregate_license_usage(license_obj.id)["families"]["PKO"]
    assert pko["boe_used_quantity"] == Decimal("10000")
    assert pko["boe_used_cif"] == Decimal("50000")
    assert pko["unlinked_allotment_quantity"] == Decimal("0")
    assert pko["unlinked_allotment_cif"] == Decimal("0")


@pytest.mark.django_db
def test_unknown_usage_is_reported_not_applied(reconciliation_setup):
    company, license_obj, import_item, plan = reconciliation_setup
    unknown = ItemNameModel.objects.create(name="MYSTERY POWDER", is_active=True)
    import_item.items.clear()
    import_item.items.add(unknown)
    boe = BillOfEntryModel.objects.create(company=company, bill_of_entry_number="BOE-UNKNOWN", product_name="MYSTERY POWDER")
    RowDetails.objects.create(
        bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
        qty=Decimal("25"), cif_fc=Decimal("75"),
    )

    result = reconcile_license_plans(license_obj.id)
    assert result["plans"][plan.id]["effective_used_quantity"] == Decimal("0")
    assert result["unmapped_usage"] == [{
        "source": "BOE", "record_id": ANY,
        "record_number": "BOE-UNKNOWN", "product_name": "MYSTERY POWDER",
        "quantity": Decimal("25"), "cif_fc": Decimal("75"),
    }]
