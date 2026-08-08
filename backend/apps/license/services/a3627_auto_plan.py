"""
A3627 Auto-Plan service — Glass & Ceramic norm's RUTILE / TITANIUM DIOXIDE /
SODA ASH / PP priority waterfall.

Business rules (from the approved spec — see task history, not re-derived
here):

    Priority 1 — RUTILE:      unit price depends on the average IMPORT unit
                               price of the licence's own RUTILE items:
                                 avg <  USD 3.00 -> price = 2.50
                                 avg >= USD 3.00 -> price = 3.50
    Priority 2 — TITANIUM DIOXIDE: fixed price 2.00
    Priority 3 — SODA ASH:         fixed price 0.70
    Priority 4 — PP:               fixed price 1.20

Each priority allocates the MAX quantity affordable at its price from the
remaining Balance CIF, deducts that value, and passes whatever is left to
the next priority — the same "sequential value-consumption across fixed
price bands" shape as every other Auto-Plan engine (see e5_plan.py's
module docstring), just without E5's fractional-residual optimisation: at
each step the quantity is simply floored to a whole unit so
``planned_qty * price`` never exceeds the running balance (the exact same
floor-quantity / fixed-rate convention e5_auto_plan.py's ``floor_qty=True``
and e132_auto_plan.py's ``_floor_qty`` already use).

Architecture — mirrors e5_auto_plan.py / e132_auto_plan.py:
  1. ``ensure_plan_item_names`` — get-or-create the 4 planning item names
     (never fail Auto-Plan because a name row is missing).
  2. Load the licence's import items (select_related hs_code, prefetch
     items, ordered by serial_number).
  3. Classify each RAW import item into RUTILE / TITANIUM DIOXIDE /
     SODA ASH / PP by re-using ``item_matcher.get_item_filters()`` — the
     SAME Q-filter rules ``bulk_auto_link_license_items`` /
     ``match_import_item_to_items`` use to tag these exact categories for
     the A3627 norm. No new regex/HSN matching logic is written here; see
     ``_matched_ids_by_category``. Priority order (RUTILE > TITANIUM
     DIOXIDE > SODA ASH > PP) breaks any (unlikely) multi-category match,
     first-match-wins, same hierarchical-bucketing convention
     e5_auto_plan.py uses.
  4. Group each already-classified bucket via
     ``plan_grouping.merge_items_for_classification`` — the same canonical
     HSN + normalized-description grouping every Auto-Plan engine uses; one
     plan line per physical-product group, anchored on the group's lowest-
     serial representative.
  5. Run the 4-priority waterfall over the grouped buckets, in licence
     serial order within each bucket (business-significant only when a
     bucket's own affordable quantity runs out mid-bucket, across several
     groups of the same category).
  6. Validate each group's line with
     ``plan_grouping.validate_group_plan_lines`` (price-ceiling check) before
     accepting it — a fixed-price-per-run waterfall like this one fits that
     stricter validator (E126/E132's choice) better than E5's looser
     ``validate_fresh_plan_lines``: every line's price is one of exactly two
     known constants (RUTILE) or a single fixed constant (the other three),
     so a price ceiling is a meaningful, cheap safety net here, not a
     ceiling-map that "doesn't meaningfully exist" (see
     validate_fresh_plan_lines's own docstring for why E5 skips it).

IMPORTANT — average RUTILE import price is NOT
``LicenseDetailsModel.average_unit_price`` (apps/license/models/core.py).
That cached_property backs a *different*, pre-existing Glass-Formers/Borax
split report (its own hardcoded prices, its own Borax->SodaAsh->Rutile->
Titanium order) and is circular: its own ``cif_value_balance_glass['rutile']``
is itself ``rutile_qty * 3.5`` — a hardcoded constant, not a real weighted
average — so the property converges to ~3.5 whenever rutile_qty > 100 and
can never plausibly land at this task's avg=2.85 / avg=3.22 acceptance
scenarios. That property, ``get_glass_formers`` and
``cif_value_balance_glass`` are left byte-for-byte untouched; this module
computes its own genuine weighted average
(sum(cif_fc) / sum(quantity) across the licence's RAW RUTILE-classified
``LicenseImportItemsModel`` rows — the ORIGINAL import quantity/value, not
``available_quantity``/``available_value``, since "average import unit
price" means the price at which the goods were actually imported) — see
``_rutile_avg_import_price``.
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_FLOOR
from functools import reduce
from operator import or_
from typing import Optional

from apps.license.services.auto_plan_shared import ensure_plan_item_names as _ensure_names
from apps.license.services.plan_grouping import merge_items_for_classification, validate_group_plan_lines
from apps.license.utils.item_matcher import get_item_filters

logger = logging.getLogger(__name__)

NORM = "A3627"

# ── Planning item names — mirrors the naming convention already live in
# item_matcher.get_item_filters() (base_name + " - " + norm) and already
# referenced in production by item_pivot_report.py ("RUTILE - A3627"). ──────
RUTILE_NAME = "RUTILE - A3627"
TITANIUM_DIOXIDE_NAME = "TITANIUM DIOXIDE - A3627"
SODA_ASH_NAME = "SODA ASH - A3627"
PP_NAME = "PP - A3627"

_RULE_NAMES_A3627: tuple[tuple[str, str], ...] = (
    (RUTILE_NAME, NORM),
    (TITANIUM_DIOXIDE_NAME, NORM),
    (SODA_ASH_NAME, NORM),
    (PP_NAME, NORM),
)

# ── Fixed planning unit prices (USD). RUTILE has two — the run picks one
# based on _rutile_avg_import_price; both are exposed so the price-ceiling
# validator always has the right ceiling for whichever branch fired. ──────
RUTILE_PRICE_LOW = Decimal("2.50")
RUTILE_PRICE_HIGH = Decimal("3.50")
RUTILE_AVG_THRESHOLD = Decimal("3.00")  # avg < 3.00 -> LOW; avg >= 3.00 -> HIGH
TITANIUM_DIOXIDE_PRICE = Decimal("2.00")
SODA_ASH_PRICE = Decimal("0.70")
PP_PRICE = Decimal("1.20")

# Priority order — business-significant: RUTILE consumes the balance first,
# then TITANIUM DIOXIDE, then SODA ASH, then PP.
_CATEGORY_BASE_NAMES = ("RUTILE", "TITANIUM DIOXIDE", "SODA ASH", "PP")

_LABEL = {
    "RUTILE": "Priority 1 – Rutile",
    "TITANIUM DIOXIDE": "Priority 2 – Titanium Dioxide",
    "SODA ASH": "Priority 3 – Soda Ash",
    "PP": "Priority 4 – PP",
}


def _matched_ids_by_category(license_obj) -> dict[str, set[int]]:
    """Classify the licence's import items into A3627 categories using the
    EXISTING ``get_item_filters()`` Q-filter rules — the single source of
    truth for RUTILE/TITANIUM DIOXIDE/SODA ASH/PP detection (see
    ``item_matcher.py``). Runs one query per category (same batching style
    ``bulk_auto_link_license_items`` uses: ``combined_q = reduce(or_,
    filters)`` then a single ``.filter(combined_q)``), never a per-item
    query loop like ``match_import_item_to_items`` (that helper does a
    fresh queryset-existence check per item per filter — fine for its own
    one-item-at-a-time callers, but O(items x filters) queries here).

    Returns ``{base_name: {import_item_id, ...}}`` for the 4 base names this
    planner cares about; a base name with no matches on this licence is
    simply absent.
    """
    from apps.license.models import LicenseImportItemsModel

    out: dict[str, set[int]] = {}
    for cfg in get_item_filters():
        if cfg["base_name"] not in _CATEGORY_BASE_NAMES or NORM not in cfg["norms"]:
            continue
        combined_q = reduce(or_, cfg["filters"])
        ids = set(
            LicenseImportItemsModel.objects
            .filter(license=license_obj)
            .filter(combined_q)
            .values_list("id", flat=True)
        )
        if ids:
            out[cfg["base_name"]] = ids
    return out


def _rutile_avg_import_price(rutile_items) -> Decimal:
    """Genuine weighted average IMPORT unit price for a licence's RUTILE-
    classified rows: sum(cif_fc) / sum(quantity) — the ORIGINAL import
    quantity/value (``LicenseImportItemsModel.quantity`` / ``.cif_fc``), not
    the currently-remaining ``available_quantity``/``available_value``.
    Returns ``Decimal('0')`` when there is no quantity to average (no
    RUTILE items, or all zero-quantity) — the caller's threshold check then
    lands in the LOW branch, which is harmless since a category with zero
    available quantity never produces a plan line regardless of price.
    """
    total_qty = Decimal("0")
    total_cif = Decimal("0")
    for ii in rutile_items:
        total_qty += ii.quantity or Decimal("0")
        total_cif += ii.cif_fc or Decimal("0")
    if total_qty <= 0:
        return Decimal("0")
    return total_cif / total_qty


def _allocate_fixed_rate(qty: Decimal, price: Decimal, remaining: Decimal) -> tuple[Decimal, Decimal]:
    """One fixed-rate, floor-quantity allocation step — the price never
    moves; the quantity is floored to a whole unit so
    ``planned_qty * price`` never exceeds ``remaining`` (same convention as
    e5_auto_plan.py's ``floor_qty=True`` / e132_auto_plan.py's
    ``_floor_qty``, applied here so qty and CIF stay exactly consistent —
    unlike e132_plan.py's continuous-quantity ``_allocate_step``, which is
    designed for a different, reporting-parity use case).

    Returns ``(planned_qty, planned_cif)`` — both ``Decimal('0')`` when
    nothing can be planned.
    """
    if qty <= 0 or price <= 0 or remaining <= 0:
        return Decimal("0"), Decimal("0")
    raw_cif = qty * price
    capped_cif = raw_cif if raw_cif <= remaining else remaining
    planned_qty = (capped_cif / price).to_integral_value(rounding=ROUND_FLOOR)
    planned_cif = (planned_qty * price).quantize(Decimal("0.01"))
    if planned_qty <= 0 or planned_cif <= 0:
        return Decimal("0"), Decimal("0")
    return planned_qty, planned_cif


def compute_a3627_auto_plan(license_obj) -> tuple[list[dict], float]:
    """Run the full A3627 Auto Plan 4-priority waterfall.

    Returns (lines, remaining_cif).
    """
    # ── Get-or-create all planned item names (never fail on missing) ──────
    name_ids: dict[str, Optional[int]] = _ensure_names(list(_RULE_NAMES_A3627))

    # ── Load import items ──────────────────────────────────────────────────
    import_items = list(
        license_obj.import_license.all()
        .select_related("hs_code")
        .prefetch_related("items")
        .order_by("serial_number")
    )

    _live_balance_cif = license_obj.get_balance_cif
    remaining = Decimal(str(_live_balance_cif if _live_balance_cif is not None else (license_obj.balance_cif or 0)))

    # ── Classify raw items into the 4 categories (existing matcher rules,
    # priority order breaks any multi-category match) ─────────────────────
    matched_ids = _matched_ids_by_category(license_obj)
    buckets: dict[str, list] = {name: [] for name in _CATEGORY_BASE_NAMES}
    for ii in import_items:
        for base_name in _CATEGORY_BASE_NAMES:
            if ii.id in matched_ids.get(base_name, ()):
                buckets[base_name].append(ii)
                break
        # else: unclassified — left unplanned, same as every other planner's
        # categories it doesn't cover.

    # ── RUTILE's price depends on this licence's own average import price
    # (see module docstring for why this is NOT LicenseDetailsModel's
    # average_unit_price) ──────────────────────────────────────────────────
    avg_price = _rutile_avg_import_price(buckets["RUTILE"])
    rutile_price = RUTILE_PRICE_LOW if avg_price < RUTILE_AVG_THRESHOLD else RUTILE_PRICE_HIGH

    item_name_by_category = {
        "RUTILE": RUTILE_NAME,
        "TITANIUM DIOXIDE": TITANIUM_DIOXIDE_NAME,
        "SODA ASH": SODA_ASH_NAME,
        "PP": PP_NAME,
    }
    price_by_category = {
        "RUTILE": rutile_price,
        "TITANIUM DIOXIDE": TITANIUM_DIOXIDE_PRICE,
        "SODA ASH": SODA_ASH_PRICE,
        "PP": PP_PRICE,
    }
    unit_price_map = {item_name_by_category[cat]: price_by_category[cat] for cat in _CATEGORY_BASE_NAMES}

    lines: list[dict] = []

    for category in _CATEGORY_BASE_NAMES:  # priority order
        item_name = item_name_by_category[category]
        price = price_by_category[category]
        for group in merge_items_for_classification(buckets[category]):
            avail_qty = group["available_quantity"]
            planned_qty, planned_cif = _allocate_fixed_rate(avail_qty, price, remaining)
            if planned_cif <= 0:
                continue

            line = {
                "import_item": group["representative_id"],
                "item_name": name_ids.get(item_name),
                "planned_quantity": float(planned_qty),
                "unit_price": float(price),
                "planned_cif_fc": float(planned_cif),
                "note": f"Auto-planned (A3627 — {_LABEL[category]})",
            }

            # ── Mandatory validation gate (never skip this) ────────────────
            if not validate_group_plan_lines(
                [line], [item_name], avail_qty, unit_price_map, is_preserved=False,
            ):
                logger.warning(
                    "compute_a3627_auto_plan: rejecting plan for group represented by "
                    "import_item %s (category=%s) — planned_quantity=%s available=%s "
                    "price=%s; likely a bug in the A3627 waterfall, since this should "
                    "never happen for its structurally-bounded computation.",
                    group["representative_id"], category, planned_qty, avail_qty, price,
                )
                continue

            lines.append(line)
            remaining -= planned_cif

    return lines, float(remaining)
