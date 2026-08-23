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
    """Rule 7 — the 40/60 PKO/Cheese split. CRITICAL business rule: the
    split target is always 40%/60% of the record's CURRENT Available
    Quantity (`quantity`), NEVER an original/total import quantity — the
    engine no longer even accepts one. Available Quantity already self-
    corrects for real consumption, so the split is simply recomputed fresh,
    every run, from whatever it currently is — no separate "already
    planned/debited" bookkeeping."""

    def _split_record(self, available_qty):
        return [{
            "record_id": 1,
            "hs_code": "15132900",
            "description": "Relevant Vegetable Oil viz Palm Kernel (1513) or Dairy Fat 0406 Vegetable Oil",
            "quantity": available_qty,
        }]

    def test_split_is_40_60_of_available_quantity(self):
        # balance_cif == exactly the default split's value (Case A — see
        # TestVegOilWastageRebalance for what happens when the balance
        # EXCEEDS this, i.e. leftover CIF to absorb).
        recs = self._split_record(Decimal("100"))
        lines = plan_e132_per_item_split(recs, balance_cif=Decimal("402"))[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by[CHEESE]["planned_quantity"], Decimal("60"))

    def test_split_follows_available_quantity_down_after_real_consumption(self):
        # The exact scenario the business rule calls out: 100kg originally
        # imported, 40kg already really allotted/debited elsewhere -> the
        # import item's available_quantity is now 60kg, and the split must
        # be 40%/60% of THAT 60kg (24/36) — never 40%/60% of the original 100.
        recs = self._split_record(Decimal("60"))
        lines = plan_e132_per_item_split(recs, balance_cif=Decimal("241.2"))[1]  # 24×1.80 + 36×5.50
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("24"))
        self.assertEqual(by[CHEESE]["planned_quantity"], Decimal("36"))

    def test_total_never_exceeds_available_quantity(self):
        for available in (Decimal("1"), Decimal("60"), Decimal("100"), Decimal("12345.678")):
            recs = self._split_record(available)
            lines = plan_e132_per_item_split(recs, balance_cif=None)[1]
            total = sum((L["planned_quantity"] for L in lines), Decimal("0"))
            self.assertEqual(total, available)

    def test_zero_available_quantity_yields_no_lines(self):
        recs = self._split_record(Decimal("0"))
        lines = plan_e132_per_item_split(recs, balance_cif=Decimal("10000"))[1]
        self.assertEqual(lines, [])

    def test_no_extra_history_parameter_accepted(self):
        # The engine no longer has any "already planned" concept to pass in —
        # confirms the old keyword argument is gone, not merely ignored.
        with self.assertRaises(TypeError):
            plan_e132_per_item_split(
                self._split_record(Decimal("100")), balance_cif=Decimal("402"),
                existing_split_allocations={1: {PKO: Decimal("30")}},
            )

    def test_explicit_cheese_never_splits(self):
        recs = [{
            "record_id": 1, "hs_code": "15132900",
            "description": "Cheese Vegetable Oil Blend (1513)",
            "quantity": Decimal("50"),
        }]
        lines = plan_e132_per_item_split(recs, balance_cif=Decimal("10000"))[1]
        # Explicit-cheese converts ALL of it (fully-priced ceiling value
        # 50×5.50=275, well under the 10000 balance, so no rebalancing
        # triggers here anyway — nothing to rebalance since there's no PKO).
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["planning_item"], CHEESE)
        self.assertEqual(lines[0]["planned_quantity"], Decimal("50"))

    def test_per_item_single_line_blended_rate(self):
        # balance_cif == exactly the default split's value (Case A) so the
        # blended rate reflects the untouched 40/60 mix.
        recs = self._split_record(Decimal("100"))
        per = plan_e132_per_item(recs, balance_cif=Decimal("402"))[1]
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
                "quantity": Decimal("100"),
            },
        ]
        result = plan_e132(recs, balance_cif=None)
        by = {i["planning_item_name"]: i for i in result["items"]}
        # record 1 contributes 10, record 2 contributes 40 (its 40% share) → 50 total
        self.assertEqual(by[PKO]["total_quantity"], Decimal("50"))
        self.assertEqual(by[CHEESE]["total_quantity"], Decimal("60"))


