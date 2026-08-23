"""Atomic, Decimal percentage-group allocation.

The target percentage is a cap on the final accounted group quantity; actual
usage is historical and is deducted once when deriving the *new* quantity.
"""
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

ZERO = Decimal("0")
QTY = Decimal("0.001")
CIF = Decimal("0.01")


def solve_percentage_group(*, base_qty, members, available_cif, group_balance_qty):
    """Return a proportional final group scale and new plan rows.

    ``members`` contains ``percentage``, ``rate``, ``actual_qty`` and optional
    ``balance_qty``.  This is intentionally a group solver: no member is
    allowed to consume the CIF pool ahead of its siblings.
    """
    base = Decimal(str(base_qty)); cash = Decimal(str(available_cif)); group_cap = Decimal(str(group_balance_qty))
    rows = [{**row, "percentage": Decimal(str(row["percentage"])), "rate": Decimal(str(row["rate"])), "actual_qty": Decimal(str(row.get("actual_qty", 0))), "balance_qty": Decimal(str(row.get("balance_qty", base)))} for row in members]
    if not rows or sum((r["percentage"] for r in rows), ZERO) != Decimal("100"):
        raise ValueError("Percentage group must contain members totalling exactly 100%.")
    # Start with the largest final group scale allowed by configured targets,
    # shared balance, member balance, and then solve its cost against CIF.
    upper = min(base, group_cap)
    for row in rows:
        if row["percentage"] > ZERO:
            # actual + new may not exceed the input's net balance/cap.
            upper = min(upper, (row["actual_qty"] + row["balance_qty"]) * Decimal("100") / row["percentage"])
    # Within the normal (non-overused) region, new cost is linear in T.
    intercept = sum((min(row["actual_qty"], row["percentage"] * upper / Decimal("100")) * row["rate"] for row in rows), ZERO)
    weighted = sum((row["percentage"] / Decimal("100") * row["rate"] for row in rows), ZERO)
    if weighted > ZERO:
        upper = min(upper, max((cash + intercept) / weighted, ZERO))
    final_total = upper.quantize(QTY, rounding=ROUND_DOWN)
    result = []
    for row in rows:
        target = (base * row["percentage"] / Decimal("100")).quantize(QTY, rounding=ROUND_DOWN)
        final_qty = (final_total * row["percentage"] / Decimal("100")).quantize(QTY, rounding=ROUND_HALF_UP)
        new_qty = max(final_qty - row["actual_qty"], ZERO).quantize(QTY, rounding=ROUND_DOWN)
        new_qty = min(new_qty, row["balance_qty"])
        new_cif = (new_qty * row["rate"]).quantize(CIF, rounding=ROUND_HALF_UP)
        result.append({**row, "percentage_target_qty": target, "final_accounted_qty": final_qty,
                       "new_planned_qty": new_qty, "new_planned_cif": new_cif,
                       "unfilled_target_qty": max(target-final_qty, ZERO)})
    # A final penny/quantity reduction, deterministic on the most expensive
    # new member, guarantees never exceeding the CIF hard cap.
    total = sum((r["new_planned_cif"] for r in result), ZERO)
    if total > cash:
        raise ValueError("No quantity-precision percentage solution fits available CIF.")
    return {"final_group_qty": final_total, "new_planned_cif": total, "members": result,
            "unallocated_cif": max(cash-total, ZERO)}


def reduce_high_rate_first(*, prior_sequence_cif, members, actual_balance_cif):
    """Apply the CIF cap without changing planned or actual quantities.

    The configured rate remains immutable rule configuration.  The result
    carries a plan-specific effective rate and adjusted CIF instead.
    """
    prior = Decimal(str(prior_sequence_cif)); cap = Decimal(str(actual_balance_cif))
    rows = [dict(row) for row in members]
    for row in rows:
        row["unit_rate"] = Decimal(str(row["unit_rate"]))
        row["new_planned_qty"] = Decimal(str(row["new_planned_qty"]))
        row["new_planned_cif"] = Decimal(str(row["new_planned_cif"]))
        row["configured_max_unit_price"] = row["unit_rate"]
        row["original_planned_cif"] = row["new_planned_cif"]
        row["member_sequence"] = int(row.get("member_sequence", 0))
        row["cif_cap_reduction_qty"] = ZERO; row["cif_cap_reduction_cif"] = ZERO
    candidate = prior + sum((r["new_planned_cif"] for r in rows), ZERO)
    excess = max(candidate-cap, ZERO)
    for row in sorted(rows, key=lambda r: (-r["unit_rate"], r["member_sequence"])):
        if excess <= ZERO or row["unit_rate"] <= ZERO:
            continue
        minimum_rate = Decimal(str(row.get("minimum_allowed_rate", ZERO)))
        minimum_cif = (row["new_planned_qty"] * minimum_rate).quantize(CIF, rounding=ROUND_HALF_UP)
        cif_cut = min(max(row["new_planned_cif"] - minimum_cif, ZERO), excess)
        row["new_planned_cif"] -= cif_cut
        # Quantity deliberately stays unchanged.  This is an effective plan
        # price, not a mutation of the saved rule's configured maximum rate.
        row["cif_cap_reduction_cif"] = cif_cut
        row["effective_unit_price"] = (
            row["new_planned_cif"] / row["new_planned_qty"]
            if row["new_planned_qty"] > ZERO else ZERO
        )
        excess = max(prior + sum((r["new_planned_cif"] for r in rows), ZERO) - cap, ZERO)
    adjusted = prior + sum((r["new_planned_cif"] for r in rows), ZERO)
    if adjusted > cap:
        raise ValueError("Actual Balance CIF cap cannot be satisfied by active percentage members.")
    for row in rows:
        row.setdefault("effective_unit_price", row["unit_rate"])
        row["adjustment_reason"] = "ACTUAL_BALANCE_CIF_CAP" if row["cif_cap_reduction_cif"] else None
    return {"candidate_new_planned_cif": candidate, "actual_balance_cif": cap,
            "cif_excess_before_adjustment": max(candidate-cap, ZERO),
            "adjusted_new_planned_cif": adjusted, "final_balance_cif": max(cap-adjusted, ZERO),
            "members": rows, "strategy": "HIGHEST_RATE_FIRST"}


