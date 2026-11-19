"""
CHARACTERISATION tests (pin CURRENT behaviour before the Sunflower/PKO-Olive
pooled-split change). Pure functions, no DB.

Each assertion documents what the code does TODAY. A test that fails after a
future change is a signal to review that change against the owner decisions,
not automatically to "fix" the assertion.
"""
import unittest
from decimal import Decimal

from apps.license.services.e126_plan import (
    OLIVE_OIL as E126_OLIVE,
    PKO as E126_PKO,
    classify_e126_record,
    plan_e126,
    plan_e126_per_item_split,
)
from apps.license.services.e132_plan import (
    CHEESE,
    PKO as E132_PKO,
    classify_e132_record,
    plan_e132,
)


def _items_by_name(result):
    return {row["planning_item_name"]: row for row in result["items"]}


class TestE126CurrentSunflowerAndSplit(unittest.TestCase):
    def test_sunflower_oil_is_unclassified_today(self):
        # Sunflower (HSN 1512) has no E126 rule: it lands in the exception report.
        self.assertEqual(classify_e126_record("15121110", "Sunflower Oil crude"), (None, None))
        self.assertEqual(classify_e126_record(None, "sunflower oil"), (None, None))

    def test_olive_oil_1509_is_olive_bucket_today(self):
        item, _reason = classify_e126_record("1509", "olive oil")
        self.assertEqual(item, E126_OLIVE)

    def test_split_is_decided_per_record_not_pooled(self):
        # PKO-alone 50 (1513) + one split record 50 (1513 + 1509 signal).
        # Pooled Q=100 would give 50/50; CURRENT per-record split gives PKO 75 / Olive 25.
        recs = [
            {"record_id": 1, "hs_code": "1513", "description": "palm kernel oil", "quantity": Decimal("50")},
            {"record_id": 2, "hs_code": "15132900", "description": "1509 blend", "quantity": Decimal("50")},
        ]
        result = plan_e126(recs, balance_cif=None)
        items = _items_by_name(result)
        self.assertEqual(items[E126_PKO]["total_quantity"], Decimal("75"))
        self.assertEqual(items[E126_OLIVE]["total_quantity"], Decimal("25"))
        self.assertEqual(items[E126_PKO]["planning_value"], Decimal("135.000"))
        self.assertEqual(items[E126_OLIVE]["planning_value"], Decimal("125.000"))
        self.assertEqual(result["total_planned"], Decimal("260.000"))

    def test_capped_mixed_case_is_rebalanced_by_value_not_50_50(self):
        # With a generous balance the wastage pass moves split-record PKO into Olive
        # (value gain), so the outcome is 50/50 here only by coincidence of the data.
        recs = [
            {"record_id": 1, "hs_code": "1513", "description": "palm kernel oil", "quantity": Decimal("50")},
            {"record_id": 2, "hs_code": "15132900", "description": "1509 blend", "quantity": Decimal("50")},
        ]
        result = plan_e126(recs, balance_cif=Decimal("1000"))
        items = _items_by_name(result)
        self.assertEqual(items[E126_PKO]["total_quantity"], Decimal("50"))
        self.assertEqual(items[E126_OLIVE]["total_quantity"], Decimal("50"))
        self.assertEqual(result["total_planned"], Decimal("340.000"))
        self.assertEqual(result["wastage"], Decimal("660.000"))

    def test_split_quantity_decimal_precision_is_exact(self):
        lines = plan_e126_per_item_split(
            [{"record_id": 3, "hs_code": "15132900", "description": "1509", "quantity": Decimal("12.5")}],
            balance_cif=None,
        )[3]
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[E126_PKO]["planned_quantity"], Decimal("6.25"))
        self.assertEqual(by[E126_OLIVE]["planned_quantity"], Decimal("6.25"))
        self.assertEqual(by[E126_PKO]["planned_cif"], Decimal("11.2500"))
        self.assertEqual(by[E126_OLIVE]["planned_cif"], Decimal("31.2500"))

    def test_split_record_is_one_record_one_contribution_per_target(self):
        # No double counting: the split record's quantity is fully distributed once.
        recs = [{"record_id": 4, "hs_code": "15132900", "description": "1509", "quantity": Decimal("100")}]
        lines = plan_e126_per_item_split(recs, balance_cif=None)[4]
        self.assertEqual(sum((L["planned_quantity"] for L in lines), Decimal("0")), Decimal("100"))

    def test_replan_is_idempotent(self):
        recs = [{"record_id": 5, "hs_code": "15132900", "description": "1509", "quantity": Decimal("40")}]
        first = plan_e126(recs, balance_cif=Decimal("500"))
        second = plan_e126(recs, balance_cif=Decimal("500"))
        self.assertEqual(first["total_planned"], second["total_planned"])
        self.assertEqual(
            [(i["planning_item_name"], i["total_quantity"]) for i in first["items"]],
            [(i["planning_item_name"], i["total_quantity"]) for i in second["items"]],
        )


class TestE132CurrentVegOil(unittest.TestCase):
    def test_olive_oil_1509_is_unclassified_in_e132_today(self):
        # E132 has NO Olive Oil bucket: an Olive record is an exception today.
        self.assertEqual(classify_e132_record("1509", "olive oil"), (None, None))

    def test_sunflower_is_unclassified_in_e132_today(self):
        self.assertEqual(classify_e132_record("1512", "sunflower oil"), (None, None))

    def test_pko_cheese_split_40_60_uncapped(self):
        result = plan_e132(
            [{"record_id": 9, "hs_code": "15132900", "description": "Vegetable Oil Dairy 0406", "quantity": Decimal("100")}],
            balance_cif=None,
        )
        items = _items_by_name(result)
        self.assertEqual(items[E132_PKO]["total_quantity"], Decimal("40"))
        self.assertEqual(items[CHEESE]["total_quantity"], Decimal("60"))
        self.assertEqual(items[E132_PKO]["planning_value"], Decimal("72.000"))
        self.assertEqual(items[CHEESE]["planning_value"], Decimal("330.000"))

    def test_pko_cheese_split_capped_at_balance_439(self):
        result = plan_e132(
            [{"record_id": 9, "hs_code": "15132900", "description": "Vegetable Oil Dairy 0406", "quantity": Decimal("100")}],
            balance_cif=Decimal("439"),
        )
        items = _items_by_name(result)
        self.assertEqual(items[E132_PKO]["total_quantity"], Decimal("30"))
        self.assertEqual(items[CHEESE]["total_quantity"], Decimal("70"))
        self.assertEqual(result["wastage"], Decimal("0.000"))


if __name__ == "__main__":
    unittest.main()
