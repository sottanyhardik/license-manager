"""
Unit + edge-case tests for the E132 planning classification engine
(apps.license.services.e132_plan). Pure functions — no DB required.
"""
import unittest
from decimal import Decimal

from apps.license.services.e132_plan import (
    ALUMINIUM, CHEESE, PKO, RBD, YEAST, NUT_NUTS, UNIT_PRICE, PLANNING_ORDER,
    classify_e132_record, plan_e132, plan_e132_per_item, plan_e132_per_item_split,
)


class TestPriorityOrder(unittest.TestCase):
    def test_planning_order(self):
        # Nuts → Yeast → PKO → RBD → Cheese → Aluminium Foil (last). Immutable
        # per the E132 Auto Planning business rules.
        self.assertEqual(PLANNING_ORDER, (NUT_NUTS, YEAST, PKO, RBD, CHEESE, ALUMINIUM))


class TestFixedPrices(unittest.TestCase):
    def test_price_table(self):
        self.assertEqual(UNIT_PRICE[NUT_NUTS], Decimal("3.00"))
        self.assertEqual(UNIT_PRICE[YEAST], Decimal("5.00"))
        self.assertEqual(UNIT_PRICE[PKO], Decimal("1.80"))
        self.assertEqual(UNIT_PRICE[RBD], Decimal("1.20"))
        self.assertEqual(UNIT_PRICE[CHEESE], Decimal("5.50"))
        self.assertEqual(UNIT_PRICE[ALUMINIUM], Decimal("4.50"))


class TestNuts(unittest.TestCase):
    """Rule 1 — 0802 (HSN or desc) AND the WORD 'nut'/'nuts' in the description."""

    def test_by_hsn_prefix_and_word(self):
        self.assertEqual(classify_e132_record("08021100", "Cashew Nuts")[0], NUT_NUTS)

    def test_by_desc_code_and_word(self):
        self.assertEqual(classify_e132_record("9999", "cashew 0802 grade nut")[0], NUT_NUTS)

    def test_singular_word_matches(self):
        self.assertEqual(classify_e132_record("08021100", "Almond Nut")[0], NUT_NUTS)

    def test_0802_without_nut_word_does_not_match(self):
        # 0802 present but no 'nut'/'nuts' word at all.
        self.assertEqual(classify_e132_record("08021100", "Almond Kernel")[0], None)

    def test_word_boundary_excludes_peanut(self):
        # 'Peanut' does not contain the standalone word 'nut' or 'nuts'.
        self.assertEqual(classify_e132_record("08029090", "Peanut Kernels")[0], None)

    def test_nuts_takes_priority_over_everything_else(self):
        # Even with a strong Cheese/Yeast-looking description, 0802+nut wins
        # because Nuts is Priority 1.
        item, _ = classify_e132_record("08021100", "Cheese Vegetable Oil Nut Blend")
        self.assertEqual(item, NUT_NUTS)


class TestYeast(unittest.TestCase):
    """Rule 2 — 2106 (HSN or desc) AND 'yeast' in the description."""

    def test_by_hsn(self):
        self.assertEqual(classify_e132_record("2106", "instant yeast")[0], YEAST)

    def test_by_desc_code(self):
        self.assertEqual(classify_e132_record(None, "bakers yeast code 2106")[0], YEAST)

    def test_2106_without_yeast_word_does_not_match_yeast(self):
        item, _ = classify_e132_record("2106", "flavour base")
        self.assertNotEqual(item, YEAST)

    def test_yeast_beats_priority_3_group(self):
        # Yeast (priority 2) wins even if the description also looks like an
        # explicit-Cheese match.
        item, _ = classify_e132_record("2106", "Yeast Cheese Vegetable Oil")
        self.assertEqual(item, YEAST)


class TestExplicitCheese(unittest.TestCase):
    """Rule 6 — CHEESE + VEGETABLE + OIL in description: highest precedence
    within Priority 3, no split, no debit adjustment."""

    def test_matches_regardless_of_hsn(self):
        item, reason = classify_e132_record(None, "Cheese Vegetable Oil Blend")
        self.assertEqual(item, CHEESE)
        self.assertIn("explicit", reason.lower())

    def test_beats_rbd_and_split(self):
        # Even with 1510 AND 1513 both present, explicit Cheese wins outright.
        item, _ = classify_e132_record(
            None, "Cheese Vegetable Oil viz Palm Kernel (1513) or RBD (1510)",
        )
        self.assertEqual(item, CHEESE)

    def test_missing_one_keyword_falls_through(self):
        # 'Cheese' + 'Oil' but no 'Vegetable' → not the explicit rule.
        item, _ = classify_e132_record(None, "Cheese Oil Blend")
        self.assertNotEqual(item, CHEESE)