def solve_balancing_price_group(*, base_qty, members, group_available_cif, group_available_qty=None, group_target_cif=None):
    """Solve a split group with auditable cross-member excess transfer."""
    base = Decimal(str(base_qty)); available = Decimal(str(group_available_cif))
    target_pool = Decimal(str(group_target_cif if group_target_cif is not None else available))
    rows = [{**row, "percentage": Decimal(str(row["percentage"])), "configured_max_unit_price": Decimal(str(row["configured_max_unit_price"])), "actual_used_qty": Decimal(str(row.get("actual_used_qty", 0))), "actual_used_cif": Decimal(str(row.get("actual_used_cif", 0)))} for row in members]
    if sum((r["percentage"] for r in rows), ZERO) != Decimal("100"):
        raise ValueError("Percentage group must total 100%.")
    for row in rows:
        row["percentage_target_qty"] = (base * row["percentage"] / Decimal("100")).quantize(QTY, rounding=ROUND_HALF_UP)
    balancing = max(rows, key=lambda row: (row["configured_max_unit_price"], -int(row.get("member_sequence", 0))))
    fixed_target_cif = sum((
        row["percentage_target_qty"] * row["configured_max_unit_price"]
        for row in rows if row is not balancing
    ), ZERO).quantize(CIF, rounding=ROUND_HALF_UP)
    for row in rows:
        row["percentage_target_cif"] = (
            target_pool - fixed_target_cif if row is balancing
            else (row["percentage_target_qty"] * row["configured_max_unit_price"]).quantize(CIF, rounding=ROUND_HALF_UP)
        )
        row["audit_remaining_qty"] = row["percentage_target_qty"] - row["actual_used_qty"]
        row["audit_remaining_cif"] = row["percentage_target_cif"] - row["actual_used_cif"]
        row["own_excess_qty"] = max(-row["audit_remaining_qty"], ZERO)
        row["own_excess_cif"] = max(-row["audit_remaining_cif"], ZERO)
        row["excess_other_item_qty"] = ZERO
        row["excess_other_item_cif"] = ZERO
    # Every over-utilised member transfers its excess to the highest-rate
    # eligible recipient; ties follow saved member sequence.  This is a
    # quantity reconciliation, not a new-plan allocation.
    for donor in sorted(rows, key=lambda row: int(row.get("member_sequence", 0))):
        if donor["own_excess_qty"] <= ZERO and donor["own_excess_cif"] <= ZERO:
            continue
        recipients = sorted(
            [row for row in rows if row is not donor and row["audit_remaining_qty"] > ZERO],
            key=lambda row: (-row["configured_max_unit_price"], int(row.get("member_sequence", 0))),
        )
        for recipient in recipients:
            transfer_qty = min(donor["own_excess_qty"], max(recipient["audit_remaining_qty"] - recipient["excess_other_item_qty"], ZERO))
            # CIF transfer follows the same donor excess exactly once; no
            # price conversion can manufacture or lose historical CIF.
            transfer_cif = min(donor["own_excess_cif"], max(recipient["audit_remaining_cif"] - recipient["excess_other_item_cif"], ZERO))
            recipient["excess_other_item_qty"] += transfer_qty
            recipient["excess_other_item_cif"] += transfer_cif
            donor["own_excess_qty"] -= transfer_qty
            donor["own_excess_cif"] -= transfer_cif
            if donor["own_excess_qty"] <= ZERO and donor["own_excess_cif"] <= ZERO:
                break
    capacity = Decimal(str(group_available_qty)) if group_available_qty is not None else None
    for row in sorted(rows, key=lambda entry: int(entry.get("member_sequence", 0))):
        row["remaining_qty"] = max(row["audit_remaining_qty"] - row["excess_other_item_qty"], ZERO)
        row["target_remaining_cif"] = max(row["audit_remaining_cif"] - row["excess_other_item_cif"], ZERO)
        if capacity is not None:
            row["remaining_qty"] = min(row["remaining_qty"], max(capacity, ZERO))
            capacity -= row["remaining_qty"]
    fixed_cif = sum((row["remaining_qty"] * row["configured_max_unit_price"] for row in rows if row is not balancing), ZERO).quantize(CIF, rounding=ROUND_HALF_UP)
    balance_cap = min(balancing["target_remaining_cif"], max(available - fixed_cif, ZERO))
    residual = min(balance_cap, (balancing["remaining_qty"] * balancing["configured_max_unit_price"]).quantize(CIF, rounding=ROUND_HALF_UP))
    effective_rate = residual / balancing["remaining_qty"] if balancing["remaining_qty"] > ZERO else ZERO
    for row in rows:
        row["remaining_cif"] = residual.quantize(CIF, rounding=ROUND_HALF_UP) if row is balancing else (row["remaining_qty"] * row["configured_max_unit_price"]).quantize(CIF, rounding=ROUND_HALF_UP)
        row["effective_unit_price"] = effective_rate if row is balancing else row["configured_max_unit_price"]
    planned_cif = sum((row["remaining_cif"] for row in rows), ZERO)
    return {"members": rows, "group_available_cif": available,
            "new_planned_cif": planned_cif,
            "unallocated_cif": max(available - planned_cif, ZERO)}
