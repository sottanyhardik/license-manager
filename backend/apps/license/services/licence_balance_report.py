"""Canonical licence item balance report (CIF and quantity), read from the database.

This is the single consumer-facing calculation for item balances. It reads the source
records once per request for a set of licences, classifies every movement by its
actual relationships (BOE membership, allocation rows, allotment membership) and calls
the approved pure calculators:

- `sale_boe_allocation.compute_utilisation` (sale/BOE rule)
- `licence_item_balance.build_item_balance` / `aggregate_items` (four-component view)

Nothing here writes to the database.

Known and deliberate limits (see docs/09-module-implementation/licence-cif-quantity-balance-open-decisions.md):
- Previous-owner BOEs are debited like any other BOE, so they reduce Available CIF and Available
  quantity (decision O-8, approved). Ownership comes only from the BOE hide/restore audit trail
  (`annotate_and_exclude_hidden`), never from importer name or BOE date. They are reported
  separately (`previous_owner`, `previous_owner_debit_*`) so audit can tell them apart.
- Quantities in units other than `kg` are reported as UNIT UNVERIFIED and are excluded from
  licence quantity totals (decision O-1).
- A BOE on item X that is linked to a sale of another item is treated as uncovered on X and
  flagged CROSS-ITEM (decision O-2).
- Allotment residue uses the BOE debit on the same item within linked BOEs (D-1 §3.4).
- The legacy engine figure (`legacy_balance_cif`) is returned for comparison only. It uses the
  older purchase/opening rules and is flagged when it differs.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from apps.license.services.licence_item_balance import (
    OVER_UTILISED,
    RECONCILED,
    REVIEW_REQUIRED,
    UNIT_UNVERIFIED,
    UNMAPPED_ITEM,
    aggregate_items,
    build_item_balance,
    normalise_unit,
)
from apps.license.services.effective_cif_mode import INDIVIDUAL_ITEM, resolve_effective_cif_mode
from apps.license.services.sale_boe_allocation import (
    AllocationError,
    BoeEntry,
    BoeLink,
    SaleEntry,
)

ZERO = Decimal("0")
OVER_ALLOCATED = "OVER-ALLOCATED"
MISMATCH = "MISMATCH"
LEGACY_TOLERANCE = Decimal("0.01")

MOVEMENT_ORIGINAL = "ORIGINAL"
MOVEMENT_SALE = "SALE"
MOVEMENT_SALE_COVERED_BOE = "SALE_COVERED_BOE"
MOVEMENT_BOE_DEBIT = "BOE_DEBIT"
MOVEMENT_OVER_LINKED = "OVER_LINKED_EXCESS"
MOVEMENT_ALLOTMENT = "ALLOTMENT"

PREVIOUS_OWNER_DEDUCTED = "PREVIOUS OWNER — DEDUCTED"
PREVIOUS_OWNER_PARTLY = "PREVIOUS OWNER — PARTLY DEDUCTED"
PREVIOUS_OWNER_COVERED = "PREVIOUS OWNER — COVERED BY SALE"
CROSS_ITEM_STATUS = "LINKED TO ANOTHER ITEM'S SALE (review)"
OVER_LINKED_BOE_STATUS = "LINKED TO AN OVER-LINKED SALE (excess counted on the invoice)"

# CIF control mode. Only a persisted literal True (Individual Item CIF ON) enforces CIF per item.
# Every other licence (NULL or False) is controlled at licence level: item CIF is attribution only.
CIF_CONTROL_LICENCE = "LICENCE"
CIF_CONTROL_ITEM = "ITEM"
LICENCE_CONTROL_STATUS = "LICENCE-LEVEL CONTROL"
# Item CIF attribution is REVIEW REQUIRED when any of these flags applies to the item.
CIF_ATTRIBUTION_FLAGS = frozenset({
    "CROSS_ITEM",
    "ALLOT_AND_SALE_OVERLAP_UNVERIFIED",
    "ALLOTMENT_LINKED_BOE_NOT_ON_ITEM",
    "OVER_LINKED_MIXED_OWNERSHIP",
})
# Set on a licence whose CIF over-utilisation result depends on how unverified sales are classified.
LICENCE_CIF_UNVERIFIED_FLAG = "LICENCE_CIF_DEPENDS_ON_UNVERIFIED_SALE"


def _s(value) -> str:
    return "" if value is None else str(value)


def _money(value) -> Optional[str]:
    return None if value is None else format(Decimal(value).quantize(Decimal("0.01")), "f")


def _qty(value) -> Optional[str]:
    return None if value is None else format(Decimal(value).quantize(Decimal("0.001")), "f")


def previous_owner_status(covered, debit) -> str:
    """Status of a previous-owner BOE. Its sale-covered part is not a second debit."""
    if debit <= ZERO:
        return PREVIOUS_OWNER_COVERED
    return PREVIOUS_OWNER_PARTLY if covered > ZERO else PREVIOUS_OWNER_DEDUCTED


def debit_row_status(*, previous_owner, cross, over_linked, covered, uncovered) -> str:
    """Status of one BOE debit row. Shared by the transactions endpoint, the ledger and the drill-down."""
    if cross:
        return CROSS_ITEM_STATUS
    if over_linked:
        return OVER_LINKED_BOE_STATUS
    if previous_owner:
        return previous_owner_status(covered, uncovered)
    if covered == ZERO:
        return "UNCOVERED"
    if uncovered == ZERO:
        return "COVERED BY SALE"
    return "PARTIALLY COVERED"


def over_linked_excess(sales_by_trade, links):
    """Per sale whose linked BOEs exceed it: (excess CIF, excess qty, BOE row ids linked to that sale)."""
    linked = defaultdict(lambda: {"cif": ZERO, "qty": ZERO, "rows": set()})
    for _lid, rd, trade_id, c, q in links:
        linked[trade_id]["cif"] += c
        linked[trade_id]["qty"] += q
        linked[trade_id]["rows"].add(rd.id)
    out = {}
    for trade_id, t in sales_by_trade.items():
        ex_c = max(ZERO, linked[trade_id]["cif"] - t["cif"])
        ex_q = max(ZERO, linked[trade_id]["qty"] - t["qty"])
        if ex_c > ZERO or ex_q > ZERO:
            out[trade_id] = (ex_c, ex_q, linked[trade_id]["rows"])
    return out


def excess_owner(row_ids, previous_owner_ids) -> str:
    """'previous' when every linked BOE is previous-owner, 'current' when none is, else 'mixed' (not attributable)."""
    flags = [rid in previous_owner_ids for rid in row_ids]
    if flags and all(flags):
        return "previous"
    if any(flags):
        return "mixed"
    return "current"


def coverage_by_row(links, is_qty: bool):
    """Sale-linked amount per BOE debit row (RowDetails id)."""
    covered = defaultdict(lambda: ZERO)
    for _lid, rd, _trade_id, c, q in links:
        covered[rd.id] += q if is_qty else c
    return covered


@dataclass
class MovementRow:
    kind: str
    date: Optional[date]
    reference: str
    customer: str
    sr: str
    measure: str
    debit: Decimal
    credit: Decimal
    running_balance: Optional[Decimal]
    link_status: str
    source_type: str
    source_id: str
    memo: bool = False
    previous_owner: bool = False

    def payload(self):
        is_qty = self.measure == "qty"
        fmt = _qty if is_qty else _money
        return {
            "kind": self.kind,
            "date": self.date.isoformat() if self.date else None,
            "reference": self.reference,
            "customer": self.customer,
            "sr": self.sr,
            "debit": fmt(self.debit) if self.debit is not None else None,
            "credit": fmt(self.credit) if self.credit is not None else None,
            "running_balance": fmt(self.running_balance) if self.running_balance is not None else None,
            "link_status": self.link_status,
            "source": {"type": self.source_type, "id": self.source_id},
            "memo": self.memo,
            "previous_owner": self.previous_owner,
        }


@dataclass
class ItemReport:
    item_id: int
    sr: str
    description: str
    hs_code: Optional[str]
    unit_raw: Optional[str]
    unit: Optional[str]
    unit_status: str
    cif: dict = field(default_factory=dict)
    qty: dict = field(default_factory=dict)
    status: str = RECONCILED
    flags: list = field(default_factory=list)
    # Previous-owner BOE debit already inside `debited`. None quantity while the unit is unverified.
    previous_owner_debit_cif: Decimal = ZERO
    previous_owner_debit_qty: Optional[Decimal] = ZERO
    cif_ledger: list = field(default_factory=list)
    qty_ledger: list = field(default_factory=list)
    customers: list = field(default_factory=list)


@dataclass
class LicenceReport:
    license_id: int
    license_number: str
    importer: str
    expiry_date: Optional[date]
    items: list = field(default_factory=list)
    summary_cif: dict = field(default_factory=dict)
    summary_qty: dict = field(default_factory=dict)
    unverified_qty_items: list = field(default_factory=list)
    previous_owner_debit_cif: Decimal = ZERO
    previous_owner_debit_qty: Optional[Decimal] = ZERO
    legacy_balance_cif: Optional[Decimal] = None
    legacy_status: str = ""
    status: str = RECONCILED
    flags: list = field(default_factory=list)
    cif_control: str = CIF_CONTROL_ITEM
    cif_scenarios: dict = field(default_factory=dict)


def _load(license_ids):
    """Read every source needed for the given licences, in a fixed number of queries."""
    from apps.allotment.models import AllotmentItems
    from apps.bill_of_entry.models import BillOfEntryModel, RowDetails, annotate_and_exclude_hidden
    from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
    from apps.reconciliation.models import InvoiceBOEAllocation
    from apps.trade.models import LicenseTrade, LicenseTradeLine

    licences = list(
        LicenseDetailsModel.objects.filter(pk__in=license_ids)
        .select_related("exporter")
        .order_by("license_expiry_date", "license_number", "id")
    )
    items = list(
        LicenseImportItemsModel.objects.filter(license_id__in=license_ids)
        .select_related("hs_code")
        .order_by("license_id", "serial_number", "id")
    )
    item_ids = [i.id for i in items]

    norm_by_license = defaultdict(set)
    for lic_id, norm in LicenseExportItemModel.objects.filter(license_id__in=license_ids, norm_class__isnull=False).values_list("license_id", "norm_class__norm_class"):
        norm_by_license[lic_id].add(norm)

    lines = list(
        LicenseTradeLine.objects.filter(sr_number_id__in=item_ids, trade__direction="SALE")
        .select_related("trade__to_company")
        .order_by("trade__invoice_date", "id")
    )
    trade_ids = {line.trade_id for line in lines}
    from apps.trade.models import TradeUtilisationClassification

    # Only an explicit INTERNAL record removes a trade from external utilisation. No record means EXTERNAL.
    trade_classifications = {
        c.trade_id: c
        for c in TradeUtilisationClassification.objects.filter(trade_id__in=trade_ids).select_related("authorised_by")
    }
    internal_trade_ids = {
        tid for tid, c in trade_classifications.items() if c.classification == TradeUtilisationClassification.CLASS_INTERNAL
    }
    trade_boe_members = defaultdict(set)
    boe_trades = defaultdict(set)
    for trade_id, bid in LicenseTrade.boes.through.objects.filter(
        licensetrade_id__in=trade_ids
    ).values_list("licensetrade_id", "billofentrymodel_id"):
        trade_boe_members[trade_id].add(bid)
        boe_trades[bid].add(trade_id)

    rows_all = list(
        RowDetails.objects.filter(sr_number_id__in=item_ids, transaction_type="D")
        .select_related("bill_of_entry__port", "bill_of_entry__company")
        .order_by("bill_of_entry__bill_of_entry_date", "id")
    )
    # Previous-owner BOEs: the hide/restore audit trail says they are hidden. Their debit is deducted.
    previous_owner_ids = set(
        annotate_and_exclude_hidden(
            RowDetails.objects.filter(sr_number_id__in=item_ids, transaction_type="D"),
            boe_field="bill_of_entry",
            hidden_only=True,
        ).values_list("id", flat=True)
    )

    allocations = {}
    for rd_id, line_id, cif_amt, qty_amt in InvoiceBOEAllocation.objects.filter(
        row_details__sr_number_id__in=item_ids,
        is_current=True,
        status=InvoiceBOEAllocation.STATUS_ACTIVE,
    ).values_list("row_details_id", "trade_line_id", "allocated_cif_fc", "allocated_qty"):
        allocations[(rd_id, line_id)] = (Decimal(cif_amt or 0), Decimal(qty_amt or 0))

    allot_items = list(
        AllotmentItems.objects.filter(item_id__in=item_ids, status="CREATED")
        .select_related("allotment__company")
        .order_by("id")
    )
    allotment_boes = defaultdict(set)
    for allot_id, bid in BillOfEntryModel.allotment.through.objects.filter(
        allotmentmodel_id__in={a.allotment_id for a in allot_items}
    ).values_list("allotmentmodel_id", "billofentrymodel_id"):
        allotment_boes[allot_id].add(bid)

    return {
        "licences": licences,
        "internal_trade_ids": internal_trade_ids,
        "trade_classifications": trade_classifications,
        "items": items,
        "norms": norm_by_license,
        "lines": lines,
        "trade_boe_members": trade_boe_members,
        "boe_trades": boe_trades,
        "rows": rows_all,
        "previous_owner_ids": previous_owner_ids,
        "allocations": allocations,
        "allot_items": allot_items,
        "allotment_boes": allotment_boes,
    }


def _sales_from_lines(lines):
    """Group sale lines by trade. Money and quantity are summed as Decimal."""
    sales_by_trade = defaultdict(lambda: {"cif": ZERO, "qty": ZERO, "inr": ZERO, "lines": [], "customer": "", "invoice": "", "date": None})
    for line in lines:
        t = sales_by_trade[line.trade_id]
        t["cif"] += Decimal(line.cif_fc or 0)
        t["inr"] += Decimal(line.cif_inr or 0)
        t["qty"] += Decimal(line.qty_kg or 0)
        t["lines"].append(line)
        t["customer"] = line.trade.to_company.name if line.trade.to_company_id else ""
        t["invoice"] = line.trade.invoice_number
        t["date"] = line.trade.invoice_date
    return sales_by_trade


def _internal_sales_by_trade(item, data):
    """INTERNAL sale trades on one item. Shown for audit only; they never enter utilisation."""
    internal = data.get("internal_trade_ids", set())
    return _sales_from_lines([l for l in data["lines_by_item"].get(item.id, []) if l.trade_id in internal])


def _item_inputs(item, data):
    """Assemble sale/BOE/link inputs for one item, following the approved rule."""
    internal = data.get("internal_trade_ids", set())
    # External sales only. An INTERNAL trade's lines are excluded here, so they cannot be matched to
    # a BOE, reduce the balance, or be counted as over-linked. Its own BOE debits still count (below).
    item_lines = [l for l in data["lines_by_item"].get(item.id, []) if l.trade_id not in internal]
    sales_by_trade = _sales_from_lines(item_lines)

    # Every debit row counts once. Previous ownership changes the label, never the arithmetic.
    debit_rows = data["rows_by_item"].get(item.id, [])

    links = []  # (link_id, rd, trade_id, cif, qty)
    cross = []  # (rd, trade_id)
    for trade_id, t in sales_by_trade.items():
        line_id = t["lines"][0].id
        for rd in debit_rows:
            if rd.bill_of_entry_id not in data["trade_boe_members"].get(trade_id, set()):
                continue
            alloc = data["allocations"].get((rd.id, line_id))
            a_cif, a_qty = alloc if alloc else (Decimal(rd.cif_fc or 0), Decimal(rd.qty or 0))
            links.append((f"L{rd.id}-T{trade_id}", rd, trade_id, a_cif, a_qty))
    for rd in debit_rows:
        for trade_id in data["boe_trades"].get(rd.bill_of_entry_id, set()):
            if trade_id not in sales_by_trade:
                cross.append((rd, trade_id))

    # Each entry: (allotment_id, allotment_item_id, outstanding cif, outstanding qty, linked_boe_not_on_this_item).
    allot_residue = []
    for ai in data["allot_by_item"].get(item.id, []):
        link = allotment_link(ai, data, debit_rows)
        allot_residue.append((ai.allotment_id, ai.id, link.outstanding_cif, link.outstanding_qty, link.elsewhere))

    return sales_by_trade, debit_rows, links, cross, allot_residue


@dataclass(frozen=True)
class AllotmentLink:
    """How one allotment item is converted to BOEs on its item.

    `boe_linked_*` is the valid, current BOE-linked amount on this item. It is the utilisation.
    `outstanding_cif` is always zero once a BOE on this item is linked. The difference between the original
    allotment CIF and the BOE-linked CIF is ignored everywhere: it is not reserved, not outstanding and not a
    debit. Quantity keeps its own rule, which is unchanged.
    """

    original_cif: Decimal
    original_qty: Decimal
    boe_linked_cif: Decimal
    boe_linked_qty: Decimal
    outstanding_cif: Decimal
    outstanding_qty: Decimal
    elsewhere: bool


def allotment_link(ai, data, debit_rows) -> AllotmentLink:
    """The one definition of an allotment's BOE conversion, shared by the balance, the drill-down and the workspace."""
    a_cif = Decimal(ai.cif_fc or 0)
    a_qty = Decimal(ai.qty or 0)
    bids = data["allotment_boes"].get(ai.allotment_id, set())
    if not bids:
        # No BOE link: the whole allotment is reserved for the customer (D-1 §3.4).
        return AllotmentLink(a_cif, a_qty, ZERO, ZERO, a_cif, a_qty, False)
    matched_c = sum((Decimal(r.cif_fc or 0) for r in debit_rows if r.bill_of_entry_id in bids), ZERO)
    matched_q = sum((Decimal(r.qty or 0) for r in debit_rows if r.bill_of_entry_id in bids), ZERO)
    # A BOE linked to the allotment that debits a different licence (or none of this item) is a review case.
    # It keeps the whole allotment outstanding, as before.
    if matched_c == ZERO:
        return AllotmentLink(a_cif, a_qty, ZERO, ZERO, a_cif, max(ZERO, a_qty - min(a_qty, matched_q)), True)
    boe_c = min(a_cif, matched_c)
    boe_q = min(a_qty, matched_q)
    # CIF: the difference is ignored, so nothing is outstanding once a BOE on this item is linked.
    # Quantity: unchanged rule, the quantity not matched by a BOE stays outstanding.
    return AllotmentLink(a_cif, a_qty, boe_c, boe_q, ZERO, max(ZERO, a_qty - boe_q), False)


