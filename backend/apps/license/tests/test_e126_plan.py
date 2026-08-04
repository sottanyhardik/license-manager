"""
Unit + edge-case tests for the E126 planning classification engine
(apps.license.services.e126_plan). Pure functions — no DB required.
Mirrors test_e132_plan.py's structure, simplified for E126's 3-item
priority set (Nuts / PKO / Olive Oil).
"""
import unittest
from decimal import Decimal

from apps.license.services.e126_plan import (
    NUT_NUTS, OLIVE_OIL, PKO, UNIT_PRICE, PLANNING_ORDER,
    classify_e126_record, plan_e126, plan_e126_per_item, plan_e126_per_item_split,
)


class TestPriorityOrder(unittest.TestCase):
    def test_planning_order(self):
        # Nuts → PKO → Olive Oil. Immutable per the E126 Auto Planning
        # business rules.
        self.assertEqual(PLANNING_ORDER, (NUT_NUTS, PKO, OLIVE_OIL))


class TestFixedPrices(unittest.TestCase):
    def test_price_table(self):
        self.assertEqual(UNIT_PRICE[NUT_NUTS], Decimal("3.00"))
        self.assertEqual(UNIT_PRICE[PKO], Decimal("1.80"))
        self.assertEqual(UNIT_PRICE[OLIVE_OIL], Decimal("5.00"))


class TestNuts(unittest.TestCase):
    """Priority 1 — 0802 (HSN or desc) AND the WORD 'nut'/'nuts' in the description."""

    def test_by_hsn_prefix_and_word(self):
        self.assertEqual(classify_e126_record("08021100", "Cashew Nuts")[0], NUT_NUTS)

    def test_by_desc_code_and_word(self):
        self.assertEqual(classify_e126_record("9999", "cashew 0802 grade nut")[0], NUT_NUTS)

    def test_singular_word_matches(self):
        self.assertEqual(classify_e126_record("08021100", "Almond Nut")[0], NUT_NUTS)

    def test_0802_without_nut_word_does_not_match(self):
        self.assertEqual(classify_e126_record("08021100", "Almond Kernel")[0], None)

    def test_word_boundary_excludes_peanut(self):
        # 'Peanut' does not contain the standalone word 'nut' or 'nuts'.
        self.assertEqual(classify_e126_record("08029090", "Peanut Kernels")[0], None)

    def test_nuts_takes_priority_over_pko_and_olive_oil(self):
        item, _ = classify_e126_record("08021100", "Palm Kernel Olive Oil Nut Blend")
        self.assertEqual(item, NUT_NUTS)


class TestPkoAndOliveOil(unittest.TestCase):
    """Priority 2 — Palm Kernel Oil (1513) / Olive Oil (1509 HSN or
    1500/1509/1510 in description) / the 40-60 split precondition."""

    def test_pko_alone_by_hsn(self):
        self.assertEqual(classify_e126_record("15132900", "Palm Kernel Oil")[0], PKO)

    def test_pko_alone_by_desc_code(self):
        self.assertEqual(classify_e126_record(None, "oil grade 1513")[0], PKO)

    def test_olive_oil_alone_by_hsn_prefix(self):
        self.assertEqual(classify_e126_record("15091000", "Extra Virgin")[0], OLIVE_OIL)

    def test_olive_oil_alone_by_desc_1509(self):
        self.assertEqual(classify_e126_record(None, "olive oil 1509 grade")[0], OLIVE_OIL)

    def test_olive_oil_alone_by_desc_1500(self):
        self.assertEqual(classify_e126_record(None, "vegetable fat 1500")[0], OLIVE_OIL)

    def test_olive_oil_alone_by_desc_1510(self):
        self.assertEqual(classify_e126_record(None, "refined oil 1510")[0], OLIVE_OIL)

    def test_olive_oil_desc_match_is_plain_substring_not_word_boundary(self):
        # Mirrors item_matcher.py's OLIVE OIL entry, which uses `icontains`
        # (plain substring) — '15091' still contains '1509'.
        self.assertEqual(classify_e126_record(None, "batch 15091 grade")[0], OLIVE_OIL)

    def test_split_when_both_signals_present(self):
        item, reason = classify_e126_record(
            "15132900", "Relevant Oil viz Palm Kernel (1513) or Olive 1509 blend",
        )
        self.assertEqual(item, "__PKO_OLIVE_SPLIT__")
        self.assertIn("split", reason.lower())

    def test_neither_signal_no_match(self):
        self.assertEqual(classify_e126_record("9999", "unrelated widget")[0], None)


