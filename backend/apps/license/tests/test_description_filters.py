"""Filter conditions for the licence import description mapping table — one server-side evaluator (no DB needed)."""
import pytest

from apps.license.services.product_intelligence.description_filters import FilterError, clean_filters, matches

ROW = {"description": ["Dietary Supplement - Almonds (Crude)"], "hsn": ["08021100"], "sion": ["E126"]}
OTHER = {"description": ["RBD PALMOLEIN OIL"], "hsn": ["15119020"], "sion": ["E5"]}
NO_CODES = {"description": ["MISC"], "hsn": [], "sion": []}


def f(*conditions, logic="all"):
    return clean_filters({"logic": logic, "conditions": [{"field": c[0], "op": c[1], "value": c[2] if len(c) > 2 else ""} for c in conditions]})


@pytest.mark.parametrize("op,value,row,expected", [
    ("contains", "dietary", ROW, True), ("contains", "DIETARY", OTHER, False),
    ("not_contains", "crude", ROW, False), ("not_contains", "crude", OTHER, True),
    ("starts_with", "dietary", ROW, True), ("starts_with", "supplement", ROW, False),
    ("not_starts_with", "dietary", ROW, False), ("not_starts_with", "dietary", OTHER, True),
    ("ends_with", "(crude)", ROW, True), ("ends_with", "oil", ROW, False),
    ("not_ends_with", "(crude)", ROW, False), ("not_ends_with", "(crude)", OTHER, True),
    ("equals", "  dietary supplement – almonds (crude) ", ROW, True),  # strict key: case / spacing / dash only
    ("equals", "dietary supplement almonds crude", ROW, False),         # no fuzzy equality
    ("not_equals", "RBD PALMOLEIN OIL", OTHER, False), ("not_equals", "RBD PALMOLEIN OIL", ROW, True),
])
def test_description_operators(op, value, row, expected):
    assert matches(row, f(("description", op, value))) is expected


@pytest.mark.parametrize("op,value,row,expected", [
    ("contains", "021", ROW, True), ("contains", "999", ROW, False),
    ("not_contains", "021", ROW, False), ("not_contains", "021", OTHER, True),
    ("starts_with", "0802", ROW, True), ("starts_with", "802", ROW, False),  # leading zero kept — never numeric
    ("not_starts_with", "0802", ROW, False), ("not_starts_with", "0802", OTHER, True),
    ("ends_with", "1100", ROW, True), ("ends_with", "00", OTHER, False),
    ("not_ends_with", "1100", ROW, False), ("not_ends_with", "1100", OTHER, True),
    ("equals", "08021100", ROW, True), ("equals", "8021100", ROW, False),
    ("not_equals", "08021100", ROW, False), ("not_equals", "08021100", OTHER, True),
])
def test_hsn_operators(op, value, row, expected):
    assert matches(row, f(("hsn", op, value))) is expected


@pytest.mark.parametrize("op,value,expected_row,expected_other", [
    ("equals", "e126", True, False), ("not_equals", "E126", False, True), ("starts_with", "E1", True, False),
    ("not_starts_with", "E1", False, True), ("contains", "12", True, False), ("not_contains", "12", False, True),
    ("ends_with", "26", True, False), ("not_ends_with", "26", False, True),
])
def test_sion_operators(op, value, expected_row, expected_other):
    assert matches(ROW, f(("sion", op, value))) is expected_row and matches(OTHER, f(("sion", op, value))) is expected_other


def test_empty_and_not_empty():
    assert matches(NO_CODES, f(("sion", "empty"))) and not matches(ROW, f(("sion", "empty")))
    assert matches(ROW, f(("hsn", "not_empty"))) and not matches(NO_CODES, f(("hsn", "not_empty")))


def test_all_and_any_logic_examples():
    e = f(("description", "contains", "DIETARY"), ("hsn", "starts_with", "0802"))
    assert matches(ROW, e) and not matches(OTHER, e)
    any_ = f(("description", "contains", "DIETARY"), ("description", "contains", "NUTS"), ("hsn", "starts_with", "1511"), logic="any")
    assert matches(ROW, any_) and matches(OTHER, any_) and not matches(NO_CODES, any_)
    g = f(("description", "contains", "OIL"), ("description", "not_contains", "CRUDE"), ("hsn", "not_starts_with", "0802"))
    assert matches(OTHER, g) and not matches(ROW, g)


def test_negative_operator_excludes_a_row_when_any_value_matches():
    row = {"description": ["PALM OIL", "PALM OIL CRUDE"], "hsn": ["15111000", "08029000"], "sion": ["E5"]}
    assert not matches(row, f(("description", "not_contains", "CRUDE")))
    assert not matches(row, f(("hsn", "not_starts_with", "0802")))


def test_no_conditions_match_everything_and_validation():
    assert matches(ROW, clean_filters(None)) and matches(ROW, clean_filters({"logic": "any", "conditions": []}))
    for bad in ({"logic": "xor"}, {"conditions": [{"field": "qty", "op": "contains", "value": "1"}]},
                {"conditions": [{"field": "hsn", "op": "like", "value": "1"}]}, {"conditions": [{"field": "hsn", "op": "contains", "value": ""}]},
                {"conditions": [{"field": "hsn", "op": "contains", "value": "x" * 201}]}, "nope", {"conditions": [{}] * 21}):
        with pytest.raises(FilterError):
            clean_filters(bad)


# --- nested groups (Licence Planning rule-builder shape) ---------------------------------------------------------------

