"""
License Purchase & Profit Report — service layer.

Reconciles two sides of a license's lifecycle that today live in separate
tables and are never combined in a single report:

- **Purchase Cost** (what it cost to *acquire* the license) —
  `LicensePurchase.amount_inr`, consolidated across every supplier invoice
  ever recorded against the license. NOT date-filtered: buying the license
  is a one-time event, so every invoice counts regardless of the report's
  date range (see module docstring rationale in the approved plan).
- **Debited CIF** (what CIF value was actually *used*) —
  `RowDetails.cif_fc` for DEBIT rows within `[from_date, to_date]`, with
  hidden (previous-owner) BOE rows excluded via `exclude_hidden()`. This is
  the same "Debited CIF" figure already used by Item Pivot / Financial
  Ledger, so this report's numbers stay consistent with the rest of the app.

Everything here is bulk (`.values().annotate()` aggregation + the balance
calculator's own `_for_licenses` bulk helpers) — never a per-license loop
that hits the DB, however many licenses match the filters.

Rounding: item-wise `allocated_purchase` is computed proportionally for
every import item on a license EXCEPT the one with the largest debited CIF
(ties broken by item id) — that item absorbs
`purchase_cost - sum(other items' allocated amounts)`, guaranteeing item
allocations sum EXACTLY to the license's `allocated_purchase` (which is
always the license's full `purchase_cost`, since every item's share was
allocated) at the paisa level, not just approximately.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.constants import DEBIT, DEC_0, DEC_000
from apps.bill_of_entry.models import RowDetails
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.models.core import LicensePurchase
from apps.license.services.balance_calculator import LicenseBalanceCalculator, exclude_hidden

# Mirrors the frontend's `NormCardGrid.tsx:22` convention — the four DFIA
# conversion norms that get their own dedicated section; anything else with
# a norm_class falls into "Others". Licenses with NO norm_class at all
# (Incentive-scheme licenses) are out of scope for this report entirely.
CONVERSION_NORMS = {"E1", "E5", "E126", "E132"}
OTHERS = "Others"
NORM_DISPLAY_ORDER = ["E1", "E5", "E126", "E132", OTHERS]

TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")
HUNDRED = Decimal("100")


def _q2(value) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _q3(value) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(THREE_PLACES, rounding=ROUND_HALF_UP)


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if not denominator:
        return DEC_0
    return _q2((numerator / denominator) * HUNDRED)


def _empty_report() -> Dict[str, Any]:
    return {
        "norms": [],
        "grand_summary": {
            "rows": [],
            "total": {"purchase": 0.0, "debited_cif": 0.0, "profit": 0.0, "margin_pct": 0.0},
        },
    }


def _as_list(value) -> Optional[List]:
    """
    Normalize a filter value that may arrive as a single scalar (existing
    single-select call sites) or a list/tuple/set (multi-select call sites)
    into `Optional[List]` — `None`/`""` stays `None` (no filter), a bare
    scalar becomes a one-item list, a collection passes through unchanged
    (falsy entries stripped).
    """
    if value is None or value == "":
        return None
    if isinstance(value, (list, tuple, set)):
        cleaned = [v for v in value if v not in (None, "")]
        return cleaned or None
    return [value]


def _normalize_norm_selection(norm) -> tuple:
    """
    Returns `(is_all, norm_buckets)`. `is_all=True` means no norm
    restriction at all (norm was falsy/"All"/absent, or the multi-select
    included "All"), matching the historical single-value "All" behaviour.
    Otherwise `norm_buckets` is the set of selected bucket names, each
    either a `CONVERSION_NORMS` code or `OTHERS`.
    """
    values = _as_list(norm) or []
    if not values or "All" in values:
        return True, set()
    return False, set(values)


def _base_license_queryset(
    norm,
    license_number,
    exporter_id,
    exclude_license_numbers=None,
):
    """
    `norm`, `license_number`, `exporter_id` each accept either a single
    scalar (original single-select contract, unchanged behaviour) or a
    list of scalars (multi-select contract used by
    `trading_register_report.py`). `exclude_license_numbers` is multi-select
    only — always an exact `__in` exclude, applied last so it wins over an
    overlapping `license_number` inclusion.
    """
    qs = LicenseDetailsModel.objects.all()

    exporter_ids = _as_list(exporter_id)
    if exporter_ids:
        qs = qs.filter(exporter_id__in=exporter_ids)

    license_numbers = _as_list(license_number)
    if license_numbers:
        if len(license_numbers) == 1:
            # Single value preserves the original "search box" contains
            # semantics; 2+ values is a multi-select of exact numbers.
            qs = qs.filter(license_number__icontains=license_numbers[0])
        else:
            qs = qs.filter(license_number__in=license_numbers)

    exclude_numbers = _as_list(exclude_license_numbers)
    if exclude_numbers:
        qs = qs.exclude(license_number__in=exclude_numbers)

    is_all, norm_buckets = _normalize_norm_selection(norm)
    if is_all:
        # "All" (default) and any unrecognized value collapse to "All"
        # semantics: still requires SOME norm class — licenses with no norm
        # class at all are out of scope for this report per the plan.
        qs = qs.filter(export_license__norm_class__isnull=False)
    else:
        conversion_selected = norm_buckets & CONVERSION_NORMS
        others_selected = OTHERS in norm_buckets
        # Each bucket's qualifying pk set is computed against its own
        # `.filter()`/`.exclude()` chain off `qs` (never combined into one
        # `Q` expression): "Others" specifically needs `.exclude()`'s
        # NOT-EXISTS semantics ("this license has NO conversion-norm export
        # item at all") which a `~Q(...)` join can't reproduce — `~Q` only
        # excludes the individual joined row, so a license with BOTH an E1
        # and an "Others" export item would wrongly re-qualify for
        # "Others" via its non-E1 row. Union the pk sets in Python instead.
        candidate_pks = set()
        if conversion_selected:
            candidate_pks |= set(
                qs.filter(export_license__norm_class__norm_class__in=conversion_selected)
                .values_list("pk", flat=True)
            )
        if others_selected:
            candidate_pks |= set(
                qs.filter(export_license__norm_class__isnull=False)
                .exclude(export_license__norm_class__norm_class__in=CONVERSION_NORMS)
                .values_list("pk", flat=True)
            )
        qs = qs.filter(pk__in=candidate_pks) if (conversion_selected or others_selected) else qs.none()

    # export_license is a reverse FK (one license -> many export items),
    # so the norm-class filters above can multiply-join; distinct() collapses back to one row per license.
    return qs.distinct()


def _norm_by_license(license_ids: List[int], norm) -> Dict[int, str]:
    """
    Norm bucket per license, bulk (not per-license).

    When `norm` names exactly ONE specific bucket (a conversion norm or
    "Others"), every id in `license_ids` already satisfies that filter via
    `_base_license_queryset` — bucket it there directly rather than
    re-deriving a "representative" norm from an unordered multi-row query,
    which could pick a *different* norm_class than the one that matched the
    filter for a license with more than one export-item norm_class.

    For "All", or a multi-select of 2+ buckets, a license can still carry
    multiple distinct norm_class values across its export items (possibly
    across more buckets than were selected); pick deterministically by
    `NORM_DISPLAY_ORDER` precedence — restricted to the selected buckets
    when this is a multi-select rather than "All" — so the choice doesn't
    depend on undefined DB row order.
    """
    is_all, norm_buckets = _normalize_norm_selection(norm)
    if not is_all and len(norm_buckets) == 1:
        (only_bucket,) = norm_buckets
        return {lid: only_bucket for lid in license_ids}

    norm_values_by_license: Dict[int, set] = defaultdict(set)
    for row in (
        LicenseDetailsModel.objects.filter(id__in=license_ids)
        .values("id", "export_license__norm_class__norm_class")
        .distinct()
    ):
        value = row["export_license__norm_class__norm_class"]
        if value is not None:
            norm_values_by_license[row["id"]].add(value)

    allowed_order = NORM_DISPLAY_ORDER if is_all else [n for n in NORM_DISPLAY_ORDER if n in norm_buckets]

    result: Dict[int, str] = {}
    for lid, values in norm_values_by_license.items():
        bucketed = {v if v in CONVERSION_NORMS else OTHERS for v in values}
        for candidate in allowed_order:
            if candidate in bucketed:
                result[lid] = candidate
                break
    return result


def build_purchase_profit_report(
    from_date,
    to_date,
    norm: str = "All",
    license_number: Optional[str] = None,
    exporter_id: Optional[int] = None,
) -> Dict[str, Any]:
    base_qs = _base_license_queryset(norm, license_number, exporter_id)
    base_license_ids = list(base_qs.values_list("id", flat=True))
    if not base_license_ids:
        return _empty_report()

    debit_qs = exclude_hidden(
        RowDetails.objects.filter(
            sr_number__license_id__in=base_license_ids,
            transaction_type=DEBIT,
            bill_of_entry__bill_of_entry_date__range=(from_date, to_date),
        )
    )

    license_ids = list(
        debit_qs.values_list("sr_number__license_id", flat=True).distinct()
    )
    if not license_ids:
        return _empty_report()

    # --- Bulk aggregations (no N+1) -----------------------------------
    total_debited_by_license: Dict[int, Decimal] = {
        row["sr_number__license_id"]: row["total"]
        for row in debit_qs.values("sr_number__license_id").annotate(
            total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
        )
    }

    items_by_license: Dict[int, List[dict]] = defaultdict(list)
    for row in debit_qs.values("sr_number__license_id", "sr_number_id").annotate(
        cif=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
        qty=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()),
    ):
        items_by_license[row["sr_number__license_id"]].append(row)

    purchase_cost_by_license: Dict[int, Decimal] = {
        row["license_id"]: row["total"]
        for row in LicensePurchase.objects.filter(license_id__in=license_ids)
        .values("license_id")
        .annotate(total=Coalesce(Sum("amount_inr"), Value(DEC_0), output_field=DecimalField()))
    }

    remaining_cif_by_license: Dict[int, Decimal] = LicenseBalanceCalculator.calculate_balance_for_licenses(
        license_ids
    )

    norm_by_license = _norm_by_license(license_ids, norm)

    # License metadata (number, exporter name) in one query.
    license_lookup = {
        lic.id: lic
        for lic in LicenseDetailsModel.objects.filter(id__in=license_ids).select_related("exporter")
    }

    # Item labels — one bulk fetch + prefetch, mirroring item_pivot_report.py's
    # "names joined, falling back to description" convention.
    import_item_ids = {row["sr_number_id"] for items in items_by_license.values() for row in items}
    import_item_lookup = {
        ii.id: ii
        for ii in LicenseImportItemsModel.objects.filter(id__in=import_item_ids).prefetch_related("items")
    }

    def _item_label(import_item_id: int) -> str:
        ii = import_item_lookup.get(import_item_id)
        if ii is None:
            return "-"
        names = [n.name for n in ii.items.all()]
        return ", ".join(names) if names else (ii.description or "-")

    # --- Assemble per-license rows -------------------------------------
    licenses_by_norm: Dict[str, List[dict]] = defaultdict(list)
    items_by_norm: Dict[str, List[dict]] = defaultdict(list)
    # Decimal accumulators per norm bucket — summed directly from the
    # source Decimal values (never reconstructed from already-serialized
    # floats), so norm/grand summaries can't drift from float round-tripping.
    norm_totals: Dict[str, Dict[str, Decimal]] = defaultdict(
        lambda: {"purchase": DEC_0, "debited_cif": DEC_0, "profit": DEC_0}
    )

    for license_id in license_ids:
        total_debited = total_debited_by_license.get(license_id, DEC_0)
        if not total_debited:
            # Guard div-by-zero defensively — shouldn't happen given the
            # license_ids filter above (every id there has >=1 debit row),
            # but a license should never appear with a zero Debited CIF.
            continue

        purchase_cost = purchase_cost_by_license.get(license_id, DEC_0)
        remaining_cif = remaining_cif_by_license.get(license_id, DEC_0)
        norm_bucket = norm_by_license.get(license_id, OTHERS)
        lic = license_lookup.get(license_id)
        license_number_val = lic.license_number if lic else ""
        exporter_name = (lic.exporter.name if lic and lic.exporter_id else "") or ""

        item_rows = items_by_license.get(license_id, [])
        # Largest debited-CIF item absorbs the rounding remainder; every
        # other item gets its exact proportional share.
        sorted_items = sorted(item_rows, key=lambda r: (-r["cif"], r["sr_number_id"]))
        largest = sorted_items[0]
        others = sorted_items[1:]

        other_allocated_sum = DEC_0
        item_output_rows = []
        for row in others:
            alloc = _q2(purchase_cost * (row["cif"] / total_debited))
            other_allocated_sum += alloc
            item_output_rows.append((row, alloc))

        largest_alloc = _q2(purchase_cost - other_allocated_sum)
        item_output_rows.append((largest, largest_alloc))

        allocated_purchase = _q2(purchase_cost)  # every item's share sums to this, by construction
        total_debited_q2 = _q2(total_debited)
        realized_profit = _q2(total_debited_q2 - allocated_purchase)
        profit_pct = _pct(realized_profit, purchase_cost)

        totals = norm_totals[norm_bucket]
        totals["purchase"] += allocated_purchase
        totals["debited_cif"] += total_debited_q2
        totals["profit"] += realized_profit

        licenses_by_norm[norm_bucket].append(
            {
                "license_id": license_id,
                "license_number": license_number_val,
                "exporter": exporter_name,
                "purchase_cost": float(allocated_purchase),
                "debited_cif": float(total_debited_q2),
                "remaining_cif": float(_q2(remaining_cif)),
                "allocated_purchase": float(allocated_purchase),
                "realized_profit": float(realized_profit),
                "profit_pct": float(profit_pct),
            }
        )

        for row, alloc in item_output_rows:
            item_cif = _q2(row["cif"])
            item_profit = _q2(item_cif - alloc)
            pct_share = _pct(row["cif"], total_debited)
            items_by_norm[norm_bucket].append(
                {
                    "license_id": license_id,
                    "license_number": license_number_val,
                    "item": _item_label(row["sr_number_id"]),
                    "qty_debited": float(_q3(row["qty"])),
                    "debited_cif": float(item_cif),
                    "pct_share": float(pct_share),
                    "allocated_purchase": float(_q2(alloc)),
                    "profit": float(item_profit),
                }
            )

    if not licenses_by_norm:
        return _empty_report()

    # --- Per-norm summaries + grand summary -----------------------------
    present_norms = [n for n in NORM_DISPLAY_ORDER if n in licenses_by_norm]
    # Any bucket not in the fixed display order (shouldn't happen) still
    # gets included, appended after the known ones.
    present_norms += [n for n in licenses_by_norm if n not in present_norms]

    norms_output = []
    grand_purchase = DEC_0
    grand_debited = DEC_0
    grand_profit = DEC_0
    grand_rows = []

    for norm_bucket in present_norms:
        lic_rows = sorted(licenses_by_norm[norm_bucket], key=lambda r: r["license_number"])
        item_rows_out = sorted(
            items_by_norm[norm_bucket], key=lambda r: (r["license_number"], -r["debited_cif"])
        )

        totals = norm_totals[norm_bucket]
        total_purchase = totals["purchase"]
        total_debited_cif = totals["debited_cif"]
        total_profit = totals["profit"]
        margin_pct = _pct(total_profit, total_purchase)

        norms_output.append(
            {
                "norm": norm_bucket,
                "licenses": lic_rows,
                "items": item_rows_out,
                "summary": {
                    "total_purchase": float(total_purchase),
                    "total_debited_cif": float(total_debited_cif),
                    "total_profit": float(total_profit),
                    "margin_pct": float(margin_pct),
                },
            }
        )

        grand_purchase += total_purchase
        grand_debited += total_debited_cif
        grand_profit += total_profit
        grand_rows.append(
            {
                "norm": norm_bucket,
                "purchase": float(total_purchase),
                "debited_cif": float(total_debited_cif),
                "profit": float(total_profit),
                "margin_pct": float(margin_pct),
            }
        )

    grand_margin_pct = _pct(grand_profit, grand_purchase)

    return {
        "norms": norms_output,
        "grand_summary": {
            "rows": grand_rows,
            "total": {
                "purchase": float(grand_purchase),
                "debited_cif": float(grand_debited),
                "profit": float(grand_profit),
                "margin_pct": float(grand_margin_pct),
            },
        },
    }