class TestHsnMatching(unittest.TestCase):
    def test_prefix_and_formatting(self):
        for hs in ("1509", "15090000", "1509.00.00", "1509 00 00"):
            self.assertEqual(classify_e126_record(hs, "")[0], OLIVE_OIL)

    def test_non_matching_hsn(self):
        self.assertEqual(classify_e126_record("8888", ""), (None, None))


class TestNullAndBlankSafe(unittest.TestCase):
    def test_both_null(self):
        self.assertEqual(classify_e126_record(None, None), (None, None))

    def test_blank_strings(self):
        self.assertEqual(classify_e126_record("", "   "), (None, None))

    def test_unicode_description_and_invalid_quantity_are_safe(self):
        records = [
            {"record_id": 1, "hs_code": "1509", "description": "  Olive \U0001f6e2  ", "quantity": "bad"},
        ]
        result = plan_e126(records, balance_cif=Decimal("100"))
        self.assertEqual(result["classified"][0].planning_item, OLIVE_OIL)
        self.assertEqual(result["classified"][0].quantity, Decimal("0"))
        self.assertEqual(result["total_planned"], Decimal("0"))


class TestCaseInsensitiveAndTrim(unittest.TestCase):
    def test_mixed_case(self):
        for desc in ("NUTS", "Nuts", "nUtS"):
            self.assertEqual(classify_e126_record("0802", desc)[0], NUT_NUTS)

    def test_whitespace_normalized(self):
        self.assertEqual(classify_e126_record(None, "  palm   kernel  1513  ")[0], PKO)


class TestNoDoubleCounting(unittest.TestCase):
    def test_each_record_exactly_one_item(self):
        records = [
            {"record_id": 1, "hs_code": "15132900", "description": "pko"},          # PKO
            {"record_id": 2, "hs_code": "1509", "description": "olive oil"},        # Olive Oil
            {"record_id": 3, "hs_code": "08021100", "description": "cashew nuts"},  # Nuts
        ]
        for r in records:
            r["quantity"] = Decimal("1")
        result = plan_e126(records)
        counts = {i["planning_item_name"]: i["num_source_records"] for i in result["items"]}
        self.assertEqual(sum(counts.values()), 3)
        self.assertEqual(counts, {PKO: 1, OLIVE_OIL: 1, NUT_NUTS: 1})


class TestAggregation(unittest.TestCase):
    def _recs(self):
        return [
            {"record_id": "A", "hs_code": "08021100", "description": "cashew nuts", "quantity": Decimal("10")},
            {"record_id": "B", "hs_code": "08029090", "description": "almond nuts", "quantity": Decimal("5.5")},
            {"record_id": "C", "hs_code": "1509", "description": "olive oil", "quantity": Decimal("100")},
            {"record_id": "D", "hs_code": "8888", "description": "unclassifiable widget", "quantity": Decimal("7")},
        ]

    def test_quantity_summed_per_item(self):
        result = plan_e126(self._recs())
        by = {i["planning_item_name"]: i for i in result["items"]}
        self.assertEqual(by[NUT_NUTS]["total_quantity"], Decimal("15.5"))
        self.assertEqual(by[NUT_NUTS]["num_source_records"], 2)
        self.assertEqual(by[OLIVE_OIL]["total_quantity"], Decimal("100"))

    def test_planning_value_uses_fixed_price(self):
        result = plan_e126(self._recs())
        by = {i["planning_item_name"]: i for i in result["items"]}
        self.assertEqual(by[NUT_NUTS]["planning_value"], Decimal("15.5") * Decimal("3.00"))
        self.assertEqual(by[OLIVE_OIL]["planning_value"], Decimal("100") * Decimal("5.00"))

    def test_exceptions_reported(self):
        result = plan_e126(self._recs())
        self.assertEqual([e.record_id for e in result["exceptions"]], ["D"])

    def test_reason_recorded_for_audit(self):
        result = plan_e126(self._recs())
        reasons = {c.record_id: c.reason for c in result["classified"]}
        self.assertIsNotNone(reasons["A"])
        self.assertIsNone(reasons["D"])


