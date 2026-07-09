"""
Unit + edge-case tests for the E132 planning classification engine
(apps.license.services.e132_plan). Pure functions — no DB required.
"""
import unittest
from decimal import Decimal

from apps.license.services.e132_plan import (
    ALUMINIUM, CHEESE, MILK, PKO, RBD, YEAST, UNIT_PRICE,
    classify_e132_record, plan_e132, plan_e132_per_item,
)


class TestClassifyPositive(unittest.TestCase):
    """Each item matches on each of its stated conditions."""

    def test_cheese_by_hsn(self):
        for code in ("0401", "0405", "0406", "2106"):
            self.assertEqual(classify_e132_record(code, "anything")[0], CHEESE)

    def test_cheese_by_oil_keyword(self):
        item, reason = classify_e132_record("9999", "Refined OIL blend")
        self.assertEqual(item, CHEESE)
        self.assertIn("oil", reason.lower())

    def test_pko(self):
        self.assertEqual(classify_e132_record("1513", "")[0], PKO)
        self.assertEqual(classify_e132_record(None, "PKO stearin")[0], PKO)
        self.assertEqual(classify_e132_record(None, "palm KERNEL")[0], PKO)

    def test_rbd(self):
        self.assertEqual(classify_e132_record("1511", "")[0], RBD)
        self.assertEqual(classify_e132_record(None, "RBD grade")[0], RBD)
        self.assertEqual(classify_e132_record(None, "Palmolein superfine")[0], RBD)

    def test_yeast_requires_both(self):
        self.assertEqual(classify_e132_record("2106", "instant YEAST")[0], YEAST)

    def test_aluminium(self):
        self.assertEqual(classify_e132_record("7607", "")[0], ALUMINIUM)
        self.assertEqual(classify_e132_record(None, "foil HSN 7607 rolls")[0], ALUMINIUM)

    def test_milk(self):
        self.assertEqual(classify_e132_record(None, "whole MILK")[0], MILK)
        self.assertEqual(classify_e132_record(None, "MILK SOLID not fat")[0], MILK)
        self.assertEqual(classify_e132_record("3502", "")[0], MILK)
        self.assertEqual(classify_e132_record(None, "code 3502 albumin")[0], MILK)


class TestHsnMatching(unittest.TestCase):
    def test_prefix_and_formatting(self):
        # equal, prefix (longer code), and dotted/spaced formats all match 0401
        for hs in ("0401", "04012000", "0401.20.00", "0401 20 00"):
            self.assertEqual(classify_e132_record(hs, "")[0], CHEESE)

    def test_non_matching_hsn(self):
        self.assertEqual(classify_e132_record("8888", ""), (None, None))


class TestOverlapAndPriority(unittest.TestCase):
    def test_yeast_overrides_cheese_for_2106(self):
        # HSN 2106 + 'yeast' → Yeast (corrected priority), NOT Cheese.
        item, reason = classify_e132_record("2106", "dried yeast")
        self.assertEqual(item, YEAST)

    def test_2106_without_yeast_is_cheese(self):
        self.assertEqual(classify_e132_record("2106", "flavour base")[0], CHEESE)

    def test_oil_keyword_beats_pko_and_rbd(self):
        # Priority: Item 1 'oil' wins over PKO/RBD when description has 'oil'.
        self.assertEqual(classify_e132_record(None, "palm kernel oil")[0], CHEESE)
        self.assertEqual(classify_e132_record(None, "RBD palmolein oil")[0], CHEESE)

    def test_pko_beats_rbd_when_no_oil(self):
        # HSN 1513 (PKO) wins even if description mentions palmolein (RBD).
        self.assertEqual(classify_e132_record("1513", "palmolein")[0], PKO)


class TestNullAndBlankSafe(unittest.TestCase):
    def test_both_null(self):
        self.assertEqual(classify_e132_record(None, None), (None, None))

    def test_blank_strings(self):
        self.assertEqual(classify_e132_record("", "   "), (None, None))

    def test_null_hsn_desc_match(self):
        self.assertEqual(classify_e132_record(None, "  Milk  ")[0], MILK)


class TestCaseInsensitiveAndTrim(unittest.TestCase):
    def test_mixed_case(self):
        for desc in ("YEAST", "Yeast", "yEaSt"):
            self.assertEqual(classify_e132_record("2106", desc)[0], YEAST)

    def test_whitespace_normalized(self):
        self.assertEqual(classify_e132_record(None, "  palm   KERNEL  ")[0], PKO)