def _measure_inputs(measure, sales_by_trade, debit_rows, links, allot_residue):
    if measure == "cif":
        sales = [SaleEntry(f"T{t}", v["cif"]) for t, v in sales_by_trade.items()]
        boes = [BoeEntry(f"R{r.id}", cif=Decimal(r.cif_fc or 0)) for r in debit_rows]
        link_objs = [BoeLink(lid, f"R{rd.id}", f"T{t}", cif=c) for lid, rd, t, c, _q in links]
        allot = sum((c for _a, _ai, c, _q, _e in allot_residue), ZERO)
    else:
        sales = [SaleEntry(f"T{t}", qty=v["qty"]) for t, v in sales_by_trade.items()]
        boes = [BoeEntry(f"R{r.id}", qty=Decimal(r.qty or 0)) for r in debit_rows]
        link_objs = [BoeLink(lid, f"R{rd.id}", f"T{t}", qty=q) for lid, rd, t, _c, q in links]
        allot = sum((q for _a, _ai, _c, q, _e in allot_residue), ZERO)
    return sales, boes, link_objs, allot


def _ledger(item, measure, sales_by_trade, debit_rows, links, cross, allot_residue, original, previous_owner_ids, license_number, internal_sales=None):
    """Movement rows for one measure, with a running balance that ends at Available."""
    is_qty = measure == "qty"
    get = (lambda r: Decimal(r.qty or 0)) if is_qty else (lambda r: Decimal(r.cif_fc or 0))
    sr = item.serial_number
    rows = []
    running = Decimal(original or ZERO)
    rows.append(MovementRow(MOVEMENT_ORIGINAL, None, license_number, "", _s(sr), measure, None, original, original, "Licence authorisation", "licence", str(item.license_id)))

    covered_by_row = coverage_by_row(links, is_qty)
    covered_by_trade = defaultdict(lambda: ZERO)
    for lid, rd, trade_id, c, q in links:
        covered_by_trade[trade_id] += q if is_qty else c

    sale_entries = []
    for trade_id, t in sales_by_trade.items():
        sold = t["qty"] if is_qty else t["cif"]
        linked = covered_by_trade[trade_id]
        if linked == ZERO:
            status = "NOT LINKED"
        elif linked > sold:
            status = "OVER-LINKED"
        elif linked == sold:
            status = "COVERED BY SALE"
        else:
            status = "PARTIALLY COVERED"
        sale_entries.append((t["date"] or date.min, trade_id, t, sold, linked, status))
    for _d, trade_id, t, sold, linked, status in sorted(sale_entries, key=lambda e: (e[0], e[1])):
        rows.append(MovementRow(MOVEMENT_SALE, t["date"], t["invoice"], t["customer"], _s(sr), measure, sold, None, None, status, "trade", str(trade_id)))
        for lid, rd, tid, c, q in links:
            if tid != trade_id:
                continue
            rows.append(MovementRow(MOVEMENT_SALE_COVERED_BOE, rd.bill_of_entry.bill_of_entry_date, _s(rd.bill_of_entry.bill_of_entry_number), t["customer"], _s(sr), measure, None, None, None, "Covered by sale (not an extra deduction)", "bill_of_entry", str(rd.bill_of_entry_id), memo=True, previous_owner=rd.id in previous_owner_ids))
        if linked > sold:
            rows.append(MovementRow(MOVEMENT_OVER_LINKED, t["date"], t["invoice"], t["customer"], _s(sr), measure, linked - sold, None, None, "OVER-LINKED: excess BOE counted as utilisation", "trade", str(trade_id)))

    for trade_id, t in sorted((internal_sales or {}).items(), key=lambda e: (e[1]["date"] or date.min, e[0])):
        sold = t["qty"] if is_qty else t["cif"]
        rows.append(MovementRow(MOVEMENT_SALE, t["date"], t["invoice"], t["customer"], _s(sr), measure, sold, None, None,
                                "INTERNAL TRADE: not external utilisation", "trade", str(trade_id), memo=True))

    for rd in debit_rows:
        remainder = get(rd) - covered_by_row[rd.id]
        if remainder <= ZERO:
            continue
        previous_owner = rd.id in previous_owner_ids
        in_cross = any(r.id == rd.id for r, _t in cross)
        status = debit_row_status(previous_owner=previous_owner, cross=in_cross, over_linked=False, covered=covered_by_row[rd.id], uncovered=remainder)
        rows.append(MovementRow(MOVEMENT_BOE_DEBIT, rd.bill_of_entry.bill_of_entry_date, _s(rd.bill_of_entry.bill_of_entry_number), "", _s(sr), measure, remainder, None, None, status, "bill_of_entry", str(rd.bill_of_entry_id), previous_owner=previous_owner))

    for allot_id, ai_id, c, q, _elsewhere in allot_residue:
        amt = q if is_qty else c
        if amt <= ZERO:
            continue
        rows.append(MovementRow(MOVEMENT_ALLOTMENT, None, f"ALLOT-{allot_id}", "", _s(sr), measure, amt, None, None, "OUTSTANDING RESERVATION", "allotment_item", str(ai_id)))

    # Running balance over non-memo rows, in display order.
    for row in rows:
        if row.memo or row.kind == MOVEMENT_ORIGINAL:
            row.running_balance = running if row.kind == MOVEMENT_ORIGINAL else None
            continue
        running = running - (row.debit or ZERO)
        row.running_balance = running
    return rows