class TestPerItemPlanning(unittest.TestCase):
    def test_per_item_price_and_value(self):
        recs = [
            {"record_id": 1, "hs_code": "08021100", "description": "cashew nuts", "quantity": Decimal("10")},
            {"record_id": 2, "hs_code": "1509", "description": "olive oil", "quantity": Decimal("4")},
            {"record_id": 3, "hs_code": "8888", "description": "widget", "quantity": Decimal("9")},
        ]
        per = plan_e126_per_item(recs)
        self.assertEqual(set(per), {1, 2})
        self.assertEqual(per[1]["planning_item"], NUT_NUTS)
        self.assertEqual(per[1]["unit_price"], Decimal("3.00"))
        self.assertEqual(per[1]["planned_cif"], Decimal("30.00"))
        self.assertEqual(per[2]["planning_item"], OLIVE_OIL)
        self.assertEqual(per[2]["planned_cif"], Decimal("4") * Decimal("5.00"))


class TestBalanceCap(unittest.TestCase):
    """Max debit per licence = Balance CIF (waterfall cap, like E1/E5/E132)."""

    def _recs(self):
        return [
            {"record_id": 1, "hs_code": "08021100", "description": "cashew nuts", "quantity": Decimal("10")},  # Nuts 10×3=30
            {"record_id": 2, "hs_code": "1509", "description": "olive oil", "quantity": Decimal("10")},         # Olive 10×5=50
        ]

    def test_total_planned_never_exceeds_balance(self):
        res = plan_e126(self._recs(), balance_cif=Decimal("50"))
        by = {i["planning_item_name"]: i for i in res["items"]}
        # Nuts (higher priority) takes its full 30; Olive Oil gets only the remaining 20.
        self.assertEqual(by[NUT_NUTS]["planning_value"], Decimal("30"))
        self.assertEqual(by[NUT_NUTS]["unit_price"], Decimal("3.00"))
        self.assertEqual(by[OLIVE_OIL]["planning_value"], Decimal("20"))
        self.assertEqual(by[OLIVE_OIL]["unit_price"], Decimal("2"))  # 20/10, rate dropped
        self.assertEqual(by[OLIVE_OIL]["max_unit_price"], Decimal("5.00"))
        self.assertEqual(res["total_planned"], Decimal("50"))
        self.assertEqual(res["wastage"], Decimal("0"))

    def test_wastage_when_balance_exceeds_demand(self):
        recs = [{"record_id": 1, "hs_code": "08021100", "description": "nuts", "quantity": Decimal("2")}]  # 2×3=6
        res = plan_e126(recs, balance_cif=Decimal("100"))
        self.assertEqual(res["total_planned"], Decimal("6"))
        self.assertEqual(res["wastage"], Decimal("94"))

    def test_per_item_uses_capped_effective_rate(self):
        per = plan_e126_per_item(self._recs(), balance_cif=Decimal("50"))
        self.assertEqual(per[1]["planned_cif"], Decimal("30"))
        self.assertEqual(per[2]["unit_price"], Decimal("2"))
        self.assertEqual(per[2]["planned_cif"], Decimal("20"))
        self.assertLessEqual(sum(p["planned_cif"] for p in per.values()), Decimal("50"))


