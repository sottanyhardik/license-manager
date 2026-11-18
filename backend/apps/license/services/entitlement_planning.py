"""Generic entitlement planning engine (pure Decimal, no ORM, no product names).

Produces the two spreadsheet-style sections for ONE licence and ONE norm:

OPENING PLANNING
    For every product group (in waterfall order) and every entitlement of the
    group (in sequence order):
        quantity    = group authorised quantity × split percentage / 100
        planned CIF = min(quantity × max unit price, CIF still available)
        CIF available after the row = previous − planned CIF
    The effective rate is planned CIF / quantity (equal to the max price
    unless the licence CIF runs out).

AFTER BOE DEBITS AND ALLOTTED
    Per entitlement:
        balance quantity = opening − BOE debited − outstanding allotted
    ``RATE`` entitlements:  balance CIF = balance quantity × opening rate
    ``RESIDUAL`` entitlement: balance CIF = remaining licence CIF − Σ other
        entitlements' balance CIF.  The spread between that and
        (opening − BOE − allotted) is reported explicitly as two components:
        CIF released by the other entitlements (their actual debit rates
        differed from the planned rate) and other authoritative adjustments
        (debits outside any planned group, unattributed debits, and the
        difference to the authoritative licence balance).  Nothing is
        invented: every component is the difference of two recorded totals.

Remaining licence CIF is the authoritative licence balance when the caller
supplies it, else opening CIF − all BOE CIF − all outstanding allotment CIF.

Quantization happens only in ``_out`` (the presentation edge).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

ZERO = Decimal("0")
HUNDRED = Decimal("100")
CENT = Decimal("0.01")
MILLI = Decimal("0.001")
RATE_Q = Decimal("0.0001")
QTY_TOLERANCE = Decimal("0.001")

RATE = "RATE"
RESIDUAL = "RESIDUAL"
VALUATIONS = (RATE, RESIDUAL)

BOE = "BOE"
ALLOTMENT = "ALLOTMENT"

# Debit attribution states (decided by the caller / adapter).
MAPPED = "MAPPED"
UNMAPPED = "UNMAPPED"          # inside a planned group, entitlement unknown
AMBIGUOUS = "AMBIGUOUS"        # matches more than one entitlement
OUTSIDE = "OUTSIDE_GROUPS"     # import item belongs to no planned group


@dataclass(frozen=True)
class EntitlementSpec:
    key: str
    label: str
    percentage: Decimal
    max_unit_price: Decimal
    valuation: str = RATE
    products: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroupSpec:
    key: str
    label: str
    quantity: Decimal
    entitlements: tuple[EntitlementSpec, ...]
    source_records: int = 0


@dataclass(frozen=True)
class Debit:
    kind: str                     # BOE | ALLOTMENT
    reference: str
    quantity: Decimal
    cif: Decimal
    status: str = MAPPED
    entitlement_key: str | None = None
    group_key: str | None = None
    detail: dict = field(default_factory=dict)


@dataclass
class _Line:
    group: GroupSpec
    spec: EntitlementSpec
    quantity: Decimal = ZERO
    planned_cif: Decimal = ZERO
    cif_available_after: Decimal = ZERO
    boe_qty: Decimal = ZERO
    boe_cif: Decimal = ZERO
    allot_qty: Decimal = ZERO
    allot_cif: Decimal = ZERO
    boe_rows: list = field(default_factory=list)
    allot_rows: list = field(default_factory=list)

    @property
    def opening_rate(self) -> Decimal:
        return self.planned_cif / self.quantity if self.quantity > 0 else self.spec.max_unit_price

    @property
    def balance_qty(self) -> Decimal:
        return self.quantity - self.boe_qty - self.allot_qty


def d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return ZERO
    return Decimal(str(value))


def _q(value: Decimal | None, step: Decimal) -> str | None:
    if value is None:
        return None
    return str(value.quantize(step, rounding=ROUND_HALF_UP))


def _money(value):
    return _q(value, CENT)


def _qty(value):
    return _q(value, MILLI)


def _rate(cif: Decimal, qty: Decimal):
    return _q(cif / qty, RATE_Q) if qty and qty != 0 else None


# ── Validation ───────────────────────────────────────────────────────────────
def validate_groups(groups: Iterable[GroupSpec]) -> list[dict]:
    """Configuration checks.  ``blocking`` issues prevent confirmation."""
    issues: list[dict] = []
    residuals = []
    for group in groups:
        total_pct = sum((e.percentage for e in group.entitlements), ZERO)
        if total_pct != HUNDRED:
            issues.append(_issue("SPLIT_NOT_100", True, group.key, None,
                                 f"{group.label}: split percentages total {total_pct}%, expected 100%."))
        keys = [e.key for e in group.entitlements]
        if len(keys) != len(set(keys)):
            issues.append(_issue("DUPLICATE_ENTITLEMENT", True, group.key, None,
                                 f"{group.label}: an entitlement is configured twice."))
        for ent in group.entitlements:
            if ent.valuation not in VALUATIONS:
                issues.append(_issue("INVALID_VALUATION", True, group.key, ent.key,
                                     f"{ent.label}: unknown valuation {ent.valuation!r}."))
            if ent.max_unit_price is None or ent.max_unit_price <= 0:
                issues.append(_issue("MISSING_UNIT_PRICE", True, group.key, ent.key,
                                     f"{ent.label}: maximum unit price is not configured."))
            if ent.valuation == RESIDUAL:
                residuals.append(ent)
    if len(residuals) > 1:
        issues.append(_issue("MULTIPLE_RESIDUAL", True, None, None,
                             "More than one entitlement is configured to absorb the residual CIF."))
    return issues


def _issue(code, blocking, group_key, entitlement_key, message, **extra) -> dict:
    return {"code": code, "blocking": blocking, "group": group_key,
            "entitlement": entitlement_key, "message": message, **extra}


# ── Engine ───────────────────────────────────────────────────────────────────
def compute_entitlement_plan(
    *,
    opening_cif,
    groups: Iterable[GroupSpec],
    debits: Iterable[Debit] = (),
    authoritative_balance=None,
    extra_issues: Iterable[dict] = (),
) -> dict:
    groups = [g for g in groups if g.entitlements]
    debits = list(debits)
    opening_cif = d(opening_cif)
    issues = validate_groups(groups) + list(extra_issues)

    lines = _opening_waterfall(opening_cif, groups)
    by_key = {line.spec.key: line for line in lines}
    outside = _attribute_debits(debits, by_key, issues)

    total_boe = sum((x.cif for x in debits if x.kind == BOE), ZERO)
    total_allot = sum((x.cif for x in debits if x.kind == ALLOTMENT), ZERO)
    computed_remaining = opening_cif - total_boe - total_allot
    remaining = d(authoritative_balance) if authoritative_balance is not None else computed_remaining
    authority_difference = remaining - computed_remaining

    opening_planned = sum((x.planned_cif for x in lines), ZERO)
    after = _after_section(lines, remaining, issues)
    adjustments = _adjustments(outside, authority_difference)
    _attach_residual_components(after, lines, adjustments, opening_cif - opening_planned)
    _over_utilisation_checks(lines, after, issues)
    unreconciled = remaining - after["total_balance_cif"]
    if unreconciled != 0:
        issues.append(_issue(
            "BALANCE_NOT_FULLY_PLANNED", False, None, None,
            f"{_money(unreconciled)} of the remaining licence CIF is not carried by any entitlement balance "
            f"(no residual entitlement, or the residual is capped at its maximum unit price)."))
    return {
        "opening": {
            "total_cif": _money(opening_cif),
            "total_quantity": _qty(sum((g.quantity for g in groups), ZERO)),
            "rows": [_opening_row(x) for x in lines],
            "groups": [_group_row(g, [x for x in lines if x.group.key == g.key]) for g in groups],
            "total_planned_cif": _money(opening_planned),
            "unplanned_cif": _money(opening_cif - opening_planned),
        },
        "after": {
            "entitlements": after["rows"],
            "total_balance_cif": _money(after["total_balance_cif"]),
            "remaining_licence_cif": _money(remaining),
        },
        "totals": {
            "boe_debit_quantity": _qty(sum((x.quantity for x in debits if x.kind == BOE), ZERO)),
            "boe_debit_cif": _money(total_boe),
            "allotment_quantity": _qty(sum((x.quantity for x in debits if x.kind == ALLOTMENT), ZERO)),
            "allotment_cif": _money(total_allot),
        },
        "reconciliation": {
            "opening_cif": _money(opening_cif),
            "boe_debit_cif": _money(total_boe),
            "allotment_cif": _money(total_allot),
            "computed_remaining_cif": _money(computed_remaining),
            "authoritative_remaining_cif": _money(remaining),
            "authority_difference": _money(authority_difference),
            "adjustments": [{**a, "cif": _money(a["cif"])} for a in adjustments],
            "unreconciled_cif": _money(unreconciled),
            "status": "RECONCILED" if unreconciled == 0 and not any(i["blocking"] for i in issues) else "ATTENTION",
        },
        "issues": issues,
        "can_confirm": not any(i["blocking"] for i in issues),
    }


def _opening_waterfall(opening_cif: Decimal, groups: list[GroupSpec]) -> list[_Line]:
    remaining = opening_cif
    lines: list[_Line] = []
    for group in groups:
        for spec in group.entitlements:
            line = _Line(group=group, spec=spec)
            line.quantity = group.quantity * spec.percentage / HUNDRED
            cap = line.quantity * (spec.max_unit_price or ZERO)
            line.planned_cif = max(min(cap, remaining), ZERO)
            remaining -= line.planned_cif
            line.cif_available_after = remaining
            lines.append(line)
    return lines


def _attribute_debits(debits: list[Debit], by_key: dict, issues: list) -> list[Debit]:
    outside: list[Debit] = []
    for debit in debits:
        line = by_key.get(debit.entitlement_key) if debit.status == MAPPED else None
        if line is None:
            outside.append(debit)
            if debit.status in (UNMAPPED, AMBIGUOUS) or (debit.status == MAPPED and debit.entitlement_key):
                issues.append(_issue(
                    "UNATTRIBUTED_DEBIT", True, debit.group_key, debit.entitlement_key,
                    f"{debit.kind} {debit.reference}: {_money(debit.cif)} CIF / {_qty(debit.quantity)} qty "
                    f"could not be attributed to one entitlement ({debit.status}).",
                    reference=debit.reference, kind=debit.kind,
                ))
            continue
        row = {"kind": debit.kind, "reference": debit.reference,
               "quantity": _qty(debit.quantity), "cif": _money(debit.cif),
               "rate": _rate(debit.cif, debit.quantity), **debit.detail}
        if debit.kind == BOE:
            line.boe_qty += debit.quantity
            line.boe_cif += debit.cif
            line.boe_rows.append(row)
        else:
            line.allot_qty += debit.quantity
            line.allot_cif += debit.cif
            line.allot_rows.append(row)
    return outside


def _after_section(lines: list[_Line], remaining: Decimal, issues: list) -> dict:
    rows: list[dict] = []
    rate_total = ZERO
    balances: dict[str, Decimal] = {}
    for line in lines:
        if line.spec.valuation == RATE:
            balances[line.spec.key] = line.balance_qty * line.opening_rate
            rate_total += balances[line.spec.key]
    for line in lines:
        if line.spec.valuation == RESIDUAL:
            residual = remaining - rate_total
            cap = max(line.balance_qty, ZERO) * line.spec.max_unit_price
            if residual > cap:
                issues.append(_issue(
                    "RESIDUAL_ABOVE_MAX_PRICE", False, line.group.key, line.spec.key,
                    f"{line.spec.label}: residual CIF {_money(residual)} exceeds balance quantity × max price "
                    f"({_money(cap)}); {_money(residual - cap)} CIF stays unplanned.",
                ))
                residual = cap
            balances[line.spec.key] = residual
    total = ZERO
    for line in lines:
        bal_cif = balances[line.spec.key]
        total += bal_cif
        rows.append({
            "group": line.group.key, "group_label": line.group.label,
            "entitlement": line.spec.key, "label": line.spec.label,
            "products": list(line.spec.products), "valuation": line.spec.valuation,
            "percentage": str(line.spec.percentage),
            "opening": {"quantity": _qty(line.quantity), "rate": _rate(line.planned_cif, line.quantity),
                        "cif": _money(line.planned_cif)},
            "boe_debited": {"quantity": _qty(line.boe_qty), "rate": _rate(line.boe_cif, line.boe_qty),
                            "cif": _money(line.boe_cif), "rows": line.boe_rows},
            "allotted": {"quantity": _qty(line.allot_qty), "rate": _rate(line.allot_cif, line.allot_qty),
                         "cif": _money(line.allot_cif), "rows": line.allot_rows},
            "components": [],
            "balance": {"quantity": _qty(line.balance_qty), "rate": _rate(bal_cif, line.balance_qty),
                        "cif": _money(bal_cif)},
            "_balance_cif": bal_cif,
        })
    return {"rows": rows, "total_balance_cif": total}


def _adjustments(outside: list[Debit], authority_difference: Decimal) -> list[dict]:
    adjustments = []
    for kind in (BOE, ALLOTMENT):
        for status, code in ((OUTSIDE, "DEBITS_OUTSIDE_PLANNED_GROUPS"), (None, "UNATTRIBUTED_DEBITS")):
            rows = [x for x in outside if x.kind == kind and ((x.status == OUTSIDE) == (status == OUTSIDE))]
            if rows:
                adjustments.append({
                    "code": f"{kind}_{code}", "cif": -sum((x.cif for x in rows), ZERO),
                    "references": [x.reference for x in rows],
                })
    if authority_difference != 0:
        adjustments.append({"code": "AUTHORITATIVE_BALANCE_DIFFERENCE", "cif": authority_difference,
                            "references": []})
    return adjustments


def _attach_residual_components(after: dict, lines: list[_Line], adjustments: list[dict],
                                opening_unplanned: Decimal) -> None:
    """Explain the residual entitlement's balance as recorded components."""
    released_total = ZERO
    for row, line in zip(after["rows"], lines):
        if line.spec.valuation != RATE:
            continue
        released = line.planned_cif - line.boe_cif - line.allot_cif - row["_balance_cif"]
        if released != 0:
            row["components"].append({"code": "RELEASED_TO_RESIDUAL", "cif": _money(-released)})
            released_total += released
    adjustment_total = sum((a["cif"] for a in adjustments), ZERO)
    for row, line in zip(after["rows"], lines):
        if line.spec.valuation == RESIDUAL:
            if released_total != 0:
                row["components"].append({"code": "RECEIVED_FROM_OTHER_ENTITLEMENTS", "cif": _money(released_total)})
            if adjustment_total != 0:
                row["components"].append({"code": "OTHER_AUTHORITATIVE_ADJUSTMENTS", "cif": _money(adjustment_total)})
            if opening_unplanned != 0:
                row["components"].append({"code": "UNPLANNED_OPENING_CIF", "cif": _money(opening_unplanned)})
            expected = (line.planned_cif - line.boe_cif - line.allot_cif + released_total + adjustment_total
                        + opening_unplanned)
            unexplained = row["_balance_cif"] - expected
            if unexplained != 0:  # residual capped at max price
                row["components"].append({"code": "UNPLANNED_ABOVE_MAX_PRICE", "cif": _money(unexplained)})
    for row in after["rows"]:
        row.pop("_balance_cif", None)


