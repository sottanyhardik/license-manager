"""
Unit + edge-case tests for the E132 planning classification engine
(apps.license.services.e132_plan). Pure functions — no DB required.
"""
import unittest
from decimal import Decimal

from decimal import Decimal as _Dec

from apps.license.services.e132_plan import (
    ALUMINIUM, CHEESE, MILK, PKO, RBD, YEAST, UNIT_PRICE, PLANNING_ORDER,
    NUT_NUTS, RAISIN_ITEM, CEREALS_FLAKES, CMC,
    classify_e132_record, plan_e132, plan_e132_per_item,
)


class TestPriorityOrder(unittest.TestCase):
    def test_planning_order(self):
        # Yeast → Cheese → PKO → RBD → Milk → Aluminium Foil → NUT & NUTS →
        # RAISIN → CEREALS FLAKES → CMC
        self.assertEqual(
            PLANNING_ORDER,
            (YEAST, CHEESE, PKO, RBD, MILK, ALUMINIUM,
             NUT_NUTS, RAISIN_ITEM, CEREALS_FLAKES, CMC),
        )


class TestNutRaisinCereals(unittest.TestCase):
    """The three added planning items (NUT & NUTS / RAISIN / CEREALS FLAKES)."""

    def test_nut_by_hsn_prefix(self):
        self.assertEqual(classify_e132_record("08021100", "almonds")[0], NUT_NUTS)

    def test_nut_by_desc_code(self):
        self.assertEqual(classify_e132_record("9999", "cashew 0802 grade a")[0], NUT_NUTS)

    def test_nut_excluded_when_milk(self):
        # 0802 present but description mentions milk → NOT nuts.
        self.assertNotEqual(classify_e132_record("08021100", "milk coated nut")[0], NUT_NUTS)

    def test_nut_excluded_when_0806(self):
        # both 0802 and 0806 signals → nuts rule bows out (0806 wins → RAISIN).
        self.assertEqual(classify_e132_record("08021100", "mix 0806")[0], RAISIN_ITEM)

    def test_raisin_by_hsn_prefix(self):
        self.assertEqual(classify_e132_record("08061000", "raisins")[0], RAISIN_ITEM)

    def test_raisin_by_desc_code(self):
        self.assertEqual(classify_e132_record("9999", "dried grapes 0806")[0], RAISIN_ITEM)

    def test_cereals_by_hsn_prefix(self):
        # ⚠ ASSUMED rule: HSN 1104 (confirm with business).
        self.assertEqual(classify_e132_record("11041200", "rolled oats")[0], CEREALS_FLAKES)

    def test_new_item_prices(self):
        self.assertEqual(UNIT_PRICE[NUT_NUTS], _Dec("10.00"))
        self.assertEqual(UNIT_PRICE[RAISIN_ITEM], _Dec("4.00"))
        self.assertEqual(UNIT_PRICE[CEREALS_FLAKES], _Dec("0.60"))
        self.assertIsNone(UNIT_PRICE[CMC])  # CMC price still TBD

    def test_raisin_priced_value(self):
        # 100 × $4 = 400, within a generous balance.
        recs = [{"record_id": 1, "quantity": 100, "hs_code": "08061000", "description": "raisins"}]
        out = plan_e132(recs, balance_cif=None)
        raisin = next(i for i in out["items"] if i["planning_item_name"] == RAISIN_ITEM)
        self.assertEqual(float(raisin["total_quantity"]), 100.0)
        self.assertEqual(float(raisin["planning_value"]), 400.0)

    def test_cmc_matches_nothing(self):
        # Placeholder rule — no criteria supplied → CMC never classified.
        self.assertNotEqual(classify_e132_record("cmc", "cmc powder")[0], CMC)


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

    def test_milk_desc_with_yeast_2106_goes_to_yeast_not_milk(self):
        # 'milk' + 'yeast' + HSN 2106 → Yeast (explicit Milk guard + priority),
        # never Milk.
        item, _ = classify_e132_record("2106", "milk powder with yeast")
        self.assertEqual(item, YEAST)


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

    def test_milk_priced_at_ceiling(self):
        # Milk price = 22 (ceiling of 0–22 range); value = qty × 22; not missing.
        result = plan_e132(self._recs())
        by = {i["planning_item_name"]: i for i in result["items"]}
        self.assertEqual(by[MILK]["unit_price"], Decimal("22.00"))
        self.assertEqual(by[MILK]["planning_value"], Decimal("3") * Decimal("22.00"))
        self.assertTrue(by[MILK]["unit_price_defined"])
        self.assertNotIn(MILK, result["missing_inputs"])

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
        # Milk: priced at the 22 ceiling → planned_cif = qty × 22
        self.assertEqual(per[2]["planning_item"], MILK)
        self.assertEqual(per[2]["unit_price"], Decimal("22.00"))
        self.assertEqual(per[2]["planned_cif"], Decimal("4") * Decimal("22.00"))