class TestRbd(unittest.TestCase):
    """Rule 4 — HSN (or desc) 1510 only."""

    def test_by_hsn(self):
        self.assertEqual(classify_e132_record("15100000", "any")[0], RBD)

    def test_by_desc_code(self):
        self.assertEqual(classify_e132_record(None, "oil code 1510")[0], RBD)

    def test_free_text_alone_does_not_match(self):
        # Business rule dropped the old free-text 'rbd'/'palmolein' fallback —
        # only the 1510 code (HSN or description) triggers RBD now.
        self.assertNotEqual(classify_e132_record(None, "RBD Palmolein Oil")[0], RBD)


class TestPkoAndCheeseStrict(unittest.TestCase):
    """Rules 3/5/7 — PKO-alone / Cheese-alone / the 40-60 split precondition."""

    def test_pko_alone_by_hsn(self):
        self.assertEqual(classify_e132_record("15132900", "Palm Kernel Oil")[0], PKO)

    def test_pko_alone_by_desc_code(self):
        self.assertEqual(classify_e132_record(None, "oil grade 1513")[0], PKO)

    def test_cheese_strict_requires_all_three(self):
        # Dairy code alone (no vegetable/oil) does not match.
        self.assertEqual(classify_e132_record("04061000", "Fresh Cheese Only")[0], None)

    def test_cheese_strict_matches_with_dairy_code_and_veg_oil(self):
        item, reason = classify_e132_record("04061000", "Relevant Vegetable Oil Fat Blend")
        self.assertEqual(item, CHEESE)
        self.assertIn("strict", reason.lower())

    def test_cheese_strict_via_description_code(self):
        item, _ = classify_e132_record(None, "0405 Vegetable Oil Fat Blend")
        self.assertEqual(item, CHEESE)

    def test_split_when_both_signals_present(self):
        item, reason = classify_e132_record(
            "15132900", "Relevant Vegetable Oil viz Palm Kernel (1513) or Dairy Fat 0406",
        )
        self.assertEqual(item, "__VEG_OIL_SPLIT__")
        self.assertIn("split", reason.lower())

    def test_2106_alone_no_longer_implies_cheese(self):
        # Old engine treated bare HSN 2106 as a Cheese trigger; the new
        # strict rule only recognises 0401/0405/0406 for Cheese.
        self.assertNotEqual(classify_e132_record("2106", "flavour base")[0], CHEESE)


class TestAluminium(unittest.TestCase):
    def test_by_hsn(self):
        self.assertEqual(classify_e132_record("7607", "")[0], ALUMINIUM)

    def test_by_desc_code(self):
        self.assertEqual(classify_e132_record(None, "foil HSN 7607 rolls")[0], ALUMINIUM)

    def test_by_description_phrase(self):
        self.assertEqual(
            classify_e132_record("39021000", "Packing Material: PP / Aluminium Foil")[0],
            ALUMINIUM,
        )

    def test_foil_alone_does_not_match(self):
        self.assertNotEqual(classify_e132_record("9999", "plastic foil wrap")[0], ALUMINIUM)

    def test_evaluated_last(self):
        # A record that is ALSO a Nuts match takes Nuts, never Aluminium,
        # even if 7607 also appears somewhere.
        item, _ = classify_e132_record("08021100", "Cashew Nuts 7607 mixed pack")
        self.assertEqual(item, NUT_NUTS)


class TestHsnMatching(unittest.TestCase):
    def test_prefix_and_formatting(self):
        for hs in ("1510", "15100000", "1510.00.00", "1510 00 00"):
            self.assertEqual(classify_e132_record(hs, "")[0], RBD)

    def test_non_matching_hsn(self):
        self.assertEqual(classify_e132_record("8888", ""), (None, None))