def _item_report(item, data, license_number, cif_control=CIF_CONTROL_ITEM):
    sales_by_trade, debit_rows, links, cross, allot_residue = _item_inputs(item, data)
    internal_sales = _internal_sales_by_trade(item, data)
    previous_owner_ids = data["previous_owner_ids"]
    unit_norm, unit_status = normalise_unit(item.unit)
    original_cif = Decimal(item.cif_fc or 0)
    original_qty = Decimal(item.quantity or 0)
    out = ItemReport(
        item_id=item.id,
        sr=_s(item.serial_number),
        description=item.description or "",
        hs_code=item.hs_code.hs_code if item.hs_code_id else None,
        unit_raw=item.unit,
        unit=unit_norm,
        unit_status=unit_status,
    )
    # Previous-owner debit (already inside `debited`): the uncovered part of each previous-owner BOE,
    # plus any over-linked excess whose linked BOEs are all previous-owner. Mixed excess stays current-owner.
    cov_c = coverage_by_row(links, False)
    cov_q = coverage_by_row(links, True)
    po_rows = [r for r in debit_rows if r.id in previous_owner_ids]
    po_c = sum((max(ZERO, Decimal(r.cif_fc or 0) - cov_c[r.id]) for r in po_rows), ZERO)
    po_q = sum((max(ZERO, Decimal(r.qty or 0) - cov_q[r.id]) for r in po_rows), ZERO)
    mixed = False
    for _trade_id, (ex_c, ex_q, row_ids) in over_linked_excess(sales_by_trade, links).items():
        owner = excess_owner(row_ids, previous_owner_ids)
        if owner == "previous":
            po_c += ex_c
            po_q += ex_q
        elif owner == "mixed":
            mixed = True
    out.previous_owner_debit_cif = po_c
    out.previous_owner_debit_qty = None if unit_status == UNIT_UNVERIFIED else po_q

    if cross:
        out.flags.append("CROSS_ITEM")
    # An internal transfer consumes nothing, so the item's final external sale decides utilisation. When the item
    # has an internal transfer but no external sale recorded, that end of the chain is unknown: REVIEW, not RECONCILED.
    if internal_sales and not sales_by_trade:
        out.flags.append("INTERNAL_TRANSFER_NO_EXTERNAL_SALE")
    # An external sale to a group company with no matched purchase: REVIEW, and still counted until resolved.
    if any(tid in data.get("unmatched_group_sale_ids", set()) for tid in sales_by_trade):
        out.flags.append("UNMATCHED_INTERNAL_TRANSACTION")
    # The overlap flag is raised by each measure's own outstanding allotment only. A CIF difference that is
    # ignored (already BOE-linked) therefore never reaches quantity status, and quantity never depends on CIF.
    overlap_by_measure = {
        "cif": bool(sales_by_trade) and any(c for _a, _ai, c, _q, _e in allot_residue),
        "qty": bool(sales_by_trade) and any(q for _a, _ai, _c, q, _e in allot_residue),
    }
    if overlap_by_measure["cif"] or overlap_by_measure["qty"]:
        out.flags.append("ALLOT_AND_SALE_OVERLAP_UNVERIFIED")
    if any(e for _a, _ai, _c, _q, e in allot_residue):
        out.flags.append("ALLOTMENT_LINKED_BOE_NOT_ON_ITEM")
    if mixed:
        out.flags.append("OVER_LINKED_MIXED_OWNERSHIP")

    for measure in ("cif", "qty"):
        original = original_cif if measure == "cif" else original_qty
        try:
            sales, boes, link_objs, allot = _measure_inputs(measure, sales_by_trade, debit_rows, links, allot_residue)
            measure_flags = [f for f in out.flags if f != "ALLOT_AND_SALE_OVERLAP_UNVERIFIED" or overlap_by_measure[measure]]
            result = build_item_balance(
                measure=measure, original=original, sales=sales, boes=boes, links=link_objs,
                outstanding_allotment=allot, unit=item.unit if measure == "qty" else None,
                extra_flags=measure_flags,
            )
            payload = {
                "original": _qty(result.original) if measure == "qty" else _money(result.original),
                "debited": _qty(result.debited) if measure == "qty" else _money(result.debited),
                "allotted": _qty(result.allotted) if measure == "qty" else _money(result.allotted),
                "invoiced": _qty(result.invoiced) if measure == "qty" else _money(result.invoiced),
                "invoiced_boe_covered": _qty(result.invoiced_boe_covered) if measure == "qty" else _money(result.invoiced_boe_covered),
                "available": _qty(result.available) if measure == "qty" else _money(result.available),
                "is_over_utilised": result.is_over_utilised,
                "unit": None if measure == "cif" else unit_norm,
                "status": result.status,
                "flags": list(result.flags),
                "identity_ok": result.identity_ok,
                "_obj": result,
            }
        except AllocationError as exc:
            payload = {"error": str(exc)[:200], "status": OVER_ALLOCATED, "available": None, "_obj": None}
        out.flags.extend(f for f in (payload.get("flags") or []) if f not in out.flags)
        if measure == "cif":
            out.cif = payload
        else:
            out.qty = payload

        if payload.get("_obj") is not None or measure == "cif":
            ledger = _ledger(item, measure, sales_by_trade, debit_rows, links, cross, allot_residue, original, previous_owner_ids, license_number, internal_sales=internal_sales)
            if measure == "cif":
                out.cif_ledger = ledger
            else:
                out.qty_ledger = ledger

    # Customer view: sold, BOE-covered (capped at the sale) and remaining entitlement, per trade.
    link_totals = defaultdict(lambda: ZERO)
    for _lid, _rd, tid, c, _q in links:
        link_totals[tid] += c
    out.customers = []
    for tid, t in sales_by_trade.items():
        covered = min(t["cif"], link_totals[tid])
        out.customers.append({
            "customer": t["customer"],
            "invoice": t["invoice"],
            "sold": _money(t["cif"]),
            "sold_qty": _qty(t["qty"]),
            "covered_by_boe": _money(covered),
            "remaining_entitlement": _money(t["cif"] - covered),
        })

    if cif_control == CIF_CONTROL_LICENCE and out.cif and out.cif.get("_obj") is not None:
        _attribute_item_cif(out)

    # Item status is the most severe of the CIF and quantity results.
    statuses = [block.get("status") for block in (out.cif, out.qty) if block]
    statuses = [st for st in statuses if st != LICENCE_CONTROL_STATUS]
    if OVER_ALLOCATED in statuses:
        out.status = OVER_ALLOCATED
    elif OVER_UTILISED in statuses:
        out.status = OVER_UTILISED
    elif UNMAPPED_ITEM in statuses:
        out.status = UNMAPPED_ITEM
    elif any(st != RECONCILED for st in statuses) or out.flags or unit_status == UNIT_UNVERIFIED:
        out.status = REVIEW_REQUIRED
    else:
        out.status = RECONCILED
    return out


