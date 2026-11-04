"""Numerical-oracle tests for the planning CIF budget.

Planning Original CIF = export-manifest CIF per SION norm (never import-item CIF).
Utilised CIF = BOE CIF + ALLOTMENT CIF + BILLED CIF WITHOUT BOE, mutually exclusive.
Each expected value below is derived by hand from those formulas.
"""
from decimal import Decimal

import pytest

from apps.license.services.planning_financial_budget import (
    STATUS_NO_AVAILABLE,
    STATUS_NO_ENTITLEMENT,
    STATUS_NOT_COMPUTED,
    STATUS_OVER_UTILISED,
    CanonicalUtilisation,
    compute_norm_budgets,
)

D = Decimal


def util(debited="0", allotted="0", invoiced="0", covered="0"):
    return CanonicalUtilisation(
        debited=D(debited), allotted=D(allotted), invoiced=D(invoiced), invoiced_boe_covered=D(covered),
    )


def one_norm(export, u, attributed="0"):
    budgets = compute_norm_budgets(
        export_cif_by_norm={1: D(export)}, attributed_cif_by_norm={1: D(attributed)}, utilisation=u,
    )
    return budgets[1]


# --- Positive availability ---------------------------------------------------

def test_positive_available_allows_allocation_up_to_licence_remainder():
    # export 1000; uncovered BOE 100 -> remaining 900; no attribution
    b = one_norm("1000", util(debited="100"))
    assert b.status is None and b.allowed
    assert b.ceiling == D("900")


def test_planning_original_is_export_manifest_not_import_cif():
    # The budget depends only on export CIF and utilisation. A larger import-item CIF
    # has no input in this calculation, so it cannot raise the ceiling.
    b = one_norm("300", util(debited="0"))
    assert b.ceiling == D("300")


# --- Billed without BOE --------------------------------------------------------

def test_billed_without_boe_sales_reduce_planning_availability():
    # invoiced 500, of which 200 is covered by BOE. Utilised = BOE 200 + billed 300 = 500.
    u = util(invoiced="500", covered="200", debited="0")
    assert u.boe_cif == D("200")
    assert u.billed_without_boe_cif == D("300")
    assert u.utilised_cif == D("500")
    b = one_norm("1000", u)
    assert b.ceiling == D("500")


def test_boe_covered_invoice_is_not_double_counted():
    # invoice 100 fully covered by a BOE of 100. Utilised = 100, not 200.
    u = util(invoiced="100", covered="100")
    assert u.utilised_cif == D("100")
    b = one_norm("300", u)
    assert b.ceiling == D("200")


def test_partial_boe_leaves_remainder_as_billed_without_boe():
    # invoice 100; BOE 60 covers 60. Billed without BOE = 40. Utilised = 60 + 40 = 100.
    u = util(invoiced="100", covered="60", debited="0")
    assert u.boe_cif == D("60")
    assert u.billed_without_boe_cif == D("40")
    assert u.utilised_cif == D("100")


def test_over_linked_boe_counts_once_as_debited():
    # BOE 100 linked to a 60 invoice: 60 covered + 40 over-linked (debited). Utilised = 100.
    u = util(debited="40", invoiced="60", covered="60")
    assert u.utilised_cif == D("100")
    assert u.boe_cif == D("100")
    assert u.billed_without_boe_cif == D("0")


# --- Allotment ---------------------------------------------------------------

def test_outstanding_allotment_without_boe_reduces_availability():
    b = one_norm("1000", util(allotted="150"))
    assert b.ceiling == D("850")


def test_allotment_overlapping_boe_is_counted_once_as_boe():
    # The allotment CIF is already represented by BOE, so it is not in `allotted`.
    # Only the BOE debit (100) is counted.
    b = one_norm("1000", util(debited="100", allotted="0"))
    assert b.ceiling == D("900")


# --- Zero, negative and over-utilisation --------------------------------------

def test_zero_available_blocks_further_allocation():
    b = one_norm("100", util(invoiced="100"))
    assert b.status == STATUS_NO_AVAILABLE
    assert b.ceiling == D("0") and not b.allowed


def test_negative_available_blocks_and_reports_excess():
    b = one_norm("100", util(invoiced="150"))
    assert b.status == STATUS_OVER_UTILISED
    assert b.over_utilised_cif == D("50")
    assert b.ceiling == D("0")


def test_legacy_positive_balance_cannot_override_negative_canonical():
    # Whatever a legacy balance says, the canonical utilisation of 150 against 100
    # entitlement is over-utilisation. The function takes no legacy input.
    b = one_norm("100", util(invoiced="150"))
    assert b.status == STATUS_OVER_UTILISED


# --- Multiple norms and attribution -------------------------------------------

def test_multiple_norms_each_bounded_by_their_own_export_entitlement():
    budgets = compute_norm_budgets(
        export_cif_by_norm={1: D("600"), 2: D("400")},
        attributed_cif_by_norm={1: D("0"), 2: D("0")},
        utilisation=util(debited="0"),
    )
    assert budgets[1].ceiling == D("600")
    assert budgets[2].ceiling == D("400")


