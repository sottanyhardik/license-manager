"""
Norm E126 — deterministic planning classification engine.

Classifies each E126 source record (a licence import item) into planning
item(s) using an ORDERED priority engine (first match wins), sums quantity
per planning item, and applies a fixed planning unit price. Deterministic,
auditable (every match carries a Classification Reason), and free of double
counting (a record contributes its available quantity to at most one bucket
— except the PKO/Olive Oil split, which by design contributes to exactly
two: Palm Kernel Oil and Olive Oil).

Mirrors apps.license.services.e132_plan's architecture exactly (Nuts +
PKO/Olive-Oil replacing PKO/Cheese), with Yeast/RBD/Aluminium/explicit-
override dropped — the E126 priority table only has three items.

────────────────────────────────────────────────────────────────────────────
BUSINESS-RULE DECISIONS (made explicit — not silent assumptions)
────────────────────────────────────────────────────────────────────────────
1. PKO-alone / Olive-Oil-alone fallback. A record that signals ONLY one of
   Palm Kernel Oil (1513) or Olive Oil (1509/1500/1510) still has to
   classify somewhere. Such a record goes 100% to that single item — no
   split (the split only applies when BOTH signals are present on the same
   record).
2. Olive Oil detection reuses the EXACT signal already registered for E126
   in apps.license.utils.item_matcher.py's "OLIVE OIL" entry (HSN starts
   with 1509, OR description contains 1500/1509/1510 as a plain substring —
   not a word-boundary match, matching that entry's `icontains` filters).
   Palm Kernel Oil detection reuses the same 1513 signal e132_plan.py uses
   internally for its own PKO detection.
3. EVERY E126 planning quantity — including the PKO/Olive-Oil split target —
   is based on the record's CURRENT Available Quantity, never its
   original/total import quantity, for the same reason as E132 (see
   e132_plan.py's decision #3): available_quantity already self-corrects
   for real consumption, so recomputing the 50%/50% split fresh against it
   every run is automatically correct and idempotent.
4. DFIA NIL / DFIA Balance / residual-balance handling is explicitly OUT OF
   SCOPE for this engine — not implemented here, to be specified separately.

DATA MAPPING (source: LicenseImportItemsModel of an E126 licence)
    Norm        → licence export norm_class == "E126" (caller filters to these)
    HSN Code    → item.hs_code.hs_code   (str, may be null/blank)
    Description → item.description        (str, may be null/blank)
    Quantity    → item.available_quantity (Decimal) — the currently
                  allocatable pool for this record; ALSO the basis for the
                  PKO/Olive-Oil 50/50 split target (never the original/total
                  import quantity — see decision #3 above).
    Record id   → item.id                (preserved for traceability)
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

NORM = "E126"

# ── Planning item names ──────────────────────────────────────────────────────
NUT_NUTS = "NUTS - E126"
PKO = "PALM KERNEL OIL - E126"
OLIVE_OIL = "OLIVE OIL - E126"

# Internal-only classification marker for a record that satisfies BOTH the
# 1513 (PKO) signal and the Olive Oil signal — never an output item name;
# expanded into PKO (50%) + Olive Oil (50%) at allocation time by
# `_split_pko_olive_record` (per-record, NOT license-wide pooled — each
# record's split target is its OWN CURRENT available quantity, never its
# original/total import quantity).
_PKO_OLIVE_SPLIT = "__PKO_OLIVE_SPLIT__"

# ── Fixed planning unit prices (USD). ────────────────────────────────────────
UNIT_PRICE: dict[str, Decimal | None] = {
    NUT_NUTS: Decimal("3.00"),
    PKO: Decimal("1.80"),
    OLIVE_OIL: Decimal("5.00"),
}

# Planning-item display/priority order for the OUTPUT — Nuts → {PKO, Olive Oil}.
PLANNING_ORDER = (NUT_NUTS, PKO, OLIVE_OIL)

_SPLIT_TARGETS: dict[str, Decimal] = {PKO: Decimal("0.5"), OLIVE_OIL: Decimal("0.5")}


# ── Normalization ────────────────────────────────────────────────────────────
def _norm_text(value: Any) -> str:
    """Lower-case, trim, collapse internal whitespace. Null/blank → ''."""
    return re.sub(r"\s+", " ", (str(value) if value is not None else "").strip()).lower()


def _norm_hsn(value: Any) -> str:
    """Digits-only HSN, so '0401', '0401.20.00', '0401 2000' all normalize to a
    comparable digit string. Null/blank → ''."""
    return re.sub(r"\D", "", str(value) if value is not None else "")


def _hsn_matches(hsn_digits: str, code: str) -> bool:
    """HSN equals the code or begins with it (prefix): '1509' matches '1509',
    '15091000', '1509.10.00'."""
    return bool(hsn_digits) and (hsn_digits == code or hsn_digits.startswith(code))


def _has_word(desc_norm: str, word: str) -> bool:
    """Whole-word (boundary) match — a numeric code in the description
    ('0802') must not match inside a longer number."""
    return re.search(rf"\b{re.escape(word)}\b", desc_norm) is not None


def _hsn_or_desc(hsn: str, desc: str, code: str) -> bool:
    """True if `code` appears as the HSN (prefix match) OR as a standalone
    token in the description."""
    return _hsn_matches(hsn, code) or _has_word(desc, code)


# ── Ordered classification rules ─────────────────────────────────────────────
# Each rule: predicate(hsn_digits, desc_norm) -> reason|None. First rule that
# matches wins. Reasons are the audit trail.

def _rule_nuts(hsn: str, desc: str) -> str | None:
    if not (_hsn_matches(hsn, "0802") or _has_word(desc, "0802")):
        return None
    if _has_word(desc, "nut") or _has_word(desc, "nuts"):
        return "HSN/desc=0802 AND description contains 'NUT'/'NUTS'"
    return None


def _is_pko_signal(hsn: str, desc: str) -> bool:
    return _hsn_or_desc(hsn, desc, "1513")


def _is_olive_oil_signal(hsn: str, desc: str) -> bool:
    """Mirrors item_matcher.py's existing "OLIVE OIL" entry exactly: HSN
    starts with 1509, OR description contains 1500/1509/1510 as a plain
    substring (that entry uses `icontains`, not a word-boundary match)."""
    if _hsn_matches(hsn, "1509"):
        return True
    return "1500" in desc or "1509" in desc or "1510" in desc


def _rule_priority_2(hsn: str, desc: str) -> tuple[str, str] | None:
    """Palm Kernel Oil / Olive Oil group (Priority 2).

    Sub-order (first match wins):
      a. Split — 1513 signal AND Olive Oil signal both present on the SAME
         record — internal `_PKO_OLIVE_SPLIT` marker, expanded 50/50 at
         allocation time.
      b. PKO alone — 1513 signal without the Olive Oil signal.
      c. Olive Oil alone — Olive Oil signal without the 1513 signal.
    """
    pko_signal = _is_pko_signal(hsn, desc)
    olive_signal = _is_olive_oil_signal(hsn, desc)
    if pko_signal and olive_signal:
        return _PKO_OLIVE_SPLIT, "HSN/desc=1513 AND Olive Oil signal (1509/1500/1510) — 50% PKO / 50% Olive Oil split"
    if pko_signal:
        return PKO, "HSN/desc=1513"
    if olive_signal:
        return OLIVE_OIL, "HSN startswith 1509, or description contains 1500/1509/1510"
    return None


def classify_e126_record(hs_code: Any, description: Any) -> tuple[str | None, str | None]:
    """Classify one E126 record by HSN/description alone (priority order:
    Nuts → {PKO/Olive-Oil split, PKO, Olive Oil}).

    Returns ``(planning_item_name, classification_reason)``; ``(None, None)``
    when no rule matches (the record goes to the exception report).
    ``planning_item_name`` may be the internal `_PKO_OLIVE_SPLIT` marker,
    which callers with quantity context (`_classify_records`) expand into
    PKO/Olive-Oil lines — callers that only care about a single display name
    should treat it as "PKO/Olive Oil split", never surface the raw marker
    to users.
    """
    hsn = _norm_hsn(hs_code)
    desc = _norm_text(description)

    reason = _rule_nuts(hsn, desc)
    if reason is not None:
        return NUT_NUTS, reason

    p2 = _rule_priority_2(hsn, desc)
    if p2 is not None:
        return p2

    return None, None


# ── Aggregation / planning result ────────────────────────────────────────────
def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value)) if value not in (None, "") else Decimal("0")
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _allocate_step(qty: Decimal, max_price: Decimal, balance: Decimal) -> tuple[Decimal, Decimal]:
    """One waterfall step, capped at the remaining Balance CIF — mirrors the E1/E5/E132
    allocation so the total planned value can never exceed the licence balance.

    Returns ``(planned_value, effective_unit_price)``:
      * qty × max_price fits the balance → use max_price;
      * otherwise → cap at the remaining balance, rate drops to balance / qty.
    """
    if qty <= 0 or balance <= 0 or max_price <= 0:
        return Decimal("0"), max_price
    requested = qty * max_price
    if requested <= balance:
        return requested, max_price
    return balance, balance / qty


def _split_pko_olive_record(available_qty: Decimal) -> dict[str, Decimal]:
    """PKO/Olive-Oil 50/50 split, PER RECORD (not license-wide pooled):
    target quantities are 50%/50% of THIS record's CURRENT Available
    Quantity — never its original/total import quantity (see decision #3).

    Returns ``{PKO: qty, OLIVE_OIL: qty}``, always summing to exactly
    ``available_qty`` (never negative, never more than what's available —
    by construction, not by capping).
    """
    z = Decimal("0")
    if available_qty <= 0:
        return {PKO: z, OLIVE_OIL: z}
    return {name: available_qty * frac for name, frac in _SPLIT_TARGETS.items()}


def _allocate_buckets(agg: dict, balance_cif) -> dict:
    """Waterfall-allocate planned value to each OUTPUT planning item in PRIORITY
    order (Nuts → PKO → Olive Oil), capping the running total at
    ``balance_cif`` (max debit per licence = Balance CIF). When
    ``balance_cif`` is None the value is uncapped (qty × max price) —
    classification-only mode.

    Returns ``{item: {"qty", "value", "price", "count"}}`` for every output
    item that carries quantity.
    """
    remaining = _d(balance_cif) if balance_cif is not None else None
    out: dict = {}
    for name in PLANNING_ORDER:
        if name not in agg:
            continue
        qty = agg[name]["qty"]
        cnt = agg[name].get("count", 0)
        max_price = UNIT_PRICE.get(name)
        if max_price is None:
            out[name] = {"qty": qty, "value": None, "price": None, "count": cnt}
        elif remaining is None:
            out[name] = {"qty": qty, "value": qty * max_price, "price": max_price, "count": cnt}
        else:
            planned, eff = _allocate_step(qty, max_price, remaining)
            remaining -= planned
            out[name] = {"qty": qty, "value": planned, "price": eff, "count": cnt}
    return out


def _agg_from(recs: list) -> dict:
    """Aggregate classified records into ``{item: {qty, count}}``. Records
    classified to the internal PKO/Olive-Oil split marker contribute their
    PKO/Olive-Oil shortfall amounts (``r["split"]``) into BOTH buckets
    instead of a single one."""
    agg: dict = {}

    def _add(name: str, qty: Decimal):
        b = agg.setdefault(name, {"qty": Decimal("0"), "count": 0})
        b["qty"] += qty
        b["count"] += 1

    for r in recs:
        if r["item"] == _PKO_OLIVE_SPLIT:
            for name, qty in r["split"].items():
                if qty > 0:
                    _add(name, qty)
        elif r["item"] is not None:
            _add(r["item"], r["qty"])
    return agg


def _classify_records(records: Iterable[dict], balance_cif) -> list:
    """Classify every record. Returns a list of dicts with normalized fields:
    ``{record_id, item, reason, qty, hsn, desc, raw_hs, raw_desc, split}``.
    ``split`` is only populated (``{PKO: qty, OLIVE_OIL: qty}``) for records
    classified to the internal PKO/Olive-Oil split marker — always 50%/50%
    of that record's OWN ``qty`` (current Available Quantity)."""
    recs = []
    for rec in records:
        raw_hs = rec.get("hs_code")
        raw_desc = rec.get("description")
        item, reason = classify_e126_record(raw_hs, raw_desc)
        qty = _d(rec.get("quantity"))
        split: dict[str, Decimal] = _split_pko_olive_record(qty) if item == _PKO_OLIVE_SPLIT else {}
        recs.append({
            "record_id": rec.get("record_id"),
            "item": item,
            "reason": reason,
            "qty": qty,
            "split": split,
            "hsn": _norm_hsn(raw_hs),
            "desc": _norm_text(raw_desc),
            "raw_hs": raw_hs,
            "raw_desc": raw_desc,
        })
    return recs


# PKO -> Olive Oil wastage-reduction rebalance (mirrors e132_plan.py's PKO ->
# Cheese rebalance). Olive Oil is priced higher than PKO, so shifting
# quantity from PKO to Olive Oil raises total planned value without raising
# total planned quantity — used ONLY to close out leftover Remaining Balance
# CIF after the full waterfall has already run.
_PKO_TO_OLIVE_VALUE_GAIN: Decimal = UNIT_PRICE[OLIVE_OIL] - UNIT_PRICE[PKO]  # $3.20/unit


def _rebalance_pko_olive_wastage(recs: list, alloc: dict, balance_cif) -> None:
    """
    Wastage-reduction pass: the 50%/50% PKO/Olive-Oil split is the DEFAULT
    allocation, but if the full waterfall still leaves Remaining Balance CIF
    unused, shift quantity from PKO to Olive Oil on the split records to
    close that gap — Olive Oil ($5.00) is priced higher than PKO ($1.80), so
    moving quantity from one to the other increases total planned value
    WITHOUT increasing total planned quantity for that record.

    Mutates `recs`' `split` dicts and `alloc`'s PKO/OLIVE_OIL entries in
    place; every other bucket (Nuts) is left exactly as the waterfall
    computed it.

    No-op when:
      * `balance_cif` is None — classification-only/report mode has no
        balance target; OR
      * there is no leftover balance.

    Otherwise, each split record is visited ONCE, in the given `recs` order,
    and its shift is a single CLOSED-FORM calculation (`min(this record's
    PKO qty, remaining_balance / price_gain)`) — deterministic and
    idempotent, same as e132_plan.py's `_rebalance_veg_oil_wastage`.
    """
    if balance_cif is None:
        return
    if _PKO_TO_OLIVE_VALUE_GAIN <= 0:
        return  # defensive — rebalancing only helps when Olive Oil > PKO price

    total_planned = sum(
        (a["value"] for a in alloc.values() if a.get("value") is not None), Decimal("0"),
    )
    remaining = _d(balance_cif) - total_planned
    if remaining <= 0:
        return  # default split already correct, or waterfall already capped

    pko_bucket = alloc.get(PKO)
    olive_bucket = alloc.get(OLIVE_OIL)
    if pko_bucket is None or olive_bucket is None:
        return

    for r in recs:
        if remaining <= 0:
            break
        if r["item"] != _PKO_OLIVE_SPLIT:
            continue
        pko_qty = r["split"].get(PKO, Decimal("0"))
        if pko_qty <= 0:
            continue

        shift = min(pko_qty, remaining / _PKO_TO_OLIVE_VALUE_GAIN)
        if shift <= 0:
            continue

        r["split"][PKO] = pko_qty - shift
        r["split"][OLIVE_OIL] = r["split"].get(OLIVE_OIL, Decimal("0")) + shift

        pko_bucket["qty"] -= shift
        pko_bucket["value"] -= shift * UNIT_PRICE[PKO]
        olive_bucket["qty"] += shift
        olive_bucket["value"] += shift * UNIT_PRICE[OLIVE_OIL]
        remaining -= shift * _PKO_TO_OLIVE_VALUE_GAIN


def _classify_and_allocate(records: Iterable[dict], balance_cif) -> tuple[list, dict]:
    """Shared pipeline for every public ``plan_e126*`` function: classify →
    aggregate → waterfall-allocate → wastage-reduction rebalance (see
    `_rebalance_pko_olive_wastage`). Kept in one place so the rebalance pass
    can never be forgotten in one of the three call sites."""
    recs = _classify_records(records, balance_cif)
    alloc = _allocate_buckets(_agg_from(recs), balance_cif)
    _rebalance_pko_olive_wastage(recs, alloc, balance_cif)
    return recs, alloc


@dataclass
class ClassifiedRecord:
    record_id: Any
    hs_code: str
    description: str
    quantity: Decimal
    planning_item: str | None
    reason: str | None


def _effective_rate(a):
    """True per-unit rate for a bucket = allocated value ÷ quantity. Correct in all
    cases: uncapped (= max price), partially balance-capped (dropped rate), and
    fully exhausted (0 — no balance left), unlike the raw ceiling price which stays
    at max even when nothing was allocated."""
    if not a or a.get("value") is None:
        return None
    q = a["qty"]
    return (a["value"] / q) if q and q > 0 else a["price"]


def _blended_pko_olive_rate(split: dict, alloc: dict):
    """Single blended rate for a split record's report line = its own PKO +
    Olive Oil shortfall value ÷ its own shortfall quantity. ``None`` if the
    record didn't actually contribute any quantity this round."""
    total_qty = Decimal("0")
    total_val = Decimal("0")
    any_priced = False
    for name, qty in split.items():
        if qty <= 0:
            continue
        rate = _effective_rate(alloc.get(name))
        total_qty += qty
        if rate is not None:
            total_val += qty * rate
            any_priced = True
    if total_qty <= 0 or not any_priced:
        return None
    return total_val / total_qty


def plan_e126_per_item(records: Iterable[dict], balance_cif=None) -> dict:
    """Per-record planning for E126 (for report views that show one plan line per
    import item).

    Classifies each record, then applies the balance-capped waterfall at the
    planning-item level (max debit per licence = Balance CIF): each record is
    priced at its planning item's EFFECTIVE unit rate (the fixed max, dropped
    proportionally if the item would overflow the remaining balance), so per-item
    planned values sum to at most ``balance_cif``. When ``balance_cif`` is None the
    price is the uncapped fixed rate.

    Returns ``{record_id: {planning_item, reason, planned_quantity, unit_price,
    planned_cif}}`` for classified records; unclassified records are omitted (they
    belong in the exception report).

    PKO/Olive-Oil split records are priced at the BLENDED effective rate (its
    own PKO + Olive Oil value ÷ its own quantity) and reported as one line
    each — the one-line-per-record shape this function guarantees. Callers
    that want the PKO/Olive-Oil breakdown per record use
    ``plan_e126_per_item_split``.
    """
    recs, alloc = _classify_and_allocate(records, balance_cif)
    out: dict = {}
    for r in recs:
        item = r["item"]
        if item is None:
            continue
        if item == _PKO_OLIVE_SPLIT:
            eff_rate = _blended_pko_olive_rate(r["split"], alloc)
            qty = sum(r["split"].values(), Decimal("0"))
        else:
            eff_rate = _effective_rate(alloc.get(item))
            qty = r["qty"]
        out[r["record_id"]] = {
            "planning_item": item,
            "reason": r["reason"],
            "planned_quantity": qty,
            "unit_price": eff_rate,
            "planned_cif": (qty * eff_rate) if eff_rate is not None else None,
        }
    return out


def plan_e126_per_item_split(records: Iterable[dict], balance_cif=None) -> dict:
    """Like ``plan_e126_per_item`` but returns a LIST of plan lines per record so a
    single split-eligible import item can be shown as its PKO/Olive-Oil split.

    Returns ``{record_id: [ {planning_item, reason, planned_quantity, unit_price,
    planned_cif}, ... ]}``. Non-split records yield a single-element list;
    split records yield one entry per target (PKO/Olive Oil) that carries
    quantity (50%/50% of the record's current Available Quantity — see
    `_split_pko_olive_record`).
    """
    recs, alloc = _classify_and_allocate(records, balance_cif)

    out: dict = {}
    for r in recs:
        item = r["item"]
        if item is None:
            continue
        rid, reason = r["record_id"], r["reason"]
        if item == _PKO_OLIVE_SPLIT:
            lines = []
            for name, qty in r["split"].items():
                if qty <= 0:
                    continue
                rate = _effective_rate(alloc.get(name))
                lines.append({
                    "planning_item": name,
                    "reason": reason,
                    "planned_quantity": qty,
                    "unit_price": rate,
                    "planned_cif": (qty * rate) if rate is not None else None,
                })
            out[rid] = lines
        else:
            qty = r["qty"]
            eff_rate = _effective_rate(alloc.get(item))
            out[rid] = [{
                "planning_item": item,
                "reason": reason,
                "planned_quantity": qty,
                "unit_price": eff_rate,
                "planned_cif": (qty * eff_rate) if eff_rate is not None else None,
            }]
    return out


def plan_e126(records: Iterable[dict], balance_cif=None) -> dict:
    """Classify + aggregate E126 records into a planning result.

    Args:
        records: iterable of dicts with keys ``record_id``, ``hs_code``,
            ``description``, ``quantity`` (the record's current Available
            Quantity — ALSO the basis for the PKO/Olive-Oil 50/50 split
            target, never an original/total import quantity). Records are
            assumed already filtered to Norm E126.
        balance_cif: licence Balance CIF $. When given, planning value is
            waterfall-allocated in priority order and capped so the total never
            exceeds it (max debit per licence = Balance CIF), and ``unit_price`` is
            the effective rate. When None, value is the uncapped qty × fixed price.

    Returns dict with:
        ``items``      – planning rows (in PLANNING_ORDER, only items with
                         records), each: norm, planning_item_name, total_quantity,
                         unit_price, planning_value, num_source_records,
                         unit_price_defined.
        ``classified`` – list[ClassifiedRecord] (full per-record audit trail).
        ``exceptions`` – list[ClassifiedRecord] with planning_item is None
                         (matched no rule).
        ``missing_inputs`` – planning items whose unit price is undefined.
    """
    recs, alloc = _classify_and_allocate(records, balance_cif)
    classified: list[ClassifiedRecord] = [
        ClassifiedRecord(
            record_id=r["record_id"],
            hs_code=str(r["raw_hs"]) if r["raw_hs"] is not None else "",
            description=str(r["raw_desc"]) if r["raw_desc"] is not None else "",
            quantity=r["qty"],
            planning_item=(r["item"] if r["item"] != _PKO_OLIVE_SPLIT else PKO + " / " + OLIVE_OIL),
            reason=r["reason"],
        )
        for r in recs
    ]
    items = []
    for name in PLANNING_ORDER:
        a = alloc.get(name)
        if a is None:
            continue
        max_price = UNIT_PRICE.get(name)
        items.append({
            "norm": NORM,
            "planning_item_name": name,
            "total_quantity": a["qty"],
            "unit_price": a["price"],        # effective rate (= max unless capped)
            "max_unit_price": max_price,     # the fixed ceiling
            "planning_value": a["value"],    # capped at remaining Balance CIF
            "num_source_records": a["count"],
            "unit_price_defined": max_price is not None,
        })

    exceptions = [c for c in classified if c.planning_item is None]
    missing_inputs = [i["planning_item_name"] for i in items if not i["unit_price_defined"]]
    total_planned = sum((i["planning_value"] for i in items if i["planning_value"] is not None),
                        Decimal("0"))
    wastage = (_d(balance_cif) - total_planned) if balance_cif is not None else None

    return {
        "items": items,
        "classified": classified,
        "exceptions": exceptions,
        "missing_inputs": missing_inputs,
        "balance_cif": _d(balance_cif) if balance_cif is not None else None,
        "total_planned": total_planned,
        "wastage": wastage,
    }