def _attribute_item_cif(out: ItemReport) -> None:
    """Licence-level control: the item CIF figures stay, but the item is not OVER-UTILISED by its own CIF.

    The item's negative CIF is attribution for the licence's pooled CIF. It is REVIEW REQUIRED only when
    the attribution cannot be verified. Quantity status is untouched.
    """
    block = out.cif
    # A raw REVIEW REQUIRED keeps its own reason (any flag on the item), so only the CIF over-utilisation is removed.
    unverified = block.get("status") == REVIEW_REQUIRED or bool(CIF_ATTRIBUTION_FLAGS.intersection(out.flags))
    block["raw_status"] = block.get("status")
    block["cif_control"] = CIF_CONTROL_LICENCE
    block["is_over_utilised"] = False
    block["status"] = REVIEW_REQUIRED if unverified else LICENCE_CONTROL_STATUS


def _unverified_sale_trade_ids(data, item_ids) -> set:
    """Sale trades on these items with no classification record, or a REVIEW record. No record means EXTERNAL."""
    from apps.trade.models import TradeUtilisationClassification

    unverified = set()
    for item_id in item_ids:
        for line in data["lines_by_item"].get(item_id, []):
            record = data["trade_classifications"].get(line.trade_id)
            if record is None or record.classification == TradeUtilisationClassification.CLASS_REVIEW:
                unverified.add(line.trade_id)
    return unverified


