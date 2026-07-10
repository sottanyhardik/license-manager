"""
Norm E132 — deterministic planning classification engine.

Classifies each E132 source record (a licence import item) into EXACTLY ONE
planning item using an ORDERED priority engine (first match wins), sums quantity
per planning item, and applies a fixed planning unit price. Deterministic,
auditable (every match carries a Classification Reason), and free of double
counting (a record contributes to at most one item).

────────────────────────────────────────────────────────────────────────────
BUSINESS-RULE DECISIONS (made explicit — not silent assumptions)
────────────────────────────────────────────────────────────────────────────
1. YEAST / HSN 2106 OVERLAP → resolved with the "corrected priority".
   The spec lists Yeast (needs "yeast" AND HSN 2106) *after* Cheese (matches
   HSN 2106 alone). Under the literal order Yeast is UNREACHABLE — any 2106
   record is taken by Cheese first, so the Yeast rule could never fire. A rule
   that can never match cannot be the intent, and the spec itself recommends the
   correction, so Yeast is evaluated FIRST as a high-priority special case.
   ⚠ Requires business confirmation. Flip PRIORITY_YEAST_FIRST to revert.

2. MILK unit price may range 0–22 USD. The ceiling (22, MILK_MAX_PRICE) is used
   as the planning unit price so Planning Value computes; adjust that one
   constant to change it. (Previously To-Be-Defined.)

3. "oil" (Item 1 keyword) is BROAD. By priority, descriptions like
   "palm kernel oil" or "RBD palmolein oil" classify to Cheese (Item 1) before
   PKO/RBD. This is faithful to the stated priority but materially affects
   results — confirm it is intended.

4. This engine is a NEW, standalone classifier. It does NOT replace the existing
   apps.license.services.e132_debit (a different sequential balance-consuming
   model used by the Download-License Excel, with different items/prices).
   Whether the debit model should migrate to this classification is an open
   business question — left untouched here.

DATA MAPPING (source: LicenseImportItemsModel of an E132 licence)
    Norm        → licence export norm_class == "E132" (caller filters to these)
    HSN Code    → item.hs_code.hs_code   (str, may be null/blank)
    Description → item.description        (str, may be null/blank)
    Quantity    → item.quantity          (Decimal)
    Record id   → item.id                (preserved for traceability)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Optional

NORM = "E132"

# ── Planning item names ──────────────────────────────────────────────────────
CHEESE = "CHEESE CREAM BUTTER AND FATS - E132"
PKO = "PKO - E132"
RBD = "RBD - E132"
YEAST = "Yeast - E132"
ALUMINIUM = "Aluminium Foil - E132"
MILK = "Milk - E132"
NUT_NUTS = "NUT & NUTS - E132"
RAISIN_ITEM = "RAISIN - E132"
CEREALS_FLAKES = "CEREALS FLAKES - E132"

# Milk's unit price may range 0–22 USD; the ceiling (22) is used as the planning
# unit price (editable down in the sheet if a lower value is agreed). Change this
# one constant to adjust.
MILK_MAX_PRICE = Decimal("22.00")

# ── Fixed planning unit prices (USD). ────────────────────────────────────────
UNIT_PRICE: dict[str, Optional[Decimal]] = {
    YEAST: Decimal("3.00"),
    CHEESE: Decimal("5.00"),
    PKO: Decimal("2.30"),
    RBD: Decimal("1.20"),
    ALUMINIUM: Decimal("4.50"),
    MILK: MILK_MAX_PRICE,  # ceiling of the permitted 0–22 range
    # ⚠ Unit prices To-Be-Defined (no price supplied yet). Until set, these items
    #   classify and aggregate quantity but show 'TBD' and contribute 0 to value
    #   (same handling Milk had before its ceiling was agreed). Set a Decimal here.
    NUT_NUTS: None,
    RAISIN_ITEM: None,
    CEREALS_FLAKES: None,
}

# Toggle the Yeast/2106 overlap resolution (decision #1). True = corrected
# priority (Yeast evaluated first); False = literal spec order (Yeast unreachable
# for HSN-2106 records). Default True per the spec's own recommendation.
PRIORITY_YEAST_FIRST = True

# Planning-item display/priority order for the output. The three additions
# (NUT & NUTS, RAISIN, CEREALS FLAKES) are appended after the confirmed six, so
# existing higher-priority classifications are unchanged.
PLANNING_ORDER = (YEAST, CHEESE, PKO, RBD, MILK, ALUMINIUM, NUT_NUTS, RAISIN_ITEM, CEREALS_FLAKES)


# ── Normalization ────────────────────────────────────────────────────────────
def _norm_text(value: Any) -> str:
    """Lower-case, trim, collapse internal whitespace. Null/blank → ''."""
    return re.sub(r"\s+", " ", (str(value) if value is not None else "").strip()).lower()


def _norm_hsn(value: Any) -> str:
    """Digits-only HSN, so '0401', '0401.20.00', '0401 2000' all normalize to a
    comparable digit string. Null/blank → ''."""
    return re.sub(r"\D", "", str(value) if value is not None else "")


def _hsn_matches(hsn_digits: str, code: str) -> bool:
    """HSN equals the code or begins with it (prefix), per matching rule #5:
    '0401' matches '0401', '04012000', '0401.20.00'."""
    return bool(hsn_digits) and (hsn_digits == code or hsn_digits.startswith(code))


def _has_word(desc_norm: str, word: str) -> bool:
    """Whole-word (boundary) match — 'oil' must NOT match 'foil'/'boil', and a
    numeric code in the description ('7607') must not match inside a longer
    number. Used where the spec says "the word ..." or matches HSN-in-description.
    """
    return re.search(rf"\b{re.escape(word)}\b", desc_norm) is not None


# ── Ordered classification rules ─────────────────────────────────────────────
# Each rule: (planning_item, predicate(hsn_digits, desc_norm) -> reason|None).
# First rule whose predicate returns a reason wins. Reasons are the audit trail.

def _rule_yeast(hsn: str, desc: str) -> Optional[str]:
    if "yeast" in desc and _hsn_matches(hsn, "2106"):
        return "Description contains 'yeast' AND HSN=2106"
    return None


def _rule_cheese(hsn: str, desc: str) -> Optional[str]:
    for code in ("0401", "0405", "0406", "2106"):
        if _hsn_matches(hsn, code):
            return f"HSN={code}"
    if _has_word(desc, "oil"):
        return "Description contains the word 'oil'"
    return None


def _rule_pko(hsn: str, desc: str) -> Optional[str]:
    if _hsn_matches(hsn, "1513"):
        return "HSN=1513"
    if "pko" in desc:
        return "Description contains 'PKO'"
    if "kernel" in desc:
        return "Description contains 'kernel'"
    return None


def _rule_rbd(hsn: str, desc: str) -> Optional[str]:
    if _hsn_matches(hsn, "1511"):
        return "HSN=1511"
    if "rbd" in desc:
        return "Description contains 'RBD'"
    if "palmolein" in desc:
        return "Description contains 'palmolein'"
    return None


def _rule_aluminium(hsn: str, desc: str) -> Optional[str]:
    if _hsn_matches(hsn, "7607"):
        return "HSN=7607"
    if _has_word(desc, "7607"):
        return "Description contains '7607'"
    return None


def _rule_milk(hsn: str, desc: str) -> Optional[str]:
    # Explicit guard: a "yeast" + HSN-2106 record is Yeast, never Milk (already
    # guaranteed by the Yeast-first priority, but kept here as defensive intent).
    if "yeast" in desc and _hsn_matches(hsn, "2106"):
        return None
    if "milk solid" in desc:
        return "Description contains 'milk solid'"
    if "milk" in desc:
        return "Description contains 'milk'"
    if _hsn_matches(hsn, "3502"):
        return "HSN=3502"
    if _has_word(desc, "3502"):
        return "Description contains '3502'"
    return None


def _rule_nut(hsn: str, desc: str) -> Optional[str]:
    # NUT & NUTS: HSN starts with 0802 (or '0802' in the description) — but NOT
    # when the record is milk or a 0806 (raisin) item, per the stated exclusions.
    if not (_hsn_matches(hsn, "0802") or _has_word(desc, "0802")):
        return None
    if "milk" in desc:                                    # exclusion: no milk
        return None
    if _hsn_matches(hsn, "0806") or _has_word(desc, "0806"):  # exclusion: no 0806
        return None
    return "HSN=0802 / desc contains '0802' (excl. milk & 0806)"


def _rule_raisin(hsn: str, desc: str) -> Optional[str]:
    # RAISIN: HSN starts with 0806 (or '0806' in the description).
    if _hsn_matches(hsn, "0806"):
        return "HSN=0806"
    if _has_word(desc, "0806"):
        return "Description contains '0806'"
    return None


def _rule_cereals(hsn: str, desc: str) -> Optional[str]:
    # ⚠ ASSUMED rule — no classification criteria were given for CEREALS FLAKES.
    #   Uses HSN 1104 (this codebase's historical cereal-flakes code). CONFIRM /
    #   replace the code or keyword below with the real rule.
    if _hsn_matches(hsn, "1104"):
        return "HSN=1104"
    if _has_word(desc, "1104"):
        return "Description contains '1104'"
    return None


# Corrected priority (decision #1). Yeast first so it is reachable; Milk ahead of
# Aluminium Foil per the confirmed business order. NUT & NUTS / RAISIN / CEREALS
# FLAKES appended last (lowest priority).
_RULES_CORRECTED = (
    (YEAST, _rule_yeast),
    (CHEESE, _rule_cheese),
    (PKO, _rule_pko),
    (RBD, _rule_rbd),
    (MILK, _rule_milk),
    (ALUMINIUM, _rule_aluminium),
    (NUT_NUTS, _rule_nut),
    (RAISIN_ITEM, _rule_raisin),
    (CEREALS_FLAKES, _rule_cereals),
)
# Literal spec order (Yeast after Cheese — provided for completeness/audit).
_RULES_LITERAL = (
    (CHEESE, _rule_cheese),
    (PKO, _rule_pko),
    (RBD, _rule_rbd),
    (YEAST, _rule_yeast),
    (ALUMINIUM, _rule_aluminium),
    (MILK, _rule_milk),
    (NUT_NUTS, _rule_nut),
    (RAISIN_ITEM, _rule_raisin),
    (CEREALS_FLAKES, _rule_cereals),
)


def _active_rules():
    return _RULES_CORRECTED if PRIORITY_YEAST_FIRST else _RULES_LITERAL


def classify_e132_record(hs_code: Any, description: Any) -> tuple[Optional[str], Optional[str]]:
    """Classify one E132 record.

    Returns ``(planning_item_name, classification_reason)``; ``(None, None)`` when
    no rule matches (the record goes to the exception report). The caller is
    responsible for ensuring the record's Norm is E132.
    """
    hsn = _norm_hsn(hs_code)
    desc = _norm_text(description)
    for item, predicate in _active_rules():
        reason = predicate(hsn, desc)
        if reason is not None:
            return item, reason
    return None, None


# ── Aggregation / planning result ────────────────────────────────────────────
def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value)) if value not in (None, "") else Decimal("0")
    except Exception:
        return Decimal("0")


def _allocate_step(qty: Decimal, max_price: Decimal, balance: Decimal) -> tuple[Decimal, Decimal]:
    """One waterfall step, capped at the remaining Balance CIF — mirrors the E1/E5
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