class TestBalanceCap(unittest.TestCase):
    """Max debit per licence = Balance CIF (waterfall cap, like E1/E5)."""

    def _recs(self):
        return [
            {"record_id": 1, "hs_code": "0401", "description": "butter", "quantity": Decimal("10")},  # Cheese 10×5=50
            {"record_id": 2, "hs_code": "1513", "description": "pko", "quantity": Decimal("10")},      # PKO 10×2.3=23
        ]

    def test_total_planned_never_exceeds_balance(self):
        res = plan_e132(self._recs(), balance_cif=Decimal("60"))
        by = {i["planning_item_name"]: i for i in res["items"]}
        # Cheese (higher priority) takes its full 50; PKO gets only the remaining 10.
        self.assertEqual(by[CHEESE]["planning_value"], Decimal("50"))
        self.assertEqual(by[CHEESE]["unit_price"], Decimal("5.00"))       # uncapped → max
        self.assertEqual(by[PKO]["planning_value"], Decimal("10"))        # capped
        self.assertEqual(by[PKO]["unit_price"], Decimal("1"))             # 10/10, rate dropped
        self.assertEqual(by[PKO]["max_unit_price"], Decimal("2.30"))      # ceiling preserved
        self.assertEqual(res["total_planned"], Decimal("60"))
        self.assertEqual(res["wastage"], Decimal("0"))
        self.assertLessEqual(res["total_planned"], Decimal("60"))

    def test_wastage_when_balance_exceeds_demand(self):
        recs = [{"record_id": 1, "hs_code": "0401", "description": "b", "quantity": Decimal("2")}]  # 2×5=10
        res = plan_e132(recs, balance_cif=Decimal("100"))
        self.assertEqual(res["total_planned"], Decimal("10"))
        self.assertEqual(res["wastage"], Decimal("90"))

    def test_per_item_uses_capped_effective_rate(self):
        per = plan_e132_per_item(self._recs(), balance_cif=Decimal("60"))
        self.assertEqual(per[1]["planned_cif"], Decimal("50"))
        self.assertEqual(per[2]["unit_price"], Decimal("1"))   # PKO rate capped
        self.assertEqual(per[2]["planned_cif"], Decimal("10"))
        # per-item planned values sum to <= balance
        self.assertLessEqual(sum(p["planned_cif"] for p in per.values()), Decimal("60"))


class TestFixedPrices(unittest.TestCase):
    def test_price_table(self):
        self.assertEqual(UNIT_PRICE[CHEESE], Decimal("5.00"))
        self.assertEqual(UNIT_PRICE[PKO], Decimal("2.30"))
        self.assertEqual(UNIT_PRICE[RBD], Decimal("1.20"))
        self.assertEqual(UNIT_PRICE[YEAST], Decimal("3.00"))
        self.assertEqual(UNIT_PRICE[ALUMINIUM], Decimal("4.50"))
        self.assertEqual(UNIT_PRICE[MILK], Decimal("22.00"))


if __name__ == "__main__":
    unittest.main()