class TestNullAndBlankSafe(unittest.TestCase):
    def test_both_null(self):
        self.assertEqual(classify_e132_record(None, None), (None, None))

    def test_blank_strings(self):
        self.assertEqual(classify_e132_record("", "   "), (None, None))

    def test_unicode_description_and_invalid_quantity_are_safe(self):
        records = [
            {"record_id": 1, "hs_code": "7607", "description": "  Foil \U0001f4e6  ", "quantity": "bad"},
        ]
        result = plan_e132(records, balance_cif=Decimal("100"))
        self.assertEqual(result["classified"][0].planning_item, ALUMINIUM)
        self.assertEqual(result["classified"][0].quantity, Decimal("0"))
        self.assertEqual(result["total_planned"], Decimal("0"))


class TestCaseInsensitiveAndTrim(unittest.TestCase):
    def test_mixed_case(self):
        for desc in ("YEAST", "Yeast", "yEaSt"):
            self.assertEqual(classify_e132_record("2106", desc)[0], YEAST)

    def test_whitespace_normalized(self):
        self.assertEqual(classify_e132_record(None, "  palm   kernel  1513  ")[0], PKO)


class TestNoDoubleCounting(unittest.TestCase):
    def test_each_record_exactly_one_item(self):
        records = [
            {"record_id": 1, "hs_code": "2106", "description": "yeast extract"},   # Yeast
            {"record_id": 2, "hs_code": "1510", "description": "rbd oil"},          # RBD
            {"record_id": 3, "hs_code": "15132900", "description": "pko"},          # PKO
            {"record_id": 4, "hs_code": "08021100", "description": "cashew nuts"},  # Nuts
        ]
        for r in records:
            r["quantity"] = Decimal("1")
        result = plan_e132(records)
        counts = {i["planning_item_name"]: i["num_source_records"] for i in result["items"]}
        self.assertEqual(sum(counts.values()), 4)
        self.assertEqual(counts, {YEAST: 1, RBD: 1, PKO: 1, NUT_NUTS: 1})


class TestAggregation(unittest.TestCase):
    def _recs(self):
        return [
            {"record_id": "A", "hs_code": "08021100", "description": "cashew nuts", "quantity": Decimal("10")},
            {"record_id": "B", "hs_code": "08029090", "description": "almond nuts", "quantity": Decimal("5.5")},
            {"record_id": "C", "hs_code": "7607", "description": "foil", "quantity": Decimal("100")},
            {"record_id": "D", "hs_code": "2106", "description": "yeast powder", "quantity": Decimal("3")},
            {"record_id": "E", "hs_code": "8888", "description": "unclassifiable widget", "quantity": Decimal("7")},
        ]

    def test_quantity_summed_per_item(self):
        result = plan_e132(self._recs())
        by = {i["planning_item_name"]: i for i in result["items"]}
        self.assertEqual(by[NUT_NUTS]["total_quantity"], Decimal("15.5"))
        self.assertEqual(by[NUT_NUTS]["num_source_records"], 2)
        self.assertEqual(by[ALUMINIUM]["total_quantity"], Decimal("100"))

    def test_planning_value_uses_fixed_price(self):
        result = plan_e132(self._recs())
        by = {i["planning_item_name"]: i for i in result["items"]}
        self.assertEqual(by[NUT_NUTS]["planning_value"], Decimal("15.5") * Decimal("3.00"))
        self.assertEqual(by[ALUMINIUM]["planning_value"], Decimal("100") * Decimal("4.50"))

    def test_exceptions_reported(self):
        result = plan_e132(self._recs())
        self.assertEqual([e.record_id for e in result["exceptions"]], ["E"])

    def test_reason_recorded_for_audit(self):
        result = plan_e132(self._recs())
        reasons = {c.record_id: c.reason for c in result["classified"]}
        self.assertIsNotNone(reasons["A"])
        self.assertIsNone(reasons["E"])


class TestPerItemPlanning(unittest.TestCase):
    def test_per_item_price_and_value(self):
        recs = [
            {"record_id": 1, "hs_code": "08021100", "description": "cashew nuts", "quantity": Decimal("10")},
            {"record_id": 2, "hs_code": "2106", "description": "yeast", "quantity": Decimal("4")},
            {"record_id": 3, "hs_code": "8888", "description": "widget", "quantity": Decimal("9")},
        ]
        per = plan_e132_per_item(recs)
        self.assertEqual(set(per), {1, 2})
        self.assertEqual(per[1]["planning_item"], NUT_NUTS)
        self.assertEqual(per[1]["unit_price"], Decimal("3.00"))
        self.assertEqual(per[1]["planned_cif"], Decimal("30.00"))
        self.assertEqual(per[2]["planning_item"], YEAST)
        self.assertEqual(per[2]["planned_cif"], Decimal("4") * Decimal("5.00"))


