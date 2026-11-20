"""Read-only Item Pivot item-summary projection.

The input is the canonical Licence Matrix DTO produced by ``ItemPivotService``.
Keeping this deliberately small and pure prevents the summary, exports and UI
from acquiring a second planning/reconciliation implementation.
"""
from decimal import Decimal, ROUND_HALF_UP

ZERO_QTY = Decimal("0.000")
ZERO_CIF = Decimal("0.00")
PLANNING_QTY_TOLERANCE = Decimal("10.000")
QTY_FIELDS = ("total_qty", "boe_used_qty", "allotted_qty", "actual_used_qty", "available_qty", "planned_qty", "balance_qty", "over_utilized_qty", "over_planned_qty")
CIF_FIELDS = ("boe_used_cif", "allotted_cif", "actual_used_cif", "available_cif", "planned_cif", "balance_cif", "over_utilized_cif", "over_planned_cif")


def _d(value, default=Decimal("0")):
    return Decimal(str(value if value is not None else default))


def decimal_or_zero(value, zero):
    return zero if value is None or value == "" else Decimal(str(value))


def determine_planning_status(*, planned_qty, available_qty, over_utilized_qty,
                              over_utilized_cif, over_planned_qty, over_planned_cif):
    if over_utilized_qty > ZERO_QTY or over_utilized_cif > ZERO_CIF:
        return "over_utilized"
    if over_planned_qty > ZERO_QTY or over_planned_cif > ZERO_CIF:
        return "over_planned"
    remaining_qty = max(available_qty - planned_qty, ZERO_QTY)
    if planned_qty > ZERO_QTY and remaining_qty <= PLANNING_QTY_TOLERANCE:
        return "planned"
    if planned_qty > ZERO_QTY:
        return "partially_planned"
    return "not_planned"


def _out(value, places):
    return str(_d(value).quantize(places, rounding=ROUND_HALF_UP))


def _unit_price(balance_cif, balance_qty):
    """Balance CIF / balance QTY to two decimals; None when no quantity is left."""
    return _out(balance_cif / balance_qty, Decimal("0.01")) if balance_qty > ZERO_QTY else None


NO_ITEM_NAME_CATEGORY = "NOT ATTRIBUTED (NO ITEM NAME)"
_CAP_FIELDS = ("has_item_cif_cap", "available_cif", "over_utilized_cif", "over_planned_cif", "balance_cif", "balance_qty")


def _used_cif(source):
    """BOE-used + allotted + billed CIF of a cell / identity part (the components that reduce the item CIF balance)."""
    return sum((_d(source.get(field)) for field in ("boe_used_cif", "allotted_cif", "billed_cif")), ZERO_CIF)


def piece_identity_key(piece):
    """Identity of a piece: canonical Item Name x SION, or its own NOT ATTRIBUTED / no-Item-Name row. The string form is the
    stable product key of the product-wise Item Report."""
    canonical_id, sion = piece.get("canonical_item_id"), piece.get("sion") or ""
    if piece.get("unattributed"):
        return ("unattributed", sion)
    return ("no_item_name", sion) if canonical_id is None else (canonical_id, sion)


def identity_key_text(key):
    return f"{key[0]}:{key[1]}"