class TestPkoOliveSplit(unittest.TestCase):
    """The 40/60 PKO/Olive-Oil split. CRITICAL business rule: the split
    target is always 40%/60% of the record's CURRENT Available Quantity
    (`quantity`), NEVER an original/total import quantity."""

    def _split_record(self, available_qty):
        return [{
            "record_id": 1,
            "hs_code": "15132900",
            "description": "Relevant Oil viz Palm Kernel (1513) or Olive 1509 blend",
            "quantity": available_qty,
        }]

    def test_split_is_40_60_of_available_quantity(self):
        # balance_cif == exactly the default split's value (Case A): 40×1.80 + 60×5.00 = 372.
        recs = self._split_record(Decimal("100"))
        lines = plan_e126_per_item_split(recs, balance_cif=Decimal("372"))[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by[OLIVE_OIL]["planned_quantity"], Decimal("60"))

    def test_split_follows_available_quantity_down_after_real_consumption(self):
        recs = self._split_record(Decimal("60"))
        lines = plan_e126_per_item_split(recs, balance_cif=Decimal("223.2"))[1]  # 24×1.80 + 36×5.00
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("24"))
        self.assertEqual(by[OLIVE_OIL]["planned_quantity"], Decimal("36"))

    def test_total_never_exceeds_available_quantity(self):
        for available in (Decimal("1"), Decimal("60"), Decimal("100"), Decimal("12345.678")):
            recs = self._split_record(available)
            lines = plan_e126_per_item_split(recs, balance_cif=None)[1]
            total = sum((L["planned_quantity"] for L in lines), Decimal("0"))
            self.assertEqual(total, available)

    def test_zero_available_quantity_yields_no_lines(self):
        recs = self._split_record(Decimal("0"))
        lines = plan_e126_per_item_split(recs, balance_cif=Decimal("10000"))[1]
        self.assertEqual(lines, [])

    def test_no_extra_history_parameter_accepted(self):
        with self.assertRaises(TypeError):
            plan_e126_per_item_split(
                self._split_record(Decimal("100")), balance_cif=Decimal("372"),
                existing_split_allocations={1: {PKO: Decimal("30")}},
            )

    def test_pko_alone_never_splits(self):
        recs = [{
            "record_id": 1, "hs_code": "15132900",
            "description": "Pure Palm Kernel Oil (1513)",
            "quantity": Decimal("50"),
        }]
        lines = plan_e126_per_item_split(recs, balance_cif=Decimal("10000"))[1]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["planning_item"], PKO)
        self.assertEqual(lines[0]["planned_quantity"], Decimal("50"))

    def test_per_item_single_line_blended_rate(self):
        recs = self._split_record(Decimal("100"))
        per = plan_e126_per_item(recs, balance_cif=Decimal("372"))[1]
        self.assertEqual(per["planned_quantity"], Decimal("100"))
        # blended = (40×1.80 + 60×5.00) / 100 = (72 + 300) / 100 = 3.72
        self.assertAlmostEqual(float(per["unit_price"]), 3.72, places=2)

    def test_split_contributes_to_shared_pko_olive_buckets(self):
        recs = [
            {"record_id": 1, "hs_code": "15132900", "description": "Palm Kernel Oil", "quantity": Decimal("10")},
            {
                "record_id": 2, "hs_code": "15132900",
                "description": "Relevant Oil viz Palm Kernel (1513) or Olive 1509 blend",
                "quantity": Decimal("100"),
            },
        ]
        result = plan_e126(recs, balance_cif=None)
        by = {i["planning_item_name"]: i for i in result["items"]}
        # record 1 contributes 10, record 2 contributes 40 (its 40% share) → 50 total
        self.assertEqual(by[PKO]["total_quantity"], Decimal("50"))
        self.assertEqual(by[OLIVE_OIL]["total_quantity"], Decimal("60"))