def _apply_licence_cif_control(report: LicenceReport, unverified: set, alternative_available) -> None:
    """Set the licence CIF status for a licence-level control licence from the pooled figure.

    base: every unverified sale is EXTERNAL (the conservative reading).
    alternative: every unverified sale is INTERNAL.
    - base not negative -> no CIF over-utilisation.
    - base negative, no unverified sale -> OVER-UTILISED.
    - base negative, alternative also negative -> OVER-UTILISED (flagged as resting on unverified sales).
    - base negative, alternative not negative -> REVIEW REQUIRED (the outcome depends on classification).
    """
    base = Decimal(report.summary_cif["available"])
    report.cif_scenarios = {
        "base_available": base,
        "alternative_available": alternative_available,
        "unverified_trade_ids": sorted(unverified),
    }
    if base >= ZERO:
        status, over = RECONCILED, False
    elif not unverified:
        status, over = OVER_UTILISED, True
    elif alternative_available is not None and Decimal(alternative_available) < ZERO:
        status, over = OVER_UTILISED, True
        report.flags.append(LICENCE_CIF_UNVERIFIED_FLAG)
    else:
        status, over = REVIEW_REQUIRED, False
        report.flags.append(LICENCE_CIF_UNVERIFIED_FLAG)
    report.summary_cif["status"] = status
    report.summary_cif["is_over_utilised"] = over