class TestVegOilWastageRebalance(unittest.TestCase):
    """The 40/60 split is the DEFAULT allocation; if the full waterfall
    still leaves Remaining Balance CIF > 0, quantity shifts from PKO to
    Cheese (higher-priced) to close that gap — see
    `_rebalance_veg_oil_wastage`."""

    def _split_record(self, available_qty, record_id=1):
        return {
            "record_id": record_id,
            "hs_code": "15132900",
            "description": "Relevant Vegetable Oil viz Palm Kernel (1513) or Dairy Fat 0406 Vegetable Oil",
            "quantity": available_qty,
        }

    def test_case_a_balance_matches_default_split_exactly_no_change(self):
        recs = [self._split_record(Decimal("100"))]
        lines = plan_e132_per_item_split(recs, balance_cif=Decimal("402"))[1]  # 40×1.80 + 60×5.50
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by[CHEESE]["planned_quantity"], Decimal("60"))

    def test_case_b_partial_rebalance_absorbs_exact_surplus(self):
        # Default value 402 + a 50 surplus = 452. Shift = 50 / 3.70 kg.
        recs = [self._split_record(Decimal("100"))]
        lines = plan_e132_per_item_split(recs, balance_cif=Decimal("452"))[1]
        by = {L["planning_item"]: L for L in lines}
        total_qty = by[PKO]["planned_quantity"] + by[CHEESE]["planned_quantity"]
        total_cif = by[PKO]["planned_cif"] + by[CHEESE]["planned_cif"]
        self.assertAlmostEqual(float(total_qty), 100.0, places=6)   # quantity conserved
        self.assertAlmostEqual(float(total_cif), 452.0, places=6)   # surplus fully absorbed
        self.assertLess(by[PKO]["planned_quantity"], Decimal("40"))    # PKO shrank
        self.assertGreater(by[CHEESE]["planned_quantity"], Decimal("60"))  # Cheese grew
        # Prices themselves never change — only the qty mix does.
        self.assertEqual(by[PKO]["unit_price"], Decimal("1.80"))
        self.assertEqual(by[CHEESE]["unit_price"], Decimal("5.50"))

    def test_case_b_all_pko_converted_when_surplus_exceeds_max_possible_gain(self):
        # Max possible gain from converting all 40kg PKO = 40 × 3.70 = 148.
        # A much larger surplus still can't manufacture more Cheese quantity
        # than the record physically has — stops once PKO hits 0, per spec.
        recs = [self._split_record(Decimal("100"))]
        lines = plan_e132_per_item_split(recs, balance_cif=Decimal("100000"))[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertNotIn(PKO, by)  # fully drained — no line emitted for it
        self.assertEqual(by[CHEESE]["planned_quantity"], Decimal("100"))
        self.assertEqual(by[CHEESE]["planned_cif"], Decimal("550"))  # 100 × 5.50 ceiling

    def test_never_allocates_negative_or_exceeds_available_quantity(self):
        recs = [self._split_record(Decimal("100"))]
        for balance in (Decimal("402"), Decimal("452"), Decimal("100000")):
            lines = plan_e132_per_item_split(recs, balance_cif=balance)[1]
            by = {L["planning_item"]: L for L in lines}
            for L in by.values():
                self.assertGreaterEqual(L["planned_quantity"], Decimal("0"))
            total_qty = sum((L["planned_quantity"] for L in by.values()), Decimal("0"))
            self.assertLessEqual(total_qty, Decimal("100.0001"))

    def test_multiple_split_records_rebalanced_in_order(self):
        # Two 100kg split records (default 40/60 each = 402 value each,
        # 804 total). A 100 surplus should drain record 1's PKO first
        # (max gain 148 > 100 needed) before ever touching record 2.
        recs = [
            self._split_record(Decimal("100"), record_id=1),
            self._split_record(Decimal("100"), record_id=2),
        ]
        result = plan_e132_per_item_split(recs, balance_cif=Decimal("904"))  # 804 + 100
        by1 = {L["planning_item"]: L for L in result[1]}
        by2 = {L["planning_item"]: L for L in result[2]}
        # Record 1 absorbed the whole surplus; record 2 stayed at the default.
        self.assertLess(by1[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by2[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by2[CHEESE]["planned_quantity"], Decimal("60"))

    def test_does_not_touch_other_buckets(self):
        recs = [
            {"record_id": 1, "hs_code": "08021100", "description": "cashew nuts", "quantity": Decimal("10")},
            {"record_id": 2, "hs_code": "2106", "description": "yeast", "quantity": Decimal("10")},
            {"record_id": 3, "hs_code": "1510", "description": "rbd", "quantity": Decimal("10")},
            {"record_id": 4, "hs_code": "7607", "description": "foil", "quantity": Decimal("10")},
            self._split_record(Decimal("100"), record_id=5),
        ]
        # Huge balance so Nuts/Yeast/RBD/Aluminium are all fully, uncapped
        # allocated AND there's still leftover to trigger PKO/Cheese rebalance.
        result = plan_e132(recs, balance_cif=Decimal("1000000"))
        by = {i["planning_item_name"]: i for i in result["items"]}
        self.assertEqual(by[NUT_NUTS]["planning_value"], Decimal("10") * Decimal("3.00"))
        self.assertEqual(by[YEAST]["planning_value"], Decimal("10") * Decimal("5.00"))
        self.assertEqual(by[RBD]["planning_value"], Decimal("10") * Decimal("1.20"))
        self.assertEqual(by[ALUMINIUM]["planning_value"], Decimal("10") * Decimal("4.50"))
        # ...while the split record's PKO/Cheese mix WAS rebalanced.
        self.assertEqual(by[PKO]["total_quantity"], Decimal("0"))
        self.assertEqual(by[CHEESE]["total_quantity"], Decimal("100"))

    def test_no_op_when_balance_cif_is_none(self):
        # Classification-only/report mode has no "remaining balance" concept.
        recs = [self._split_record(Decimal("100"))]
        lines = plan_e132_per_item_split(recs, balance_cif=None)[1]
        by = {L["planning_item"]: L for L in lines}
        self.assertEqual(by[PKO]["planned_quantity"], Decimal("40"))
        self.assertEqual(by[CHEESE]["planned_quantity"], Decimal("60"))

    def test_deterministic_and_idempotent(self):
        recs = [self._split_record(Decimal("100"))]
        run1 = plan_e132_per_item_split(recs, balance_cif=Decimal("452"))[1]
        run2 = plan_e132_per_item_split(recs, balance_cif=Decimal("452"))[1]
        self.assertEqual(
            [(L["planning_item"], L["planned_quantity"]) for L in run1],
            [(L["planning_item"], L["planned_quantity"]) for L in run2],
        )


if __name__ == "__main__":
    unittest.main()