def _allocate_buckets(agg: dict, balance_cif) -> dict:
    """Waterfall-allocate planned value to each planning item in PRIORITY order
    (Yeast → Cheese → PKO → RBD → Milk → Aluminium Foil → NUT & NUTS → RAISIN →
    CEREALS FLAKES), capping the running total
    at ``balance_cif`` (max debit per licence = Balance CIF). When ``balance_cif`` is
    None the value is uncapped (qty × max price) — classification-only mode.

    Returns ``{item: (planned_value, effective_unit_price)}``.
    """
    remaining = _d(balance_cif) if balance_cif is not None else None
    out: dict = {}
    for name in PLANNING_ORDER:
        if name not in agg:
            continue
        qty = agg[name]["qty"]
        max_price = UNIT_PRICE.get(name)
        if max_price is None:
            out[name] = (None, None)
        elif remaining is None:
            out[name] = (qty * max_price, max_price)
        else:
            planned, eff = _allocate_step(qty, max_price, remaining)
            remaining -= planned
            out[name] = (planned, eff)
    return out


@dataclass
class ClassifiedRecord:
    record_id: Any
    hs_code: str
    description: str
    quantity: Decimal
    planning_item: Optional[str]
    reason: Optional[str]


def plan_e132_per_item(records: Iterable[dict], balance_cif=None) -> dict:
    """Per-record planning for E132 (for report views that show one plan line per
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
    """
    classified = []
    agg: dict = {}
    for rec in records:
        item, reason = classify_e132_record(rec.get("hs_code"), rec.get("description"))
        if item is None:
            continue
        qty = _d(rec.get("quantity"))
        classified.append((rec.get("record_id"), item, reason, qty))
        agg.setdefault(item, {"qty": Decimal("0")})["qty"] += qty

    alloc = _allocate_buckets(agg, balance_cif)  # {item: (planned_value, eff_rate)}
    out: dict = {}
    for rid, item, reason, qty in classified:
        _planned, eff_rate = alloc.get(item, (None, None))
        out[rid] = {
            "planning_item": item,
            "reason": reason,
            "planned_quantity": qty,
            "unit_price": eff_rate,
            "planned_cif": (qty * eff_rate) if eff_rate is not None else None,
        }
    return out