def _unmatched_group_sale_ids(data) -> set:
    """External sales between two registered group companies that have no matched purchase.

    They stay in utilisation for now (nothing is classified silently) and are flagged for review.
    Matching uses the persisted COPIED pair or the same invoice, parties, date and lines. See
    apps.trade.services.internal_transfers.
    """
    from apps.trade.services.internal_transfers import is_group_transfer, match_counterpart_purchase

    internal = data.get("internal_trade_ids", set())
    trades = {}
    for lines in data["lines_by_item"].values():
        for line in lines:
            if line.trade_id not in internal and line.trade_id not in trades and is_group_transfer(line.trade):
                trades[line.trade_id] = line.trade
    return {tid for tid, trade in trades.items() if match_counterpart_purchase(trade) is None}


def _index(data):
    """Group loaded rows by item so per-item classification is a dictionary lookup."""
    data["lines_by_item"] = defaultdict(list)
    for line in data["lines"]:
        data["lines_by_item"][line.sr_number_id].append(line)
    data["rows_by_item"] = defaultdict(list)
    for r in data["rows"]:
        data["rows_by_item"][r.sr_number_id].append(r)
    data["allot_by_item"] = defaultdict(list)
    for ai in data["allot_items"]:
        data["allot_by_item"][ai.item_id].append(ai)
    return data


def build_licence_balance_reports(license_ids, *, include_legacy: bool = True, internal_trade_ids=None):
    """Return {licence_id: LicenceReport} for the given licences. Fixed query count, independent of page size."""
    from apps.license.services.balance_calculator import LicenseBalanceCalculator

    license_ids = list(dict.fromkeys(int(i) for i in license_ids))
    if not license_ids:
        return {}
    data = _load(license_ids)
    if internal_trade_ids is not None:
        # Evidence runs only: treat these trades as internal without writing a classification record.
        data["internal_trade_ids"] = set(internal_trade_ids)
    _index(data)
    data["unmatched_group_sale_ids"] = _unmatched_group_sale_ids(data)

    items_by_licence = defaultdict(list)
    for item in data["items"]:
        items_by_licence[item.license_id].append(item)

    reports = {}
    for lic in data["licences"]:
        report = LicenceReport(
            license_id=lic.id,
            license_number=lic.license_number,
            importer=lic.exporter.name if lic.exporter_id else "",
            expiry_date=lic.license_expiry_date,
        )
        report.cif_control = CIF_CONTROL_ITEM if resolve_effective_cif_mode(lic) == INDIVIDUAL_ITEM else CIF_CONTROL_LICENCE
        report.items = [
            _item_report(item, data, lic.license_number, report.cif_control)
            for item in items_by_licence.get(lic.id, [])
        ]
        report.previous_owner_debit_cif = sum((i.previous_owner_debit_cif for i in report.items), ZERO)
        po_qty = [i.previous_owner_debit_qty for i in report.items]
        report.previous_owner_debit_qty = None if any(q is None for q in po_qty) else sum(po_qty, ZERO)

        cif_parts = [i.cif["_obj"] for i in report.items if i.cif.get("_obj") is not None]
        if cif_parts and len(cif_parts) == len(report.items):
            total = aggregate_items(cif_parts)
            report.summary_cif = {
                "original": _money(total.original), "debited": _money(total.debited),
                "allotted": _money(total.allotted), "invoiced": _money(total.invoiced),
                "invoiced_boe_covered": _money(total.invoiced_boe_covered),
                "available": _money(total.available), "is_over_utilised": total.is_over_utilised,
                "status": total.status,
            }
        elif not report.items:
            # No SION items: no authorised item CIF, so nothing is utilised. Stated as an exception, not left blank.
            report.summary_cif = {
                "original": _money(ZERO), "debited": _money(ZERO), "allotted": _money(ZERO), "invoiced": _money(ZERO),
                "invoiced_boe_covered": _money(ZERO), "available": _money(ZERO), "is_over_utilised": False,
                "status": REVIEW_REQUIRED,
            }
            report.flags.append("NO_SION_ITEMS")
        else:
            report.summary_cif = {"status": OVER_ALLOCATED if any(i.status == OVER_ALLOCATED for i in report.items) else REVIEW_REQUIRED}

        verified_qty, unverified_qty = [], []
        for i in report.items:
            obj = i.qty.get("_obj")
            if obj is None:
                continue
            (verified_qty if i.unit_status != UNIT_UNVERIFIED else unverified_qty).append(obj)
        report.unverified_qty_items = [{"item_id": i.item_id, "sr": i.sr, "unit_raw": i.unit_raw, "status": UNIT_UNVERIFIED} for i in report.items if i.unit_status == UNIT_UNVERIFIED]
        if verified_qty and not any(i.unit_status == UNIT_UNVERIFIED for i in report.items):
            total_q = aggregate_items(verified_qty)
            report.summary_qty = {
                "original": _qty(total_q.original), "debited": _qty(total_q.debited),
                "allotted": _qty(total_q.allotted), "invoiced": _qty(total_q.invoiced),
                "available": _qty(total_q.available), "is_over_utilised": total_q.is_over_utilised,
                "unit": total_q.unit, "status": total_q.status,
            }
        else:
            report.summary_qty = {
                "status": UNIT_UNVERIFIED,
                "note": "Quantity totals withheld: one or more items use a unit that is not verified.",
                "unresolved_items": len(report.unverified_qty_items),
            }

        if include_legacy:
            legacy = LicenseBalanceCalculator.calculate_financial_balance(lic)
            report.legacy_balance_cif = legacy
            cif_available = report.summary_cif.get("available")
            if cif_available is not None and abs(Decimal(cif_available) - Decimal(legacy)) > LEGACY_TOLERANCE:
                report.legacy_status = MISMATCH
                report.flags.append("LEGACY_BALANCE_DIFFERS")
            else:
                report.legacy_status = RECONCILED

        reports[lic.id] = report

    if internal_trade_ids is None:
        _apply_cif_control_scenarios(reports, data)
    for report in reports.values():
        report.status = _licence_status(report)
    return reports