class TestBalanceCap(unittest.TestCase):
    """Max debit per licence = Balance CIF (waterfall cap, like E1/E5)."""

    def _recs(self):
        return [
            {"record_id": 1, "hs_code": "08021100", "description": "cashew nuts", "quantity": Decimal("10")},  # Nuts 10×3=30
            {"record_id": 2, "hs_code": "1510", "description": "rbd", "quantity": Decimal("10")},               # RBD 10×1.2=12
        ]

    def test_total_planned_never_exceeds_balance(self):
        res = plan_e132(self._recs(), balance_cif=Decimal("35"))
        by = {i["planning_item_name"]: i for i in res["items"]}
        # Nuts (higher priority) takes its full 30; RBD gets only the remaining 5.
        self.assertEqual(by[NUT_NUTS]["planning_value"], Decimal("30"))
        self.assertEqual(by[NUT_NUTS]["unit_price"], Decimal("3.00"))
        self.assertEqual(by[RBD]["planning_value"], Decimal("5"))
        self.assertEqual(by[RBD]["unit_price"], Decimal("0.5"))  # 5/10, rate dropped
        self.assertEqual(by[RBD]["max_unit_price"], Decimal("1.20"))
        self.assertEqual(res["total_planned"], Decimal("35"))
        self.assertEqual(res["wastage"], Decimal("0"))

    def test_wastage_when_balance_exceeds_demand(self):
        recs = [{"record_id": 1, "hs_code": "08021100", "description": "nuts", "quantity": Decimal("2")}]  # 2×3=6
        res = plan_e132(recs, balance_cif=Decimal("100"))
        self.assertEqual(res["total_planned"], Decimal("6"))
        self.assertEqual(res["wastage"], Decimal("94"))

    def test_per_item_uses_capped_effective_rate(self):
        per = plan_e132_per_item(self._recs(), balance_cif=Decimal("35"))
        self.assertEqual(per[1]["planned_cif"], Decimal("30"))
        self.assertEqual(per[2]["unit_price"], Decimal("0.5"))
        self.assertEqual(per[2]["planned_cif"], Decimal("5"))
        self.assertLessEqual(sum(p["planned_cif"] for p in per.values()), Decimal("35"))