class TestPkoOliveWastageRebalance(unittest.TestCase):
    """The 40/60 split is the DEFAULT allocation; if the full waterfall
    still leaves Remaining Balance CIF > 0, quantity shifts from PKO to
    Olive Oil (higher-priced) to close that gap — see
    `_rebalance_pko_olive_wastage`."""

    def _split_record(self, available_qty, record_id=1):
        return {
            "record_id": record_id,
            "hs_code": "15132900",
            "description": "Relevant Oil viz Palm Kernel (1513) or Olive 1509 blend",
            "quantity": available_qty,
        }

    def test_case_a_balance_matches_default_split_exactly_no_change(self):
        recs = [self._split_record(Decimal("100"))]
        lines = plan_e126_per_item_split(recs, balance_cif=Decimal("372"))[1]  # 40×1.80 + 60×5.00
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by[OLIVE_OIL]["planned_quantity"], Decimal("60"))

    def test_case_b_partial_rebalance_absorbs_exact_surplus(self):
        # Default value 372 + a 50 surplus = 422. Shift = 50 / 3.20 kg.
        recs = [self._split_record(Decimal("100"))]
        lines = plan_e126_per_item_split(recs, balance_cif=Decimal("422"))[1]
        by = {L["planning_item"]: L for L in lines}
        total_qty = by[PKO]["planned_quantity"] + by[OLIVE_OIL]["planned_quantity"]
        total_cif = by[PKO]["planned_cif"] + by[OLIVE_OIL]["planned_cif"]
        self.assertAlmostEqual(float(total_qty), 100.0, places=6)   # quantity conserved
        self.assertAlmostEqual(float(total_cif), 422.0, places=6)   # surplus fully absorbed
        self.assertLess(by[PKO]["planned_quantity"], Decimal("40"))       # PKO shrank
        self.assertGreater(by[OLIVE_OIL]["planned_quantity"], Decimal("60"))  # Olive Oil grew
        # Prices themselves never change — only the qty mix does.
        self.assertEqual(by[PKO]["unit_price"], Decimal("1.80"))
        self.assertEqual(by[OLIVE_OIL]["unit_price"], Decimal("5.00"))

    def test_case_b_all_pko_converted_when_surplus_exceeds_max_possible_gain(self):
        # Max possible gain from converting all 40kg PKO = 40 × 3.20 = 128.
        recs = [self._split_record(Decimal("100"))]
        lines = plan_e126_per_item_split(recs, balance_cif=Decimal("100000"))[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertNotIn(PKO, by)  # fully drained — no line emitted for it
        self.assertEqual(by[OLIVE_OIL]["planned_quantity"], Decimal("100"))
        self.assertEqual(by[OLIVE_OIL]["planned_cif"], Decimal("500"))  # 100 × 5.00 ceiling

    def test_never_allocates_negative_or_exceeds_available_quantity(self):
        recs = [self._split_record(Decimal("100"))]
        for balance in (Decimal("372"), Decimal("422"), Decimal("100000")):
            lines = plan_e126_per_item_split(recs, balance_cif=balance)[1]
            by = {L["planning_item"]: L for L in lines}
            for L in by.values():
                self.assertGreaterEqual(L["planned_quantity"], Decimal("0"))
            total_qty = sum((L["planned_quantity"] for L in by.values()), Decimal("0"))
            self.assertLessEqual(total_qty, Decimal("100.0001"))

    def test_multiple_split_records_rebalanced_in_order(self):
        # Two 100kg split records (default 40/60 each = 372 value each,
        # 744 total). A 100 surplus should drain record 1's PKO first
        # (max gain 128 > 100 needed) before ever touching record 2.
        recs = [
            self._split_record(Decimal("100"), record_id=1),
            self._split_record(Decimal("100"), record_id=2),
        ]
        result = plan_e126_per_item_split(recs, balance_cif=Decimal("844"))  # 744 + 100
        by1 = {L["planning_item"]: L for L in result[1]}
        by2 = {L["planning_item"]: L for L in result[2]}
        # Record 1 absorbed the whole surplus; record 2 stayed at the default.
        self.assertLess(by1[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by2[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by2[OLIVE_OIL]["planned_quantity"], Decimal("60"))

    def test_does_not_touch_other_buckets(self):
        recs = [
            {"record_id": 1, "hs_code": "08021100", "description": "cashew nuts", "quantity": Decimal("10")},
            self._split_record(Decimal("100"), record_id=2),
        ]
        # Huge balance so Nuts is fully, uncapped allocated AND there's
        # still leftover to trigger PKO/Olive-Oil rebalance.
        result = plan_e126(recs, balance_cif=Decimal("1000000"))
        by = {i["planning_item_name"]: i for i in result["items"]}
        self.assertEqual(by[NUT_NUTS]["planning_value"], Decimal("10") * Decimal("3.00"))
        # ...while the split record's PKO/Olive-Oil mix WAS rebalanced.
        self.assertEqual(by[PKO]["total_quantity"], Decimal("0"))
        self.assertEqual(by[OLIVE_OIL]["total_quantity"], Decimal("100"))

    def test_no_op_when_balance_cif_is_none(self):
        recs = [self._split_record(Decimal("100"))]
        lines = plan_e126_per_item_split(recs, balance_cif=None)[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by[OLIVE_OIL]["planned_quantity"], Decimal("60"))

    def test_deterministic_and_idempotent(self):
        recs = [self._split_record(Decimal("100"))]
        run1 = plan_e126_per_item_split(recs, balance_cif=Decimal("422"))[1]
        run2 = plan_e126_per_item_split(recs, balance_cif=Decimal("422"))[1]
        self.assertEqual(
            [(L["planning_item"], L["planned_quantity"]) for L in run1],
            [(L["planning_item"], L["planned_quantity"]) for L in run2],
        )


if __name__ == "__main__":
    unittest.main()