def _identity_pieces(cell):
    """The cell's contributions by canonical identity. A cell of one identity is used exactly as the matrix computed it;
    a category cell that merged several identities is split into its identity parts (the parts sum to the cell). Item
    CIF caps belong to the cell's own planned identity, never to the other merged sources."""
    parts = cell.get("identity_parts") or []
    if len(parts) <= 1:
        part = parts[0] if parts else {}
        piece = dict(cell)
        piece["capacity_balance_cif"] = None if cell.get("unattributed") else str(max(_d(cell.get("canonical_item_cif_capacity")) - _used_cif(cell), ZERO_CIF))
        if parts:
            piece.update({"canonical_item_id": part.get("canonical_item_id"), "item_name": part.get("item_name") or cell.get("item_name"),
                          "identity_reason": part.get("reason"), "hsn_codes": part.get("hsn_codes"), "identity_sources": part.get("source_items", [])})
        return [piece]
    # Shared entitlement: a part merged onto sources another part already holds carries usage but no entitlement. Its
    # usage consumes the holder's entitlement (pooled), so the parts' availability sums to the cell's and the
    # zero-entitlement part is never flagged as over-using an entitlement it does not have.
    def sources(part):
        return {row.get("import_item_id") for row in part.get("source_items", [])}

    def used_of(part):
        return sum((_d(part.get(f)) for f in ("debited_qty", "allotted_qty", "billed_qty")), ZERO_QTY)

    def adjusted_of(part):
        return _d(part.get("adjusted_total_qty", part.get("total_qty")))

    net = [adjusted_of(part) - used_of(part) for part in parts]
    # Item CIF capacity pools the same way as quantity: a zero-entitlement part's used CIF reduces its holder's balance.
    net_cif = [_d(part.get("canonical_item_cif_capacity")) - _used_cif(part) for part in parts]
    pooled_into = {}
    for index, part in enumerate(parts):
        if adjusted_of(part) == ZERO_QTY and used_of(part) > ZERO_QTY:
            holder = next((j for j, other in enumerate(parts) if j != index and adjusted_of(other) > ZERO_QTY and sources(other) & sources(part)), None)
            if holder is not None:
                net[holder] -= used_of(part)
                net[index] = ZERO_QTY
                net_cif[holder] -= _used_cif(part)
                net_cif[index] = ZERO_CIF
                pooled_into[index] = holder
    pieces, cap_owner_used = [], False
    for index, part in enumerate(parts):
        piece = {**part, "identity_reason": part.get("reason"), "identity_sources": part.get("source_items", []),
                 "available_qty": str(max(net[index], ZERO_QTY)), "pooled_over_utilized_qty": str(max(-net[index], ZERO_QTY)),
                 "capacity_balance_cif": str(max(net_cif[index], ZERO_CIF)),
                 "has_item_cif_cap": False}
        if not cap_owner_used and cell.get("has_item_cif_cap") and part.get("canonical_item_id") == cell.get("canonical_item_id"):
            piece.update({field: cell.get(field) for field in _CAP_FIELDS})
            cap_owner_used = True
        pieces.append(piece)
    return pieces


