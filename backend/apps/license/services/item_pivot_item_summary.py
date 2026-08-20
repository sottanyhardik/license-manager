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


def project_item_summary(licenses):
    """Aggregate canonical matrix cells by canonical item identity plus SION.

    ``licenses`` is intentionally a list of already filtered matrix licences;
    no query, plan calculation, or name-based matching happens here.
    """
    buckets = {}
    for license_row in licenses:
        for item_key, cell in (license_row.get("items") or {}).items():
            canonical_id = cell.get("canonical_item_id")
            sion = cell.get("sion") or ""
            key = (canonical_id, sion)
            bucket = buckets.setdefault(key, {
                "canonical_item_id": canonical_id, "item_name": cell.get("item_name") or item_key,
                "sion": sion, "hsn_codes": set(), "license_ids": set(), "affected_license_ids": set(),
                **{field: ZERO_QTY for field in QTY_FIELDS}, **{field: ZERO_CIF for field in CIF_FIELDS},
                "exception_count": 0, "has_item_cif_cap": False,
            })
            bucket["license_ids"].add(license_row.get("license_id"))
            bucket["has_item_cif_cap"] = bucket["has_item_cif_cap"] or bool(cell.get("has_item_cif_cap"))
            bucket["hsn_codes"].update(filter(None, [cell.get("hsn_code")]))
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
            over_utilized_qty = max(actual_qty - total, ZERO_QTY)
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
        row = {
            "canonical_item_id": bucket["canonical_item_id"], "item_name": bucket["item_name"],
            "sion": bucket["sion"], "hsn_codes": sorted(bucket["hsn_codes"]),
            "license_count": len(bucket["license_ids"] - {None}),
            **{field: _out(bucket[field], Decimal("0.000")) for field in QTY_FIELDS},
            **{field: _out(bucket[field], Decimal("0.00")) for field in CIF_FIELDS},
            "average_unit_price": _out(planned_cif / planned_qty if planned_qty > ZERO_QTY else ZERO_CIF, Decimal("0.00")),
            "exception_count": bucket["exception_count"],
            "affected_license_ids": sorted(value for value in bucket["affected_license_ids"] if value is not None),
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
    rows.sort(key=lambda row: (row["sion"], row["item_name"], row["canonical_item_id"] or -1))
    totals = {field: sum((_d(row[field]) for row in rows), ZERO_QTY if field in QTY_FIELDS else ZERO_CIF) for field in QTY_FIELDS + CIF_FIELDS}
    totals = {field: _out(value, Decimal("0.000") if field in QTY_FIELDS else Decimal("0.00")) for field, value in totals.items()}
    total_qty, total_cif = _d(totals["planned_qty"]), _d(totals["planned_cif"])
    totals.update({"license_count": len({lic.get("license_id") for lic in licenses}), "item_count": len(rows),
                   "weighted_average_unit_price": _out(total_cif / total_qty if total_qty > ZERO_QTY else ZERO_CIF, Decimal("0.00"))})
    return {"item_summary": rows, "item_summary_totals": totals}