class TestVegOilSplit(unittest.TestCase):
    """Rules 7/8 — the 40/60 PKO/Cheese split and the existing-allocation
    (debit) adjustment, per record, based on the record's ORIGINAL quantity."""

    def _split_record(self, available_qty, original_qty):
        return [{
            "record_id": 1,
            "hs_code": "15132900",
            "description": "Relevant Vegetable Oil viz Palm Kernel (1513) or Dairy Fat 0406 Vegetable Oil",
            "quantity": available_qty,
            "original_quantity": original_qty,
        }]

    def test_fresh_split_is_40_60_of_original_quantity(self):
        recs = self._split_record(Decimal("100"), Decimal("100"))
        lines = plan_e132_per_item_split(recs, balance_cif=Decimal("10000"))[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by[CHEESE]["planned_quantity"], Decimal("60"))

    def test_debit_adjustment_example_from_spec(self):
        # 100kg total, PKO already planned 30kg → allocate PKO=10, Cheese=60
        # (NOT a naive 28/42 re-split of the 70kg remaining).
        recs = self._split_record(Decimal("70"), Decimal("100"))
        lines = plan_e132_per_item_split(
            recs, balance_cif=Decimal("10000"),
            existing_split_allocations={1: {PKO: Decimal("30")}},
        )[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("10"))
        self.assertEqual(by[CHEESE]["planned_quantity"], Decimal("60"))

    def test_target_already_met_allocates_zero(self):
        recs = self._split_record(Decimal("70"), Decimal("100"))
        lines = plan_e132_per_item_split(
            recs, balance_cif=Decimal("10000"),
            existing_split_allocations={1: {PKO: Decimal("40"), CHEESE: Decimal("60")}},
        )[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("0"))
        self.assertEqual(by[CHEESE]["planned_quantity"], Decimal("0"))

    def test_shortfall_never_negative_when_over_planned(self):
        # Already planned exceeds target (data drift) — shortfall floors at 0,
        # never goes negative.
        recs = self._split_record(Decimal("10"), Decimal("100"))
        lines = plan_e132_per_item_split(
            recs, balance_cif=Decimal("10000"),
            existing_split_allocations={1: {PKO: Decimal("999")}},
        )[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("0"))

    def test_shortfall_capped_at_available_quantity(self):
        # Fresh split but only 70kg is actually available (30kg already
        # consumed by something outside this record's plan history) — the
        # combined new shortfall (100) is scaled down to fit within 70.
        recs = self._split_record(Decimal("70"), Decimal("100"))
        lines = plan_e132_per_item_split(recs, balance_cif=Decimal("10000"))[1]
        by = {L["planning_item"]: L for L in lines}
        total = by[PKO]["planned_quantity"] + by[CHEESE]["planned_quantity"]
        self.assertEqual(total, Decimal("70"))
        # Proportional: 40/100 × 70 = 28, 60/100 × 70 = 42.
        self.assertAlmostEqual(float(by[PKO]["planned_quantity"]), 28.0, places=2)
        self.assertAlmostEqual(float(by[CHEESE]["planned_quantity"]), 42.0, places=2)

    def test_explicit_cheese_never_splits_or_adjusts(self):
        recs = [{
            "record_id": 1, "hs_code": "15132900",
            "description": "Cheese Vegetable Oil Blend (1513)",
            "quantity": Decimal("50"), "original_quantity": Decimal("50"),
        }]
        lines = plan_e132_per_item_split(
            recs, balance_cif=Decimal("10000"),
            existing_split_allocations={1: {PKO: Decimal("999")}},  # must be ignored
        )[1]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["planning_item"], CHEESE)
        self.assertEqual(lines[0]["planned_quantity"], Decimal("50"))

    def test_no_prior_allocation_defaults_to_full_target(self):
        # `existing_split_allocations=None` (report-only context) behaves
        # exactly like an empty history.
        recs = self._split_record(Decimal("100"), Decimal("100"))
        lines_a = plan_e132_per_item_split(recs, balance_cif=Decimal("10000"))[1]
        lines_b = plan_e132_per_item_split(
            recs, balance_cif=Decimal("10000"), existing_split_allocations={},
        )[1]
        self.assertEqual(
            {L["planning_item"]: L["planned_quantity"] for L in lines_a},
            {L["planning_item"]: L["planned_quantity"] for L in lines_b},
        )

    def test_original_quantity_defaults_to_quantity_when_absent(self):
        # Report-only callers never pass `original_quantity` — it should
        # fall back to `quantity` so the split still works sensibly.
        recs = [{
            "record_id": 1, "hs_code": "15132900",
            "description": "Relevant Vegetable Oil viz Palm Kernel (1513) or Dairy Fat 0406 Vegetable Oil",
            "quantity": Decimal("100"),
        }]
        lines = plan_e132_per_item_split(recs, balance_cif=Decimal("10000"))[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by[CHEESE]["planned_quantity"], Decimal("60"))

    def test_per_item_single_line_blended_rate(self):
        recs = self._split_record(Decimal("100"), Decimal("100"))
        per = plan_e132_per_item(recs, balance_cif=Decimal("10000"))[1]
        self.assertEqual(per["planned_quantity"], Decimal("100"))
        # blended = (40×1.80 + 60×5.50) / 100 = (72 + 330) / 100 = 4.02
        self.assertAlmostEqual(float(per["unit_price"]), 4.02, places=2)

    def test_split_contributes_to_shared_pko_cheese_buckets(self):
        # A plain PKO-alone record and a split record both contribute to the
        # SAME PKO bucket for the CIF waterfall.
        recs = [
            {"record_id": 1, "hs_code": "15132900", "description": "Palm Kernel Oil", "quantity": Decimal("10")},
            {
                "record_id": 2, "hs_code": "15132900",
                "description": "Relevant Vegetable Oil viz Palm Kernel (1513) or Dairy Fat 0406 Vegetable Oil",
                "quantity": Decimal("100"), "original_quantity": Decimal("100"),
            },
        ]
        result = plan_e132(recs, balance_cif=None)
        by = {i["planning_item_name"]: i for i in result["items"]}
        # record 1 contributes 10, record 2 contributes 40 (its 40% share) → 50 total
        self.assertEqual(by[PKO]["total_quantity"], Decimal("50"))
        self.assertEqual(by[CHEESE]["total_quantity"], Decimal("60"))


if __name__ == "__main__":
    unittest.main()