def _licence_status(report: LicenceReport) -> str:
    if report.summary_cif.get("is_over_utilised"):
        return OVER_UTILISED
    if any(i.status == OVER_ALLOCATED for i in report.items):
        return OVER_ALLOCATED
    if any(i.status == UNMAPPED_ITEM for i in report.items):
        return UNMAPPED_ITEM
    if any(i.status != RECONCILED for i in report.items) or report.unverified_qty_items or report.flags:
        return REVIEW_REQUIRED
    return RECONCILED


def _apply_cif_control_scenarios(reports, data) -> None:
    """Decide the CIF status of every licence-level control licence from its pooled figure.

    A negative pooled figure that rests on unverified sales is re-run with those sales treated as INTERNAL,
    so the status can be stated as either OVER-UTILISED or REVIEW REQUIRED. Only the affected licences are re-run.
    """
    unverified_by_licence = {}
    needs_alternative = {}
    for lic_id, report in reports.items():
        if report.cif_control != CIF_CONTROL_LICENCE or "available" not in report.summary_cif:
            continue
        unverified = _unverified_sale_trade_ids(data, [i.item_id for i in report.items])
        unverified_by_licence[lic_id] = unverified
        if Decimal(report.summary_cif["available"]) < ZERO and unverified:
            needs_alternative[lic_id] = unverified

    alternative = {}
    if needs_alternative:
        every_unverified = set().union(*needs_alternative.values())
        alt_reports = build_licence_balance_reports(
            list(needs_alternative),
            include_legacy=False,
            internal_trade_ids=set(data["internal_trade_ids"]) | every_unverified,
        )
        for lic_id in needs_alternative:
            alternative[lic_id] = alt_reports[lic_id].summary_cif.get("available")

    for lic_id, unverified in unverified_by_licence.items():
        report = reports[lic_id]
        _apply_licence_cif_control(report, unverified, alternative.get(lic_id))
        report.summary_cif["cif_control"] = CIF_CONTROL_LICENCE


def serialise_licence_summary(report: LicenceReport):
    return {
        "licence_id": report.license_id,
        "licence_number": report.license_number,
        "importer": report.importer,
        "expiry_date": report.expiry_date.isoformat() if report.expiry_date else None,
        "cif": report.summary_cif,
        "qty": report.summary_qty,
        "previous_owner_debit_cif": _money(report.previous_owner_debit_cif),
        "previous_owner_debit_qty": _qty(report.previous_owner_debit_qty),
        "legacy_balance_cif": _money(report.legacy_balance_cif) if report.legacy_balance_cif is not None else None,
        "legacy_status": report.legacy_status,
        "status": report.status,
        "flags": report.flags,
        "unverified_qty_items": report.unverified_qty_items,
        "cif_control": report.cif_control,
        "cif_scenarios": _scenarios_payload(report.cif_scenarios),
    }


def _scenarios_payload(scenarios: dict) -> Optional[dict]:
    if not scenarios:
        return None
    return {
        "base_available": _money(scenarios["base_available"]),
        "alternative_available": scenarios["alternative_available"],
        "unverified_trade_ids": scenarios["unverified_trade_ids"],
    }


def available_cif_by_licence(license_ids) -> dict:
    """
    Canonical available CIF for each licence, as the same decimal string the
    workspace shows. One batch for the whole list page (fixed query count).
    Licences with no CIF figure are absent from the result.
    """
    reports = build_licence_balance_reports(license_ids, include_legacy=False)
    return {
        licence_id: serialise_licence_summary(report)["cif"].get("available")
        for licence_id, report in reports.items()
    }


def serialise_licence_detail(report: LicenceReport):
    payload = serialise_licence_summary(report)
    payload["items"] = [_with_cif_display(serialise_item(i), report) for i in report.items]
    return payload


def _with_cif_display(item_payload: dict, report: LicenceReport) -> dict:
    """Attach the Available CIF each item row displays, decided here so the frontend never chooses a source.

    Licence-level control: every row shows the licence's own available CIF. It is one balance, not an
    allocation, so it is the same value on every row and must never be summed across rows.
    Item-level control (Individual Item CIF ON): each row shows its own available CIF.
    """
    if report.cif_control == CIF_CONTROL_LICENCE:
        item_payload["cif_control"] = CIF_CONTROL_LICENCE
        item_payload["available_cif_display"] = report.summary_cif.get("available")
    else:
        item_payload["cif_control"] = CIF_CONTROL_ITEM
        item_payload["available_cif_display"] = item_payload["cif"].get("available")
    return item_payload


def serialise_item(item: ItemReport, *, include_movements: bool = False):
    def clean(block):
        return {k: v for k, v in block.items() if k != "_obj"} if block else {}

    data = {
        "item_id": item.item_id,
        "sr": item.sr,
        "description": item.description,
        "hs_code": item.hs_code,
        "unit": item.unit,
        "unit_raw": item.unit_raw,
        "unit_status": item.unit_status,
        "cif": clean(item.cif),
        "qty": clean(item.qty),
        "status": item.status,
        "flags": item.flags,
        "previous_owner_debit_cif": _money(item.previous_owner_debit_cif),
        "previous_owner_debit_qty": _qty(item.previous_owner_debit_qty),
        "customers": item.customers,
    }
    if include_movements:
        data["cif_movements"] = [r.payload() for r in item.cif_ledger]
        data["qty_movements"] = [r.payload() for r in item.qty_ledger]
    return data