def project_item_summary(licenses):
    """Aggregate canonical matrix cells by canonical item identity plus SION.

    ``licenses`` is intentionally a list of already filtered matrix licences;
    no query, plan calculation, or name-based matching happens here.
    """
    buckets = {}
    for license_row in licenses:
        pieces = ((item_key, piece) for item_key, whole_cell in (license_row.get("items") or {}).items() for piece in _identity_pieces(whole_cell))
        for item_key, cell in pieces:
            canonical_id = cell.get("canonical_item_id")
            sion = cell.get("sion") or ""
            # Identity = canonical Item Name × SION. NOT ATTRIBUTED usage, and sources with no single Item Name, are their
            # own rows — never merged into an item, and the no-Item-Name sources are never merged with each other by name.
            no_item_name = not cell.get("unattributed") and canonical_id is None
            key = piece_identity_key(cell)
            bucket = buckets.setdefault(key, {
                "canonical_item_id": canonical_id, "identity": key,
                "item_name": NO_ITEM_NAME_CATEGORY if no_item_name else cell.get("item_name") or item_key,
                "product_category": NO_ITEM_NAME_CATEGORY if no_item_name else cell.get("product_category"),
                "sion": sion, "hsn_codes": set(), "license_ids": set(), "affected_license_ids": set(),
                **{field: ZERO_QTY for field in QTY_FIELDS}, **{field: ZERO_CIF for field in CIF_FIELDS},
                "exception_count": 0, "has_item_cif_cap": False,
                "billed_qty": ZERO_QTY, "billed_cif": ZERO_CIF, "item_total_cif": None, "capacity_balance_cif": None, "is_planned": False,
                "priority_candidates": [], "unit_balance_cif": ZERO_CIF, "unit_balance_qty": ZERO_QTY,
                "source_records": [] if no_item_name or cell.get("unattributed") else None, "units": set(),
            })
            # Quantity units of the identity's own source rows: quantities are only added when they share a unit; a
            # mixed row is flagged (no conversion factor is applied or assumed).
            bucket["units"].update(src.get("unit") for src in (cell.get("identity_sources") or cell.get("source_items") or []) if src.get("unit"))
            if no_item_name:
                bucket["source_records"].extend(
                    {"license_id": license_row.get("license_id"), "license_number": license_row.get("license_number"),
                     "reason": cell.get("identity_reason") or "no_item_name", "matrix_key": item_key, "description": cell.get("item_name"), **source}
                    for source in cell.get("identity_sources") or [])
            elif cell.get("unattributed"):
                # TARGET MISSING usage keeps its per-transaction records (BOE / allotment / billed) with licence provenance,
                # so the summary row is traceable exactly like the licence cell it aggregates. Display only.
                bucket["source_records"].extend(
                    {"license_id": license_row.get("license_id"), "license_number": license_row.get("license_number"), **record}
                    for record in cell.get("unattributed_records") or [])
            bucket["license_ids"].add(license_row.get("license_id"))
            # Additive product-report figures. Billed-without-BOE is carried on every cell; item CIF (total / balance) exists
            # only where the engine has it — NOT ATTRIBUTED usage has none (stays None: missing, not 0).
            bucket["billed_qty"] += max(_d(cell.get("billed_qty")), ZERO_QTY)
            bucket["billed_cif"] += max(_d(cell.get("billed_cif")), ZERO_CIF)
            if not cell.get("unattributed"):
                bucket["item_total_cif"] = (bucket["item_total_cif"] or ZERO_CIF) + _d(cell.get("item_total_cif", cell.get("canonical_item_cif_capacity")))
                bucket["capacity_balance_cif"] = (bucket["capacity_balance_cif"] or ZERO_CIF) + _d(cell.get("capacity_balance_cif"))
                bucket["is_planned"] = bucket["is_planned"] or cell.get("priority_source") not in ("unplanned", "unattributed", None)
            bucket["has_item_cif_cap"] = bucket["has_item_cif_cap"] or bool(cell.get("has_item_cif_cap"))
            # RUTILE is the only block with a unit price (matrix balance CIF / balance QTY).
            if cell.get("product_category") == "RUTILE":
                bucket["unit_balance_cif"] += max(_d(cell.get("balance_cif")), ZERO_CIF)
                bucket["unit_balance_qty"] += max(_d(cell.get("balance_qty")), ZERO_QTY)
            priority = cell.get("planning_priority")
            if priority is not None:
                bucket["priority_candidates"].append((
                    int(priority),
                    int(cell.get("priority_item_order") if cell.get("priority_item_order") is not None else 999999),
                    cell.get("planning_rule_id"), cell.get("planning_rule_name"),
                    cell.get("planning_strategy"), cell.get("priority_source") or "active_sion_rule",
                ))
            # HSN codes of this identity's own source rows only (never a merged cell's joined string).
            bucket["hsn_codes"].update(cell["hsn_codes"] if cell.get("hsn_codes") is not None else
                                       [hs.strip() for hs in str(cell.get("hsn_code") or "").split(",") if hs.strip()])
            total = max(_d(cell.get("adjusted_total_qty", cell.get("total_qty"))), ZERO_QTY)
            boe_qty, allot_qty = max(_d(cell.get("debited_qty")), ZERO_QTY), max(_d(cell.get("allotted_qty")), ZERO_QTY)
            boe_cif, allot_cif = max(_d(cell.get("boe_used_cif")), ZERO_CIF), max(_d(cell.get("allotted_cif")), ZERO_CIF)
            actual_qty, actual_cif = max(boe_qty + allot_qty, ZERO_QTY), max(boe_cif + allot_cif, ZERO_CIF)
            # An item CIF position exists only when canonical planning supplied
            # an explicit hard item cap.  The licence's shared CIF balance is
            # not an item cap and must never be projected as one here.
            has_item_cif_cap = bool(cell.get("has_item_cif_cap"))
            available_qty = max(_d(cell.get("available_qty", total - actual_qty)), ZERO_QTY)
            available_cif = max(_d(cell.get("available_cif")), ZERO_CIF) if has_item_cif_cap else ZERO_CIF
            planned_qty = max(_d(cell.get("effective_planned_qty", cell.get("plan_qty"))), ZERO_QTY)
            planned_cif = max(_d(cell.get("effective_planned_cif", cell.get("planned_cif"))), ZERO_CIF)
            # NOT ATTRIBUTED usage has no entitlement of its own — it is reported, not an item over-use.
            over_utilized_qty = (ZERO_QTY if cell.get("unattributed")
                                 else _d(cell["pooled_over_utilized_qty"]) if cell.get("pooled_over_utilized_qty") is not None
                                 else max(actual_qty - total, ZERO_QTY))
            # Reuse the matrix's canonical excess values.  In particular, do
            # not infer a capacity from a proportional display allocation.
            over_utilized_cif = max(_d(cell.get("over_utilized_cif")), ZERO_CIF) if has_item_cif_cap else ZERO_CIF
            values = {
                "total_qty": total, "boe_used_qty": boe_qty, "allotted_qty": allot_qty,
                "actual_used_qty": actual_qty, "available_qty": available_qty,
                "planned_qty": planned_qty, "balance_qty": max(available_qty - planned_qty, ZERO_QTY),
                "boe_used_cif": boe_cif, "allotted_cif": allot_cif,
                "actual_used_cif": actual_cif, "available_cif": available_cif,
                "planned_cif": planned_cif, "balance_cif": max(available_cif - planned_cif, ZERO_CIF),
                "over_utilized_qty": over_utilized_qty, "over_utilized_cif": over_utilized_cif,
                "over_planned_qty": max(planned_qty - available_qty, ZERO_QTY),
                "over_planned_cif": max(_d(cell.get("over_planned_cif")), ZERO_CIF) if has_item_cif_cap else ZERO_CIF,
            }
            for name, value in values.items():
                bucket[name] += value
            if any(values[name] > ZERO_QTY for name in ("over_utilized_qty", "over_planned_qty")) or any(values[name] > ZERO_CIF for name in ("over_utilized_cif", "over_planned_cif")):
                bucket["exception_count"] += 1
                bucket["affected_license_ids"].add(license_row.get("license_id"))

    rows = []
    for bucket in buckets.values():
        planned_qty, planned_cif = bucket["planned_qty"], bucket["planned_cif"]
        priority = min(
            bucket["priority_candidates"], key=lambda candidate: candidate[:2], default=None,
        )
        row = {
            "canonical_item_id": bucket["canonical_item_id"], "item_name": bucket["item_name"],
            "product_category": bucket["product_category"],
            "sion": bucket["sion"], "hsn_codes": sorted(bucket["hsn_codes"]),
            "license_count": len(bucket["license_ids"] - {None}),
            **{field: _out(bucket[field], Decimal("0.000")) for field in QTY_FIELDS},
            **{field: _out(bucket[field], Decimal("0.00")) for field in CIF_FIELDS},
            "average_unit_price": _out(planned_cif / planned_qty if planned_qty > ZERO_QTY else ZERO_CIF, Decimal("0.00")),
            "unit_price": _unit_price(bucket["unit_balance_cif"], bucket["unit_balance_qty"]),
            "exception_count": bucket["exception_count"],
            "affected_license_ids": sorted(value for value in bucket["affected_license_ids"] if value is not None),
            **({"source_records": bucket["source_records"]} if bucket["source_records"] is not None else {}),
            "units": sorted(bucket["units"]), "mixed_units": len(bucket["units"]) > 1,
            "identity_key": identity_key_text(bucket["identity"]),
            "billed_qty": _out(bucket["billed_qty"], Decimal("0.000")), "billed_cif": _out(bucket["billed_cif"], Decimal("0.00")),
            "item_total_cif": None if bucket["item_total_cif"] is None else _out(bucket["item_total_cif"], Decimal("0.00")),
            "capacity_balance_cif": None if bucket["capacity_balance_cif"] is None else _out(bucket["capacity_balance_cif"], Decimal("0.00")),
            "is_planned": bucket["is_planned"],
            "planning_priority": priority[0] if priority else None,
            "priority_item_order": priority[1] if priority else None,
            "planning_rule_id": priority[2] if priority else None,
            "planning_rule_name": priority[3] if priority else None,
            "planning_strategy": priority[4] if priority else None,
            "priority_source": priority[5] if priority else "unmatched",
        }
        if not bucket["has_item_cif_cap"]:
            row["available_cif"] = None
            row["balance_cif"] = None
        values = {name: _d(row[name]) for name in QTY_FIELDS + CIF_FIELDS}
        row["remaining_qty"] = _out(max(values["available_qty"] - values["planned_qty"], ZERO_QTY), Decimal("0.000"))
        row["remaining_cif"] = _out(max(values["available_cif"] - values["planned_cif"], ZERO_CIF), Decimal("0.00"))
        row["planning_qty_tolerance"] = _out(PLANNING_QTY_TOLERANCE, Decimal("0.000"))
        row["is_within_planning_tolerance"] = values["planned_qty"] > ZERO_QTY and _d(row["remaining_qty"]) <= PLANNING_QTY_TOLERANCE
        row["is_over_utilized"] = values["over_utilized_qty"] > ZERO_QTY or values["over_utilized_cif"] > ZERO_CIF
        row["is_over_planned"] = values["over_planned_qty"] > ZERO_QTY or values["over_planned_cif"] > ZERO_CIF
        row["status"] = determine_planning_status(planned_qty=values["planned_qty"], available_qty=values["available_qty"], over_utilized_qty=values["over_utilized_qty"], over_utilized_cif=values["over_utilized_cif"], over_planned_qty=values["over_planned_qty"], over_planned_cif=values["over_planned_cif"])
        rows.append(row)
    # API order is authoritative: active SION-rule priority, then configured
    # split-member order.  Unmatched rows intentionally follow all matched.
    rows.sort(key=lambda row: (
        row["sion"], row["planning_priority"] is None,
        row["planning_priority"] if row["planning_priority"] is not None else 999999,
        row["priority_item_order"] if row["priority_item_order"] is not None else 999999,
        (row["item_name"] or "").casefold(), row["canonical_item_id"] or -1,
    ))
    totals = {field: sum((_d(row[field]) for row in rows), ZERO_QTY if field in QTY_FIELDS else ZERO_CIF) for field in QTY_FIELDS + CIF_FIELDS}
    totals = {field: _out(value, Decimal("0.000") if field in QTY_FIELDS else Decimal("0.00")) for field, value in totals.items()}
    total_qty, total_cif = _d(totals["planned_qty"]), _d(totals["planned_cif"])
    totals["billed_qty"] = _out(sum((_d(row["billed_qty"]) for row in rows), ZERO_QTY), Decimal("0.000"))
    totals["billed_cif"] = _out(sum((_d(row["billed_cif"]) for row in rows), ZERO_CIF), Decimal("0.00"))
    for field in ("item_total_cif", "capacity_balance_cif"):  # None when no row has the figure (missing, not 0)
        present = [_d(row[field]) for row in rows if row[field] is not None]
        totals[field] = _out(sum(present, ZERO_CIF), Decimal("0.00")) if present else None
    totals.update({"license_count": len({lic.get("license_id") for lic in licenses}), "item_count": len(rows),
                   "weighted_average_unit_price": _out(total_cif / total_qty if total_qty > ZERO_QTY else ZERO_CIF, Decimal("0.00")),
                   "unit_price": _unit_price(sum((bucket["unit_balance_cif"] for bucket in buckets.values()), ZERO_CIF), sum((bucket["unit_balance_qty"] for bucket in buckets.values()), ZERO_QTY))})
    if not any(bucket["has_item_cif_cap"] for bucket in buckets.values()):
        totals["available_cif"] = None
        totals["balance_cif"] = None
    return {"item_summary": rows, "item_summary_totals": totals}
