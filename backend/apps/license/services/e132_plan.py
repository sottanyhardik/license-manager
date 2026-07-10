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
NUT_NUTS = "NUT & NUTS - E132"
RAISIN_ITEM = "RAISIN - E132"
CEREALS_FLAKES = "CEREALS FLAKES - E132"
CMC = "CMC - E132"

# ── Milk split ───────────────────────────────────────────────────────────────
# Milk is detected by classification (see _rule_milk) into a single internal pool
# (MILK), then the pooled milk quantity is SPLIT across three whey products at
# fixed prices so that (a) all milk quantity is utilised and (b) the planned value
# equals the balance available at milk's turn ("0 $ left"). See _split_milk.
MILK = "Milk - E132"          # internal classification pool only — NOT an output item
SWP = "SWP - E132"            # Skimmed Whey Powder
DWP = "DWP - E132"            # Demineralised Whey Powder
WPC = "WPC - E132"            # Whey Protein Concentrate
MILK_PRODUCTS = (SWP, DWP, WPC)   # display order of the three split products

# ── Fixed planning unit prices (USD). ────────────────────────────────────────
UNIT_PRICE: dict[str, Optional[Decimal]] = {
    YEAST: Decimal("3.00"),
    CHEESE: Decimal("5.00"),
    PKO: Decimal("2.30"),
    RBD: Decimal("1.20"),
    ALUMINIUM: Decimal("4.50"),
    SWP: Decimal("1.50"),
    DWP: Decimal("5.00"),
    WPC: Decimal("22.00"),
    NUT_NUTS: Decimal("10.00"),
    RAISIN_ITEM: Decimal("4.00"),
    CEREALS_FLAKES: Decimal("0.60"),
    # ⚠ CMC price is set, but _rule_cmc is still a placeholder that matches nothing
    #   — CMC will not classify any record until a real rule is supplied.
    CMC: Decimal("5.00"),
}

# Toggle the Yeast/2106 overlap resolution (decision #1). True = corrected
# priority (Yeast evaluated first); False = literal spec order (Yeast unreachable
# for HSN-2106 records). Default True per the spec's own recommendation.
PRIORITY_YEAST_FIRST = True

# Planning-item display/priority order for the OUTPUT. The milk pool occupies rank
# 5 as three products (SWP, DWP, WPC). Records still classify to the MILK pool;
# _allocate_buckets expands that pool into these three at planning time.
PLANNING_ORDER = (
    YEAST, CHEESE, PKO, RBD,
    SWP, DWP, WPC,
    NUT_NUTS, RAISIN_ITEM, CEREALS_FLAKES, CMC, ALUMINIUM,
)


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


def _rule_cmc(hsn: str, desc: str) -> Optional[str]:
    # CMC: HSN starts with 3912 (or '3912' in the description). CMC is evaluated
    # LAST in the priority order, so this only catches items not already claimed
    # by a higher-priority rule ("not classified elsewhere").
    if _hsn_matches(hsn, "3912"):
        return "HSN=3912"
    if _has_word(desc, "3912"):
        return "Description contains '3912'"
    return None