def g(op, *children):
    return {"operator": op, "conditions": list(children)}


def c(field, op, value=""):
    return {"field": field, "op": op, "value": value}


NUTS_E1 = {"description": ["Mixed Nuts"], "hsn": ["20081910"], "sion": ["E1"]}
PALM = {"description": ["PALM OLEIN OIL"], "hsn": ["15119010"], "sion": ["E5"]}
PALM_CRUDE = {"description": ["CRUDE PALM OIL"], "hsn": ["15111000"], "sion": ["E5"]}
PALM_REFINED_CRUDE = {"description": ["REFINED PALM OIL (CRUDE GRADE)"], "hsn": ["15119020"], "sion": ["E5"]}
PKO = {"description": ["PALM KERNEL OIL"], "hsn": ["15132110"], "sion": ["E126"]}


def test_example_a_root_any_with_nested_all_groups():
    flt = clean_filters(g("ANY", g("ALL", c("description", "contains", "DIETARY"), c("hsn", "starts_with", "0802")),
                          g("ALL", c("description", "contains", "NUTS"), c("sion", "equals", "E1"))))
    assert matches(ROW, flt) and matches(NUTS_E1, flt) and not matches(OTHER, flt)


def test_example_b_root_all_with_nested_any():
    flt = clean_filters(g("ALL", c("description", "contains", "OIL"), g("ANY", c("hsn", "starts_with", "1511"), c("hsn", "starts_with", "1513"))))
    assert matches(PALM_CRUDE, flt) and matches(PKO, flt) and matches(OTHER, flt)
    assert not matches({"description": ["OLIVE OIL"], "hsn": ["15091000"], "sion": []}, flt)


def test_example_c_mixed_positive_and_negative_in_nested_group():
    flt = clean_filters(g("ALL", c("description", "contains", "PALM"), g("ANY", c("description", "not_contains", "CRUDE"), c("description", "starts_with", "REFINED"))))
    assert matches(PALM, flt) and matches(PALM_REFINED_CRUDE, flt) and not matches(PALM_CRUDE, flt)


def test_example_d_exclusion_with_null_safe_negatives():
    flt = clean_filters(g("ALL", c("description", "contains", "OIL"), c("description", "not_contains", "CRUDE"),
                          c("hsn", "not_starts_with", "0802"), c("sion", "not_empty")))
    assert matches(PALM, flt) and not matches(PALM_CRUDE, flt)
    assert not matches({"description": ["SOYA OIL"], "hsn": [], "sion": []}, flt)  # SION is not empty → excluded when missing


def test_three_levels_and_independent_logic_per_group():
    deep = g("ALL", c("description", "contains", "OIL"),
             g("ANY", c("sion", "equals", "E126"),
               g("ALL", c("hsn", "starts_with", "1511"), g("ANY", c("description", "not_contains", "CRUDE"), c("description", "starts_with", "REFINED")))))
    flt = clean_filters(deep)
    assert matches(PKO, flt) and matches(PALM_REFINED_CRUDE, flt) and not matches(PALM_CRUDE, flt)
    assert flt["conditions"][1]["conditions"][1]["conditions"][1]["operator"] == "OR"  # nested groups are kept, never flattened


def test_spec_shape_with_groups_list_and_all_any_aliases():
    flt = clean_filters({"operator": "ALL", "conditions": [c("description", "contains", "OIL")],
                         "groups": [{"operator": "ANY", "conditions": [c("hsn", "starts_with", "1511"), c("hsn", "starts_with", "1513")]}]})
    assert flt == {"operator": "AND", "conditions": [c("description", "contains", "OIL"),
                                                      {"operator": "OR", "conditions": [c("hsn", "starts_with", "1511"), c("hsn", "starts_with", "1513")]}]}


def test_group_validation_matches_planning():
    assert clean_filters(g("ALL", c("hsn", "starts_with", "15"), g("ANY"))) == {"operator": "AND", "conditions": [c("hsn", "starts_with", "15")]}  # empty nested pruned
    assert matches(ROW, clean_filters(g("ANY", g("ALL"))))  # only empty groups → no filter
    for bad in (g("XOR", c("hsn", "contains", "1")), g("ALL", g("ANY", c("hsn", "contains", ""))), {"operator": "ALL", "conditions": "x"},
                g("ALL", {"field": "hsn", "op": "contains"}), g("ALL", *[c("hsn", "contains", str(n)) for n in range(130)])):
        with pytest.raises(FilterError):
            clean_filters(bad)
    node = c("hsn", "contains", "1")
    for _ in range(13):
        node = g("ALL", node)
    with pytest.raises(FilterError, match="deeply nested"):
        clean_filters(node)


def test_ambiguous_nodes_are_rejected_never_silently_dropped():
    for bad in (g("ALL", {"field": "hsn", "op": "contains", "value": "1511", "operator": "AND"}),  # leaf carrying a group key
                c("hsn", "contains", "1511"),                                                     # unwrapped root leaf
                g("ALL", {"operator": "AND", "conditions": [], "field": "hsn"}),                  # group carrying a leaf key
                g("ALL", {"unexpected": 1})):
        with pytest.raises(FilterError):
            clean_filters(bad)
    with pytest.raises(FilterError, match="Condition 2.1"):
        clean_filters(g("ALL", c("hsn", "contains", "1"), g("ANY", c("hsn", "contains", ""))))
    assert clean_filters({"id": "r", "operator": "AND", "conditions": [{"id": "c1", **c("hsn", "contains", "1")}]})["conditions"] == [c("hsn", "contains", "1")]