def _over_utilisation_checks(lines: list[_Line], after: dict, issues: list) -> None:
    for row, line in zip(after["rows"], lines):
        if line.balance_qty < -QTY_TOLERANCE:
            issues.append(_issue("OVER_UTILISED_QUANTITY", True, line.group.key, line.spec.key,
                                 f"{line.spec.label}: debits exceed the entitlement by "
                                 f"{_qty(-line.balance_qty)} qty."))
        if d(row["balance"]["cif"]) < 0:
            issues.append(_issue("OVER_UTILISED_CIF", True, line.group.key, line.spec.key,
                                 f"{line.spec.label}: balance CIF is negative ({row['balance']['cif']})."))


def _opening_row(line: _Line) -> dict:
    return {
        "group": line.group.key, "group_label": line.group.label,
        "entitlement": line.spec.key, "label": line.spec.label,
        "products": list(line.spec.products), "percentage": str(line.spec.percentage),
        "valuation": line.spec.valuation,
        "quantity": _qty(line.quantity),
        "max_unit_price": str(line.spec.max_unit_price),
        "unit_price": _rate(line.planned_cif, line.quantity),
        "planned_cif": _money(line.planned_cif),
        "cif_available": _money(line.cif_available_after),
    }


def _group_row(group: GroupSpec, lines: list[_Line]) -> dict:
    split_qty = sum((x.quantity for x in lines), ZERO)
    return {
        "group": group.key, "label": group.label, "quantity": _qty(group.quantity),
        "source_records": group.source_records,
        "split_quantity": _qty(split_qty),
        "reconciles": abs(split_qty - group.quantity) <= QTY_TOLERANCE,
        "split": [{"entitlement": x.spec.key, "label": x.spec.label,
                   "percentage": str(x.spec.percentage)} for x in lines],
    }