class TestNoDoubleCounting(unittest.TestCase):
    def test_each_record_exactly_one_item(self):
        # A record hitting several rules' keywords still lands in exactly one.
        records = [
            {"record_id": 1, "hs_code": "2106", "description": "yeast extract"},  # Yeast
            {"record_id": 2, "hs_code": "2106", "description": "cheese"},          # Cheese
            {"record_id": 3, "hs_code": "1513", "description": "rbd palmolein"},   # PKO (hsn wins)
            {"record_id": 4, "hs_code": "1511", "description": "milk"},            # RBD (hsn wins)
        ]
        for r in records:
            r["quantity"] = Decimal("1")
        result = plan_e132(records)
        # 4 records, 4 distinct items, each count == 1 → no double counting.
        counts = {i["planning_item_name"]: i["num_source_records"] for i in result["items"]}
        self.assertEqual(sum(counts.values()), 4)
        self.assertEqual(counts, {YEAST: 1, CHEESE: 1, PKO: 1, RBD: 1})


class TestAggregation(unittest.TestCase):
    def _recs(self):
        return [
            {"record_id": "A", "hs_code": "0401", "description": "butter", "quantity": Decimal("10")},
            {"record_id": "B", "hs_code": "0406", "description": "cheese", "quantity": Decimal("5.5")},
            {"record_id": "C", "hs_code": "7607", "description": "foil",   "quantity": Decimal("100")},
            {"record_id": "D", "hs_code": "9999", "description": "milk powder", "quantity": Decimal("3")},
            {"record_id": "E", "hs_code": "8888", "description": "unclassifiable widget", "quantity": Decimal("7")},
        ]

    def test_quantity_summed_per_item(self):
        result = plan_e132(self._recs())
        by = {i["planning_item_name"]: i for i in result["items"]}
        self.assertEqual(by[CHEESE]["total_quantity"], Decimal("15.5"))
        self.assertEqual(by[CHEESE]["num_source_records"], 2)
        self.assertEqual(by[ALUMINIUM]["total_quantity"], Decimal("100"))

    def test_planning_value_uses_fixed_price(self):
        result = plan_e132(self._recs())
        by = {i["planning_item_name"]: i for i in result["items"]}
        self.assertEqual(by[CHEESE]["planning_value"], Decimal("15.5") * Decimal("5.00"))
        self.assertEqual(by[ALUMINIUM]["planning_value"], Decimal("100") * Decimal("4.50"))

    def test_milk_price_is_undefined_and_reported(self):
        result = plan_e132(self._recs())
        by = {i["planning_item_name"]: i for i in result["items"]}
        self.assertIsNone(by[MILK]["unit_price"])
        self.assertIsNone(by[MILK]["planning_value"])
        self.assertFalse(by[MILK]["unit_price_defined"])
        self.assertIn(MILK, result["missing_inputs"])

    def test_exceptions_reported(self):
        result = plan_e132(self._recs())
        self.assertEqual([e.record_id for e in result["exceptions"]], ["E"])

    def test_reason_recorded_for_audit(self):
        result = plan_e132(self._recs())
        reasons = {c.record_id: c.reason for c in result["classified"]}
        self.assertEqual(reasons["A"], "HSN=0401")
        self.assertIsNone(reasons["E"])


class TestPerItemPlanning(unittest.TestCase):
    def test_per_item_price_and_value(self):
        recs = [
            {"record_id": 1, "hs_code": "0401", "description": "butter", "quantity": Decimal("10")},
            {"record_id": 2, "hs_code": None, "description": "whole milk", "quantity": Decimal("4")},
            {"record_id": 3, "hs_code": "8888", "description": "widget", "quantity": Decimal("9")},
        ]
        per = plan_e132_per_item(recs)
        # classified records only (rec 3 unclassified is omitted)
        self.assertEqual(set(per), {1, 2})
        self.assertEqual(per[1]["planning_item"], CHEESE)
        self.assertEqual(per[1]["unit_price"], Decimal("5.00"))
        self.assertEqual(per[1]["planned_cif"], Decimal("50.00"))
        # Milk: price undefined → planned_cif None (never invented)
        self.assertEqual(per[2]["planning_item"], MILK)
        self.assertIsNone(per[2]["unit_price"])
        self.assertIsNone(per[2]["planned_cif"])


class TestFixedPrices(unittest.TestCase):
    def test_price_table(self):
        self.assertEqual(UNIT_PRICE[CHEESE], Decimal("5.00"))
        self.assertEqual(UNIT_PRICE[PKO], Decimal("2.30"))
        self.assertEqual(UNIT_PRICE[RBD], Decimal("1.20"))
        self.assertEqual(UNIT_PRICE[YEAST], Decimal("3.00"))
        self.assertEqual(UNIT_PRICE[ALUMINIUM], Decimal("4.50"))
        self.assertIsNone(UNIT_PRICE[MILK])


if __name__ == "__main__":
    unittest.main()
