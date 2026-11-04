"""
Numerical validation of the authoritative CIF utilisation formula on the
production path: build_item_balance -> sale_boe_allocation.compute_utilisation
(with allotment_link for the allotment side).

Authoritative rule:
    Utilised CIF  = BOE CIF + ALLOTMENT CIF + BILLED CIF WITHOUT BOE
    Available CIF = Original CIF - Utilised CIF

Component definitions used by the independent oracle below:
    BOE CIF              = sum of every BOE CIF on the item (each BOE counted once)
    BILLED WITHOUT BOE   = sum over sales of max(0, sold - linked)
                           (the part of an invoice NOT represented by any BOE link)
    ALLOTMENT CIF        = outstanding allotment CIF not represented by a BOE

Because BILLED WITHOUT BOE excludes the linked part of every invoice, and BOE CIF
counts each BOE once, no source transaction can be counted twice.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.license.services.licence_item_balance import build_item_balance
from apps.license.services.licence_balance_report import allotment_link
from apps.license.services.sale_boe_allocation import (
    AllocationError,
    BoeEntry,
    BoeLink,
    SaleEntry,
)

D = Decimal


def _run(original, sales, boes, links=(), allot=D("0")):
    return build_item_balance(
        measure="cif",
        original=D(original),
        sales=[SaleEntry(s, cif=D(v)) for s, v in sales],
        boes=[BoeEntry(b, cif=D(v)) for b, v in boes],
        links=[BoeLink(lid, b, s, cif=D(v)) for lid, b, s, v in links],
        outstanding_allotment=D(allot),
    )


def _oracle(original, sales, boes, links, allot):
    """Independent three-component computation from first principles."""
    boe_cif = sum((D(v) for _, v in boes), D("0"))
    linked_per_sale = {s: D("0") for s, _ in sales}
    for _lid, _b, s, v in links:
        linked_per_sale[s] += D(v)
    billed_without_boe = sum(
        (max(D("0"), D(v) - linked_per_sale[s]) for s, v in sales), D("0")
    )
    utilised = boe_cif + D(allot) + billed_without_boe
    return {
        "boe": boe_cif,
        "allot": D(allot),
        "billed_wo_boe": billed_without_boe,
        "utilised": utilised,
        "available": D(original) - utilised,
    }


def _assert_matches_formula(result, original, sales, boes, links, allot):
    expected = _oracle(original, sales, boes, links, allot)
    assert result.original == D(original)
    # Production is expressed as debited (uncovered BOE + over-linked) + allotted + invoiced.
    # Invoiced counts every sale once, and the BOE-covered part of it is only a sub-amount,
    # so the production utilised total must equal the oracle utilised total exactly.
    production_utilised = result.debited + result.allotted + result.invoiced
    assert production_utilised == expected["utilised"]
    assert result.available == expected["available"]
    assert result.identity_ok is True
    return expected


# ---------------------------------------------------------------------------
# 1. BOE fully covering an invoice
# ---------------------------------------------------------------------------
def test_boe_fully_covers_invoice_counts_once():
    sales = [("S1", "100")]
    boes = [("B1", "100")]
    links = [("L1", "B1", "S1", "100")]
    r = _run("1000", sales, boes, links)
    e = _assert_matches_formula(r, "1000", sales, boes, links, "0")
    assert e["boe"] == D("100") and e["billed_wo_boe"] == D("0")
    assert r.available == D("900")
    assert r.debited == D("0")  # no uncovered BOE
    assert r.invoiced_boe_covered == D("100")


# ---------------------------------------------------------------------------
# 2. Invoice without BOE
# ---------------------------------------------------------------------------
def test_invoice_without_boe_is_billed_without_boe():
    sales = [("S1", "200")]
    r = _run("1000", sales, [], [])
    e = _assert_matches_formula(r, "1000", sales, [], [], "0")
    assert e["billed_wo_boe"] == D("200")
    assert r.available == D("800")


# ---------------------------------------------------------------------------
# 3. Partial BOE coverage
# ---------------------------------------------------------------------------
def test_partial_boe_coverage_splits_invoice_between_boe_and_billed():
    sales = [("S1", "100")]
    boes = [("B1", "60")]
    links = [("L1", "B1", "S1", "60")]
    r = _run("1000", sales, boes, links)
    e = _assert_matches_formula(r, "1000", sales, boes, links, "0")
    # 60 represented by BOE, 40 billed without BOE. Total utilised = 100, not 160.
    assert e["boe"] == D("60") and e["billed_wo_boe"] == D("40")
    assert e["utilised"] == D("100")
    assert r.available == D("900")


# ---------------------------------------------------------------------------
# 4. Allotment without BOE
# ---------------------------------------------------------------------------
def test_allotment_without_boe_reduces_available():
    r = _run("1000", [], [], [], allot="150")
    _assert_matches_formula(r, "1000", [], [], [], "150")
    assert r.allotted == D("150")
    assert r.available == D("850")


# ---------------------------------------------------------------------------
# 5. BOE and allotment overlap: the same CIF must not be counted twice
# ---------------------------------------------------------------------------
def _ai(cif, qty="0"):
    return SimpleNamespace(allotment_id=1, id=1, cif_fc=D(cif), qty=D(qty))


def _rd(rid, boe_id, cif, qty="0"):
    return SimpleNamespace(id=rid, bill_of_entry_id=boe_id, cif_fc=D(cif), qty=D(qty))


def test_boe_linked_to_allotment_removes_overlap_from_outstanding_allotment():
    ai = _ai("100")
    data = {"allotment_boes": {1: {"B1"}}}
    debit_rows = [_rd(1, "B1", "100")]
    link = allotment_link(ai, data, debit_rows)
    # The allotment CIF is already represented by BOE B1, so nothing stays outstanding for CIF.
    assert link.outstanding_cif == D("0")

    # Feed the production formula: B1 is an uncovered BOE (no sale), allotment outstanding = 0.
    r = _run("1000", [], [("B1", "100")], [], allot=str(link.outstanding_cif))
    assert r.allotted == D("0")
    assert r.debited == D("100")
    # Counted once, as BOE. Double counting would give 800.
    assert r.available == D("900")


def test_allotment_partially_covered_by_boe_keeps_only_unmatched_quantity_outstanding():
    ai = _ai("0", qty="50")
    data = {"allotment_boes": {1: {"B1"}}}
    debit_rows = [_rd(1, "B1", "0", qty="30")]
    link = allotment_link(ai, data, debit_rows)
    # Quantity rule: only the quantity not matched by a BOE stays outstanding.
    assert link.outstanding_qty == D("20")


# ---------------------------------------------------------------------------
# 6. Multiple invoices and BOEs
# ---------------------------------------------------------------------------
def test_multiple_invoices_and_boes_no_double_count():
    sales = [("S1", "60"), ("S2", "80")]
    boes = [("B1", "100"), ("B2", "50")]
    links = [
        ("L1", "B1", "S1", "60"),  # B1 fully covers S1
        ("L2", "B1", "S2", "40"),  # B1 partly covers S2
    ]
    r = _run("500", sales, boes, links)
    e = _assert_matches_formula(r, "500", sales, boes, links, "0")
    # BOE total 150 + billed-without-BOE 40 (S2 remainder) = 190 utilised.
    assert e["utilised"] == D("190")
    assert r.available == D("310")
    assert r.debited == D("50")  # only B2 is uncovered; B1 is fully consumed
    assert r.invoiced == D("140")


# ---------------------------------------------------------------------------
# 7. Duplicate allocation attempts
# ---------------------------------------------------------------------------
def test_duplicate_link_id_is_rejected():
    with pytest.raises(AllocationError):
        _run(
            "1000",
            [("S1", "100")],
            [("B1", "100")],
            [("L1", "B1", "S1", "50"), ("L1", "B1", "S1", "50")],
        )


def test_boe_over_allocated_beyond_its_own_amount_is_rejected():
    with pytest.raises(AllocationError):
        _run(
            "1000",
            [("S1", "100"), ("S2", "100")],
            [("B1", "100")],
            [("L1", "B1", "S1", "80"), ("L2", "B1", "S2", "80")],
        )


# ---------------------------------------------------------------------------
# 8. Zero balance
# ---------------------------------------------------------------------------
def test_exactly_consumed_licence_has_zero_available_and_is_not_over_utilised():
    sales = [("S1", "100")]
    r = _run("100", sales, [], [])
    _assert_matches_formula(r, "100", sales, [], [], "0")
    assert r.available == D("0")
    assert r.is_over_utilised is False


# ---------------------------------------------------------------------------
# 9. Negative balance
# ---------------------------------------------------------------------------
def test_negative_available_is_preserved_not_clamped():
    sales = [("S1", "150")]
    r = _run("100", sales, [], [])
    _assert_matches_formula(r, "100", sales, [], [], "0")
    assert r.available == D("-50")
    assert r.is_over_utilised is True
    assert r.over_utilised_amount == D("50")
    assert r.status == "OVER-UTILISED"


# ---------------------------------------------------------------------------
# 10. Over-utilisation via over-linking: BOE linked beyond the invoice
# ---------------------------------------------------------------------------
def test_over_linked_boe_excess_is_counted_not_dropped():
    sales = [("S1", "60")]
    boes = [("B1", "100")]
    links = [("L1", "B1", "S1", "100")]  # links 100 to a 60 invoice
    r = _run("90", sales, boes, links)
    _assert_matches_formula(r, "90", sales, boes, links, "0")
    # 40 over-linked excess is utilisation: 60 invoiced + 40 over-linked = 100 utilised.
    assert r.debited == D("40")
    assert r.invoiced == D("60")
    assert r.available == D("-10")
    assert r.is_over_utilised is True


# ---------------------------------------------------------------------------
# Cross-cutting: no transaction is counted twice in any combined scenario.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "original,sales,boes,links,allot",
    [
        ("1000", [("S1", "100")], [("B1", "100")], [("L1", "B1", "S1", "100")], "0"),
        ("1000", [("S1", "100")], [("B1", "60")], [("L1", "B1", "S1", "60")], "150"),
        ("500", [("S1", "60"), ("S2", "80")], [("B1", "100"), ("B2", "50")],
         [("L1", "B1", "S1", "60"), ("L2", "B1", "S2", "40")], "25"),
        ("90", [("S1", "60")], [("B1", "100")], [("L1", "B1", "S1", "100")], "0"),
        ("100", [("S1", "150")], [], [], "10"),
    ],
)
def test_production_matches_independent_formula(original, sales, boes, links, allot):
    r = _run(original, sales, boes, links, allot)
    _assert_matches_formula(r, original, sales, boes, links, allot)
    e = _oracle(original, sales, boes, links, allot)
    assert r.available == e["available"]


# ---------------------------------------------------------------------------
# Business definition: Original CIF is the import-licence entitlement, unadjusted.
# See docs/09-module-implementation/licence-cif-quantity-balance-business-rules.md §1.1.
# ---------------------------------------------------------------------------
class TestOriginalCifDefinition:
    def test_original_cif_is_passed_through_unchanged(self):
        # Purchase credits / trade debits are NOT applied to Original CIF.
        # Whatever sales and BOEs exist, the reported Original equals the endorsed entitlement.
        r = _run("1234.56", [("S1", "200")], [("B1", "50")], [("L1", "B1", "S1", "50")])
        assert r.original == D("1234.56")

    def test_original_cif_is_not_adjusted_by_zero_movements(self):
        r = _run("1000", [], [], [])
        assert r.original == D("1000")
        assert r.available == D("1000")

    def test_production_path_does_not_import_the_d1_calculator(self):
        # Guard: the separate D-1 engine must not be wired into production consumers
        # until purchase-credit / trade-debit treatment is formally decided.
        from pathlib import Path

        services = Path(__file__).resolve().parents[1] / "services"
        for name in ("licence_item_balance.py", "sale_boe_allocation.py", "licence_balance_report.py"):
            source = (services / name).read_text()
            assert "financial_position" not in source, f"{name} must not depend on financial_position"