def build_licence_transactions(license_id):
    """Transactions behind a licence's balance, grouped for the workspace tabs.

    Uses the same loader and per-item classification as `build_licence_balance_reports`,
    so a BOE, allotment or invoice shown here has the same effect as in the balance.
    Returns plain strings for money and quantity.
    """
    data = _index(_load([license_id]))
    previous_owner_ids = data["previous_owner_ids"]
    boes, allotments, invoices = [], [], []
    for item in data["items"]:
        sales_by_trade, debit_rows, links, cross, allot_residue = _item_inputs(item, data)
        covered_by_row = coverage_by_row(links, False)
        covered_qty_by_row = coverage_by_row(links, True)
        covered_by_trade = defaultdict(lambda: ZERO)
        for _lid, rd, trade_id, c, _q in links:
            covered_by_trade[trade_id] += c
        cross_row_ids = {rd.id for rd, _t in cross}

        # Sales whose linked BOEs exceed the sale amount (their excess is counted on the invoice).
        linked_by_trade = defaultdict(lambda: ZERO)
        for _lid, _rd, trade_id, c, _q in links:
            linked_by_trade[trade_id] += c
        over_linked_trades = {
            tid for tid, t in sales_by_trade.items() if linked_by_trade[tid] > t["cif"]
        }

        for rd in debit_rows:
            previous_owner = rd.id in previous_owner_ids
            cif = Decimal(rd.cif_fc or 0)
            covered = covered_by_row[rd.id]
            uncovered = max(ZERO, cif - covered)
            qty_amount = Decimal(rd.qty or 0)
            covered_qty = covered_qty_by_row[rd.id]
            linked_invoices = sorted({
                trade_id for _lid, r, trade_id, _c, _q in links if r.id == rd.id
            })
            status = debit_row_status(
                previous_owner=previous_owner,
                cross=rd.id in cross_row_ids,
                over_linked=any(tid in over_linked_trades for tid in linked_invoices),
                covered=covered,
                uncovered=uncovered,
            )
            boes.append({
                "item_id": item.id, "sr": _s(item.serial_number),
                "boe_number": _s(rd.bill_of_entry.bill_of_entry_number),
                "boe_date": rd.bill_of_entry.bill_of_entry_date.isoformat() if rd.bill_of_entry.bill_of_entry_date else None,
                "port": rd.bill_of_entry.port.name if rd.bill_of_entry.port_id else "",
                "customer": rd.bill_of_entry.company.name if rd.bill_of_entry.company_id else "",
                "cif_fc": _money(cif), "cif_inr": _money(rd.cif_inr), "qty": _qty(rd.qty),
                "linked_sale_trade_ids": linked_invoices,
                "linked_sale_invoices": [sales_by_trade[tid]["invoice"] for tid in linked_invoices if tid in sales_by_trade],
                "covered_cif": _money(covered), "uncovered_cif": _money(uncovered),
                "covered_qty": _qty(covered_qty), "uncovered_qty": _qty(max(ZERO, qty_amount - covered_qty)),
                "previous_owner": previous_owner, "status": status,
                "source": {"type": "bill_of_entry", "id": rd.bill_of_entry_id},
            })

        covered_totals = defaultdict(lambda: ZERO)
        for _lid, _rd, trade_id, c, _q in links:
            covered_totals[trade_id] += c
        for trade_id, t in sales_by_trade.items():
            linked = covered_totals[trade_id]
            covered = min(t["cif"], linked)
            over_linked = max(ZERO, linked - t["cif"])
            if over_linked > ZERO:
                status = "OVER-LINKED: excess counted as utilisation"
            elif linked == ZERO:
                status = "NOT LINKED"
            elif linked == t["cif"]:
                status = "COVERED BY BOE"
            else:
                status = "PARTIALLY COVERED BY BOE"
            invoices.append({
                "item_id": item.id, "sr": _s(item.serial_number),
                "invoice_number": t["invoice"],
                "invoice_date": t["date"].isoformat() if t["date"] else None,
                "customer": t["customer"],
                "cif_fc": _money(t["cif"]), "cif_inr": _money(t["inr"]), "qty": _qty(t["qty"]),
                "covered_by_boe": _money(covered), "uncovered": _money(t["cif"] - covered),
                "over_linked": _money(over_linked),
                "status": status, "source": {"type": "trade", "id": trade_id},
                "classification": "EXTERNAL",
            })
        for trade_id, t in _internal_sales_by_trade(item, data).items():
            record = data["trade_classifications"].get(trade_id)
            invoices.append({
                "item_id": item.id, "sr": _s(item.serial_number),
                "invoice_number": t["invoice"],
                "invoice_date": t["date"].isoformat() if t["date"] else None,
                "customer": t["customer"],
                "cif_fc": _money(t["cif"]), "cif_inr": _money(t["inr"]), "qty": _qty(t["qty"]),
                "covered_by_boe": _money(ZERO), "uncovered": _money(ZERO), "over_linked": _money(ZERO),
                "status": "INTERNAL TRADE: not external utilisation",
                "classification": "INTERNAL",
                "classification_reason": record.reason if record else "",
                "source": {"type": "trade", "id": trade_id},
            })

        for allot_id, ai_id, residue_c, residue_q, elsewhere in allot_residue:
            ai = next(a for a in data["allot_by_item"].get(item.id, []) if a.id == ai_id)
            cif = Decimal(ai.cif_fc or 0)
            qty = Decimal(ai.qty or 0)
            # BOE-linked CIF is the utilisation. The difference from the original is ignored, never outstanding.
            covered = allotment_link(ai, data, debit_rows).boe_linked_cif
            status = "LINKED BOE ON ANOTHER LICENCE / ITEM (review)" if elsewhere else (
                "LINKED TO BOE" if covered > ZERO else "OUTSTANDING")
            if sales_by_trade and residue_c > ZERO:
                status += "; same item has a sale (overlap unverified)"
            allotments.append({
                "item_id": item.id, "sr": _s(item.serial_number),
                "allotment_id": allot_id,
                "allotment_date": ai.allotment.created_on.date().isoformat() if ai.allotment.created_on else None,
                "customer": ai.allotment.company.name if ai.allotment.company_id else "",
                "cif_fc": _money(cif), "qty": _qty(qty),
                "boe_covered_cif": _money(covered), "outstanding_cif": _money(residue_c),
                "outstanding_qty": _qty(residue_q), "status": status,
                "source": {"type": "allotment_item", "id": ai_id},
            })

    return {"license_id": license_id, "boes": boes, "allotments": allotments, "invoices": invoices}