def test_attributed_usage_reduces_only_its_own_norm_first():
    # 300 of BOE usage is attributed to norm 1. Norm 1 has 600 export, so 300 remains.
    # Norm 2 keeps its full 400 because the licence remainder is 700.
    budgets = compute_norm_budgets(
        export_cif_by_norm={1: D("600"), 2: D("400")},
        attributed_cif_by_norm={1: D("300"), 2: D("0")},
        utilisation=util(debited="300"),
    )
    assert budgets[1].ceiling == D("300")
    assert budgets[2].ceiling == D("400")


def test_norm_over_attribution_blocks_that_norm_even_when_licence_has_room():
    # Norm 1 export 100; 150 of usage attributed to it. Licence remainder is 450 (>0),
    # but norm 1 is over-attributed by 50.
    budgets = compute_norm_budgets(
        export_cif_by_norm={1: D("100"), 2: D("500")},
        attributed_cif_by_norm={1: D("150"), 2: D("0")},
        utilisation=util(debited="150"),
    )
    assert budgets[1].status == STATUS_OVER_UTILISED
    assert budgets[1].over_utilised_cif == D("50")
    assert budgets[2].status is None


def test_ceiling_never_exceeds_licence_remainder_across_norms():
    # Two norms with 1000 each. Licence utilised 1500 leaves 500 for the licence.
    # Each norm is bounded by the licence remainder, so neither can take more than 500.
    budgets = compute_norm_budgets(
        export_cif_by_norm={1: D("1000"), 2: D("1000")},
        attributed_cif_by_norm={1: D("0"), 2: D("0")},
        utilisation=util(debited="1500"),
    )
    assert budgets[1].ceiling == D("500")
    assert budgets[2].ceiling == D("500")


def test_unattributed_utilisation_is_reported_and_counted_at_licence_level():
    b = one_norm("1000", util(debited="200"), attributed="0")
    assert b.unattributed_utilisation_cif == D("200")
    assert b.ceiling == D("800")


# --- Missing data, fail closed ------------------------------------------------

def test_missing_canonical_result_fails_closed_for_every_norm():
    budgets = compute_norm_budgets(
        export_cif_by_norm={1: D("500"), 2: D("300")},
        attributed_cif_by_norm={},
        utilisation=None,
    )
    for b in budgets.values():
        assert b.status == STATUS_NOT_COMPUTED
        assert b.ceiling == D("0") and not b.allowed


def test_missing_export_entitlement_is_a_data_quality_block():
    budgets = compute_norm_budgets(
        export_cif_by_norm={1: D("0")},
        attributed_cif_by_norm={},
        utilisation=util(),
    )
    assert budgets[1].status == STATUS_NO_ENTITLEMENT
    assert budgets[1].ceiling == D("0")


def test_missing_attribution_defaults_to_zero_not_to_a_guess():
    # No attribution entry for norm 1: treated as zero attributed usage, never guessed.
    b = compute_norm_budgets(
        export_cif_by_norm={1: D("100")}, attributed_cif_by_norm={}, utilisation=util(debited="10"),
    )[1]
    assert b.attributed_cif == D("0")
    assert b.ceiling == D("90")


# --- Determinism, invariants and repeat execution ----------------------------

@pytest.mark.parametrize(
    "debited,allotted,invoiced,covered",
    [
        ("0", "0", "0", "0"),
        ("100", "0", "0", "0"),
        ("0", "150", "0", "0"),
        ("0", "0", "500", "200"),
        ("40", "0", "60", "60"),
        ("30", "20", "250", "100"),
    ],
)
def test_utilisation_components_are_mutually_exclusive_and_sum_to_utilised(debited, allotted, invoiced, covered):
    u = util(debited=debited, allotted=allotted, invoiced=invoiced, covered=covered)
    assert u.boe_cif + u.allotment_cif + u.billed_without_boe_cif == u.utilised_cif
    assert u.utilised_cif == D(debited) + D(allotted) + D(invoiced)


def test_repeated_computation_is_idempotent():
    args = dict(
        export_cif_by_norm={1: D("600"), 2: D("400")},
        attributed_cif_by_norm={1: D("300"), 2: D("0")},
        utilisation=util(debited="300", invoiced="50", covered="10"),
    )
    first = compute_norm_budgets(**args)
    second = compute_norm_budgets(**args)
    assert {k: (v.status, v.ceiling) for k, v in first.items()} == {k: (v.status, v.ceiling) for k, v in second.items()}


def test_separate_licences_are_computed_independently():
    a = one_norm("1000", util(debited="100"))
    b = one_norm("50", util(invoiced="80"))
    assert a.ceiling == D("900")
    assert b.status == STATUS_OVER_UTILISED and b.over_utilised_cif == D("30")


def test_ceiling_is_never_negative():
    for export, utilised in [("0", "0"), ("10", "1000"), ("1000", "1000")]:
        b = one_norm(export, util(invoiced=utilised))
        assert b.ceiling >= 0


def test_summary_parsing_maps_canonical_fields():
    u = CanonicalUtilisation.from_summary({
        "debited": "40.00", "allotted": "20.00", "invoiced": "60.00", "invoiced_boe_covered": "60.00",
    })
    assert u.utilised_cif == D("120.00")
    assert u.boe_cif == D("100.00")
    assert u.billed_without_boe_cif == D("0.00")