def plan_e132(records: Iterable[dict], balance_cif=None) -> dict:
    """Classify + aggregate E132 records into a planning result.

    Args:
        records: iterable of dicts with keys ``record_id``, ``hs_code``,
            ``description``, ``quantity``. Records are assumed already filtered
            to Norm E132.
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
    classified: list[ClassifiedRecord] = []
    agg: dict[str, dict] = {}

    for rec in records:
        hs = rec.get("hs_code")
        desc = rec.get("description")
        qty = _d(rec.get("quantity"))
        item, reason = classify_e132_record(hs, desc)
        cr = ClassifiedRecord(
            record_id=rec.get("record_id"),
            hs_code=str(hs) if hs is not None else "",
            description=str(desc) if desc is not None else "",
            quantity=qty,
            planning_item=item,
            reason=reason,
        )
        classified.append(cr)
        if item is not None:
            bucket = agg.setdefault(item, {"qty": Decimal("0"), "count": 0})
            bucket["qty"] += qty  # rule #4/#6: quantity into exactly one item
            bucket["count"] += 1

    alloc = _allocate_buckets(agg, balance_cif)  # priority-order, balance-capped
    items = []
    for name in PLANNING_ORDER:
        if name not in agg:
            continue
        max_price = UNIT_PRICE.get(name)
        total_qty = agg[name]["qty"]
        planned, eff_rate = alloc[name]
        items.append({
            "norm": NORM,
            "planning_item_name": name,
            "total_quantity": total_qty,
            "unit_price": eff_rate,          # effective rate (= max unless capped)
            "max_unit_price": max_price,     # the fixed ceiling
            "planning_value": planned,       # capped at remaining Balance CIF
            "num_source_records": agg[name]["count"],
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