# Corrected priority (decision #1). Yeast first so it is reachable. Aluminium Foil
# is evaluated LAST per the confirmed business order.
_RULES_CORRECTED = (
    (YEAST, _rule_yeast),
    (CHEESE, _rule_cheese),
    (PKO, _rule_pko),
    (RBD, _rule_rbd),
    (MILK, _rule_milk),
    (NUT_NUTS, _rule_nut),
    (RAISIN_ITEM, _rule_raisin),
    (CEREALS_FLAKES, _rule_cereals),
    (CMC, _rule_cmc),
    (ALUMINIUM, _rule_aluminium),
)
# Literal spec order (Yeast after Cheese — provided for completeness/audit).
_RULES_LITERAL = (
    (CHEESE, _rule_cheese),
    (PKO, _rule_pko),
    (RBD, _rule_rbd),
    (YEAST, _rule_yeast),
    (MILK, _rule_milk),
    (NUT_NUTS, _rule_nut),
    (RAISIN_ITEM, _rule_raisin),
    (CEREALS_FLAKES, _rule_cereals),
    (CMC, _rule_cmc),
    (ALUMINIUM, _rule_aluminium),
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


def _split_milk(pool_qty: Decimal, remaining) -> dict:
    """Split the pooled milk quantity across SWP / DWP / WPC by the target average
    price (avg = balance available at milk's turn ÷ milk quantity):

        avg < 1.5      → all SWP (full qty & value; effective rate = avg)
        1.5 ≤ avg < 5  → split SWP + DWP
        5   ≤ avg < 22 → split SWP + WPC
        avg ≥ 22       → all WPC (value = 22 × qty; any balance beyond flows on)

    In the split bands the two quantities are chosen so ALL milk quantity is used
    AND the planned value equals the balance available to milk ("0 $ left"). Each
    product keeps its fixed unit price; only the quantities move.

    Returns ``{SWP|DWP|WPC: (qty, unit_price, planned_value)}``.
    """
    p_swp, p_dwp, p_wpc = UNIT_PRICE[SWP], UNIT_PRICE[DWP], UNIT_PRICE[WPC]
    z = Decimal("0")
    empty = {SWP: (z, p_swp, z), DWP: (z, p_dwp, z), WPC: (z, p_wpc, z)}
    Q = pool_qty
    if Q <= 0:
        return empty
    if remaining is None:
        # Classification-only mode (no balance target): show qty × the top rate.
        return {SWP: (z, p_swp, z), DWP: (z, p_dwp, z), WPC: (Q, p_wpc, Q * p_wpc)}
    B = remaining
    if B <= 0:
        return empty  # no balance left → milk cannot be planned here
    avg = B / Q
    if avg < p_swp:
        # Below the cheapest product: all SWP at the effective (dropped) rate so the
        # full quantity and the full available value are shown on the SWP line.
        return {SWP: (Q, B / Q, B), DWP: (z, p_dwp, z), WPC: (z, p_wpc, z)}
    if avg < p_dwp:
        # SWP + DWP: q_dwp units moved up from SWP so the value reaches the balance.
        q_dwp = (B - p_swp * Q) / (p_dwp - p_swp)
        q_swp = Q - q_dwp
        return {SWP: (q_swp, p_swp, q_swp * p_swp),
                DWP: (q_dwp, p_dwp, q_dwp * p_dwp),
                WPC: (z, p_wpc, z)}
    if avg < p_wpc:
        # SWP + WPC.
        q_wpc = (B - p_swp * Q) / (p_wpc - p_swp)
        q_swp = Q - q_wpc
        return {SWP: (q_swp, p_swp, q_swp * p_swp),
                DWP: (z, p_dwp, z),
                WPC: (q_wpc, p_wpc, q_wpc * p_wpc)}
    # avg ≥ 22 → only WPC; any balance above 22 × qty flows to later items.
    return {SWP: (z, p_swp, z), DWP: (z, p_dwp, z), WPC: (Q, p_wpc, Q * p_wpc)}


def _allocate_buckets(agg: dict, balance_cif) -> dict:
    """Waterfall-allocate planned value to each OUTPUT planning item in PRIORITY
    order (Yeast → Cheese → PKO → RBD → [milk: SWP/DWP/WPC] → NUT & NUTS → RAISIN →
    CEREALS FLAKES → CMC → Aluminium Foil), capping the running total at
    ``balance_cif`` (max debit per licence = Balance CIF). When ``balance_cif`` is
    None the value is uncapped (qty × max price) — classification-only mode.

    The milk pool (agg[MILK]) is expanded into SWP/DWP/WPC via _split_milk using the
    balance remaining when milk's turn is reached.

    Returns ``{item: {"qty", "value", "price", "count"}}`` for every output item
    that carries quantity.
    """
    remaining = _d(balance_cif) if balance_cif is not None else None
    out: dict = {}
    milk_done = False
    for name in PLANNING_ORDER:
        if name in MILK_PRODUCTS:
            if milk_done:
                continue
            milk_done = True
            pool = agg.get(MILK)
            pool_qty = pool["qty"] if pool else Decimal("0")
            pool_count = pool.get("count", 0) if pool else 0
            if pool_qty <= 0:
                continue
            split = _split_milk(pool_qty, remaining)
            total_val = sum((v for (_q, _p, v) in split.values()), Decimal("0"))
            if remaining is not None:
                remaining -= total_val
            for i, prod in enumerate(MILK_PRODUCTS):
                q, p, v = split[prod]
                # Attribute the source-record count to the first product row only,
                # so the total record count is not triple-counted.
                out[prod] = {"qty": q, "value": v, "price": p, "count": pool_count if i == 0 else 0}
            continue
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

    Milk records are priced at the BLENDED effective milk rate (total split value ÷
    total milk quantity) and reported as one line each — the one-line-per-record
    shape this function guarantees. Callers that want the SWP/DWP/WPC breakdown per
    record use ``plan_e132_per_item_split``.
    """
    classified = []
    agg: dict = {}
    for rec in records:
        item, reason = classify_e132_record(rec.get("hs_code"), rec.get("description"))
        if item is None:
            continue
        qty = _d(rec.get("quantity"))
        classified.append((rec.get("record_id"), item, reason, qty))
        b = agg.setdefault(item, {"qty": Decimal("0"), "count": 0})
        b["qty"] += qty
        b["count"] += 1

    alloc = _allocate_buckets(agg, balance_cif)  # {item: {qty,value,price,count}}
    _milk_rate = _blended_milk_rate(alloc)
    out: dict = {}
    for rid, item, reason, qty in classified:
        if item == MILK:
            eff_rate = _milk_rate
        else:
            eff_rate = _effective_rate(alloc.get(item))
        out[rid] = {
            "planning_item": item,
            "reason": reason,
            "planned_quantity": qty,
            "unit_price": eff_rate,
            "planned_cif": (qty * eff_rate) if eff_rate is not None else None,
        }
    return out


def _effective_rate(a):
    """True per-unit rate for a bucket = allocated value ÷ quantity. Correct in all
    cases: uncapped (= max price), partially balance-capped (dropped rate), and
    fully exhausted (0 — no balance left), unlike the raw ceiling price which stays
    at max even when nothing was allocated."""
    if not a or a.get("value") is None:
        return None
    q = a["qty"]
    return (a["value"] / q) if q and q > 0 else a["price"]


def _blended_milk_rate(alloc: dict):
    """Effective single milk rate = total split value ÷ total milk quantity, or None
    if there is no milk / no priced milk value."""
    qty = sum((alloc[p]["qty"] for p in MILK_PRODUCTS if p in alloc), Decimal("0"))
    val = sum((alloc[p]["value"] for p in MILK_PRODUCTS
               if p in alloc and alloc[p]["value"] is not None), Decimal("0"))
    return (val / qty) if qty > 0 else None


def plan_e132_per_item_split(records: Iterable[dict], balance_cif=None) -> dict:
    """Like ``plan_e132_per_item`` but returns a LIST of plan lines per record so a
    single milk import item can be shown as its SWP/DWP/WPC split (decision 3.B).

    Returns ``{record_id: [ {planning_item, reason, planned_quantity, unit_price,
    planned_cif}, ... ]}``. Non-milk records yield a single-element list; milk
    records yield one entry per split product that carries quantity, apportioning
    the record's quantity by the pool's product fractions.
    """
    classified = []
    agg: dict = {}
    for rec in records:
        item, reason = classify_e132_record(rec.get("hs_code"), rec.get("description"))
        if item is None:
            continue
        qty = _d(rec.get("quantity"))
        classified.append((rec.get("record_id"), item, reason, qty))
        b = agg.setdefault(item, {"qty": Decimal("0"), "count": 0})
        b["qty"] += qty
        b["count"] += 1

    alloc = _allocate_buckets(agg, balance_cif)
    # Pool fractions for apportioning each milk record across the products.
    pool_qty = agg.get(MILK, {}).get("qty", Decimal("0"))
    milk_fracs = []
    if pool_qty > 0:
        for prod in MILK_PRODUCTS:
            a = alloc.get(prod)
            if a and a["qty"] > 0:
                milk_fracs.append((prod, a["qty"] / pool_qty, a["price"]))

    out: dict = {}
    for rid, item, reason, qty in classified:
        if item == MILK:
            lines = []
            for prod, frac, price in milk_fracs:
                pq = qty * frac
                lines.append({
                    "planning_item": prod,
                    "reason": reason,
                    "planned_quantity": pq,
                    "unit_price": price,
                    "planned_cif": (pq * price) if price is not None else None,
                })
            out[rid] = lines
        else:
            eff_rate = _effective_rate(alloc.get(item))
            out[rid] = [{
                "planning_item": item,
                "reason": reason,
                "planned_quantity": qty,
                "unit_price": eff_rate,
                "planned_cif": (qty * eff_rate) if eff_rate is not None else None,
            }]
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
